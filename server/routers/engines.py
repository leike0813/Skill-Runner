from fastapi import APIRouter, HTTPException  # type: ignore[import-not-found]

from ..models import EngineModelsResponse, EnginesResponse, EngineModelInfo
from ..services.model_registry import model_registry

router = APIRouter(prefix="/engines", tags=["engines"])


@router.get("", response_model=EnginesResponse)
async def list_engines():
    return EnginesResponse(engines=model_registry.list_engines())


@router.get("/{engine}/models", response_model=EngineModelsResponse)
async def list_models(engine: str):
    try:
        catalog = model_registry.get_models(engine)
        return EngineModelsResponse(
            engine=catalog.engine,
            cli_version_detected=catalog.cli_version_detected,
            snapshot_version_used=catalog.snapshot_version_used,
            source="pinned_snapshot",
            fallback_reason=catalog.fallback_reason,
            models=[
                EngineModelInfo(
                    id=entry.id,
                    display_name=entry.display_name,
                    deprecated=entry.deprecated,
                    notes=entry.notes,
                    supported_effort=entry.supported_effort
                )
                for entry in catalog.models
            ]
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
