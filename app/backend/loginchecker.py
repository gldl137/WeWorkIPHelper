#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
登录状态检查模块

提供登录状态验证功能，包括：
1. 本地Cookie格式验证
2. 通过访问企业微信首页验证登录状态（同时保持Cookie活跃）
"""

import requests
from backend.database import get_auth_info, save_auth_info
from backend.configmanager import logger


def validate_cookie_format(cookies):
    """
    验证Cookie格式（本地验证，不发起网络请求）

    参数:
        cookies: Cookie字符串

    返回: (is_valid: bool, message: str)
    """
    if not cookies:
        return False, "Cookie不能为空"

    # 检查必要的Cookie字段
    if 'wwrtx.sid' not in cookies:
        return False, "Cookie格式不正确，缺少必要的登录凭证"

    if 'wwrtx.vid' not in cookies:
        return False, "Cookie格式不正确，缺少必要的用户ID"

    # 检查Cookie长度
    if len(cookies) < 100:
        return False, "Cookie内容太短，可能不完整"

    return True, "Cookie格式正确"


def check_login_by_homepage():
    """
    通过访问企业微信首页验证登录状态
    同时保持Cookie活跃，防止过期

    返回: (is_logged_in: bool, message: str)
    """
    try:
        # 获取当前认证信息
        auth_info = get_auth_info()

        # 检查是否有Cookie
        cookies = auth_info.get('cookies', '')
        if not cookies:
            return False, "Cookie为空"

        # 解析Cookie字符串
        cookie_dict = {}
        for cookie in cookies.split(';'):
            cookie = cookie.strip()
            if '=' in cookie:
                key, value = cookie.split('=', 1)
                cookie_dict[key] = value

        # 检查关键Cookie
        required_cookies = ['wwrtx.sid', 'wwrtx.ltype', 'wwrtx.refid']
        missing_cookies = [c for c in required_cookies if c not in cookie_dict]
        if missing_cookies:
            return False, f"Cookie不完整，缺少: {', '.join(missing_cookies)}"

        # 构建Cookie字符串用于请求
        cookie_header = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])

        # 访问企业微信首页
        headers = {
            'Cookie': cookie_header,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://work.weixin.qq.com/',
        }

        logger.info("[登录检查] 正在访问企业微信首页验证登录状态")

        response = requests.get(
            'https://work.weixin.qq.com/wework_admin/frame',
            headers=headers,
            timeout=30,
            allow_redirects=True
        )

        # 检查响应
        if response.status_code == 200:
            # 检查是否被重定向到登录页
            if 'login' in response.url.lower() or 'auth' in response.url.lower():
                logger.warning("[登录检查] Cookie已失效，被重定向到登录页")
                # 清空数据库中的登录状态
                save_auth_info(cookies=None, is_logged_in=False)
                return False, "Cookie已失效，需要重新登录"

            # 检查页面内容是否包含登录相关的错误信息
            if '请重新登录' in response.text or '登录超时' in response.text:
                logger.warning("[登录检查] 页面显示需要重新登录")
                save_auth_info(cookies=None, is_logged_in=False)
                return False, "会话已过期，需要重新登录"

            logger.info("[登录检查] 登录验证成功，Cookie有效")
            return True, "登录状态正常"
        else:
            logger.warning(f"[登录检查] HTTP错误: {response.status_code}")
            return False, f"访问失败: HTTP {response.status_code}"

    except requests.exceptions.Timeout:
        logger.error("[登录检查] 请求超时")
        return False, "请求超时，网络连接异常"
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[登录检查] 网络连接失败: {e}")
        return False, "网络连接失败，请检查网络"
    except Exception as e:
        logger.error(f"[登录检查] 验证登录状态异常: {e}")
        return False, f"验证失败: {str(e)}"


def check_login_status():
    """
    主要的登录状态检查函数
    优先检查本地状态，然后访问首页验证

    返回: (is_logged_in: bool, message: str)
    """
    try:
        # 获取当前认证信息
        auth_info = get_auth_info()

        # 检查是否已登录
        if not auth_info.get('is_logged_in', False):
            return False, "未登录"

        # 检查是否有Cookie
        cookies = auth_info.get('cookies', '')
        if not cookies:
            return False, "Cookie为空"

        # 先进行本地Cookie格式验证
        is_valid, message = validate_cookie_format(cookies)
        if not is_valid:
            return False, message

        # 通过访问首页验证登录状态
        return check_login_by_homepage()

    except Exception as e:
        logger.error(f"检查登录状态失败: {e}")
        return False, f"检查失败: {str(e)}"
