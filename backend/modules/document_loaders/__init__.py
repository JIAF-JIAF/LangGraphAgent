"""
文档加载器模块
支持多种文档格式的加载，包括 txt、pdf、docx 和 excel

使用方式:
    from modules.document_loaders import DocumentLoaderFactory

    docs = DocumentLoaderFactory.load("path/to/document.txt")
"""

from .loader_factory import DocumentLoaderFactory

# 导入所有加载器，触发注册
from . import text_loader
from . import pdf_loader
from . import docx_loader
from . import excel_loader

__all__ = ['DocumentLoaderFactory']