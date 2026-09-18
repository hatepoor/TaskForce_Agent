"""模型配置覆盖:设置页可改的六项(LLM / Embedding),存 .taskforce/model_config.json。

本文件作用:
    设置页保存的模型接入信息落盘在 .taskforce/(与 session.py 同目录,.gitignore 已含),
    .env 仍是默认值来源——程序不写回 .env(注释与顺序会被破坏);
    config.get_settings() 读到 .env 后叠加覆盖,因此**进程启动时生效一次**,
    保存后需重启后端(GET /models/config 用 restart_required 显式提示这一点)。

使用位置:
    - settings/config.py:get_settings() 叠加覆盖、applied_overrides() 记启动快照;
    - api/routers/model_settings.py:读写覆盖表 + 掩码回显。
"""
import json
from pathlib import Path

# 可被设置页覆盖的六项(其余配置仍只认 .env)
OVERRIDABLE = (
    "llm_base_url", "llm_api_key", "llm_model",
    "embedding_base_url", "embedding_api_key", "embedding_model",
)
# 密钥字段:回显只给掩码,提交掩码表示"保持不动"
SECRET_FIELDS = ("llm_api_key", "embedding_api_key")

_STORE_DIR = Path(".taskforce")  # 与 settings/session.py 同约定:项目根下的隐藏目录
CONFIG_PATH = _STORE_DIR / "model_config.json"


def load_overrides(path: Path | None = None) -> dict[str, str]:
    """读覆盖表:缺失/JSON 损坏/形状不符一律空表(配置读不出来不该让进程起不来)。"""
    p = path or CONFIG_PATH
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if k in OVERRIDABLE and isinstance(v, str) and v != ""}


def save_overrides(values: dict[str, str], path: Path | None = None) -> dict[str, str]:
    """整表写入(合并由调用方先做);空值项落盘前剔除(空值即"无覆盖")。"""
    cleaned = {
        k: v for k, v in values.items() if k in OVERRIDABLE and isinstance(v, str) and v != ""
    }
    p = path or CONFIG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    return cleaned


def apply_overrides(settings, overrides: dict[str, str]):
    """把覆盖值就地写进 Settings(调用方持有唯一实例)。"""
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def merge_overrides(current: dict[str, str], incoming: dict[str, str | None]) -> dict[str, str]:
    """把 PUT 提交的字段合并进现表(缺项 = 不动)。

    三条规则(前端表单按此设计):
    - 字段缺失/为 None → 不提交此项,保持原值(改一项只发一项);
    - 空串 → 清除该项覆盖(回落 .env);
    - 密钥字段收到掩码占位符 → 保持不动(前端拿不到原文,原样回传即"不改");
    - 其余非空值去首尾空白后写入。
    """
    merged = dict(current)
    for key, raw in incoming.items():
        if key not in OVERRIDABLE or raw is None or not isinstance(raw, str):
            continue
        value = raw.strip()
        if value == "":
            merged.pop(key, None)
        elif key in SECRET_FIELDS and is_masked(value):
            continue
        else:
            merged[key] = value
    return merged


def mask(value: str) -> str:
    """密钥掩码:长度 > 8 留前后各 4 位,短值全掩;空串原样返回。"""
    if value == "":
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}****{value[-4:]}"


def is_masked(value: str) -> bool:
    """掩码占位判定:含 **** 或为空(两者都表示"没有可用原文")。"""
    return value == "" or "****" in value


def is_http_url(value: str) -> bool:
    """base_url 形状校验:http(s):// 开头且后面有内容(要拿它拼 OpenAI 客户端)。"""
    return value.startswith(("http://", "https://")) and len(value) > len("https://")
