# CHANGELOG

> All notable changes to this project will be documented in this file.
> 
> The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
> and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.1.0] - 2026-06-09

### Added
- **Manifest 驱动架构（核心架构演进）**
  - 新增 `manifest.py`：PLUGIN.yaml 解析器 + 数据类定义
    - `PluginManifest`：插件顶层配置（name / description / version / expert / routing / intents / prompt）
    - `ExpertConfig`：Expert 元信息配置（category / icon / label / priority）
    - `RoutingConfig`：路由配置（target_format / target_prefix / aliases / default_fallback）
    - `IntentConfig`：意图配置（dynamic / static）
    - `PromptConfig`：Prompt 模板配置（capability_template / single_hint / multi_hint）
  - 每个 Expert 插件目录新增 `PLUGIN.yaml` 声明式配置文件
    - `plugins/mcp_plugin/PLUGIN.yaml`：MCP Expert 配置
    - `plugins/skill_plugin/PLUGIN.yaml`：Skill Expert 配置
    - `plugins/rag_plugin/PLUGIN.yaml`：RAG Expert 配置
    - `plugins/chat_plugin/PLUGIN.yaml`：Chat Expert 配置
  - 插件目录结构标准化：`plugins/{plugin_name}/plugin.py` + `plugins/{plugin_name}/PLUGIN.yaml`

### Changed
- **ExpertPlugin 基类改造**
  - 构造函数接受 `PluginManifest` 参数，自动生成 `ExpertMeta`
  - `register_intents()` 从 Manifest 的 `intents.static` 自动注册静态意图
  - `render_capability()` 使用 Manifest 的 `prompt.capability_template` 渲染能力描述
- **PluginRegistry 增强**
  - 新增 `build_route_alias_map()`：构建路由别名映射（如 `system → chat`）
  - 新增 `get_default_fallback_category()`：获取默认回退类别（从 Manifest 的 `routing.default_fallback`）
  - 新增 `get_default_fallback_expert_name()`：获取默认回退 Expert 名称
  - 新增 `build_target_format_descriptions()`：动态生成 target 格式描述（替代硬编码）
  - 新增 `build_category_options()`：动态生成类别选项列表
- **Planner Prompt 动态化**
  - `DECOMPOSE_PROMPT` 移除硬编码的 target 格式描述和类别选项
  - 改为 `{target_format_descriptions}` 和 `{category_options}` 动态变量
  - `models.py` 新增 `build_planned_subtask_model()` 和 `build_task_decomposition_model()` 动态注入 Field 描述
- **路由逻辑动态化**
  - `executable_intent_decomposer.py`：路由别名解析改用 `build_route_alias_map()`
  - `dispatch.py`：默认回退类别改用 `get_default_fallback_category()`
  - `merge.py`：默认回退 Expert 名称改用 `get_default_fallback_expert_name()`
- **插件加载方式统一**
  - `plugins/__init__.py` 新增 `create_builtin_plugins()` 工厂函数
  - 从各插件目录的 `PLUGIN.yaml` 加载 Manifest 并创建插件实例
  - `agent.py` 改用 `create_builtin_plugins()` 替代手动注册

### Removed
- 旧插件文件（移至子目录）
  - `plugins/mcp_plugin.py` → `plugins/mcp_plugin/plugin.py`
  - `plugins/skill_plugin.py` → `plugins/skill_plugin/plugin.py`
  - `plugins/rag_plugin.py` → `plugins/rag_plugin/plugin.py`
  - `plugins/chat_plugin.py` → `plugins/chat_plugin/plugin.py`
- 硬编码配置
  - `prompts.py` 中 4 行 target 格式硬编码
  - `prompts.py` 中 "mcp/skill/rag/chat" 类别硬编码
  - `models.py` 中 Field 描述硬编码
  - `dispatch.py` 中默认回退类别 `"mcp"` 硬编码
  - `merge.py` 中默认回退 Expert `"chat_expert"` 硬编码

### Fixed
- **`_build_expert_state` 使用 `self` 但不是类方法**：改为参数传入 `plugin_registry`
- **Merge 润色 Prompt 去重不够强**：加强去重规则为"最高优先级"

---

## [2.0.1] - 2026-06-08

