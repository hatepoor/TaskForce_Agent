# 00-Bootstrap 模块开发文档:脚手架与基础设施

> 状态:见 [ROADMAP.md](../ROADMAP.md) | 代码目录:项目根配置 + `settings/config.py` + `settings/db/base.py`
> 一句话:做完本模块,系统具备"一键起 PG + 一键连库 + 配置带启动断言"的地基,但还没有任何 Agent。

## 1. 目标与范围

- **做什么**:uv 工程化(依赖分组、Python 钉死、hatchling 打包 src 六包)、Docker Compose 起 pgvector、`.env.example`、`settings/config.py`(两套 LLM/embedding 配置 + 启动断言)、`settings/db/base.py`(psycopg 连接辅助 + 幂等建扩展)、ruff 配置。
- **范围外**:不做任何 LangGraph 图、不接 LLM、不做 Store/自建业务表(业务表随 04/06 建)。

> **进度说明:目录骨架与全部配置文件已于项目初始化时创建完成**(src 六包目录 + 全部 `__init__.py`、`pyproject.toml`、`.python-version`、`docker-compose.yml`、`.env.example`、`.gitignore`、`agents.md`、`mcp_config.json` 占位,根目录脚手架残留 `main.py`/`test_main.http` 已删除)。本模块剩余工作为 T4-T7(代码与联调验证)。

## 2. 前置依赖

无。本模块是依赖链的根。

## 3. 产出物(文件清单)

| 文件 | 职责 | 状态 |
|---|---|---|
| `pyproject.toml` | 依赖分组(运行时 + dev)、Python `>=3.12,<3.13`、hatchling、`packages` = src 六包、aliyun 镜像、ruff 配置 | ✅ 已建 |
| `.python-version` | 内容 `3.12` | ✅ 已建 |
| `docker-compose.yml` | pgvector/pgvector:pg16,主机端口 **5433**,healthcheck,数据卷 | ✅ 已建 |
| `.env.example` | 全部配置模板(LLM/Embedding/DB/沙箱/LOG_LEVEL) | ✅ 已建 |
| `.gitignore` | `.env`、`.taskforce/`、IDE、缓存 | ✅ 已建 |
| `agents.md` | 全局背景占位(用户手工维护,06 生效) | ✅ 已建 |
| `mcp_config.json` | 空配置占位(08 定义 schema) | ✅ 已建 |
| `settings/config.py` | `Settings` + `get_settings()`(lru_cache 单例)+ `assert_ready()` | 🔲 待写 |
| `settings/db/base.py` | psycopg 连接辅助 + `CREATE EXTENSION IF NOT EXISTS vector` 幂等执行 | 🔲 待写 |
| 目录骨架 | `src/{agent,tools,prompts,settings,api,cli}` 全部子包与 `__init__.py`、`tests/`、`skills/` | ✅ 已建 |

## 4. 分步任务清单

### T1:✅(已完成)目录骨架与配置文件
初始化时创建,验收:`find src -name "__init__.py" | wc -l` 返回 16;`uv run python --version` 输出 3.12.x。

### T2:✅(已完成)pyproject 改写 + uv sync
- [ ] 执行 `uv sync`,提交更新后的 uv.lock。
- 验收:`uv sync` 成功;`uv run python -c "import langgraph, langchain_openai, psycopg"` 无报错;`uv run python -c "from settings import __doc__"` 不报 ImportError(hatchling 六包安装生效)。

### T3:✅(已完成)docker-compose 起 PG
- [ ] `docker compose up -d`;复制 `.env.example` 为 `.env` 并填写 LLM 三件套。
- 验收:`docker compose ps` 显示 healthy;`docker compose exec postgres pg_isready -U taskforce` 返回 accepting。

### T4:实现 settings/config.py
`settings/config.py`:`pydantic_settings.BaseSettings`(env_file=".env", extra="ignore"),字段与 `.env.example` 一一对应;`assert_ready()` 校验 LLM 三件套与 DATABASE_URL 非空,缺失则抛出**含变量清单的中文 RuntimeError**;`@lru_cache get_settings()` 内先 assert 再返回。
- 验收:无 .env 时 `uv run python -c "from settings.config import get_settings; get_settings()"` 抛出中文缺失清单;有 .env 后正常返回对象。

### T5:实现 settings/db/base.py
- [ ] `get_conn(database_url)` 上下文辅助 + `ensure_vector_ext(database_url)` 执行 `CREATE EXTENSION IF NOT EXISTS vector`;全部用 `pathlib` 处理路径、显式 `encoding="utf-8"` 读写。
- 验收:重复执行两次 `ensure_vector_ext` 均成功;`SELECT extname FROM pg_extension` 能查到 vector。

### T6:ruff 验证
- 验收:`uv run ruff check .` 通过(配置已入 pyproject)。

### T7:pytest 骨架验证
- [ ] 确认 `uv run pytest -q` 空目录下正常退出(无测试时返回码 5 可接受,或加一个 smoke 测试)。
- 验收:`uv run pytest -q` 无导入错误。

## 5. 验收标准(整模块)

- [ ] `uv sync` 成功;`docker compose up -d` 后 PG healthy;
- [ ] `uv run python -c "from settings.config import get_settings; s=get_settings(); print(s.llm_model)"` 正常输出;
- [ ] `ensure_vector_ext` 幂等;`ruff check .` 通过;
- [ ] 模块完成后在 ROADMAP 总表置 ✅。

## 6. 常见坑与规避(Windows 特供)

| 坑 | 表现 | 规避 |
|---|---|---|
| Docker 未启动 / 非 WSL2 | `docker ps` 报错 | 开机自启关闭时先启动 Docker Desktop;`wsl --set-default-version 2` |
| 5432 端口被占 | 容器端口映射失败 | 已用 5433;若 5433 也冲突,改 compose 与 DATABASE_URL 两处 |
| 控制台 GBK | 中文/emoji 乱码或 UnicodeEncodeError | `PYTHONUTF8=1` 环境变量(一劳永逸);代码内所有文件 IO 显式 utf-8 |
| 路径分隔符 | 手拼 `\` 出错 | 全项目只用 `pathlib.Path` |
| 代理拦截 | 方舟 API 连不上 | 给 `NO_PROXY` 加 `localhost,127.0.0.1` |
| langgraph 版本漂移 | checkpoint-postgres 1.x/2.x API 不同 | 已锁 `>=2.0.0`;langchain-openai 与 langchain-core 大版本一起动 |
| 六包顶层名通用(agent/tools 等) | 潜在第三方同名包冲突 | 当前依赖树无同名包;后续新增依赖时留意 |

## 7. 契约接口

**本模块定义**(其他模块禁止复制定义):
```python
# settings/config.py
class Settings(BaseSettings):
    llm_base_url: str; llm_api_key: str; llm_model: str
    llm_input_price_per_m: float; llm_output_price_per_m: float
    embedding_base_url: str; embedding_api_key: str; embedding_model: str
    database_url: str; sandbox_url: str; sandbox_api_key: str
    log_level: str
def get_settings() -> Settings: ...          # lru_cache 单例,内含 assert_ready()

# settings/db/base.py
def get_conn(database_url: str) -> ContextManager[psycopg.Connection]: ...
def ensure_vector_ext(database_url: str) -> None: ...
```

**本模块消费**:无。
