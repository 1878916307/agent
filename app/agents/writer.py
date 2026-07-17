"""报告撰写 Agent (Writer)

核心知识点:
- 读取分析结论，生成最终的 Markdown 格式报告
- 当审核不通过时，会收到 review_feedback 并据此修改报告
- 展示了 Agent 如何根据反馈迭代优化输出

面试要点:
- 打回修改机制: reviewer 不通过 -> writer 收到反馈 -> 重新生成
- 这是 Supervisor 模式中的"循环"能力的体现
"""

import logging
from langchain_core.messages import SystemMessage

from app.agents.state import AgentState
from app.agents.llm import get_llm

logger = logging.getLogger(__name__)

WRITER_SYSTEM_PROMPT = """你是一个专业的调研报告撰写专家。你的任务是：

基于数据分析 Agent 提供的分析结论，撰写一份完整、专业的竞品调研报告。

调研主题: {topic}
竞品列表: {competitors}

分析结论:
---
{analysis_result}
---

{review_section}

请撰写一份 Markdown 格式的竞品调研报告，必须包含以下章节:

# 调研报告标题

## 1. 执行摘要
- 调研背景和目的
- 核心发现概述（3-5条）

## 2. 调研方法
- 数据来源和采集方式
- 分析框架

## 3. 竞品概览
- 各竞品基本信息（公司背景、产品定位、目标用户）

## 4. 详细对比分析
- 产品功能对比（表格形式）
- 技术路线对比
- 定价策略对比
- 市场表现对比

## 5. SWOT 分析
- 各竞品 SWOT 分析

## 6. 市场趋势与机会
- 行业发展趋势
- 技术演进方向
- 潜在市场机会

## 7. 结论与建议
- 核心结论
- 行动建议
- 风险提示

## 8. 附录
- 数据来源列表
- 术语说明

写作要求:
- 语言专业、简洁、客观
- 数据要有来源标注
- 表格要清晰规范
- 结论要有数据支撑
"""

WRITER_REVISION_PROMPT = """

---
审核意见（上一次报告的问题）:
{review_feedback}

请根据以上审核意见，修改并完善报告。重点解决审核中指出的问题。
保留报告中正确的部分，修正有问题的部分。
"""


def writer_node(state: AgentState) -> dict:
    """报告撰写节点 - 生成或修改调研报告"""
    logger.info("[Writer] 开始撰写报告")

    llm = get_llm(temperature=0.5)

    analysis_result = state.get("analysis_result", "暂无分析数据")
    review_feedback = state.get("review_feedback", "")

    # 如果有审核反馈，追加修改指令
    review_section = ""
    if review_feedback:
        review_section = WRITER_REVISION_PROMPT.format(review_feedback=review_feedback)
        logger.info("[Writer] 收到审核反馈，进行修改")

    prompt = WRITER_SYSTEM_PROMPT.format(
        topic=state.get("topic", ""),
        competitors=", ".join(state.get("competitors", [])) or "未指定",
        analysis_result=analysis_result,
        review_section=review_section,
    )

    response = llm.invoke([SystemMessage(content=prompt)])
    report_draft = response.content

    logger.info(f"[Writer] 报告完成, 数据量: {len(report_draft)} 字")

    return {
        "messages": [response],
        "report_draft": report_draft,
        "current_phase": "writer_done",
    }
