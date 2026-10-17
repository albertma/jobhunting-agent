"""SQLite 持久化：去重 + 历史记录"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from .models import Job


def _db_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / "data" / "jobs.db"


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id          TEXT PRIMARY KEY,
            source      TEXT NOT NULL,
            title       TEXT NOT NULL,
            company     TEXT NOT NULL,
            url         TEXT NOT NULL,
            description TEXT,
            tags        TEXT,        -- JSON 列表
            location    TEXT,
            salary      TEXT,
            job_type    TEXT,
            posted_at   TEXT,
            score       REAL DEFAULT 0,
            applied     INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT NOT NULL,
            ran_at      TEXT NOT NULL,
            found       INTEGER,
            new         INTEGER,
            skipped     INTEGER,
            error       TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_created
        ON jobs(created_at DESC)
    """)
    conn.commit()


def _ensure_db() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    _init_db(conn)
    return conn


def seen_jobs(days: int = 7) -> set[str]:
    """返回最近 N 天内已见过的 job id（用于去重）"""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = _ensure_db()
    try:
        rows = conn.execute(
            "SELECT id FROM jobs WHERE created_at >= ?", (cutoff,)
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


def save_jobs(jobs: list[Job]) -> tuple[int, int]:
    """保存新职位，返回 (入库数, 跳过数)"""
    conn = _ensure_db()
    try:
        saved = 0
        skipped = 0
        now = datetime.now().isoformat()
        for job in jobs:
            exists = conn.execute(
                "SELECT 1 FROM jobs WHERE id = ?", (job.id,)
            ).fetchone()
            if exists:
                skipped += 1
                continue
            import json
            conn.execute(
                """INSERT INTO jobs
                   (id,source,title,company,url,description,tags,location,
                    salary,job_type,posted_at,score,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    job.id, job.source, job.title, job.company, job.url,
                    job.description, json.dumps(job.tags),
                    job.location, job.salary, job.job_type, job.posted_at,
                    job.score, now,
                ),
            )
            saved += 1
        conn.commit()
        return saved, skipped
    finally:
        conn.close()


def log_run(
    source: str,
    found: int,
    new: int,
    skipped: int,
    error: str | None = None,
) -> None:
    """记录一次抓取运行"""
    conn = _ensure_db()
    try:
        conn.execute(
            """INSERT INTO run_log (source, ran_at, found, new, skipped, error)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source, datetime.now().isoformat(), found, new, skipped, error),
        )
        conn.commit()
    finally:
        conn.close()


def get_applied() -> set[str]:
    """返回已投递的 job id"""
    conn = _ensure_db()
    try:
        rows = conn.execute(
            "SELECT id FROM jobs WHERE applied = 1"
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


def mark_applied(job_id: str) -> None:
    conn = _ensure_db()
    try:
        conn.execute("UPDATE jobs SET applied = 1 WHERE id = ?", (job_id,))
        conn.commit()
    finally:
        conn.close()


def recent_jobs(limit: int = 20) -> list[Job]:
    """最近入库的职位（用于 report）"""
    conn = _ensure_db()
    try:
        import json
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        cols = [d[0] for d in conn.execute("PRAGMA table_info(jobs)").fetchall()]
        return [
            Job(
                id=r[cols.index("id")],
                source=r[cols.index("source")],
                title=r[cols.index("title")],
                company=r[cols.index("company")],
                url=r[cols.index("url")],
                description=r[cols.index("description") or 0] or "",
                tags=json.loads(r[cols.index("tags") or 0] or "[]"),
                location=r[cols.index("location") or 0] or "",
                salary=r[cols.index("salary") or 0] or "",
                job_type=r[cols.index("job_type") or 0] or "",
                posted_at=r[cols.index("posted_at") or 0] or "",
                score=r[cols.index("score")],
                applied=bool(r[cols.index("applied")]),
            )
            for r in rows
        ]
    finally:
        conn.close()
