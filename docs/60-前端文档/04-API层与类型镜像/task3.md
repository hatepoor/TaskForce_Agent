# Task 3: ApiProbeView 端点实测验收

> 模块: `04-API层与类型镜像`
> 前置 task: task2
> 模块依赖: 02
> 状态: ✅ 已完成

## 目标

临时探针页逐端点实测正反路径,确认封装与契约一致,随后删除探针代码。

## 前置准备

- [ ] task2 已完成并通过验收
- [ ] 后端运行中且 docker PG 已起

## 实现步骤

1. **临时 `ApiProbeView.vue`**(验完即删,不算业务代码):
   - 文件: `dev/front/src/views/ApiProbeView.vue`
   - 详情: 依次调 GET 六端点展示原始 JSON 与耗时
2. **正反路径手动验证**:DELETE 一个不存在 doc_id(观察 404/500 详情);MCP test 一个假服务器(确认 `ok:false` 不抛);memory 传中文 key 删除
3. **删除探针代码**,路由表中移除

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/views/ApiProbeView.vue` | 新增→删除 | 临时 |
| `dev/front/src/router/index.ts` | 临时修改→还原 | |

## 验收标准

- [x] 六 GET 端点返回 JSON 且类型断言不报错
- [x] 404/400/`ok:false` 三种"非异常失败"均能以 detail 文案展示
- [x] 探针代码删除后 `npm run build` 双绿
