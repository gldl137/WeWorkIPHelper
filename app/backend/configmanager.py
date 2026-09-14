#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行环境与全局配置
负责：Docker判断、路径配置、时区设置、日志初始化、密钥管理
"""

import os
import sys
import logging
import secrets

# ==================== 路径配置（必须先定义 DATA_DIR）====================
IS_DOCKER = os.path.exists('/.dockerenv')
DATA_DIR = "/app/data" if IS_DOCKER else os.path.join(os.getcwd(), "data")

# 确保数据目录存在
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

# ==================== 日志初始化 ====================
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone, timedelta, tzinfo

# 创建上海时区
class ShanghaiTimezone(tzinfo):
    """上海时区（UTC+8）"""
    def __init__(self):
        super().__init__()
        self.offset = timedelta(hours=8)
    
    def utcoffset(self, dt):
        return self.offset
    
    def tzname(self, dt):
        return "CST"
    
    def dst(self, dt):
        return timedelta(0)

# 自定义日志格式化器，使用上海时区
class ShanghaiFormatter(logging.Formatter):
    """使用上海时区的日志格式化器"""
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        self.shanghai_tz = ShanghaiTimezone()
    
    def formatTime(self, record, datefmt=None):
        """格式化时间为上海时区"""
        ct = self.converter(record.created)
        if datefmt:
            s = ct.strftime(datefmt)
        else:
            t = ct.strftime("%Y-%m-%d %H:%M:%S")
            s = "%s,%03d" % (t, record.msecs)
        return s
    
    def converter(self, timestamp):
        """将时间戳转换为上海时区"""
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return dt.astimezone(self.shanghai_tz)

# 后台完整日志（只输出到控制台，不生成文件）
# 前台简洁日志文件（只显示重要日志）
frontend_log_file = os.path.join(DATA_DIR, "weworkiphelper.log")

# 创建前台日志文件处理器，限制每个日志文件最大10MB，不保留备份
frontend_file_handler = RotatingFileHandler(
    frontend_log_file,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=0,  # 不保留备份
    encoding='utf-8',
    mode='a'
)

# 创建前台日志过滤器，只记录重要日志
class FrontendLogFilter(logging.Filter):
    """前台日志过滤器，过滤掉不必要的日志"""
    def filter(self, record):
        # 过滤掉werkzeug的HTTP请求日志
        if 'werkzeug' in record.name:
            return False
        # 过滤掉健康检查日志
        if 'GET /api/status' in record.getMessage():
            return False
        if 'GET /api/logs' in record.getMessage():
            return False
        # 过滤掉OPTIONS请求日志
        if 'OPTIONS' in record.getMessage() and 'HTTP/1.1' in record.getMessage():
            return False
        # 只记录INFO及以上级别的日志
        if record.levelno < logging.INFO:
            return False
        return True

# 创建前台日志处理器，同时写入前台文件和后台控制台
class DualHandler(logging.Handler):
    """双日志处理器，同时写入前台文件和后台控制台"""
    def __init__(self, frontend_file_handler):
        super().__init__()
        self.frontend_file_handler = frontend_file_handler
    
    def emit(self, record):
        # 始终输出到后台控制台（显示完整日志）
        print(self.format(record))
        
        # 只将重要日志写入前台文件
        if self.frontend_file_handler.filter(record):
            self.frontend_file_handler.emit(record)

# 配置后台完整日志（只输出到控制台）
backend_logger = logging.getLogger('backend')
backend_logger.setLevel(logging.INFO)

# 配置前台简洁日志
frontend_logger = logging.getLogger('frontend')
frontend_logger.setLevel(logging.INFO)

# 设置前台文件处理器格式（使用上海时区）
frontend_file_handler.setFormatter(ShanghaiFormatter('%(asctime)s - %(levelname)s - %(message)s'))
frontend_file_handler.addFilter(FrontendLogFilter())

# 设置控制台输出格式（显示完整日志，包括logger名称，使用上海时区）
console_formatter = ShanghaiFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 使用双日志处理器
dual_handler = DualHandler(frontend_file_handler)
dual_handler.setFormatter(console_formatter)
backend_logger.addHandler(dual_handler)

# 主logger（向后兼容）
logger = backend_logger

logger.info("前台日志文件已配置")

# ==================== Windows 控制台编码设置 ====================
if sys.platform == 'win32':
    try:
        import ctypes
        if hasattr(ctypes, 'windll'):
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# ==================== 路径配置继续 ====================
DB_PATH = os.path.join(DATA_DIR, "database.sqlite")
# SESSION_PATH 已废弃 - 系统切换到纯API模式，无需会话目录

# ==================== 时区设置（固定上海）====================
os.environ['TZ'] = 'Asia/Shanghai'
if sys.platform != 'win32':
    import time as time_module
    time_module.tzset()

# 时区常量
TIMEZONE = 'Asia/Shanghai'

# ==================== Secret Key 管理 ====================
def load_or_create_secret_key():
    """加载或创建 Secret Key"""
    secret_file = os.path.join(DATA_DIR, "secret.key")
    try:
        if os.path.exists(secret_file):
            with open(secret_file, "r") as f:
                logger.info("密钥文件加载成功")
                return f.read().strip()
        else:
            key = secrets.token_hex(24)
            with open(secret_file, "w") as f:
                f.write(key)
            logger.info("生成并保存新密钥")
            return key
    except Exception as e:
        logger.error(f"密钥初始化失败: {e}")
        return "default-fallback-key"
