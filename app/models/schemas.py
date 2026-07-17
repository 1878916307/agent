"""请求/响应数据模型"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchRequest(BaseModel):
    """调研任务请求"""
    topic: str = Field(..., description="调研主题，例如：国内大模型竞品分析")
    competitors: Optional[list[str]] = Field(
        default=None,
        description="指定竞品列表，例如：['文心一言', '通义千问', '豆包', 'Kimi']"
    )
    focus_dimensions: Optional[list[str]] = Field(
        default=None,
        description="关注维度，例如：['产品功能', '定价策略', '技术路线', '市场份额']"
    )


class StageResult(BaseModel):
    """单个阶段的中间结果"""
    stage: str = Field(..., description="阶段名称")
    status: str = Field(..., description="阶段状态")
    summary: str = Field(default="", description="阶段摘要")


class ResearchResponse(BaseModel):
    """调研任务响应"""
    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    topic: str = Field(default="", description="调研主题")
    final_report: Optional[str] = Field(default=None, description="最终调研报告 (Markdown)")
    stages: list[StageResult] = Field(default_factory=list, description="各阶段中间结果")
    error: Optional[str] = Field(default=None, description="错误信息")
    created_at: str = Field(default="", description="创建时间")
    updated_at: str = Field(default="", description="更新时间")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    service: str = "multi-agent-research"
