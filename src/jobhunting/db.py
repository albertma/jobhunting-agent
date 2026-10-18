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
    # ── 增量迁移（幂等：列已存在则跳过）──
    for ddl in (
        "ALTER TABLE jobs ADD COLUMN applied_at TEXT",
        "ALTER TABLE jobs ADD COLUMN replied_at TEXT",
        "ALTER TABLE jobs ADD COLUMN followup_sent INTEGER DEFAULT 0",
    ):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass
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


def get_job(job_id: str) -> Job | None:
    """按 id 取单个职位（draft 命令用）"""
    conn = _ensure_db()
    try:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _row_to_job(conn, row) if row else None
    finally:
        conn.close()


def prune_jobs(days: int = 90) -> int:
    """删除超过保留期的职位（已投递的永久保留），返回删除数"""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = _ensure_db()
    try:
        cur = conn.execute(
            "DELETE FROM jobs WHERE created_at < ? AND applied = 0", (cutoff,)
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def prune_run_log(keep: int = 500) -> int:
    """只保留最近 keep 条运行日志，返回删除数"""
    conn = _ensure_db()
    try:
        cur = conn.execute(
            """DELETE FROM run_log WHERE id <= (
                   SELECT id FROM run_log ORDER BY id DESC LIMIT 1 OFFSET ?
               )""",
            (keep,),
        )
        conn.commit()
        return cur.rowcount
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
    now = datetime.now().isoformat()
    conn = _ensure_db()
    try:
        conn.execute(
            "UPDATE jobs SET applied = 1, applied_at = ? WHERE id = ?",
            (now, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_replied(job_id: str) -> None:
    """标记已收到回复（不再提醒跟进）"""
    conn = _ensure_db()
    try:
        conn.execute(
            "UPDATE jobs SET replied_at = ? WHERE id = ?",
            (datetime.now().isoformat(), job_id),
        )
        conn.commit()
    finally:
        conn.close()


def due_followups(days: int = 7) -> list[dict]:
    """已投递但超过 N 天无回复、且尚未提醒过的职位"""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = _ensure_db()
    try:
        rows = conn.execute(
            """SELECT id, title, company, url, applied_at
               FROM jobs
               WHERE applied = 1
                 AND replied_at IS NULL
                 AND followup_sent = 0
                 AND applied_at IS NOT NULL
                 AND applied_at <= ?
               ORDER BY applied_at ASC""",
            (cutoff,),
        ).fetchall()
        return [
            {"id": r[0], "title": r[1], "company": r[2], "url": r[3], "applied_at": r[4]}
            for r in rows
        ]
    finally:
        conn.close()


def mark_followup_sent(ids: list[str]) -> None:
    """标记已提醒（避免重复推送）"""
    if not ids:
        return
    conn = _ensure_db()
    try:
        conn.executemany(
            "UPDATE jobs SET followup_sent = 1 WHERE id = ?", [(i,) for i in ids]
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_job(conn: sqlite3.Connection, r: tuple) -> Job:
    """把一行结果转为 Job"""
    import json
    # PRAGMA table_info: (cid, name, type, ...) — 列名在第 1 列
    cols = [d[1] for d in conn.execute("PRAGMA table_info(jobs)").fetchall()]

    def col(name: str, default=""):
        return r[cols.index(name)] if name in cols else default

    return Job(
        id=col("id"),
        source=col("source"),
        title=col("title"),
        company=col("company"),
        url=col("url"),
        description=col("description") or "",
        tags=json.loads(col("tags") or "[]"),
        location=col("location") or "",
        salary=col("salary") or "",
        job_type=col("job_type") or "",
        posted_at=col("posted_at") or "",
        score=col("score", 0) or 0,
        applied=bool(col("applied", 0)),
    )


def all_jobs() -> list[Job]:
    """全量职位（用于重算评分）"""
    conn = _ensure_db()
    try:
        rows = conn.execute("SELECT * FROM jobs").fetchall()
        return [_row_to_job(conn, r) for r in rows]
    finally:
        conn.close()


def top_jobs(days: int = 7, limit: int = 15) -> list[Job]:
    """最近 N 天内未投递的最高分职位（用于手动推送）"""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    conn = _ensure_db()
    try:
        rows = conn.execute(
            """SELECT * FROM jobs
               WHERE created_at >= ? AND applied = 0
               ORDER BY score DESC LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
        return [_row_to_job(conn, r) for r in rows]
    finally:
        conn.close()


def update_scores(jobs: list[Job]) -> int:
    """批量回写评分，返回更新数"""
    conn = _ensure_db()
    try:
        conn.executemany(
            "UPDATE jobs SET score = ? WHERE id = ?",
            [(j.score, j.id) for j in jobs],
        )
        conn.commit()
        return len(jobs)
    finally:
        conn.close()


def recent_jobs(limit: int = 20) -> list[Job]:
    """最近入库的职位（用于 report）"""
    conn = _ensure_db()
    try:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_job(conn, r) for r in rows]
    finally:
        conn.close()
