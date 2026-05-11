from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Run, TestResult

router = APIRouter(prefix="/api", tags=["compare"])


class CompareRequest(BaseModel):
    runs: list[dict]  # [{project, run}, ...]
    status_change_only: bool = False
    keyword: str = ""


@router.post("/compare")
async def compare_runs(body: CompareRequest, db: AsyncSession = Depends(get_db)):
    if len(body.runs) < 2:
        return {"error": "至少选择 2 个 Run"}

    # Load all selected runs
    run_data = []
    for item in body.runs:
        r = await db.get(Run, item["run"])
        if not r or r.project_key != item["project"]:
            return {"error": f"Run {item['run']} not found"}
        trs = await db.execute(
            select(TestResult).where(TestResult.run_id == r.id)
        )
        run_data.append({
            "run_id": str(r.id),
            "project": r.project_key,
            "branch": r.branch or "",
            "label": f"{r.project_key}/{r.branch or '?'}",
            "tests": {t.history_id or t.full_name: t for t in trs.scalars().all() if t.history_id},
        })

    # Collect all historyIds
    all_ids: set[str] = set()
    for rd in run_data:
        all_ids.update(rd["tests"].keys())

    # Filter by keyword
    if body.keyword:
        kw = body.keyword.lower()
        all_ids = {
            hid for hid in all_ids
            if any(
                rd["tests"].get(hid) and (
                    kw in (rd["tests"][hid].name or "").lower()
                    or kw in (rd["tests"][hid].full_name or "").lower()
                )
                for rd in run_data
            )
        }

    # Build comparison matrix
    tests = []
    summary = {"all_pass": 0, "all_fail": 0, "mixed": 0, "flaky": 0}

    for hid in sorted(all_ids):
        results = {}
        statuses = []
        names = set()
        labels = None

        for rd in run_data:
            tr = rd["tests"].get(hid)
            if tr:
                results[rd["run_id"]] = {
                    "status": tr.status,
                    "duration_ms": tr.duration_ms,
                    "error_message": _extract_message(tr),
                    "labels": tr.labels,
                }
                statuses.append(tr.status)
                names.add(tr.name)
                if tr.full_name:
                    names.add(tr.full_name)
                if tr.labels and not labels:
                    labels = tr.labels

        if body.status_change_only and len(set(statuses)) <= 1:
            continue

        # Classify
        unique_statuses = set(statuses)
        if unique_statuses == {"passed"}:
            cat = "all_pass"
        elif unique_statuses <= {"failed", "broken"}:
            cat = "all_fail"
        else:
            fail_count = sum(1 for s in statuses if s in ("failed", "broken"))
            pass_count = sum(1 for s in statuses if s == "passed")
            if fail_count > 0 and pass_count > 0:
                cat = "flaky" if fail_count >= 2 else "mixed"
            else:
                cat = "mixed"

        summary[cat] += 1

        if not body.status_change_only or cat in ("mixed", "flaky", "all_fail"):
            tests.append({
                "historyId": hid,
                "name": sorted(names)[0] if names else hid[:16],
                "fullName": sorted(names)[-1] if len(names) > 1 else "",
                "labels": labels,
                "results": results,
                "summary": cat,
            })

    return {
        "columns": [
            {
                "run_id": rd["run_id"],
                "project": rd["project"],
                "branch": rd["branch"],
                "label": rd["label"],
                "total": len(rd["tests"]),
                "passed": sum(1 for t in rd["tests"].values() if t.status == "passed"),
                "failed": sum(1 for t in rd["tests"].values() if t.status in ("failed", "broken")),
            }
            for rd in run_data
        ],
        "summary": summary,
        "tests": tests,
    }


def _extract_message(tr: TestResult) -> str | None:
    if tr.status_details and isinstance(tr.status_details, dict):
        return tr.status_details.get("message")
    return None