### Changed
- **意图注册插件化**
  - `IntentRegistry` 移除 `register_from_mcp_tools` / `register_from_skills` / `register_from_knowledge_bases` 三个特定方法
  - 只保留 `register_intent` 通用接口，新增 Expert 无需修改 IntentRegistry
  - 各插件在 `register_intents()` 中直接调用 `register_intent()` 逐个注册意图
  - `ChatPlugin.register_intents()` 主动注册 `CHAT_INTENTS` + `SYSTEM_INTENTS`，不再由 IntentRegistry 硬编码
  - `IntentRegistry._register_system_intents()` 只保留 `complex_plan` 框架级意图
- **意图识别 Prompt 优化**
  - `complex_plan` 意图不再从 `get_intent_descriptions()` 中过滤，暴露给 LLM
  - Prompt 中明确 `complex_plan` 是主动判断而非兜底选项
  - 新增优先级规则：先判断请求性质，再匹配具体意图
- **可执行类别动态化**
  - 移除 `models.py` 中的 `EXECUTABLE_CATEGORIES` 硬编码常量
  - `PluginRegistry` 新增 `build_executable_categories()` 方法，从已注册插件的 `meta.category` 动态构建
  - `ExecutableIntentDecomposer` 和 `PlannerDecomposeNode` 改为从 `plugin_registry` 动态获取类别
- **任务分解逻辑独立**
  - 新增 `ExecutableIntentDecomposer`（`planner/executable_intent_decomposer.py`）：可执行意图规则映射分解
  - `PlannerDecomposeNode` 重构为纯编排者，委托分解逻辑给 `ExecutableIntentDecomposer` 和 `ComplexPlanDecomposer`
  - 共享数据模型 `TaskDecomposition` / `PlannedSubtask` 移至 `planner/models.py`，解决循环导入

### Fixed
- `SkillPlugin` 和 `RAGPlugin` 缺少 `IntentCategory` 导入，导致意图注册失败
- `get_intent_descriptions()` 过滤所有 system 类别意图，导致 skill/rag 意图不出现在 LLM Prompt 中

---

## [2.1.0] - 2026-06-08

### Changed
- **插件化架构重构（核心架构变更）**
  - Expert 从硬编码 Subgraph 重构为基于 `ExpertPlugin` 抽象基类的插件化架构
  - 新增 `ExpertPlugin` 抽象基类（`plugin_base.py`）：定义 `meta` / `execute` / `on_activate` / `on_deactivate` / `render_capability` 契约
  - 新增 `ExpertMeta` 数据类（`meta.py`）：统一插件元信息（name / category / description / priority / icon / label）
  - 新增 `PluginRegistry` 注册表（`plugin_registry.py`）：管理插件生命周期，提供框架集成接口
    - `register_graph_nodes()`：动态注册图节点和边，替代硬编码 `graph.add_node` + `graph.add_edge`
    - `build_category_map()`：动态生成 category → expert 映射，替代硬编码 `CATEGORY_EXPERT_MAP`
    - `build_dispatch_targets()`：动态生成调度路由目标，替代硬编码 `PLANNER_DISPATCH_TARGETS`
    - `build_capability_descriptions()`：动态生成能力描述，替代硬编码 `DECOMPOSE_PROMPT` 中的能力列表
  - 新增 `helpers.py`：插件公共工具函数（`filter_intents_by_category` / `build_hints_input` / `invoke_agent_safely` / `build_agent_result` 等）
  - 4 个内置插件实现：
    - `MCPPlugin`（`plugins/mcp_plugin.py`）：MCP 工具调用插件
    - `SkillPlugin`（`plugins/skill_plugin.py`）：技能执行插件
    - `RAGPlugin`（`plugins/rag_plugin.py`）：知识库检索插件
    - `ChatPlugin`（`plugins/chat_plugin.py`）：对话处理插件
  - `PlannerDecomposeNode` 改为从 `PluginRegistry` 动态获取能力描述
  - `PlannerDispatchNode` 改为从 `PluginRegistry` 动态获取路由映射
  - `MultiAgentGraphBuilder` 改为从 `PluginRegistry` 动态注册图节点和边
  - `Step` 枚举支持动态步骤注册（`register_step` / `get_step`），新插件自动支持 SSE 事件推送
- **插件初始化方式统一**
  - 所有插件在构造函数中初始化 `self._meta`，通过 `@property meta` 返回
  - 所有插件在 `on_activate(context)` 中获取依赖（ai_client / rag_workflow 等）并创建 Agent
  - 基类提供 `_invoke_agent` 和 `_build_result` 辅助方法，插件主动调用
- **Planner 模块拆分**
  - `PlannerDecomposeNode` 独立为 `planner/decompose.py`
  - `PlannerDispatchNode` 独立为 `planner/dispatch.py`
  - 移除 `planner/__init__.py`（仅导入，无实质内容）
