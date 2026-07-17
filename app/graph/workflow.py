"""LangGraph 状态图构建与编译

核心知识点 - LangGraph 状态图:
- StateGraph: 有状态的图，每个节点共享同一个 State
- add_node: 注册节点（每个 Agent 对应一个节点）
- add_edge / add_conditional_edges: 定义节点间的连接
- 条件边(conditional_edges): 根据 State 动态决定下一个节点（Supervisor 的核心）
- compile: 将图编译为可执行对象

面试要点:
- 为什么用图不用链？链是线性的，图支持分支、循环、中断恢复
- 条件边如何实现？通过一个路由函数读取 State，返回下一个节点名称
- START 和 END 是 LangGraph 的内置虚拟节点
"""

import logging
from langgraph.graph import StateGraph, START, END

from app.agents.state import AgentState
from app.agents.supervisor import supervisor_node
from app.agents.researcher import researcher_node
from app.agents.analyst import analyst_node
from app.agents.writer import writer_node
from app.agents.reviewer import reviewer_node
from app.config import settings

logger = logging.getLogger(__name__)


def route_after_supervisor(state: AgentState) -> str:
    """Supervisor 路由函数 - 根据当前阶段决定下一个节点

    这是条件边的核心实现：
    - 读取 state["current_phase"] 判断当前阶段
    - 返回下一个节点的名称（字符串）
    - LangGraph 会自动路由到对应节点

    面试要点:
    - 路由函数只能访问 state，不能访问外部变量
    - 返回值必须是已注册的节点名称之一
    - 要处理所有可能的状态，避免路由到不存在的节点
    """
    phase = state.get("current_phase", "")
    iteration = state.get("iteration_count", 0)

    logger.info(f"[Router] 当前阶段: {phase}, 迭代次数: {iteration}")

    # 完成状态 -> 结束
    if phase == "done":
        return "end"

    # 超过最大迭代次数 -> 强制结束
    if iteration > settings.MAX_RESEARCH_ITERATIONS + settings.MAX_REVIEW_RETRIES:
        logger.warning("[Router] 超过最大迭代次数，强制结束")
        return "end"

    # 根据阶段路由
    if phase == "researcher":
        return "researcher"
    elif phase == "analyst":
        return "analyst"
    elif phase == "writer":
        return "writer"
    elif phase == "reviewer":
        return "reviewer"

    # 默认流程：按阶段顺序执行
    if not state.get("research_data"):
        return "researcher"
    elif not state.get("analysis_result"):
        return "analyst"
    elif not state.get("report_draft"):
        return "writer"
    elif not state.get("review_feedback"):
        return "reviewer"
    elif state.get("review_passed"):
        return "end"
    else:
        # 审核未通过，打回 writer
        if iteration < settings.MAX_REVIEW_RETRIES:
            return "writer"
        return "end"


def build_graph() -> StateGraph:
    """构建 LangGraph 状态图

    图的拓扑结构:
    START -> supervisor -> [条件路由] -> researcher / analyst / writer / reviewer / END
    researcher -> supervisor (数据回流)
    analyst -> supervisor (分析回流)
    writer -> supervisor (报告回流)
    reviewer -> supervisor (审核回流) 或 writer (打回修改)
    """

    # 创建状态图，传入 State 类型
    graph = StateGraph(AgentState)

    # 注册节点（每个 Agent 对应一个节点）
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("writer", writer_node)
    graph.add_node("reviewer", reviewer_node)

    # 定义边
    # START -> supervisor（入口）
    graph.add_edge(START, "supervisor")

    # supervisor -> 条件路由（动态决定下一个节点）
    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "researcher": "researcher",
            "analyst": "analyst",
            "writer": "writer",
            "reviewer": "reviewer",
            "end": END,
        },
    )

    # 各专项 Agent 完成后回到 supervisor（结果回流）
    graph.add_edge("researcher", "supervisor")
    graph.add_edge("analyst", "supervisor")
    graph.add_edge("writer", "supervisor")
    graph.add_edge("reviewer", "supervisor")

    # 编译图
    compiled = graph.compile()
    logger.info("[Graph] 状态图编译完成")

    return compiled


# 全局图实例（延迟初始化）
_graph_instance = None


def get_graph():
    """获取编译后的图实例（单例）"""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_graph()
    return _graph_instance
