# CHANGELOG

> All notable changes to this project will be documented in this file.
> 
> The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
> and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.8.0] - 2026-06-03

### Added
- **多 Agent 协作模块（Phase 2：专业 Subgraph 集成 / 专家架构）**
  - `ExpertAgentFactory`：领域专精 Agent 工厂，为每个 Expert 创建独立 Agent（只绑定领域工具，从根源杜绝工具幻觉）
  - `MCPExpertNode`：MCP Expert Subgraph，ReAct 循环自动完成参数提取和工具选择
  - `SkillExpertNode`：Skill Expert Subgraph，ReAct 循环自动完成技能选择和参数提取
  - `RAGExpertNode`：RAG Expert Subgraph，ReAct 循环自动完成知识库选择、检索和答案生成
  - `PlannerExpertNode`：Planner Expert Subgraph，通过委托工具（delegate_to_*）编排跨领域子任务
  - `ChatExpertNode`：Chat Expert Subgraph，集成 RefinerRegistry 润色，与旧 CallModelNode 行为一致
  - `BaseExpertNode`：Expert 基类，仅提供 `_build_input` 公共逻辑，子类继承后保持各自实现
  - `MergeNode`：Merge 节点，合并所有 Expert 结果，使用纯 LLM（无工具）润色生成最终回答
  - `supervisor_node`：Supervisor 路由节点，负责流式事件推送和 agent_results 重置
  - Send API 并行分发：混合可执行意图按类别分组，并行发送到多个 Expert
  - `_route_from_supervisor`：声明式条件路由函数，支持单目标路由和并行 Send 分发
  - `_build_parallel_sends`：构建并行 Send 列表，每个 Expert 只接收属于自己类别的意图
  - `_create_disabled_expert_node`：未启用 Expert 的空节点（确保 Send API 路由目标存在）
- **状态管理增强**
  - `add_agent_results` 自定义 reducer：支持并行 Expert 追加 + Supervisor 重置（None → 清空）
  - `keep_last` reducer：并行安全，取最后一个值
  - Supervisor 每轮返回 `{"agent_results": None}` 重置，避免跨请求累积
- **工具封装**
  - `create_planner_tools()`：含委托工具（delegate_to_mcp/skill/rag_expert），Planner 通过委托工具跨领域编排
  - `create_rag_tools()`：knowledge_search + knowledge_generate
  - `get_mcp_tools()` / `mcp_execute`：MCP 动态工具透传 + 兜底工具
  - `get_skill_tools()` / `skill_execute`：Skill 动态工具透传 + 兜底工具
- **Feature Flag 细粒度控制**
  - `MULTI_AGENT_MCP_EXPERT_ENABLED`：MCP Expert 开关
  - `MULTI_AGENT_SKILL_EXPERT_ENABLED`：Skill Expert 开关
  - `MULTI_AGENT_RAG_EXPERT_ENABLED`：RAG Expert 开关
  - `MULTI_AGENT_PLANNER_EXPERT_ENABLED`：Planner Expert 开关
  - 默认全部开启
- **Step 枚举扩展**
  - 新增 SUPERVISOR、RAG_EXPERT、SKILL_EXPERT、MCP_EXPERT、CHAT_EXPERT、PLANNER_EXPERT

### Changed
- **MultiAgentState 字段更新**
  - `agent_results` 从 `operator.add` 改为 `add_agent_results` 自定义 reducer
  - 所有字段添加 `keep_last` reducer，解决 Send API 并行写入冲突
- **supervisor_node 职责简化**
  - 只负责流式事件推送和 agent_results 重置
  - 路由日志统一由 `_route_from_supervisor` 输出，消除重复日志
- **summarize_results 兼容性增强**
  - 支持 LLM 传入 `{task_id: {...}}` 字典或 `[{...}]` 列表格式，统一转为列表
- **方法注释规范化**
  - 所有 Phase 2 改动代码的方法添加 Args/Returns 注释（参考 feeling.py 格式）

### Fixed
- **agent_results 跨请求累积**：自定义 reducer + Supervisor 重置，避免 Checkpointer 恢复历史状态导致残留
- **Supervisor 路由日志重复**：supervisor_node 和 _route_from_supervisor 各打一次日志，统一为后者
- **summarize_results TypeError**：LLM 传入字典格式导致 `string indices must be integers` 错误，增加格式自适应
- **Send API "Ignoring unknown node name"**：未启用的 Expert 注册空节点，确保路由目标存在
- **并行状态冲突**：Send API 并行执行时多个节点写入同一 state key 报错，添加 keep_last reducer

---

## [1.7.0] - 2026-05-31

