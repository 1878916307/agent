"""信息采集 Agent (Researcher)

核心知识点:
- 这是第一个使用工具的 Agent，通过 bind_tools 将工具绑定到 LLM
- Agent 会自主决定调用哪个工具、传什么参数（这是 Agent 和普通 Chain 的区别）
- 使用 create_react_agent 创建带工具调用的 Agent
- 工具调用结果会写回 State 的 research_data 字段

面试要点:
- Agent 的"自主决策"体现在 LLM 根据任务描述自行构造搜索关键词
- 工具调用失败时的兜底处理
"""

import logging
from langchain_core.messages import SystemMessage

from app.agents.state import AgentState
from app.agents.llm import get_llm
from app.tools.search import search_competitor_info, search_market_data

logger = logging.getLogger(__name__)

RESEARCHER_SYSTEM_PROMPT = """你是一个专业的竞品信息采集整理师。你的任务是：

1. 根据调研主题: {topic}和竞品列表: {competitors}，关注维度: {focus_dimensions}，制定搜索策略
2. 使用搜索工具逐个采集每个竞品的关注维度信息
3. 整理采集结果，输出结构化的竞品数据

输出要求:
- 每个竞品的信息要分类整理
- 标注信息来源
- 如果某个竞品信息缺失，标注"未采集到"

最终请输出完整的采集结果。"""


def researcher_node(state: AgentState) -> dict:
    """信息采集节点 - 使用搜索工具采集竞品数据"""
    logger.info(f"[Researcher] 开始采集, 主题: {state.get('topic', '')}")

    llm = get_llm(temperature=0.2)

    # 绑定搜索工具
    tools = [search_competitor_info, search_market_data]
    llm_with_tools = llm.bind_tools(tools)

    # 构建系统提示
    system_prompt = RESEARCHER_SYSTEM_PROMPT.format(
        topic=state.get("topic", ""),
        competitors=", ".join(state.get("competitors", [])) or "请自行确定竞品列表",
        focus_dimensions=", ".join(state.get("focus_dimensions", [])) or "全面分析",
    )

    messages = [SystemMessage(content=system_prompt)]

    # 第一轮：让 LLM 规划搜索策略并调用工具
    # 由于不使用 LangGraph 的 ReAct Agent，我们手动执行工具调用循环
    all_tool_results = []

    for iteration in range(3):  # 最多3轮工具调用
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        # 检查是否有工具调用
        if not response.tool_calls:
            break

        # 执行所有工具调用
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            logger.info(f"[Researcher] 调用工具: {tool_name}, 参数: {tool_args}")

            # 查找并执行工具
            tool_map = {t.name: t for t in tools}
            if tool_name in tool_map:
                result = tool_map[tool_name].invoke(tool_args)
                all_tool_results.append(f"[{tool_name}] {tool_args.get('query', '')}:\n{result}")

                # 将工具结果作为 ToolMessage 加入消息列表
                from langchain_core.messages import ToolMessage
                messages.append(ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"],
                ))

    # 最终让 LLM 汇总所有采集结果
    final_response = llm.invoke(messages) 
    research_data = final_response.content

    logger.info(f"[Researcher] 采集完成, 数据量: {len(research_data)} 字")

    return {
        "messages": [final_response],
        "research_data": research_data,
        "current_phase": "researcher_done",
        "iteration_count": state.get("iteration_count", 0) + 1,
    }
