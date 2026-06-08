"""
意图注册表

动态管理意图类型。所有意图均由插件或框架注册，无硬编码。

插件化架构：
  - 业务意图：由插件在 register_intents() 中调用 registry.register_intent() 注册
  - 系统意图：由 ChatPlugin 统一注册（chat + system 意图）
  - 框架意图：complex_plan 由 IntentRegistry 初始化时注册（框架级调度意图）
  - 新增 Expert 只需在插件中实现 register_intents()，框架零改动
"""

from typing import Dict, List, Any, Optional

from .intent_types import Intent, IntentCategory, IntentConstants
from modules.logger import log


class IntentRegistry:
    """
    意图注册表

    动态管理意图类型：
    - 框架意图：complex_plan（初始化时自动注册，框架级调度意图）
    - 业务意图：由插件通过 register_intent() 注册（mcp/skill/rag 等）
    - 对话意图：由 ChatPlugin 统一注册（chat + system 意图）

    意图类型命名规范：
    - MCP 工具：mcp_{tool_name}（如 mcp_weather, mcp_dingtalk）
    - Skill 技能：skill_{skill_name}（如 skill_drawio, skill_analysis）
    - RAG 知识库：rag_{kb_name}（如 rag_exams, rag_politics）
    """

    def __init__(self):
        self._intents: Dict[str, Dict[str, Any]] = {}
        self._register_system_intents()
        log("意图注册表初始化完成", module="Intent.Registry")

    def _register_system_intents(self):
        """注册框架级意图（complex_plan），chat 和 system 意图由 ChatPlugin 注册"""
        for intent_type, description in IntentConstants.PLAN_INTENTS.items():
            self._intents[intent_type] = {
                "type": intent_type,
                "category": IntentCategory.COMPLEX_PLAN,
                "description": description,
                "target": "complex_plan",
                "examples": [],
            }
            log(f"注册 ComplexPlan 意图: {intent_type}", module="Intent.Registry")

    # ===== 通用注册接口（插件调用） =====

    def register_intent(
        self,
        intent_type: str,
        category: IntentCategory,
        description: str,
        target: str,
        **kwargs,
    ) -> None:
        """
        注册单个意图（通用接口，供插件调用）

        Args:
            intent_type: 意图类型标识（如 mcp_get_weather, skill_drawio-skill）
            category: 意图类别（IntentCategory 枚举）
            description: 意图描述（用于 LLM Prompt）
            target: 目标处理器标识（如 mcp:get_weather, skill:drawio-skill）
            **kwargs: 额外元数据（如 tool_name, skill_name, knowledge_base 等）
        """
        self._intents[intent_type] = {
            "type": intent_type,
            "category": category,
            "description": description,
            "target": target,
            "examples": kwargs.pop("examples", []),
            **kwargs,
        }
        log(f"注册意图: {intent_type} ({category.value})", module="Intent.Registry")

    # ===== 查询接口 =====

    def get_intent(self, intent_type: str) -> Optional[Dict[str, Any]]:
        """
        获取意图信息

        Args:
            intent_type: 意图类型

        Returns:
            意图信息，不存在返回 None
        """
        return self._intents.get(intent_type)

    def get_all_intents(self) -> Dict[str, Dict[str, Any]]:
        """获取所有意图类型"""
        return self._intents

    def get_intents_by_category(self, category: IntentCategory) -> Dict[str, Dict[str, Any]]:
        """
        按类别获取意图

        Args:
            category: 意图类别

        Returns:
            该类别的意图字典
        """
        return {
            k: v for k, v in self._intents.items()
            if v.get("category") == category
        }

    def get_intent_examples(self) -> List[Dict[str, str]]:
        """
        获取所有意图示例（用于 L2 向量匹配）

        Returns:
            示例列表，每个示例包含 intent 和 text
        """
        examples = []
        for intent_type, intent_info in self._intents.items():
            for example in intent_info.get("examples", []):
                examples.append({
                    "intent": intent_type,
                    "text": example,
                })
        return examples

    def get_intent_descriptions(self) -> str:
        """
        获取所有意图的描述文本（用于 LLM Prompt）

        Returns:
            格式化的意图描述
        """
        lines = []
        for intent_type, intent_info in self._intents.items():
            description = intent_info.get("description", "")
            target = intent_info.get("target", "")
            lines.append(f"- {intent_type}: {description} (目标: {target})")

        return "\n".join(lines)

    def get_intent_count(self) -> int:
        """获取意图总数"""
        return len(self._intents)

    def clear(self):
        """清空所有意图（保留框架级意图 complex_plan）"""
        self._intents.clear()
        self._register_system_intents()
        log("意图注册表已清空", module="Intent.Registry")
