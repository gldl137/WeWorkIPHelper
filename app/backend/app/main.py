#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信自动化运维系统 - Flask 应用入口
只负责：启动与装配

运行方式（工作目录必须为 app/，即 backend 的上一级目录）：
    cd app && python -m backend.app.main
"""

import os
import logging
from flask import Flask, request
from flask_cors import CORS

# 导入配置（从 backend 包）
from backend.configmanager import load_or_create_secret_key, logger

# 禁用werkzeug的默认日志
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# 导入数据库初始化
from backend.database import init_database

# 导入路由注册
from backend.routes import register_routes

# 导入任务调度器
from backend.taskscheduler import init_scheduler

# 导入可信域名验证应用
from backend.trusteddomainverify import run_verify_app

# 导入系统配置
from backend.database import get_system_config

# ==================== Flask 应用创建 ====================

# 配置模板和静态文件目录（相对本文件所在目录 backend/app/）
# 均指向前端构建产物（frontend/templates、frontend/src -> backend/templates、backend/static）
app = Flask(
    __name__,
    template_folder='../templates',
    static_folder='../static'
)

# 模板改动即时生效（无需重启后端即可读到前端构建产物的更新）
app.config['TEMPLATES_AUTO_RELOAD'] = True
# 静态资源不强缓存，避免修改后浏览器仍使用旧文件（页面引用另带 ?v= 版本号）
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# 配置 CORS，允许前端跨域访问
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 设置 Secret Key
app.secret_key = load_or_create_secret_key()

# 记录HTTP请求，只输出到控制台，不写入前台日志文件
@app.after_request
def log_request(response):
    """记录每个HTTP请求到控制台"""
    from backend.configmanager import ShanghaiFormatter
    formatter = ShanghaiFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    import logging
    record = logging.LogRecord(
        name='backend',
        level=logging.INFO,
        pathname='',
        lineno=0,
        msg=f'"{request.method} {request.path} HTTP/{request.environ.get("SERVER_PROTOCOL", "1.1")}" {response.status_code}',
        args=(),
        exc_info=None
    )
    print(formatter.format(record))
    return response

# ==================== 初始化 ====================

# 初始化数据库
if init_database():
    logger.info("数据库初始化成功")
else:
    logger.error("数据库初始化失败，请检查权限")

# 显示启动信息
logger.info("=" * 70)
env_type = "Docker" if os.environ.get('IS_DOCKER') == 'true' else "本地"
logger.info(f"企业微信IP自动更新系统启动中... [{env_type}] 端口: {os.environ.get('PORT', 5000)}/{os.environ.get('VERIFY_PORT', 5001)}")
logger.info("系统已切换到纯API模式，无需浏览器")
logger.info("=" * 70)

# 注册所有路由
register_routes(app)

# 启动任务调度器
init_scheduler()

# ==================== 应用启动 ====================

if __name__ == '__main__':
    import threading
    
    # 启动参数
    port = int(os.environ.get('PORT', 1110))
    host = os.environ.get('HOST', '0.0.0.0')
    
    # 检查是否启用验证服务
    config = get_system_config()
    verify_enabled = config.get('verify_enabled', 1)
    
    if verify_enabled:
        # 在后台线程中启动验证服务（守护线程）
        verify_port = int(os.environ.get('VERIFY_PORT', 1109))
        logger.info(f"启动可信域名验证应用，监听地址: {host}:{verify_port}")
        verify_thread = threading.Thread(
            target=lambda: run_verify_app(host=host, port=verify_port), 
            daemon=True  # 守护线程，主应用退出时自动结束
        )
        verify_thread.start()
    else:
        logger.info("可信域名验证服务已禁用，不启动验证应用")
    
    # 主应用作为主线程运行（不使用 daemon，确保稳定运行）
    logger.info("=" * 70)
    logger.info(f"应用启动完成 [{host}:{port}] (按 Ctrl+C 停止)")
    logger.info("=" * 70)
    
    try:
        app.run(host=host, port=port, debug=False)
    except KeyboardInterrupt:
        logger.info("应用已停止")
