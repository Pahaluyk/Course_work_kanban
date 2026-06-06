import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import Task, Project, ProjectMember, User
from app.schemas import TaskCreate, TaskUpdate, TaskOut
from app.services.auth import get_current_user, require_role

router = APIRouter(prefix="/tasks", tags=["tasks"])
templates = Jinja2Templates(directory="templates")

VALID_STATUSES = {"backlog", "todo", "in_progress", "review", "done"}
VALID_PRIORITIES = {"low", "medium", "high"}


async def check_project_access(project_id: uuid.UUID, user: User, db: AsyncSession):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    if project.owner_id == user.id:
        return project
    member = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id
        )
    )
    if not member.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Нет доступа к проекту")
    return project


@router.get("/api/{project_id}/list")
async def list_tasks(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await check_project_access(project_id, current_user, db)
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.assignee))
        .where(Task.project_id == project_id)
        .order_by(Task.created_at)
    )
    tasks = result.scalars().all()
    return [TaskOut.model_validate(t) for t in tasks]


@router.post("/api/{project_id}/create")
async def create_task(
    project_id: uuid.UUID,
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await check_project_access(project_id, current_user, db)
    # Only manager can create tasks
    result = await db.execute(select(Project).where(Project.id == project_id))
    proj = result.scalar_one_or_none()
    if proj.owner_id != current_user.id and current_user.role != "manager":
        raise HTTPException(status_code=403, detail="Только менеджер может создавать задачи")
    if data.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Недопустимый статус")
    if data.priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail="Недопустимый приоритет")
    task = Task(
        title=data.title,
        description=data.description,
        status=data.status,
        priority=data.priority,
        due_date=data.due_date,
        project_id=project_id,
        assignee_id=data.assignee_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {"id": str(task.id), "title": task.title}


@router.get("/api/detail/{task_id}")
async def get_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.assignee), selectinload(Task.attachments).selectinload(Task.attachments))
        .where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    await check_project_access(task.project_id, current_user, db)
    return TaskOut.model_validate(task)


@router.put("/api/detail/{task_id}")
async def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    await check_project_access(task.project_id, current_user, db)

    # Developers can only update status of their own tasks
    if current_user.role == "developer":
        if task.assignee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Можно редактировать только свои задачи")
        if data.status is not None:
            if data.status not in VALID_STATUSES:
                raise HTTPException(status_code=400, detail="Недопустимый статус")
            task.status = data.status
    elif current_user.role == "observer":
        raise HTTPException(status_code=403, detail="Наблюдатель не может редактировать задачи")
    else:
        # Manager — full update
        if data.title is not None:
            task.title = data.title
        if data.description is not None:
            task.description = data.description
        if data.status is not None:
            if data.status not in VALID_STATUSES:
                raise HTTPException(status_code=400, detail="Недопустимый статус")
            task.status = data.status
        if data.priority is not None:
            if data.priority not in VALID_PRIORITIES:
                raise HTTPException(status_code=400, detail="Недопустимый приоритет")
            task.priority = data.priority
        if data.due_date is not None:
            task.due_date = data.due_date
        if data.assignee_id is not None:
            task.assignee_id = data.assignee_id

    await db.commit()
    return {"message": "Задача обновлена"}


@router.patch("/api/detail/{task_id}/status")
async def update_task_status(
    task_id: uuid.UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Quick status update for drag & drop on kanban board."""
    new_status = payload.get("status")
    if new_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Недопустимый статус")

    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    await check_project_access(task.project_id, current_user, db)

    if current_user.role == "observer":
        raise HTTPException(status_code=403, detail="Наблюдатель не может изменять задачи")
    if current_user.role == "developer" and task.assignee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Разработчик может менять статус только своих задач")

    task.status = new_status
    await db.commit()
    return {"message": "Статус обновлён"}


@router.delete("/api/detail/{task_id}")
async def delete_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("manager")),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    await db.delete(task)
    await db.commit()
    return {"message": "Задача удалена"}
