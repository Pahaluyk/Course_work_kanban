import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import Project, ProjectMember, User
from app.schemas import ProjectCreate, ProjectUpdate, ProjectOut, UserOut
from app.services.auth import get_current_user, require_role

router = APIRouter(prefix="/projects", tags=["projects"])
templates = Jinja2Templates(directory="templates")


async def get_project_or_404(project_id: uuid.UUID, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.owner), selectinload(Project.members).selectinload(ProjectMember.user))
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return project


async def check_project_access(project: Project, user: User, db: AsyncSession):
    """Check if user is owner or member of a project."""
    if project.owner_id == user.id:
        return
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Нет доступа к проекту")


# ── Pages ─────────────────────────────────────────────────────────────────────
@router.get("/", response_class=HTMLResponse)
async def projects_page(request: Request):
    return templates.TemplateResponse("projects/list.html", {"request": request})


@router.get("/{project_id}/board", response_class=HTMLResponse)
async def board_page(request: Request, project_id: uuid.UUID):
    return templates.TemplateResponse("projects/board.html", {"request": request, "project_id": str(project_id)})


@router.get("/{project_id}/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, project_id: uuid.UUID):
    return templates.TemplateResponse("analytics/report.html", {"request": request, "project_id": str(project_id)})


# ── API ───────────────────────────────────────────────────────────────────────
@router.get("/api/list")
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Return projects where user is owner or member
    owned = await db.execute(
        select(Project).options(selectinload(Project.owner)).where(Project.owner_id == current_user.id)
    )
    member_proj_ids = await db.execute(
        select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id)
    )
    member_ids = [r[0] for r in member_proj_ids.all()]
    member_projects = await db.execute(
        select(Project).options(selectinload(Project.owner)).where(Project.id.in_(member_ids))
    )
    all_projects = {p.id: p for p in owned.scalars().all()}
    for p in member_projects.scalars().all():
        all_projects[p.id] = p
    return [ProjectOut.model_validate(p) for p in all_projects.values()]


@router.post("/api/create")
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("manager")),
):
    project = Project(name=data.name, description=data.description, owner_id=current_user.id)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return {"id": str(project.id), "name": project.name}


@router.get("/api/{project_id}")
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_or_404(project_id, db)
    await check_project_access(project, current_user, db)
    return ProjectOut.model_validate(project)


@router.put("/api/{project_id}")
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("manager")),
):
    project = await get_project_or_404(project_id, db)
    if project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Только владелец может редактировать проект")
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    await db.commit()
    return {"message": "Обновлено"}


@router.delete("/api/{project_id}")
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("manager")),
):
    project = await get_project_or_404(project_id, db)
    if project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Только владелец может удалить проект")
    await db.delete(project)
    await db.commit()
    return {"message": "Удалено"}


# ── Members ───────────────────────────────────────────────────────────────────
@router.get("/api/{project_id}/members")
async def list_members(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_or_404(project_id, db)
    await check_project_access(project, current_user, db)
    result = await db.execute(
        select(ProjectMember).options(selectinload(ProjectMember.user))
        .where(ProjectMember.project_id == project_id)
    )
    members = result.scalars().all()
    return [UserOut.model_validate(m.user) for m in members]


@router.post("/api/{project_id}/members/{user_id}")
async def add_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("manager")),
):
    project = await get_project_or_404(project_id, db)
    if project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Только владелец может добавлять участников")
    # Check user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    # Check not already a member
    existing = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Уже является участником")
    member = ProjectMember(project_id=project_id, user_id=user_id)
    db.add(member)
    await db.commit()
    return {"message": "Участник добавлен"}


@router.delete("/api/{project_id}/members/{user_id}")
async def remove_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("manager")),
):
    project = await get_project_or_404(project_id, db)
    if project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Только владелец может удалять участников")
    result = await db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Участник не найден")
    await db.delete(member)
    await db.commit()
    return {"message": "Участник удалён"}


@router.get("/api/users/all")
async def list_all_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return [UserOut.model_validate(u) for u in users]
