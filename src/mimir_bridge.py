"""Embedded Mimir-compatible memory store for the Qwen MemoryAgent.

A self-contained, stdlib-only persistent memory backend that mirrors the model
used by Perseus Computing's production Mimir system: structured entities, FTS5
full-text search, optional dense (vector) recall, and Ebbinghaus-style decay.

Why embedded? So this repo runs anywhere -- `git clone`, `pip install`, set a
Qwen Cloud key, and go. No external binary, no daemon. The on-disk SQLite file
survives reboots, giving the agent true cross-session memory.

The production Mimir backend (https://perseus.observer) adds a Rust core,
AES-256-GCM encryption at rest, 27 MCP tools, and cross-workspace federation;
this module implements the same conceptual model in a compact, auditable form.

Public API (used by agent.py):
    remember(category, key, content, summary="", tags=None, importance=0.5)
    recall(query, limit=10, category="", mode="hybrid")
    decay(); cohere(); stats(); forget(category, key)
"""

import re
import json
import math
import time
import sqlite3


def _cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _tokens(text):
    return [t for t in re.findall(r"\w+", (text or "").lower()) if len(t) > 1]


class MimirBridge:
    """Self-contained SQLite-backed persistent memory store.

    Args:
        db_path: Path to the SQLite database file (auto-created).
        embed_fn: Optional callable(text) -> list[float] for dense recall.
                  Wire to QwenClient.embed to enable hybrid search.
        binary: Accepted for backward compatibility; ignored.
    """

    def __init__(self, db_path="./mimir.db", embed_fn=None, binary=None):
        self.db_path = db_path
        self.embed_fn = embed_fn
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.has_fts = self._fts5_available()
        self._init_schema()

    # ---- schema -------------------------------------------------------

    def _fts5_available(self):
        try:
            self.conn.execute("CREATE VIRTUAL TABLE temp.__fts_probe USING fts5(x)")
            self.conn.execute("DROP TABLE temp.__fts_probe")
            return True
        except sqlite3.OperationalError:
            return False

    def _init_schema(self):
        c = self.conn
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                category     TEXT NOT NULL,
                key          TEXT NOT NULL,
                content      TEXT NOT NULL,
                summary      TEXT DEFAULT '',
                tags         TEXT DEFAULT '[]',
                importance   REAL DEFAULT 0.5,
                embedding    TEXT,
                created_at   REAL,
                last_access  REAL,
                access_count INTEGER DEFAULT 0,
                decay_score  REAL DEFAULT 1.0,
                archived     INTEGER DEFAULT 0,
                UNIQUE(category, key)
            )
            """
        )
        if self.has_fts:
            c.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    content, summary, key, category,
                    content='memories', content_rowid='id'
                )
                """
            )
            c.executescript(
                """
                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, content, summary, key, category)
                    VALUES (new.id, new.content, new.summary, new.key, new.category);
                END;
                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content, summary, key, category)
                    VALUES ('delete', old.id, old.content, old.summary, old.key, old.category);
                END;
                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content, summary, key, category)
                    VALUES ('delete', old.id, old.content, old.summary, old.key, old.category);
                    INSERT INTO memories_fts(rowid, content, summary, key, category)
                    VALUES (new.id, new.content, new.summary, new.key, new.category);
                END;
                """
            )
        self.conn.commit()

    # ---- writes -------------------------------------------------------

    def remember(self, category, key, content, summary="", tags=None,
                 importance=0.5):
        now = time.time()
        emb = None
        if self.embed_fn:
            try:
                v = self.embed_fn(content)
                if v:
                    emb = json.dumps(v)
            except Exception:
                emb = None
        self.conn.execute(
            """
            INSERT INTO memories
                (category, key, content, summary, tags, importance, embedding,
                 created_at, last_access, access_count, decay_score, archived)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1.0, 0)
            ON CONFLICT(category, key) DO UPDATE SET
                content     = excluded.content,
                summary     = excluded.summary,
                tags        = excluded.tags,
                importance  = excluded.importance,
                embedding   = excluded.embedding,
                last_access = excluded.last_access,
                decay_score = 1.0,
                archived    = 0
            """,
            (category, key, content, summary or content[:200],
             json.dumps(tags or []), float(importance), emb, now, now),
        )
        self.conn.commit()
        return {"status": "stored", "category": category, "key": key}

    # ---- reads --------------------------------------------------------

    def recall(self, query, limit=10, category="", mode="hybrid"):
        candidates = {}

        # Lexical leg (FTS5, or LIKE fallback).
        for rank, row in enumerate(self._lexical_search(query, category, limit * 3)):
            candidates[row["id"]] = {"row": row, "fts": 1.0 / (rank + 1), "dense": 0.0}

        # Dense leg (Qwen embeddings), if enabled.
        if mode in ("hybrid", "dense") and self.embed_fn:
            qv = None
            try:
                qv = self.embed_fn(query)
            except Exception:
                qv = None
            if qv:
                for row in self._rows_with_embeddings(category):
                    try:
                        sim = _cosine(qv, json.loads(row["embedding"]))
                    except (TypeError, json.JSONDecodeError):
                        continue
                    if row["id"] in candidates:
                        candidates[row["id"]]["dense"] = sim
                    elif sim > 0.2:
                        candidates[row["id"]] = {"row": row, "fts": 0.0, "dense": sim}

        scored = []
        for c in candidates.values():
            row = c["row"]
            decay = row["decay_score"] if row["decay_score"] is not None else 1.0
            imp = row["importance"] if row["importance"] is not None else 0.5
            score = (0.5 * c["fts"] + 0.5 * c["dense"] + 0.15 * imp) * (0.5 + 0.5 * decay)
            scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)

        out = []
        for score, row in scored[:limit]:
            self._touch(row["id"])
            out.append({
                "category": row["category"],
                "key": row["key"],
                "content": row["content"],
                "summary": row["summary"],
                "importance": row["importance"],
                "decay_score": row["decay_score"],
                "score": round(score, 4),
            })
        return out

    def _lexical_search(self, query, category, limit):
        if self.has_fts:
            match = " OR ".join(f'"{t}"' for t in _tokens(query))
            if not match:
                return []
            sql = (
                "SELECT m.* FROM memories_fts f "
                "JOIN memories m ON m.id = f.rowid "
                "WHERE memories_fts MATCH ? AND m.archived = 0"
            )
            params = [match]
            if category:
                sql += " AND m.category = ?"
                params.append(category)
            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)
            try:
                return list(self.conn.execute(sql, params))
            except sqlite3.OperationalError:
                return []
        # LIKE fallback (FTS5 not compiled in).
        toks = _tokens(query)
        if not toks:
            return []
        clause = " OR ".join("LOWER(content) LIKE ?" for _ in toks)
        params = [f"%{t}%" for t in toks]
        sql = f"SELECT * FROM memories WHERE archived = 0 AND ({clause})"
        if category:
            sql += " AND category = ?"
            params.append(category)
        sql += " LIMIT ?"
        params.append(limit)
        return list(self.conn.execute(sql, params))

    def _rows_with_embeddings(self, category):
        sql = "SELECT * FROM memories WHERE archived = 0 AND embedding IS NOT NULL"
        params = []
        if category:
            sql += " AND category = ?"
            params.append(category)
        return list(self.conn.execute(sql, params))

    def _touch(self, id_):
        self.conn.execute(
            "UPDATE memories SET last_access = ?, access_count = access_count + 1, "
            "decay_score = 1.0 WHERE id = ?",
            (time.time(), id_),
        )
        self.conn.commit()

    # ---- maintenance --------------------------------------------------

    def decay(self):
        now = time.time()
        rows = self.conn.execute(
            "SELECT id, importance, last_access, access_count "
            "FROM memories WHERE archived = 0"
        ).fetchall()
        updated = archived = 0
        for r in rows:
            age_days = max(0.0, (now - (r["last_access"] or now)) / 86400.0)
            imp = r["importance"] if r["importance"] is not None else 0.5
            # Important / frequently-recalled memories decay slower.
            strength = 1.0 + imp * 9.0 + (r["access_count"] or 0) * 0.5
            score = math.exp(-age_days / max(strength, 0.1))
            arch = 1 if (score < 0.05 and imp < 0.8) else 0
            self.conn.execute(
                "UPDATE memories SET decay_score = ?, archived = ? WHERE id = ?",
                (round(score, 4), arch, r["id"]),
            )
            updated += 1
            archived += arch
        self.conn.commit()
        return {"status": "ok", "updated": updated, "archived": archived}

    def cohere(self):
        d = self.decay()
        rows = self.conn.execute(
            "SELECT id, content FROM memories WHERE archived = 0 "
            "ORDER BY importance DESC, access_count DESC"
        ).fetchall()
        seen = {}
        merged = 0
        for r in rows:
            sig = r["content"].strip().lower()
            if sig in seen:
                self.conn.execute(
                    "UPDATE memories SET archived = 1 WHERE id = ?", (r["id"],)
                )
                merged += 1
            else:
                seen[sig] = r["id"]
        self.conn.commit()
        return {"status": "ok", "decayed": d["updated"], "merged_duplicates": merged}

    def forget(self, category, key):
        cur = self.conn.execute(
            "UPDATE memories SET archived = 1 WHERE category = ? AND key = ?",
            (category, key),
        )
        self.conn.commit()
        return {"status": "forgotten", "rows": cur.rowcount}

    def stats(self):
        row = self.conn.execute(
            "SELECT COUNT(*) AS total, COALESCE(SUM(archived), 0) AS archived "
            "FROM memories"
        ).fetchone()
        cats = self.conn.execute(
            "SELECT category, COUNT(*) AS c FROM memories "
            "WHERE archived = 0 GROUP BY category"
        ).fetchall()
        total = row["total"] or 0
        archived = row["archived"] or 0
        return {
            "total": total,
            "active": total - archived,
            "archived": archived,
            "by_category": {r["category"]: r["c"] for r in cats},
            "fts5": self.has_fts,
            "db_path": self.db_path,
        }
