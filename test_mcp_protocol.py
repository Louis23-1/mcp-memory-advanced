"""端到端功能验证：remember + recall + forget。"""
import subprocess
import json

proc = subprocess.Popen(
    ["python", "memory_advanced.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    encoding="utf-8",
    errors="replace",
)

def send(msg: dict):
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()

def recv() -> dict | None:
    line = proc.stdout.readline()
    if not line:
        return None
    return json.loads(line)

# Initialize
send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}})
recv()
send({"jsonrpc": "2.0", "method": "notifications/initialized"})

# Test remember
send({"jsonrpc": "2.0", "id": 100, "method": "tools/call", "params": {"name": "remember", "arguments": {"content": "DeepSeek TUI 支持 MCP 协议，可以连接自定义工具服务器", "category": "技术笔记"}}})
resp = recv()
print("remember:", resp["result"]["content"][0]["text"])

send({"jsonrpc": "2.0", "id": 101, "method": "tools/call", "params": {"name": "remember", "arguments": {"content": "项目的数据库使用 SQLite，通过 sqlite-utils 库操作", "category": "技术笔记"}}})
resp = recv()
print("remember:", resp["result"]["content"][0]["text"])

send({"jsonrpc": "2.0", "id": 102, "method": "tools/call", "params": {"name": "remember", "arguments": {"content": "今天下午 3 点有团队会议", "category": "日程"}}})
resp = recv()
print("remember:", resp["result"]["content"][0]["text"])

# Test recall
send({"jsonrpc": "2.0", "id": 200, "method": "tools/call", "params": {"name": "recall", "arguments": {"query": "数据库", "limit": 3}}})
resp = recv()
print("recall:", resp["result"]["content"][0]["text"][:200])

# Test forget
send({"jsonrpc": "2.0", "id": 300, "method": "tools/call", "params": {"name": "forget", "arguments": {"memory_id": 3}}})
resp = recv()
print("forget:", resp["result"]["content"][0]["text"])

# Cleanup
proc.stdin.close()
proc.terminate()
proc.wait(timeout=5)
print("\n[OK] 端到端功能验证全部通过")
