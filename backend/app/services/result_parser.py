import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models import Run, TestResult, TestStep, TestAttachment

logger = logging.getLogger(__name__)

# Allure status → internal enum
_STATUS_MAP = {
    "passed": "passed",
    "failed": "failed",
    "broken": "broken",
    "skipped": "skipped",
    "unknown": "unknown",
}


def _ts_to_dt(ts: int | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)


async def parse_results(run: Run, db: AsyncSession) -> None:
    """
    Parse all *-result.json files from a run's allure-results directory
    and write structured data into PostgreSQL.
    """
    results_dir = settings.results_dir(run.project_key, str(run.id))
    result_files = sorted(results_dir.glob("*-result.json"))

    if not result_files:
        logger.warning("No result files found in %s", results_dir)
        raise ValueError("No allure result files found in uploaded archive")

    stats = {"passed": 0, "failed": 0, "broken": 0, "skipped": 0, "unknown": 0}
    earliest_start = None
    latest_stop = None

    for rf in result_files:
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Skipping invalid result file %s: %s", rf.name, e)
            continue

        start_ts = data.get("start")
        stop_ts = data.get("stop")
        start_dt = _ts_to_dt(start_ts) if start_ts else None
        stop_dt = _ts_to_dt(stop_ts) if stop_ts else None
        duration = (stop_ts - start_ts) if (start_ts and stop_ts) else None

        status = _STATUS_MAP.get(data.get("status", "unknown"), "unknown")
        stats[status] += 1

        if start_dt and (earliest_start is None or start_dt < earliest_start):
            earliest_start = start_dt
        if stop_dt and (latest_stop is None or stop_dt > latest_stop):
            latest_stop = stop_dt

        tr = TestResult(
            run_id=run.id,
            uuid=data.get("uuid", ""),
            history_id=data.get("historyId"),
            test_case_id=data.get("testCaseId"),
            full_name=data.get("fullName"),
            name=data.get("name", "Unknown"),
            description=data.get("description"),
            status=status,
            stage=data.get("stage"),
            start_time=start_dt,
            stop_time=stop_dt,
            duration_ms=duration,
            labels=data.get("labels"),
            links=data.get("links"),
            parameters=data.get("parameters"),
            status_details=data.get("statusDetails"),
        )
        db.add(tr)
        await db.flush()

        await _parse_steps(tr, data.get("steps", []), db)
        await _parse_attachments(tr, data.get("attachments", []), results_dir, db)

    # Parse environment files
    await _parse_environment(run, results_dir)

    run.total = sum(stats.values())
    run.passed = stats["passed"]
    run.failed = stats["failed"]
    run.broken = stats["broken"]
    run.skipped = stats["skipped"]
    run.unknown = stats["unknown"]
    if earliest_start and latest_stop:
        run.duration_ms = int((latest_stop - earliest_start).total_seconds() * 1000)

    logger.info("Parsed %d results for run %s", len(result_files), run.id)


async def _parse_steps(
    test_result: TestResult,
    steps: list[dict],
    db: AsyncSession,
    parent: TestStep | None = None,
) -> None:
    for s in steps:
        start_ts = s.get("start")
        stop_ts = s.get("stop")
        duration = (stop_ts - start_ts) if (start_ts and stop_ts) else None

        step = TestStep(
            test_result_id=test_result.id,
            parent_step_id=parent.id if parent else None,
            name=s.get("name", ""),
            status=_STATUS_MAP.get(s.get("status", "unknown"), "unknown"),
            stage=s.get("stage"),
            start_time=_ts_to_dt(start_ts),
            stop_time=_ts_to_dt(stop_ts),
            duration_ms=duration,
            status_details=s.get("statusDetails"),
        )
        db.add(step)
        await db.flush()

        await _parse_attachments(
            test_result, s.get("attachments", []),
            settings.results_dir(test_result.run.project_key, str(test_result.run.id)),
            db, step=step,
        )
        await _parse_steps(test_result, s.get("steps", []), db, parent=step)


async def _parse_attachments(
    test_result: TestResult,
    attachments: list[dict],
    results_dir: Path,
    db: AsyncSession,
    step: TestStep | None = None,
) -> None:
    for a in attachments:
        source = a.get("source", "")
        file_path = None
        size = 0

        if source:
            src_file = results_dir / source
            if src_file.exists():
                size = src_file.stat().st_size
                file_path = str(src_file)

        att = TestAttachment(
            test_result_id=test_result.id,
            step_id=step.id if step else None,
            name=a.get("name", ""),
            source=source,
            type=a.get("type", ""),
            file_path=file_path,
            size=size,
        )
        db.add(att)


async def _parse_environment(run: Run, results_dir: Path) -> None:
    """Parse environment.xml or environment.properties into run.environment."""
    xml_file = results_dir / "environment.xml"
    props_file = results_dir / "environment.properties"

    if xml_file.exists():
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(xml_file)
            root = tree.getroot()
            items = []
            for p in root.findall("parameter"):
                k = p.findtext("key", "")
                v = p.findtext("value", "")
                if k:
                    items.append({"key": k, "value": v})
            run.environment = items
            return
        except Exception as e:
            logger.warning("Failed to parse environment.xml: %s", e)

    if props_file.exists():
        try:
            items = []
            for line in props_file.read_text(errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    items.append({"key": k.strip(), "value": v.strip()})
            run.environment = items
        except Exception as e:
            logger.warning("Failed to parse environment.properties: %s", e)
