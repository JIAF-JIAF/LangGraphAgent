"""
配置模块
集中管理 MCP 项目常量配置
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

import json

MCP_HOST = os.getenv("MCP_HOST")
MCP_PORT = int(os.getenv("MCP_PORT"))
MCP_PATH = os.getenv("MCP_PATH")
APP_HOST = os.getenv("SERVER_HOST")
APP_PORT = int(os.getenv("SERVER_PORT"))
LOG_LEVEL = os.getenv("LOG_LEVEL")
LOG_FORMAT = os.getenv("LOG_FORMAT")
LOG_DATE_FORMAT = os.getenv("LOG_DATE_FORMAT")


__all__ = [
    'MCP_HOST',
    'MCP_PORT',
    'MCP_PATH',
    'APP_HOST',
    'APP_PORT',
    'LOG_LEVEL',
    'LOG_FORMAT',
    'LOG_DATE_FORMAT'
]