- **代码质量优化**
  - `PluginRegistry.build_category_map()` 优先级比较逻辑简化，避免 if 嵌套
  - `graph.py` 内嵌套方法提取为类方法（`_route_from_supervisor` / `_route_from_planner_dispatch`）
  - 移除所有 `importlib` 动态导入，改为顶层静态导入
  - 移除 `global` 关键字使用，改为实例属性

### Removed
- `ExpertMeta.enabled` 字段（插件可用性通过条件注册和 `on_activate` 中跳过 Agent 创建处理）
- 旧 Subgraph 文件（`subgraphs/mcp_subgraph.py` / `skill_subgraph.py` / `rag_subgraph.py` / `chat_subgraph.py` / `planner_subgraph.py`）
- 旧工具文件（`tools/mcp_tools.py` / `skill_tools.py` / `rag_tools.py` / `planner_tools.py`）
- 旧 `expert_agent_factory.py`
- 硬编码 `CATEGORY_EXPERT_MAP` 和 `PLANNER_DISPATCH_TARGETS`

### Fixed
- **意图识别优化**：LLM Prompt 新增"优先匹配可用意图列表中的具体意图"规则，修正示例（`mcp_get_weather_recommendation` 不再误识别为 `complex_plan`）
- **客户端超时**：`test.js` 的 `fetch` 添加 `AbortController` 超时控制（10 分钟），避免长时间请求被系统层断开报 `fetch failed`
- **RAG 插件注册**：移除条件注册，统一无条件注册，在 `on_activate` 中处理 `rag_workflow` 不可用的情况

---

## [2.0.0] - 2026-06-07

### Changed
- **统一 Planner 路由重构（核心架构变更）**
  - Supervisor 路由简化：所有意图统一路由到 `planner_decompose`，移除多路径分支
  - `SUPERVISOR_ROUTE_TABLE` 简化为单条规则（`condition=True → planner_expert`）
  - `_route_from_supervisor` 始终返回 `planner_decompose`，不再根据意图类型做分支判断
  - 移除 `_build_parallel_sends` 和 `_route_expert_after_execution` 函数
  - Expert 执行后固定边回到 `planner_dispatch`，不再条件路由
  - 移除 `SUPERVISOR_ROUTE_TARGETS` 中除 `planner_decompose` 外的所有条目
- **Planner 内部区分处理**
  - `EXECUTABLE_CATEGORIES` 扩展为 `{mcp, skill, rag, chat, system}`
  - 可执行意图（mcp/skill/rag/chat/system）→ 直接构建子任务，不调 LLM，单波次完成
  - complex_plan 意图 → 每个 complex_plan 独立调用 LLM 分解，保留完整规划能力（零降级）
  - 混合意图 → 可执行直接构建 + complex_plan LLM 分解，合并后统一波次调度
- **chat/system 意图映射**
  - `_build_subtasks_from_intents` 将 chat/system 映射为 `chat` 类别子任务
  - `_group_intents_by_category` 合并 chat 和 system 到 `chat` 分组
- **MergeNode 适配统一路由**
  - 移除 `is_planner_flow` 判断（统一路由后所有结果都有 subtask_idx）
  - 新增 `_refine_single_chat` 方法，单个 chat_expert 结果也走 LLM 润色
- **chat_expert 调用方式修复**
  - `_generate_subtask_content` 修复 `Assistant.invoke` 调用方式：从 dict 参数改为 `(input: str, context: AgentContext)`
  - 修复取值 key：`response.get("output")` → `result.get("answer")`
  - 移除已失效的 Supervisor 直接调度路径（RefinerRegistry 润色），统一由 MergeNode 润色
- **chat_refiner.py 调用方式修复**
  - 同步修复 `Assistant.invoke` 调用方式和取值 key
- **graph.py 清理**
  - 移除 `from langgraph.types import Send`（未使用）
  - 移除 `resolve_route`、`classify_intents`、`SUPERVISOR_ROUTE_TABLE` import
  - `_route_from_supervisor` 简化为直接提取类别信息做日志

### Added
- **Expert 异常保护**
  - mcp_expert、rag_expert、skill_expert、chat_expert 全部新增 try/except 异常捕获
  - `DataInspectionFailed`（内容安全审查）返回友好提示
  - 其他异常返回错误信息摘要，日志输出完整错误详情（不裁剪）

