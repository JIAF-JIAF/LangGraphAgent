"""
意图注册表

动态管理意图类型，从可用工具（MCP + Skill + RAG）自动注册意图。
这是业界 2026 年的标准做法：意图类型不是硬编码，而是动态获取。
"""

from typing import Dict, List, Any, Optional
from langchain_core.tools import BaseTool

from .intent_types import Intent, IntentCategory, IntentConstants
from modules.logger import log


class IntentRegistry:
    """
    意图注册表
    
    动态管理意图类型：
    - 从 MCP 工具注册意图
    - 从 Skill 技能注册意图
    - 从 RAG 知识库注册意图
    
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
        """注册系统意图和聊天意图"""
        for intent_type, description in IntentConstants.SYSTEM_INTENTS.items():
            self._intents[intent_type] = {
                "type": intent_type,
                "category": IntentCategory.SYSTEM,
                "description": description,
                "target": "system",
                "examples": [],
            }
        
        for intent_type, description in IntentConstants.CHAT_INTENTS.items():
            self._intents[intent_type] = {
                "type": intent_type,
                "category": IntentCategory.CHAT,
                "description": description,
                "target": "chat",
                "examples": [],
            }
            log(f"注册 Chat 意图: {intent_type}", module="Intent.Registry")
    
    def register_from_mcp_tools(self, mcp_tools: List[BaseTool]) -> int:
        """
        从 MCP 工具注册意图
        
        Args:
            mcp_tools: MCP 工具列表
            
        Returns:
            注册的意图数量
        """
        count = 0
        for tool in mcp_tools:
            intent_type = f"mcp_{tool.name}"
            self._intents[intent_type] = {
                "type": intent_type,
                "category": IntentCategory.MCP,
                "tool_name": tool.name,
                "description": tool.description,
                "target": f"mcp:{tool.name}",
                "examples": [],
            }
            count += 1
            log(f"注册 MCP 意图: {intent_type}", module="Intent.Registry")
        
        log(f"从 MCP 工具注册 {count} 个意图", module="Intent.Registry")
        return count
    
    def register_from_skills(self, skills: List[Dict[str, Any]]) -> int:
        """
        从技能注册意图
        
        Args:
            skills: 技能列表
            
        Returns:
            注册的意图数量
        """
        count = 0
        for skill in skills:
            skill_name = skill.get("name", "")
            if not skill_name:
                continue
            
            intent_type = f"skill_{skill_name}"
            self._intents[intent_type] = {
                "type": intent_type,
                "category": IntentCategory.SKILL,
                "skill_name": skill_name,
                "description": skill.get("description", f"执行 {skill_name} 技能"),
                "target": f"skill:{skill_name}",
                "examples": skill.get("examples", []),
            }
            count += 1
            log(f"注册 Skill 意图: {intent_type}", module="Intent.Registry")
        
        log(f"从技能注册 {count} 个意图", module="Intent.Registry")
        return count
    
    def register_from_knowledge_bases(self, knowledge_bases: List[Dict[str, str]]) -> int:
        """
        从知识库注册意图
        
        Args:
            knowledge_bases: 知识库信息列表，每个元素包含 name 和 description
            
        Returns:
            注册的意图数量
        """
        count = 0
        for kb_info in knowledge_bases:
            kb_name = kb_info.get("name", "")
            if not kb_name:
                continue
            
            kb_description = kb_info.get("description", f"查询 {kb_name} 知识库")
            intent_type = f"rag_{kb_name}"
            self._intents[intent_type] = {
                "type": intent_type,
                "category": IntentCategory.RAG,
                "knowledge_base": kb_name,
                "description": kb_description,
                "target": f"knowledge_base:{kb_name}",
                "examples": [],
            }
            count += 1
            log(f"注册 RAG 意图: {intent_type} - {kb_description}", module="Intent.Registry")
        
        log(f"从知识库注册 {count} 个意图", module="Intent.Registry")
        return count
    
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
            category = intent_info.get("category", IntentCategory.SYSTEM)
            if category == IntentCategory.SYSTEM:
                continue
            
            description = intent_info.get("description", "")
            target = intent_info.get("target", "")
            lines.append(f"- {intent_type}: {description} (目标: {target})")
        
        return "\n".join(lines)
    
    def get_intent_count(self) -> int:
        """获取意图总数"""
        return len(self._intents)
    
    def clear(self):
        """清空所有意图（保留系统意图）"""
        self._intents.clear()
        self._register_system_intents()
        log("意图注册表已清空", module="Intent.Registry")
