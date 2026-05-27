"""
LangGraph Agent 实现

意图路由 + RAG + 任务规划架构：

START → feeling_detect → intent_recognize → intent_router → ┌── direct ──→ execute_direct → call_model
                                                              │
                                                              ├── plan ──→ router → ┌── retrieve → plan
                                                              │                      │
                                                              │                      └── plan
                                                              │                              │
                                                              └── system ──→ call_model      ▼
                                                                                  execute_task → check → call_model

架构说明：
- 意图识别：识别用户意图（支持多意图）
- 意图路由：根据意图类型决定执行路径
  - direct: 简单意图（RAG/Skill/MCP）直接执行，跳过规划
  - plan: 复杂意图需要规划，走原有流程
  - system: 系统指令直接返回
- RAG 检索：从知识库检索相关文档
- 任务规划：将复杂需求拆分为子任务
- 任务执行：按顺序执行子任务

采用 LangGraph 标准会话管理：
- 使用 Checkpointer 进行状态持久化
- 通过 thread_id 实现会话隔离
- 在 call_model 节点中更新对话历史
- 支持感情侦测，动态更新 prompt
- 支持任务规划

技能执行：
- 技能操作注册为 LangChain Agent 的工具（skill_list, skill_instructions, skill_reference, skill_run_script）
- LangChain Agent 通过 tool calling 自主发现和执行技能
- LangGraph 不包含技能相关节点，避免流程污染

架构设计：
- agent.py：只负责流程编排（节点定义、边连接）
- context_builder.py：负责上下文构建（RAG 文档、对话历史等）
- task_generators/：负责任务生成策略
"""

import time
from typing import Optional, Dict, Any, List, Literal
from langgraph.graph import StateGraph, END, START

from modules.logger import log
from modules.intent import IntentCategory, IntentConstants
from modules.context import AgentContext
from .states import AgentState, create_initial_state
from .task_generators import TaskGeneratorChain
from .context_builder import ContextBuilder
from .executors import ExecutorRegistry
from .refiners import RefinerRegistry, RefineContext


