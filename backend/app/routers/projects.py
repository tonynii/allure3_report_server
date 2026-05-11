from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Project, Run
from app.schemas import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.get(Project, body.key)
    if existing:
        raise HTTPException(status_code=409, detail=f"Project '{body.key}' already exists")

    project = Project(
        key=body.key,
        name=body.name,
        description=body.description,
        max_runs=body.max_runs,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return _to_project_response(project)


@router.get("", response_model=list[ProjectListResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = result.scalars().all()

    responses = []
    for p in projects:
        runs_count = await _count_runs(p.key, db)
        latest_status = await _latest_run_status(p.key, db)
        responses.append(ProjectListResponse(
            key=p.key,
            name=p.name,
            description=p.description,
            runs_count=runs_count,
            latest_run_status=latest_status,
            created_at=p.created_at,
        ))
    return responses


@router.get("/{project_key}", response_model=ProjectResponse)
async def get_project(project_key: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_key)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    runs_count = await _count_runs(project.key, db)
    latest_status = await _latest_run_status(project.key, db)
    return ProjectResponse(
        key=project.key,
        name=project.name,
        description=project.description,
        max_runs=project.max_runs,
        runs_count=runs_count,
        latest_run_status=latest_status,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.put("/{project_key}", response_model=ProjectResponse)
async def update_project(project_key: str, body: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_key)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
    if body.max_runs is not None:
        project.max_runs = body.max_runs
    await db.commit()
    await db.refresh(project)
    return _to_project_response(project)


@router.delete("/{project_key}", status_code=204)
async def delete_project(project_key: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_key)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete entire project directory
    import shutil
    from app.config import settings
    project_dir = settings.project_dir(project_key)
    if project_dir.exists():
        shutil.rmtree(project_dir)

    await db.delete(project)
    await db.commit()


async def _count_runs(project_key: str, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count(Run.id)).where(Run.project_key == project_key)
    )
    return result.scalar() or 0


async def _latest_run_status(project_key: str, db: AsyncSession) -> str | None:
    result = await db.execute(
        select(Run.status).where(Run.project_key == project_key).order_by(Run.created_at.desc()).limit(1)
    )
    row = result.first()
    return row[0] if row else None


def _to_project_response(p: Project) -> ProjectResponse:
    return ProjectResponse(
        key=p.key,
        name=p.name,
        description=p.description,
        max_runs=p.max_runs,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )
