# 模块 R:ReAct 化改造 — 问题与解决记录

> 格式规范见 [README.md](README.md)。本文件登记模块 R(子智能体 ReAct 化,ADR-0010)开发中的实踩坑位。

## 1. 直挂子图的同键名通道即共享:子图消息并进主图历史

- **现象**:retriever ReAct 子图(共享键直挂)上线后,`tests/test_graph.py` 全图测试中 supervisor 收到的 messages 里混入了 ToolMessage;answer 的输入同样被污染;fake model 按消息形态分发时错乱。
- **根因**:LangGraph 直挂模式("Add a subgraph as a node")的共享机制是**按键名匹配**——子图 state 里声明了 `messages: Annotated[list, add_messages]`,与主图 AgentState 的 `messages` 同名,即成为共享通道:子图整个 ReAct 历史(System/Human/AIMessage(tool_calls)/ToolMessage)被 add_messages 合并进主图。此前 stub 子图没有 messages 键所以从未暴露;"子图 messages 键不外泄"的说法只对 wrapper 模式成立。
- **解决**:子图消息键改名 `react_msgs`(仍配 `add_messages` reducer)。工具节点是手写的(等价 ToolNode),不依赖 prebuilt ToolNode 的 "messages" 键名契约,改名无副作用;还顺带实现了真正的"子智能体独立上下文"(主图看不到子图消息,子图看不到主图消息)。
- **关联**:ADR-0010 红线 2(已按实证修正)、react-refactor-plan.md §1.2、docs.langchain.com/oss/python/langgraph/use-subgraphs(共享键直挂)、troubleshooting/03(直挂方案的来源)。

## 2. fake model 的模式标记是单发的,会被下一次调用冲掉

- **现象**:全图测试中 Route 对象被塞进子图消息通道,报 `NotImplementedError: Unsupported message type: Route`(消息强制转换失败);或 supervisor 收到 AIMessage 当路由结果(`'AIMessage' object has no attribute 'next'`)。
- **根因**:FakeScriptedLLM 用"with_structured_output/bind_tools 设置模式 → 下一次 invoke 消费"的单发标记。但 bind_tools 在**建图时**调用,随后 supervisor 的 with_structured_output(Route) 把 react 模式冲掉,导致 agent 节点的 invoke 走了 routes 脚本返回 Route;Route 被当作 AIMessage 加进 react_msgs 触发消息强制转换报错。
- **解决**:fake 改为按**消息形态**分发:pending 单发模式(route/answer_out)优先;首条系统提示含 "kb_search" → react 首帧;消息含 ToolMessage → react 续轮(脚本耗尽自动收尾);否则普通 invoke 走 routes 脚本。见 test_graph.py::FakeScriptedLLM。
- **关联**:tests/test_graph.py、tests/test_retriever.py(FakeReActLLM 同思路:react_done 后的 invoke 视为 finalize 的 AnswerOut 调用)。

## 3. 轮数上限的"自然收尾"与"被掐断"要按最后一条消息判断

- **现象**:若 finalize 仅按 `iteration >= max_iterations` 判定 partial,模型恰好在最后一轮上限处给出最终答案时会被误判为"被掐断"。
- **根因**:iteration 计的是"已完成工具轮数",不区分"模型还想继续调工具"与"模型已自然收尾"。
- **解决**:finalize 判据用 `getattr(react_msgs[-1], "tool_calls", None)`——最后一条消息仍带 tool_calls 即被上限截停(partial + warnings);否则视为自然收尾,走正常分支。见 retriever.py::build_summary。
- **关联**:ADR-0010 R6(双层防失控)、react-refactor-plan.md §1.2。

## 4. 测试直连 public 表,pytest 一次跑完清空用户真实知识库

- **现象**:REPL 上传的文档检索突然全部空命中;此前单独探针还能搜到。
- **根因**:test_rag.py 的 `test_dim_mismatch_raises` 在 finally 中无条件 `DROP TABLE chunks/documents`(public schema)——跑一次 pytest 就把用户上传的真实文档连块删光。模块 04 的 roundtrip 测试还会把 fixture 文档插进用户知识库(反向污染)。
- **解决**:store fixture 改为**隔离 schema**——随机建 `test_rag_xxxx` schema,经连接串 `options=-csearch_path%3D{schema}%2Cpublic` 让 RAGStore 全部建表/插查落在该 schema,测完 `DROP SCHEMA CASCADE`;维度测试照常在隔离 schema 内伪造 vector(4) 表,public 数据零接触。
- **关联**:tests/test_rag.py、04-DEV 坑表(已回填)、教训:**任何测试不得对共享 schema 做无条件的 DDL**。

## 5. glm 对 QA 型收尾不调强制工具,with_structured_output 解析 content 即崩

- **现象**:finalize 的 `with_structured_output(AnswerOut)` 抛 `ValueError: expected value at line 1 column 1`(37s 后);同一模型 supervisor 的 Route 结构化调用一直正常。
- **根因**:glm-5.3-flash 遇到"基于命中组织答案"这类 QA 任务时,经常无视强制 tool_choice、直接把回答写在 content 里(甚至自包成 markdown 伪 schema);function-calling 式结构化输出解析非 JSON content 开头即崩。supervisor 是纯分类决策,模型老老实实调工具,故不受影响。
- **解决**:finalize **取消第二次 LLM 调用**,直接解析 agent 最终消息——JSON(含围栏)则提取 conclusion/key_points,否则空白折叠后截断 100 字;同时 retriever.md 硬性要求"收尾用 2-3 句自然语言,禁止 JSON/标题/字段名"。顺带每轮省 16-37s。
- **关联**:retriever.py::_extract_answer、tests/test_retriever.py(test_extract_answer_variants)、经验:**结构化输出对"分类"稳、对"生成"不稳;生成型收尾优先解析模型自然输出**。
