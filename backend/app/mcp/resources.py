import json

from sqlalchemy import select, func

from app.mcp.server import mcp
from app.database import async_session
from app.models import Project, Run


@mcp.resource("allure://projects")
async def list_projects_resource() -> str:
    """所有项目列表，含最新运行状态"""
    async with async_session() as db:
        result = await db.execute(select(Project).order_by(Project.created_at.desc()))
        projects = result.scalars().all()
        items = []
        for p in projects:
            cnt = await db.execute(
                select(func.count(Run.id)).where(Run.project_key == p.key)
            )
            runs_count = cnt.scalar() or 0
            items.append({
                "key": p.key,
                "name": p.name,
                "description": p.description,
                "runs_count": runs_count,
            })
        return json.dumps(items, ensure_ascii=False)


@mcp.resource("allure://{project_key}/overview")
async def project_overview(project_key: str) -> str:
    """项目概览：基本信息 + 最近 run 统计"""
    async with async_session() as db:
        project = await db.get(Project, project_key)
        if not project:
            return json.dumps({"error": f"项目 '{project_key}' 不存在"})
        latest_res = await db.execute(
            select(Run)
            .where(Run.project_key == project_key, Run.status == "completed")
            .order_by(Run.created_at.desc())
            .limit(1)
        )
        latest = latest_res.scalar_one_or_none()
        overview = {
            "key": project.key,
            "name": project.name,
            "description": project.description,
            "max_runs": project.max_runs,
            "latest_run": {
                "id": str(latest.id) if latest else None,
                "status": latest.status if latest else None,
                "total": latest.total if latest else 0,
                "passed": latest.passed if latest else 0,
                "failed": latest.failed if latest else 0,
            } if latest else None,
        }
        return json.dumps(overview, ensure_ascii=False)


@mcp.resource("allure://{project_key}/runs/{run_id}/summary")
async def run_summary(project_key: str, run_id: str) -> str:
    """单次运行的统计摘要"""
    async with async_session() as db:
        run = await db.get(Run, run_id)
        if not run or run.project_key != project_key:
            return json.dumps({"error": "Run not found"})
        summary = {
            "id": str(run.id),
            "project_key": run.project_key,
            "status": run.status,
            "total": run.total,
            "passed": run.passed,
            "failed": run.failed,
            "broken": run.broken,
            "skipped": run.skipped,
            "duration_ms": run.duration_ms,
            "created_at": str(run.created_at) if run.created_at else None,
        }
        return json.dumps(summary, ensure_ascii=False)
