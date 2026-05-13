"""
UserStore 基类定义

定义用户存储的标准接口，所有用户存储实现都应继承此类。
"""

from typing import Optional, Dict, Any, List


class BaseUserStore:
    """
    用户存储基类
    
    定义用户存储的标准接口，所有用户存储实现都应继承此类并实现以下方法：
    - add_user: 添加用户
    - get_user: 获取用户
    - update_user: 更新用户
    - delete_user: 删除用户
    - get_all_users: 获取所有用户
    - clear: 清空所有用户
    """

    def add_user(self, user_id: str, user_data: Dict[str, Any]) -> None:
        """
        添加用户

        Args:
            user_id: 用户唯一标识
            user_data: 用户数据字典
        """
        raise NotImplementedError

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户

        Args:
            user_id: 用户唯一标识

        Returns:
            用户数据字典，如果不存在返回 None
        """
        raise NotImplementedError

    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> bool:
        """
        更新用户数据

        Args:
            user_id: 用户唯一标识
            user_data: 要更新的用户数据

        Returns:
            如果更新成功返回 True，否则返回 False
        """
        raise NotImplementedError

    def delete_user(self, user_id: str) -> bool:
        """
        删除用户

        Args:
            user_id: 用户唯一标识

        Returns:
            如果删除成功返回 True，否则返回 False
        """
        raise NotImplementedError

    def get_all_users(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有用户

        Returns:
            所有用户数据字典，key 为 user_id
        """
        raise NotImplementedError

    def get_user_ids(self) -> List[str]:
        """
        获取所有用户 ID

        Returns:
            用户 ID 列表
        """
        return list(self.get_all_users().keys())

    def clear(self) -> None:
        """清空所有用户数据"""
        raise NotImplementedError

    def get_stats(self) -> Dict[str, Any]:
        """
        获取存储统计信息

        Returns:
            统计信息字典
        """
        raise NotImplementedError
