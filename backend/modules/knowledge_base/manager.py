"""
知识库管理器 - 统一管理所有知识库的元数据
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class KnowledgeBaseManager:
    def __init__(self):
        self.knowledge_base_dir = os.getenv("KNOWLEDGE_BASE_DIR", "knowledge_base")
        self.metadata_file = os.path.join(self.knowledge_base_dir, "databases.json")
        self.metadata = self.load_metadata()

    def load_metadata(self):
        """加载知识库元数据"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载元数据失败: {e}")
        return {}

    def save_metadata(self):
        """保存知识库元数据"""
        os.makedirs(self.knowledge_base_dir, exist_ok=True)
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)

    def get_databases(self):
        """获取所有知识库列表"""
        result = []
        for db_name, meta in self.metadata.items():
            docs = meta.get("documents", {})
            vector_count = sum(doc.get("vector_count", 0) for doc in docs.values())
            result.append({
                "name": db_name,
                "description": meta.get("description", ""),
                "document_count": len(docs),
                "vector_count": vector_count,
                "created_at": meta.get("created_at", ""),
                "updated_at": meta.get("updated_at", "")
            })
        return result

    def get_database(self, db_name):
        """获取单个知识库详情"""
        if db_name not in self.metadata:
            return None

        meta = self.metadata[db_name]
        docs = meta.get("documents", {})
        # 转换为前端需要的格式
        documents_list = []
        for filename, info in docs.items():
            documents_list.append({
                "filename": filename,
                "chunk_count": info.get("chunk_count", 0),
                "vector_count": info.get("vector_count", 0),
                "added_at": info.get("added_at", "")
            })
        
        return {
            "name": db_name,
            "description": meta.get("description", ""),
            "documents": documents_list,
            "created_at": meta.get("created_at", ""),
            "updated_at": meta.get("updated_at", "")
        }

    def create_database(self, db_name, description=""):
        """创建新知识库"""
        if db_name in self.metadata:
            return False, "数据库已存在"

        db_path = os.path.join(self.knowledge_base_dir, db_name)
        os.makedirs(db_path, exist_ok=True)

        self.metadata[db_name] = {
            "description": description,
            "documents": {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        self.save_metadata()

        return True, "创建成功"

    def update_database(self, db_name, description):
        """更新知识库描述"""
        if db_name not in self.metadata:
            return False, "数据库不存在"

        self.metadata[db_name]["description"] = description
        self.metadata[db_name]["updated_at"] = datetime.now().isoformat()
        self.save_metadata()

        return True, "更新成功"

    def delete_database(self, db_name):
        """删除知识库"""
        if db_name not in self.metadata:
            return False, "数据库不存在"

        db_path = os.path.join(self.knowledge_base_dir, db_name)
        if os.path.exists(db_path):
            import shutil
            shutil.rmtree(db_path)

        del self.metadata[db_name]
        self.save_metadata()

        return True, "删除成功"

    def add_document(self, db_name, filename, chunk_count=0, vector_count=0):
        """添加文档到知识库"""
        if db_name not in self.metadata:
            return False, "数据库不存在"

        docs = self.metadata[db_name]["documents"]
        if filename not in docs:
            self.metadata[db_name]["documents"][filename] = {
                "chunk_count": chunk_count,
                "vector_count": vector_count,
                "added_at": datetime.now().isoformat()
            }
            self.metadata[db_name]["updated_at"] = datetime.now().isoformat()
            self.save_metadata()

        return True, "添加成功"

    def update_document_stats(self, db_name, filename, chunk_count, vector_count):
        """更新文档的统计信息"""
        if db_name not in self.metadata:
            return False, "数据库不存在"

        docs = self.metadata[db_name]["documents"]
        if isinstance(docs, dict) and filename in docs:
            self.metadata[db_name]["documents"][filename]["chunk_count"] = chunk_count
            self.metadata[db_name]["documents"][filename]["vector_count"] = vector_count
            self.metadata[db_name]["updated_at"] = datetime.now().isoformat()
            self.save_metadata()
            return True, "更新成功"

        return False, "文档不存在或格式不支持"

    def remove_document(self, db_name, filename):
        """从知识库移除文档"""
        if db_name not in self.metadata:
            return False, "数据库不存在"

        docs = self.metadata[db_name]["documents"]
        if filename in docs:
            del self.metadata[db_name]["documents"][filename]
            self.metadata[db_name]["updated_at"] = datetime.now().isoformat()
            self.save_metadata()
            return True, "移除成功"

        return False, "文档不存在"

    def get_all_collection_names(self):
        """获取所有知识库名称（用于动态初始化索引器）"""
        return list(self.metadata.keys())

kb_manager = KnowledgeBaseManager()
