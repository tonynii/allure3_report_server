import shutil
import logging
from datetime import datetime, timezone
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models import Project, Run
from app.services.allure_cli import cleanup_history_for_runs

logger = logging.getLogger(__name__)


async def cleanup_old_runs(project: Project, db: AsyncSession) -> int:
    """Delete oldest runs exceeding max_runs. Returns number deleted."""
    count_query = select(func.count(Run.id)).where(
        Run.project_key == project.key, Run.status == "completed"
    )
    result = await db.execute(count_query)
    total = result.scalar() or 0

    to_delete = max(0, total - project.max_runs)
    if to_delete <= 0:
        return 0

    # Find oldest completed runs to delete
    q = (
        select(Run.id)
        .where(Run.project_key == project.key, Run.status == "completed")
        .order_by(Run.created_at.asc())
        .limit(to_delete)
    )
    result = await db.execute(q)
    old_ids = [row[0] for row in result.all()]

    for run_id in old_ids:
        run_dir = settings.run_dir(project.key, str(run_id))
        if run_dir.exists():
            shutil.rmtree(run_dir)
            logger.info("Deleted run directory: %s", run_dir)

    cleanup_history_for_runs(project.key, [str(rid) for rid in old_ids])

    stmt = delete(Run).where(Run.id.in_(old_ids))
    await db.execute(stmt)
    await db.commit()

    logger.info("Cleaned up %d old runs for project %s", len(old_ids), project.key)
    return len(old_ids)
