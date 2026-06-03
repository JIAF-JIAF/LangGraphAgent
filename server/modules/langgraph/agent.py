"""
LangGraph Agent - 主入口

职责：
- 初始化组件
- 编译状态图
- 提供统一调用接口

架构设计：
- agent.py：只负责流程编排（不再包含节点定义）
- nodes/：节点定义模块（单一职责）
- edges.py：条件路由函数
- graph.py：图构建器
- context_builder.py：上下文构建
- task_generators/：任务生成策略
"""

from typing import Optional, Dict, Any
from modules.logger import log
from .states import AgentState
from .executors import ExecutorRegistry
from .refiners import RefinerRegistry
from .graph import GraphBuilder
from .multi_agent import is_multi_agent_enabled
from .multi_agent.graph import MultiAgentGraphBuilder


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
        ai_client: Any = None,
        skill_manager: Any = None,
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
            ai_client: AI 客户端实例（用于 ExpertAgentFactory 创建领域专精 Agent）
            skill_manager: 技能管理器实例（用于 ExpertAgentFactory 获取技能工具）
        """
        self._agent = agent
        self._rag_workflow = rag_workflow
        self._checkpointer = checkpointer
        self._feeling_detector = feeling_detector
        self._task_planner = task_planner
        self._intent_router = intent_router
        self._verbose = verbose
        self._ai_client = ai_client
        self._skill_manager = skill_manager
        self._graph = None
        
        # 构建精炼器（用于最终回答的润色处理）
        self._refiners = RefinerRegistry.build_all()
        # 构建执行器（用于各类意图的直接执行）
        self._executors = ExecutorRegistry.build_all(
            rag_workflow=rag_workflow,
            agent=agent,
        )

        # 构建图
        self._build_graph()

    def _build_graph(self):
        """构建状态图（支持 Feature Flag 切换）"""
        if is_multi_agent_enabled():
            builder = MultiAgentGraphBuilder(
                feeling_detector=self._feeling_detector,
                intent_router=self._intent_router,
                agent=self._agent,
                refiners=self._refiners,
                rag_workflow=self._rag_workflow,
                task_planner=self._task_planner,
                executors=self._executors,
                ai_client=self._ai_client,
                skill_manager=self._skill_manager,
            )
            self._graph = builder.build()
            self._graph = self._graph.compile(checkpointer=self._checkpointer)
            log("LangGraph 多 Agent 状态图构建完成（混合架构）", "LangGraph")
        else:
            builder = GraphBuilder(
                feeling_detector=self._feeling_detector,
                intent_router=self._intent_router,
                rag_workflow=self._rag_workflow,
                task_planner=self._task_planner,
                agent=self._agent,
                executors=self._executors,
                refiners=self._refiners,
            )
            self._graph = builder.build()
            self._graph = self._graph.compile(checkpointer=self._checkpointer)
            log("LangGraph 状态图构建完成", "LangGraph")

    def invoke(self, query: str, session_id: str = "default", uid: Optional[str] = None) -> Dict[str, Any]:
        """
        执行 Agent（LangGraph 1.0+ 官方标准调用方式）
        无论是否有历史，永远只传增量！

        Args:
            query: 用户查询
            session_id: 会话 ID
            uid: 用户 ID
        """
        log(f"=== 开始处理请求 ===", "LangGraph")
        log(f"会话ID: {session_id}", "LangGraph")
        log(f"用户ID: {uid}", "LangGraph")
        log(f"用户查询: {query}", "LangGraph")

        # 正确：永远只传增量！
        # LangGraph 会自动从 Checkpointer 恢复历史状态
        input_state = {
            "query": query,
            "session_id": session_id,
            "uid": uid,
        }

        log(f"传入增量状态: {list(input_state.keys())}", "LangGraph")

        # 调用 LangGraph
        result = self._graph.invoke(
            input_state,
            config={"configurable": {"thread_id": session_id}}
        )

        log(f"=== 请求处理完成 ===", "LangGraph")
        return {
            "answer": result["answer"],
            "feeling": result["feeling"],
        }

    def stream(self, query: str, session_id: str = "default", uid: Optional[str] = None):
        """
        流式执行 Agent，对齐 AG-UI 协议

        使用多流模式同时获取：
        - updates: 节点完成事件（用于展示思考步骤）
        - custom: 节点内部自定义进度事件（通过 get_stream_writer 推送）
        - messages: LLM 逐 token 输出（用于打字机效果）

        Args:
            query: 用户查询
            session_id: 会话 ID
            uid: 用户 ID

        Yields:
            Tuple[str, Any]: (mode, chunk) 元组
                mode="updates" 时 chunk 为 {node_name: state_delta}
                mode="custom" 时 chunk 为自定义事件字典
                mode="messages" 时 chunk 为 (AIMessageChunk, metadata) 元组
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

        for mode, chunk in self._graph.stream(
            input_state,
            config,
            stream_mode=["updates", "custom", "messages"],
        ):
            yield (mode, chunk)

        log(f"=== 流式处理完成 ===", "LangGraph")

    def get_graph(self):
        """
        获取编译后的状态图

        Returns:
            编译后的 StateGraph 对象
        """
        return self._graph
