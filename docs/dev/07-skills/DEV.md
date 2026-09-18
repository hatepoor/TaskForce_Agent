# 07-Skills 模块开发文档:Skills 渐进式加载

> 状态:见 [ROADMAP.md](../ROADMAP.md) | 代码目录:`tools/skills/`
> 一句话:做完本模块,放一个 SKILL.md 进 `skills/` 目录,主智能体就"知道"这个能力,执行智能体用时才读全文。(支线:核心仅依赖 01;提示词接入需 03)

## 1. 目标与范围

- **做什么**:`SkillRegistry`--扫描 `skills/` 目录(每子文件夹一个 SKILL.md);解析 frontmatter(name/description);`list_metadata()` 供主智能体系统提示词的 `$skills_meta` 插槽消费;`load_skill(name)` 读全文(执行智能体按需调用);`/skills` 命令;附 1-2 个示例 Skill。
- **范围外**:Skill 脚本的执行在沙箱跑(09 装配);本模块只做"扫描、解析与提供数据",提示词插槽本身是 03 定义的。

## 2. 前置依赖

| 依赖模块 | 需要其中的什么 |
|---|---|
| [01-minimal-agent](../01-minimal-agent/DEV.md) | REPL 命令注册表(T1/T3) |
| [03-graph-skeleton](../03-graph-skeleton/DEV.md) | supervisor 提示词的 `$skills_meta` 插槽(仅 T2 需要;03 未完成时 T2 顺延) |

## 3. 产出物(文件清单)

| 文件 | 职责 |
|---|---|
| `tools/skills/loader.py` | `SkillRegistry`:`list_metadata()` / `load_skill(name)` / 目录扫描 |
| `skills/hello-world/SKILL.md` | 示例 Skill(frontmatter + 正文指令) |
| `cli/repl.py`(改) | `/skills` 命令 |
| `tests/test_skills.py` | 扫描/解析/加载单测(临时目录 fixture) |

SKILL.md 约定:frontmatter `name`(唯一标识)、`description`(一句话,常驻提示词用);正文 = 给智能体的完整指令;可选附带脚本文件。

## 4. 分步任务清单

### T1:SkillRegistry 扫描与解析
- [ ] 扫描 `skills/*/SKILL.md`;yaml frontmatter 解析(name 冲突/缺字段报可读错误);`list_metadata()` 返回 `[{name, description, dir}]`;`load_skill(name)` 返回全文(含目录内其他文件的相对路径说明)。
- 验收:临时目录 fixture 单测全绿(正常/缺 frontmatter/重名三情形)。

### T2:元数据接入主图提示词(需 03 已完成,否则顺延)
- [ ] 在主图提示词组装处把 `SkillRegistry.list_metadata()` 渲染进 supervisor.md 的 `$skills_meta` 插槽(格式见 PROMPT-DESIGN §1.1 第 4 段:每行 `name: description`,注明"全文由执行智能体按需加载,你不直接读取");目录变化在会话线程启动时刷新。03 未完成时本任务挂起,先做 T1/T3。
- 验收:03 完成后:放入示例 Skill,REPL 问"你有哪些技能"能列出;日志确认只注入了元数据而非全文。

### T3:/skills 命令
- [ ] 列出 name/description/目录;顺手 `python -m tools.skills.loader` 可独立检查。
- 验收:命令输出与目录一致。

## 5. 验收标准(整模块)

- [ ] 03 完成后:新增一个 SKILL.md,重启会话后主智能体能口头描述该能力;
- [ ] token 验证:系统提示词增量 ≈ 元数据行数 × ~30 token(而非全文);
- [ ] `uv run pytest tests/test_skills.py -q` 全绿。

## 6. 常见坑与规避

| 坑 | 规避 |
|---|---|
| frontmatter 解析失败拖垮启动 | 单个 Skill 解析错误只告警跳过,不阻塞 |
| name 含空格/中文导致工具调用困难 | 校验 `^[a-z0-9-]+$`,不合法报错 |
| 提示词里塞全文 | 渐进式加载是本模块的存在意义,验收含 token 检查 |

## 7. 契约接口

**本模块定义**:
```python
class SkillRegistry:
    def list_metadata(self) -> list[dict]: ...          # [{name, description, dir}]
    def load_skill(self, name: str) -> str: ...          # SKILL.md 全文
```

**本模块消费**:`get_settings`(00)、REPL 命令注册表(01)。
