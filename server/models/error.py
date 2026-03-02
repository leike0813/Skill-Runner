"""Error response models."""

from typing import Any, Dict, Optional

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard API Error response structure."""

    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
