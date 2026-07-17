"""合规审核 Agent (Reviewer)

核心知识点 - 幻觉抑制的关键环节:
- 独立审核节点是抑制幻觉的核心手段之一
- 生成与审核分离（双 LLM 分工），避免"自己审自己"
- 审核不通过时打回 writer 修改，形成循环
- 这体现了 LangGraph 相比 LangChain Chain 的核心优势：支持循环

面试要点:
- 为什么要独立审核？LLM 自己生成的内容自己检查容易"自圆其说"
- 审核维度：事实准确性、内容完整性、格式规范性、逻辑一致性
- 循环次数限制：防止无限打回循环（在 Supervisor 中控制）
"""

import logging
from langchain_core.messages import SystemMessage

from app.agents.state import AgentState
from app.agents.llm import get_llm

logger = logging.getLogger(__name__)

REVIEWER_SYSTEM_PROMPT = """你是一个严谨的调研报告审核专家。你的任务是：

审核竞品调研报告的质量，从以下维度进行评估:

调研主题: {topic}

原始采集数据（用于核实报告中的事实）:
---
{research_data}
---

待审核的报告:
---
{report_draft}
---

请从以下维度审核报告:

1. **事实准确性** (权重: 40%)
   - 报告中的数据是否与采集数据一致
   - 是否存在编造或夸大的内容（幻觉检测）
   - 数据引用是否准确

2. **内容完整性** (权重: 25%)
   - 是否覆盖了所有要求的章节
   - 各竞品是否都有分析
   - 是否遗漏了重要信息

3. **逻辑一致性** (权重: 20%)
   - 结论是否有数据支撑
   - 前后论述是否矛盾
   - 推理过程是否合理

4. **格式规范性** (权重: 15%)
   - Markdown 格式是否正确
   - 表格是否清晰
   - 层次是否分明

输出格式:
审核结果: PASS 或 FAIL
评分: X/100
详细意见:
- 事实准确性: ...
- 内容完整性: ...
- 逻辑一致性: ...
- 格式规范性: ...
修改建议: (如果 FAIL，列出需要修改的具体内容)
"""


def reviewer_node(state: AgentState) -> dict:
    """合规审核节点 - 审核报告质量"""
    logger.info("[Reviewer] 开始审核报告")

    llm = get_llm(temperature=0.1)

    report_draft = state.get("report_draft", "")
    research_data = state.get("research_data", "")

    prompt = REVIEWER_SYSTEM_PROMPT.format(
        topic=state.get("topic", ""),
        research_data=research_data[:3000],  # 限制长度避免超出 token
        report_draft=report_draft,
    )

    response = llm.invoke([SystemMessage(content=prompt)])
    review_feedback = response.content

    # 解析审核结果
    review_passed = _parse_review_result(review_feedback)

    logger.info(f"[Reviewer] 审核完成, 结果: {'PASS' if review_passed else 'FAIL'}")

    return {
        "messages": [response],
        "review_feedback": review_feedback,
        "review_passed": review_passed,
        "final_report": report_draft if review_passed else state.get("report_draft", ""),
        "current_phase": "reviewer_done",
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def _parse_review_result(review_text: str) -> bool:
    """解析审核结果，判断是否通过"""
    text_upper = review_text.upper()

    # 查找明确的 PASS/FAIL 标记
    if "审核结果: PASS" in text_upper or "审核结果:PASS" in text_upper:
        return True
    if "审核结果: FAIL" in text_upper or "审核结果:FAIL" in text_upper:
        return False

    # 如果没有明确标记，根据评分判断
    import re
    score_match = re.search(r"评分[:\s]*(\d+)/100", review_text)
    if score_match:
        score = int(score_match.group(1))
        return score >= 70

    # 默认通过（避免无限循环）
    logger.warning("[Reviewer] 无法解析审核结果，默认通过")
    return True
