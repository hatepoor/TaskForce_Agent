"""thread_id 本地持久化(02 模块契约)。

2026-09-04 用户决议:REPL 每次启动开新会话,不再自动接上;本模块保留
current_thread_id 读写,用作"上次会话"提示与 /resume 的落点。

使用位置:
    - cli/repl.py:main() 启动时读上次会话 id / 写新会话 id(/new、/resume 亦走 set_current)。
"""
import uuid
from pathlib import Path

_STORE_DIR = Path(".taskforce")          # 项目根下的隐藏目录(.gitignore 已含)
_STORE_FILE = _STORE_DIR / "current_thread"

class SessionStore:
    """thread_id 的本地文件存储(.taskforce/current_thread),REPL 会话切换的数据源。"""

    @property
    def current_thread_id(self) -> str:
        """读当前 thread_id;文件不存在则生成 sess-{8位hex} 并写入。"""
        if _STORE_FILE.exists():
            # .strip() 去掉换行/空格
            return _STORE_FILE.read_text(encoding="utf-8").strip()
        tid = f"sess-{uuid.uuid4().hex[:8]}"  # 例:sess-3fa2b1c9
        self.set_current(tid)  #复用写方法, 别复制粘贴写文件逻辑
        return tid

    def set_current(self, tid: str) -> None:
        """把指定 thread_id 写入本地文件(目录不存在则先建)。"""
        _STORE_DIR.mkdir(exist_ok=True)                 #目录不存在则建(第二次运行已存在,不报错)
        _STORE_FILE.write_text(tid, encoding="utf-8")      # 显式 utf-8,Windows坑表条款
