"""LangGraph 全局 State 定义

核心知识点:
- State 使用 TypedDict 定义，所有 Agent 共享同一个 State
- Annotated + reducer_fn 实现消息追加而非覆盖（这是 LangGraph 的关键机制）
- 每个 Agent 节点读取 State、处理后写回 State
"""

from typing import Annotated, Optional
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """多智能体竞品调研系统的全局状态

    字段说明:
    - messages: 全局消息列表，使用 add_messages reducer 实现追加机制
    - topic: 调研主题
    - competitors: 竞品列表
    - focus_dimensions: 关注维度
    - task_plan: 总指挥的任务规划
    - research_data: 信息采集 Agent 采集的原始数据
    - analysis_result: 数据分析 Agent 的分析结论
    - report_draft: 报告撰写 Agent 生成的报告草稿
    - review_feedback: 合规审核 Agent 的审核意见
    - final_report: 最终通过的调研报告
    - current_phase: 当前执行阶段
    - iteration_count: 当前迭代次数（防止无限循环）
    - review_passed: 审核是否通过
    """

    # 消息列表 - 使用 Reducer 追加，而非覆盖
    messages: Annotated[list[BaseMessage], add_messages]

    # 调研输入
    topic: str
    competitors: list[str]
    focus_dimensions: list[str]

    # 总指挥规划
    task_plan: str

    # 各 Agent 产出
    research_data: str
    analysis_result: str
    report_draft: str
    review_feedback: str
    final_report: str

    # 流程控制
    current_phase: str  # supervisor / researcher / analyst / writer / reviewer / done
    iteration_count: int
    review_passed: bool
