#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强版 MCP 记忆服务器 (memory_advanced)
=========================================

功能：
  - remember(content, category)  存入记忆
  - recall(query, limit=5)       语义搜索记忆（sentence-transformers，降级为关键词）
  - forget(memory_id)            按 ID 删除记忆

数据库：
  - 路径从环境变量 MEMORY_DB_PATH 读取，默认 ./memory_advanced.db
  - 表结构：id (自增), content, category, timestamp, embedding (BLOB)
  - WAL 模式，单连接

编程铁律：
  - 第 11 条：embedding 以 BLOB 存储（numpy tobytes/frombuffer），非 JSON 字符串
  - 第 12 条：所有外部接口函数在最外层 try/except 兜底

依赖：
  pip install -r requirements.txt
"""

import os
import sys
import json
import asyncio
import sqlite3
from datetime import datetime, timezone
from typing import Any

import numpy as np

# 确保 stdout/stderr 使用 UTF-8（Windows 兼容）
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── MCP 核心 ────────────────────────────────────────────────────────────
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── AI 嵌入（可选，安装 sentence-transformers 后启用语义搜索）────────────
try:
    from sentence_transformers import SentenceTransformer

    _model = SentenceTransformer("all-MiniLM-L6-v2")
    EMBED_MODEL = _model
    EMBEDDING_DIM = _model.get_embedding_dimension()
    print(f"[memory] 语义模型已加载: all-MiniLM-L6-v2 (维度={EMBEDDING_DIM})", file=sys.stderr, flush=True)
except Exception as exc:
    EMBED_MODEL = None
    EMBEDDING_DIM = 384
    print(f"[memory] 语义模型加载失败，降级为关键词匹配: {exc}", file=sys.stderr, flush=True)


# ══════════════════════════════════════════════════════════════════════════
# 数据库初始化（单连接 + WAL 模式）
# ══════════════════════════════════════════════════════════════════════════

DB_PATH = os.environ.get("MEMORY_DB_PATH", os.path.join(os.getcwd(), "memory_advanced.db"))

from sqlite_utils import Database

db = Database(DB_PATH)
db.conn.execute("PRAGMA journal_mode=WAL")
db.conn.execute("PRAGMA foreign_keys=ON")


# 注册余弦相似度 SQLite 函数（操作 BLOB 向量）
def _cosine_similarity_blob(a_blob: bytes, b_blob: bytes) -> float:
    """计算两个 BLOB 向量的余弦相似度。"""
    try:
        a = np.frombuffer(a_blob, dtype=np.float32)
        b = np.frombuffer(b_blob, dtype=np.float32)
        dot = float(np.dot(a, b))
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)
    except Exception:
        return 0.0


db.conn.create_function("cosine_similarity", 2, _cosine_similarity_blob)


# ── 建表 ────────────────────────────────────────────────────────────────
if "memories" not in db.table_names():
    db["memories"].create(
        {
            "id": int,
            "content": str,
            "category": str,
            "timestamp": str,
            "embedding": bytes,  # BLOB
        },
        pk="id",
    )
    db["memories"].enable_fts(["content", "category"], create_triggers=True, tokenize="porter")
    print(f"[memory] 数据库已初始化: {DB_PATH}", file=sys.stderr, flush=True)
else:
    # 兼容旧表：补齐缺失列，TEXT→BLOB 迁移
    # columns 可能为 Column 对象或 tuple（取决于 sqlite-utils 版本）
    try:
        raw_cols = db["memories"].columns
        cols = {}
        for c in raw_cols:
            if isinstance(c, (list, tuple)):
                name, ctype = c[1], c[2]
            else:
                name, ctype = c.name, c.type
            cols[name] = ctype
    except Exception:
        cols = {}
    if "embedding" not in cols:
        db["memories"].add_column("embedding", bytes)
    elif cols.get("embedding") == "TEXT":
        _migrate_embedding_to_blob()


def _migrate_embedding_to_blob() -> None:
    """将旧版 TEXT 类型的 embedding 迁移为 BLOB。"""
    rows = db.conn.execute(
        "SELECT id, embedding FROM memories WHERE embedding IS NOT NULL AND embedding != '[]' AND embedding != X''"
    ).fetchall()
    if not rows:
        return
    print(f"[memory] 迁移 {len(rows)} 条 embedding: TEXT → BLOB ...", file=sys.stderr, flush=True)
    count = 0
    for rid, raw in rows:
        if isinstance(raw, str) and raw.startswith("["):
            try:
                vec = np.array(json.loads(raw), dtype=np.float32)
                db.conn.execute("UPDATE memories SET embedding=? WHERE id=?", (vec.tobytes(), rid))
                count += 1
            except Exception:
                pass
    db.conn.commit()
    print(f"[memory] embedding 迁移完成 ({count} 条)", file=sys.stderr, flush=True)


# ══════════════════════════════════════════════════════════════════════════
# 工具实现
# ══════════════════════════════════════════════════════════════════════════

def _embed(text: str) -> bytes | None:
    """对文本进行向量嵌入，返回 BLOB；不可用时返回 None。"""
    if EMBED_MODEL is None:
        return None
    return EMBED_MODEL.encode(text).astype(np.float32).tobytes()


async def remember(content: str, category: str = "general") -> str:
    """存入一条记忆。"""
    timestamp = datetime.now(timezone.utc).isoformat()
    embedding = _embed(content) or b""

    record = {
        "content": content,
        "category": category,
        "timestamp": timestamp,
        "embedding": embedding,
    }
    row = db["memories"].insert(record)
    memory_id = row.last_pk
    if memory_id is None:
        memory_id = db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return f"记忆已存入 | id={memory_id} | 分类={category}"


async def recall(query: str, limit: int = 5) -> str:
    """语义搜索记忆。优先向量相似度，降级为关键词匹配。"""
    if EMBED_MODEL is not None:
        query_blob = _embed(query)
        if query_blob is not None:
            rows = db.conn.execute(
                """
                SELECT id, content, category, timestamp,
                       cosine_similarity(embedding, ?) AS score
                FROM memories
                WHERE embedding IS NOT NULL AND embedding != X''
                ORDER BY score DESC
                LIMIT ?
                """,
                (query_blob, limit),
            ).fetchall()
        else:
            rows = []
    else:
        rows = _keyword_search(query, limit)

    if not rows:
        return f"未找到与 '{query}' 相关的记忆。"

    lines = []
    for i, row in enumerate(rows, 1):
        rid, content = row[0], row[1]
        cat = row[2] if len(row) > 2 else ""
        ts = row[3] if len(row) > 3 else ""
        score = row[4] if len(row) > 4 else None

        ts_short = ts[:19] if ts else ""
        line = f"#{i} id={rid} [{cat}] {content}"
        if score is not None:
            line += f" (相关度: {score:.4f})"
        if ts_short:
            line += f" @{ts_short}"
        lines.append(line)

    return "\n".join(lines)


def _keyword_search(query: str, limit: int) -> list[tuple]:
    """FTS 关键词搜索降级。"""
    try:
        # sqlite-utils search 返回 dict-like Row 对象 → 转 tuple
        results = list(db["memories"].search(query, limit=limit))
        formatted = []
        for r in results:
            d = dict(r)
            formatted.append((
                d.get("id", 0),
                d.get("content", ""),
                d.get("category", ""),
                d.get("timestamp", ""),
                d.get("score", None),
            ))
        return formatted
    except Exception:
        pattern = f"%{query}%"
        return list(db.conn.execute(
            "SELECT id, content, category, timestamp, NULL FROM memories "
            "WHERE content LIKE ? OR category LIKE ? ORDER BY id DESC LIMIT ?",
            (pattern, pattern, limit),
        ))


async def forget(memory_id: int) -> str:
    """按 ID 删除一条记忆。"""
    db["memories"].delete(memory_id)
    return f"记忆 id={memory_id} 已删除。"


# ══════════════════════════════════════════════════════════════════════════
# MCP Server 注册
# ══════════════════════════════════════════════════════════════════════════

server = Server("memory-advanced")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="remember",
            description="存入一条记忆到知识库。content 为记忆内容，category 为可选分类标签（默认 general）。",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "要记住的内容",
                    },
                    "category": {
                        "type": "string",
                        "description": "分类标签（默认 general）",
                        "default": "general",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="recall",
            description="从知识库中搜索记忆。优先使用语义向量搜索，降级为关键词匹配。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回条数上限（默认 5）",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="forget",
            description="按 ID 删除一条记忆。",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "integer",
                        "description": "要删除的记忆 ID",
                    },
                },
                "required": ["memory_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    工具调用分发。

    编程铁律第 12 条：所有对外暴露的入口在最外层 try/except 兜底，
    返回结构化错误，绝不把裸异常抛给调用方。
    """
    try:
        if name == "remember":
            content = arguments["content"]
            category = arguments.get("category", "general")
            result = await remember(content, category)
            return [TextContent(type="text", text=result)]

        elif name == "recall":
            query = arguments["query"]
            limit = arguments.get("limit", 5)
            result = await recall(query, limit)
            return [TextContent(type="text", text=result)]

        elif name == "forget":
            memory_id = arguments["memory_id"]
            result = await forget(memory_id)
            return [TextContent(type="text", text=result)]

        else:
            return [TextContent(type="text", text=f"未知工具: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"工具执行出错 [{name}]: {e}")]


# ══════════════════════════════════════════════════════════════════════════
# 主入口：stdio 模式
# ══════════════════════════════════════════════════════════════════════════

async def main() -> None:
    try:
        async with stdio_server() as (read_stream, write_stream):
            print(f"[memory] 服务器已启动 | 数据库: {DB_PATH}", file=sys.stderr, flush=True)
            await server.run(read_stream, write_stream, server.create_initialization_options())
    except asyncio.CancelledError:
        pass
    finally:
        db.conn.close()


if __name__ == "__main__":
    asyncio.run(main())
