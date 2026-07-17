"""LLM 实例化工具

核心知识点:
- ChatOpenAI 是 LangChain 对 OpenAI 兼容 API 的统一封装
- 通过 openai_api_base 参数可以无缝切换不同 LLM 供应商
- LangSmith 回调自动注入，无需手动配置

面试要点:
- 为什么用 ChatOpenAI 而不是直接调 API？统一接口，换模型只改配置不改代码
- LangSmith 的 callback 是自动注入的，只要设了环境变量就会生效
"""

import os
from langchain_openai import ChatOpenAI
from app.config import settings


def get_llm(temperature: float = 0.3) -> ChatOpenAI:
    """获取 LLM 实例

    使用 DeepSeek 通过 OpenAI 兼容格式调用。
    temperature 控制输出随机性：
    - 低值(0.1-0.3): 更确定性，适合分析、审核类任务
    - 中值(0.5-0.7): 平衡，适合报告撰写
    - 高值(0.8+): 更创造性，适合头脑风暴

    LangSmith 集成:
    - 当 LANGSMITH_API_KEY 环境变量存在时，LangChain 会自动将每次调用
      记录到 LangSmith 平台，包括：prompt、completion、耗时、token 数
    - 无需修改任何代码，只需设置环境变量即可启用
    """
    # LangSmith 环境变量会自动被 LangChain 检测并启用
    # 参考: https://docs.smith.langchain.com/observability
    if settings.LANGSMITH_ENABLED:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = "multi-agent-research"

    return ChatOpenAI(
        model=settings.LLM_MODEL_NAME,
        openai_api_key=settings.LLM_API_KEY,
        openai_api_base=settings.LLM_BASE_URL,
        temperature=temperature,
    )
"""LLM 实例化工具"""

from langchain_openai import ChatOpenAI
from app.config import settings


def get_llm(temperature: float = 0.3) -> ChatOpenAI:
    """获取 LLM 实例

    使用 DeepSeek 通过 OpenAI 兼容格式调用。
    temperature 控制输出随机性：
    - 低值(0.1-0.3): 更确定性，适合分析、审核类任务
    - 中值(0.5-0.7): 平衡，适合报告撰写
    - 高值(0.8+): 更创造性，适合头脑风暴
    """
    return ChatOpenAI(
        model=settings.LLM_MODEL_NAME,
        openai_api_key=settings.LLM_API_KEY,
        openai_api_base=settings.LLM_BASE_URL,
        temperature=temperature,
    )
