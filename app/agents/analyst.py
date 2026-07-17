"""数据分析 Agent (Analyst)

核心知识点:
- 这是纯 LLM 推理节点（不使用工具），读取 State 中 research_data 进行分析
- 展示了多 Agent 之间如何通过 State 传递数据
- 分析结果写回 State 的 analysis_result 字段

面试要点:
- 节点间数据传递: 通过共享 State 实现，而非直接通信
- 职责分离: 采集和分析分开，各自 prompt 专注自己的任务
"""

import logging
from langchain_core.messages import SystemMessage

from app.agents.state import AgentState
from app.agents.llm import get_llm

logger = logging.getLogger(__name__)

ANALYST_SYSTEM_PROMPT = """你是一个资深的数据分析师，擅长竞品分析和市场研究。你的任务是：

基于信息采集 Agent 提供的原始数据，进行深度分析并输出结构化的分析结论。

调研主题: {topic}
竞品列表: {competitors}
关注维度: {focus_dimensions}

以下是信息采集 Agent 提供的原始数据:
---
{research_data}
---

请完成以下分析任务:

1. **竞品对比分析**
   - 从{focus_dimensions}这些维度进行横向对比
   - 找出各竞品的差异化优势

2. **SWOT 分析**
   - 对每个主要竞品进行 SWOT 分析（优势、劣势、机会、威胁）

3. **市场趋势分析**
   - 行业整体发展趋势
   - 技术演进方向
   - 市场竞争格局

4. **关键发现与洞察**
   - 提炼3-5个最重要的发现
   - 给出数据支撑

输出要求:
- 使用结构化格式，层次清晰
- 每个结论要有数据/事实支撑
- 区分事实和推测，推测部分标注"推测"
"""


def analyst_node(state: AgentState) -> dict:
    """数据分析节点 - 对采集数据进行深度分析"""
    logger.info("[Analyst] 开始分析")

    llm = get_llm(temperature=0.3)

    research_data = state.get("research_data", "暂无数据")

    prompt = ANALYST_SYSTEM_PROMPT.format(
        topic=state.get("topic", ""),
        competitors=", ".join(state.get("competitors", [])) or "未指定",
        focus_dimensions=", ".join(state.get("focus_dimensions", [])) or "全面分析",
        research_data=research_data,
    )

    response = llm.invoke([SystemMessage(content=prompt)])
    analysis_result = response.content

    logger.info(f"[Analyst] 分析完成, 数据量: {len(analysis_result)} 字")

    return {
        "messages": [response],
        "analysis_result": analysis_result,
        "current_phase": "analyst_done",
    }
