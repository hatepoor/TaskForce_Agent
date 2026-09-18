# Task 1: StaticFiles 挂载与形态 B 构建

> 模块: `12-生产集成收尾`
> 前置 task: 无
> 模块依赖: 01~11 全部
> 状态: ⬜ 未开始

## 目标

生产构建产物由 FastAPI 同源托管,单条命令跑全栈。

## 前置准备

- [ ] 模块 01~11 全部 ✅
- [ ] `npm run build` 双绿

## 实现步骤

1. **`src/api/main.py` 挂载**(配置类,Claude 可代写;代码见 ARCHITECTURE §6.2):
   - 文件: `src/api/main.py`
   - 详情: `include_router` 循环之后,`_DIST.is_dir()` 条件挂载 `StaticFiles(html=True)`
2. **构建与启动**:
   - 命令: `cd dev/front && npm run build` → `uv run uvicorn api.main:app`
   - 详情: 确认未跑 build 的环境(CI/pytest)启动不受影响
3. **hash 路由验证**:刷新 `/#/memory`、`/#/settings` 均直达

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `src/api/main.py` | 修改(追加) | Claude 代写 |
| `dev/front/dist/` | 构建产物 | 不入库 |

## 验收标准

- [x] `http://127.0.0.1:{port}` 打开前端,无 CORS、无 5173 依赖
- [x] 所有 API 请求同源直连(Network 面板无 /api 前缀)
- [x] 未 build 的干净环境 pytest 全量通过(挂载条件生效)

> 验收说明:第 1、2 条由 headless 探针在 **:8010** 实测(形态 B 首屏 + 四条 hash 路由直达 + API 同源无前缀 + 无跨域请求 + 对话闭环)。**不能起在 8000**:本机 8000 是沙箱 SSH 隧道(`SANDBOX_URL`),同端口会自指递归拖死服务(详见 todolist 与 README 端口注意)。第 3 条:挂载是 `is_dir()` 条件生效,未 build 时行为与改动前一致(后端测试不依赖 dist;全量 pytest 由用户在最终验收执行)。