### Removed
- `MULTI_AGENT_PARALLEL_ENABLED` Feature Flag（统一路由后并行由 Planner 波次调度自动处理，不再需要独立开关）
- `_build_parallel_sends` 函数（Supervisor 不再直接并行分发）
- `_route_expert_after_execution` 函数（Expert 固定边回到 planner_dispatch）
- chat_subgraph 中 Supervisor 直接调度路径（RefinerRegistry 润色分支）

### Fixed
- **chat_expert 返回 dict 字符串**：`Assistant.invoke` 传 dict 导致 LLM 收到混乱输入，返回 `{'answer': '...', 'intermediate_steps': [], ...}` 原始 dict 字符串。修复后返回纯文本回答
- **chat_expert 重复第一轮回答**：dict 被当作 input 字符串传入，包含第一轮完整对话历史，LLM 直接复述。修复后 chat_history 走正规通道，LLM 能正确区分历史和当前问题
- **MergeNode 单 chat 结果跳过润色**：统一路由后 chat_expert 只生成纯内容，但 MergeNode 对单个 chat_expert 结果直接取 answer 跳过润色。修复后也走 LLM 润色

---

## [1.9.0] - 2026-06-07

### Added
- **多 Agent 协作模块（Phase 3：Planner 编排 + 旧架构清理 + Bug 修复）**
  - `PlannerExpertNode`：Planner 分解+调度 Subgraph，Orchestrator-Worker 模式
    - `planner_decompose`：LLM 结构化输出分解复杂任务为 `PlannedSubtask` 列表
    - `planner_dispatch`：波次调度，独立子任务并行 Send，依赖子任务按波次串行
    - `PlannedSubtask`：含 `targets: List[str]` 字段，引导 LLM 输出正确 target
    - `_restore_intents_from_subtask`：从子任务恢复意图，2 分支（有 targets / 无 targets 兜底）
    - `DECOMPOSE_PROMPT`：引导 LLM 填写 targets 字段，减少路由失败
  - `BaseExpertNode`：Expert 基类，提供 `_build_input` / `_build_result` / `_get_subtask_idx` 公共逻辑
  - `MergeNode`：合并所有 Expert 结果，3 种润色策略（单 chat / 多子任务 / 单非 chat）
  - `ChatExpertNode`：Chat Expert Subgraph，集成 RefinerRegistry + chat_refiner 兜底润色
  - `MCPExpertNode`：MCP Expert Subgraph，ReAct 循环完成工具选择和参数提取
  - `SkillExpertNode`：Skill Expert Subgraph，含 `_extract_skill_name` 校验逻辑
  - `RAGExpertNode`：RAG Expert Subgraph，ReAct 循环完成知识库选择、检索和生成
  - `ExpertAgentFactory`：领域专精 Agent 工厂，`_get_skill_tools` 动态加载技能工具
  - `chat_refiner.py`：Chat 兜底润色器，替代旧 Refiner 链
  - 意图识别后处理修正：`_correct_chat_to_complex_plan`，chat → complex_plan 自动修正
  - `IntentCategory.COMPLEX_PLAN`：新增意图类别，对应 Planner 分解路径
  - `IntentConstants.COMPLEX_CATEGORIES`：`{PLAN}` 类别组

### Changed
- **Supervisor 节点增强**
  - 同时重置 `agent_results`、`planned_subtasks`、`__dispatch_complete__` 三个字段
  - 避免跨请求残留导致 PlannerDispatch 误判
- **SkillExpertNode 技能名称提取**
  - `_extract_skill_name` 增加校验：排除中文/空格/逗号等非法 target
  - 合法 target → 快速路径（直接 skill_instructions），非法 target → 兜底路径（先 skill_list）
- **PlannedSubtask 字段统一**
  - `target: str` → `targets: List[str]`，与可执行意图格式统一
  - `_restore_intents_from_subtask` 从 3 分支简化为 2 分支
- **意图识别 Prompt 优化**
  - 类别选项增加 `complex_plan`，LLM 可识别需要多步骤编排的意图
  - `_correct_chat_to_complex_plan` 后处理修正，减少误判
- **Step 枚举更新**
  - 新增 `PLANNER_DECOMPOSE`、`PLANNER_DISPATCH`、`MERGE`
  - 移除旧架构步骤：`EXECUTE_DIRECT`、`EXECUTE_TASK`、`CHECK_TASK`、`CALL_MODEL`、`RAG_ROUTER`

