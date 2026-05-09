"""
内存检查点存储实现

使用内存字典存储检查点数据，适合开发测试环境。
注意：重启服务后数据会丢失，生产环境建议使用 Redis 或数据库存储。
"""

from typing import Optional, Dict, List, Any, Iterator, Tuple, Sequence
from langgraph.checkpoint.base import (
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    PendingWrite,
)

from .base import BaseCheckpointSaver


class MemorySaver(BaseCheckpointSaver):
    """
    内存检查点存储

    使用内存字典存储检查点，特点：
    - 无需外部依赖
    - 读写速度快
    - 重启后数据丢失
    - 适合开发测试环境

    Example:
        >>> from modules.langgraph.checkpoint import MemorySaver
        >>> checkpointer = MemorySaver()
    """

    def __init__(self):
        """初始化内存存储"""
        self._store: Dict[str, Checkpoint] = {}
        self._history: Dict[str, List[Tuple[Checkpoint, CheckpointMetadata]]] = {}
        self._pending_writes: Dict[str, List[PendingWrite]] = {}

    def _get_key(self, config: Dict[str, Any]) -> str:
        """从配置中提取 thread_id 作为存储键"""
        return config.get("configurable", {}).get("thread_id", "default")

    def get(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        """
        获取检查点

        Args:
            config: 配置信息，必须包含 configurable.thread_id

        Returns:
            检查点数据，如果不存在返回 None
        """
        key = self._get_key(config)
        return self._store.get(key)

    def get_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """
        获取检查点元组（检查点 + 元数据）

        Args:
            config: 配置信息

        Returns:
            CheckpointTuple，如果不存在返回 None
        """
        key = self._get_key(config)
        checkpoint = self._store.get(key)
        if checkpoint:
            history = self._history.get(key, [])
            metadata = history[-1][1] if history else CheckpointMetadata()
            parent_config = history[-1][0].get("parent_config") if history else None
            return CheckpointTuple(config, checkpoint, metadata)
        return None

    def put(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Dict[str, Any]
    ):
        """
        保存检查点

        Args:
            config: 配置信息
            checkpoint: 检查点数据
            metadata: 检查点元数据
            new_versions: 新版本信息
        """
        key = self._get_key(config)
        self._store[key] = checkpoint

        if key not in self._history:
            self._history[key] = []
        self._history[key].append((checkpoint, metadata))

    def put_writes(
        self,
        config: Dict[str, Any],
        writes: Sequence[Tuple[str, Any]],
        task_id: str
    ):
        """
        保存待写入的数据

        Args:
            config: 配置信息
            writes: 待写入的数据列表
            task_id: 任务 ID
        """
        key = self._get_key(config)
        if key not in self._pending_writes:
            self._pending_writes[key] = []
        self._pending_writes[key].extend(writes)

    def list(
        self,
        config: Dict[str, Any],
        limit: Optional[int] = None,
        before: Optional[Checkpoint] = None
    ) -> Iterator[CheckpointTuple]:
        """
        列出检查点

        Args:
            config: 配置信息
            limit: 返回数量限制
            before: 只返回此检查点之前的检查点

        Returns:
            检查点迭代器
        """
        key = self._get_key(config)
        history = self._history.get(key, [])

        if before:
            filtered = []
            for checkpoint, metadata in history:
                if checkpoint == before:
                    break
                filtered.append(CheckpointTuple(config, checkpoint, metadata))
            yield from filtered
        else:
            for checkpoint, metadata in history:
                yield CheckpointTuple(config, checkpoint, metadata)

    def clear(self, thread_id: Optional[str] = None):
        """
        清除检查点

        Args:
            thread_id: 线程 ID，如果为 None 则清除所有检查点
        """
        if thread_id:
            self._store.pop(thread_id, None)
            self._history.pop(thread_id, None)
            self._pending_writes.pop(thread_id, None)
        else:
            self._store.clear()
            self._history.clear()
            self._pending_writes.clear()

    def get_stats(self) -> Dict[str, Any]:
        """
        获取存储统计信息

        Returns:
            统计信息字典
        """
        return {
            "total_threads": len(self._store),
            "total_checkpoints": sum(len(hist) for hist in self._history.values())
        }
