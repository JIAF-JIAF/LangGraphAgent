#!/usr/bin/env python
"""
MCP 服务器独立启动脚本
运行此脚本启动独立的 MCP 服务
"""

import sys
import os

# 添加父目录到路径，以便导入 mcp 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcp_server.tools.weather_plugin
import mcp_server.tools.weather_recommend_plugin
import mcp_server.tools.submit_form_plugin
import mcp_server.tools.dingtalk.dingtalk_schedule_create_plugin
import mcp_server.tools.dingtalk.dingtalk_schedule_query_plugin
import mcp_server.tools.dingtalk.dingtalk_schedule_delete_plugin
import mcp_server.tools.dingtalk.dingtalk_todo_plugin

import mcp_server.mcp_server as mcp_server_mod
import mcp_server.logger as logger

def main():
    logger.logger.info("从注册表注册工具...")
    mcp_server_mod.register_from_registry()
    logger.logger.info("工具注册完成")

    logger.logger.info("启动服务器...")
    port = int(os.environ.get("MCP_PORT", 8080))
    mcp_server_mod.run_server(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()