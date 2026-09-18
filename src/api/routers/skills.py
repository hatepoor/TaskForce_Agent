"""技能路由(模块 11 T3):GET /skills。

复用 07 的 SkillRegistry 元数据(结构化 JSON,非渲染文本)。
"""
from fastapi import APIRouter

from tools.skills.loader import SkillRegistry

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
def list_skills():
    return {"skills": SkillRegistry().list_metadata()}
