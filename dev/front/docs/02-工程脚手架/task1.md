# Task 1: 工程初始化与代理配置

> 模块: `02-工程脚手架`
> 前置 task: 无
> 模块依赖: 无
> 状态: ✅ 已完成

## 目标

`dev/front/` 工程创建完成,Vite dev server 可启动,代理配置就位。

## 前置准备

- [ ] Node.js ≥ 20.19 已安装
- [ ] 后端 `uv run uvicorn api.main:app` 可在 8000 端口启动

## 实现步骤

1. **脚手架生成与清理**(配置类,Claude 可代写):
   - 文件: `dev/front/*`
   - 详情: `npm create vite@latest . -- --template vue-ts`;删除 `HelloWorld.vue`、示例 svg 与样式
2. **vite.config.ts**:别名 + `/api` proxy + rewrite + SSE 防缓冲(全文见 ARCHITECTURE §1.5)
   - 文件: `dev/front/vite.config.ts`
3. **环境文件与 .gitignore**:`.env.development`(VITE_API_BASE=/api)、`.env.production`(空)、忽略规则
   - 文件: `dev/front/.env.development`、`.env.production`、`.gitignore`
4. **tsconfig 严格模式基线**(ARCHITECTURE §1.4)
   - 文件: `dev/front/tsconfig.app.json`
5. **package.json scripts**:`dev/build/preview/typecheck/test/lint`(§6.1)
   - 文件: `dev/front/package.json`

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/vite.config.ts` | 新增 | proxy + 别名 + SSE 防缓冲 |
| `dev/front/.env.development` / `.env.production` | 新增 | 入库 |
| `dev/front/tsconfig.app.json` | 修改 | 严格项 |
| `dev/front/package.json` | 修改 | scripts |
| `dev/front/.gitignore` | 新增 | 四条规则 |

## 验收标准

- [x] `npm run dev` 启动在 5173 端口且 `strictPort` 生效
- [x] `curl http://localhost:5173/api/health` 透传后端 JSON(rewrite 生效)
- [x] `npx vue-tsc --noEmit` 零错误
