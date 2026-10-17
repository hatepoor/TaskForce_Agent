"""远程沙箱客户端:腾讯云 Agent Runtime(AGS),经 E2B SDK 接入(2026-09-23 换内核)。

旧自建 HTTP 协议(POST /execute 等)已废弃;新协议 = E2B 兼容 SDK,配置三件套
(声明在 settings.config.Settings,字段名即环境变量名):
    E2B_API_KEY   AGS 控制台签发的 API Key(e2b_ 前缀,需 Code Interpreter Sandbox 权限)
    E2B_DOMAIN    地域 endpoint(如 ap-guangzhou.tencentags.com,不带 https:// 前缀)
    AGS_TEMPLATE  沙箱模板名(控制台创建的沙箱工具名),缺省 Sandbox
创建实例时全显式传参,不走环境变量——测试替换 get_settings 即全链路可控。

Execution 字段语义(实测 2026-09-23,与直觉不同处):
    print 输出在 ex.logs.stdout(list);ex.text 是富结果的主结果文本,即最后
    一个表达式的值,仅当无 print 输出时兜底用。

实例模型变化:旧协议无状态(每次执行新建容器,工作区独立持久),E2B 是长驻
实例——进程内懒创建单例复用,SANDBOX_TTL 到期云端自动回收,下次调用重建;
atexit 兜底 kill,防 REPL/脚本退出后实例空转计费(按实例存活时长计费)。

对外契约(不变,见 ROADMAP §7):
execute_python(code, timeout) -> {ok, stdout, stderr, exit_code, duration_ms, truncated}
    exit_code: 0 成功 / 124 执行超时 / 1 代码抛异常(旧 137 OOM 语义不再可感知)
write_file(filename, content) -> {ok, path}
read_file(filename) -> {ok, filename, content}  文件不存在=ok False
list_files() -> {ok, files}(经 execute_python 跑 os.listdir,cwd 语义与代码执行一致)
sandbox_health() -> {"status": "ok"} 或 {ok: False, error}(E2B 无 health 端点,轻量探活)

工具侧纪律:任何失败(未配置/网络/超时)一律返回结构化 {ok: False, error},
不抛异常——错误进 ToolMessage 让 LLM 自行向用户说明,图不崩。

使用位置:
- tools/tool/files.py(内置工具包装)、agent/subagents/executor.py(装配)、
  agent/answer.py(sandbox_meta 注入)、api/routers/health.py(健康端点);
- tests/test_executor.py(子图 mock)、tests/test_sandbox.py(client 单测 + 真沙箱冒烟)。
"""

import atexit
import json
import time
from functools import lru_cache

from e2b.exceptions import (
    FileNotFoundException,
    SandboxNotFoundException,
    TimeoutException,
)
from e2b_code_interpreter import Sandbox

from settings.config import get_settings

EXEC_TIMEOUT_DEFAULT = 60   # 代码执行默认限时(秒)
STDOUT_LIMIT = 10_000       # stdout 截断上限(字符)
SANDBOX_TTL = 3600          # 实例最长存活(秒,到期云端自动回收,按存活时长计费)

_ERR_UNCONFIGURED = "沙箱未配置:请在 .env 填写 E2B_API_KEY / E2B_DOMAIN / AGS_TEMPLATE"

_sbx: Sandbox | None = None


def _configured() -> bool:
    """配置是否齐全(api_key 与 domain 必填,template 可缺省兜底)。"""
    s = get_settings()
    return bool(s.e2b_api_key and s.e2b_domain)


def _template() -> str:
    """沙箱模板名:.env 的 AGS_TEMPLATE 优先,缺省用控制台创建的 Sandbox。"""
    return get_settings().ags_template or "Sandbox"


def _sandbox() -> Sandbox:
    """懒创建长驻实例;到期云端自动回收,之后首次调用触发重建。"""
    global _sbx
    if _sbx is None:
        s = get_settings()
        _sbx = Sandbox.create(
            template=_template(),
            timeout=SANDBOX_TTL,
            api_key=s.e2b_api_key,
            domain=s.e2b_domain,
        )
        sandbox_meta.cache_clear()  # 实例重建后三态概览要重算,不吃旧的"不可达"缓存
    return _sbx


def _drop() -> None:
    """丢弃失效实例引用:云端已删除时本地对象不可再用。"""
    global _sbx
    _sbx = None


def _is_missing_sandbox(e: Exception) -> bool:
    """实例已被云端回收(TTL 到期 / 手动删除)的判据。

    run_code 走 envd 通道,404 被 SDK 映射成基类 NotFoundException(消息含
    sandbox instance does not exist);控制面操作则抛 SandboxNotFoundException。
    文件不存在(FileNotFoundException)不是实例失效,不能触发重建。
    """
    if isinstance(e, SandboxNotFoundException):
        return True
    if isinstance(e, FileNotFoundException):
        return False
    text = str(e).lower()
    return "sandbox" in text and any(
        k in text for k in ("not found", "does not exist", "deleted")
    )


