"""
Expert 插件元信息数据类
"""

from dataclasses import dataclass


@dataclass
class ExpertMeta:
    """
    插件元信息

    框架根据这些字段自动完成：
    - name → graph.add_node(name, plugin) + graph.add_edge(name, "planner_dispatch")
    - category → CATEGORY_EXPERT_MAP 映射（Planner 路由用）
    - name → PLANNER_DISPATCH_TARGETS 路由目标
    - render_capability() → DECOMPOSE_PROMPT 能力描述
    - icon/label → SSE 事件展示

    Attributes:
        name: 插件唯一名称，同时作为 LangGraph 节点名。如 "mcp_expert"
        category: 意图类别，Planner 据此路由子任务到 Expert。如 "mcp"
        description: 功能描述，用于日志和 render_capability()
        version: 版本号
        priority: 同 category 多插件时的优先级（越小越优先）
        icon: SSE 事件图标
        label: SSE 事件显示名
    """
    name: str
    category: str
    description: str
    version: str = "1.0.0"
    priority: int = 100
    icon: str = "⚡"
    label: str = ""

    def __post_init__(self):
        if not self.label:
            self.label = self.name