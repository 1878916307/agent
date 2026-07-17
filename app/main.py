"""FastAPI 入口 + 路由

核心知识点 - 工程化封装:
- FastAPI 提供标准 HTTP 接口，解耦前端和后端
- SSE (Server-Sent Events) 实现实时流式推送 Agent 执行进展
- SQLite 持久化：任务状态、报告数据持久存储，服务重启不丢失
- PDF 报告导出：Markdown → HTML → PDF
- LangSmith 可观测性：追踪每个 Agent 的调用链、耗时、token 消耗

面试要点:
- SSE vs WebSocket: SSE 是单向推送，适合服务端→客户端的实时通知；WebSocket 是双向通信
- 为什么用 SSE？调研任务是长时间运行的，SSE 让前端实时看到每个 Agent 的进度
- SQLite 的优势：零配置、无需独立部署进程，适合单机应用
"""

import uuid
import json
import logging
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response

from app.models.schemas import (
    ResearchRequest,
    ResearchResponse,
    HealthResponse,
    TaskStatus,
    StageResult,
)
from app.graph.workflow import get_graph
from app.config import settings
from app.db.database import init_db, create_task, get_task, update_task, list_tasks

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("=" * 60)
    logger.info("多智能体竞品调研系统启动")
    logger.info(f"LLM: {settings.LLM_MODEL_NAME} @ {settings.LLM_BASE_URL}")
    logger.info(f"LangSmith: {'已启用' if settings.LANGSMITH_ENABLED else '未启用'}")
    logger.info(f"数据库: SQLite ({settings.DB_PATH})")
    logger.info("=" * 60)

    # 初始化数据库
    init_db()

    yield
    logger.info("系统关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="多智能体竞品调研系统",
    description="基于 LangGraph Supervisor 模式的多 Agent 协作系统，自动化竞品调研与报告生成",
    version="2.0.0",
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


def _run_research_task_sync(task_id: str, request: ResearchRequest):
    """执行调研任务（同步版本，在后台线程中运行）

    核心流程:
    1. 初始化 State
    2. 调用 LangGraph 图执行
    3. 收集各阶段结果
    4. 更新任务状态（持久化到 SQLite）
    """
    try:
        update_task(task_id, status=TaskStatus.RUNNING)

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
            ).model_dump())
        if final_state.get("analysis_result"):
            stages.append(StageResult(
                stage="数据分析",
                status="completed",
                summary=final_state["analysis_result"][:500] + "..." if len(final_state["analysis_result"]) > 500 else final_state["analysis_result"],
            ).model_dump())
        if final_state.get("report_draft"):
            stages.append(StageResult(
                stage="报告撰写",
                status="completed",
                summary=final_state["report_draft"][:500] + "..." if len(final_state["report_draft"]) > 500 else final_state["report_draft"],
            ).model_dump())
        if final_state.get("review_feedback"):
            stages.append(StageResult(
                stage="合规审核",
                status="passed" if final_state.get("review_passed") else "failed",
                summary=final_state["review_feedback"][:500] + "..." if len(final_state["review_feedback"]) > 500 else final_state["review_feedback"],
            ).model_dump())

        # 更新任务结果（持久化到 SQLite）
        final_report = final_state.get("final_report") or final_state.get("report_draft", "")
        update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            final_report=final_report,
            stages=stages,
        )

        logger.info(f"[Task {task_id}] 调研完成")

    except Exception as e:
        logger.error(f"[Task {task_id}] 执行失败: {str(e)}", exc_info=True)
        update_task(task_id, status=TaskStatus.FAILED, error=str(e))


async def _run_research_task_stream(task_id: str, request: ResearchRequest):
    """执行调研任务（流式版本，通过 LangGraph stream 实时推送进展）

    核心知识点:
    - LangGraph 的 stream() 方法：每执行完一个节点就 yield 一次状态更新
    - 结合 SSE 实时推送给前端，用户可以看到每个 Agent 的执行进度
    - 这是面试中"实时交互"的加分项
    """
    try:
        update_task(task_id, status=TaskStatus.RUNNING)

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

        logger.info(f"[Task {task_id}] 开始流式执行调研: {request.topic}")

        graph = get_graph()
        stages = []
        final_report = ""

        # 核心：使用 stream() 而非 invoke()，每完成一个节点就推送事件
        for event in graph.stream(initial_state):
            # event 格式: {node_name: state_update}
            for node_name, state_update in event.items():
                phase = state_update.get("current_phase", "")
                logger.info(f"[SSE] 节点完成: {node_name}, 阶段: {phase}")

                # 推送节点完成事件
                yield {
                    "event": "agent_complete",
                    "data": {
                        "agent": node_name,
                        "phase": phase,
                        "message": f"{node_name} 执行完成",
                    }
                }

                # 收集各阶段结果
                if state_update.get("research_data"):
                    stages.append(StageResult(
                        stage="信息采集",
                        status="completed",
                        summary=state_update["research_data"][:500] + "...",
                    ).model_dump())
                    yield {
                        "event": "stage_complete",
                        "data": {"stage": "信息采集", "data_size": len(state_update["research_data"])}
                    }

                if state_update.get("analysis_result"):
                    stages.append(StageResult(
                        stage="数据分析",
                        status="completed",
                        summary=state_update["analysis_result"][:500] + "...",
                    ).model_dump())
                    yield {
                        "event": "stage_complete",
                        "data": {"stage": "数据分析", "data_size": len(state_update["analysis_result"])}
                    }

                if state_update.get("report_draft"):
                    final_report = state_update["report_draft"]
                    stages.append(StageResult(
                        stage="报告撰写",
                        status="completed",
                        summary=state_update["report_draft"][:500] + "...",
                    ).model_dump())
                    yield {
                        "event": "stage_complete",
                        "data": {"stage": "报告撰写", "data_size": len(state_update["report_draft"])}
                    }

                if state_update.get("review_feedback"):
                    review_passed = state_update.get("review_passed", False)
                    stages.append(StageResult(
                        stage="合规审核",
                        status="passed" if review_passed else "failed",
                        summary=state_update["review_feedback"][:500] + "...",
                    ).model_dump())
                    yield {
                        "event": "stage_complete",
                        "data": {"stage": "合规审核", "passed": review_passed}
                    }

                if state_update.get("final_report"):
                    final_report = state_update["final_report"]

        # 任务完成
        if not final_report:
            final_report = ""

        update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            final_report=final_report,
            stages=stages,
        )

        # 推送完成事件
        yield {
            "event": "task_complete",
            "data": {
                "task_id": task_id,
                "report_length": len(final_report),
                "message": "调研任务完成",
            }
        }

        logger.info(f"[Task {task_id}] 流式调研完成")

    except Exception as e:
        logger.error(f"[Task {task_id}] 流式执行失败: {str(e)}", exc_info=True)
        update_task(task_id, status=TaskStatus.FAILED, error=str(e))
        yield {
            "event": "error",
            "data": {"error": str(e), "message": "任务执行失败"}
        }


