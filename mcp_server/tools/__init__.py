"""
MCP 工具定义模块
包含所有具体的工具实现
"""

from .weather_plugin import get_weather
from .weather_recommend_plugin import get_weather_recommendation
from .submit_form_plugin import submit_form
from .dingtalk.dingtalk_todo_plugin import create_dingtalk_todo
from .dingtalk.dingtalk_schedule_query_plugin import query_dingtalk_schedule
from .dingtalk.dingtalk_schedule_create_plugin import create_dingtalk_schedule
from .dingtalk.dingtalk_schedule_delete_plugin import delete_dingtalk_schedule, delete_dingtalk_schedule_by_id

__all__ = [
    'get_weather',
    'get_weather_recommendation',
    'submit_form',
    'create_dingtalk_todo',
    'query_dingtalk_schedule',
    'create_dingtalk_schedule',
    'search_dingtalk_schedule',
    'delete_dingtalk_schedule',
    'delete_dingtalk_schedule_by_id',
]