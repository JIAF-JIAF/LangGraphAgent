"""
向量数据库管理服务
独立的 Flask 服务，提供向量数据库的管理功能
"""

import os
import sys
import shutil
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# 添加模块路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.ai_client import AIClient
from modules.rag.indexer import ChromaIndexer
from modules.document_loaders import DocumentLoaderFactory
from knowledge_base import kb_manager
from api.mcp_config_api import mcp_config_bp
from api.skill_install_api import skill_install_bp
from api.skill_config_api import skill_config_bp
from api.rag_api import rag_api_bp

load_dotenv()

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'
app.url_map.strict_slashes = False
CORS(app)

# 注册 MCP 配置 API 蓝图
app.register_blueprint(mcp_config_bp)

# 注册 Skill 安装 API 蓝图
app.register_blueprint(skill_install_bp)

# 注册 Skill 配置 API 蓝图
app.register_blueprint(skill_config_bp)

# 注册 RAG API 蓝图
app.register_blueprint(rag_api_bp)

# 全局变量
ai_client = None

# 从环境变量读取配置
CHROMA_DB_DIR = os.getenv("VECTOR_STORE_PERSIST_DIRECTORY", "db/chroma")
ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.md', '.csv', '.docx', '.xlsx', '.xls'}

def init_ai_client():
    """初始化 AI 客户端"""
    global ai_client
    if ai_client is None:
        ai_client = AIClient()
    return ai_client

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

def get_database_stats(db_name):
    """获取数据库统计信息"""
    try:
        init_ai_client()
        indexer = ChromaIndexer(
            ai_client=ai_client,
            collection_name=db_name
        )

        if indexer.load_index():
            stats = indexer.get_collection_stats()
            return stats
        return {"vector_count": 0}
    except Exception as e:
        print(f"获取数据库统计失败: {e}")
        return {"vector_count": 0}

