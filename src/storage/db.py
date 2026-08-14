import sqlite3
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Optional


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY, name TEXT, type TEXT, url TEXT,
                enabled BOOLEAN DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY, date TEXT, source_id TEXT REFERENCES sources(id),
                title TEXT, url TEXT, summary TEXT, tags TEXT, category TEXT,
                content_raw TEXT, content_parsed TEXT,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tools (
                id TEXT PRIMARY KEY, name TEXT, vendor TEXT, category TEXT,
                cloud TEXT, open_source BOOLEAN, url TEXT, github TEXT,
                description TEXT, discovered_date TEXT, tags TEXT
            );

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT, started_at TIMESTAMP, items_collected INT, status TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_items_date ON items(date);
            CREATE INDEX IF NOT EXISTS idx_items_source ON items(source_id);
            CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);

            CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
                title, summary, content_parsed, tags, content='items', content_rowid='rowid'
            );

            CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
                INSERT INTO items_fts(rowid, title, summary, content_parsed, tags)
                VALUES (new.rowid, new.title, new.summary, new.content_parsed, new.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
                INSERT INTO items_fts(items_fts, rowid, title, summary, content_parsed, tags)
                VALUES ('delete', old.rowid, old.title, old.summary, old.content_parsed, old.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON items BEGIN
                INSERT INTO items_fts(items_fts, rowid, title, summary, content_parsed, tags)
                VALUES ('delete', old.rowid, old.title, old.summary, old.content_parsed, old.tags);
                INSERT INTO items_fts(rowid, title, summary, content_parsed, tags)
                VALUES (new.rowid, new.title, new.summary, new.content_parsed, new.tags);
            END;
        """)
        self.conn.commit()

    def upsert_source(self, source_id: str, name: str, stype: str, url: str):
        self.conn.execute(
            "INSERT INTO sources (id, name, type, url) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, url=excluded.url",
            (source_id, name, stype, url),
        )
        self.conn.commit()

    def insert_item(self, item: dict) -> bool:
        try:
            self.conn.execute(
                "INSERT INTO items (id, date, source_id, title, url, summary, tags, category, content_raw, content_parsed) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item["id"], item["date"], item["source_id"],
                    item["title"], item["url"], item.get("summary", ""),
                    item.get("tags", ""), item.get("category", ""),
                    item.get("content_raw", ""), item.get("content_parsed", ""),
                ),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def item_exists(self, item_id: str) -> bool:
        return self.conn.execute("SELECT 1 FROM items WHERE id=?", (item_id,)).fetchone() is not None

    def get_items_by_date(self, dt: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT i.*, COALESCE(s.name, i.source_id) as source_name FROM items i "
            "LEFT JOIN sources s ON i.source_id = s.id "
            "WHERE i.date = ? ORDER BY i.collected_at DESC", (dt,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_items(self, limit: int = 100, offset: int = 0) -> list[dict]:
        rows = self.conn.execute(
            "SELECT i.*, COALESCE(s.name, i.source_id) as source_name FROM items i "
            "LEFT JOIN sources s ON i.source_id = s.id "
            "ORDER BY i.date DESC, i.collected_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    def search_items(self, query: str, limit: int = 50) -> list[dict]:
        try:
            rows = self.conn.execute(
                "SELECT i.*, COALESCE(s.name, i.source_id) as source_name FROM items i "
                "LEFT JOIN sources s ON i.source_id = s.id "
                "JOIN items_fts fts ON i.rowid = fts.rowid "
                "WHERE items_fts MATCH ? ORDER BY rank LIMIT ?",
                (query, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []

    def upsert_tool(self, tool: dict):
        self.conn.execute(
            "INSERT INTO tools (id, name, vendor, category, cloud, open_source, url, github, description, discovered_date, tags) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "name=excluded.name, vendor=excluded.vendor, category=excluded.category, "
            "url=excluded.url, description=excluded.description, tags=excluded.tags",
            (
                tool["id"], tool["name"], tool.get("vendor", ""),
                tool.get("category", ""), tool.get("cloud", ""),
                tool.get("open_source", False), tool.get("url", ""),
                tool.get("github", ""), tool.get("description", ""),
                tool.get("discovered_date", date.today().isoformat()),
                tool.get("tags", ""),
            ),
        )
        self.conn.commit()

    def get_tools(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM tools ORDER BY discovered_date DESC").fetchall()
        return [dict(r) for r in rows]

    def get_tools_stats(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) FROM tools").fetchone()[0]
        by_category = self.conn.execute(
            "SELECT category, COUNT(*) as cnt FROM tools GROUP BY category ORDER BY cnt DESC"
        ).fetchall()
        by_cloud = self.conn.execute(
            "SELECT cloud, COUNT(*) as cnt FROM tools GROUP BY cloud ORDER BY cnt DESC"
        ).fetchall()
        open_source = self.conn.execute(
            "SELECT COUNT(*) FROM tools WHERE open_source = 1"
        ).fetchone()[0]
        return {
            "total": total,
            "by_category": [dict(r) for r in by_category],
            "by_cloud": [dict(r) for r in by_cloud],
            "open_source": open_source,
        }

    def get_distinct_dates(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT date FROM items ORDER BY date DESC"
        ).fetchall()
        return [r["date"] for r in rows]

    def get_sources(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM sources WHERE enabled=1").fetchall()
        return [dict(r) for r in rows]

    def start_run(self, dt: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO runs (date, started_at, status) VALUES (?, datetime('now'), 'running')",
            (dt,),
        )
        self.conn.commit()
        return cur.lastrowid

    def finish_run(self, run_id: int, count: int, status: str = "completed"):
        self.conn.execute(
            "UPDATE runs SET items_collected=?, status=? WHERE id=?",
            (count, status, run_id),
        )
        self.conn.commit()

    def get_recent_runs(self, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()
