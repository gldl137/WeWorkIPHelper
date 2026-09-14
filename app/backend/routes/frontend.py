#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
前端页面片段蓝图 - 提供 /init 与 /templates/<name>

模板由 backend/templates 提供（即 frontend/templates 的构建产物）。
"""

from flask import Blueprint, render_template, jsonify

# 创建蓝图（不指定 template_folder，复用应用的 backend/templates）
frontend_bp = Blueprint('frontend', __name__)


@frontend_bp.route('/init')
def init_page():
    """初始化页面"""
    return render_template('init.html')


@frontend_bp.route('/templates/<template_name>')
def get_template(template_name):
    """提供页面片段模板"""
    try:
        # 确保只提供允许的模板文件
        allowed_templates = ['dashboard.html', 'cookie.html', 'apps.html', 'settings.html']

        if template_name not in allowed_templates:
            return jsonify({'error': 'Template not found'}), 404

        return render_template(template_name)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
