"""SQLite 数据持久化

核心知识点:
- 用 SQLite 替代内存 dict，实现任务状态持久化
- 服务重启后任务数据不丢失
- 支持历史任务查询

面试要点:
- 为什么用 SQLite？轻量级，无需额外部署数据库，适合单机部署
- 生产环境可平滑迁移到 PostgreSQL/MySQL
- 使用参数化查询防止 SQL 注入
"""

import sqlite3
import json
import logging
from datetime import datetime
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = "data/research.db"


def _ensure_data_dir():
    """确保数据目录存在"""
    import os
    os.makedirs("data", exist_ok=True)


@contextmanager
def get_db():
    """获取数据库连接（上下文管理器，自动关闭）"""
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 让结果可以通过列名访问
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """初始化数据库表结构"""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                competitors TEXT,
                focus_dimensions TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                final_report TEXT,
                stages TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
    logger.info("[DB] 数据库初始化完成")


def create_task(task_id: str, topic: str, competitors: list = None, focus_dimensions: list = None) -> dict:
    """创建新任务"""
    now = datetime.now().isoformat()
    task = {
        "task_id": task_id,
        "topic": topic,
        "competitors": competitors or [],
        "focus_dimensions": focus_dimensions or [],
        "status": "pending",
        "final_report": None,
        "stages": [],
        "error": None,
        "created_at": now,
        "updated_at": now,
    }

    with get_db() as conn:
        conn.execute(
            """INSERT INTO tasks 
               (task_id, topic, competitors, focus_dimensions, status, final_report, stages, error, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task_id,
                topic,
                json.dumps(task["competitors"], ensure_ascii=False),
                json.dumps(task["focus_dimensions"], ensure_ascii=False),
                task["status"],
                task["final_report"],
                json.dumps(task["stages"], ensure_ascii=False),
                task["error"],
                now,
                now,
            ),
        )
        conn.commit()

    logger.info(f"[DB] 任务已创建: {task_id}")
    return task


def update_task(task_id: str, **kwargs):
    """更新任务字段"""
    if not kwargs:
        return

    # JSON 序列化特定字段
    json_fields = {"competitors", "focus_dimensions", "stages"}
    updates = {}
    for key, value in kwargs.items():
        if key in json_fields:
            updates[key] = json.dumps(value, ensure_ascii=False)
        else:
            updates[key] = value

    updates["updated_at"] = datetime.now().isoformat()

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [task_id]

    with get_db() as conn:
        conn.execute(f"UPDATE tasks SET {set_clause} WHERE task_id = ?", values)
        conn.commit()

    logger.debug(f"[DB] 任务已更新: {task_id}, 字段: {list(kwargs.keys())}")


def get_task(task_id: str) -> Optional[dict]:
    """查询单个任务"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()

    if not row:
        return None

    return _row_to_dict(row)


def list_tasks(limit: int = 20) -> list[dict]:
    """查询任务列表（按创建时间倒序）"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()

    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row) -> dict:
    """将数据库行转换为字典，反序列化 JSON 字段"""
    task = dict(row)
    json_fields = {"competitors", "focus_dimensions", "stages"}
    for field in json_fields:
        if task.get(field):
            try:
                task[field] = json.loads(task[field])
            except (json.JSONDecodeError, TypeError):
                task[field] = [] if field != "stages" else []
    return task
