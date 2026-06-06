import uuid
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, EmailStr


# ── Auth ──────────────────────────────────────────────────────────────────────
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "developer"  # manager | developer | observer


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


# ── Project ───────────────────────────────────────────────────────────────────
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    owner_id: uuid.UUID
    created_at: datetime
    owner: Optional[UserOut] = None

    model_config = {"from_attributes": True}


# ── Task ──────────────────────────────────────────────────────────────────────
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "backlog"
    priority: str = "medium"
    due_date: Optional[date] = None
    assignee_id: Optional[uuid.UUID] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    assignee_id: Optional[uuid.UUID] = None


class TaskOut(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str]
    status: str
    priority: str
    due_date: Optional[date]
    project_id: uuid.UUID
    assignee_id: Optional[uuid.UUID]
    created_at: datetime
    assignee: Optional[UserOut] = None

    model_config = {"from_attributes": True}


# ── Attachment ────────────────────────────────────────────────────────────────
class AttachmentOut(BaseModel):
    id: uuid.UUID
    filename: str
    filepath: str
    task_id: uuid.UUID
    uploaded_by: uuid.UUID
    uploaded_at: datetime
    uploader: Optional[UserOut] = None

    model_config = {"from_attributes": True}


# ── Analytics ────────────────────────────────────────────────────────────────
class TaskProgress(BaseModel):
    status: str
    count: int


class MemberLoad(BaseModel):
    username: str
    total: int
    done: int
    overdue: int


class AnalyticsOut(BaseModel):
    project_name: str
    task_progress: list[TaskProgress]
    member_load: list[MemberLoad]
    overdue_count: int
    total_tasks: int
