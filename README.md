# Memory Advanced — 增强版 MCP 记忆服务器

基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 的语义记忆服务器，为 DeepSeek TUI 等 MCP 客户端提供跨会话持久化记忆。

## 功能

| 工具 | 说明 |
|------|------|
| `remember` | 存入记忆，支持分类标签（默认 `general`） |
| `recall` | 语义搜索记忆（向量相似度 + FTS 关键词降级） |
| `forget` | 按 ID 删除指定记忆 |

特性：

- **语义搜索**：使用 `sentence-transformers`（`all-MiniLM-L6-v2`）进行向量嵌入和余弦相似度排序
- **BLOB 向量存储**：embedding 以二进制 BLOB 存储，避免 JSON 解析开销（编程铁律第 11 条）
- **异常兜底**：所有 MCP 工具入口在最外层 try/except 捕获异常（编程铁律第 12 条）
- **WAL 模式**：SQLite WAL 模式，支持并发读
- **自动降级**：若模型不可用，自动切换为 SQLite FTS 关键词匹配
- **项目隔离**：通过环境变量 `MEMORY_DB_PATH` 为不同项目指定独立数据库
- **零配置启动**：首次运行自动建表，开箱即用

## 快速开始

### 环境要求

- Python >= 3.10
- pip

### 克隆

```bash
git clone https://github.com/Louis23-1/mcp-memory-advanced.git
cd mcp-memory-advanced
```

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动（stdio 模式）

```bash
python memory_advanced.py
```

### 注册到 DeepSeek TUI

```bash
deepseek mcp add memory --command python --arg "$(pwd)/memory_advanced.py"
```

Windows PowerShell 用户使用绝对路径：

```powershell
deepseek mcp add memory --command python --arg "C:\path\to\memory_advanced.py"
```

重启 DeepSeek TUI 后即可使用 `remember`、`recall`、`forget` 工具。

## 项目隔离

记忆服务器的数据库路径由 `MEMORY_DB_PATH` 控制，默认 `./memory_advanced.db`。不同项目自动生成独立数据库：

```
项目 A/          项目 B/
├── memory_advanced.db    ├── memory_advanced.db
└── ...                   └── ...
```

如需多项目共享记忆，在 `mcp.json` 中指定固定路径：

```json
{
  "servers": {
    "memory": {
      "command": "python",
      "args": ["C:\\path\\to\\memory_advanced.py"],
      "env": { "MEMORY_DB_PATH": "C:\\shared\\common_memory.db" }
    }
  }
}
```

## 让 AI 自动使用记忆

在项目根目录的 `.deepseek/instructions.md` 中添加：

```markdown
## 记忆策略

每次会话开始时，先调用 `recall` 搜索与当前任务相关的历史记忆。

工作流程：
1. 会话开始 → `recall(query="当前任务关键词", limit=5)`
2. 发现值得记录的信息 → `remember(content="...", category="分类")`
3. 记忆过时或错误 → `forget(memory_id=<id>)`

可用分类：`项目约定`、`技术笔记`、`用户偏好`、`决策记录`
```

## 故障排查

```bash
# 手动运行脚本，查看错误信息
python memory_advanced.py

# 检查服务器注册状态
deepseek mcp list

# 运行测试
python -m pytest test_startup.py test_mcp_protocol.py -v
```

常见问题：
- Python 版本低于 3.10 → 升级 Python
- 缺少依赖 → `pip install -r requirements.txt`
- 语义搜索精度低 → 将模型替换为 `BAAI/bge-small-zh-v1.5`（中文优化）

## 项目结构

```
├── memory_advanced.py       # MCP 记忆服务器主程序
├── test_startup.py          # 启动验证测试（pytest）
├── test_mcp_protocol.py     # MCP 协议端到端测试（pytest）
├── requirements.txt         # Python 依赖
├── AGENTS.md                # AI 工作指南
└── README.md                # 本文档
```

## 技术栈

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — MCP 协议实现
- [sqlite-utils](https://sqlite-utils.datasette.io/) — SQLite 数据库操作
- [sentence-transformers](https://www.sbert.net/) — 文本向量化（可选）
- SQLite FTS5 — 全文搜索降级方案
- NumPy — 向量运算

## License

MIT
