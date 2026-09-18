"""模型设置路由:GET/PUT /models/config(设置页配置主模型与 Embedding 的接入信息)。

覆盖表落盘 .taskforce/model_config.json(见 settings/model_overrides.py),.env 为默认值来源;
保存后**重启后端生效**(进程启动时读一次),GET 用 restart_required 显式提示。
安全约定:api_key 只回掩码,原文不出网关;PUT 收到掩码原样回传 = 保持不动。
PUT 语义:**缺项 = 不动**(改一项只发一项),空串 = 清除覆盖,非空 = 写入。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from settings.config import applied_overrides, effective_config
from settings.model_overrides import (
    OVERRIDABLE,
    SECRET_FIELDS,
    is_http_url,
    load_overrides,
    mask,
    merge_overrides,
    save_overrides,
)

router = APIRouter(prefix="/models", tags=["models"])

# PUT 校验的两处 base_url:字段名 -> 报错用的中文标签
_URL_FIELDS = (("llm_base_url", "主模型 base_url"), ("embedding_base_url", "Embedding base_url"))


class ModelConfigRequest(BaseModel):
    """全可选的六项:**不提交的字段保持不动**(前端只发改动项);空串 = 清除该项覆盖。"""

    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model: str | None = None


def _snapshot() -> dict:
    """当前状态:重启后的生效值(密钥掩码)+ 覆盖来源 + 是否待重启。

    config 给的是 **.env + 覆盖表**(重启后的生效值),不是进程里正在跑的那份:
    表单编辑的是"已保存的配置",给运行中旧值会把刚保存的内容盖回输入框;
    两者是否一致由 restart_required 单独提示。
    """
    values = effective_config()
    saved = load_overrides()
    return {
        "config": {
            field: (mask(values[field]) if field in SECRET_FIELDS else values[field])
            for field in OVERRIDABLE
        },
        "overridden": sorted(saved),
        "restart_required": saved != applied_overrides(),
    }


@router.get("/config")
def read_config() -> dict:
    """生效配置(重启后口径)+ 覆盖来源 + 待重启标记(密钥只回掩码)。"""
    return _snapshot()


@router.put("/config")
def update_config(req: ModelConfigRequest) -> dict:
    """保存覆盖表:缺项不动、空串清除覆盖(回落 .env)、密钥掩码保持不动;返回保存后的快照。"""
    incoming = req.model_dump()
    for field, label in _URL_FIELDS:
        value = incoming[field]
        if value is not None and value.strip() != "" and not is_http_url(value.strip()):
            raise HTTPException(
                status_code=400, detail=f"{label} 需以 http:// 或 https:// 开头"
            )
    save_overrides(merge_overrides(load_overrides(), incoming))
    return _snapshot()
