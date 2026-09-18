"""提示词加载器:prompts/ 数据包的唯一读取口(零代码 md + $ 占位符渲染)。

使用位置:
    - agent/supervisor.py:load_prompt("supervisor");
    - agent/answer.py:load_prompt("answer");
    - agent/subagents/retriever.py:load_prompt("base") + load_prompt("subagents/retriever")。
"""
from importlib import resources
from string import Template


def load_prompt(name:str,**slots:str)->str:
    """
    读 prompts/<name>.md 并渲染 $ 占位符。
    例:load_prompt("supervisor", agents_md="...", memory="...")
    占位符必须用 $name 形式(string.Template):提示词内含 JSON 花括号,
    str.format 会崩;缺失插槽 Template.substitute 直接 KeyError,符合预期。
    """
    text=resources.files("prompts").joinpath(f"{name}.md").read_text(encoding="utf-8")
    return Template(text).substitute(**slots)
