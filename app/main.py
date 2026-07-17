"""FastAPI 入口 + 路由

核心知识点 - 工程化封装:
- FastAPI 提供标准 HTTP 接口，解耦前端和后端
- 异步任务处理：调研任务耗时长，采用异步执行 + 轮询查询
- 任务状态管理：内存 dict 存储（生产环境可替换为 Redis）
- 统一异常处理 + 日志记录
"""

import uuid
import logging
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models.schemas import (
    ResearchRequest,
    ResearchResponse,
    HealthResponse,
    TaskStatus,
    StageResult,
)
from app.graph.workflow import get_graph
from app.config import settings

# 日志配置
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# 任务存储（内存版，生产环境替换为 Redis）
tasks_store: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("=" * 60)
    logger.info("多智能体竞品调研系统启动")
    logger.info(f"LLM: {settings.LLM_MODEL_NAME} @ {settings.LLM_BASE_URL}")
    logger.info("=" * 60)
    yield
    logger.info("系统关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="多智能体竞品调研系统",
    description="基于 LangGraph Supervisor 模式的多 Agent 协作系统，自动化竞品调研与报告生成",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 中间件（允许前端跨域调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _run_research_task(task_id: str, request: ResearchRequest):
    """执行调研任务（在后台线程中运行）

    核心流程:
    1. 初始化 State
    2. 调用 LangGraph 图执行
    3. 收集各阶段结果
    4. 更新任务状态
    """
    try:
        tasks_store[task_id]["status"] = TaskStatus.RUNNING
        tasks_store[task_id]["updated_at"] = datetime.now().isoformat()

        # 初始化 State
        initial_state = {
            "messages": [],
            "topic": request.topic,
            "competitors": request.competitors or [],
            "focus_dimensions": request.focus_dimensions or [],
            "task_plan": "",
            "research_data": "",
            "analysis_result": "",
            "report_draft": "",
            "review_feedback": "",
            "final_report": "",
            "current_phase": "",
            "iteration_count": 0,
            "review_passed": False,
        }

        logger.info(f"[Task {task_id}] 开始执行调研: {request.topic}")

        # 获取编译后的图并执行
        graph = get_graph()
        final_state = graph.invoke(initial_state)

        # 提取各阶段结果
        stages = []
        if final_state.get("research_data"):
            stages.append(StageResult(
                stage="信息采集",
                status="completed",
                summary=final_state["research_data"][:500] + "..." if len(final_state["research_data"]) > 500 else final_state["research_data"],
            ))
        if final_state.get("analysis_result"):
            stages.append(StageResult(
                stage="数据分析",
                status="completed",
                summary=final_state["analysis_result"][:500] + "..." if len(final_state["analysis_result"]) > 500 else final_state["analysis_result"],
            ))
        if final_state.get("report_draft"):
            stages.append(StageResult(
                stage="报告撰写",
                status="completed",
                summary=final_state["report_draft"][:500] + "..." if len(final_state["report_draft"]) > 500 else final_state["report_draft"],
            ))
        if final_state.get("review_feedback"):
            stages.append(StageResult(
                stage="合规审核",
                status="passed" if final_state.get("review_passed") else "failed",
                summary=final_state["review_feedback"][:500] + "..." if len(final_state["review_feedback"]) > 500 else final_state["review_feedback"],
            ))

        # 更新任务结果
        tasks_store[task_id].update({
            "status": TaskStatus.COMPLETED,
            "final_report": final_state.get("final_report") or final_state.get("report_draft", ""),
            "stages": stages,
            "updated_at": datetime.now().isoformat(),
        })

        logger.info(f"[Task {task_id}] 调研完成")

    except Exception as e:
        logger.error(f"[Task {task_id}] 执行失败: {str(e)}", exc_info=True)
        tasks_store[task_id].update({
            "status": TaskStatus.FAILED,
            "error": str(e),
            "updated_at": datetime.now().isoformat(),
        })


@app.post("/api/v1/research", response_model=ResearchResponse)
async def create_research_task(request: ResearchRequest):
    """提交调研任务

    异步执行：立即返回 task_id，后台执行调研任务。
    客户端通过 GET /api/v1/research/{task_id} 轮询结果。
    """
    task_id = str(uuid.uuid4())[:8]

    tasks_store[task_id] = {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        "topic": request.topic,
        "final_report": None,
        "stages": [],
        "error": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    # 在后台线程中执行（避免阻塞异步事件循环）
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _run_research_task, task_id, request)

    logger.info(f"[Task {task_id}] 任务已创建: {request.topic}")

    return ResearchResponse(**tasks_store[task_id])


@app.get("/api/v1/research/{task_id}", response_model=ResearchResponse)
async def get_research_task(task_id: str):
    """查询任务状态与结果"""
    if task_id not in tasks_store:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    return ResearchResponse(**tasks_store[task_id])


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse()
