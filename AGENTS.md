# Memory Advanced MCP Server

基于 MCP 协议的语义记忆服务器，为 DeepSeek TUI 提供跨会话持久化记忆。

## 命令

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务器（stdio 模式）
python memory_advanced.py

# 运行测试
python -m pytest test_startup.py test_mcp_protocol.py -v
```

## 项目结构

- `memory_advanced.py` — MCP 记忆服务器主程序
- `test_startup.py` — 启动验证测试（pytest）
- `test_mcp_protocol.py` — MCP 协议端到端测试（pytest）
- `requirements.txt` — Python 依赖
- `README.md` — 完整文档

## 环境变量

- `MEMORY_DB_PATH` — 数据库路径，默认 `./memory_advanced.db`

## 编程铁律遵守

- **第 11 条**：embedding 以 BLOB 存储，非 JSON 字符串
- **第 12 条**：所有外部接口函数在最外层 try/except 兜底

## 技术栈

- MCP Python SDK — 协议实现
- sqlite-utils — 数据库操作
- sentence-transformers — 文本向量化
- SQLite FTS5 — 全文搜索降级方案

## Guidelines

- Follow existing code style and patterns
- Write tests for new functionality
- Keep changes focused and atomic
- Document public APIs