def _sse_format(event: str, data: dict) -> str:
    """格式化 SSE 消息

    SSE 协议:
    - event: 事件名称
    - data: JSON 格式的数据
    - 每条消息以两个换行结束
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ============================================================
# API 接口
# ============================================================

@app.post("/api/v1/research", response_model=ResearchResponse)
async def create_research_task(request: ResearchRequest):
    """提交调研任务（异步执行，后台运行）

    客户端通过 GET /api/v1/research/{task_id} 轮询结果。
    或使用 GET /api/v1/research/{task_id}/stream 获取实时流式推送。
    """
    task_id = str(uuid.uuid4())[:8]

    # 持久化到 SQLite
    task = create_task(
        task_id=task_id,
        topic=request.topic,
        competitors=request.competitors,
        focus_dimensions=request.focus_dimensions,
    )

    # 在后台线程中执行
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _run_research_task_sync, task_id, request)

    logger.info(f"[Task {task_id}] 任务已创建: {request.topic}")

    return ResearchResponse(**task)


@app.post("/api/v1/research/{task_id}/stream")
async def stream_research_task(task_id: str, request: ResearchRequest):
    """流式执行调研任务（SSE 实时推送）

    核心知识点:
    - SSE (Server-Sent Events) 实现服务端→客户端的单向实时推送
    - 使用 LangGraph 的 stream() 方法，每完成一个 Agent 就推送事件
    - Content-Type: text/event-stream

    面试要点:
    - SSE vs WebSocket: SSE 更轻量，适合单向推送场景
    - 前端用 EventSource API 接收事件
    """
    # 先检查任务是否已存在
    existing = get_task(task_id)
    if existing and existing["status"] == TaskStatus.COMPLETED:
        # 已完成的任务直接返回结果
        return ResearchResponse(**existing)

    # 创建新任务
    create_task(
        task_id=task_id,
        topic=request.topic,
        competitors=request.competitors,
        focus_dimensions=request.focus_dimensions,
    )

    async def event_generator():
        async for sse_event in _run_research_task_stream(task_id, request):
            yield _sse_format(sse_event["event"], sse_event["data"])

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


@app.get("/api/v1/research/{task_id}", response_model=ResearchResponse)
async def get_research_task(task_id: str):
    """查询任务状态与结果"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    return ResearchResponse(**task)


@app.get("/api/v1/tasks")
async def list_all_tasks(limit: int = 20):
    """查询历史任务列表

    面试要点: 有了 SQLite 持久化，服务重启后历史任务仍可查询
    """
    tasks = list_tasks(limit=limit)
    return {"tasks": tasks, "total": len(tasks)}


@app.get("/api/v1/research/{task_id}/export")
async def export_report_pdf(task_id: str):
    """导出调研报告为 PDF

    核心知识点:
    - Markdown → HTML → PDF 的转换链
    - 使用 markdown 库转换格式
    - 使用 weasyprint 生成 PDF（支持中文）

    面试要点:
    - 为什么做 PDF 导出？产品化交付，让报告可直接使用
    """
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    report = task.get("final_report") or task.get("report_draft")
    if not report:
        raise HTTPException(status_code=400, detail="报告尚未生成")

    try:
        import markdown
        from weasyprint import HTML

        # Markdown → HTML
        html_content = markdown.markdown(
            report,
            extensions=["tables", "fenced_code", "toc"],
        )

        # 包装完整 HTML（含中文支持样式）
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: "Microsoft YaHei", "SimHei", sans-serif; padding: 40px; line-height: 1.8; }}
                h1 {{ color: #1a1a1a; border-bottom: 2px solid #333; padding-bottom: 10px; }}
                h2 {{ color: #333; margin-top: 30px; }}
                h3 {{ color: #555; }}
                table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
                th {{ background-color: #f5f5f5; font-weight: bold; }}
                code {{ background-color: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
                blockquote {{ border-left: 4px solid #ddd; margin: 0; padding-left: 16px; color: #666; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        # HTML → PDF
        pdf_bytes = HTML(string=full_html).write_pdf()

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="report_{task_id}.pdf"'
            },
        )

    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"PDF 导出依赖缺失，请安装: pip install markdown weasyprint. 错误: {str(e)}"
        )
    except Exception as e:
        logger.error(f"PDF 导出失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF 生成失败: {str(e)}")


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse()
