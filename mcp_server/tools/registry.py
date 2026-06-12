"""
工具注册中心
提供统一的工具定义规范和注册机制
"""

from typing import Callable, Dict, Any, List, Optional


class ToolParameter:
    """工具参数定义"""
    def __init__(self, name: str, type: str = "string", 
                 description: str = "", required: bool = True):
        self.name = name
        self.type = type
        self.description = description
        self.required = required


class ToolDefinition:
    """工具定义规范"""
    def __init__(self, name: str, description: str, func: Callable,
                 parameters: List[ToolParameter] = None, return_type: str = "string"):
        self.name = name
        self.description = description
        self.func = func
        self.parameters = parameters if parameters else []
        self.return_type = return_type


_TOOL_REGISTRY: Dict[str, ToolDefinition] = {}


def register_tool(name: str, description: str, 
                  parameters: Optional[List[Dict[str, Any]]] = None, 
                  return_type: str = "string"):
    """工具注册装饰器"""
    def decorator(func: Callable) -> Callable:
        tool_params = []
        if parameters:
            for param in parameters:
                tool_params.append(ToolParameter(
                    name=param.get('name', ''),
                    type=param.get('type', 'string'),
                    description=param.get('description', ''),
                    required=param.get('required', True)
                ))
        
        tool_def = ToolDefinition(
            name=name,
            description=description,
            func=func,
            parameters=tool_params,
            return_type=return_type
        )
        _TOOL_REGISTRY[name] = tool_def
        return func
    return decorator


def get_registered_tools() -> List[ToolDefinition]:
    """获取所有已注册的工具"""
    return list(_TOOL_REGISTRY.values())


def get_tool(name: str) -> Optional[ToolDefinition]:
    """获取指定工具"""
    return _TOOL_REGISTRY.get(name)


def clear_registry():
    """清空注册表"""
    _TOOL_REGISTRY.clear()


__all__ = [
    'ToolDefinition',
    'register_tool',
    'get_registered_tools',
    'get_tool',
    'clear_registry'
]