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
