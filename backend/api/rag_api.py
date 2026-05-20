"""
RAG 知识库管理 API

提供知识库向量化、重建等管理接口。
"""

import os
from flask import Blueprint, jsonify
from modules.rag.rag import RAGWorkflow
from modules.ai_client import AIClient

rag_api_bp = Blueprint('rag_api', __name__, url_prefix='/rag')


def get_rag_workflow():
    """获取 RAGWorkflow 实例"""
    ai_client = AIClient()
    return RAGWorkflow(llm_client=ai_client)


@rag_api_bp.route('/vectorize/all', methods=['POST'])
def rebuild_all_indexes():
    """
    全量向量化：重建所有知识库的索引

    Returns:
        JSON 响应，包含各知识库的向量化结果
    """
    try:
        rag = get_rag_workflow()

        results = {}
        for kb_name in rag.indexers.keys():
            try:
                rag.switch_knowledge_base(kb_name)
                source_dir = os.path.join("knowledge_base", kb_name)
                result = rag.indexers[kb_name].build_index(source_dir)
                results[kb_name] = {
                    "status": result.get("status", "unknown"),
                    "message": result.get("message", ""),
                    "count": result.get("count", 0)
                }
            except Exception as e:
                results[kb_name] = {
                    "status": "error",
                    "message": str(e),
                    "count": 0
                }

        success_count = sum(1 for r in results.values() if r["status"] in ["created", "loaded"])
        return jsonify({
            "status": "success",
            "message": f"全量向量化完成，成功 {success_count}/{len(results)} 个知识库",
            "data": results
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"全量向量化失败: {str(e)}"
        }), 500


@rag_api_bp.route('/vectorize/<kb_name>', methods=['POST'])
def rebuild_index(kb_name):
    """
    重建指定知识库的索引

    Args:
        kb_name: 知识库名称

    Returns:
        JSON 响应，包含向量化结果
    """
    try:
        rag = get_rag_workflow()

        if kb_name not in rag.indexers:
            return jsonify({
                "status": "error",
                "message": f"知识库 '{kb_name}' 不存在"
            }), 404

        rag.switch_knowledge_base(kb_name)
        source_dir = os.path.join("knowledge_base", kb_name)
        result = rag.indexers[kb_name].build_index(source_dir)

        return jsonify({
            "status": "success",
            "data": {
                "kb_name": kb_name,
                "status": result.get("status", "unknown"),
                "message": result.get("message", ""),
                "count": result.get("count", 0)
            }
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"向量化失败: {str(e)}"
        }), 500


@rag_api_bp.route('/knowledge-bases', methods=['GET'])
def list_knowledge_bases():
    """
    获取所有知识库列表

    Returns:
        JSON 响应，包含知识库列表和统计信息
    """
    try:
        rag = get_rag_workflow()

        kbs = []
        for kb_name in rag.indexers.keys():
            try:
                rag.switch_knowledge_base(kb_name)
                stats = rag.indexers[kb_name].get_collection_stats()
                kbs.append({
                    "name": kb_name,
                    "vector_count": stats.get("vector_count", 0)
                })
            except Exception as e:
                kbs.append({
                    "name": kb_name,
                    "vector_count": 0,
                    "error": str(e)
                })

        return jsonify({
            "status": "success",
            "data": kbs,
            "count": len(kbs)
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500