def _call(fn):
    """SDK 调用入口:实例已失效则丢弃引用、重建一次再试。"""
    try:
        return fn(_sandbox())
    except Exception as e:
        if not _is_missing_sandbox(e):
            raise
        _drop()
        return fn(_sandbox())


def _kill() -> None:
    """进程退出兜底回收云端实例(已回收/不存在时静默),防实例空转计费。"""
    global _sbx
    if _sbx is not None:
        try:
            _sbx.kill()
        except Exception:  # 退出路径不因清理失败报错
            pass
        _sbx = None


atexit.register(_kill)


def execute_python(code: str, timeout: int = EXEC_TIMEOUT_DEFAULT) -> dict:
    """远程执行 Python 代码。成功:{ok, stdout, stderr, exit_code, duration_ms, truncated}。"""
    if not _configured():
        return {"ok": False, "error": _ERR_UNCONFIGURED}
    start = time.monotonic()
    try:
        ex = _call(lambda sbx: sbx.run_code(code, timeout=timeout))
    except TimeoutException as e:
        # 超时映射回旧契约 124,由 LLM 判断语义
        return {"ok": False, "error": f"沙箱执行超时({timeout}s):{e}", "exit_code": 124}
    except Exception as e:
        return {"ok": False, "error": f"沙箱执行失败:{type(e).__name__}: {e}", "exit_code": -1}

    logs = getattr(ex, "logs", None)
    # print 输出在 logs.stdout;ex.text 是最后表达式的值(富结果),仅无 print 时兜底
    out = "\n".join(logs.stdout or []) if logs else ""
    if not out and ex.text:
        out = ex.text
    stderr = "\n".join(logs.stderr or []) if logs else ""
    exit_code = 0
    if ex.error is not None:
        # 代码内异常:traceback 进 stderr,与旧协议"错误信息对 LLM 可见"对齐
        exit_code = 1
        tb = ex.error.traceback or f"{ex.error.name}: {ex.error.value}"
        stderr = f"{stderr}\n{tb}".strip()
    truncated = len(out) > STDOUT_LIMIT
    return {
        "ok": True,
        "stdout": out[:STDOUT_LIMIT],
        "stderr": stderr,
        "exit_code": exit_code,
        "duration_ms": int((time.monotonic() - start) * 1000),
        "truncated": truncated,
    }


def write_file(filename: str, content: str) -> dict:
    """写沙箱工作区文件。成功:{ok, path}。"""
    if not _configured():
        return {"ok": False, "error": _ERR_UNCONFIGURED}
    try:
        path = _call(lambda sbx: sbx.files.write(filename, content))
    except Exception as e:
        return {"ok": False, "error": f"沙箱写入失败:{type(e).__name__}: {e}"}
    return {"ok": True, "path": str(path or filename)}


def read_file(filename: str) -> dict:
    """读沙箱工作区文件。成功:{ok, filename, content};不存在返回 ok=False。"""
    if not _configured():
        return {"ok": False, "error": _ERR_UNCONFIGURED}
    try:
        content = _call(lambda sbx: sbx.files.read(filename))
    except Exception as e:
        return {"ok": False, "error": f"沙箱读取失败:{type(e).__name__}: {e}"}
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    return {"ok": True, "filename": filename, "content": content}


def list_files() -> dict:
    """列工作区文件。E2B 虽有 files.list,但工作目录语义以代码执行为准,仍跑 os.listdir。"""
    r = execute_python("import os, json; print(json.dumps(sorted(os.listdir('.'))))", timeout=30)
    if not r.get("ok"):
        return r
    try:
        return {"ok": True, "files": json.loads(r["stdout"].strip().splitlines()[-1])}
    except (ValueError, IndexError):
        return {"ok": False, "error": f"list_files 解析失败:{r.get('stdout', '')[:200]}"}


def sandbox_health() -> dict:
    """健康检查:E2B 无 health 端点,跑一句最轻代码探活(首次调用会顺带创建实例)。"""
    if not _configured():
        return {"ok": False, "error": _ERR_UNCONFIGURED}
    try:
        _call(lambda sbx: sbx.run_code("1", timeout=15))
    except Exception as e:
        return {"ok": False, "error": f"沙箱不可达:{type(e).__name__}: {e}"}
    return {"status": "ok"}


@lru_cache(maxsize=1)
def sandbox_meta() -> str:
    """沙箱状态概览,注入 answer 提示词(ADR-0011 静态内容,进程内缓存一次)。

    三态语义(同 mcp_meta,防"已配置但连不上"误报成"未配置"):
    未配置 / 已配置但不可达 / 正常(能力概览)。
    """
    if not _configured():
        return "(执行沙箱未配置:代码执行类任务当前不可用)"
    if sandbox_health().get("status") != "ok":  # 探活成功返回 {status: ok},勿用 .get("ok")
        return "(执行沙箱已配置,但当前连接不可达,执行类任务可能失败)"
    return (
        f"远程 Python 沙箱已就绪(腾讯云 Agent Runtime,模板 {_template()}):"
        "支持执行代码(execute_python)与工作区文件读写(write_file/read_file/list_files),"
        "由执行智能体(executor)实际调用。"
    )
