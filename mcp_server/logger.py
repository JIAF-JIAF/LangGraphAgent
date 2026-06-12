"""
日志配置模块
提供统一的日志记录功能
"""

import logging
import sys


def setup_logger(name: str = "chartflow") -> logging.Logger:
    """
    配置日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if logger.handlers:
        return logger
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


logger = setup_logger()


def info(msg: str) -> None:
    """便捷的 INFO 级别日志"""
    logger.info(msg)


def error(msg: str) -> None:
    """便捷的 ERROR 级别日志"""
    logger.error(msg)


def warn(msg: str) -> None:
    """便捷的 WARNING 级别日志"""
    logger.warning(msg)


def debug(msg: str) -> None:
    """便捷的 DEBUG 级别日志"""
    logger.debug(msg)


__all__ = ['setup_logger', 'logger', 'info', 'error', 'warn', 'debug']