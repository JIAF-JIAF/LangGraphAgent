# CHANGELOG

> All notable changes to this project will be documented in this file.
> 
> The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
> and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.5.0] - 2026-05-25

### Added
- SSE 流式对话支持
- 技能索引系统
- 前端聊天界面优化
- 智能客服功能增强

### Changed
- 替换所有 print 日志为统一日志模块
- 重构智能客服聊天界面
- 优化向量数据库管理功能

### Fixed
- 代理执行器配置问题
- 数据库文件路径问题

---

## [1.4.0] - 2026-05-24

### Added
- Excel 文件支持（钉钉纵横 SDK 支持）
- Word 文档预览（仓颉编辑器支持）
- PDF 文件预览功能（react-pdf）
- 文件预览组件

### Changed
- 完善知识库管理功能
- 优化前端页面布局与依赖

---

## [1.3.0] - 2026-05-23

### Added
- 技能系统文档
- Agent 配置页面 UI 重构

### Changed
- **重大重构**：技能系统架构，替换旧技能管理逻辑
- 重构前后端接口与 UI

---

## [1.2.0] - 2026-05-22

### Changed
- **重大重构**：LangGraph 状态管理与依赖
- 优化钉钉机器人集成
- 重构系统初始化逻辑，使用组件工厂统一管理依赖

---

## [1.1.0] - 2026-05-20

### Added
- 技能系统与 MCP 配置功能
- 配置中心相关说明
- Agent 技能系统

### Changed
- 重构 Agent 配置页面 UI
- 更新 README 文档

---

## [1.0.0] - 2026-05-19

### Added
- Agent 技能系统
- 技能管理流程重构
- 前后端接口与 UI 重构
- 部署配置优化

### Changed
- 技能管理系统架构
- 前后端接口统一

---

## [0.9.0] - 2026-05-17

### Added
- 任务规划与反思校验能力
- 智能任务规划功能说明与截图

### Changed
- 完善 LangGraph 架构
- 移除显式 config 参数，改用环境变量统一管理配置

---

## [0.8.0] - 2026-05-16

### Added
- 向量数据库管理前端和后端服务
- 知识库可视化管理功能

### Changed
- **重大重构**：知识库模块并实现可视化管理
- 优化前端页面布局与依赖

---

## [0.7.0] - 2026-05-15

### Added
- Docker 部署文档
- 钉钉助手内容
- 多项新功能

### Changed
- 项目结构优化

---

## [0.6.0] - 2026-05-13

### Added
- 钉钉 Stream 机器人服务
- 用户存储模块
- uid 支持（钉钉集成）
- MCP 多服务器支持

### Changed
- 用户 ID 获取逻辑修复
- 模型版本更新
- 文档更新

---

## [0.5.0] - 2026-05-12

### Added
- 钉钉工具集成
- dingtalk & mcp multi-server support

### Changed
- 配置重构
- 代码重构

---

## [0.4.0] - 2026-05-11

### Added
- **情绪检测模块**：集成到对话流程
- 6 种情绪检测（default、upbeat、angry、cheerful、depressed、friendly）

### Fixed
- Prompt 变量名拼写错误

---

## [0.3.0] - 2026-05-10

### Added
- **Redis 持久化存储支持**
- 检查点存储模块重构

### Changed
- **重大重构**：检查点和 RAG 模块结构
- 迁移配置从文件到环境变量
- 迁移至 LangGraph 架构并重构文档

### Fixed
- 配置和检查点存储变更

---

## [0.2.0] - 2026-05-09

### Added
- **LangGraph 支持**：实现渐进式迁移
- 检查点存储模块
- RAG 工作流完整实现
- 查询扩展功能提升检索效果

### Changed
- **重大重构**：LangGraph 模块实现完整 RAG 工作流
- 优化 RAG 流程并更新对话历史管理
- 重构 Agent 架构

---

## [0.1.0] - 2026-05-09

