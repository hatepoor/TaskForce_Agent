"""远程沙箱 HTTP 客户端(模块 09 T1):Python 执行 + 工作区文件读写。

协议(以用户沙箱实测为准,2026-09-10,契约变更见 ROADMAP §7):
POST /execute     {code, language, timeout} -> {stdout, stderr, exit_code, duration_ms}
        stdout 为容器 stdout+stderr 合并;exit_code: 0 成功/124 超时/137 OOM/-1 沙箱异常
POST /files/write {filename, content} -> {ok, path}
GET  /files/read?filename=... -> {filename, content}  404=文件不存在
GET  /health      -> {"status": "ok"}(免鉴权)
鉴权:Authorization: Bearer <SANDBOX_API_KEY>。
无 session_id:沙箱无状态,每次执行新建容器;/files/* 操作持久工作区,/execute 时挂载进容器(实测可见)。

工具侧纪律:任何失败(未配置/网络/HTTP 错误)一律返回结构化 {ok: False, error},
不抛异常——错误进 ToolMessage 让 LLM 自行向用户说明,图不崩。

使用位置:
- tools/tool/files.py(内置工具包装)、agent/subagents/executor.py(装配);
- tests/test_executor.py(单测 mock + 真沙箱冒烟 skipif)。
"""

import json
from functools import lru_cache

import httpx

from settings.config import get_settings

EXEC_TIMEOUT_DEFAULT = 60   # 代码执行默认限时(秒,传给沙箱)
HTTP_TIMEOUT = 70           # HTTP 客户端超时,必须大于执行限时
STDOUT_LIMIT = 10_000       # stdout 截断上限(字符)


def _request(
        method: str,
        path: str, *,
        json_body: dict | None = None,
        params: dict | None = None
    ) -> dict:
    """统一请求:拼 URL/Bearer 头;网络与 HTTP 错误转结构化 error,不抛。"""
    s = get_settings()
    if not s.sandbox_url:
        return {"ok": False, "error": "沙箱未配置:请在 .env 填写 SANDBOX_URL 与 SANDBOX_API_KEY"}
    try:
        resp = httpx.request(
            method, s.sandbox_url.rstrip("/") + path,
            json=json_body, params=params, timeout=HTTP_TIMEOUT,
            headers={"Authorization": f"Bearer {s.sandbox_api_key}"} if s.sandbox_api_key else {},
        )
        if resp.status_code >= 400:
            return {"ok": False, "error": f"沙箱返回 HTTP {resp.status_code}: {resp.text[:200]}"}
        return resp.json()
    except httpx.HTTPError as e:
        return {"ok": False, "error": f"沙箱不可达:{type(e).__name__}: {e}"}


def execute_python(code: str, timeout: int = EXEC_TIMEOUT_DEFAULT) -> dict:
    """远程执行 Python 代码。成功:{ok, stdout, stderr, exit_code, duration_ms, truncated}。"""
    r = _request(
        "POST",
        "/execute",
        json_body={"code": code, "language": "python", "timeout": timeout})
    if r.get("ok") is False:
        return r
    out = str(r.get("stdout", ""))
    truncated = len(out) > STDOUT_LIMIT
    return {
        "ok": True,
        "stdout": out[:STDOUT_LIMIT],
        "stderr": r.get("stderr", ""),
        "exit_code": r.get("exit_code"),
        "duration_ms": r.get("duration_ms"),
        "truncated": truncated,
    }


def write_file(filename: str, content: str) -> dict:
    """写沙箱工作区文件。成功:{ok, path}。"""
    r = _request("POST", "/files/write", json_body={"filename": filename, "content": content})
    return r if r.get("ok") is False else {"ok": True, "path": r.get("path", filename)}


def read_file(filename: str) -> dict:
    """读沙箱工作区文件。成功:{ok, filename, content};不存在返回 ok=False。"""
    r = _request("GET", "/files/read", params={"filename": filename})
    if r.get("ok") is False:
        return r
    return {"ok": True, "filename": r.get("filename", filename), "content": r.get("content", "")}


def list_files() -> dict:
    """列工作区文件。协议无列目录端点,经 execute_python 跑 os.listdir 组合实现。"""
    r = execute_python("import os, json; print(json.dumps(sorted(os.listdir('.'))))", timeout=30)
    if not r.get("ok"):
        return r
    try:
        return {"ok": True, "files": json.loads(r["stdout"].strip().splitlines()[-1])}
    except (ValueError, IndexError):
        return {"ok": False, "error": f"list_files 解析失败:{r.get('stdout', '')[:200]}"}


def sandbox_health() -> dict:
    """健康检查(/health 免鉴权),供 REPL /sandbox 与测试冒烟。"""
    return _request("GET", "/health")


@lru_cache(maxsize=1)
def sandbox_meta() -> str:
    """沙箱状态概览,注入 answer 提示词(ADR-0011 静态内容,进程内缓存一次)。

    三态语义(同 mcp_meta,防"已配置但连不上"误报成"未配置"):
    未配置 / 已配置但不可达 / 正常(能力概览)。
    """
    s = get_settings()
    if not s.sandbox_url:
        return "(执行沙箱未配置:代码执行类任务当前不可用)"
    if sandbox_health().get("status") != "ok":  # /health 返回 {status: ok},勿用 .get("ok")
        return "(执行沙箱已配置,但当前连接不可达,执行类任务可能失败)"
    return (
        f"远程 Python 沙箱已就绪({s.sandbox_url}):支持执行代码(execute_python)"
        "与工作区文件读写(write_file/read_file/list_files),由执行智能体(executor)实际调用。"
    )
