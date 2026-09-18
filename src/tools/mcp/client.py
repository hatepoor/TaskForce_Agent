import asyncio
import sys
from functools import lru_cache

from langchain_mcp_adapters.client import MultiServerMCPClient

from tools.mcp.config import MCPConfig, MCPConfigError, load_mcp_config

INDEX_TOKEN_WARN=3000 #工具索引 token 上限告警，
CONNECT_TIMEOUT = 10.0  # 单服务器连接/调用超时(秒)


class MCPToolProvider:
    """工具发现:索引常驻(short_desc)+ 按需详情;单服务器失败降级。"""

    def __init__(self, config: MCPConfig | None = None, timeout: float = CONNECT_TIMEOUT):
        self._config = config or load_mcp_config()
        self._timeout = timeout
        self._tool_cache:dict={} # name -> BaseTool(list_tools 时刷新,T3 两层描述共用)

    def _client(self) -> MultiServerMCPClient:
        """配置 -> MultiServerMCPClient;模型 model_dump 即 adapters 的连接配置
        (StdioServer->stdio / HttpServer->streamable http),远程/本地同一条路径。"""
        servers = {
            name: s.model_dump(exclude_none=True)
            for name, s in self._config.servers.items()
        }
        return MultiServerMCPClient(servers)

    def get_tool_detail(self, name: str) -> dict:
        """返回工具完整 schema(描述 + 参数 JSON schema);不在已知索引时报可读错误。"""
        tool = self._get_cached(name)
        return {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.args
        }

    def get_langchain_tools(self, names: list[str]) -> list:
        """按名单取可绑定 LLM 的工具对象(模块 09 executor 装配用);缺的告警跳过。"""
        out = []
        for n in names:
            try:
                out.append(self._get_cached(n))
            except MCPConfigError as e:
                print(f"[mcp] {e}(跳过)", file=sys.stderr)
        return out

    def _get_cached(self, name: str):
        tool = self._tool_cache.get(name)
        if tool is None:
            raise MCPConfigError(f"工具 {name} 不在已发现索引中(先 list_tools 或检查服务器连通)")
        return tool

    def _warn_index_size(self, results: list[dict]) -> None:
        """索引总量粗估(中文约 2 字符/token,保守)超阈值则告警。"""
        chars = sum(len(r["name"]) + len(r["short_desc"]) for r in results)
        if chars // 2 > INDEX_TOKEN_WARN:
            print(f"[mcp] 工具索引约 {chars // 2} tok,超过 {INDEX_TOKEN_WARN} 上限,建议配白名单",
            file=sys.stderr)

    def list_tools(self) -> list[dict]:
        """逐服务器发现工具 -> [{server, name, short_desc}](索引,desc 截断 30 字)。

        单服务器失败:告警跳过,不阻塞其他服务器(核心验收:降级不崩)。
        """
        results: list[dict] = []
        client = self._client()
        for name in self._config.servers:
            try:
                tools = asyncio.run(
                    asyncio.wait_for(client.get_tools(server_name=name), self._timeout)
                )
            except Exception as e:
                print(f"[mcp] 服务器 {name} 不可达,已跳过:{type(e).__name__}: {e}",file=sys.stderr)
                continue
            for t in tools:
                desc = (getattr(t, "description", "") or "").strip()
                results.append({
                    "server": name,
                    "name": t.name,
                    "short_desc": desc[:30] + ("…" if len(desc) > 30 else ""),
                })
                self._tool_cache[t.name]=t
        self._warn_index_size(results)
        return results


def render_mcp_meta(server_tools: list[dict]) -> str:
    """服务器/工具发现结果 -> 提示词片段(每行 <server>/<tool>: short_desc)。纯函数,便于单测。"""
    if not server_tools:
        return "(未配置外部工具)"
    return "\n".join(f"- {t['server']}/{t['name']}: {t['short_desc']}" for t in server_tools)


@lru_cache(maxsize=1)
def mcp_meta() -> str:
    """进程内缓存一次 MCP 发现(ADR-0011 静态内容,与 skills_meta 同款);失败降级不阻塞主图。

    区分三种态(实测坑:list_tools 失败返回空列表而非抛异常,不能把"已配置但连不上"
    误报成"未配置"):未配置 / 已配置但连接暂不可用 / 正常清单。uvx 冷启动+握手可能
    超过 10s,用 60s 超时(该发现只在进程内跑一次,lru_cache 兜底)。
    """
    if not load_mcp_config().servers:
        return "(未配置外部工具)"
    found = MCPToolProvider(timeout=60).list_tools()
    if not found:
        return "(已配置外部工具,但当前连接暂不可用)"
    return render_mcp_meta(found)
