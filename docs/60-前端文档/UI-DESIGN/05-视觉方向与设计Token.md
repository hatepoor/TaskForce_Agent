# 5. 视觉方向与设计 Token

> 一句话: 视觉基调、字号与排版层级、CSS 变量草案(tokens.css 直接采用)
> 体系: 前端文档 · UI-DESIGN · 设计分片
> 上游: [README](./README.md)
> 下游: [06-键盘与滚动细节.md](./06-键盘与滚动细节.md)
> 细节见: [手册索引](./README.md)

## 5. 视觉方向与设计 Token

### 5.1 基调

**深色为默认,浅色跟随系统备选。** 理由:这是长时间盯着的本地工具,深色降低视觉疲劳;深色下"低亮度分层"比浅色更容易做得克制——近黑底 + 微弱亮度差分层,极少分隔线撑起结构。

- **分层靠亮度,不靠边框**。四级背景 `base → panel → raised → hover`,每级亮度差 4–6%。边框只在表格、输入框等真正需要时出现,对比度极低。
- **只有一个强调色**:冷蓝 `#5b9dff`。只出现在四处:当前导航项、主按钮、焦点环、链接。**其余一律无色。**
- **身份色只给三个子智能体**:8px 圆点 + 12px 标签文字,不做色块背景。这是唯一多色区域,承载真实信息。
- **语义色只在真出问题时用**:成功绿几乎不出现(大部分"成功"用灰字表达),警告黄、危险红只在错误条与删除按钮。
- **圆角小**:4/6/8px。开发者工具的"认真感"来自紧凑和对齐,不是大圆角卡片。
- **动效几乎为零**:hover 过渡(120ms)+ 轨迹点呼吸态,**仅此两处**。没有消息飞入、没有列表错峰淡入、没有骨架屏闪光。`prefers-reduced-motion` 下全部关闭。

**"像认真做的开发者工具"的三个具体判据**:① 等宽字体用在所有 id、路径、命令、用量数字;② 表格悬停整行高亮、数字列右对齐;③ 焦点环清晰可见(2px outline offset 1px),键盘可达。

### 5.2 字号与排版层级

| 层级 | 字号 | 行高 | 字重 | 用途 |
|---|---|---|---|---|
| 视图标题 | 16px | 1.4 | 600 | "知识库""长期记忆" |
| 对话正文 | 14px | 1.7 | 400 | AI 回复、用户气泡 |
| 外壳正文 | 13px | 1.5 | 400 | 导航、按钮、表单、列表 |
| 元信息 | 12px | 1.5 | 400 | 轨迹条、表格、时间、用量 |
| 角标 | 11px | 1.4 | 500 | 状态标签、计数 |
| 代码 | 12.5px | 1.6 | 400 | 代码块、id、路径、usage |

中文字体栈必含 `"Microsoft YaHei"`(Windows 开发机),等宽首选 `"Cascadia Mono"`(Win11 自带)。

### 5.3 CSS 变量草案(定稿,tokens.css 直接采用)

```css
:root {
  /* ── 背景:四级分层,近黑非纯黑 ───────────────────────── */
  --bg-base:        #101114;  /* 应用底:对话区 */
  --bg-panel:       #16181d;  /* 侧栏、导航轨 */
  --bg-raised:      #1c1f26;  /* 卡片、用户气泡、表格行悬停 */
  --bg-input:       #1a1d23;  /* 输入框、引用块 */
  --bg-hover:       #22262e;  /* 通用悬停 */

  /* ── 描边:低对比,能省则省 ──────────────────────────── */
  --border-subtle:  #23262e;
  --border-strong:  #32363f;
  --border-focus:   #5b9dff;

  /* ── 文本 ──────────────────────────────────────────── */
  --text-primary:   #e6e8ec;
  --text-secondary: #a2a8b4;
  --text-muted:     #6b7280;
  --text-inverse:   #0f1115;

  /* ── 强调色:全界面唯一 ─────────────────────────────── */
  --accent:         #5b9dff;
  --accent-hover:   #7cb0ff;
  --accent-soft:    rgba(91, 157, 255, .12);

  /* ── 语义 ──────────────────────────────────────────── */
  --success:        #4ec9a3;
  --warning:        #e0b252;
  --danger:         #e06c75;
  --danger-soft:    rgba(224, 108, 117, .10);

  /* ── 子智能体身份色:仅用于圆点与标签文字 ────────────── */
  --agent-retriever: #5b9dff;
  --agent-research:  #a98bff;
  --agent-executor:  #e0a552;

  /* ── 字号 ──────────────────────────────────────────── */
  --fs-xs:   11px;  --fs-sm: 12px;  --fs-md: 13px;
  --fs-lg:   14px;  --fs-xl: 16px;  --fs-code: 12.5px;

  /* ── 行高 ──────────────────────────────────────────── */
  --lh-tight: 1.35;  --lh-base: 1.5;  --lh-body: 1.7;

  /* ── 间距:4 的倍数 ─────────────────────────────────── */
  --sp-1: 4px;  --sp-2: 8px;  --sp-3: 12px;
  --sp-4: 16px; --sp-5: 24px; --sp-6: 32px;

  /* ── 圆角:小即是克制 ───────────────────────────────── */
  --r-sm: 4px;  --r-md: 6px;  --r-lg: 8px;  --r-full: 999px;

  /* ── 阴影:深色下只在浮层用 ─────────────────────────── */
  --shadow-pop: 0 8px 24px rgba(0, 0, 0, .45);
  --shadow-pop-sm: 0 2px 8px rgba(0, 0, 0, .35);

  /* ── 字体 ──────────────────────────────────────────── */
  --font-ui:   system-ui, -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
  --font-mono: "Cascadia Mono", ui-monospace, Consolas, "JetBrains Mono", monospace;

  /* ── 动效 ──────────────────────────────────────────── */
  --t-fast: 120ms ease;  --t-base: 200ms ease;

  /* ── 布局 ──────────────────────────────────────────── */
  --layout-rail:   56px;
  --layout-panel:  240px;
  --layout-drawer: 360px;
  --measure-text:  760px;   /* 对话正文最大宽度 */
  --measure-page:  1040px;  /* 管理页内容最大宽度 */

  /* ── 焦点环 ────────────────────────────────────────── */
  --focus-ring: 2px solid var(--border-focus);
  --focus-offset: 1px;
}

/* 浅色备选:跟随系统,不提供手动切换按钮 */
@media (prefers-color-scheme: light) {
  :root {
    --bg-base:        #ffffff;
    --bg-panel:       #f7f8fa;
    --bg-raised:      #ffffff;
    --bg-input:       #f2f3f5;
    --bg-hover:       #eef0f3;
    --border-subtle:  #e4e6ea;
    --border-strong:  #d0d3d9;
    --text-primary:   #1a1d23;
    --text-secondary: #5a616e;
    --text-muted:     #8b919c;
    --accent:         #2f6fe4;
    --accent-hover:   #2359c4;
    --accent-soft:    rgba(47, 111, 228, .10);
    --success:        #1f9e78;
    --warning:        #b07d18;
    --danger:         #cf3f4a;
    --agent-retriever:#2f6fe4;
    --agent-research: #7d4fd4;
    --agent-executor: #b8761a;
    --shadow-pop:     0 8px 24px rgba(16, 20, 30, .12);
  }
}
```
