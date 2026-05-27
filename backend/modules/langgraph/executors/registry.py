"""
执行器注册表（工厂模式）

管理所有意图执行器，支持注册和构建。
"""

from typing import Dict, Type, Any, List, Optional
from modules.logger import log
from .base import BaseExecutor, ExecutionResult


class ExecutorRegistry:
    """
    执行器注册表（工厂类）
    
    管理所有执行器类，新的执行器通过 ExecutorRegistry.register() 注册。
    """

    _executors: Dict[str, Type[BaseExecutor]] = {}

    @classmethod
    def register(cls, category: str, executor_class: Type[BaseExecutor]) -> None:
        """
        注册执行器类
        
        Args:
            category: 意图类别，如 "rag"、"skill"、"mcp"
            executor_class: 继承自 BaseExecutor 的执行器类
        """
        cls._executors[category.lower()] = executor_class
        log(f"[ExecutorRegistry] 注册执行器: {category}", "Executor")

    @classmethod
    def build(cls, category: str, **kwargs) -> BaseExecutor:
        """
        构建执行器实例
        
        Args:
            category: 意图类别
            **kwargs: 传递给执行器的初始化参数
            
        Returns:
            执行器实例
            
        Raises:
            ValueError: 如果执行器类型不支持
        """
        executor_class = cls._executors.get(category.lower())
        if executor_class is None:
            supported = ", ".join(cls._executors.keys())
            raise ValueError(f"不支持的执行器类型: {category}，支持的类型: {supported}")
        
        return executor_class(**kwargs)

    @classmethod
    def get_supported_types(cls) -> list:
        """
        获取支持的执行器类型列表
        
        Returns:
            支持的类型列表
        """
        return list(cls._executors.keys())

    @classmethod
    def build_all(cls, **kwargs) -> Dict[str, BaseExecutor]:
        """
        构建所有执行器实例
        
        Args:
            **kwargs: 传递给执行器的初始化参数
            
        Returns:
            执行器实例字典
        """
        return {
            category: cls.build(category, **kwargs)
            for category in cls._executors
        }

    @classmethod
    def execute(
        cls,
        intent: Dict[str, Any],
        context: Dict[str, Any],
        executors: Dict[str, BaseExecutor],
    ) -> ExecutionResult:
        """
        执行单个意图
        
        Args:
            intent: 意图数据
            context: 执行上下文
            executors: 执行器实例字典
            
        Returns:
            执行结果
        """
        category = intent.get("category", "")
        executor = executors.get(category)
        
        if not executor:
            log(f"[ExecutorRegistry] 未找到执行器: {category}", "Executor")
            return ExecutionResult(
                success=False,
                content=f"不支持的意图类别: {category}",
                error="executor_not_found"
            )
        
        if not executor.validate_intent(intent):
            log(f"[ExecutorRegistry] 意图数据无效: {intent}", "Executor")
            return ExecutionResult(
                success=False,
                content="意图数据无效",
                error="invalid_intent"
            )
        
        return executor.execute(intent, context)

    @classmethod
    def execute_all(
        cls,
        intents: List[Dict[str, Any]],
        context: Dict[str, Any],
        executors: Dict[str, BaseExecutor],
    ) -> List[Dict[str, Any]]:
        """
        执行多个意图
        
        Args:
            intents: 意图列表
            context: 执行上下文
            executors: 执行器实例字典
            
        Returns:
            执行结果列表
        """
        results = []
        
        for i, intent in enumerate(intents):
            intent_type = intent.get("type", "unknown")
            log(f"[ExecutorRegistry] 执行意图 [{i+1}/{len(intents)}]: {intent_type}", "Executor")
            
            execution_result = cls.execute(intent, context, executors)
            
            results.append({
                "type": intent.get("category", "unknown"),
                "target": intent.get("target", ""),
                "content": execution_result.content,
                "success": execution_result.success,
            })
        
        log(f"[ExecutorRegistry] 执行完成，共 {len(results)} 个结果", "Executor")
        return results