class LangGraphAgent:
    """
    LangGraph Agent

    核心功能：
    - 调用 RAGWorkflow 处理检索逻辑（可替换）
    - 调用外部 Agent 处理对话（可替换）
    - 使用 Checkpointer 进行状态持久化（可替换）
    - 支持感情侦测，动态更新 prompt（可替换）
    - 支持任务规划：将复杂需求拆分为子任务（可替换）

    设计理念：
    - 所有核心组件均通过构造函数注入，内部不感知具体实现
    - 通过鸭子类型实现多态，只需实现约定的接口方法即可替换
    - 保持架构灵活性，支持多种实现方案无缝切换

    技能执行：
    - 技能操作已注册为 LangChain Agent 的工具
    - Agent 通过 tool calling 自主发现和执行技能
    - LangGraph 不包含技能相关节点
    """

    def __init__(
        self,
        agent: Any,
        rag_workflow: Any,
        checkpointer: Any,
        feeling_detector: Any,
        task_planner: Any,
        intent_router: Any = None,
        verbose: bool = True,
    ):
        """
        初始化 LangGraph Agent

        Args:
            agent: 外部 Agent 实例（可替换），需实现 invoke(query, session_id, chat_history, feeling, uid) 方法
            rag_workflow: RAGWorkflow 实例（可替换），用于处理检索逻辑
            checkpointer: 检查点存储实例（可替换），需实现 LangGraph CheckpointSaver 接口
            feeling_detector: 感情侦测器实例（可替换），需实现 detect(text, detailed) 方法
            task_planner: 任务规划器实例（可替换），需实现 plan(query, context) 方法
            intent_router: 意图路由器实例（可替换），需实现 route(query) 方法
            verbose: 是否输出详细日志

        替换说明：
        - 所有标注"(可替换)"的参数均可传入不同实现
        - 内部仅依赖约定接口，不依赖具体实现类
        - 实现方式由调用方决定，内部不感知
        """
        self._agent = agent
        self._rag_workflow = rag_workflow
        self._checkpointer = checkpointer
        self._feeling_detector = feeling_detector
        self._task_planner = task_planner
        self._intent_router = intent_router
        self._verbose = verbose
        self._graph = None
        
        self._executors = ExecutorRegistry.build_all(
            rag_workflow=rag_workflow,
            agent=agent,
        )
        
        self._refiners = RefinerRegistry.build_all()

        self._build_graph()

    def _feeling_detect_node(self, state: AgentState) -> AgentState:
        """
        感情侦测节点：分析用户输入的情绪状态

        Args:
            state: 当前状态（包含 query）

        Returns:
            更新后的状态（包含 feeling）
        """
        query = state["query"]
        log(f"[节点: feeling_detect] 开始执行，查询: {query[:30]}...", "LangGraph")

        feeling = self._feeling_detector.detect(query)
        log(f"[节点: feeling_detect] 情绪分析结果: {feeling}", "LangGraph")

        return {"feeling": feeling}

    def _intent_recognize_node(self, state: AgentState) -> AgentState:
        """
        意图识别节点：识别用户意图（支持多意图）

        Args:
            state: 当前状态（包含 query）

        Returns:
            更新后的状态（包含 intents, is_multi_intent, current_intent）
        """
        query = state["query"]
        query_preview = query[:30] if len(query) > 30 else query
        log(f"[节点: intent_recognize] 开始意图识别: {query_preview}...", "LangGraph")

        if not self._intent_router:
            log(f"[节点: intent_recognize] 未配置意图路由器，跳过意图识别", "LangGraph")
            return {
                "intents": [],
                "is_multi_intent": False,
                "current_intent_idx": 0,
                "current_intent": None,
            }

        intents = self._intent_router.route(query)
        is_multi_intent = len(intents) > 1

        log(f"[节点: intent_recognize] 识别到 {len(intents)} 个意图，是否多意图: {is_multi_intent}", "LangGraph")
        for i, intent in enumerate(intents):
            content_preview = intent.content[:30] if len(intent.content) > 30 else intent.content
            log(f"  [{i+1}] {intent.type}: {content_preview}...", "LangGraph")

        intents_data = [intent.to_dict() for intent in intents]
        current_intent = intents_data[0] if intents_data else None

        return {
            "intents": intents_data,
            "is_multi_intent": is_multi_intent,
            "current_intent_idx": 0,
            "current_intent": current_intent,
        }

    def _route_by_intent(self, state: AgentState) -> Literal["direct", "plan", "system"]:
        """
        条件路由：根据意图类型决定执行路径

        Args:
            state: 当前状态（包含 intents）

        Returns:
            "direct": 简单意图直接执行
            "plan": 复杂意图需要规划
            "system": 系统指令
        """
        intents = state.get("intents", [])

        if not intents:
            return "plan"

        for intent_data in intents:
            category = IntentCategory(intent_data["category"])
            if category == IntentCategory.SYSTEM:
                return "system"

        for intent_data in intents:
            category = IntentCategory(intent_data["category"])
            if category not in IntentConstants.SIMPLE_CATEGORIES:
                return "plan"

        return "direct"

    def _intent_router_node(self, state: AgentState) -> AgentState:
        """
        意图路由节点：根据意图类型决定执行路径

        Args:
            state: 当前状态（包含 intents）

        Returns:
            更新后的状态（包含 execution_mode）
        """
        intents = state.get("intents", [])
        route = self._route_by_intent(state)

        if not intents:
            log(f"[节点: intent_router] 无意图，走规划模式", "LangGraph")
        elif route == "system":
            log(f"[节点: intent_router] 检测到系统指令，走系统模式", "LangGraph")
        elif route == "plan":
            log(f"[节点: intent_router] 检测到复杂意图，走规划模式", "LangGraph")
        else:
            log(f"[节点: intent_router] 全是简单意图，走直接执行模式", "LangGraph")
        
        log(f"  意图数量: {len(intents)}", "LangGraph")

        return {"execution_mode": route}

    def _execute_direct_node(self, state: AgentState) -> AgentState:
        """
        直接执行节点：按顺序执行简单意图（RAG/Skill/MCP）

        Args:
            state: 当前状态（包含 intents）

        Returns:
            更新后的状态（包含 intent_results）
        """
        intents = state.get("intents", [])
        
        log(f"[节点: execute_direct] 开始直接执行 {len(intents)} 个意图", "LangGraph")
        
        context = {
            "query": state["query"],
            "feeling": state["feeling"],
            "chat_history": state.get("chat_history", []),
        }
        
        results = ExecutorRegistry.execute_all(intents, context, self._executors)
        
        log(f"[节点: execute_direct] 执行完成，收集到 {len(results)} 个结果", "LangGraph")

        return {
            "intent_results": results,
        }

    def _router_node(self, state: AgentState) -> AgentState:
        """
        路由节点：判断是否需要检索

        Args:
            state: 当前状态（包含 query, session_id, chat_history, feeling）

        Returns:
            更新后的状态（只需返回需要更新的字段）
        """
        query = state["query"]
        log(f"[节点: router] 开始执行查询: {query[:30]}...", "LangGraph")

        need_retrieve = self._rag_workflow.should_retrieve(query)
        log(f"[节点: router] 决策: {'需要检索' if need_retrieve else '不需要检索'}", "LangGraph")

        return {"need_retrieve": need_retrieve}

    def _retrieve_node(self, state: AgentState) -> AgentState:
        """
        检索节点：执行检索

        Args:
            state: 当前状态

        Returns:
            更新后的状态（documents 使用 list_append，返回增量）
        """
        query = state["query"]
        log(f"[节点: retrieve] 开始执行", "LangGraph")

        # 选择最合适的知识库
        kb = self._rag_workflow.select_knowledge_base(query)
        self._rag_workflow.switch_knowledge_base(kb)

        # 执行检索
        documents = self._rag_workflow.retrieve(query)
        log(f"[节点: retrieve] 检索到 {len(documents)} 个文档", "LangGraph")

        # 设置 RAG 成功标志（用于后续节点判断）
        rag_success = len(documents) > 0
        log(f"[节点: retrieve] RAG 成功: {rag_success}", "LangGraph")

        # 使用 list_append reducer，返回新文档（增量）
        return {
            "documents": documents,
            "rag_success": rag_success,
        }

    def _plan_node(self, state: AgentState) -> AgentState:
        """
        规划节点：将复杂需求拆分为子任务

        使用责任链模式处理任务生成，支持灵活扩展。

        Args:
            state: 当前状态（包含 query, documents, answer, rag_success）

        Returns:
            更新后的状态（包含子任务队列和初始状态）
        """
        query = state["query"]
        log(f"[节点: plan] 开始任务规划", "LangGraph")

        # 使用责任链模式生成子任务
        chain = TaskGeneratorChain.build()
        subtasks = chain.handle(state, self._task_planner, query)

        log(f"[节点: plan] 生成 {len(subtasks)} 个子任务", "LangGraph")
        for i, task in enumerate(subtasks):
            log(f"  [{i+1}] {task['task_description'][:30]}...", "LangGraph")

        return {
            "subtasks": subtasks,
            "current_task_idx": 0,
            "is_task_completed": False,
        }

    def _execute_task_node(self, state: AgentState) -> AgentState:
        """
        任务执行节点：执行当前子任务

        Args:
            state: 当前状态（包含 subtasks, current_task_idx, feeling）

        Returns:
            更新后的状态（包含执行结果）
        """
        subtasks = state["subtasks"]
        current_idx = state["current_task_idx"]
        feeling = state["feeling"]

        current_task = subtasks[current_idx]
        task_desc = current_task["task_description"]
        log(f"[节点: execute_task] 执行任务 {current_idx + 1}/{len(subtasks)}: {task_desc[:30]}...", "LangGraph")

        # 使用 ContextBuilder 构建完整任务 prompt
        documents = state.get("documents", [])
        enhanced_task = ContextBuilder.build_task_with_context(task_desc, documents)
        if documents:
            log(f"[节点: execute_task] 注入 {len(documents)} 个RAG文档作为上下文", "LangGraph")

        # 调用 Agent 执行任务
        agent_context = AgentContext(
            session_id=state.get("session_id", "default"),
            chat_history=state.get("chat_history", []),
            feeling=feeling
        )
        
        result = self._agent.invoke(enhanced_task, agent_context)
        task_result = result.get("answer", "")

        log(f"[节点: execute_task] 任务执行完成: {task_result[:50]}...", "LangGraph")

        # 更新任务结果
        subtasks[current_idx]["result"] = task_result
        subtasks[current_idx]["status"] = "completed"

        return {
            "subtasks": subtasks,
            "answer": task_result,
            "is_task_completed": True
        }

    def _check_task_complete_node(self, state: AgentState) -> AgentState:
        """
        任务完成检查节点：判断是否有更多任务需要执行

        Args:
            state: 当前状态（包含 subtasks, current_task_idx, answer）

        Returns:
            更新后的状态（汇总最终答案或更新任务索引）
        """
        subtasks = state["subtasks"]
        current_idx = state["current_task_idx"]
        answer = state["answer"]

        log(f"[节点: check_task_complete] 检查任务完成情况", "LangGraph")

        # 如果已完成所有任务
        if current_idx >= len(subtasks) - 1:
            log(f"[节点: check_task_complete] 所有任务已完成", "LangGraph")

            # 生成汇总结果
            summary = self._task_planner.get_summary(subtasks)
            if summary:
                answer = summary
                log(f"[节点: check_task_complete] 生成汇总结果: {summary[:50]}...", "LangGraph")
            return {
                "answer": answer,
                "is_task_completed": True,
                "current_task_idx": current_idx
            }

        # 还有更多任务
        next_idx = current_idx + 1
        log(f"[节点: check_task_complete] 准备执行下一个任务: {next_idx + 1}/{len(subtasks)}", "LangGraph")

        return {
            "current_task_idx": next_idx,
            "is_task_completed": False,
        }

    def _should_retrieve(self, state: AgentState) -> Literal["retrieve", "plan"]:
        """
        条件路由：判断是否需要检索

        Args:
            state: 当前状态（包含 need_retrieve）

        Returns:
            "retrieve" 或 "plan"，决定下一步流向
        """
        decision = "retrieve" if state["need_retrieve"] else "plan"
        log(f"[条件路由] 决策: {decision}", "LangGraph")
        return decision

    def _should_continue_tasks(self, state: AgentState) -> Literal["execute_task", "call_model"]:
        """
        条件路由：判断是否继续执行下一个任务

        Args:
            state: 当前状态（包含 subtasks, current_task_idx, is_task_completed）

        Returns:
            "execute_task" 或 "call_model"，决定下一步流向
        """
        subtasks = state["subtasks"]
        current_idx = state["current_task_idx"]
        is_task_completed = state.get("is_task_completed", False)

        # 判断是否所有任务都已执行完成
        # current_idx 是刚执行完的任务索引，需要大于等于最后一个任务索引才算全部完成
        if is_task_completed or current_idx > len(subtasks) - 1:
            log(f"[条件路由] 所有任务已完成，进入最终回答", "LangGraph")
            return "call_model"
        else:
            log(f"[条件路由] 还有任务未完成，继续执行任务 {current_idx + 1}/{len(subtasks)}", "LangGraph")
            return "execute_task"

    def _call_model_node(self, state: AgentState) -> AgentState:
        """
        调用模型节点：生成最终回答，更新对话历史

        Args:
            state: 当前状态（包含 query, answer, chat_history, feeling, intent_results）

        Returns:
            更新后的状态（包含最终回答和新消息增量）
        """
        query = state["query"]
        answer = state.get("answer", "")
        chat_history = state.get("chat_history", [])
        feeling = state["feeling"]
        intent_results = state.get("intent_results", [])

        log(f"[节点: call_model] 开始执行，回答长度: {len(answer)}，对话历史长度: {len(chat_history)}，意图结果数量: {len(intent_results)}", "LangGraph")
        
        context = RefineContext.from_state(state)
        answer = RefinerRegistry.refine(context, self._agent, self._refiners)

        log(f"[节点: call_model] 执行完成: {answer[:50]}...", "LangGraph")

        return {
            "answer": answer,
            "feeling": feeling,
            "chat_history": ContextBuilder.build_chat_history(query, answer)
        }

    def _build_graph(self):
        """
        构建状态图（意图路由 + RAG + 任务规划）

        START → feeling_detect → intent_recognize → intent_router → ┌── direct ──→ execute_direct → call_model
                                                                      │
                                                                      ├── plan ──→ router → ┌── retrieve → plan
                                                                      │                      │
                                                                      │                      └── plan
                                                                      │                              │
                                                                      └── system ──→ call_model      ▼
                                                                                          execute_task → check → call_model

        意图路由说明：
        - direct: 简单意图（RAG/Skill/MCP）直接执行，跳过规划
        - plan: 复杂意图需要规划，走原有流程
        - system: 系统指令直接返回

        RAG 流程说明：
        - retrieve 节点：检索文档，存入 state["documents"]
        - plan 节点：任务规划，可访问 state["documents"]
        - execute_task 节点：执行任务时，将 RAG 文档作为上下文注入到 prompt
        """
        log("开始构建 LangGraph 状态图...", "LangGraph")

        self._graph = StateGraph(AgentState)

        # 添加节点
        self._graph.add_node("feeling_detect", self._feeling_detect_node)
        self._graph.add_node("intent_recognize", self._intent_recognize_node)
        self._graph.add_node("intent_router", self._intent_router_node)
        self._graph.add_node("execute_direct", self._execute_direct_node)
        self._graph.add_node("router", self._router_node)
        self._graph.add_node("retrieve", self._retrieve_node)
        self._graph.add_node("plan", self._plan_node)
        self._graph.add_node("execute_task", self._execute_task_node)
        self._graph.add_node("check_task_complete", self._check_task_complete_node)
        self._graph.add_node("call_model", self._call_model_node)

        # 基础流程：情绪检测 -> 意图识别 -> 意图路由
        self._graph.add_edge(START, "feeling_detect")
        self._graph.add_edge("feeling_detect", "intent_recognize")
        self._graph.add_edge("intent_recognize", "intent_router")

        # 意图路由分支：direct / plan / system
        self._graph.add_conditional_edges(
            "intent_router",
            self._route_by_intent,
            {
                "direct": "execute_direct", 
                "plan": "router", 
                "system": "call_model",
            }
        )

        # 直接执行路径
        self._graph.add_edge("execute_direct", "call_model")

        # 规划路径：路由 -> 检索或直接规划
        self._graph.add_conditional_edges(
            "router",
            self._should_retrieve,
            {"retrieve": "retrieve", "plan": "plan"}
        )

        # RAG 路径：检索后直接进入规划
        self._graph.add_edge("retrieve", "plan")

        # 任务执行主路径
        self._graph.add_edge("plan", "execute_task")
        self._graph.add_edge("execute_task", "check_task_complete")

        # 任务完成检查后的条件分支
        self._graph.add_conditional_edges(
            "check_task_complete",
            self._should_continue_tasks,
            {"execute_task": "execute_task", "call_model": "call_model"}
        )

        # 最终路径
        self._graph.add_edge("call_model", END)

        # 编译图
        self._graph = self._graph.compile(checkpointer=self._checkpointer)
        log("LangGraph 状态图构建完成", "LangGraph")

    def invoke(self, query: str, session_id: str = "default", uid: Optional[str] = None) -> Dict[str, Any]:
        """
        执行 Agent（LangGraph 1.0+ 官方标准调用方式）
        无论是否有历史，永远只传增量！
        """
        log(f"=== 开始处理请求 ===", "LangGraph")
        log(f"会话ID: {session_id}", "LangGraph")
        log(f"用户ID: {uid}", "LangGraph")
        log(f"用户查询: {query}", "LangGraph")

        # ========================
        # ✅ 正确：永远只传增量！
        # LangGraph 会自动从 Checkpointer 恢复历史状态
        # ========================
        input_state = {
            "query": query,
            "session_id": session_id,
            "uid": uid,
        }

        log(f"传入增量状态: {list(input_state.keys())}", "LangGraph")

        # 调用 LangGraph
        result = self._graph.invoke(
            input_state, # ✅ 只传增量
            config={"configurable": {"thread_id": session_id}}
        )

        log(f"=== 请求处理完成 ===", "LangGraph")
        return {
            "answer": result["answer"],
            "feeling": result["feeling"],
        }

    def stream(self, query: str, session_id: str = "default", uid: Optional[str] = None):
        """
        流式执行 Agent，逐节点返回状态更新

        Args:
            query: 用户查询
            session_id: 会话 ID
            uid: 用户 ID

        Yields:
            Dict[str, Any]: 每个节点的状态更新
        """
        log(f"=== 开始流式处理请求 ===", "LangGraph")
        log(f"会话ID: {session_id}", "LangGraph")
        log(f"用户ID: {uid}", "LangGraph")
        log(f"用户查询: {query}", "LangGraph")

        input_state = {
            "query": query,
            "session_id": session_id,
            "uid": uid,
        }

        config = {"configurable": {"thread_id": session_id}}

        for event in self._graph.stream(input_state, config, stream_mode="updates"):
            yield event

        log(f"=== 流式处理完成 ===", "LangGraph")

    def get_graph(self):
        """
        获取编译后的状态图

        Returns:
            编译后的 StateGraph 对象
        """
        return self._graph
