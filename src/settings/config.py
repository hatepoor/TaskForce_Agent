"""全局配置:pydantic-settings 读 .env,进程内单例(lru_cache)。

本文件作用:
    Settings 声明全部环境变量(LLM / Embedding / 数据库 / 沙箱 / 计费单价),
    get_settings() 缓存单例并在缺失必填项时给可读中文报错;
    设置页保存的模型覆盖(.taskforce/model_config.json)在此叠加,.env 仍是默认值来源;
    assert_ready 供需要显式校验的场景复用。

使用位置:
    - agent/build.py:make_llm 取 LLM 配置;
    - settings/usage.py:UsageTracker 取计费单价;
    - settings/db/checkpointer.py、tools/rag/store.py、tools/rag/embed.py:
      取 database_url / embedding 配置;
    - cli/repl.py:进程入口取全局配置。
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from settings.model_overrides import OVERRIDABLE, apply_overrides, load_overrides

# .env 锚定项目根(src/settings/config.py → 上溯 3 级),与运行工作目录无关:
# PyCharm 直接运行脚本时 CWD 是 src/api,按 CWD 找 .env 会全部配置缺失
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """ .env 配置的强类型映射;字段名即环境变量名(大小写不敏感)。"""
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")
    # extra="ignore" 很重要:.env 里若有未声明的变量不报错

    # LLM(火山方舟)
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_input_price_per_m: float = 0.0
    llm_output_price_per_m: float = 0.0

    # Embedding(智谱,04 模块才用,允许为空)
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""

    # 数据库 / 沙箱 / 搜索(anysearch,10 模块启用) / 运行时
    database_url: str
    sandbox_url: str = ""
    sandbox_api_key: str = ""
    anysearch_api_key: str = ""  # 搜索 API 可选;留空走匿名调用(按 IP 限流)
    log_level: str = "INFO"


def assert_ready(s: Settings) -> None:
    """校验必填配置齐全,缺失时抛出带变量名清单的 RuntimeError。"""
    required = ("llm_base_url", "llm_api_key", "llm_model", "database_url")
    missing = [name.upper() for name in required if not getattr(s, name)]
    if missing:
        raise RuntimeError(
            f"配置缺失,请在 .env 中填写以下变量:{', '.join(missing)}"
        )


# 进程启动时实际叠加的那份覆盖(/models/config 用它判断"已保存但未生效")
_APPLIED: dict[str, str] = {}


@lru_cache
def get_settings() -> Settings:
    """配置单例入口:首次调用加载 .env,叠加设置页覆盖,校验必填后缓存。

    覆盖表(.taskforce/model_config.json)只在启动时读一次——保存后需重启后端;
    必填校验放在叠加之后:被覆盖补上的项不该再报缺失。
    """
    s = Settings()
    _APPLIED.clear()
    _APPLIED.update(load_overrides())
    apply_overrides(s, _APPLIED)
    assert_ready(s)
    return s


def applied_overrides() -> dict[str, str]:
    """启动时实际生效的覆盖表;尚未初始化则先初始化(不依赖调用方顺序)。"""
    get_settings()
    return dict(_APPLIED)


def effective_config() -> dict[str, str]:
    """.env 默认 + 盘上覆盖表 = **重启后**的生效值(设置页表单的编辑对象)。

    与 get_settings() 的区别:后者是"当前进程运行中的值"(启动时定死并缓存),
    这里是"保存并重启后的值"——保存后表单要显示这个,否则刚填的值会被运行值盖回输入框。
    """
    base = Settings()
    merged = {field: str(getattr(base, field, "") or "") for field in OVERRIDABLE}
    merged.update(load_overrides())
    return merged
