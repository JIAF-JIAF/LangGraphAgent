"""
Checkpointer 基类定义

继承自 LangGraph 的 BaseCheckpointSaver，确保兼容性。
"""

from typing import Optional, Dict, List, Any, AsyncIterator
from langgraph.checkpoint.base import BaseCheckpointSaver as LangGraphBaseCheckpointSaver
from langgraph.checkpoint.base import (
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)


class BaseCheckpointSaver(LangGraphBaseCheckpointSaver):
    """
    检查点存储基类
    
    继承自 LangGraph 的 BaseCheckpointSaver，确保兼容性。
    所有自定义检查点存储都应继承此类并实现以下方法：
    - get: 获取检查点
    - put: 保存检查点
    - list: 列出检查点
    """

    async def aget(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        """异步获取检查点"""
        return self.get(config)

    async def aput(self, config: Dict[str, Any], checkpoint: Checkpoint):
        """异步保存检查点"""
        return self.put(config, checkpoint)

    async def alist(self, config: Dict[str, Any]) -> AsyncIterator[CheckpointTuple]:
        """异步列出检查点"""
        for item in self.list(config):
            yield item
