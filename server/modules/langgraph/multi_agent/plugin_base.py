"""
Expert 插件抽象基类

契约定义：插件必须提供 meta + execute，框架负责图注册、边连接、路由。
插件通过 meta.category 参与意图路由，通过 meta.name 作为图节点名。

Manifest 驱动架构：
  - 插件从 PLUGIN.yaml 加载 Manifest，自动生成 ExpertMeta
  - routing/prompt/intents 全部声明式，消除硬编码
  - 静态意图从 Manifest 自动注册，无需子类手写

新增 Expert 只需：
  1. 创建插件目录（含 PLUGIN.yaml + plugin.py）
  2. 继承 ExpertPlugin，传入 manifest
  3. registry.register(YourPlugin(manifest))
  4. 框架自动完成图注册、边连接、路由映射、能力描述

框架代码零改动。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from modules.langgraph.multi_agent.meta import ExpertMeta
from modules.langgraph.multi_agent.manifest import PluginManifest
from modules.langgraph.multi_agent.helpers import (
    push_step_event,
    invoke_agent_safely,
    build_intent_results,
    build_agent_result,
)
from modules.langgraph.context_builder import ContextBuilder
from modules.intent.intent_types import IntentCategory


class ExpertPlugin(ABC):
    """
    Expert 插件抽象基类

    Manifest 驱动架构：
      - 构造时传入 PluginManifest，自动生成 ExpertMeta
      - 静态意图从 Manifest 自动注册（register_intents 默认实现）
      - render_capability 使用 Manifest 的 capability_template

    框架通过以下方式与插件交互：
    1. on_activate(context)  → 注入共享资源，插件创建 Agent
    2. meta                  → 获取路由/注册信息（从 Manifest 自动生成）
    3. __call__(state)       → LangGraph 节点入口，委托给 execute()
    4. render_capability()   → Planner Prompt 中的能力描述（从 Manifest 模板生成）
    """

    def __init__(self, manifest: PluginManifest):
        """
        初始化插件

        Args:
            manifest: PluginManifest 实例，从 PLUGIN.yaml 加载
        """
        self._manifest = manifest
        self._meta = ExpertMeta(
            name=manifest.name,
            category=manifest.expert.category,
            description=manifest.description,
            version=manifest.version,
            priority=manifest.expert.priority,
            icon=manifest.expert.icon,
            label=manifest.expert.label or manifest.name,
        )

    @property
    def manifest(self) -> PluginManifest:
        """插件 Manifest"""
        return self._manifest

    @property
    def meta(self) -> ExpertMeta:
        """插件元信息（从 Manifest 自动生成）"""
        return self._meta

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

    def register_intents(self, intent_registry: Any) -> int:
        """
        向意图注册表注册本插件能处理的意图

        Manifest 驱动：自动注册 Manifest 中声明的静态意图。
        子类可覆写以注册动态意图（如从 MCP 工具列表注册），
        建议调用 super().register_intents() 保留静态意图注册。

        Args:
            intent_registry: IntentRegistry 实例

        Returns:
            注册的意图数量
        """
        count = 0
        for intent_def in self._manifest.intents.static:
            intent_type = intent_def.get("intent_type", "")
            if not intent_type:
                continue

            # 从 target 推断 category
            target = intent_def.get("target", "")
            category_str = self._infer_category_from_target(target)

            intent_registry.register_intent(
                intent_type=intent_type,
                category=category_str,
                description=intent_def.get("description", ""),
                target=target,
            )
            count += 1
        return count

    def _infer_category_from_target(self, target: str) -> IntentCategory:
        """
        从 target 推断意图类别（返回 IntentCategory 枚举）

        Args:
            target: 目标标识，如 "chat"、"system"、"mcp:get_weather"

        Returns:
            IntentCategory 枚举值
        """
        # 先确定 category 字符串
        if ":" in target:
            cat_str = target.split(":")[0]
        else:
            # 特殊映射：system → chat（由 Manifest routing.aliases 决定）
            alias = self._manifest.routing.aliases.get(target)
            if alias:
                cat_str = alias
            else:
                cat_str = self._manifest.expert.category

        # 映射为 IntentCategory 枚举
        try:
            return IntentCategory(cat_str)
        except ValueError:
            return IntentCategory.CHAT

    def render_capability(self) -> str:
        """
        渲染能力描述（用于 Planner DECOMPOSE_PROMPT）

        使用 Manifest 的 capability_template 模板，支持 {category}/{description} 占位符。
        子类可覆写提供更详细的能力清单（如动态工具列表）。

        Returns:
            能力描述文本
        """
        template = self._manifest.prompt.capability_template
        return template.format(
            category=self.meta.category,
            description=self.meta.description,
            tools="",  # 子类 render_capability 覆写时填充
        )

    # ===== 辅助方法（子类可复用）=====

    def _invoke_agent(self, agent, input_text: str, context, started_detail: str = "") -> str:
        """
        调用 Agent 并推送事件

        封装事件推送 + Agent 调用，子类只需传入 agent/input/context。

        Args:
            agent: Agent 实例
            input_text: 输入文本
            context: AgentContext 实例
            started_detail: started 事件的详情（可选，如"处理：查询天气"）

        Returns:
            Agent 回答文本
        """
        push_step_event(self.meta, "started", detail=started_detail)
        answer = invoke_agent_safely(agent, input_text, context)
        completed_detail = f"完成（{len(answer)} 字）" if answer else "完成"
        push_step_event(self.meta, "completed", detail=completed_detail)
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