### Added
- **多 Agent 协作模块（Phase 1：Supervisor + Chat Subgraph）**
  - `MultiAgentGraphBuilder`：构建混合架构主图，Supervisor 替代 intent_router 按意图类别细粒度分发
  - `supervisor_node`：声明式路由表驱动，优先级由 `SUPERVISOR_ROUTE_TABLE` 定义（complex > executable > dialog）
  - `ChatRespondNode` + `create_chat_subgraph()`：Chat 意图走独立 Subgraph，集成 RefinerRegistry
  - Feature Flag 切换：`MULTI_AGENT_ENABLED=true` 时走新图，`false` 时走旧图，零侵入
- **声明式路由架构（核心重构）**
  - `classify_intents()`：意图分类函数（单一真相源），所有路由器共用
  - `RouteRule` 数据类：条件谓词 + 目标 + 描述模板
  - `resolve_route()`：纯函数，按路由表顺序匹配，第一个 condition 为 True 的规则命中
  - `SUPERVISOR_ROUTE_TABLE`：新架构路由表（complex > executable > dialog → fallback chat_expert）
  - `LEGACY_ROUTE_TABLE`：旧架构路由表（system > complex → fallback direct）
  - 消除 4 处 if/else 硬编码，改优先级只需改路由表，路由代码零改动

### Changed
- **意图识别 Prompt 修复**
  - 类别选项增加 "chat"，LLM 不再将 general_chat 归为 "system"
  - content 字段强调保留用户约束条件（如"直接画，不用询问"）
- **IntentRouterNode / route_by_intent / _route_from_supervisor 重构**
  - 统一改用 `resolve_route()` + 对应路由表，消除重复的 if/else 路由逻辑
  - 行为与重构前完全一致（31 场景 + 64 组合验证通过）
- **IntentConstants 新增 category groups**
  - `EXECUTABLE_CATEGORIES = {MCP, SKILL, RAG}`
  - `DIALOG_CATEGORIES = {CHAT, SYSTEM}`
  - `COMPLEX_CATEGORIES = {PLAN}`
  - 新增类别只需加枚举 + 加 group 成员，路由表零改动

### Fixed
- Supervisor 多意图路由错误：mcp/skill 意图被 system/chat 遮蔽，导致可执行意图未执行
- 未知 category 处理：归入 `has_complex`，走 router/plan 而非静默丢弃

---

## [1.6.0] - 2026-05-30

### Added
- **AG-UI 协议事件类型枚举化**
  - 后端：`modules/sse/events.py` 定义 `EventType` 和 `StepStatus` 枚举
  - 前端：`client/src/api/events.js` 定义事件类型常量
  - 避免字符串硬编码，提高代码可维护性
- **思考步骤枚举封装**
  - `modules/langgraph/nodes/steps.py` 定义 `Step` 枚举
  - 封装 step/label/icon 属性，提供 `started_event()` / `completed_event()` 方法
  - 节点代码简化为一行：`writer(Step.FEELING_DETECT.started_event())`
- **多 Agent 协作模块（Phase 0：基础设施与状态扩展）**
  - `multi_agent/` 目录结构：nodes/、subgraphs/、tools/
  - Feature Flag 机制：`MULTI_AGENT_ENABLED`、`MULTI_AGENT_{NAME}_ENABLED`、`MULTI_AGENT_PARALLEL_ENABLED`，默认关闭
  - `MultiAgentState`：扩展 AgentState（18 字段 → 20 字段），新增 `current_agent` + `agent_results`（operator.add reducer 支持 Send 并行）
  - RAG @tool 封装：`knowledge_search(query, kb_name)` + `knowledge_generate(query, context)`
  - Skill 动态适配：`get_skill_tools(skill_manager)` 透传 + `skill_execute` 兜底委托 SkillExecutor
  - MCP 动态适配：`get_mcp_tools()` 透传 + `mcp_execute` 兜底委托 MCPExecutor + `reload_mcp_tools()` 热刷新
  - Planner @tool 封装：`decompose_task(query, context)` + `summarize_results(query, results)`
  - Step 枚举扩展：新增 SUPERVISOR、RAG_EXPERT、SKILL_EXPERT、MCP_EXPERT、CHAT_EXPERT、PLANNER_EXPERT

### Changed
- **Docker 服务命名统一**
  - 容器名统一为 `agent-{服务名}` 格式（替代 `chatbot-{服务名}`）
  - 服务名与目录名保持一致：`client`（替代 `db-frontend`）
  - 更新 `docker-compose.yml` 和 `client/nginx.conf`
- **SSE 事件处理器优化**
  - `SSEEventProcessor` 新增 `process()` 方法统一处理多流事件分发
  - 降低 `app.py` 路由层职责，提高代码内聚性
- **节点文件简化**
  - 所有节点文件改为导入 `Step` 枚举，移除局部常量定义
  - 使用枚举方法替代手动拼字典，代码更简洁

### Fixed
- `steps.py` 导入路径修正（`modules.sse.events` 替代 `.events`）

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

**Last Updated**: 2026-06-03  
**Current Version**: 1.8.0