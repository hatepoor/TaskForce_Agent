# 二、端点全表 · Skills 资源 + MCP 资源

> 一句话: Skills 资源:技能元数据列表;MCP 资源:服务器列表、新增 / 覆盖、删除、连通性测试
> 体系: 前端文档 · API-CONTRACT · 端点分片
> 上游: [README](./README.md)
> 下游: [05-端点-设置与健康.md](./05-端点-设置与健康.md)
> 细节见: [手册索引](./README.md)

### 2.5 Skills 资源

#### `GET /skills` — 技能元数据列表

```json
{
  "skills": [
    { "name": "pdf-extract", "description": "从 PDF 中提取结构化文本与表格", "dir": "F:\\project\\my_pro_3\\skills\\pdf-extract" }
  ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | `string` | 已通过 `^[a-z0-9-]+$` 校验,可安全用作 key |
| `description` | `string` | frontmatter 的 description,可能为 `""` |
| `dir` | `string` | **服务端本地绝对路径**;仅调试展示,不做正式 UI 元素 |

**前端注意**:本接口每次现扫目录,但智能体侧 `_skills_meta()` 是 `lru_cache(maxsize=1)`——新增技能目录后**本接口立刻可见,但智能体路由仍用旧缓存**,需重启后端。技能页加一行提示:"技能变更需重启后端生效"。

### 2.6 MCP 资源

#### `GET /mcp/servers` — 服务器列表(name → config 字典)

```json
{
  "servers": {
    "context7": { "transport": "stdio", "command": "npx", "args": ["-y", "@upstash/context7-mcp"], "env": {} },
    "docs-langchain": { "transport": "http", "url": "https://docs.langchain.com/mcp", "headers": {} }
  }
}
```

后端 `model_dump(exclude_none=True)`,**未设置的字段不会出现**(`args`/`env`/`headers` 可能整个缺失),渲染时全部按可选处理。

| transport | 字段 |
|---|---|
| `"stdio"` | `command: string`(必填)、`args: string[]`、`env: Record<string,string>` |
| `"http"` | `url: string`(必填)、`headers: Record<string,string>` |

错误码:配置文件 JSON 损坏时 `MCPConfigError` 未捕获 → 500。

#### `POST /mcp/servers` — 新增/覆盖服务器

**B6 落地前(现状,前端必须按此实现)**:参数在 **query string** 里,body 直接是 config 对象(FastAPI 对"标量参数 + 单一 dict 体"的默认行为):

```http
POST /mcp/servers?name=github-mcp
Content-Type: application/json

{ "transport": "stdio", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"], "env": { "GITHUB_TOKEN": "ghp_xxx" } }
```

```js
await fetch(`${BASE}/mcp/servers?name=${encodeURIComponent(name)}`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(config),
})
```

成功:`{ "ok": true, "name": "github-mcp" }`。**同名会静默覆盖**,前端应做二次确认。

错误码:

| 码 | 条件 | detail |
|---|---|---|
| 422 | `TypeAdapter(MCPServerConfig)` 解析失败(如 `transport` 缺失/非法) | `配置无效:{原始 pydantic 异常}` |
| 500 | `name` 不匹配 `^[a-z0-9_-]+$`(B8 落地前 `_check_name` 未捕获) | — |

前端做名称/格式校验比依赖后端更稳。

#### `DELETE /mcp/servers/{name}` — 删除服务器

成功:`{ "ok": true, "name": "github-mcp" }`。不存在返 404(`服务器 {name} 不存在`)。

#### `POST /mcp/servers/{name}/test` — 连通性探测

请求体:无。后端最长阻塞约 10 秒,前端必须单独给超时/loading 态。

探测到工具:

```json
{ "ok": true, "name": "context7", "tools": ["resolve-library-id", "get-library-docs"] }
```

探测失败(降级,不抛):`{ "ok": false, "name": "context7", "tools": [] }`。**`ok:false` 是正常业务返回,不是异常,UI 显示"未连通"而非红色报错。**

`tools` 形状 B8 落地前未确定(可能是对象数组),前端防御式渲染:

```js
const label = typeof t === 'string' ? t : (t?.name ?? JSON.stringify(t))
```

错误码:404(服务器不存在)。
