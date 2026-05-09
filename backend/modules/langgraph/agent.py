"""
LangGraph Agent 实现

标准 LangGraph RAG 流程：
START → router → ┌── 需要检索 ──→ retrieve → generate → END
                  │
                  └── 不需要检索 ──→ call_model → END

采用 LangGraph 标准会话管理：
- 使用 Checkpointer 进行状态持久化
- 通过 thread_id 实现会话隔离
- 状态由 LangGraph 自动管理，无需手动维护 chat_history
"""

import time
from typing import Optional, Dict, Any, List, Literal
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage, AIMessage

from .state import AgentState
from .checkpoint import MemorySaver, BaseCheckpointSaver


class LangGraphAgent:
    """
    LangGraph Agent

    纯调度层：
    - 调用 RAGWorkflow 处理检索逻辑
    - 调用外部 Agent 处理对话（可替换）
    - 使用 Checkpointer 进行状态持久化（可替换）
    """

    def __init__(
        self,
        agent: Any = None,
        rag_workflow: Optional[Any] = None,
        checkpointer: Optional[Any] = None,
        verbose: bool = True
    ):
        """
        初始化 LangGraph Agent

        Args:
            agent: 外部 Agent 实例（可替换），需实现 invoke(query, session_id) 方法
            rag_workflow: RAGWorkflow 实例，用于处理检索逻辑（可替换）
            checkpointer: 检查点存储实例（可替换），默认为 MemorySaver。
                         支持 RedisSaver、SQLiteSaver 或自定义实现 BaseCheckpointSaver 接口的类
            verbose: 是否输出详细日志
        """
        self._agent = agent              # 可替换的 Agent
        self._rag_workflow = rag_workflow  # 可替换的 RAG
        self._verbose = verbose

        # 使用传入的 checkpointer，默认使用 MemorySaver
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

    def _update_chat_history(self, chat_history: List, query: str, answer: str) -> List:
        """
        更新对话历史（统一方法）

        Args:
            chat_history: 当前对话历史
            query: 用户查询
            answer: 回答内容

        Returns:
            更新后的对话历史
        """
        return chat_history + [
            HumanMessage(content=query),
            AIMessage(content=answer)
        ]

    def _router_node(self, state: AgentState) -> AgentState:
        """
        路由节点：判断是否需要检索

        Args:
            state: 当前状态（包含 query, session_id, chat_history）

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
        生成节点：基于检索结果生成回答

        Args:
            state: 当前状态（包含 query, documents, chat_history）

        Returns:
            更新后的状态（返回 answer 和更新后的 chat_history）
        """
        query = state["query"]
        documents = state.get("documents", [])
        chat_history = state.get("chat_history", [])

        self._log(f"[节点: generate] 开始执行文档数: {len(documents)}")

        # 调用 RAG 生成回答
        if self._rag_workflow:
            answer = self._rag_workflow.generate(query, documents)
        else:
            answer = "RAG 服务不可用，请稍后重试"

        self._log(f"[节点: generate] 生成完成: {answer[:50]}...")

        # 使用统一方法更新对话历史
        updated_chat_history = self._update_chat_history(chat_history, query, answer)
        return {"answer": answer, "chat_history": updated_chat_history}

    def _call_model_node(self, state: AgentState) -> AgentState:
        """
        调用模型节点：调用外部 Agent

        Args:
            state: 当前状态（包含 query, chat_history）

        Returns:
            更新后的状态（返回 answer 和更新后的 chat_history）
        """
        query = state["query"]
        chat_history = state.get("chat_history", [])

        self._log(f"[节点: call_model] 开始执行，对话历史长度: {len(chat_history)}")

        # 调用外部 Agent，传递对话历史
        if self._agent:
            result = self._agent.invoke(query, None, chat_history)
            answer = result.get("answer", "")
        else:
            answer = "Agent 服务不可用，请稍后重试"

        self._log(f"[节点: call_model] 执行完成: {answer[:50]}...")

        # 使用统一方法更新对话历史
        updated_chat_history = self._update_chat_history(chat_history, query, answer)
        return {"answer": answer, "chat_history": updated_chat_history}

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

    def _build_graph(self):
        """
        构建状态图

        节点：
        - router: 路由节点
        - retrieve: 检索节点
        - generate: 生成节点（基于检索结果）
        - call_model: 调用外部 Agent 节点
        """
        self._log("开始构建 LangGraph 状态图...")

        self._graph = StateGraph(AgentState)

        self._graph.add_node("router", self._router_node)
        self._graph.add_node("retrieve", self._retrieve_node)
        self._graph.add_node("generate", self._generate_node)
        self._graph.add_node("call_model", self._call_model_node)

        self._graph.add_edge(START, "router")

        self._graph.add_conditional_edges(
            "router",
            self._should_retrieve,
            {"retrieve": "retrieve", "call_model": "call_model"}
        )

        self._graph.add_edge("retrieve", "generate")
        self._graph.add_edge("generate", END)
        self._graph.add_edge("call_model", END)

        # 使用 MemorySaver 进行状态持久化
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
            包含 answer 的结果
        """
        self._log(f"=== 开始处理请求 ===")
        self._log(f"会话ID: {session_id}")
        self._log(f"用户查询: {query}")

        # 只需传入 query，LangGraph 自动从 checkpointer 恢复 chat_history
        # 节点返回值会自动合并到状态中（包含 chat_history 更新）
        result = self._graph.invoke(
            {"query": query},
            config={"configurable": {"thread_id": session_id}}
        )

        self._log(f"=== 请求处理完成 ===")
        return {"answer": result.get("answer", "")}

    def get_graph(self):
        """
        获取编译后的状态图

        Returns:
            编译后的图
        """
        return self._graph
