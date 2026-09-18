"""联网搜索工具(模块 10 T1):AnySearch API 直连,返回 topN 标题/链接/摘要。

 协议(用户提供文档,2026-09-10):
     POST https://api.anysearch.com/v1/search
         body {query, max_results} -> {code, message, request_id,
               data:{results:[{title, url, snippet, content, ...}], metadata}}
     鉴权:Authorization: Bearer <ANYSEARCH_API_KEY>(可选,匿名按 IP 限流);
     max_results 范围 1-10,默认 10。
 工具侧纪律:网络失败/HTTP 错误/code!=0/无结果一律返回 "[]",不抛异常——
 错误不打扰模型,T3 由 research 子图 LLM 判定"查不到"诚实返回 partial。

 使用位置:
     - agent/subagents/research.py:调研 ReAct 子图唯一工具;
     - tests/test_websearch.py:mock httpx 验证格式与降级。
 """

import json
import sys

import httpx
from langchain_core.tools import tool

from settings.config import get_settings

API_BASE = "https://api.anysearch.com"
HTTP_TIMEOUT = 15  # 单次搜索超时(秒)
SNIPPET_MAX = 300  # 每条摘要截断上限(字符,T3 上下文闸门)
MAX_RESULTS = 5  # 单次返回条数上限(T3:只喂 top3-5)
TITLE_MAX = 100

def _search(query:str,max_results:int)->list[dict]:
    """anysearch 原始调用，错误由调用方兜底，这里只保证不抛"""
    s=get_settings()
    resp=httpx.post(
        f"{API_BASE}/v1/search",
        json={"query": query, "max_results": max_results},
        timeout=HTTP_TIMEOUT,
        headers={"Authorization": f"Bearer {s.anysearch_api_key}"} if s.anysearch_api_key else {},
    )
    if resp.status_code>400:
        return []
    data=resp.json()
    if data.get("code")!=0:
        return []
    return list(data.get("data", {}).get("results", [])or [])

@tool
def web_search(query:str,max_results:int=MAX_RESULTS)->str:
    """联网搜索网页,返回 top 条目的标题/链接/摘要(JSON 列表),用于调研搜-评-再搜。

    Args:
        query: 搜索词,中文或英文均可。
        max_results: 返回条数(1-5,超出截断)。
    """
    n=max(1,min(max_results,MAX_RESULTS))
    try:
        raw=_search(query,n)
    except (httpx.HTTPError, ValueError) as e:
        print(f"[web_search] 搜索失败:{type(e).__name__}: {e}", file=sys.stderr)
        return "[]"
    out = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        title = " ".join(str(r.get("title") or "").split())[:TITLE_MAX]
        url = str(r.get("url") or "").strip()
        snippet = " ".join(str(r.get("snippet") or r.get("content") or "").split())[:SNIPPET_MAX]
        if not title and not snippet:
            continue
        out.append({"title": title, "url": url, "snippet": snippet})
        if len(out) >= n:
            break
    return json.dumps(out, ensure_ascii=False)
