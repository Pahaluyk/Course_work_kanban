import uuid
import os
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models import Attachment, Task, ProjectMember, Project
from app.schemas import AttachmentOut
from app.services.auth import get_current_user
from app.models import User
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/attachments", tags=["attachments"])
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "app/static/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


async def check_task_access(task_id: uuid.UUID, user: User, db: AsyncSession) -> Task:
    result = await db.execute(
        select(Task).options(selectinload(Task.attachments)).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    # Check project access
    proj_result = await db.execute(select(Project).where(Project.id == task.project_id))
    project = proj_result.scalar_one_or_none()
    if project.owner_id == user.id:
        return task
    member = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == task.project_id,
            ProjectMember.user_id == user.id
        )
    )
    if not member.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Нет доступа к задаче")
    return task


@router.get("/task/{task_id}")
async def list_attachments(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await check_task_access(task_id, current_user, db)
    result = await db.execute(
        select(Attachment)
        .options(selectinload(Attachment.uploader))
        .where(Attachment.task_id == task_id)
        .order_by(Attachment.uploaded_at)
    )
    attachments = result.scalars().all()
    return [AttachmentOut.model_validate(a) for a in attachments]


@router.post("/task/{task_id}/upload")
async def upload_attachment(
    task_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "observer":
        raise HTTPException(status_code=403, detail="Наблюдатель не может загружать файлы")

    task = await check_task_access(task_id, current_user, db)

    # Validate file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Файл слишком большой (максимум 10 МБ)")

    # Save file with unique name
    ext = os.path.splitext(file.filename)[1]
    unique_name = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(UPLOAD_DIR, unique_name)

    async with aiofiles.open(filepath, "wb") as f:
        await f.write(content)

    attachment = Attachment(
        filename=file.filename,
        filepath=filepath,
        task_id=task_id,
        uploaded_by=current_user.id,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return AttachmentOut.model_validate(attachment)


@router.get("/download/{attachment_id}")
async def download_attachment(
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Вложение не найдено")
    await check_task_access(attachment.task_id, current_user, db)
    if not os.path.exists(attachment.filepath):
        raise HTTPException(status_code=404, detail="Файл не найден на сервере")
    return FileResponse(
        path=attachment.filepath,
        filename=attachment.filename,
        media_type="application/octet-stream",
    )


@router.delete("/{attachment_id}")
async def delete_attachment(
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "observer":
        raise HTTPException(status_code=403, detail="Наблюдатель не может удалять файлы")

    result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Вложение не найдено")

    await check_task_access(attachment.task_id, current_user, db)

    # Only uploader or manager can delete
    if current_user.role != "manager" and attachment.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="Нет прав на удаление")

    if os.path.exists(attachment.filepath):
        os.remove(attachment.filepath)

    await db.delete(attachment)
    await db.commit()
    return {"message": "Вложение удалено"}
