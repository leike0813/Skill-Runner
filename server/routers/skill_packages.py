import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile  # type: ignore[import-not-found]

from ..models import (
    SkillInstallCreateResponse,
    SkillInstallStatus,
    SkillInstallStatusResponse
)
from ..services.skill.skill_install_store import skill_install_store
from ..services.skill.skill_package_manager import skill_package_manager
from ..services.ui.ui_auth import require_ui_basic_auth


router = APIRouter(
    prefix="/skill-packages",
    tags=["skill-packages"],
    dependencies=[Depends(require_ui_basic_auth)],
)
logger = logging.getLogger(__name__)


@router.post("/install", response_model=SkillInstallCreateResponse)
async def install_skill_package(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    try:
        payload = await file.read()
        if not payload:
            raise HTTPException(status_code=400, detail="Uploaded package is empty")
        request_id = str(uuid.uuid4())
        await skill_package_manager.create_install_request(request_id, payload)
        background_tasks.add_task(skill_package_manager.run_install, request_id)
        return SkillInstallCreateResponse(
            request_id=request_id,
            status=SkillInstallStatus.QUEUED
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        # Boundary mapping for unexpected install failures.
        logger.exception(
            "skill_packages.install failed; returning HTTP 500",
            extra={
                "component": "router.skill_packages",
                "action": "install_skill_package",
                "error_type": type(exc).__name__,
                "fallback": "http_500",
            },
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{request_id}", response_model=SkillInstallStatusResponse)
async def get_install_status(request_id: str):
    record = await skill_install_store.get_install(request_id)
    if not record:
        raise HTTPException(status_code=404, detail="Install request not found")

    try:
        created_at = datetime.fromisoformat(record["created_at"])
    except ValueError:
        created_at = datetime.utcnow()
    try:
        updated_at = datetime.fromisoformat(record["updated_at"])
    except ValueError:
        updated_at = created_at

    return SkillInstallStatusResponse(
        request_id=request_id,
        status=SkillInstallStatus(record["status"]),
        created_at=created_at,
        updated_at=updated_at,
        skill_id=record.get("skill_id"),
        version=record.get("version"),
        action=record.get("action"),
        error=record.get("error")
    )
