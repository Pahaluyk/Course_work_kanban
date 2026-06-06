import uuid
import csv
import io
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import Task, Project, ProjectMember, User
from app.schemas import AnalyticsOut, TaskProgress, MemberLoad
from app.services.auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])


async def check_project_access(project_id: uuid.UUID, user: User, db: AsyncSession) -> Project:
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


@router.get("/project/{project_id}")
async def get_analytics(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await check_project_access(project_id, current_user, db)
    today = date.today()

    # Task progress by status
    status_result = await db.execute(
        select(Task.status, func.count(Task.id).label("cnt"))
        .where(Task.project_id == project_id)
        .group_by(Task.status)
    )
    status_rows = status_result.all()
    task_progress = [TaskProgress(status=r.status, count=r.cnt) for r in status_rows]
    total_tasks = sum(p.count for p in task_progress)

    # Overdue count
    overdue_result = await db.execute(
        select(func.count(Task.id))
        .where(
            Task.project_id == project_id,
            Task.due_date < today,
            Task.status != "done",
        )
    )
    overdue_count = overdue_result.scalar() or 0

    # Member workload
    members_result = await db.execute(
        select(ProjectMember).options(selectinload(ProjectMember.user))
        .where(ProjectMember.project_id == project_id)
    )
    members = members_result.scalars().all()

    # Also include owner
    owner_result = await db.execute(select(User).where(User.id == project.owner_id))
    owner = owner_result.scalar_one_or_none()

    all_users = {m.user_id: m.user for m in members}
    if owner:
        all_users[owner.id] = owner

    member_load = []
    for user_id, user in all_users.items():
        tasks_result = await db.execute(
            select(Task).where(Task.project_id == project_id, Task.assignee_id == user_id)
        )
        user_tasks = tasks_result.scalars().all()
        done = sum(1 for t in user_tasks if t.status == "done")
        overdue = sum(1 for t in user_tasks if t.due_date and t.due_date < today and t.status != "done")
        member_load.append(MemberLoad(
            username=user.username,
            total=len(user_tasks),
            done=done,
            overdue=overdue,
        ))

    return AnalyticsOut(
        project_name=project.name,
        task_progress=task_progress,
        member_load=member_load,
        overdue_count=overdue_count,
        total_tasks=total_tasks,
    )


@router.get("/project/{project_id}/export/csv")
async def export_csv(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export full project task report as CSV."""
    project = await check_project_access(project_id, current_user, db)

    # Only manager can export
    if current_user.role == "observer":
        raise HTTPException(status_code=403, detail="Наблюдатель не может экспортировать данные")

    result = await db.execute(
        select(Task)
        .options(selectinload(Task.assignee))
        .where(Task.project_id == project_id)
        .order_by(Task.created_at)
    )
    tasks = result.scalars().all()
    today = date.today()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")

    # Header
    writer.writerow([
        "ID", "Название", "Описание", "Статус", "Приоритет",
        "Срок", "Исполнитель", "Просрочена", "Дата создания"
    ])

    for task in tasks:
        is_overdue = (
            task.due_date and task.due_date < today and task.status != "done"
        )
        writer.writerow([
            str(task.id),
            task.title,
            task.description or "",
            task.status,
            task.priority,
            str(task.due_date) if task.due_date else "",
            task.assignee.username if task.assignee else "",
            "Да" if is_overdue else "Нет",
            str(task.created_at.date()),
        ])

    output.seek(0)
    safe_name = f"report_{project.id}_{today}.csv"

    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={safe_name}"},
    )
