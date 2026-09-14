#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP 更新模块
负责：企业微信可信 IP 的更新操作
注意：此模块使用企业微信 API 直接更新，不依赖浏览器自动化
      如果官方 API 变更，只需修改此文件
"""

import requests
import random
from backend.configmanager import logger
from backend.database import get_auth_info, save_auth_info, update_app_trusted_ip


def update_ip_for_app(app_id, new_ip, cookies=None, app_name=None):
    """
    使用API直接更新企业微信可信IP

    参数:
        app_id: 应用ID
        new_ip: 新的IP地址
        cookies: 可选，Cookie字符串。如果不提供，从数据库获取
        app_name: 可选，应用名称。如果不提供，从数据库获取

    返回: (success: bool, message: str, trusted_ip: str)
    """
    # 如果未提供应用名称，从数据库获取
    if app_name is None:
        from backend.database import get_app_ids
        apps = get_app_ids()
        app = next((a for a in apps if a['app_id'] == app_id), None)
        app_name = app['app_name'] if app else app_id
    
    logger.info(f"开始更新应用 {app_name} ({app_id}) 的IP白名单为 {new_ip}...")
    
    try:
        # 如果没有提供cookies，从数据库获取
        if not cookies:
            auth_info = get_auth_info()
            cookies = auth_info.get('cookies')
        
        if not cookies:
            return False, "未登录，无法更新IP", None
        
        # 解析Cookie字符串
        cookie_dict = {}
        for cookie in cookies.split(';'):
            cookie = cookie.strip()
            if '=' in cookie:
                key, value = cookie.split('=', 1)
                cookie_dict[key] = value
        
        # 检查关键Cookie是否存在
        required_cookies = ['wwrtx.sid', 'wwrtx.ltype', 'wwrtx.refid']
        missing_cookies = [c for c in required_cookies if c not in cookie_dict]
        if missing_cookies:
            return False, f"Cookie格式错误: 缺少{missing_cookies}", None
        
        # 构建Cookie字符串用于请求头
        cookie_header = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])
        
        # 构建API请求参数
        params = {
            'lang': 'zh_CN',
            'f': 'json',
            'ajax': '1',
            'timeZoneInfo[zone_offset]': '-8',
            'random': str(random.random())
        }
        
        # 表单数据
        data = [
            ('app_id', app_id),
            ('ipList[]', new_ip)
        ]
        
        # API请求URL
        api_url = "https://work.weixin.qq.com/wework_admin/apps/saveIpConfig"
        
        logger.info(f"发送API请求到: {api_url}")
        
        # 发送POST请求
        headers = {
            'Cookie': cookie_header,
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://work.weixin.qq.com/wework_admin/frame',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://work.weixin.qq.com'
        }
        
        response = requests.post(api_url, params=params, data=data, headers=headers, timeout=30)
        logger.info(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                logger.debug(f"API响应: {result}")
                
                # 检查是否有errCode字段
                if 'errCode' in result:
                    err_code = result.get('errCode')
                    if err_code == 0:
                        logger.info(f"应用 {app_name} ({app_id}) IP更新成功")
                        # 从API响应中获取实际的可信IP列表
                        ip_list = result.get('data', {}).get('ipList', [])
                        if ip_list:
                            trusted_ip = ', '.join(ip_list)
                            logger.info(f"应用 {app_name} ({app_id}) 实际可信IP: {trusted_ip}")
                        else:
                            trusted_ip = ''
                        # 保存可信IP到数据库
                        update_app_trusted_ip(app_id, trusted_ip)
                        return True, f"IP更新成功: {new_ip}", trusted_ip
                    else:
                        error_msg = result.get('message', '未知错误')
                        if err_code == -3:
                            # Cookie失效，清空数据库
                            save_auth_info(cookies=None, is_logged_in=False)
                            return False, "Cookie已失效，请重新导入有效的Cookie", None
                        elif err_code == -2:
                            return False, f"参数错误: {error_msg}", None
                        else:
                            return False, f"API调用失败: {error_msg}", None

                # 检查是否有errcode字段（旧格式）
                elif 'errcode' in result:
                    if result.get('errcode') == 0:
                        logger.info(f"应用 {app_name} ({app_id}) IP更新成功")
                        # 从API响应中获取实际的可信IP列表
                        ip_list = result.get('data', {}).get('ipList', [])
                        if ip_list:
                            trusted_ip = ', '.join(ip_list)
                            logger.info(f"应用 {app_name} ({app_id}) 实际可信IP: {trusted_ip}")
                        else:
                            trusted_ip = ''
                        # 保存可信IP到数据库
                        update_app_trusted_ip(app_id, trusted_ip)
                        return True, f"IP更新成功: {new_ip}", trusted_ip
                    else:
                        return False, f"API调用失败: {result.get('errmsg', '未知错误')}", None

                # 检查是否有"reject_subadmin_ids"字段
                elif 'data' in result and 'reject_subadmin_ids' in result['data']:
                    if result['data']['reject_subadmin_ids']:
                        return False, f"权限不足: 被拒绝的管理员ID: {result['data']['reject_subadmin_ids']}", None
                    else:
                        logger.info(f"应用 {app_name} ({app_id}) IP更新成功")
                        # 从API响应中获取实际的可信IP列表
                        ip_list = result.get('data', {}).get('ipList', [])
                        if ip_list:
                            trusted_ip = ', '.join(ip_list)
                            logger.info(f"应用 {app_name} ({app_id}) 实际可信IP: {trusted_ip}")
                        else:
                            trusted_ip = ''
                        # 保存可信IP到数据库
                        update_app_trusted_ip(app_id, trusted_ip)
                        return True, f"IP更新成功: {new_ip}", trusted_ip

                # 检查其他可能的成功标识
                elif result.get('ret') == 0 or result.get('success') == True:
                    logger.info(f"应用 {app_name} ({app_id}) IP更新成功")
                    # 从API响应中获取实际的可信IP列表
                    ip_list = result.get('data', {}).get('ipList', [])
                    if ip_list:
                        trusted_ip = ', '.join(ip_list)
                        logger.info(f"应用 {app_name} ({app_id}) 实际可信IP: {trusted_ip}")
                    else:
                        trusted_ip = ''
                    # 保存可信IP到数据库
                    update_app_trusted_ip(app_id, trusted_ip)
                    return True, f"IP更新成功: {new_ip}", trusted_ip
                else:
                    logger.warning(f"响应格式异常: {result}")
                    return False, "API响应格式异常", None
                    
            except ValueError as e:
                logger.error(f"JSON解析错误: {e}")
                if 'success' in response.text.lower() or '保存成功' in response.text:
                    # 从API响应中获取实际的可信IP列表
                    try:
                        result = response.json()
                        ip_list = result.get('data', {}).get('ipList', [])
                        if ip_list:
                            trusted_ip = ', '.join(ip_list)
                            logger.info(f"应用 {app_name} ({app_id}) 实际可信IP: {trusted_ip}")
                        else:
                            trusted_ip = ''
                    except:
                        trusted_ip = ''
                    # 保存可信IP到数据库
                    update_app_trusted_ip(app_id, trusted_ip)
                    return True, f"IP更新成功: {new_ip}", trusted_ip
                else:
                    return False, f"响应解析失败: {response.text[:200]}", None
        else:
            return False, f"HTTP请求失败: {response.status_code}", None
            
    except Exception as e:
        logger.error(f"更新IP失败: {e}")
        return False, f"执行过程中出错: {str(e)}", None


def update_ip_for_all_apps(new_ip, cookies=None):
    """
    为所有启用的应用更新IP白名单
    
    参数:
        new_ip: 新的IP地址
        cookies: 可选，Cookie字符串
    
    返回: (all_success: bool, results: list)
    """
    apps = get_enabled_app_ids()
    if not apps:
        return False, [{"error": "没有配置启用的应用ID"}]
    
    results = []
    all_success = True
    
    for app in apps:
        app_id = app['app_id']
        app_name = app.get('app_name', '')
        success, message, _ = update_ip_for_app(app_id, new_ip, cookies, app_name)
        results.append({
            'app_id': app_id,
            'app_name': app_name,
            'success': success,
            'message': message
        })
        if not success:
            all_success = False
    
    return all_success, results