### Added
- 基于 [LangchainAgent](https://github.com/JIAF-JIAF/LangchainAgent) 项目迁移而来
- 之前做的基于 LangChain 的 Agent 项目
- 保留核心架构：Flask 后端 + React 前端
- 保留基础功能：知识库检索（RAG）、LangChain Agent、MCP 工具服务
- 初始化智能客服系统项目结构

### Changed
- 从 LangchainAgent 项目迁移至 LangGraph 架构
- 优化项目结构和目录布局
- 更新依赖和配置文件

---

## Architecture Evolution

### Phase 0: LangchainAgent Legacy (Before 2026-05-09)
- **原始项目**: [LangchainAgent](https://github.com/JIAF-JIAF/LangchainAgent)
- 基于 LangChain 的 Agent 项目
- Flask + React 分离架构
- 基础 RAG 功能（ChromaDB）
- LangChain Agent 作为核心执行层
- MCP 工具服务基础架构

### Phase 1: LangGraph Migration (2026-05-09)
- **迁移至 LangGraph 架构**
- 保留核心架构：Flask 后端 + React 前端
- 保留基础功能：知识库检索（RAG）、LangChain Agent、MCP 工具服务
- 状态管理（StateGraph）
- 检查点持久化（Memory → Redis）
- 工作流编排（节点、边、路由）
- 完整 RAG 工作流实现

### Phase 2: Multi-Intent Recognition (2026-05-11 - 2026-05-25)
- **意图识别模块**（modules/intent/）
- 分层漏斗路由（L1 关键词 → L2 向量 → L3 LLM）
- 多意图识别支持
- 意图类型动态注册（Registry 模式）
- 执行器注册表（ExecutorRegistry）
- 精炼器注册表（RefinerRegistry）

---

## Key Features

### 1. 分层漏斗路由
- **L1 关键词匹配**：<1ms，80% 请求在此层处理
- **L2 向量语义匹配**：保留入口，暂未实现
- **L3 LLM 意图识别**：1-2s，处理复杂意图

### 2. 多意图识别
- 支持识别包含多个意图的用户请求
- 示例："先查询行测技巧，再画架构图"
- 自动拆分为子任务并按顺序执行

### 3. 模块化 RAG
- 可插拔的索引器（ChromaDB / Milvus）
- 可插拔的检索器（Simple / Reranking / Filtered）
- 可插拔的生成器（Stuff / MapReduce / Refine）

### 4. MCP 工具服务
- 独立部署的工具服务
- 支持分布式多服务器
- 动态添加/删除工具

### 5. 技能系统
- 基于 SKILL.md 的技能匹配
- 技能执行引擎
- 支持数据分析、绘图、旅行规划

### 6. 智能任务规划
- 基于 LLM 的 1-5 级难度评估
- 自动生成多步骤执行计划
- 反思校验机制

### 7. 状态持久化
- Memory 检查点存储（开发环境）
- Redis 检查点存储（生产环境）
- 会话状态持久化

### 8. 情绪感知
- 6 种情绪检测
- 动态更新 Prompt
- 基于关键词规则

### 9. 钉钉集成
- 日程管理（创建、查询、删除）
- 待办事项
- 钉钉机器人集成
- Stream 机器人服务

### 10. 可视化配置
- 前端 UI 管理知识库
- MCP 工具配置
- 技能安装管理
- Word/Excel/PDF 文件预览

---

## Technology Stack

### Backend
- **Framework**: Flask
- **AI Framework**: LangGraph + LangChain
- **Vector DB**: ChromaDB / Milvus
- **Persistence**: Redis / Memory
- **Tools**: MCP (Model Context Protocol)

### Frontend
- **Framework**: React + Vite
- **State Management**: Zustand
- **UI Components**: Ant Design
- **File Preview**: PDF.js, 仓颉编辑器

### Architecture Patterns
- **LangGraph**: StateGraph, Checkpointer, Command API
- **Registry Pattern**: ExecutorRegistry, RefinerRegistry, IntentRegistry
- **Factory Pattern**: CheckpointFactory, AssistantFactory, LoaderFactory
- **Strategy Pattern**: ChromaIndexer, MilvusIndexer
- **Chain of Responsibility**: TaskGeneratorChain

---

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
- [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## Contributors

- **Jianyf** - Project Lead & Architecture Design

---

## License

This project is licensed under the MIT License.

---

**Last Updated**: 2026-05-25  
**Current Version**: 1.5.0