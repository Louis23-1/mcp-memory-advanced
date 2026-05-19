# MCP Memory Server 项目

## 项目概述

本目录包含一个基于 MCP 协议的语义记忆服务器，为 DeepSeek TUI 提供跨会话持久化记忆。

## 记忆策略

你在本项目中可以访问以下三个 MCP 工具：

| 工具 | 用途 |
|------|------|
| `remember` | 存入记忆，`content` 必填，`category` 可选默认 `general` |
| `recall` | 语义搜索记忆，`query` 必填，`limit` 默认 5 |
| `forget` | 按 ID 删除记忆，`memory_id` 必填 |

### 自动化规则

1. **会话开始时** — 先调用 `recall(query="<当前任务关键词>", limit=5)` 搜索相关历史记忆，作为上下文参考。

2. **执行过程中** — 遇到以下情况使用 `remember` 存入：
   - 用户表达的偏好、习惯、约束
   - 项目约定、架构决策、技术选型
   - 重要的操作结果、踩坑经验
   - 建议分类：`项目约定`、`技术笔记`、`用户偏好`、`决策记录`

3. **记忆管理** — 发现过时或错误的记忆时使用 `forget` 删除。

### 数据库

- 默认路径：`./memory_advanced.db`
- 可通过环境变量 `MEMORY_DB_PATH` 切换项目数据库
- 表结构：id (自增), content, category, timestamp, embedding

---

# AI 编码指南

以下规则在每次生成代码时必须遵守，违反任意一条就重写。

## 0. 前置检查（动手写代码之前）

生成任何代码前，先对照 `编程铁律.txt` 逐条过一遍：
- 有没有硬编码套餐名/语言代码？
- 新增功能是不是独立文件/配置，没碰旧代码？
- 用户可见字符串是不是全走 i18n？
- document.title、meta、manifest 有没有纳入语言切换？
- 数值数组是存 BLOB 还是 JSON 字符串？
- 外部接口有没有 try/except 兜底？

违反任一条 → 先调整设计，再写代码。

## 1. 多语言是默认，不是后加的功能

**所有面向用户的应用都必须是多语言的，没有例外。** 不做单语言版本再"以后加 i18n"。

- 第一个 commit 就要有 i18n 骨架：语言文件（zh.json / fr.json / en.json）、切换器、data-i18n 属性
- 系统级文本同步切换：document.title、meta description、PWA manifest、Service Worker 通知
- 永远不允许出现 UI 是法语但标题是英语的情况
- 推荐语言顺序：简体中文（默认回退）→ 法语 → 英语

## 2. 中文语义搜索技术栈

做中文语义搜索/向量检索时：
- 模型首选 `BAAI/bge-small-zh-v1.5`（中文优化，维度 512）
- 备选 `BAAI/bge-base-zh-v1.5`（精度更高，维度 768，模型更大）
- **禁止**用 `all-MiniLM-L6-v2` 处理中文内容（英文模型，中文精度差）
- 向量存 BLOB，不存 JSON 字符串（见编程铁律第 11 条）
- 相似度用余弦，自己注册 SQLite 自定义函数

## 3. 技术栈偏好

- 后端/脚本：Python 3.10+（类型注解、async/await）
- 数据库：SQLite + sqlite-utils（轻量、零配置、FTS5 全文搜索）
- 前端：原生 HTML/CSS/JS，不用 React/Vue 等框架（除非项目规模确实需要）
- 离线能力：Service Worker + IndexedDB，PWA 优先
- 部署：静态托管 + Cloudflare Worker（有后端逻辑时）
- MCP：stdio 模式，Python SDK

## 4. 错误处理强制规范

- 所有异步操作返回 `{ ok: boolean, data?: any, error?: string }` 结构
- 外部接口（HTTP handler、MCP tool、CLI 入口）必须外层 try/except
- 不允许裸异常透传给调用方
- 不允许 return null 表示错误

## 5. 代码风格

- 函数签名有类型注解
- 纯函数优先，副作用推至边界
- 模块级常量大写，函数级变量小写
- 注释写"为什么这样做"，不写"这行代码做什么"
- 注释用中文

## 6. 禁止事项

- 禁止在业务代码中硬编码任何字符串常量（套餐名、语言代码、文件路径、URL）
- 禁止 `if (lang === 'fr')` 或 `if (plan === 'platinum')` 分支
- 禁止修改已有函数的内部逻辑来满足新需求
- 禁止在回复中使用感叹号或过度热情的语气
- 禁止闲聊非技术话题

## 7. 对话风格

- 冷静、直接、工程师之间的对话方式
- 陈述事实，不说"这太棒了"、"看起来很好"之类的话
- 提供方案时附带权衡分析，不推销单一选项
- 每次回复聚焦一件事，不铺开讲
