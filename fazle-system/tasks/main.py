# ============================================================
# Fazle Task Engine — Scheduling, reminders, and automation
# ============================================================
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import httpx
import logging
import uuid
from typing import Optional
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fazle-task-engine")


class Settings(BaseSettings):
    brain_url: str = "http://fazle-brain:8200"
    memory_url: str = "http://fazle-memory:8300"
    dograh_api_url: str = "http://dograh-api:8000"

    class Config:
        env_prefix = "FAZLE_"


settings = Settings()

app = FastAPI(title="Fazle Task Engine — Scheduling & Automation", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = AsyncIOScheduler()

# In-memory task store
tasks: dict[str, dict] = {}

TASK_TYPES = {"reminder", "call", "summary", "instruction", "custom"}


@app.on_event("startup")
async def startup():
    scheduler.start()
    logger.info("Task scheduler started")


@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()


# ── Health ──────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "fazle-task-engine", "timestamp": datetime.utcnow().isoformat()}


# ── Task models ─────────────────────────────────────────────
class TaskCreateRequest(BaseModel):
    title: str
    description: str = ""
    scheduled_at: Optional[str] = None
    task_type: str = "reminder"
    payload: dict = Field(default_factory=dict)


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str
    task_type: str
    status: str
    scheduled_at: Optional[str]
    created_at: str
    payload: dict


# ── Create task ─────────────────────────────────────────────
@app.post("/tasks", response_model=TaskResponse)
async def create_task(request: TaskCreateRequest):
    """Create a new scheduled task or reminder."""
    if request.task_type not in TASK_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid task type. Must be one of: {TASK_TYPES}")

    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    task = {
        "id": task_id,
        "title": request.title,
        "description": request.description,
        "task_type": request.task_type,
        "status": "pending",
        "scheduled_at": request.scheduled_at,
        "created_at": now,
        "payload": request.payload,
    }

    tasks[task_id] = task

    # Schedule if a time is provided
    if request.scheduled_at:
        try:
            trigger_time = datetime.fromisoformat(request.scheduled_at)
            scheduler.add_job(
                _execute_task,
                trigger=DateTrigger(run_date=trigger_time),
                args=[task_id],
                id=task_id,
                replace_existing=True,
            )
            logger.info(f"Task {task_id} scheduled for {request.scheduled_at}")
        except ValueError:
            logger.warning(f"Invalid schedule time: {request.scheduled_at}")

    return TaskResponse(**task)


# ── List tasks ──────────────────────────────────────────────
@app.get("/tasks")
async def list_tasks(status: Optional[str] = None, task_type: Optional[str] = None):
    """List all tasks, optionally filtered."""
    result = list(tasks.values())
    if status:
        result = [t for t in result if t["status"] == status]
    if task_type:
        result = [t for t in result if t["task_type"] == task_type]
    result.sort(key=lambda t: t["created_at"], reverse=True)
    return {"tasks": result, "count": len(result)}


# ── Get task ────────────────────────────────────────────────
@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(**tasks[task_id])


# ── Update task status ──────────────────────────────────────
class TaskUpdateRequest(BaseModel):
    status: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None


@app.patch("/tasks/{task_id}")
async def update_task(task_id: str, request: TaskUpdateRequest):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    if request.status:
        tasks[task_id]["status"] = request.status
    if request.title:
        tasks[task_id]["title"] = request.title
    if request.description:
        tasks[task_id]["description"] = request.description

    return tasks[task_id]


# ── Delete task ─────────────────────────────────────────────
@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    # Remove scheduled job if exists
    try:
        scheduler.remove_job(task_id)
    except Exception:
        pass

    del tasks[task_id]
    return {"status": "deleted", "id": task_id}


# ── Task execution ─────────────────────────────────────────
async def _execute_task(task_id: str):
    """Execute a scheduled task."""
    if task_id not in tasks:
        return

    task = tasks[task_id]
    task["status"] = "executing"
    logger.info(f"Executing task: {task['title']} ({task['task_type']})")

    try:
        if task["task_type"] == "reminder":
            await _handle_reminder(task)
        elif task["task_type"] == "call":
            await _handle_call_task(task)
        elif task["task_type"] == "summary":
            await _handle_summary(task)

        task["status"] = "completed"
    except Exception as e:
        logger.error(f"Task execution failed: {e}")
        task["status"] = "failed"


async def _handle_reminder(task: dict):
    """Store reminder result in memory."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                f"{settings.memory_url}/store",
                json={
                    "type": "personal",
                    "user": "Azim",
                    "content": {"task_id": task["id"], "reminder": task["title"]},
                    "text": f"Reminder: {task['title']}. {task['description']}",
                },
            )
        except Exception as e:
            logger.warning(f"Failed to store reminder: {e}")


async def _handle_call_task(task: dict):
    """Trigger an outbound call via Dograh."""
    logger.info(f"Call task: {task['title']} — would trigger Dograh outbound call")


async def _handle_summary(task: dict):
    """Generate a summary using the brain."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            await client.post(
                f"{settings.brain_url}/chat",
                json={
                    "message": f"Generate a summary for: {task['description']}",
                    "user": "Azim",
                },
            )
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