### Removed
- **旧架构代码彻底清理（10 个文件 + 多处引用）**
  - 删除 `nodes/execute.py`（ExecuteDirectNode, ExecuteTaskNode, CheckTaskCompleteNode）
  - 删除 `nodes/rag.py`（RouterNode, RetrieveNode）
  - 删除 `nodes/plan.py`（PlanNode）
  - 删除 `nodes/model.py`（CallModelNode）
  - 删除 `graph.py`（旧 GraphBuilder）
  - 删除 `edges.py`（旧条件路由函数）
  - 删除 `refiners/intent_refiner.py`、`summary_refiner.py`、`direct_refiner.py`
  - 删除 `task_generators/` 整个目录（旧任务生成责任链）
  - 移除 `IntentRouterNode`（旧路径专用路由节点）
  - 移除 `LEGACY_ROUTE_TABLE` 及相关导出
  - 移除 `SUPERVISOR_ROUTE_TARGETS` 中的 `execute_direct`、`router` 条目
  - 移除 `ExecutorRegistry.build_all` 调用和 `executors` 参数

### Fixed
- **Skill Expert 反复重试 Bug**：Planner 分解子任务时 target 用描述文字拼凑（如 `"skill:根据技术方案设计，使用 drawio..."`），Skill Expert 找不到技能目录。修复：`_extract_skill_name` 校验 + `PlannedSubtask.targets` 引导 LLM 输出正确 target
- **Supervisor State 残留 Bug**：上一轮走 Planner 路径后，下一轮残留 `planned_subtasks` 导致 PlannerDispatch 误判跳过执行。修复：Supervisor 同时重置三个字段
- **MergeNode `Step.CALL_MODEL` 引用残留**：已删除枚举仍被引用，替换为 `Step.MERGE`
- **RefinerRegistry 无润色器注册**：新增 `chat_refiner.py` 作为兜底润色器
- **summarize_results TypeError**：LLM 传入字典格式导致类型错误，增加格式自适应

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

### Phase 3: Multi-Agent Collaboration (2026-05-30 - 2026-06-07)
- **Supervisor + Expert + Planner 架构**
- Supervisor 声明式路由（SUPERVISOR_ROUTE_TABLE）
- 5 个领域专精 Expert（MCP / Skill / RAG / Planner / Chat）
- 工具隔离：每个 Expert 只绑定自己领域的工具
- Send API 并行分发
- Planner 分解+波次调度（Orchestrator-Worker 模式）
- Merge 节点统一润色
- 旧架构代码彻底清理（10 个文件 + 多处引用）
- 自定义 reducer（add_agent_results、keep_last）
- Feature Flag 细粒度控制

### Phase 4: Unified Planner Routing (2026-06-07)
- **统一 Planner 路由重构**
- Supervisor 统一路由所有意图到 planner_decompose
- 可执行意图直接构建子任务（不调 LLM）
- complex_plan LLM 独立分解（完整规划能力零降级）
- 混合意图合并后统一波次调度
- Expert 执行后固定边回到 planner_dispatch
- 移除 Supervisor 直接调度和并行分发路径
- 移除 `MULTI_AGENT_PARALLEL_ENABLED` Feature Flag
- Expert 异常保护（内容安全审查友好提示）
- chat_expert 调用方式修复（Assistant.invoke 参数和取值 key）

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

### 6. 多 Agent 协作
- 统一 Planner 路由：所有意图 → planner_decompose
- 可执行意图直接构建子任务 + complex_plan LLM 独立分解
- Planner 波次调度（Orchestrator-Worker 模式）
- 4 个领域专精 Expert（MCP / Skill / RAG / Chat）
- Merge 节点统一润色

### 7. 智能任务规划
- 基于 LLM 的 1-5 级难度评估
- 自动生成多步骤执行计划
- 反思校验机制

### 8. 状态持久化
- Memory 检查点存储（开发环境）
- Redis 检查点存储（生产环境）
- 会话状态持久化

### 9. 情绪感知
- 6 种情绪检测
- 动态更新 Prompt
- 基于关键词规则

### 10. 钉钉集成
- 日程管理（创建、查询、删除）
- 待办事项
- 钉钉机器人集成
- Stream 机器人服务

### 11. 可视化配置
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
- **LangGraph**: StateGraph, Checkpointer, Send API, Command API
- **Orchestrator-Worker**: Planner 分解 + 波次调度
- **Registry Pattern**: ExecutorRegistry, RefinerRegistry, IntentRegistry
- **Factory Pattern**: CheckpointFactory, AssistantFactory, LoaderFactory, ExpertAgentFactory
- **Strategy Pattern**: ChromaIndexer, MilvusIndexer

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

**Last Updated**: 2026-06-08  
**Current Version**: 2.0.1