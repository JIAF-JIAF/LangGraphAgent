"""
LangGraph Agent 实现

标准 LangGraph RAG 流程：
START → feeling_detect → router → ┌── 需要检索 ──→ retrieve → generate → call_model → END
                                  │
                                  └── 不需要检索 ──→ call_model → END

采用 LangGraph 标准会话管理：
- 使用 Checkpointer 进行状态持久化
- 通过 thread_id 实现会话隔离
- 在 call_model 节点中更新对话历史
- 支持感情侦测，动态更新 prompt
"""

import time
from typing import Optional, Dict, Any, List, Literal
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage, AIMessage

from .state import AgentState
from modules.checkpoint import MemorySaver
from modules.prompt import create_prompt


class LangGraphAgent:
    """
    LangGraph Agent

    纯调度层：
    - 调用 RAGWorkflow 处理检索逻辑
    - 调用外部 Agent 处理对话（可替换）
    - 使用 Checkpointer 进行状态持久化（可替换）
    - 在 call_model 节点中更新对话历史
    - 支持感情侦测，动态更新 prompt
    """

    def __init__(
        self,
        agent: Any = None,
        rag_workflow: Optional[Any] = None,
        checkpointer: Optional[Any] = None,
        feeling_detector: Optional[Any] = None,
        verbose: bool = True
    ):
        """
        初始化 LangGraph Agent

        Args:
            agent: 外部 Agent 实例（可替换），需实现 invoke(query, session_id) 方法
            rag_workflow: RAGWorkflow 实例，用于处理检索逻辑（可替换）
            checkpointer: 检查点存储实例（可替换），默认为 MemorySaver。
                         支持自定义实现 BaseCheckpointSaver 接口的类
            feeling_detector: 感情侦测器实例，用于分析用户情绪
            verbose: 是否输出详细日志
        """
        self._agent = agent              # 可替换的 Agent
        self._rag_workflow = rag_workflow  # 可替换的 RAG
        self._feeling_detector = feeling_detector  # 感情侦测器
        self._verbose = verbose

        # 使用传入的 checkpointer，默认使用自定义 MemorySaver（保持不动，支持外部传入）
        self._checkpointer = checkpointer or MemorySaver()
        self._graph = None

        self._build_graph()

    def _log(self, message: str, level: str = "INFO"):
        """
        输出日志

        Args:
            message: 日志消息
            level: 日志级别
        """
        if self._verbose:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [LangGraph] [{level}] {message}", flush=True)

    def _feeling_detect_node(self, state: AgentState) -> AgentState:
        """
        感情侦测节点：分析用户输入的情绪状态

        Args:
            state: 当前状态（包含 query）

        Returns:
            更新后的状态（包含 feeling）
        """
        query = state["query"]

        self._log(f"[节点: feeling_detect] 开始执行，查询: {query[:30]}...")

        if self._feeling_detector:
            feeling = self._feeling_detector.detect(query, True)
            self._log(f"[节点: feeling_detect] 情绪分析结果: {feeling}")
        else:
            feeling = {"feeling": "default", "score": 5}
            self._log(f"[节点: feeling_detect] 感情侦测器不可用，使用默认情绪")

        return {"feeling": feeling}

    def _router_node(self, state: AgentState) -> AgentState:
        """
        路由节点：判断是否需要检索

        Args:
            state: 当前状态（包含 query, session_id, chat_history, feeling）

        Returns:
            更新后的状态（只需返回需要更新的字段）
        """
        query = state["query"]

        self._log(f"[节点: router] 开始执行查询: {query[:30]}...")

        if self._rag_workflow:
            need_retrieve = self._rag_workflow.should_retrieve(query)
            self._log(f"[节点: router] 决策: {'需要检索' if need_retrieve else '不需要检索'}")
        else:
            need_retrieve = False
            self._log(f"[节点: router] RAG 不可用，直接调用 Agent")

        return {"need_retrieve": need_retrieve}

    def _retrieve_node(self, state: AgentState) -> AgentState:
        """
        检索节点：执行检索

        Args:
            state: 当前状态

        Returns:
            更新后的状态（只需返回 documents）
        """
        query = state["query"]

        self._log(f"[节点: retrieve] 开始执行")

        if self._rag_workflow:
            kb = self._rag_workflow.select_knowledge_base(query)
            self._rag_workflow.switch_knowledge_base(kb)
            documents = self._rag_workflow.retrieve(query)
            self._log(f"[节点: retrieve] 检索到 {len(documents)} 个文档")
        else:
            documents = []
            self._log(f"[节点: retrieve] RAG 不可用，返回空文档")

        return {"documents": documents}

    def _generate_node(self, state: AgentState) -> AgentState:
        """
        生成节点：调用 RAG 生成基于文档的回答

        Args:
            state: 当前状态（包含 query, documents, chat_history）

        Returns:
            更新后的状态（返回 RAG 生成的 answer，传给 call_model 进行最终回答）
        """
        query = state["query"]
        documents = state.get("documents", [])

        self._log(f"[节点: generate] 开始执行，文档数: {len(documents)}")

        # 调用 RAG 生成回答
        if self._rag_workflow:
            answer = self._rag_workflow.generate(query, documents)
        else:
            answer = "RAG 服务不可用，请稍后重试"

        self._log(f"[节点: generate] RAG 生成完成: {answer[:50]}...")

        # 返回 RAG 生成的回答，传给 call_model 进行最终处理
        return {"answer": answer}

    def _build_enhanced_query(self, query: str, rag_answer: str) -> str:
        """
        构建增强查询

        Args:
            query: 原始用户查询
            rag_answer: RAG 生成的结果

        Returns:
            增强后的查询
        """
        if rag_answer:
            return f"基于以下信息回答问题：\n{rag_answer}\n\n问题：{query}"
        return query

    def _call_model_node(self, state: AgentState) -> AgentState:
        """
        调用模型节点：调用外部 Agent（基于 RAG 结果或原始问题），支持动态 prompt 更新

        Args:
            state: 当前状态（包含 query, answer(RAG结果), chat_history, feeling）

        Returns:
            更新后的状态（返回 answer 和更新后的 chat_history）
        """
        query = state["query"]
        rag_answer = state.get("answer", "")
        chat_history = state.get("chat_history", [])
        feeling = state.get("feeling", {"feeling": "default", "score": 5})

        self._log(f"[节点: call_model] 开始执行，RAG结果: {'有' if rag_answer else '无'}，对话历史长度: {len(chat_history)}")
        self._log(f"[节点: call_model] 当前情绪: {feeling}")

        # 总是调用 Agent，基于 RAG 结果或原始问题
        if self._agent:
            # 动态更新 prompt（根据情绪）
            self._update_prompt_with_feeling(feeling)

            enhanced_query = self._build_enhanced_query(query, rag_answer)

            result = self._agent.invoke(enhanced_query, None, chat_history, feeling)
            answer = result.get("answer", "")
        else:
            # 如果没有 Agent，直接使用 RAG 结果或返回错误
            answer = rag_answer if rag_answer else "Agent 服务不可用，请稍后重试"

        self._log(f"[节点: call_model] 执行完成: {answer[:50]}...")

        result_state = self._update_chat_history(state, query, answer)
        result_state["answer"] = answer
        result_state["feeling"] = feeling

        return result_state

    def _update_prompt_with_feeling(self, feeling: Dict[str, Any]):
        """
        根据情绪动态更新 Agent 的 prompt

        Args:
            feeling: 情绪对象，格式: {"feeling": str, "score": int}
        """
        if self._agent:
            new_prompt = create_prompt(feeling=feeling)
            self._agent.update_prompt(new_prompt)
            self._log(f"[节点: call_model] 已根据情绪更新 prompt: {feeling['feeling']}")

    def _should_retrieve(self, state: AgentState) -> Literal["retrieve", "call_model"]:
        """
        条件路由

        Args:
            state: 当前状态

        Returns:
            下一个节点名称
        """
        decision = "retrieve" if state.get("need_retrieve", False) else "call_model"
        self._log(f"[条件路由] 决策: {decision}")
        return decision

    def _update_chat_history(self, state: AgentState, query: str, answer: str) -> AgentState:
        """
        统一更新对话历史

        Args:
            state: 当前状态
            query: 用户查询
            answer: AI 回答

        Returns:
            更新后的状态（包含新的 chat_history）
        """
        if query and answer:
            self._log(f"[_update_chat_history] 自动更新对话历史")
            return {
                "chat_history": state.get("chat_history", []) + [
                    HumanMessage(content=query),
                    AIMessage(content=answer)
                ]
            }
        return state

    def _build_graph(self):
        """
        构建状态图

        标准 RAG 流程：
        START → feeling_detect → router → ┌── 需要检索 ──→ retrieve → generate → call_model → END
                                          │
                                          └── 不需要检索 ──→ call_model → END
        """
        self._log("开始构建 LangGraph 状态图...")

        self._graph = StateGraph(AgentState)

        self._graph.add_node("feeling_detect", self._feeling_detect_node)
        self._graph.add_node("router", self._router_node)
        self._graph.add_node("retrieve", self._retrieve_node)
        self._graph.add_node("generate", self._generate_node)
        self._graph.add_node("call_model", self._call_model_node)

        self._graph.add_edge(START, "feeling_detect")
        self._graph.add_edge("feeling_detect", "router")

        self._graph.add_conditional_edges(
            "router",
            self._should_retrieve,
            {"retrieve": "retrieve", "call_model": "call_model"}
        )

        # 完整的 RAG 流程：retrieve → generate → call_model
        self._graph.add_edge("retrieve", "generate")
        self._graph.add_edge("generate", "call_model")

        self._graph.add_edge("call_model", END)

        # 使用 checkpointer 进行状态持久化（保持不动，支持外部传入）
        self._graph = self._graph.compile(checkpointer=self._checkpointer)
        self._log("LangGraph 状态图构建完成")

    def invoke(self, query: str, session_id: str = "default") -> Dict[str, Any]:
        """
        执行 Agent（标准 LangGraph 调用方式）

        只需传入 query，其他状态由 LangGraph 通过 checkpointer 自动管理

        Args:
            query: 用户查询
            session_id: 会话 ID（用于会话隔离）

        Returns:
            包含 answer 和 feeling 的结果
        """
        self._log(f"=== 开始处理请求 ===")
        self._log(f"会话ID: {session_id}")
        self._log(f"用户查询: {query}")

        result = self._graph.invoke(
            {"query": query},
            config={"configurable": {"thread_id": session_id}}
        )

        self._log(f"=== 请求处理完成 ===")
        return {
            "answer": result.get("answer", ""),
            "feeling": result.get("feeling", {"feeling": "default", "score": 5})
        }

    def get_graph(self):
        """
        获取编译后的状态图

        Returns:
            编译后的图
        """
        return self._graph
