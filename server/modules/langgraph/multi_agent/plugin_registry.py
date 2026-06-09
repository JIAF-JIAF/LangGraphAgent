"""
插件注册表

核心职责：管理插件生命周期，并提供框架集成接口。
新增 Expert 只需：写插件类 → registry.register(plugin) → 框架自动完成图注册。

Manifest 驱动架构解决的硬编码问题：
1. graph.add_node / add_edge → register_graph_nodes()
2. CATEGORY_EXPERT_MAP → build_category_map()
3. PLANNER_DISPATCH_TARGETS → build_dispatch_targets()
4. DECOMPOSE_PROMPT 能力描述 → build_capability_descriptions()
5. 路由别名映射 → build_route_alias_map()
6. 默认回退类别 → get_default_fallback_category()
7. target 格式描述 → build_target_format_descriptions()
8. 类别选项 → build_category_options()
"""

from typing import Dict, Any, List, Optional
from modules.logger import log
from modules.langgraph.multi_agent.meta import ExpertMeta
from modules.langgraph.multi_agent.plugin_base import ExpertPlugin


class PluginRegistry:
    """
    插件注册表

    管理所有 ExpertPlugin 实例，提供框架集成接口。
    框架通过注册表动态获取节点、路由映射、能力描述等，
    新增 Expert 不需要修改任何框架代码。
    """

    def __init__(self):
        self._plugins: Dict[str, ExpertPlugin] = {}

    # ===== 注册 =====

    def register(self, plugin: ExpertPlugin) -> None:
        """
        注册插件

        Args:
            plugin: ExpertPlugin 实例
        """
        name = plugin.meta.name
        if name in self._plugins:
            log(f"[PluginRegistry] 插件已存在，覆盖: {name}", "Plugin")

        self._plugins[name] = plugin
        log(f"[PluginRegistry] 注册插件: {name} (category={plugin.meta.category})", "Plugin")

    def unregister(self, name: str) -> None:
        """
        注销插件

        Args:
            name: 插件名称
        """
        if name in self._plugins:
            self._plugins[name].on_deactivate()
            del self._plugins[name]
            log(f"[PluginRegistry] 注销插件: {name}", "Plugin")

    # ===== 生命周期 =====

    def activate_all(self, context: Dict[str, Any]) -> None:
        """
        激活所有插件

        Args:
            context: 共享资源上下文（ai_client, base_agent 等）
        """
        for plugin in self._plugins.values():
            plugin.on_activate(context)
            log(f"[PluginRegistry] 激活: {plugin.meta.name}", "Plugin")

    def register_intents(self, intent_registry: Any) -> int:
        """
        遍历所有插件，向意图注册表注册意图

        必须在 activate_all 之后调用，因为插件需要先创建资源
        （如 SkillManager、RAGWorkflow）才能知道有哪些意图可注册。

        Args:
            intent_registry: IntentRegistry 实例

        Returns:
            注册的意图总数
        """
        total = 0
        for plugin in self._plugins.values():
            count = plugin.register_intents(intent_registry)
            total += count
            if count > 0:
                log(f"[PluginRegistry] {plugin.meta.name} 注册 {count} 个意图", "Plugin")
        log(f"[PluginRegistry] 意图注册完成，共 {total} 个", "Plugin")
        return total

    # ===== 框架集成：图注册 =====

    def register_graph_nodes(self, graph) -> None:
        """
        将所有已注册插件自动注册为 LangGraph 节点，并连接边

        替代原 graph.py 中的硬编码：
          graph.add_node("mcp_expert", mcp_expert)
          graph.add_edge("mcp_expert", "planner_dispatch")
          ...

        Args:
            graph: StateGraph 实例
        """
        for name, plugin in self._plugins.items():
            # 注册节点：插件本身就是 callable（__call__ → execute）
            graph.add_node(name, plugin)
            # 连接边：Expert 执行后回到 planner_dispatch
            graph.add_edge(name, "planner_dispatch")
            log(f"[PluginRegistry] 图节点已注册: {name} → planner_dispatch", "Plugin")

    # ===== 框架集成：路由映射 =====

    def build_category_map(self) -> Dict[str, str]:
        """
        构建 category → expert_name 映射

        替代原 planner_decompose.py 中的硬编码：
          CATEGORY_EXPERT_MAP = {"mcp": "mcp_expert", "skill": "skill_expert", ...}

        同 category 多插件时取 priority 最高的。

        Returns:
            {"mcp": "mcp_expert", "skill": "skill_expert", ...}
        """
        category_map: Dict[str, str] = {}
        for plugin in self._plugins.values():
            cat = plugin.meta.category
            existing = category_map.get(cat)

            if existing is not None and plugin.meta.priority >= self._plugins[existing].meta.priority:
                continue

            category_map[cat] = plugin.meta.name
        return category_map

    def build_dispatch_targets(self) -> Dict[str, str]:
        """
        构建 planner_dispatch 条件路由目标映射

        替代原 graph.py 中的硬编码：
          PLANNER_DISPATCH_TARGETS = {
              "mcp_expert": "mcp_expert", "skill_expert": "skill_expert", ...
              "merge": "merge",
          }

        Returns:
            {"mcp_expert": "mcp_expert", ..., "merge": "merge"}
        """
        targets = {name: name for name in self._plugins}
        targets["merge"] = "merge"
        return targets

    # ===== 框架集成：Planner 能力描述 =====

    def build_executable_categories(self) -> set:
        """
        从已注册插件动态构建可执行意图类别集合

        替代原 models.py 中的硬编码：
          EXECUTABLE_CATEGORIES = {"mcp", "skill", "rag", "chat", "system"}

        新增 Expert 插件时，只要 meta.category 设置正确，
        此方法自动包含新类别，无需修改任何框架代码。

        Returns:
            {"mcp", "skill", "rag", "chat", ...}（由插件 meta.category 决定）
        """
        categories = set()
        for plugin in self._plugins.values():
            categories.add(plugin.meta.category)
        return categories

    def build_capability_descriptions(self) -> str:
        """
        生成所有插件的能力描述文本

        替代原 DECOMPOSE_PROMPT 中硬编码的：
          "- mcp: 外部工具调用。当前可用工具：{mcp_tools}"
          "- skill: 技能执行。当前可用技能：{skills}"
          ...

        Returns:
            能力描述文本，可直接插入 DECOMPOSE_PROMPT
        """
        lines = []
        seen_categories = set()

        for plugin in sorted(self._plugins.values(), key=lambda p: p.meta.priority):
            cat = plugin.meta.category
            if cat in seen_categories:
                continue

            lines.append(plugin.render_capability())
            seen_categories.add(cat)
        return "\n".join(lines)

    # ===== 框架集成：Manifest 驱动路由 =====

    def build_route_alias_map(self) -> Dict[str, str]:
        """
        构建路由别名映射

        从各插件的 Manifest routing.aliases 合并。
        替代硬编码的 if cat == "system": cat = "chat" 逻辑。

        Returns:
            {"system": "chat", ...}（别名 → 目标类别）
        """
        alias_map: Dict[str, str] = {}
        for plugin in self._plugins.values():
            for alias, target in plugin.manifest.routing.aliases.items():
                alias_map[alias] = target
        return alias_map

    def get_default_fallback_category(self) -> str:
        """
        获取默认回退类别

        从 Manifest routing.default_fallback=true 的插件获取。
        替代硬编码的 default "mcp" / "chat"。

        Returns:
            默认回退类别字符串，无则返回 "chat"
        """
        for plugin in self._plugins.values():
            if plugin.manifest.routing.default_fallback:
                return plugin.meta.category
        return "chat"

    def get_default_fallback_expert_name(self) -> str:
        """
        获取默认回退 Expert 名称

        Returns:
            默认回退 Expert 名称，无则返回 "chat_expert"
        """
        for plugin in self._plugins.values():
            if plugin.manifest.routing.default_fallback:
                return plugin.meta.name
        return "chat_expert"

    def build_target_format_descriptions(self) -> str:
        """
        构建 target 格式描述文本

        从各插件的 Manifest routing.target_format 生成，
        用于 DECOMPOSE_PROMPT 中的 targets 字段填写规则。

        替代硬编码的：
          "- skill 类别 → ["skill:技能ID"]"
          "- mcp 类别 → ["mcp:工具名"]"
          ...

        Returns:
            target 格式描述文本
        """
        lines = []
        seen_categories = set()

        for plugin in sorted(self._plugins.values(), key=lambda p: p.meta.priority):
            cat = plugin.meta.category
            if cat in seen_categories:
                continue

            target_format = plugin.manifest.routing.target_format
            if target_format:
                lines.append(f"- {cat} 类别 → [\"{target_format}\"]")
            else:
                lines.append(f"- {cat} 类别 → 留空 []")

            seen_categories.add(cat)

        return "\n".join(lines)

    def build_category_options(self) -> str:
        """
        构建类别选项文本

        从已注册插件的 category 动态生成，
        用于 DECOMPOSE_PROMPT 和 Pydantic Field 描述。

        替代硬编码的 "mcp/skill/rag/chat"。

        Returns:
            类别选项文本，如 "mcp、skill、rag 或 chat"
        """
        categories = sorted(self.build_executable_categories())
        if not categories:
            return "chat"

        if len(categories) == 1:
            return categories[0]

        return "、".join(categories[:-1]) + " 或 " + categories[-1]

    # ===== 查询 =====

    def get_plugin(self, name: str) -> Optional[ExpertPlugin]:
        """
        获取插件实例

        Args:
            name: 插件名称

        Returns:
            ExpertPlugin 实例，不存在返回 None
        """
        return self._plugins.get(name)

    def get_all_plugins(self) -> Dict[str, ExpertPlugin]:
        """获取所有插件"""
        return dict(self._plugins)
