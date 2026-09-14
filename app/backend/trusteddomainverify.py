#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可信域名验证应用 - 独立Flask应用
监听1109端口，用于企业微信可信域名验证
"""

import os
import logging
from flask import Flask, request
from backend.configmanager import logger, DATA_DIR

# 禁用werkzeug的默认日志
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# 创建独立的Flask应用
verify_app = Flask(__name__)

# 记录HTTP请求，只输出到控制台，不写入前台日志文件
@verify_app.after_request
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

# 确保WW_verify文件夹存在
WW_VERIFY_DIR = os.path.join(DATA_DIR, 'WW_verify')
os.makedirs(WW_VERIFY_DIR, exist_ok=True)


@verify_app.route("/", defaults={"path": ""})
@verify_app.route("/<path:path>")
def catch_all(path):
    """返回WW_verify文件夹中的txt文件内容"""
    try:
        # 检查验证服务是否启用
        from backend.database import get_system_config
        config = get_system_config()
        verify_enabled = config.get('verify_enabled', 1)
        # SQLite 返回的是整数 0 或 1，需要正确判断
        if verify_enabled == 0 or verify_enabled == False:
            return "验证服务已禁用", 503
        
        # 查找WW_verify文件夹中的txt文件
        txt_files = [f for f in os.listdir(WW_VERIFY_DIR) if f.endswith('.txt')]
        
        if not txt_files:
            return "未找到验证文件", 404
        
        # 返回第一个txt文件的内容
        txt_file = txt_files[0]
        file_path = os.path.join(WW_VERIFY_DIR, txt_file)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return content, 200
    except Exception as e:
        logger.error(f"读取验证文件失败: {e}")
        return "读取验证文件失败", 500


def run_verify_app(host='127.0.0.1', port=5001):
    """运行验证应用"""
    verify_app.run(host=host, port=port, debug=False)
