"""总指挥 Agent (Supervisor)

核心知识点 - Supervisor 模式:
- 总指挥是整个工作流的调度中心，不直接执行具体任务
- 它分析当前状态，决定下一步调用哪个专项 Agent
- 通过条件边(conditional edge)实现动态路由
- 汇总各 Agent 的产出，判断任务是否完成

面试要点:
- Supervisor 模式 vs 去中心化模式: Supervisor 更可控，适合生产环境
- 条件路由是 Supervisor 的核心，通过 LLM 判断下一步该走哪个分支
"""

import logging
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import AgentState
from app.agents.llm import get_llm
from app.config import settings

logger = logging.getLogger(__name__)

SUPERVISOR_SYSTEM_PROMPT = """你是一个竞品调研项目的总指挥。你的职责是：

1. 分析调研主题和当前进度
2. 制定详细的调研任务计划
3. 决定下一步应该由哪个专项 Agent 执行任务

当前可用的专项 Agent:
- researcher: 信息采集 Agent，负责联网搜索采集竞品数据
- analyst: 数据分析 Agent，负责对采集数据进行 SWOT 分析和对比分析
- writer: 报告撰写 Agent，负责生成 Markdown 格式的调研报告
- reviewer: 合规审核 Agent，负责审核报告的准确性和完整性

工作流程:
1. 首先制定任务计划
2. 然后按顺序调度: researcher -> analyst -> writer -> reviewer
3. 如果 reviewer 审核不通过，需要打回 writer 修改

当前状态:
- 调研主题: {topic}
- 竞品列表: {competitors}
- 关注维度: {focus_dimensions}
- 当前迭代次数: {iteration_count}

{context_info}

请分析当前状态，输出你下一步要调度的 Agent 名称。
只能输出以下之一: researcher, analyst, writer, reviewer, FINISH

输出格式:
决策: <agent名称或FINISH>
理由: <简要说明>
"""


def supervisor_node(state: AgentState) -> dict:
    """总指挥节点 - 分析状态并决定下一步调度"""
    logger.info(f"[Supervisor] 开始分析, 当前阶段: {state.get('current_phase', 'init')}") #todo 初始为'' 有错

    llm = get_llm(temperature=0.1)

    # 构建上下文信息
    context_parts = []
    if state.get("task_plan"):
        context_parts.append(f"任务计划: {state['task_plan']}")
    if state.get("research_data"):
        context_parts.append(f"信息采集结果: 已完成 (数据量: {len(state['research_data'])}字)")
    else:
        context_parts.append("信息采集结果: 未完成")
    if state.get("analysis_result"):
        context_parts.append(f"数据分析结果: 已完成 (数据量: {len(state['analysis_result'])}字)")
    else:
        context_parts.append("数据分析结果: 未完成")
    if state.get("report_draft"):
        context_parts.append(f"报告草稿: 已完成 (数据量: {len(state['report_draft'])}字)")
    else:
        context_parts.append("报告草稿: 未完成")
    if state.get("review_feedback"):
        context_parts.append(f"审核意见: {state['review_feedback'][:200]}...")
    if state.get("review_passed"):
        context_parts.append("审核状态: 已通过")

    context_info = "\n".join(context_parts) if context_parts else "暂无，请开始制定计划。"

    prompt = SUPERVISOR_SYSTEM_PROMPT.format(
        topic=state.get("topic", ""),
        competitors=", ".join(state.get("competitors", [])) or "未指定",
        focus_dimensions=", ".join(state.get("focus_dimensions", [])) or "全面分析",
        iteration_count=state.get("iteration_count", 0),
        context_info=context_info,
    )

    response = llm.invoke([SystemMessage(content=prompt)])
    decision_text = response.content.strip()

    logger.info(f"[Supervisor] 决策结果: {decision_text[:100]}")

    # 解析决策
    next_agent = _parse_decision(decision_text, state)

    # 如果是第一次调用，生成任务计划
    task_plan = state.get("task_plan", "")
    if not task_plan:
        task_plan = decision_text

    return {
        "messages": [response],
        "task_plan": task_plan or decision_text,
        "current_phase": next_agent if next_agent != "FINISH" else "done",
    }


def _parse_decision(decision_text: str, state: AgentState) -> str:
    """解析总指挥的决策文本"""
    text_lower = decision_text.lower()

    iteration = state.get("iteration_count", 0)

    # 如果审核已通过，直接结束
    if state.get("review_passed"):
        return "FINISH"

    # 超过最大迭代次数，强制结束
    if iteration >= settings.MAX_RESEARCH_ITERATIONS:
        logger.warning("[Supervisor] 超过最大迭代次数，强制结束")
        return "FINISH"

    # 按阶段顺序调度
    if not state.get("research_data"):
        return "researcher"
    elif not state.get("analysis_result"):
        return "analyst"
    elif not state.get("report_draft"):
        return "writer"
    elif not state.get("review_feedback"):
        return "reviewer"
    elif state.get("review_passed"):
        return "FINISH"
    else:
        # 审核未通过，打回 writer 修改
        if iteration < settings.MAX_REVIEW_RETRIES:
            return "writer"
        return "FINISH"
