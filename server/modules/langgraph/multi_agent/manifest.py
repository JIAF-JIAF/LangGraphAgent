"""
PLUGIN.yaml Manifest 解析器

从每个插件目录的 PLUGIN.yaml 加载声明式配置，
生成 PluginManifest 数据类，驱动 ExpertMeta / 路由 / Prompt 等运行时行为。

对齐 agentskills.io 开放标准：
  - name / description / version 为必填字段
  - expert / routing / intents / prompt 为 Expert Agent 专属扩展

新增 Expert 只需：
  1. 在插件目录创建 PLUGIN.yaml
  2. 写 plugin.py 继承 ExpertPlugin
  3. 框架自动加载 Manifest → 生成 ExpertMeta → 注册路由/意图/Prompt
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

import yaml
from modules.logger import log


# ==================== Manifest 数据类 ====================


@dataclass
class RoutingConfig:
    """
    路由声明配置

    消除硬编码：target 格式、前缀、别名映射、默认回退

    Attributes:
        target_format: targets 字段格式描述，如 "mcp:{tool_name}"
        target_prefix: 意图 target 前缀，如 "mcp:"、"skill:"、"knowledge_base:"
        aliases: 路由别名映射，如 {"system": "chat"} 表示 system 意图路由到 chat Expert
        default_fallback: 是否为默认回退 Expert（无匹配时兜底）
    """
    target_format: str = ""
    target_prefix: str = ""
    aliases: Dict[str, str] = field(default_factory=dict)
    default_fallback: bool = False


@dataclass
class IntentConfig:
    """
    意图声明配置

    消除硬编码：意图发现方式（动态/静态）

    Attributes:
        dynamic: 运行时动态发现意图（如从 MCP 工具列表、技能列表）
        static: 静态意图列表，如 [{"intent_type": "general_chat", "description": "通用对话", "target": "chat"}]
    """
    dynamic: bool = False
    static: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class PromptConfig:
    """
    Prompt 模板配置

    消除硬编码：capability 描述模板、单/多意图提示模板

    Attributes:
        capability_template: 能力描述模板，支持 {category}/{description}/{tools} 占位符
        single_hint: 单意图提示模板，支持 {target} 占位符
        multi_hint: 多意图提示前缀
    """
    capability_template: str = "{category}: {description}"
    single_hint: str = ""
    multi_hint: str = ""


@dataclass
class ExpertConfig:
    """
    Expert Agent 专属配置

    Attributes:
        category: 意图类别，Planner 路由用
        icon: SSE 事件图标
        label: SSE 事件显示名
        priority: 同 category 多插件时的优先级（越小越优先）
    """
    category: str = ""
    icon: str = "⚡"
    label: str = ""
    priority: int = 100


@dataclass
class PluginManifest:
    """
    插件 Manifest（PLUGIN.yaml 的 Python 表示）

    对齐 agentskills.io 必填字段 + Expert Agent 专属扩展

    Attributes:
        name: Agent 唯一名称（对齐 agentskills.io），同时作为 LangGraph 节点名
        description: 功能描述 + 触发场景（对齐 agentskills.io）
        version: 版本号（对齐 agentskills.io）
        expert: Expert Agent 专属配置
        routing: 路由声明配置
        intents: 意图声明配置
        prompt: Prompt 模板配置
    """
    name: str
    description: str
    version: str = "1.0.0"
    expert: ExpertConfig = field(default_factory=ExpertConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    intents: IntentConfig = field(default_factory=IntentConfig)
    prompt: PromptConfig = field(default_factory=PromptConfig)

    def __post_init__(self):
        """从 expert.category 自动填充 name 的默认 category"""
        if self.expert.category and not self.expert.label:
            self.expert.label = self.name


# ==================== YAML 解析 ====================


def load_manifest(plugin_dir: str) -> Optional[PluginManifest]:
    """
    从插件目录加载 PLUGIN.yaml

    Args:
        plugin_dir: 插件目录绝对路径

    Returns:
        PluginManifest 实例，文件不存在或解析失败返回 None
    """
    yaml_path = os.path.join(plugin_dir, "PLUGIN.yaml")

    if not os.path.exists(yaml_path):
        log(f"[Manifest] PLUGIN.yaml 不存在: {yaml_path}", "Plugin")
        return None

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or not isinstance(data, dict):
            log(f"[Manifest] PLUGIN.yaml 格式无效: {yaml_path}", "Plugin")
            return None

        manifest = _parse_manifest(data)
        log(f"[Manifest] 加载成功: {manifest.name} (category={manifest.expert.category})", "Plugin")
        return manifest

    except Exception as e:
        log(f"[Manifest] 加载失败 {yaml_path}: {e}", "Plugin")
        return None


def _parse_manifest(data: Dict[str, Any]) -> PluginManifest:
    """
    解析 YAML 字典为 PluginManifest

    Args:
        data: YAML 解析后的字典

    Returns:
        PluginManifest 实例
    """
    expert_data = data.get("expert", {})
    routing_data = data.get("routing", {})
    intents_data = data.get("intents", {})
    prompt_data = data.get("prompt", {})

    return PluginManifest(
        name=data.get("name", ""),
        description=data.get("description", ""),
        version=data.get("version", "1.0.0"),
        expert=ExpertConfig(
            category=expert_data.get("category", ""),
            icon=expert_data.get("icon", "⚡"),
            label=expert_data.get("label", ""),
            priority=expert_data.get("priority", 100),
        ),
        routing=RoutingConfig(
            target_format=routing_data.get("target_format", ""),
            target_prefix=routing_data.get("target_prefix", ""),
            aliases=routing_data.get("aliases", {}),
            default_fallback=routing_data.get("default_fallback", False),
        ),
        intents=IntentConfig(
            dynamic=intents_data.get("dynamic", False),
            static=intents_data.get("static", []),
        ),
        prompt=PromptConfig(
            capability_template=prompt_data.get("capability_template", "{category}: {description}"),
            single_hint=prompt_data.get("single_hint", ""),
            multi_hint=prompt_data.get("multi_hint", ""),
        ),
    )
