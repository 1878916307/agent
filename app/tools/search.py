"""Tavily 搜索工具封装

核心知识点:
- LangGraph Agent 的工具需要使用 @tool 装饰器或 Tool 类封装
- 工具必须有清晰的 docstring，LLM 会根据 docstring 理解工具用途
- 工具返回字符串结果，LLM 基于结果继续推理
"""

from tavily import TavilyClient
from langchain_core.tools import tool
from app.config import settings


def _get_tavily_client() -> TavilyClient:
    """获取 Tavily 客户端实例"""
    return TavilyClient(api_key=settings.TAVILY_API_KEY)


@tool
def search_competitor_info(query: str) -> str:
    """搜索竞品相关信息。输入搜索关键词，返回相关网页内容摘要。
    用于采集竞品的产品功能、定价、技术路线、市场表现等信息。
    """
    try:
        client = _get_tavily_client()
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            include_answer=True,
            include_raw_content=True,
        )

        results = []

        # 如果有直接答案，先加上
        if response.get("answer"):
            results.append(f"【搜索摘要】{response['answer']}")

        # 整理搜索结果
        for i, item in enumerate(response.get("results", []), 1):
            title = item.get("title", "无标题")
            content = item.get("raw_content", "无内容")
            url = item.get("url", "")
            results.append(f"\n--- 结果 {i} ---")
            results.append(f"标题: {title}")
            results.append(f"来源: {url}")
            results.append(f"内容: {content}")

        if not results:
            return "未找到相关信息，请尝试调整搜索关键词。"

        return "\n".join(res3ults)

    except Exception as e:
        return f"搜索出错: {str(e)}，请尝试其他关键词或稍后重试。"


@tool
def search_market_data(query: str) -> str:
    """搜索市场数据和行业报告信息。输入搜索关键词，返回市场规模、增长趋势、市场份额等数据。
    """
    try:
        client = _get_tavily_client()
        response = client.search(
            query=query + " 市场规模 数据 报告",
            search_depth="advanced",
            max_results=5,
            include_answer=True,
            include_raw_content=True,
        )

        results = []
        if response.get("answer"):
            results.append(f"【市场数据摘要】{response['answer']}")

        for i, item in enumerate(response.get("results", []), 1):
            title = item.get("title", "无标题")
            content = item.get("content", "无内容")
            url = item.get("url", "")
            results.append(f"\n--- 市场数据 {i} ---")
            results.append(f"标题: {title}")
            results.append(f"来源: {url}")
            results.append(f"内容: {content}")

        if not results:
            return "未找到相关市场数据。"

        return "\n".join(results)

    except Exception as e:
        return f"搜索出错: {str(e)}"
