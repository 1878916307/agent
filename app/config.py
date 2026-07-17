"""统一配置管理

核心知识点:
- 所有配置集中在一个文件中，通过 .env 环境变量注入
- LangSmith 配置：启用后可追踪每个 Agent 的调用链
- SQLite 配置：数据持久化路径

面试要点:
- 为什么用环境变量？不同环境（开发/测试/生产）可以用不同配置，无需改代码
- LangSmith 的作用：调试 LLM 应用的关键工具，可以看到每一步的输入输出、耗时、token 消耗
"""

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

    # LangSmith 可观测性配置
    # 启用后，每次 Agent 调用 LLM 都会被 LangSmith 记录
    # 可以在 https://smith.langchain.com 查看调用链、耗时、token 消耗
    LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")
    LANGSMITH_ENABLED: bool = bool(os.getenv("LANGSMITH_API_KEY", ""))

    # SQLite 数据库配置
    DB_PATH: str = os.getenv("DB_PATH", "data/research.db")


settings = Settings()
