"""
工具管理器模块

提供统一的工具注册和获取接口，整合：
- MCP 工具（从 mcp 模块获取）
- 技能工具（从 skill 模块获取）

设计目的：
- 解耦工具注册逻辑，便于维护和扩展
- 提供独立的 API 供其他模块调用
- 统一管理所有工具的生命周期
"""

from typing import List, Any, Optional

from langchain_core.tools import BaseTool

from modules.skill import SkillManager
from modules.logger import log
from modules.mcp import MCPToolService


class ToolManager:
    """
    工具管理器

    统一管理 MCP 工具和技能工具的获取与合并。
    """

    def __init__(self, llm_client: Optional[Any] = None):
        """
        初始化工具管理器

        Args:
            llm_client: LLM 客户端（用于初始化技能管理器）
        """
        self._llm_client = llm_client
        self._skill_manager = None
        self._cached_tools = None

    def _init_skill_manager(self):
        """延迟初始化技能管理器"""
        if self._skill_manager is None and self._llm_client is not None:
            self._skill_manager = SkillManager(llm_client=self._llm_client)

    def get_mcp_tools(self) -> List[BaseTool]:
        """
        获取所有 MCP 工具

        Returns:
            List[BaseTool]: MCP 工具列表
        """
        return MCPToolService.get_tools()

    def get_skill_tools(self) -> List[BaseTool]:
        """
        获取所有技能工具

        Returns:
            List[BaseTool]: 技能工具列表（skill_list, skill_instructions, skill_reference, skill_run_script）
        """
        self._init_skill_manager()
        if self._skill_manager:
            return self._skill_manager.get_tools()
        return []

    def get_all_tools(self) -> List[BaseTool]:
        """
        获取所有工具（MCP 工具 + 技能工具）

        Returns:
            List[BaseTool]: 合并后的工具列表
        """
        if self._cached_tools is not None:
            return self._cached_tools

        mcp_tools = self.get_mcp_tools()
        skill_tools = self.get_skill_tools()

        # 合并工具列表（MCP 工具在前，技能工具在后）
        self._cached_tools = mcp_tools + skill_tools

        return self._cached_tools

    def reload(self) -> None:
        """
        重新加载所有工具

        清除缓存，下次调用 get_all_tools() 时重新获取
        """
        self._cached_tools = None
        if self._skill_manager:
            self._skill_manager.reload()

    @property
    def tool_count(self) -> int:
        """
        获取工具总数

        Returns:
            int: 工具数量
        """
        return len(self.get_all_tools())

    @property
    def mcp_tool_count(self) -> int:
        """
        获取 MCP 工具数量

        Returns:
            int: MCP 工具数量
        """
        return len(self.get_mcp_tools())

    @property
    def skill_tool_count(self) -> int:
        """
        获取技能工具数量

        Returns:
            int: 技能工具数量
        """
        return len(self.get_skill_tools())


__all__ = ["ToolManager"]
