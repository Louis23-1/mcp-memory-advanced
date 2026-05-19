# Memory Advanced — 增强版 MCP 记忆服务器

基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 的语义记忆服务器，为 DeepSeek TUI 提供跨会话的持久化记忆能力。

## 功能

| 工具 | 说明 |
|------|------|
| `remember` | 存入记忆，支持分类标签（默认 `general`） |
| `recall` | 语义搜索记忆（向量相似度 + 关键词降级） |
| `forget` | 按 ID 删除指定记忆 |

特性：

- **语义搜索**：使用 `sentence-transformers`（`all-MiniLM-L6-v2`）进行向量嵌入和余弦相似度排序
- **自动降级**：若模型不可用，自动切换为 SQLite FTS 关键词匹配
- **项目隔离**：通过环境变量 `MEMORY_DB_PATH` 为不同项目指定独立数据库
- **零配置启动**：首次运行自动建表，开箱即用

## 快速开始

### 1. 环境要求

- Python >= 3.10
- pip

### 2. 安装依赖

```bash
pip install mcp sqlite-utils sentence-transformers numpy
```

### 3. 下载服务器脚本

```bash
git clone https://github.com/<your-username>/mcp-memory-advanced.git
cd mcp-memory-advanced
```

### 4. 注册到 DeepSeek TUI

```bash
deepseek mcp add memory --command python --arg "$(pwd)/memory_advanced.py"
```

> **Windows (PowerShell)：** 将 `$(pwd)` 替换为绝对路径，例如：
> ```powershell
> deepseek mcp add memory --command python --arg C:\Users\louie\Music\MCP\memory_advanced.py
> ```

### 5. 验证

重启 DeepSeek TUI，在新会话中尝试：

```
remember(content="DeepSeek 支持 MCP 协议", category="技术笔记")
recall(query="MCP")
```

---

## DeepSeek TUI MCP 配置详解

### 什么是 MCP

Model Context Protocol (MCP) 是一种开放协议，允许 AI 助手通过标准化接口连接外部工具和数据源。DeepSeek TUI 内置 MCP 客户端，可以自动发现并调用注册的 MCP 服务器提供的工具。

### 配置方式

DeepSeek TUI 的 MCP 配置存储在 `~/.deepseek/mcp.json`。你可以通过 CLI 命令或直接编辑该文件来管理服务器。

#### 方式一：CLI 命令（推荐）

```bash
# 添加 stdio 服务器（通过命令行启动）
deepseek mcp add <名称> --command <启动命令> --arg <参数1> --arg <参数2>

# 添加 HTTP/SSE 服务器（通过 URL 连接）
deepseek mcp add <名称> --url <服务器URL>

# 列出所有已注册的服务器
deepseek mcp list

# 移除服务器
deepseek mcp remove <名称>
```

**示例：**

```bash
# Python 脚本服务器
deepseek mcp add my-tool --command python --arg /path/to/server.py

# Node.js 服务器
deepseek mcp add my-node-tool --command node --arg /path/to/server.js

# 远程 HTTP 服务器
deepseek mcp add remote-tool --url https://example.com/mcp
```

#### 方式二：直接编辑 mcp.json

配置文件路径：`~/.deepseek/mcp.json`

```json
{
  "timeouts": {
    "connect_timeout": 10,
    "execute_timeout": 60,
    "read_timeout": 120
  },
  "servers": {
    "memory": {
      "command": "python",
      "args": [
        "C:\\path\\to\\memory_advanced.py"
      ],
      "env": {},
      "url": null,
      "enabled": true
    }
  }
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `command` | string | 启动服务器的可执行文件路径 |
| `args` | string[] | 传递给 command 的参数列表 |
| `url` | string 或 null | HTTP/SSE 服务器地址（与 command 二选一） |
| `env` | object | 传递给子进程的环境变量，如 `{"MEMORY_DB_PATH": "./project.db"}` |
| `enabled` | boolean | 是否启用该服务器（默认 true） |
| `disabled` | boolean | 是否禁用该服务器 |
| `connect_timeout` | number 或 null | 连接超时（秒），null 使用全局默认 |
| `execute_timeout` | number 或 null | 执行超时（秒），null 使用全局默认 |
| `read_timeout` | number 或 null | 读取超时（秒），null 使用全局默认 |

### 多项目使用指南

#### 自动隔离（零配置，推荐）

记忆服务器的数据库路径由 `MEMORY_DB_PATH` 环境变量控制，默认值为 `./memory_advanced.db`（当前工作目录）。这意味着：**你在哪个项目目录下启动 DeepSeek TUI，数据库文件就会自动生成在那里。**

换项目无需任何操作——MCP 服务只注册一次，数据库自动隔离：

```
项目 A 目录/
├── .deepseek/instructions.md   ← 记忆策略
├── memory_advanced.db           ← 自动生成，只含项目 A 的记忆
└── ...

