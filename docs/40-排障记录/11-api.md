# 模块 11:FastAPI 6-router + 收尾 — 问题与解决记录

> 格式规范见 [README.md](README.md)。本文件登记模块 11(chat SSE / HITL 恢复 / 六 router / 测试)开发中的实踩坑位。

## 1. Annotated 联合别名(discriminator union)没有 `.model_validate`

- **现象**:`MCPServerConfig = Annotated[StdioServer | HttpServer, Field(discriminator="transport")]`,调用 `MCPServerConfig.model_validate(config)` 抛 `AttributeError`(被端点 except 兜成 422"配置无效")。
- **根因**:`Annotated[...]` 是 `typing._AnnotatedAlias`,不是 pydantic model 类,没有继承 `BaseModel.model_validate`。区分:模型类(有 class body)才可以直接 `Model.model_validate`;类型别名(union/Annotated)不行。
- **解决**:`from pydantic import TypeAdapter; server = TypeAdapter(MCPServerConfig).validate_python(config)`,discriminator 解析照常工作。
- **关联**:src/api/routers/mcp.py::create_server、tools/mcp/config.py。

## 2. 函数内局部 import 无法被测试 monkeypatch

- **现象**:knowledge router 端点里写 `from tools.rag.store import RAGStore`,测试 `monkeypatch.setattr(kb, "RAGStore", fake)` 不生效,端点仍构造真实 RAGStore 去连 DB。
- **根因**:函数内 `from X import Y` 在每次调用时把 `tools.rag.store.RAGStore` 重新绑定到局部名;monkeypatch 改的是 `api.routers.knowledge.RAGStore` 模块属性,端点根本不查它。REPL 用局部 import 是"首次命令才连库"的惰性手段,API 端 import 本身不连库(构造才连),局部化无收益。
- **解决**:knowledge.py 把 RAGStore import 提到模块顶层(import 不连库,构造才连),测试 monkeypatch 生效。
- **关联**:src/api/routers/knowledge.py、tests/test_api.py;经验:**要给依赖注入/假替换的对象,import 必须落在被 patch 的模块命名空间,函数内局部 import 会绕过 patch**。

## 3. langchain-core 新版 AIMessage.usage_metadata 的 total_tokens 必填

- **现象**:测试里 `AIMessage(content="回复", usage_metadata={"input_tokens": 5, "output_tokens": 3})` 构造抛 `ValidationError: usage_metadata.total_tokens Field required`。
- **根因**:langchain-core 更新后 `UsageMetadata` 的 `total_tokens` 由可选变必填,直接构造 AIMessage 时缺字段即校验失败(旧版本可省略)。
- **解决**:fake AIMessage 的 usage_metadata 补 `"total_tokens": n`。
- **关联**:tests/test_api.py;经验:**mock 消息对象时按当前 langchain-core 的 UsageMetadata 全字段构造,别按旧文档省略 total_tokens**。

## 4. Python bytes 字面量不能含非 ASCII 字符

- **现象**:测试写 `b"# 笔记内容"`(multipart 上传内容),pytest 收集阶段报 `SyntaxError: bytes can only contain ASCII literal characters`,整个 test_api.py 无法导入。
- **根因**:Python 的 `b"..."` 字面量只接受 ASCII;中文必须显式编码。
- **解决**:改 `"# 笔记内容".encode("utf-8")`(或 b 前缀加转义)。
- **关联**:tests/test_api.py::test_knowledge_list_upload_delete。

## 5. ruff B008:`File(...)` 作参数默认值是 FastAPI 惯用写法

- **现象**:`def upload_knowledge(file: UploadFile = File(...))` 被 ruff B008 报"Do not perform function call in argument defaults"。
- **根因**:B008 是通用规则,面向普通函数;FastAPI 的 `File/Query/Body` 参数默认值是声明式 API 的标准用法,非缺陷。
- **解决**:pyproject `[tool.ruff.lint.per-file-ignores]` 对 `src/api/*.py` 追加 `B008`(与 E402 同款理由)。
- **关联**:pyproject.toml;经验:**FastAPI 依赖注入参数(File/Query/Depends)的 B008 应全项目忽略,不要逐个 `# noqa`**。

## 6. 沙箱健康判断键误用 → /health 误报 "unreachable"(09 同型坑复发)

- **现象**:沙箱实际健康(经 ssh 隧道 `GET /health` 返回 `{"status": "ok"}`),但 API `GET /health` 的 `sandbox` 字段恒显示 `"unreachable"`;沙箱真故障时反而能正确透传错误文本(HTTP 502 等),迷惑性强——**健康时误报,故障时正常**。
- **根因**:路由用 `sb.get("ok")` 判断成功,而 `sandbox_health()` 成功时透传的是沙箱原生响应 `{"status": "ok"}`(**无 `ok` 键**)→ 恒落入 else 的 `sb.get("error", "unreachable")` 兜底。与 09 模块 `sandbox_meta` 踩的是同一个键(彼处修好并留了注释"勿用 `.get('ok')`",此路由是漏网处)。测试亦未拦住:`tests/test_api.py` mock 了现实中**不存在的形状** `{"ok": True}`,形成假绿。
- **解决**:`src/api/routers/health.py` 判断改为 `sb.get("status") == "ok"`(契约 §2.2);测试 mock 修为真实形状 `{"status": "ok"}`,并补 sandbox 错误路径用例(断言 error 透传、且 status 不降级——契约:status 只随 DB 降级)。
- **关联**:src/api/routers/health.py、tests/test_api.py、tools/sandbox/client.py::sandbox_meta(参考实现)、API-CONTRACT §2.2;经验:**mock 形状必须抄自真实响应/契约原文,禁止凭直觉造形状;全仓排查 `.get("ok")` 类判断键与真实响应的一致性**。
