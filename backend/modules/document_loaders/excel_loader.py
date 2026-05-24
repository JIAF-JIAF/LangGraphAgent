"""
Excel 文档加载器
支持 .xlsx 和 .xls 格式
"""

from typing import List
from langchain_core.documents import Document
import pandas as pd

from .loader_factory import BaseDocumentLoader, DocumentLoaderFactory


class ExcelDocumentLoader(BaseDocumentLoader):
    """
    Excel 文档加载器
    支持 .xlsx 和 .xls 格式
    """

    def load(self) -> List[Document]:
        """
        加载 Excel 文档
        
        Returns:
            Document 对象列表，每个工作表作为一个 Document
        """
        try:
            excel_file = pd.ExcelFile(self.file_path)
            documents = []
            
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                
                if df.empty:
                    continue
                
                content_parts = [f"工作表: {sheet_name}", ""]
                
                df_filled = df.fillna("")
                
                for idx, row in df_filled.iterrows():
                    row_values = []
                    for col in df.columns:
                        value = row[col]
                        if str(value).strip():
                            row_values.append(f"{col}: {value}")
                    if row_values:
                        content_parts.append(" | ".join(row_values))
                
                content = "\n".join(content_parts)
                
                if content.strip():
                    doc = Document(
                        page_content=content,
                        metadata={
                            "source": self.file_path,
                            "sheet_name": sheet_name,
                            "rows": len(df),
                            "columns": len(df.columns)
                        }
                    )
                    documents.append(doc)
            
            return documents
        except Exception as e:
            print(f"加载 Excel 文档失败: {e}")
            return []


DocumentLoaderFactory.register_loader(".xlsx", ExcelDocumentLoader)
DocumentLoaderFactory.register_loader(".xls", ExcelDocumentLoader)
