"""
意图类型定义

定义意图对象和基础意图类型。
意图类型不是硬编码，而是从可用工具（MCP + Skill + RAG）动态获取。
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Set, Callable, Tuple


class IntentCategory(Enum):
    """
    意图类别枚举

    意图分为以下类别：
    - MCP: MCP 工具调用
    - SKILL: 技能执行
    - RAG: 知识库检索
    - CHAT: 简单对话（闲聊、问候、感谢、简单问答等，LLM 直接回答即可）
    - SYSTEM: 系统指令（帮助、退出等）
    - COMPLEX_PLAN: 复杂规划（需要拆分子任务、多步骤执行的需求，如创建应用、设计方案）
    """

    MCP = "mcp"
    SKILL = "skill"
    RAG = "rag"
    CHAT = "chat"
    SYSTEM = "system"
    COMPLEX_PLAN = "complex_plan"


@dataclass
class Intent:
    """
    意图对象
    
    表示用户请求中的一个独立意图。
    
    Attributes:
        type: 意图类型（如 mcp_weather, skill_drawio, rag_exams）
        category: 意图类别
        content: 意图具体内容
        target: 目标处理器（如 skill:drawio-skill, knowledge_base:exams）
        order: 执行顺序（从1开始）
        confidence: 置信度（0-1）
        metadata: 额外元数据
    """
    
    type: str
    category: IntentCategory
    content: str
    target: str
    order: int
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type,
            "category": self.category.value,
            "content": self.content,
            "target": self.target,
            "order": self.order,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Intent":
        """从字典创建"""
        return cls(
            type=data["type"],
            category=IntentCategory(data.get("category", "system")),
            content=data["content"],
            target=data.get("target", ""),
            order=data["order"],
            confidence=data.get("confidence", 1.0),
            metadata=data.get("metadata", {}),
        )
    
    def get_handler_node(self) -> str:
        """
        获取处理该意图的 LangGraph 节点名称
        
        Returns:
            节点名称
        """
        if self.category == IntentCategory.RAG:
            return "retrieve"
        elif self.category == IntentCategory.SKILL:
            return "skill_executor"
        elif self.category == IntentCategory.MCP:
            return "mcp_executor"
        else:
            return "call_model"


class IntentConstants:
    """意图相关常量"""
    
    MULTI_INTENT_CONNECTORS = [
        "先", "再", "然后", "接着", "之后", "同时",
        "首先", "其次", "最后", "并且", "以及", "另外",
    ]
    
    SYSTEM_INTENTS = {
        "system_help": "帮助",
        "system_exit": "退出",
        "system_confirm": "确认",
        "system_cancel": "取消",
    }
    
    CHAT_INTENTS = {
        "general_chat": "通用对话，处理闲聊、问候、感谢等日常对话",
    }
    
    PLAN_INTENTS = {
        "complex_plan": "复杂规划，需要拆分子任务、多步骤执行的需求（如创建应用、设计方案）",
    }

    EXECUTABLE_CATEGORIES: Set["IntentCategory"] = {
        IntentCategory.MCP,
        IntentCategory.SKILL,
        IntentCategory.RAG,
    }

    DIALOG_CATEGORIES: Set["IntentCategory"] = {
        IntentCategory.CHAT,
        IntentCategory.SYSTEM,
    }

    COMPLEX_CATEGORIES: Set["IntentCategory"] = {
        IntentCategory.COMPLEX_PLAN,
    }

    SIMPLE_CATEGORIES = EXECUTABLE_CATEGORIES


def classify_intents(intents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    分类意图集合（单一真相源）

    所有路由逻辑（Supervisor、旧 IntentRouter、edges）统一调用此函数，
    新增类别只需修改 IntentConstants 的 category groups，无需改路由代码。

    Args:
        intents: 意图列表（来自 state["intents"]，每项为 dict 含 "category" 键）

    Returns:
        {
            "categories": Set[IntentCategory],        # 已识别的类别集合
            "unknown_categories": Set[str],           # 无法识别的原始 category 字符串
            "has_complex": bool,                      # 是否有复杂意图（含未知类别）
            "has_executable": bool,                   # 是否有可执行意图（mcp/skill/rag）
            "has_dialog": bool,                       # 是否有对话意图（chat/system）
        }
    """
    categories: Set[IntentCategory] = set()
    unknown_categories: Set[str] = set()

    for intent_data in intents:
        category_str = intent_data.get("category", "chat")
        try:
            categories.add(IntentCategory(category_str))
        except ValueError:
            unknown_categories.add(category_str)

    return {
        "categories": categories,
        "unknown_categories": unknown_categories,
        "has_complex": bool(categories & IntentConstants.COMPLEX_CATEGORIES) or bool(unknown_categories),
        "has_executable": bool(categories & IntentConstants.EXECUTABLE_CATEGORIES),
        "has_dialog": bool(categories & IntentConstants.DIALOG_CATEGORIES),
    }


@dataclass(frozen=True)
class RouteRule:
    """
    声明式路由规则

    一条规则 = 条件谓词 + 目标 + 描述模板。
    resolve_route 按表顺序遍历，第一个 condition 为 True 的规则命中。

    Attributes:
        condition: 输入 classify_intents 结果，返回是否命中
        target: 命中时返回的路由目标
        label: 日志描述模板，可用 {cat_names} / {exec_names} / {complex_names} 占位
    """

    condition: Callable[[Dict[str, Any]], bool]
    target: str
    label: str


def _format_route_detail(info: Dict[str, Any], label: str) -> str:
    """格式化路由描述，替换占位符"""
    categories = info["categories"]
    cat_names = ", ".join(sorted(c.value for c in categories))

    exec_cats = categories & IntentConstants.EXECUTABLE_CATEGORIES
    complex_cats = categories & IntentConstants.COMPLEX_CATEGORIES

    return label.format(
        cat_names=cat_names,
        exec_names=", ".join(sorted(c.value for c in exec_cats)) if exec_cats else "无",
        complex_names=", ".join(sorted(c.value for c in complex_cats)) if complex_cats else "未知",
    )


def resolve_route(
    info: Dict[str, Any],
    rules: List[RouteRule],
    fallback: str,
    fallback_label: str = "",
) -> Tuple[str, str]:
    """
    按优先级遍历路由表，返回 (target, detail)

    第一个 condition(info) 为 True 的规则命中，否则走 fallback。
    路由优先级完全由路由表的声明顺序决定，无需 if/else。

    Args:
        info: classify_intents 的返回值
        rules: 路由规则表（按优先级从高到低排列）
        fallback: 无规则命中时的兜底目标
        fallback_label: 兜底时的描述（可选）

    Returns:
        (target, detail) 元组
    """
    for rule in rules:
        if rule.condition(info):
            detail = _format_route_detail(info, rule.label)
            return rule.target, detail

    return fallback, fallback_label


SUPERVISOR_ROUTE_TABLE: List[RouteRule] = [
    # 统一路由：所有意图均走 planner_decompose
    # Planner 内部区分处理：
    #   - 可执行意图（mcp/skill/rag/chat/system）→ 直接构建子任务，不调 LLM，单波次完成
    #   - complex_plan 意图 → LLM 独立分解，保留完整规划能力
    #   - 混合意图 → 可执行直接构建 + complex_plan LLM 分解，合并后波次调度
    RouteRule(
        condition=lambda i: True,
        target="planner_expert",
        label="统一路由 → planner_expert（类别: {cat_names}）",
    ),
]

