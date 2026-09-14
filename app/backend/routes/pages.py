#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
页面路由 - 返回 HTML
"""

from flask import render_template
from backend.database import is_initial_config_needed, get_system_config


def register_page_routes(app):
    """注册页面路由"""
    
    @app.route('/')
    def index():
        """主页面 - 检查是否需要初始化向导"""
        need_init = is_initial_config_needed()
        config = get_system_config()
        
        return render_template(
            'index.html',  # 使用新的模块化模板
            need_init=need_init,
            # 安全考虑：不再把管理密码注入页面。
            # 前端首次访问会要求输入密码，用 /api/verify_password 换取随机 token 作鉴权，
            # 这样日常请求头里只出现随机 token，抓包不会泄露密码。
            api_token='',
            webhook_url=config['wecom_webhook_url'] if config['wecom_webhook_url'] else ''
        )
    
    # 注册页面片段蓝图（由 backend/routes/frontend.py 提供）
    from backend.routes.frontend import frontend_bp
    app.register_blueprint(frontend_bp)