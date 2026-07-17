"""统一配置管理"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """应用配置"""

    # LLM 配置 (DeepSeek via OpenAI-compatible API)
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "deepseek-chat")

    # Tavily 搜索配置
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

    # 服务配置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Agent 配置
    MAX_RESEARCH_ITERATIONS: int = 3  # 最大采集轮次
    MAX_REVIEW_RETRIES: int = 2  # 最大审核打回次数


settings = Settings()
