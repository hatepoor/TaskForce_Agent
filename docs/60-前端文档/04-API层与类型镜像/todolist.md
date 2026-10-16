# API层与类型镜像 开发进度

> 编号: `04`
> 依赖模块: 02
> 最后更新: 2026-09-17

## Task 进度总览

| Task | 名称 | 状态 | 依赖 |
|------|------|------|------|
| [task1](./task1.md) | 类型镜像(types/ 六文件) | ✅ | 无 |
| [task2](./task2.md) | 六资源封装(api/) | ✅ | task1 |
| [task3](./task3.md) | ApiProbeView 端点实测验收 | ✅ | task2 |

## 进度日志

### 2026-09-17

- ✅ task1: types/ 六文件(api/chat/knowledge/memory/skills/mcp) — 契约手工镜像;vue-tsc 零错
- ✅ task2: api/ 六资源封装 — mcp name-in-query(坑 12)封装层消化、memory key encodeURIComponent、upload FormData 不设 Content-Type(120s 超时)、SSE 三入口签名占位(待模块 05)
- ✅ task3: ApiProbeView 实测 — headless 29 项全过(GET×8 正路径 + 反路径 500/400/ok:false/404/中文 key);探针已删、路由已还原;build 双绿 + vitest 10/10
- 验收期修复(后端):/chat/threads/meta 500 — 带参 SQL 中 `LIKE 'sess-%'` 未转义为 `'sess-%%'`(psycopg 占位符解析);补真库回归测试;后端已重启、端点 200(troubleshooting/common.md #4)
