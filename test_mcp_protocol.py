"""端到端功能验证：remember + recall + forget。

按 MCP 协议标准，通过子进程与服务器进行 JSON-RPC 通信。
"""
import os
import subprocess
import json
import tempfile
import time

import pytest


@pytest.fixture
def server_proc():
    """启动 MCP 服务器子进程，使用临时数据库隔离测试数据。"""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    env = {**os.environ, "MEMORY_DB_PATH": db_path}

    proc = subprocess.Popen(
        ["python", "memory_advanced.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    # 等待服务器就绪
    time.sleep(0.5)

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    for path in [db_path]:
        try:
            os.unlink(path)
        except OSError:
            pass


def _send(proc, msg: dict):
    proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
    proc.stdin.flush()


def _recv(proc) -> dict | None:
    line = proc.stdout.readline()
    return json.loads(line) if line else None


def _init(proc):
    """发送 MCP initialize 握手。"""
    _send(proc, {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        },
    })
    resp = _recv(proc)
    assert resp is not None, "initialize 无响应"
    assert resp.get("id") == 1
    _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})


class TestMCPServer:
    """MCP 协议级端到端测试。"""

    def test_initialize(self, server_proc):
        """服务器应正确响应 initialize 请求。"""
        _init(server_proc)

    def test_remember_and_recall(self, server_proc):
        """写入一条记忆，再搜索应能匹配到。"""
        _init(server_proc)
        content = "DeepSeek TUI 支持 MCP 协议"
        category = "技术笔记"

        # remember
        _send(server_proc, {
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {"name": "remember", "arguments": {"content": content, "category": category}},
        })
        resp = _recv(server_proc)
        assert resp is not None, "remember 无响应"
        text = resp["result"]["content"][0]["text"]
        assert "记忆已存入" in text, f"remember 应返回确认消息，收到: {text}"
        assert "id=" in text
        assert "技术笔记" in text

        # recall
        _send(server_proc, {
            "jsonrpc": "2.0",
            "id": 200,
            "method": "tools/call",
            "params": {"name": "recall", "arguments": {"query": "MCP", "limit": 5}},
        })
        resp = _recv(server_proc)
        assert resp is not None, "recall 无响应"
        text = resp["result"]["content"][0]["text"]
        assert content in text, f"recall 应返回记忆内容，收到: {text}"

    def test_forget(self, server_proc):
        """删除一条记忆后，搜索不应再返回它。"""
        _init(server_proc)

        # 先写入
        _send(server_proc, {
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {"name": "remember", "arguments": {"content": "临时数据", "category": "test"}},
        })
        resp = _recv(server_proc)
        assert resp is not None

        # forget
        _send(server_proc, {
            "jsonrpc": "2.0",
            "id": 300,
            "method": "tools/call",
            "params": {"name": "forget", "arguments": {"memory_id": 1}},
        })
        resp = _recv(server_proc)
        assert resp is not None, "forget 无响应"
        text = resp["result"]["content"][0]["text"]
        assert "已删除" in text, f"forget 应返回删除确认，收到: {text}"

        # 验证已删除
        _send(server_proc, {
            "jsonrpc": "2.0",
            "id": 400,
            "method": "tools/call",
            "params": {"name": "recall", "arguments": {"query": "临时", "limit": 5}},
        })
        resp = _recv(server_proc)
        assert resp is not None
        text = resp["result"]["content"][0]["text"]
        assert "未找到" in text, f"删除后搜索应返回未找到，收到: {text}"

    def test_unknown_tool(self, server_proc):
        """调用不存在的工具应返回友好的错误消息，而非抛出异常。"""
        _init(server_proc)
        _send(server_proc, {
            "jsonrpc": "2.0",
            "id": 999,
            "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}},
        })
        resp = _recv(server_proc)
        assert resp is not None
        text = resp["result"]["content"][0]["text"]
        assert "未知工具" in text, f"未知工具应返回提示，收到: {text}"