项目 B 目录/
├── .deepseek/instructions.md   ← 记忆策略
├── memory_advanced.db           ← 自动生成，只含项目 B 的记忆
└── ...
```

**操作步骤：**

1. 在新项目目录下创建 `.deepseek/instructions.md`，复制下面这段：

```markdown
## 记忆策略

你在本项目中可以访问以下三个 MCP 工具：

| 工具 | 用途 |
|------|------|
| `remember` | 存入记忆，`content` 必填，`category` 可选默认 `general` |
| `recall` | 语义搜索记忆，`query` 必填，`limit` 默认 5 |
| `forget` | 按 ID 删除记忆，`memory_id` 必填 |

### 自动化规则

1. **会话开始时** — 先调用 `recall(query="<当前任务关键词>", limit=5)` 搜索相关历史记忆。
2. **执行过程中** — 遇到值得记录的信息使用 `remember` 存入。
3. **记忆管理** — 发现过时或错误的记忆时使用 `forget` 删除。

建议分类：`项目约定`、`技术笔记`、`用户偏好`、`决策记录`
```

2. 在该项目目录下启动 DeepSeek TUI，MCP 服务会自动连接。

3. 首次使用 `remember` 时，`memory_advanced.db` 自动创建在该目录。

4. 换个项目，重复步骤 1-2——数据库完全独立。

#### 共享数据库（多项目共用记忆）

如果你希望多个项目共享同一个记忆库，在 `mcp.json` 中指定固定路径：

```json
{
  "servers": {
    "memory": {
      "command": "python",
      "args": ["C:\\path\\to\\memory_advanced.py"],
      "env": { "MEMORY_DB_PATH": "C:\\shared\\common_memory.db" },
      "enabled": true
    }
  }
}
```

这样所有项目都读写 `C:\shared\common_memory.db`，真正做到跨项目知识共享。

#### 多实例注册（不同项目用不同模型）

如果你需要为不同项目使用不同的嵌入模型（如中文项目用 BGE，英文项目用 MiniLM），可以注册多个实例：

```json
{
  "servers": {
    "memory-zh": {
      "command": "python",
      "args": ["C:\\path\\to\\memory_advanced.py"],
      "env": { "MEMORY_DB_PATH": "C:\\projects\\chinese-app\\.memory.db" },
      "enabled": true
    },
    "memory-en": {
      "command": "python",
      "args": ["C:\\path\\to\\memory_advanced_en.py"],
      "env": { "MEMORY_DB_PATH": "C:\\projects\\english-app\\.memory.db" },
      "enabled": true
    }
  }
}
```

#### 总结

| 需求 | 方案 | 操作 |
|------|------|------|
| 换项目自动隔离 | 默认行为 | 在新目录启动，复制 `instructions.md` |
| 多项目共享记忆 | 固定路径 | 在 `mcp.json` 中设 `MEMORY_DB_PATH` |
| 不同项目用不同模型 | 多实例 | 注册多个 MCP 服务器，各指不同脚本/DB |

### 让 AI 自动使用记忆

在项目根目录创建 `.deepseek/instructions.md`，添加以下内容：

```markdown
## 记忆策略

每次会话开始时，请先调用 recall 工具搜索与当前任务相关的历史记忆。

工作流程：
1. 会话开始 → recall(query="当前任务关键词", limit=5)
2. 发现值得记录的信息 → remember(content="...", category="分类")
3. 记忆过时或错误 → forget(memory_id=<id>)

可用分类：项目约定、技术笔记、用户偏好、决策记录
```

DeepSeek TUI 会在每个新会话中自动加载该指令，AI 将按照规则检索和存储记忆。

### 故障排查

**服务器无法启动**

```bash
# 手动运行脚本，查看错误信息
python memory_advanced.py
```

常见问题：
- Python 版本低于 3.10 → 升级 Python
- 缺少依赖 → `pip install -r requirements.txt`
- Windows 编码问题 → 脚本已内置 UTF-8 适配，如仍有问题请检查终端编码设置

**工具未出现在会话中**

1. 确认服务器已启用：`deepseek mcp list`
2. 重启 DeepSeek TUI
3. 检查 `~/.deepseek/mcp.json` 中 `enabled` 为 `true`

**语义搜索精度低**

`all-MiniLM-L6-v2` 是轻量级通用模型，对中文语义的捕捉能力有限。如需更高精度，可在 `memory_advanced.py` 中将模型替换为：

```python
EMBED_MODEL = SentenceTransformer("BAAI/bge-small-zh-v1.5")  # 中文优化
```

---

## 项目结构

```
mcp-memory-advanced/
├── memory_advanced.py       # MCP 记忆服务器主程序
├── test_startup.py           # 启动验证测试
├── test_mcp_protocol.py      # MCP 协议端到端测试
├── .gitignore
└── README.md
```

## 技术栈

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — 协议实现
- [sqlite-utils](https://sqlite-utils.datasette.io/) — 数据库操作
- [sentence-transformers](https://www.sbert.net/) — 文本向量化
- SQLite FTS5 — 全文搜索降级方案

## License

MIT
