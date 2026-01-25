"""
API Router for Skill Discovery.

Exposes endpoints for:
- Listing available skills (GET /skills)
- Retrieving metadata for a specific skill (GET /skills/{skill_id})
"""

from fastapi import APIRouter, HTTPException  # type: ignore[import-not-found]
from typing import List
from ..models import SkillManifest
from ..services.skill_registry import skill_registry

router = APIRouter(prefix="/skills", tags=["skills"])

@router.get("", response_model=List[SkillManifest])
async def list_skills():
    return skill_registry.list_skills()

@router.get("/{skill_id}", response_model=SkillManifest)
async def get_skill(skill_id: str):
    skill = skill_registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill
