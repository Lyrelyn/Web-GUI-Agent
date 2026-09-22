"""Task lifecycle routes."""

from typing import cast

from fastapi import APIRouter, Request, status

from web_gui_agent.api.schemas.task import CreateTaskRequest, TaskResponse
from web_gui_agent.application.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _task_service(request: Request) -> TaskService:
    return cast(TaskService, request.app.state.task_service)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(payload: CreateTaskRequest, request: Request) -> TaskResponse:
    task = await _task_service(request).create(payload.to_domain())
    return TaskResponse.from_domain(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, request: Request) -> TaskResponse:
    task = await _task_service(request).get(task_id)
    return TaskResponse.from_domain(task)


@router.delete("/{task_id}", response_model=TaskResponse)
async def cancel_task(task_id: str, request: Request) -> TaskResponse:
    task = await _task_service(request).cancel(task_id)
    return TaskResponse.from_domain(task)
