import io
import logging
import mimetypes
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTasks

from app.config import settings
from app.database import get_db
from app.models import Project, Run, TestResult, TestStep, TestAttachment
from app.schemas import (
    RunResponse,
    RunDetailResponse,
    RunListItem,
    TestResultSummary,
    TestResultDetail,
)
from app.services.allure_cli import generate_report, cleanup_history_for_runs
from app.services.result_parser import parse_results
from app.services.cleanup import cleanup_old_runs

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["reports"])

ALLOWED_EXTENSIONS = {".zip"}
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB


@router.post("/{project_key}/runs", response_model=RunResponse, status_code=202)
async def upload_results(
    project_key: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    branch: str | None = None,
    commit_hash: str | None = None,
):
    project = await db.get(Project, project_key)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = file.filename[file.filename.rfind("."):].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Only {ALLOWED_EXTENSIONS} files are allowed")

    run = Run(
        project_key=project_key,
        status="processing",
        branch=branch,
        commit_hash=commit_hash,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Read file content into memory
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        run.status = "failed"
        run.error_message = "Upload exceeds maximum size"
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(status_code=400, detail="Upload exceeds maximum size")

    # Extract zip
    results_dir = settings.results_dir(project_key, str(run.id))
    results_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            zf.extractall(results_dir)
    except zipfile.BadZipFile:
        run.status = "failed"
        run.error_message = "Invalid zip file"
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        raise HTTPException(status_code=400, detail="Invalid zip file")

    # If the zip contains a top-level allure-results dir, flatten it
    _flatten_results_dir(results_dir)

    background_tasks.add_task(
        _process_run,
        str(run.id),
        project_key,
        project.name,
        project.allure_config,
    )

    return _to_run_response(run)


@router.get("/{project_key}/runs", response_model=list[RunListItem])
async def list_runs(project_key: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_key)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Run).where(Run.project_key == project_key).order_by(Run.created_at.desc())
    )
    runs = result.scalars().all()
    return [RunListItem.model_validate(r) for r in runs]


