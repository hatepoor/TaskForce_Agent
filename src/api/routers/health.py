"""健康检查路由(模块 11 T3):GET /health(存活 + DB + 沙箱自检)。"""
from fastapi import APIRouter

from settings.config import get_settings
from settings.db.checkpointer import get_checkpointer
from tools.sandbox.client import sandbox_health

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """DB 与沙箱自检:DB 异常降级 status;沙箱异常只报 sandbox 字段(契约 §2.2),不抛 500。"""
    status: dict = {"status": "ok", "db": "ok", "sandbox": "unknown"}
    try:
        get_checkpointer(get_settings().database_url)
    except Exception as e:
        status["db"] = f"error: {e}"
        status["status"] = "degraded"
    sb = sandbox_health()
    # 契约:沙箱 /health 返回 {"status": "ok"};勿用 .get("ok")(见 client.sandbox_meta 注释)
    if sb.get("status") == "ok":
        status["sandbox"] = "ok"
    else:
        status["sandbox"] = sb.get("error", "unreachable")
    return status
