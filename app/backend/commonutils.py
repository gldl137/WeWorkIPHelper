#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
纯业务工具函数
与 HTTP/Flask 无关，可独立运行
"""

import requests
from datetime import datetime, timezone
from backend.database import get_system_config


def send_notification(notify_url, message):
    """发送通知到指定URL"""
    if not notify_url:
        return False, "通知URL未配置"

    try:
        response = requests.post(
            notify_url,
            json={'message': message, 'timestamp': datetime.now(timezone.utc).astimezone().isoformat()},
            timeout=10
        )
        if response.status_code == 200:
            return True, "通知发送成功"
        else:
            return False, f"通知发送失败，状态码: {response.status_code}"
    except Exception as e:
        return False, f"通知发送异常: {str(e)}"


def send_wecom_webhook(webhook_url, content):
    """发送企业微信机器人消息（图文消息格式）"""
    if not webhook_url:
        return False, "Webhook URL未配置"
    
    # 检查通知是否启用
    config = get_system_config()
    notification_enabled = config.get('notification_enabled', 1)
    if not notification_enabled or notification_enabled == 0:
        return False, "通知已禁用"
    
    try:
        # 将文本内容转换为图文消息格式
        lines = content.strip().split('\n')
        title = lines[0] if lines else "企业微信IP更新通知"
        # 描述排除最后一行（时间）
        description = '\n'.join(lines[1:-1]) if len(lines) > 2 else ('\n'.join(lines[1:]) if len(lines) > 1 else content)
        
        # 构建图文消息
        message = {
            'msgtype': 'news',
            'news': {
                'articles': [
                    {
                        'title': title,
                        'description': description,
                        'url': 'https://wxip.137967630.xyz:8888',
                        'picurl': 'https://gitee.com/gldl137/wechat-work-bot/raw/master/images/WXIP.jpg'
                    }
                ]
            }
        }
        
        response = requests.post(
            webhook_url,
            json=message,
            timeout=10
        )
        result = response.json()
        if result.get('errcode') == 0:
            return True, "Webhook发送成功"
        else:
            return False, f"Webhook发送失败: {result.get('errmsg')}"
    except Exception as e:
        return False, f"Webhook发送异常: {str(e)}"


def format_datetime(dt, format_str='%Y-%m-%d %H:%M:%S'):
    """格式化日期时间"""
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except:
            return dt
    return dt.strftime(format_str)


def time_diff_text(last_time):
    """计算时间差并返回文本描述"""
    if not last_time:
        return "从未"

    try:
        if isinstance(last_time, str):
            last_time = datetime.fromisoformat(last_time.replace('Z', '+00:00'))

        diff = datetime.now(timezone.utc).astimezone() - last_time
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return f"{int(seconds)}秒前"
        elif seconds < 3600:
            return f"{int(seconds / 60)}分钟前"
        elif seconds < 86400:
            return f"{int(seconds / 3600)}小时前"
        else:
            return f"{int(seconds / 86400)}天前"
    except:
        return str(last_time)
