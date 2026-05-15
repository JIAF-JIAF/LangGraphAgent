"""
钉钉待办事项工具
"""
import time
from mcp_module.tools.registry import register_tool
from mcp_module.tools.dingtalk.dingtalk_client import get_dingtalk_client
from mcp_module.logger import info, error


@register_tool(
    name="create_dingtalk_todo",
    description="创建钉钉待办事项",
    parameters=[
        {
            "name": "subject",
            "type": "string",
            "description": "待办事项标题",
            "required": True
        },
        {
            "name": "dueTime",
            "type": "integer",
            "description": "截止时间，Unix时间戳，单位毫秒，例如1617675000000，当前时间为{}".format(int(time.time() * 1000)),
            "required": False
        },
        {
            "name": "description",
            "type": "string",
            "description": "待办事项描述",
            "required": False
        },
        {
            "name": "priority",
            "type": "integer",
            "description": "优先级，10较低，20普通，30紧急，40非常紧急",
            "required": False
        },
        {
            "name": "operatorId",
            "type": "string",
            "description": "操作者用户的unionId，可选参数",
            "required": False
        },
        {
            "name": "user_id",
            "type": "string",
            "description": "用户ID，内部参数",
            "required": False
        }
    ],
    return_type="string"
)
def create_dingtalk_todo(subject: str, dueTime: int = None, description: str = None, priority: int = 0, operatorId: str = None, user_id: str = None) -> str:
    """创建钉钉待办事项"""
    info(f"[工具调用] create_dingtalk_todo - 参数: subject={subject}, dueTime={dueTime}, description={description}, priority={priority}, operatorId={operatorId}")
    
    if not subject or not subject.strip():
        info(f"[工具返回] create_dingtalk_todo - 失败: 缺少标题参数")
        return "请提供待办事项标题"

    try:
        info(f"[工具执行] create_dingtalk_todo - 正在创建待办事项...")
        
        client = get_dingtalk_client()
        access_token = client.get_access_token()
        
        info(f"[工具执行] create_dingtalk_todo - 正在获取用户unionId...")
        unionId = client.get_union_id(access_token, client.get_current_user_id(user_id))
        
        if not unionId:
            error(f"[工具返回] create_dingtalk_todo - 失败: 未能获取到unionId")
            return "未能获取到用户unionId"
        
        info(f"[工具执行] create_dingtalk_todo - 获取到unionId: {unionId}")
        
        todo_data = {
            "subject": subject,
            "priority": priority if priority else 20
        }
        
        if dueTime:
            todo_data["dueTime"] = dueTime
        if description:
            todo_data["description"] = description
        
        endpoint = f'/v1.0/todo/users/{unionId}/tasks'
        params = {}
        if operatorId:
            params['operatorId'] = operatorId
        
        result = client.request('POST', endpoint, params=params, data=todo_data)
        
        if result.get('code') == 0 or result.get('errcode') == 0 or 'id' in result:
            task_id = result.get('taskId', result.get('result', {}).get('taskId', result.get('id', '')))
            info(f"[工具返回] create_dingtalk_todo - 成功: 待办事项创建完成，taskId={task_id}")
            return f"钉钉待办事项创建成功:\n标题: {subject}\ntaskId: {task_id}"
        else:
            error(f"[工具返回] create_dingtalk_todo - 失败: {result}")
            errmsg = result.get('errmsg', result.get('message', '未知错误'))
            return f"创建钉钉待办事项失败: {errmsg}"

    except Exception as e:
        error(f"[工具返回] create_dingtalk_todo - 失败: {str(e)}")
        return f"创建钉钉待办事项失败: {str(e)}"
