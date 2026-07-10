from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


DB_PATH = Path(__file__).with_name("moon_studio.db")


@contextmanager
def connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    schema = """
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        goal TEXT DEFAULT '', stage TEXT DEFAULT '', priority TEXT NOT NULL DEFAULT 'P2',
        deadline TEXT, next_action TEXT DEFAULT '', created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
        type TEXT DEFAULT '', priority TEXT NOT NULL DEFAULT 'P2',
        status TEXT NOT NULL DEFAULT '未开始', deadline TEXT,
        estimated_hours REAL NOT NULL DEFAULT 0, actual_hours REAL NOT NULL DEFAULT 0,
        progress INTEGER NOT NULL DEFAULT 0, notes TEXT DEFAULT '',
        completed_at TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS time_blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        block_date TEXT NOT NULL, period TEXT NOT NULL,
        plan TEXT NOT NULL, actual_result TEXT DEFAULT '', actual_hours REAL NOT NULL DEFAULT 0,
        project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
        is_protected INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS contents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brand TEXT NOT NULL, title TEXT NOT NULL, content_type TEXT NOT NULL,
        platform TEXT NOT NULL, status TEXT NOT NULL DEFAULT '想法', publish_at TEXT,
        production_hours REAL NOT NULL DEFAULT 0, copywriting TEXT DEFAULT '', notes TEXT DEFAULT '',
        views INTEGER NOT NULL DEFAULT 0, likes INTEGER NOT NULL DEFAULT 0,
        saves INTEGER NOT NULL DEFAULT 0, comments INTEGER NOT NULL DEFAULT 0,
        followers_gained INTEGER NOT NULL DEFAULT 0, review_summary TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ideas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, description TEXT DEFAULT '', type TEXT DEFAULT '',
        created_at TEXT NOT NULL, value_judgment TEXT DEFAULT '',
        will_execute INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT '待评估'
    );
    CREATE TABLE IF NOT EXISTS weekly_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_start TEXT NOT NULL UNIQUE, completed TEXT DEFAULT '', unfinished TEXT DEFAULT '',
        reasons TEXT DEFAULT '', over_time TEXT DEFAULT '', good_content TEXT DEFAULT '',
        continue_tests TEXT DEFAULT '', next_three TEXT DEFAULT '', stop_doing TEXT DEFAULT '',
        updated_at TEXT NOT NULL
    );
    """
    defaults = [
        ("作品集冲刺", "完成作品集并准备求职", "冲刺阶段", "P0", "2026-07-22", "完成今天的作品集深度工作"),
        ("Bree原创IP", "长期打造原创角色 IP，测试高关注内容", "冷启动", "P1", None, "选择一个内容假设进行测试"),
        ("Moon设计师账号", "建立个人设计师品牌", "定位探索", "P2", None, "记录一个真实的创作过程"),
        ("求职", "管理目标公司、岗位、投递和面试", "备用模块", "P2", None, "7月22日后提高优先级"),
    ]
    now = datetime.now().isoformat(timespec="seconds")
    with connection() as conn:
        conn.executescript(schema)
        conn.executemany(
            "INSERT OR IGNORE INTO projects (name, goal, stage, priority, deadline, next_action, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(*row, now) for row in defaults],
        )


def query(sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    with connection() as conn:
        return [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    with connection() as conn:
        cursor = conn.execute(sql, tuple(params))
        return int(cursor.lastrowid or 0)


def ensure_default_time_blocks(day: date) -> None:
    day_text = day.isoformat()
    if query("SELECT id FROM time_blocks WHERE block_date = ? LIMIT 1", (day_text,)):
        return
    portfolio = query("SELECT id FROM projects WHERE name = '作品集冲刺'")
    portfolio_id = portfolio[0]["id"] if portfolio else None
    rows = [
        (day_text, "上午", "创作 / 灵感 / 账号内容", "", 0, None, 0),
        (day_text, "13:30-18:00", "作品集深度工作", "", 0, portfolio_id, 1),
        (day_text, "晚上", "发布内容 / 复盘 / 学习", "", 0, None, 0),
    ]
    with connection() as conn:
        conn.executemany(
            "INSERT INTO time_blocks (block_date, period, plan, actual_result, actual_hours, project_id, is_protected) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

