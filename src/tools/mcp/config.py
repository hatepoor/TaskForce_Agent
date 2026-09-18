import json
import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, ValidationError

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "mcp_config.json"
_NAME_RE = re.compile(r"^[a-z0-9_-]+$")


class MCPConfigError(ValueError):
    """MCP 配置可读错误:JSON 损坏、schema 不符、名字非法等。"""


class StdioServer(BaseModel):
    """本地 stdio 服务器:子进程启动。"""
    transport: Literal["stdio"] = "stdio"
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class HttpServer(BaseModel):
    """远程 streamable HTTP 服务器:url 直连(可带 headers 鉴权)。"""

    transport: Literal["http"] = "http"
    url: str
    headers: dict[str, str] = Field(default_factory=dict)

MCPServerConfig = Annotated[StdioServer | HttpServer, Field(discriminator="transport")]

class MCPConfig(BaseModel):
    """全部服务器配置,按名字索引。"""

    servers: dict[str, MCPServerConfig] = Field(default_factory=dict)


def _check_name(name: str) -> None:
    if not _NAME_RE.match(name):
        raise MCPConfigError(f"服务器名不合法 {name!r}(须 ^[a-z0-9_-]+$)")

def load_mcp_config(path: Path | str | None = None) -> MCPConfig:
    """读配置;文件不存在视为空配置(首次使用),JSON/schema 错误抛 MCPConfigError。"""
    p = Path(path) if path else DEFAULT_PATH
    if not p.is_file():
        return MCPConfig()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return MCPConfig(**data)
    except json.JSONDecodeError as e:
        raise MCPConfigError(f"mcp_config.json 不是合法 JSON:{e}") from e
    except ValidationError as e:
        raise MCPConfigError(f"mcp_config.json schema 不符:{e}") from e


def save_mcp_config(config: MCPConfig, path: Path | str | None = None) -> None:
    p = Path(path) if path else DEFAULT_PATH
    p.write_text(config.model_dump_json(indent=2), encoding="utf-8")


def add_server(name: str, server: MCPServerConfig, path: Path | str | None = None) -> None:
    """新增(或覆盖)一个服务器配置并落盘。"""
    _check_name(name)
    config = load_mcp_config(path)
    config.servers[name] = server
    save_mcp_config(config, path)

def remove_server(name: str, path: Path | str | None = None) -> bool:
    """删除服务器配置;存在返回 True,不存在返回 False。"""
    _check_name(name)
    config = load_mcp_config(path)
    if name not in config.servers:
        return False
    del config.servers[name]
    save_mcp_config(config, path)
    return True
