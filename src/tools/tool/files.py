"""内置文件工具(模块 09):read_file/write_file/list_files,操作远程沙箱工作区。

Agent 不直接写本机(ADR-0007):一切文件操作经沙箱;本文件只是把
tools/sandbox/client.py 的函数包装成 @tool 形态供 executor 绑定。
返回值统一 str(dict)——ToolMessage content 是字符串,保持工具层无结构化负担。
"""
from langchain_core.tools import tool

from tools.sandbox.client import list_files as _list_files
from tools.sandbox.client import read_file as _read_file
from tools.sandbox.client import write_file as _write_file


@tool
def read_file(filename: str) -> str:
    """读取沙箱工作区文件内容。文件不存在时返回错误说明。"""
    return str(_read_file(filename))


@tool
def write_file(filename: str, content: str) -> str:
    """在沙箱工作区写文件(filename 为相对路径,如 hello.py、data/result.csv)。"""
    return str(_write_file(filename, content))


@tool
def list_files() -> str:
    """列出沙箱工作区全部文件名。"""
    return str(_list_files())
