# MCP Memory Server 项目

基于 MCP 协议的语义记忆服务器，为 DeepSeek TUI 提供跨会话持久化记忆。

当前工作区路径：`C:\Users\louie\Music\MCP`

## 可用的 MCP 工具

本项目中 `memory` 服务器提供了以下三个工具：

| 工具 | 用途 |
|------|------|
| `remember` | 存入记忆，`content` 必填，`category` 可选（默认 `general`） |
| `recall` | 语义搜索记忆，`query` 必填，`limit` 可选（默认 5） |
| `forget` | 按 ID 删除记忆，`memory_id` 必填 |

## 记忆策略

### 会话开始时

先调用 `recall` 搜索与当前任务相关的历史记忆：

```
recall(query="当前任务关键词", limit=5)
```

### 执行过程中

遇到以下情况使用 `remember` 存入：

- 用户表达的项目偏好、习惯、约束
- 项目约定、架构决策、技术选型
- 重要的操作结果、踩坑经验、配置细节

建议分类：`项目约定`、`技术笔记`、`用户偏好`、`决策记录`

### 记忆管理

发现过时或错误的记忆时使用 `forget` 删除。

## 数据库

- 默认路径：`./memory_advanced.db`（当前工作目录下自动生成）
- 可通过环境变量 `MEMORY_DB_PATH` 切换项目数据库
- SQLite WAL 模式，支持并发读
- embedding 以 BLOB 存储（numpy tobytes/frombuffer），非 JSON 字符串
- 向量搜索用余弦相似度（SQLite 自定义函数），降级用 FTS5 全文搜索

## 维护命令

```bash
# 启动测试
python -m pytest test_startup.py test_mcp_protocol.py -v

# 手动启动服务器（stdio 模式）
python memory_advanced.py
```
