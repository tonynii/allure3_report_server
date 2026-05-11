import os
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Project, Run
from app.config import settings

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    # Project count
    proj_count_res = await db.execute(select(func.count(Project.key)))
    project_count = proj_count_res.scalar() or 0

    # Total runs
    runs_count_res = await db.execute(select(func.count(Run.id)))
    total_runs = runs_count_res.scalar() or 0

    # Projects with latest run
    proj_res = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = proj_res.scalars().all()

    project_list = []
    total_passed = 0
    total_tests = 0

    for p in projects:
        runs_cnt_res = await db.execute(
            select(func.count(Run.id)).where(Run.project_key == p.key)
        )
        runs_count = runs_cnt_res.scalar() or 0

        latest_res = await db.execute(
            select(Run)
            .where(Run.project_key == p.key, Run.status == "completed")
            .order_by(Run.created_at.desc())
            .limit(1)
        )
        latest = latest_res.scalar_one_or_none()

        project_list.append({
            "key": p.key,
            "name": p.name,
            "description": p.description,
            "runs_count": runs_count,
            "max_runs": p.max_runs,
            "latest_run": {
                "id": str(latest.id) if latest else None,
                "status": latest.status if latest else None,
                "passed": latest.passed if latest else 0,
                "failed": latest.failed if latest else 0,
                "broken": latest.broken if latest else 0,
                "skipped": latest.skipped if latest else 0,
                "total": latest.total if latest else 0,
                "duration_ms": latest.duration_ms if latest else None,
                "created_at": str(latest.created_at) if latest else None,
            } if latest else None,
        })

        if latest:
            total_passed += latest.passed or 0
            total_tests += latest.total or 0

    # Overall pass rate
    overall_pass_rate = round(total_passed / total_tests, 4) if total_tests > 0 else 0

    # Recent runs across all projects
    recent_res = await db.execute(
        select(Run, Project.name)
        .join(Project, Run.project_key == Project.key)
        .order_by(Run.created_at.desc())
        .limit(10)
    )
    recent_runs = []
    for run, proj_name in recent_res.all():
        recent_runs.append({
            "id": str(run.id),
            "project_key": run.project_key,
            "project_name": proj_name,
            "status": run.status,
            "passed": run.passed,
            "failed": run.failed,
            "broken": run.broken,
            "skipped": run.skipped,
            "total": run.total,
            "duration_ms": run.duration_ms,
            "created_at": str(run.created_at) if run.created_at else None,
        })

    return {
        "project_count": project_count,
        "total_runs": total_runs,
        "overall_pass_rate": overall_pass_rate,
        "projects": project_list,
        "recent_runs": recent_runs,
    }


def _dir_size(p):
    if not p.exists():
        return 0
    total = 0
    for f in p.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total


def _format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    else:
        return f"{n / (1024 * 1024):.1f} MB"


_allure_version: str | None = None


def _get_allure_version() -> str:
    global _allure_version
    if _allure_version is not None:
        return _allure_version
    try:
        import subprocess
        result = subprocess.run(["npx", "allure", "--version"], capture_output=True, text=True, timeout=10)
        _allure_version = result.stdout.strip() or "unknown"
    except Exception:
        _allure_version = "unknown"
    return _allure_version


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    proj_res = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = proj_res.scalars().all()

    project_list = []
    for p in projects:
        runs_cnt_res = await db.execute(
            select(func.count(Run.id)).where(Run.project_key == p.key)
        )
        runs_count = runs_cnt_res.scalar() or 0

        project_dir = settings.project_dir(p.key)
        storage = _dir_size(project_dir)

        project_list.append({
            "key": p.key,
            "name": p.name,
            "description": p.description,
            "runs_count": runs_count,
            "max_runs": p.max_runs,
            "storage_bytes": storage,
            "storage_human": _format_bytes(storage),
            "created_at": str(p.created_at) if p.created_at else None,
        })

    return {
        "data_dir": settings.data_dir,
        "default_max_runs": settings.max_runs_default,
        "allure_version": _get_allure_version(),
        "projects": project_list,
    }
