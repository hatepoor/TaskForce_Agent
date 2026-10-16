# 只用 LangGraph + LangChain,不使用 deep agents

项目最初计划同时使用 LangGraph、LangChain 和 deep agents 三个框架。deep agents 是对 LangGraph 的一层高层封装,大量使用它意味着学到的是 deep agents 的配置方式而非 LangGraph 本身,与项目"以学习 LangGraph 为核心目的"冲突。因此决定:所有智能体均用 LangGraph 原生 StateGraph 手写,LangChain 仅承担模型抽象、文档加载与文本分割等基础能力,不引入 deep agents,也不引入 LangChain 的旧 chain/agent 抽象。

## Considered Options

- 全部智能体用 deep agents 创建:被否决,与学习目标冲突。
- 选一个智能体用 deep agents 做对照组:被否决,用户决定完全抛弃 deep agents,减少依赖面。
