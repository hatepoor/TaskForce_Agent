"""FastAPI 入口(模块 11):七 router 挂载 + lifespan 初始化;双入口之一,共用业务层。

使用位置:
    uv run uvicorn api.main:app --port 8010
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routers import chat, health, knowledge, mcp, memory, model_settings, skills
from settings.config import get_settings
from settings.db.checkpointer import get_checkpointer


@asynccontextmanager
async def lifespan(_app):
    # 预检 DB:checkpointer 连库并幂等建表;连不上启动即报
    get_checkpointer(get_settings().database_url)
    yield


app = FastAPI(title="TaskForce", lifespan=lifespan)
for r in (chat.router, health.router, knowledge.router, memory.router,
          model_settings.router, skills.router, mcp.router):
    app.include_router(r)

# 前端构建产物同源托管(形态 B:一条 uvicorn 起全栈)。
# 仅当 dist 存在时挂载,没跑过 npm build 的环境(CI/pytest)照常启动;
# 必须在 include_router 之后:FastAPI 按注册顺序匹配,精确路由优先。
_DIST = Path(__file__).resolve().parents[2] / "dev" / "front" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="front")


if __name__ == "__main__":
    # IDE 直接运行入口(等价命令行: uv run uvicorn api.main:app --port 8010 --reload)
    # 端口固定 8010(项目约定,勿改):8000 是本机沙箱 SSH 隧道,同端口会自指递归
    import uvicorn

    uvicorn.run("api.main:app", host="127.0.0.1", port=8010, reload=True)