@app.route('/databases', methods=['GET'])
def get_databases():
    """获取所有数据库列表"""
    try:
        databases = kb_manager.get_databases()

        result = []
        for db in databases:
            stats = get_database_stats(db["name"])
            result.append({
                "name": db["name"],
                "description": db["description"],
                "document_count": db["document_count"],
                "vector_count": stats.get("vector_count", 0),
                "documents": kb_manager.get_database(db["name"]).get("documents", [])
            })

        return jsonify({
            "status": "success",
            "data": result,
            "total": len(result)
        })
    except Exception as e:
        print(f"获取数据库列表失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/databases', methods=['POST'])
def create_database():
    """新建数据库"""
    try:
        data = request.get_json()
        db_name = data.get('name')
        description = data.get('description', '')

        if not db_name:
            return jsonify({"status": "error", "message": "数据库名称不能为空"}), 400

        if not db_name.replace('_', '').isalnum():
            return jsonify({"status": "error", "message": "数据库名称只能包含字母、数字和下划线"}), 400

        success, msg = kb_manager.create_database(db_name, description)
        if not success:
            return jsonify({"status": "error", "message": msg}), 400

        init_ai_client()
        indexer = ChromaIndexer(
            ai_client=ai_client,
            collection_name=db_name
        )
        indexer.build_index(os.path.join(kb_manager.knowledge_base_dir, db_name))

        return jsonify({
            "status": "success",
            "message": "数据库创建成功",
            "data": {"name": db_name, "description": description}
        })
    except Exception as e:
        print(f"创建数据库失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/databases/<db_name>', methods=['GET'])
def get_database(db_name):
    """获取单个数据库详情"""
    try:
        db = kb_manager.get_database(db_name)
        if not db:
            return jsonify({"status": "error", "message": "数据库不存在"}), 404

        stats = get_database_stats(db_name)

        return jsonify({
            "status": "success",
            "data": {
                "name": db["name"],
                "description": db["description"],
                "document_count": len(db["documents"]),
                "vector_count": stats.get("vector_count", 0),
                "documents": db["documents"],
                "created_at": db["created_at"],
                "updated_at": db["updated_at"]
            }
        })
    except Exception as e:
        print(f"获取数据库详情失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/databases/<db_name>', methods=['PUT'])
def update_database(db_name):
    """更新数据库信息"""
    try:
        data = request.get_json()
        description = data.get('description', '')

        success, msg = kb_manager.update_database(db_name, description)
        if not success:
            return jsonify({"status": "error", "message": msg}), 404

        return jsonify({
            "status": "success",
            "message": "数据库信息更新成功"
        })
    except Exception as e:
        print(f"更新数据库失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/databases/<db_name>', methods=['DELETE'])
def delete_database(db_name):
    """删除数据库"""
    try:
        init_ai_client()
        indexer = ChromaIndexer(
            ai_client=ai_client,
            collection_name=db_name
        )
        indexer.delete_collection()

        success, msg = kb_manager.delete_database(db_name)
        if not success:
            return jsonify({"status": "error", "message": msg}), 404

        return jsonify({
            "status": "success",
            "message": "数据库删除成功"
        })
    except Exception as e:
        print(f"删除数据库失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/databases/<db_name>/upload', methods=['POST'])
def upload_files(db_name):
    """上传文件到数据库"""
    try:
        if not kb_manager.get_database(db_name):
            return jsonify({"status": "error", "message": "数据库不存在"}), 404

        if 'files' not in request.files:
            return jsonify({"status": "error", "message": "未选择文件"}), 400

        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({"status": "error", "message": "未选择文件"}), 400

        uploaded_files = []
        db_path = os.path.join(kb_manager.knowledge_base_dir, db_name)

        for file in files:
            if file and allowed_file(file.filename):
                filename = file.filename
                file_path = os.path.join(db_path, filename)
                file.save(file_path)
                uploaded_files.append(filename)
                # 先添加文档（不带统计信息）
                kb_manager.add_document(db_name, filename)
                print(f"文件已保存: {file_path}")

        if not uploaded_files:
            return jsonify({"status": "error", "message": "没有有效的文件"}), 400

        init_ai_client()
        indexer = ChromaIndexer(
            ai_client=ai_client,
            collection_name=db_name
        )

        result = indexer.build_index(db_path)

        if result["status"] in ["created", "loaded"]:
            stats = indexer.get_collection_stats()
            total_vector_count = stats.get('vector_count', 0)
            
            # 更新每个上传文件的统计信息
            for filename in uploaded_files:
                # 暂时设置相同的统计，实际应该根据文件内容计算
                kb_manager.update_document_stats(db_name, filename, 0, total_vector_count)

            return jsonify({
                "status": "success",
                "message": f"文件上传并向量化完成，共 {len(uploaded_files)} 个文件，生成 {total_vector_count} 个向量",
                "data": {
                    "uploaded_files": uploaded_files,
                    "vector_count": total_vector_count
                }
            })
        else:
            return jsonify({"status": "error", "message": result.get("message", "向量化失败")}), 500

    except Exception as e:
        print(f"上传文件失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/databases/<db_name>/documents', methods=['GET'])
def get_documents(db_name):
    """获取数据库中的文档列表"""
    try:
        db = kb_manager.get_database(db_name)
        if not db:
            return jsonify({"status": "error", "message": "数据库不存在"}), 404

        # 直接返回已格式化的文档列表
        documents = db.get("documents", [])

        return jsonify({
            "status": "success",
            "data": documents,
            "total": len(documents)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/databases/<db_name>/documents/<doc_name>', methods=['GET', 'DELETE'])
def handle_document(db_name, doc_name):
    """获取或删除文档"""
    if request.method == 'GET':
        return get_document_content(db_name, doc_name)
    else:
        return delete_document(db_name, doc_name)

def get_document_content(db_name, doc_name):
    """获取文档内容"""
    try:
        db = kb_manager.get_database(db_name)
        if not db:
            return jsonify({"status": "error", "message": "数据库不存在"}), 404

        file_path = os.path.join(kb_manager.knowledge_base_dir, db_name, doc_name)
        if not os.path.exists(file_path):
            return jsonify({"status": "error", "message": "文档不存在"}), 404

        from flask import send_file
        return send_file(file_path, as_attachment=False)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def delete_document(db_name, doc_name):
    """删除数据库中的单个文档"""
    try:
        db = kb_manager.get_database(db_name)
        if not db:
            return jsonify({"status": "error", "message": "数据库不存在"}), 404

        file_path = os.path.join(kb_manager.knowledge_base_dir, db_name, doc_name)
        if os.path.exists(file_path):
            os.remove(file_path)
        else:
            return jsonify({"status": "error", "message": "文档不存在"}), 404

        kb_manager.remove_document(db_name, doc_name)

        init_ai_client()
        indexer = ChromaIndexer(
            ai_client=ai_client,
            collection_name=db_name
        )
        indexer.delete_collection()
        indexer.build_index(os.path.join(kb_manager.knowledge_base_dir, db_name))

        vector_count = 0
        if indexer.load_index():
            stats = indexer.get_collection_stats()
            vector_count = stats.get('vector_count', 0)

        return jsonify({
            "status": "success",
            "message": "文档删除成功",
            "data": {"vector_count": vector_count}
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({"status": "success", "message": "服务运行正常"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