@router.get("/{project_key}/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(
    project_key: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    run = await _get_run_or_404(project_key, run_id, db)
    detail = RunDetailResponse(
        id=run.id,
        project_key=run.project_key,
        status=run.status,
        branch=run.branch,
        commit_hash=run.commit_hash,
        total=run.total,
        passed=run.passed,
        failed=run.failed,
        broken=run.broken,
        skipped=run.skipped,
        unknown=run.unknown,
        duration_ms=run.duration_ms,
        error_message=run.error_message,
        environment=run.environment,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )

    result = await db.execute(
        select(TestResult)
        .where(TestResult.run_id == run.id)
        .order_by(TestResult.name)
    )
    test_results = result.scalars().all()
    detail.test_results = [TestResultSummary.model_validate(tr) for tr in test_results]
    return detail


async def _get_run_or_404(project_key: str, run_id: str, db: AsyncSession) -> Run:
    run = await db.get(Run, run_id)
    if not run or run.project_key != project_key:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def _to_run_response(run: Run) -> RunResponse:
    return RunResponse(
        id=run.id,
        project_key=run.project_key,
        status=run.status,
        branch=run.branch,
        commit_hash=run.commit_hash,
        total=run.total,
        passed=run.passed,
        failed=run.failed,
        broken=run.broken,
        skipped=run.skipped,
        unknown=run.unknown,
        duration_ms=run.duration_ms,
        error_message=run.error_message,
        environment=run.environment,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


def _flatten_results_dir(results_dir):
    """If the zip extracted to results_dir/allure-results/, move files up one level."""
    nested = results_dir / "allure-results"
    if nested.is_dir():
        for item in nested.iterdir():
            target = results_dir / item.name
            if not target.exists():
                shutil.move(str(item), str(target))
        nested.rmdir()


def _to_step_detail(step: TestStep):
    from app.schemas import TestStepDetail, TestAttachmentSummary
    children = [_to_step_detail(c) for c in (step.children or [])]
    attachments = [
        TestAttachmentSummary(id=a.id, name=a.name, source=a.source, type=a.type, size=a.size)
        for a in (step.attachments or [])
    ]
    return TestStepDetail(
        id=step.id,
        name=step.name,
        status=step.status,
        duration_ms=step.duration_ms,
        stage=step.stage,
        start_time=step.start_time,
        stop_time=step.stop_time,
        status_details=step.status_details,
        children=children,
        attachments=attachments,
    )


def _to_test_result_detail(tr: TestResult):
    from app.schemas import TestResultDetail, TestAttachmentSummary
    steps = [_to_step_detail(s) for s in (tr.steps or []) if s.parent_step_id is None]
    attachments = [
        TestAttachmentSummary(id=a.id, name=a.name, source=a.source, type=a.type, size=a.size)
        for a in (tr.attachments or [])
    ]
    return TestResultDetail(
        id=tr.id,
        uuid=tr.uuid,
        history_id=tr.history_id,
        full_name=tr.full_name,
        name=tr.name,
        description=tr.description,
        status=tr.status,
        stage=tr.stage,
        start_time=tr.start_time,
        stop_time=tr.stop_time,
        duration_ms=tr.duration_ms,
        test_case_id=tr.test_case_id,
        labels=tr.labels,
        links=tr.links,
        parameters=tr.parameters,
        status_details=tr.status_details,
        steps=steps,
        attachments=attachments,
    )


@router.get("/{project_key}/runs/{run_id}/tests/{test_result_id}", response_model=TestResultDetail)
async def get_test_result(
    project_key: str,
    run_id: str,
    test_result_id: str,
    db: AsyncSession = Depends(get_db),
):
    run = await _get_run_or_404(project_key, run_id, db)

    result = await db.execute(
        select(TestResult)
        .where(TestResult.id == test_result_id, TestResult.run_id == run.id)
        .options(
            selectinload(TestResult.steps).selectinload(TestStep.children).selectinload(TestStep.children),
            selectinload(TestResult.steps).selectinload(TestStep.attachments),
            selectinload(TestResult.attachments),
        )
    )
    tr = result.unique().scalar_one_or_none()
    if not tr:
        raise HTTPException(status_code=404, detail="Test result not found")

    return _to_test_result_detail(tr)


@router.get("/{project_key}/attachments/{attachment_id}")
async def download_attachment(
    project_key: str,
    attachment_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TestAttachment).where(TestAttachment.id == attachment_id)
    )
    att = result.scalar_one_or_none()
    if not att or not att.file_path:
        raise HTTPException(status_code=404, detail="Attachment not found")

    file = Path(att.file_path)
    if not file.exists():
        raise HTTPException(status_code=404, detail="Attachment file not found on disk")

    effective_type = att.type or ""
    if not effective_type:
        guessed, _ = mimetypes.guess_type(att.name or att.source)
        effective_type = guessed or "application/octet-stream"

    is_previewable = (
        effective_type.startswith("image/")
        or effective_type.startswith("text/")
        or effective_type in ("application/json", "application/pdf")
    )

    if is_previewable:
        return FileResponse(file, media_type=effective_type)
    else:
        return FileResponse(
            file,
            filename=att.name or att.source,
            media_type=effective_type,
        )


@router.delete("/{project_key}/runs/{run_id}", status_code=204)
async def delete_run(project_key: str, run_id: str, db: AsyncSession = Depends(get_db)):
    run = await _get_run_or_404(project_key, run_id, db)
    await db.delete(run)
    await db.commit()

    run_dir = settings.run_dir(project_key, run_id)
    if run_dir.exists():
        shutil.rmtree(run_dir)

    cleanup_history_for_runs(project_key, [run_id])


@router.post("/{project_key}/runs/{run_id}/regenerate", response_model=RunResponse)
async def regenerate_report(
    project_key: str,
    run_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_key)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    run = await _get_run_or_404(project_key, run_id, db)
    if run.status not in ("completed", "failed"):
        raise HTTPException(status_code=400, detail="Can only regenerate completed or failed runs")

    report_dir = settings.report_dir(project_key, str(run.id))
    if report_dir.exists():
        shutil.rmtree(report_dir)

    run.status = "processing"
    run.error_message = None
    await db.commit()
    await db.refresh(run)

    background_tasks.add_task(
        _regenerate_run,
        str(run.id),
        project_key,
        project.name,
        project.allure_config,
    )

    return _to_run_response(run)


@router.get("/{project_key}/reports/latest/{path:path}")
async def serve_latest_report(project_key: str, path: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_key)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Run)
        .where(Run.project_key == project_key, Run.status == "completed")
        .order_by(Run.created_at.desc())
        .limit(1)
    )
    latest_run = result.scalar_one_or_none()
    if not latest_run:
        raise HTTPException(status_code=404, detail="No completed reports yet")

    return await _serve_report_file(project_key, str(latest_run.id), path)


@router.get("/{project_key}/reports/{run_id}/{path:path}")
async def serve_report(project_key: str, run_id: str, path: str, db: AsyncSession = Depends(get_db)):
    run = await _get_run_or_404(project_key, run_id, db)
    if run.status != "completed":
        raise HTTPException(status_code=404, detail="Report not yet generated")
    return await _serve_report_file(project_key, run_id, path)


async def _serve_report_file(project_key: str, run_id: str, path: str):
    report_dir = settings.report_dir(project_key, run_id)

    target = report_dir / (path or "index.html")
    if not target.exists():
        target = report_dir / "index.html"
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(target)


async def _process_run(run_id: str, project_key: str, project_name: str, allure_config: str | None = None) -> None:
    from app.database import async_session

    async with async_session() as db:
        run = await db.get(Run, run_id)
        if not run:
            return

        try:
            await parse_results(run, db)
            await db.commit()
            await generate_report(project_key, run_id, project_name, allure_config)

            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()

            await _cleanup_if_needed(project_key)

        except Exception as e:
            logger.exception("Failed to process run %s: %s", run_id, e)
            run.status = "failed"
            run.error_message = str(e)[:1000]
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()


async def _cleanup_if_needed(project_key: str):
    from app.database import async_session
    async with async_session() as cleanup_db:
        project = await cleanup_db.get(Project, project_key)
        if project:
            await cleanup_old_runs(project, cleanup_db)


async def _regenerate_run(run_id: str, project_key: str, project_name: str, allure_config: str | None = None) -> None:
    from app.database import async_session

    async with async_session() as db:
        run = await db.get(Run, run_id)
        if not run:
            return

        try:
            await generate_report(project_key, run_id, project_name, allure_config)

            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as e:
            logger.exception("Failed to regenerate report for run %s: %s", run_id, e)
            run.status = "failed"
            run.error_message = str(e)[:1000]
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()
