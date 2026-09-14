#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公网 IP 获取模块
负责：获取当前公网 IP 地址
说明：支持多个 IP 检测源，自动切换
"""

import requests
from backend.configmanager import logger

# IP 检测地址列表
IP_CHECK_URLS = [
    'https://ddns.oray.com/checkip',
    'http://v4.66666.host:66/ip',
    'https://myip.ipip.net',
    'https://4.ipw.cn',
    'https://ip.3322.net'
]


def validate_ip(ip):
    """
    验证IP地址格式是否有效
    参数: ip - IP地址字符串
    返回: bool
    """
    if not ip or '.' not in ip:
        return False

    parts = ip.split('.')
    if len(parts) != 4:
        return False

    for part in parts:
        try:
            num = int(part)
            if num < 0 or num > 255:
                return False
        except ValueError:
            return False

    return True


def get_current_public_ip():
    """
    获取当前公网IP地址
    依次尝试多个检测源，直到成功获取有效IP
    返回: str - IP地址，或 None（获取失败）
    """
    for url in IP_CHECK_URLS:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.text.strip()

                # 解析不同格式的IP地址
                if 'Current IP Address:' in data:
                    # ddns.oray.com 格式: "Current IP Address: 221.234.198.194"
                    ip = data.split('Current IP Address:')[1].strip()
                elif '当前 IP：' in data:
                    # myip.ipip.net 格式: "当前 IP：221.234.198.194  来自于：中国 湖北 武汉  电信"
                    ip = data.split('当前 IP：')[1].split(' ')[0].strip()
                elif ' ' in data and '.' in data:
                    # v4.66666.host 格式: "221.234.198.194   lucky666.cn"
                    ip = data.split(' ')[0].strip()
                else:
                    # 其他格式直接返回（如纯IP地址）
                    ip = data

                # 验证IP地址格式
                if validate_ip(ip):
                    return ip
                else:
                    logger.warning(f"从 {url} 获取的IP格式无效: {data}")
                    continue

        except Exception as e:
            logger.warning(f"从 {url} 获取IP失败: {e}")
            continue

    logger.error("所有IP检测地址都不可用")
    return None
