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
  - 表结构：id (自增), content, category, timestamp, embedding (JSON 数组)

依赖：
  pip install mcp sqlite-utils sentence-transformers numpy
"""

import os
import sys
import json
import time
import asyncio
import sqlite3
from datetime import datetime, timezone
from typing import Any

# 确保 stdout/stderr 使用 UTF-8（Windows 兼容）
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── MCP 核心 ────────────────────────────────────────────────────────────
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── 数据库工具 ──────────────────────────────────────────────────────────
from sqlite_utils import Database

# ── AI 嵌入（可选，安装 sentence-transformers 后启用语义搜索）────────────
try:
    from sentence_transformers import SentenceTransformer
    EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    EMBEDDING_DIM = EMBED_MODEL.get_embedding_dimension()
    print(f"[memory] 语义模型已加载: all-MiniLM-L6-v2 (维度={EMBEDDING_DIM})", file=sys.stderr, flush=True)
except Exception as exc:
    EMBED_MODEL = None
    EMBEDDING_DIM = 384  # 占位维度，实际不使用
    print(f"[memory] 语义模型加载失败，降级为关键词匹配: {exc}", file=sys.stderr, flush=True)


# ══════════════════════════════════════════════════════════════════════════
# 数据库初始化
# ══════════════════════════════════════════════════════════════════════════

def get_db_path() -> str:
    """从环境变量读取数据库路径，若未设置则使用默认值。"""
    return os.environ.get("MEMORY_DB_PATH", os.path.join(os.getcwd(), "memory_advanced.db"))


DB_PATH = get_db_path()
db = Database(DB_PATH)

# 确保表存在（自动建表）
if "memories" not in db.table_names():
    db["memories"].create({
        "id": int,          # 自增主键
        "content": str,     # 记忆内容
        "category": str,    # 分类标签
        "timestamp": str,   # ISO 时间戳
        "embedding": str,   # JSON 数组字符串（仅在 EMBED_MODEL 可用时写入）
    }, pk="id")
    db["memories"].enable_fts(["content", "category"], create_triggers=True, tokenize="porter")
    print(f"[memory] 数据库已初始化: {DB_PATH}", file=sys.stderr, flush=True)
else:
    # 确保 embedding 列存在（兼容旧表不含此列的迁移场景）
    try:
        db["memories"].add_column("embedding", str)
    except sqlite3.OperationalError:
        pass  # 列已存在，忽略

def _cosine_similarity_impl(a_json: str, b_json: str) -> float:
    """SQLite 自定义函数：计算两个 JSON 数组的余弦相似度。"""
    try:
        import math
        import numpy as np
        a = np.array(json.loads(a_json), dtype=np.float32)
        b = np.array(json.loads(b_json), dtype=np.float32)
        dot = float(np.dot(a, b))
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)
    except Exception:
        return 0.0


# 获取原生 sqlite3 连接（用于向量余弦相似度计算）
SQLITE3_DB = sqlite3.connect(DB_PATH)
SQLITE3_DB.create_function("cosine_similarity", 2, _cosine_similarity_impl)


# ══════════════════════════════════════════════════════════════════════════
# 工具实现
# ══════════════════════════════════════════════════════════════════════════

def _embed(text: str) -> str | None:
    """对文本进行向量嵌入，返回 JSON 数组字符串；不可用时返回 None。"""
    if EMBED_MODEL is None:
        return None
    vec = EMBED_MODEL.encode(text).tolist()
    return json.dumps(vec)


async def remember(content: str, category: str = "general") -> str:
    """
    存入一条记忆。

    Args:
        content:  记忆内容（任意文本）
        category: 分类标签（默认 general）

    Returns:
        确认信息，含新记忆的 ID
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    embedding = _embed(content) or "[]"

    record = {
        "content": content,
        "category": category,
        "timestamp": timestamp,
        "embedding": embedding,
    }
    row = db["memories"].insert(record)
    memory_id = row.last_pk  # 对于单条 insert 即自增 id
    # 兼容不同版本的 sqlite_utils
    if memory_id is None:
        # 手动查询最后插入的 id
        memory_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return f"记忆已存入 | id={memory_id} | 分类={category}"


