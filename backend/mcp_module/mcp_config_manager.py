"""
MCP 服务器配置管理器

负责管理 MCP 服务器配置的读取、写入和更新。
配置文件采用 YAML 格式存储，支持动态添加、删除和修改服务器配置。
"""

import os
import yaml
import requests
from datetime import datetime
from typing import List, Dict, Optional

CONFIG_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'config',
    'mcp_servers.yaml'
)


class MCPConfigManager:
    """MCP 服务器配置管理器"""
    
    def __init__(self, config_path: str = CONFIG_FILE_PATH):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为 CONFIG_FILE_PATH
        """
        self.config_path = config_path
        self._ensure_config_file()
    
    def _ensure_config_file(self):
        """
        确保配置文件存在
        
        如果配置目录不存在则创建，配置文件不存在则创建空配置
        """
        config_dir = os.path.dirname(self.config_path)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        
        if not os.path.exists(self.config_path):
            empty_config = {
                "servers": []
            }
            self._save_config(empty_config)
    
    def _load_config(self) -> Dict:
        """
        加载配置文件
        
        Returns:
            配置字典，包含 servers 列表
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {"servers": []}
        except (yaml.YAMLError, FileNotFoundError):
            return {"servers": []}
    
    def _save_config(self, config: Dict):
        """
        保存配置文件
        
        Args:
            config: 要保存的配置字典
        """
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, sort_keys=False)
    
    def get_all_servers(self) -> List[Dict]:
        """
        获取所有 MCP 服务器配置
        
        Returns:
            服务器配置列表
        """
        config = self._load_config()
        return config.get("servers", [])
    
    def get_server_by_id(self, server_id: int) -> Optional[Dict]:
        """
        根据 ID 获取服务器配置
        
        Args:
            server_id: 服务器 ID
        
        Returns:
            服务器配置字典，如果不存在返回 None
        """
        servers = self.get_all_servers()
        return next((s for s in servers if s["id"] == server_id), None)
    
    def add_server(self, server_data: Dict) -> Dict:
        """
        添加新的 MCP 服务器
        
        Args:
            server_data: 服务器数据，包含 name, url, protocol, description
        
        Returns:
            新添加的服务器配置字典
        """
        config = self._load_config()
        servers = config.get("servers", [])
        
        max_id = max((s["id"] for s in servers), default=0)
        new_server = {
            "id": max_id + 1,
            "name": server_data.get("name", "未命名服务器"),
            "url": server_data["url"],
            "protocol": server_data.get("protocol", "StreamableHTTP"),
            "status": "disconnected",
            "description": server_data.get("description", ""),
            "created_at": datetime.now().isoformat()
        }
        
        servers.append(new_server)
        config["servers"] = servers
        self._save_config(config)
        
        return new_server
    
    def update_server(self, server_id: int, updates: Dict) -> Optional[Dict]:
        """
        更新服务器配置
        
        Args:
            server_id: 服务器 ID
            updates: 要更新的字段字典
        
        Returns:
            更新后的服务器配置字典，如果不存在返回 None
        """
        config = self._load_config()
        servers = config.get("servers", [])
        
        for server in servers:
            if server["id"] == server_id:
                server.update({
                    k: v for k, v in updates.items() 
                    if k in ["name", "url", "protocol", "description", "status"]
                })
                self._save_config(config)
                return server
        
        return None
    
    def delete_server(self, server_id: int) -> bool:
        """
        删除服务器配置
        
        Args:
            server_id: 服务器 ID
        
        Returns:
            删除成功返回 True，失败返回 False
        """
        config = self._load_config()
        servers = config.get("servers", [])
        
        initial_count = len(servers)
        servers = [s for s in servers if s["id"] != server_id]
        
        if len(servers) < initial_count:
            config["servers"] = servers
            self._save_config(config)
            return True
        
        return False
    
    def test_connection(self, server_id: int) -> Dict:
        """
        测试服务器连接
        
        Args:
            server_id: 服务器 ID
        
        Returns:
            连接测试结果字典，包含 success 和 message 字段
        """
        server = self.get_server_by_id(server_id)
        if not server:
            return {"success": False, "message": "服务器不存在"}
        
        try:
            response = requests.get(server["url"], timeout=5)
            if response.status_code == 200:
                server["status"] = "connected"
                self.update_server(server_id, {"status": "connected"})
                return {"success": True, "message": "连接成功"}
            else:
                server["status"] = "disconnected"
                self.update_server(server_id, {"status": "disconnected"})
                return {"success": False, "message": f"连接失败，状态码: {response.status_code}"}
        except requests.exceptions.RequestException as e:
            server["status"] = "disconnected"
            self.update_server(server_id, {"status": "disconnected"})
            return {"success": False, "message": f"连接失败: {str(e)}"}
    
    def get_default_server(self) -> Optional[Dict]:
        """
        获取默认服务器
        
        返回第一个可用的服务器
        
        Returns:
            默认服务器配置字典，如果没有服务器返回 None
        """
        servers = self.get_all_servers()
        return servers[0] if servers else None


# 创建单例实例
mcp_config_manager = MCPConfigManager()
