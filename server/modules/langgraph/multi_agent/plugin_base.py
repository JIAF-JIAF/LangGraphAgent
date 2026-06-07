"""
Expert 插件抽象基类

契约定义：插件必须提供 meta + execute，框架负责图注册、边连接、路由。
插件通过 meta.category 参与意图路由，通过 meta.name 作为图节点名。

新增 Expert 只需：
  1. 继承 ExpertPlugin，实现 meta + execute
  2. registry.register(YourPlugin())
  3. 框架自动完成图注册、边连接、路由映射、能力描述

框架代码零改动。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from modules.langgraph.multi_agent.meta import ExpertMeta
from modules.langgraph.multi_agent.helpers import (
    push_step_event,
    invoke_agent_safely,
    build_intent_results,
    build_agent_result,
)
from modules.langgraph.context_builder import ContextBuilder


class ExpertPlugin(ABC):
    """
    Expert 插件抽象基类

    框架通过以下方式与插件交互：
    1. on_activate(context)  → 注入共享资源，插件创建 Agent
    2. meta                  → 获取路由/注册信息
    3. __call__(state)       → LangGraph 节点入口，委托给 execute()
    4. render_capability()   → Planner Prompt 中的能力描述
    """

    @property
    @abstractmethod
    def meta(self) -> ExpertMeta:
        """插件元信息"""
        pass

    @abstractmethod
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行插件逻辑

        Args:
            state: LangGraph 状态（query, intents, __subtask_idx__ 等）

        Returns:
            状态更新字典，必须包含 "agent_results"
        """
        pass

    def on_activate(self, context: Dict[str, Any]):
        """
        激活回调，框架注入共享资源

        context 包含：ai_client, rag_workflow, skill_manager, base_agent 等
        插件在此创建 Agent、加载工具等。
        """
        pass

    def on_deactivate(self):
        """停用回调，释放资源"""
        pass

    def render_capability(self) -> str:
        """
        渲染能力描述（用于 Planner DECOMPOSE_PROMPT）

        默认返回 "- {category}: {description}"
        子类可覆写提供更详细的能力清单

        Returns:
            能力描述文本，如 "mcp: 外部工具调用。当前可用工具：weather, dingtalk"
        """
        return f"- {self.meta.category}: {self.meta.description}"

    # ===== 辅助方法（子类可复用）=====

    def _invoke_agent(self, agent, input_text: str, context) -> str:
        """
        调用 Agent 并推送事件

        封装事件推送 + Agent 调用，子类只需传入 agent/input/context。

        Args:
            agent: Agent 实例
            input_text: 输入文本
            context: AgentContext 实例

        Returns:
            Agent 回答文本
        """
        push_step_event(self.meta, "started")
        answer = invoke_agent_safely(agent, input_text, context)
        push_step_event(self.meta, "completed")
        return answer

    def _build_result(
        self,
        answer: str,
        state: Dict[str, Any],
        *,
        intent_results: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        构建标准状态更新字典

        自动从 state 提取 subtask_idx 和 query，自动构建 chat_history，
        自动填充 self.meta.name。插件只需传入 answer 和 intent_results。

        Args:
            answer: Agent 回答
            state: LangGraph 状态（自动提取 __subtask_idx__ 和 query）
            intent_results: 意图结果列表（插件自行构建）

        Returns:
            状态更新字典
        """
        subtask_idx = state.get("__subtask_idx__")
        query = state.get("query", "")
        chat_history = ContextBuilder.build_chat_history(query, answer) if query else None

        return build_agent_result(
            self.meta.name, 
            answer, 
            intent_results, 
            subtask_idx, 
            chat_history
        )

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph 节点入口

        框架通过 graph.add_node(name, plugin) 注册插件为节点，
        LangGraph 调用节点时执行此方法，委托给 execute()。

        Args:
            state: LangGraph 状态（query, intents, __subtask_idx__ 等）

        Returns:
            状态更新字典，由 execute() 返回
        """
        return self.execute(state)