async def recall(query: str, limit: int = 5) -> str:
    """
    语义搜索记忆。

    优先使用 sentence-transformers 进行向量相似度搜索；
    若未安装，则降级为基于 FTS 的关键词匹配。

    Args:
        query: 搜索查询文本
        limit: 返回条数上限（默认 5）

    Returns:
        格式化的搜索结果
    """
    if EMBED_MODEL is not None:
        # ── 语义搜索路径 ────────────────────────────────────────────────
        query_vec = _embed(query)
        cur = SQLITE3_DB.execute("""
            SELECT id, content, category, timestamp,
                   cosine_similarity(embedding, ?) AS score
            FROM memories
            WHERE embedding IS NOT NULL AND embedding != '[]'
            ORDER BY score DESC
            LIMIT ?
        """, (query_vec, limit))
        rows = cur.fetchall()
    else:
        # ── 关键词搜索降级路径 ──────────────────────────────────────────
        try:
            rows = list(db["memories"].search(query, limit=limit))
            # search 返回的是 (rowid, score) 或包含 content 的元组
            # 实际测试下 sqlite_utils 的 search 返回 dict-like 对象
            formatted_rows = []
            for row in rows:
                # row 可能是 sqlite_utils 的 Row 对象，尝试转为 dict
                if hasattr(row, "keys"):
                    d = dict(row)
                elif isinstance(row, dict):
                    d = row
                else:
                    # 如果是 (rowid, score) 元组
                    rid = row[0]
                    mem = db["memories"].get(rid)
                    if mem:
                        mem["score"] = row[1] if len(row) > 1 else 0.0
                        d = mem
                    else:
                        continue
                formatted_rows.append(d)
            rows = formatted_rows
        except Exception:
            # 最终的简单关键词匹配降级
            pattern = f"%{query}%"
            rows = list(db["memories"].rows_where(
                "content LIKE ? OR category LIKE ?",
                [pattern, pattern],
                order_by="id DESC",
                limit=limit,
            ))

    if not rows:
        return f"未找到与 '{query}' 相关的记忆。"

    lines = []
    for i, row in enumerate(rows, 1):
        # 兼容不同返回格式
        if isinstance(row, dict):
            rid = row.get("id", "?")
            content = row.get("content", "")
            cat = row.get("category", "")
            ts = row.get("timestamp", "")
            score = row.get("score", None)
        elif isinstance(row, (list, tuple)):
            # 向量搜索返回 (id, content, category, timestamp, score)
            rid = row[0]
            content = row[1] if len(row) > 1 else ""
            cat = row[2] if len(row) > 2 else ""
            ts = row[3] if len(row) > 3 else ""
            score = row[4] if len(row) > 4 else None
        else:
            continue

        ts_short = ts[:19] if ts else ""
        line = f"#{i} id={rid} [{cat}] {content}"
        if score is not None:
            line += f" (相关度: {score:.4f})"
        if ts_short:
            line += f" @{ts_short}"
        lines.append(line)

    return "\n".join(lines)


async def forget(memory_id: int) -> str:
    """
    按 ID 删除一条记忆。

    Args:
        memory_id: 要删除的记忆 ID

    Returns:
        确认信息
    """
    db["memories"].delete(memory_id)
    return f"记忆 id={memory_id} 已删除。"


# ══════════════════════════════════════════════════════════════════════════
# MCP Server 注册
# ══════════════════════════════════════════════════════════════════════════

# 创建服务器实例
server = Server("memory-advanced")

# 注册工具列表
@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="remember",
            description="存入一条记忆到知识库。content 为记忆内容，category 为可选分类标签（默认 general）。",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "要记住的内容"},
                    "category": {"type": "string", "description": "分类标签（默认 general）", "default": "general"},
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
                    "query": {"type": "string", "description": "搜索查询"},
                    "limit": {"type": "integer", "description": "返回条数上限（默认 5）", "default": 5},
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
                    "memory_id": {"type": "integer", "description": "要删除的记忆 ID"},
                },
                "required": ["memory_id"],
            },
        ),
    ]


# 工具调用分发
@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
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
        raise ValueError(f"未知工具: {name}")


# ══════════════════════════════════════════════════════════════════════════
# 主入口：stdio 模式
# ══════════════════════════════════════════════════════════════════════════

async def main():
    async with stdio_server() as (read_stream, write_stream):
        print(f"[memory] 服务器已启动 | 数据库: {DB_PATH}", file=sys.stderr, flush=True)
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
