"""
MCP 服务器配置 API

提供 MCP 服务器的增删改查接口，支持管理后台动态配置。
"""

from flask import Blueprint, request, jsonify
from mcp_module.mcp_config_manager import mcp_config_manager

mcp_config_bp = Blueprint('mcp_config', __name__, url_prefix='/mcp')


@mcp_config_bp.route('/servers', methods=['GET'])
def get_servers():
    """
    获取所有 MCP 服务器列表
    
    Returns:
        JSON 响应，包含服务器列表和数量
    """
    servers = mcp_config_manager.get_all_servers()
    return jsonify({
        "status": "success",
        "data": servers,
        "count": len(servers)
    })


@mcp_config_bp.route('/servers/<int:server_id>', methods=['GET'])
def get_server(server_id):
    """
    获取单个服务器配置
    
    Args:
        server_id: 服务器 ID
    
    Returns:
        JSON 响应，包含服务器配置或错误信息
    """
    server = mcp_config_manager.get_server_by_id(server_id)
    if server:
        return jsonify({
            "status": "success",
            "data": server
        })
    return jsonify({
        "status": "error",
        "message": "服务器不存在"
    }), 404


@mcp_config_bp.route('/servers', methods=['POST'])
def add_server():
    """
    添加新的 MCP 服务器
    
    Request Body:
        {
            "name": "服务器名称",
            "url": "服务器地址",
            "protocol": "协议类型",
            "description": "描述"
        }
    
    Returns:
        JSON 响应，包含新添加的服务器配置
    """
    data = request.get_json()
    
    if not data or 'url' not in data:
        return jsonify({
            "status": "error",
            "message": "缺少必要参数: url"
        }), 400
    
    new_server = mcp_config_manager.add_server(data)
    return jsonify({
        "status": "success",
        "message": "服务器添加成功",
        "data": new_server
    }), 201


@mcp_config_bp.route('/servers/<int:server_id>', methods=['PUT'])
def update_server(server_id):
    """
    更新服务器配置
    
    Args:
        server_id: 服务器 ID
    
    Request Body:
        {
            "name": "服务器名称",
            "url": "服务器地址",
            "protocol": "协议类型",
            "description": "描述"
        }
    
    Returns:
        JSON 响应，包含更新后的服务器配置
    """
    data = request.get_json()
    
    if not data:
        return jsonify({
            "status": "error",
            "message": "缺少更新数据"
        }), 400
    
    updated_server = mcp_config_manager.update_server(server_id, data)
    if updated_server:
        return jsonify({
            "status": "success",
            "message": "服务器更新成功",
            "data": updated_server
        })
    return jsonify({
        "status": "error",
        "message": "服务器不存在"
    }), 404


@mcp_config_bp.route('/servers/<int:server_id>', methods=['DELETE'])
def delete_server(server_id):
    """
    删除服务器配置
    
    Args:
        server_id: 服务器 ID
    
    Returns:
        JSON 响应，包含删除结果
    """
    success = mcp_config_manager.delete_server(server_id)
    if success:
        return jsonify({
            "status": "success",
            "message": "服务器删除成功"
        })
    return jsonify({
        "status": "error",
        "message": "服务器不存在"
    }), 404


@mcp_config_bp.route('/servers/<int:server_id>/test', methods=['POST'])
def test_server_connection(server_id):
    """
    测试服务器连接
    
    Args:
        server_id: 服务器 ID
    
    Returns:
        JSON 响应，包含连接测试结果
    """
    result = mcp_config_manager.test_connection(server_id)
    return jsonify({
        "status": "success" if result["success"] else "error",
        "message": result["message"],
        "data": {"server_id": server_id, "status": result["success"]}
    })


@mcp_config_bp.route('/servers/default', methods=['GET'])
def get_default_server():
    """
    获取默认服务器
    
    返回第一个可用的服务器作为默认服务器
    
    Returns:
        JSON 响应，包含默认服务器配置
    """
    server = mcp_config_manager.get_default_server()
    if server:
        return jsonify({
            "status": "success",
            "data": server
        })
    return jsonify({
        "status": "error",
        "message": "暂无服务器配置"
    }), 404
