import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from app.database import engine, Base
from app.routers import auth, projects, tasks, attachments, analytics


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Task Tracker",
    description="Веб-приложение для командного управления и мониторинга задач с канбан-досками",
    version="1.0.0",
    lifespan=lifespan,
)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(attachments.router)
app.include_router(analytics.router)


@app.get("/")
async def root():
    return RedirectResponse(url="/projects/")


@app.get("/health")
async def health():
    return {"status": "ok", "app": "Task Tracker"}
