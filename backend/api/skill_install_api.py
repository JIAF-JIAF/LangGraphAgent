"""
Skill 安装 API

提供从 GitHub 安装 Skill 的接口。
"""

import os
from flask import Blueprint, request, jsonify
from modules.skill.installer import get_installer
from modules.skill.skill_engine import get_engine, reset_engine

skill_install_bp = Blueprint('skill_install', __name__, url_prefix='/skills')


@skill_install_bp.route('/install', methods=['POST'])
def install_skill():
    """
    从 GitHub 安装 Skill

    Request Body:
        {
            "url": "https://github.com/Agents365-ai/drawio-skill"
        }

    Returns:
        JSON 响应，包含安装结果
    """
    try:
        data = request.get_json()
        if not data or "url" not in data:
            return jsonify({
                "status": "error",
                "message": "缺少 url 参数"
            }), 400

        url = data["url"].strip()
        if not url:
            return jsonify({
                "status": "error",
                "message": "url 不能为空"
            }), 400

        installer = get_installer()
        result = installer.install_from_url(url)

        if result.success:
            reset_engine()
            engine = get_engine()
            skill = engine.get(result.skill_name)

            return jsonify({
                "status": "success",
                "message": result.message,
                "data": {
                    "name": result.skill_name,
                    "version": result.version,
                    "installed_path": result.installed_path,
                    "skill": skill
                }
            })
        else:
            return jsonify({
                "status": "error",
                "message": result.message
            }), 400

    except Exception as e:
        print(f"[SkillInstall] 安装失败: {e}")
        return jsonify({
            "status": "error",
            "message": f"安装失败: {str(e)}"
        }), 500


@skill_install_bp.route('/<skill_name>', methods=['DELETE'])
def uninstall_skill(skill_name):
    """
    卸载 Skill

    Args:
        skill_name: Skill 名称

    Returns:
        JSON 响应，包含卸载结果
    """
    try:
        installer = get_installer()
        result = installer.uninstall(skill_name)

        if result.success:
            reset_engine()

            return jsonify({
                "status": "success",
                "message": result.message
            })
        else:
            return jsonify({
                "status": "error",
                "message": result.message
            }), 400

    except Exception as e:
        print(f"[SkillInstall] 卸载失败: {e}")
        return jsonify({
            "status": "error",
            "message": f"卸载失败: {str(e)}"
        }), 500


@skill_install_bp.route('/', methods=['GET'])
def list_skills():
    """
    获取已安装的 Skill 列表

    Returns:
        JSON 响应，包含 Skill 列表
    """
    try:
        installer = get_installer()
        skills = installer.list_installed()

        return jsonify({
            "status": "success",
            "data": skills,
            "count": len(skills)
        })
    except Exception as e:
        print(f"[SkillInstall] 获取列表失败: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@skill_install_bp.route('/<skill_name>', methods=['GET'])
def get_skill(skill_name):
    """
    获取 Skill 详情

    Args:
        skill_name: Skill 名称

    Returns:
        JSON 响应，包含 Skill 详情
    """
    try:
        engine = get_engine()
        skill = engine.get(skill_name)

        if skill:
            return jsonify({
                "status": "success",
                "data": skill
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Skill 不存在"
            }), 404
    except Exception as e:
        print(f"[SkillInstall] 获取 Skill 详情失败: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@skill_install_bp.route('/<skill_name>/references/<path:ref_path>', methods=['GET'])
def get_skill_reference(skill_name, ref_path):
    """
    获取 Skill 的引用文件内容

    Args:
        skill_name: Skill 名称
        ref_path: 引用文件路径

    Returns:
        JSON 响应，包含文件内容
    """
    try:
        engine = get_engine()
        content = engine.get_reference(skill_name, ref_path)

        if content is not None:
            return jsonify({
                "status": "success",
                "data": {"content": content}
            })
        else:
            return jsonify({
                "status": "error",
                "message": "引用文件不存在"
            }), 404
    except Exception as e:
        print(f"[SkillInstall] 获取引用文件失败: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@skill_install_bp.route('/reload', methods=['POST'])
def reload_skills():
    """
    重新加载所有 Skill

    Returns:
        JSON 响应，包含重新加载结果
    """
    try:
        reset_engine()
        engine = get_engine()
        skills = engine.list()

        return jsonify({
            "status": "success",
            "message": "重新加载成功",
            "count": len(skills)
        })
    except Exception as e:
        print(f"[SkillInstall] 重新加载失败: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
