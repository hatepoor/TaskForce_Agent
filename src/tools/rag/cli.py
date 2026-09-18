"""RAG 管理命令行:python -m tools.rag.cli upload|list|delete|search(04 模块契约)。

使用位置:
    独立命令行入口(不进 REPL);与 cli/repl.py 的 /kb 命令功能对应,共用 RAGStore。
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path

from tools.rag.store import RAGStore

USAGE = (
    "用法:python -m tools.rag.cli upload <文件路径> | list |"
    " delete <doc_id> | search <关键词>"
)


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in ("upload", "list", "delete", "search"):
        print(USAGE)
        raise SystemExit(1)

    cmd = args[0]
    store = RAGStore()

    if cmd == "upload":
        if len(args) < 2:
            print(USAGE)
            raise SystemExit(1)
        # 路径带引号时剥掉(shell/cmd 复制路径常带引号),否则后缀名带引号匹配失败
        path = Path(args[1].strip().strip("\"'"))
        doc_id, created = store.upload(path, path.name)
        if created:
            print(f"已上传:{path.name} -> {doc_id}")
        else:
            print(f"内容重复,已复用已有文档:{doc_id}(未重复入库)")

    elif cmd == "list":
        docs = store.list_docs()
        if not docs:
            print("(知识库为空)")
        for d in docs:
            print(f"{d['doc_id']}  {d['filename']}  chunks={d['chunks']}\n{d['created_at']}")

    elif cmd == "delete":
        if len(args) < 2:
            print(USAGE)
            raise SystemExit(1)
        store.delete(args[1])
        print(f"已删除:{args[1]}")

    elif cmd == "search":
        if len(args) < 2:
            print(USAGE)
            raise SystemExit(1)
        hits = store.search(args[1], top_k=5)
        if not hits:
            print("(无命中)")
        for h in hits:
            print(f"[{h['score']:.4f}] {h['filename']}#{h['seq']}: {h['content'][:80]}")


if __name__ == "__main__":
    main()
