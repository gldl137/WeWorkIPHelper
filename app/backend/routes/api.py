#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 路由 - 返回 JSON
"""

from flask import jsonify, request
from datetime import datetime, timezone
from functools import wraps
from backend.configmanager import logger, DATA_DIR
from backend.database import (
    get_system_config, save_system_config, is_initial_config_needed,
    get_app_ids, save_app_id, delete_app_id, toggle_app_enabled,
    get_auth_info, save_auth_info, clear_auth_info, get_ip_status, update_ip_status,
    add_ip_update_history, get_enabled_app_ids
)
from backend.publicipfetcher import get_current_public_ip
# 浏览器功能已移除，使用纯API模式
from backend.loginchecker import check_login_status
from backend.ip_updater import update_ip_for_app
from backend.taskscheduler import get_scheduler
from backend.commonutils import send_wecom_webhook


def require_api_key(f):
    """API密钥验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        config = get_system_config()
        admin_token = config.get('admin_token', '')
        
        # 如果没有设置管理员token，允许访问（初始化阶段）
        if not admin_token:
            return f(*args, **kwargs)
        
        # 获取请求中的API密钥
        api_key = request.headers.get('X-API-KEY')
        
        # 验证API密钥（支持旧密码和新的token）
        from backend.database import validate_auth_token, cleanup_expired_tokens
        
        # 先尝试验证token
        if api_key and validate_auth_token(api_key):
            # Token有效，清理过期token
            cleanup_expired_tokens()
            return f(*args, **kwargs)
        
        # 如果token验证失败，尝试验证密码（向后兼容）
        if api_key and api_key == admin_token:
            return f(*args, **kwargs)
        
        # 都验证失败
        return jsonify({
            'success': False, 
            'message': '未授权访问，请重新登录',
            'need_auth': True,
            'admin_token_exists': bool(admin_token)  # 告诉前端是否已设置密码
        }), 401
    
    return decorated_function


def register_api_routes(app):
    """注册 API 路由"""
    
    # ==================== 系统状态 API ====================
    
    @app.route('/api/status')
    @require_api_key
    def api_status():
        """获取系统状态"""
        try:
            # 获取应用数量
            apps = get_app_ids()
            app_count = len(apps)
            
            # 从数据库获取登录状态（持久化）
            auth_info = get_auth_info()
            is_logged_in = auth_info.get('is_logged_in', False)
            last_login_time = auth_info.get('last_login_time')
            
            # 从数据库获取IP状态（持久化）
            ip_status = get_ip_status()
            
            # 获取当前IP（实时检测）
            current_ip = get_current_public_ip()
            
            status_data = {
                'is_logged_in': is_logged_in,
                'last_check_time': last_login_time,
                'current_ip': current_ip,
                'last_updated_ip': ip_status.get('last_updated_ip'),
                'update_status': ip_status.get('update_status'),
                'last_update_time': ip_status.get('last_update_time'),
                'app_count': app_count,
                'cookies': auth_info.get('cookies'),
                'cookie_saved_time': auth_info.get('updated_at'),
                'message': '从数据库读取持久化状态'
            }
            
            return jsonify(status_data)
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    # ==================== 验证文件管理 API ====================
    
    @app.route('/api/verify/files', methods=['GET'])
    @require_api_key
    def api_get_verify_files():
        """获取验证文件列表"""
        try:
            import os
            from backend.configmanager import DATA_DIR
            
            WW_VERIFY_DIR = os.path.join(DATA_DIR, 'WW_verify')
            os.makedirs(WW_VERIFY_DIR, exist_ok=True)
            
            files = [f for f in os.listdir(WW_VERIFY_DIR) if f.endswith('.txt')]
            return jsonify({'success': True, 'files': files})
        except Exception as e:
            logger.error(f"获取验证文件列表失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/verify/upload', methods=['POST'])
    @require_api_key
    def api_upload_verify_file():
        """上传验证文件"""
        try:
            import os
            from backend.configmanager import DATA_DIR
            
            WW_VERIFY_DIR = os.path.join(DATA_DIR, 'WW_verify')
            os.makedirs(WW_VERIFY_DIR, exist_ok=True)
            
            if 'file' not in request.files:
                return jsonify({'success': False, 'message': '未选择文件'}), 400
            
            file = request.files['file']
            
            if file.filename == '':
                return jsonify({'success': False, 'message': '未选择文件'}), 400
            
            if not file.filename.endswith('.txt'):
                return jsonify({'success': False, 'message': '只能上传txt文件'}), 400
            
            # 保存文件
            file_path = os.path.join(WW_VERIFY_DIR, file.filename)
            file.save(file_path)
            
            logger.info(f"验证文件已上传: {file.filename}")
            return jsonify({'success': True, 'message': '文件上传成功'})
        except Exception as e:
            logger.error(f"上传验证文件失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/verify/files/<filename>', methods=['DELETE'])
    @require_api_key
    def api_delete_verify_file(filename):
        """删除验证文件"""
        try:
            import os
            from backend.configmanager import DATA_DIR
            
            WW_VERIFY_DIR = os.path.join(DATA_DIR, 'WW_verify')
            file_path = os.path.join(WW_VERIFY_DIR, filename)
            
            if not os.path.exists(file_path):
                return jsonify({'success': False, 'message': '文件不存在'}), 404
            
            os.remove(file_path)
            logger.info(f"验证文件已删除: {filename}")
            return jsonify({'success': True, 'message': '文件已删除'})
        except Exception as e:
            logger.error(f"删除验证文件失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/verify/toggle', methods=['POST'])
    @require_api_key
    def api_toggle_verify_service():
        """切换验证服务状态"""
        try:
            data = request.get_json()
            enabled = data.get('enabled', True)
            
            save_system_config(verify_enabled=enabled)
            
            logger.info(f"验证服务状态已更新: {'启用' if enabled else '禁用'}")
            return jsonify({'success': True, 'message': f"验证服务已{'启用' if enabled else '禁用'}"})
        except Exception as e:
            logger.error(f"切换验证服务状态失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/notification/toggle', methods=['POST'])
    @require_api_key
    def api_toggle_notification():
        """切换通知状态"""
        try:
            data = request.get_json()
            enabled = data.get('enabled', True)
            
            save_system_config(notification_enabled=enabled)
            
            logger.info(f"通知状态已更新: {'启用' if enabled else '禁用'}")
            return jsonify({'success': True, 'message': f"通知已{'启用' if enabled else '禁用'}"})
        except Exception as e:
            logger.error(f"切换通知状态失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/health')
    def health_check():
        """健康检查"""
        config = get_system_config()
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.now(timezone.utc).astimezone().isoformat(),
            'verify_service_enabled': config.get('verify_enabled', 1)
        })
    
    @app.route('/api/check_init')
    def api_check_init_status():
        """检查是否需要初始化"""
        try:
            need_init = is_initial_config_needed()
            return jsonify({
                'success': True,
                'need_init': need_init
            })
        except Exception as e:
            logger.error(f"检查初始化状态失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/verify_password', methods=['POST'])
    def api_verify_password():
        """验证管理员密码，返回认证token"""
        try:
            data = request.get_json()
            password = data.get('password', '')
            
            if not password:
                return jsonify({
                    'success': False,
                    'message': '密码不能为空'
                }), 400
            
            # 获取系统配置中的管理员token
            config = get_system_config()
            admin_token = config.get('admin_token', '')
            
            if not admin_token:
                return jsonify({
                    'success': False,
                    'message': '系统未初始化，请先设置管理员密码'
                }), 400
            
            # 验证密码是否匹配
            if password == admin_token:
                # 生成认证token
                from backend.database import generate_auth_token
                auth_token = generate_auth_token()
                
                return jsonify({
                    'success': True,
                    'message': '密码验证成功',
                    'token': auth_token
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '密码错误'
                }), 401
                
        except Exception as e:
            logger.error(f"验证密码失败: {e}")
            return jsonify({
                'success': False,
                'message': f'验证失败: {str(e)}'
            }), 500
    
    # ==================== 配置管理 API ====================
    
    @app.route('/api/config', methods=['GET', 'POST'])
    @require_api_key
    def api_config():
        """系统配置管理"""
        if request.method == 'GET':
            config = get_system_config()
            return jsonify({'success': True, 'config': config})
        
        elif request.method == 'POST':
            data = request.get_json()
            try:
                admin_token = data.get('admin_token')
                wecom_webhook_url = data.get('wecom_webhook_url')
                login_check_interval = data.get('login_check_interval')
                public_ip_check_interval = data.get('public_ip_check_interval')
                login_check_cron = data.get('login_check_cron')
                public_ip_check_cron = data.get('public_ip_check_cron')
                notification_enabled = data.get('notification_enabled')

                # 必须使用关键字参数：save_system_config 的形参顺序与这里的字段顺序不同，
                # 用位置参数会把 cron 写进 verify_enabled / notification_enabled 字段。
                save_system_config(
                    admin_token=admin_token,
                    wecom_webhook_url=wecom_webhook_url,
                    login_check_interval=login_check_interval,
                    public_ip_check_interval=public_ip_check_interval,
                    notification_enabled=notification_enabled,
                    login_check_cron=login_check_cron,
                    public_ip_check_cron=public_ip_check_cron
                )
                
                if admin_token:
                    # 修改了管理密码：清空已签发的 token，强制所有设备重新登录
                    from backend.database import clear_all_auth_tokens
                    clear_all_auth_tokens()

                logger.info("系统配置已更新")
                return jsonify({'success': True, 'message': '配置已保存'})
            except Exception as e:
                logger.error(f"保存配置失败: {e}")
                return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/config/test-webhook', methods=['POST'])
    @require_api_key
    def api_test_webhook():
        """测试Webhook配置"""
        try:
            import requests
            
            data = request.get_json()
            webhook_url = data.get('webhook_url')
            
            if not webhook_url:
                return jsonify({'success': False, 'message': 'Webhook地址不能为空'}), 400
            
            # 发送测试消息
            test_message = {
                'msgtype': 'text',
                'text': {
                    'content': '企微 IP 助手测试消息：Webhook 配置成功！'
                }
            }
            
            response = requests.post(webhook_url, json=test_message, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    return jsonify({'success': True, 'message': '测试消息已发送，请检查企业微信群'})
                else:
                    return jsonify({
                        'success': False, 
                        'message': f"发送失败: {result.get('errmsg', '未知错误')}"
                    }), 400
            else:
                return jsonify({
                    'success': False,
                    'message': f"HTTP错误: {response.status_code}"
                }), response.status_code
                
        except requests.exceptions.Timeout:
            return jsonify({'success': False, 'message': '请求超时，请检查Webhook地址是否正确'}), 500
        except requests.exceptions.ConnectionError:
            return jsonify({'success': False, 'message': '网络连接失败，请检查Webhook地址是否可访问'}), 500
        except Exception as e:
            logger.error(f"测试Webhook失败: {e}")
            return jsonify({'success': False, 'message': f'测试失败: {str(e)}'}), 500
    
    # ==================== 登录相关 API ====================
    
    @app.route('/api/check_login')
    @require_api_key
    def api_check_login():
        """检查登录状态"""
        try:
            is_logged_in, message = check_login_status()
            return jsonify({
                'success': True,
                'is_logged_in': is_logged_in,
                'message': message
            })
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/save_cookies', methods=['POST'])
    @require_api_key
    def api_save_cookies():
        """保存Cookie"""
        data = request.get_json()
        cookies = data.get('cookies', '')
        
        if not cookies:
            return jsonify({'success': False, 'message': 'Cookie不能为空'}), 400
        
        try:
            save_auth_info(cookies, True)
            logger.info("Cookie已保存")
            
            return jsonify({'success': True, 'message': 'Cookie已保存'})
        except Exception as e:
            logger.error(f"保存Cookie失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/test_cookies', methods=['POST'])
    @require_api_key
    def api_test_cookies():
        """测试Cookie有效性"""
        data = request.get_json()
        cookies = data.get('cookies', '')
        
        if not cookies:
            return jsonify({'success': False, 'message': 'Cookie不能为空'}), 400
        
        try:
            # 简单的Cookie格式验证
            if 'wwrtx.sid' not in cookies:
                return jsonify({'success': False, 'message': 'Cookie格式不正确，缺少必要的登录凭证'})
            
            if 'wwrtx.vid' not in cookies:
                return jsonify({'success': False, 'message': 'Cookie格式不正确，缺少必要的用户ID'})
            
            # 检查Cookie长度
            if len(cookies) < 100:
                return jsonify({'success': False, 'message': 'Cookie内容太短，可能不完整'})
            
            logger.info("Cookie格式验证通过")
            return jsonify({'success': True, 'message': 'Cookie格式正确，可以正常使用'})
            
        except Exception as e:
            logger.error(f"测试Cookie失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/clear_cookies', methods=['POST'])
    @require_api_key
    def api_clear_cookies():
        """清除Cookie"""
        try:
            clear_auth_info()
            logger.info("Cookie已清除")
            
            return jsonify({'success': True, 'message': 'Cookie已清除'})
        except Exception as e:
            logger.error(f"清除Cookie失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/logout', methods=['POST'])
    def api_logout():
        """退出登录 - 仅清除前端认证状态，不影响微信Cookie"""
        try:
            # 注意：此接口仅通知前端清除本地存储的apiToken
            # 不清除数据库中的微信Cookie，也不清除admin_token
            # 微信Cookie只能通过 /api/clear_cookies 接口清除

            logger.info("用户已退出登录（仅前端状态）")

            return jsonify({'success': True, 'message': '退出登录成功'})
        except Exception as e:
            logger.error(f"退出登录失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    # 浏览器功能已移除 - 使用纯API模式
    

    
    # ==================== 应用管理 API ====================
    
    @app.route('/api/apps', methods=['GET', 'POST'])
    @require_api_key
    def api_apps():
        """应用管理"""
        if request.method == 'GET':
            try:
                apps = get_app_ids()
                return jsonify({'success': True, 'apps': apps})
            except Exception as e:
                logger.error(f"获取应用列表失败: {e}")
                return jsonify({'success': False, 'message': str(e)}), 500
        
        elif request.method == 'POST':
            data = request.get_json()
            app_id = data.get('app_id')
            app_name = data.get('app_name', '')
            remark = data.get('remark', '')

            if not app_name:
                return jsonify({'success': False, 'message': '应用名称不能为空'}), 400

            if not app_id:
                return jsonify({'success': False, 'message': '应用ID不能为空'}), 400

            try:
                save_app_id(app_id, app_name, remark)
                logger.info(f"应用 {app_name} ({app_id}) 已添加")
                return jsonify({'success': True, 'message': '应用已添加'})
            except Exception as e:
                logger.error(f"添加应用失败: {e}")
                return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/apps/<app_id>', methods=['DELETE', 'PUT'])
    @require_api_key
    def api_delete_app(app_id):
        """删除应用或更新应用名称"""
        if request.method == 'DELETE':
            try:
                delete_app_id(app_id)
                logger.info(f"应用 {app_id} 已删除")
                return jsonify({'success': True, 'message': '应用已删除'})
            except Exception as e:
                logger.error(f"删除应用失败: {e}")
                return jsonify({'success': False, 'message': str(e)}), 500
        elif request.method == 'PUT':
            try:
                data = request.get_json()
                app_name = data.get('app_name', '').strip()

                if not app_name:
                    return jsonify({'success': False, 'message': '应用名称不能为空'}), 400

                # 更新应用名称
                from backend.database import update_app_name
                update_app_name(app_id, app_name)
                logger.info(f"应用 {app_id} 名称已更新为: {app_name}")
                return jsonify({'success': True, 'message': '应用名称已更新'})
            except Exception as e:
                logger.error(f"更新应用名称失败: {e}")
                return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/apps/<app_id>/toggle', methods=['POST'])
    @require_api_key
    def api_toggle_app(app_id):
        """切换应用启用状态"""
        try:
            toggle_app_enabled(app_id)
            logger.info(f"应用 {app_id} 启用状态已切换")
            return jsonify({'success': True, 'message': '应用状态已更新'})
        except Exception as e:
            logger.error(f"切换应用状态失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    # ==================== IP 更新 API ====================
    
    @app.route('/api/ip/update', methods=['POST'])
    @require_api_key
    def api_update_ip():
        """手动触发IP更新"""
        try:
            data = request.get_json(silent=True) or {}
            app_id = data.get('app_id')
            
            # 获取当前IP
            current_ip = get_current_public_ip()
            if not current_ip:
                return jsonify({'success': False, 'message': '无法获取当前公网IP'}), 500
            
            # 如果指定了应用ID，只更新该应用
            if app_id:
                old_ip = get_ip_status().get('last_updated_ip', '')
                # 获取应用名称
                apps = get_app_ids()
                app = next((a for a in apps if a['app_id'] == app_id), None)
                app_name = app['app_name'] if app else app_id
                success, message, trusted_ip = update_ip_for_app(app_id, current_ip, app_name=app_name)
                if success:
                    update_ip_status(current_ip, current_ip, '更新成功')
                    # 记录历史
                    add_ip_update_history(app_id, app_name, old_ip, current_ip, trusted_ip, 'success', '更新成功')
                    # 发送通知
                    config = get_system_config()
                    webhook_url = config.get('wecom_webhook_url')
                    if webhook_url:
                        send_wecom_webhook(
                            webhook_url,
                            f"✅ 企微可信IP更新成功\n\n应用: {app_name}\n新IP: {current_ip}\n时间: {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                else:
                    # 记录失败历史
                    apps = get_app_ids()
                    app = next((a for a in apps if a['app_id'] == app_id), None)
                    app_name = app['app_name'] if app else app_id
                    add_ip_update_history(app_id, app_name, old_ip, current_ip, trusted_ip, 'failed', message)
                
                return jsonify({'success': success, 'message': message})
            
            # 否则更新所有应用
            apps = get_app_ids()
            if not apps:
                return jsonify({'success': False, 'message': '没有配置应用ID'}), 400
            
            results = []
            all_success = True
            
            for app in apps:
                app_id = app['app_id']
                app_name = app['app_name']
                old_ip = get_ip_status().get('last_updated_ip', '')
                success, message, trusted_ip = update_ip_for_app(app_id, current_ip, app_name=app_name)
                results.append({'app_id': app_id, 'success': success, 'message': message})
                # 记录历史
                add_ip_update_history(app_id, app_name, old_ip, current_ip, trusted_ip, 'success' if success else 'failed', message)
                if not success:
                    all_success = False
            
            if all_success:
                update_ip_status(current_ip, current_ip, '全部更新成功')
            else:
                update_ip_status(current_ip, current_ip, '部分更新失败')
            
            return jsonify({
                'success': all_success,
                'message': 'IP更新完成',
                'results': results,
                'current_ip': current_ip
            })
            
        except Exception as e:
            logger.error(f"更新IP失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/ip/current')
    @require_api_key
    def api_current_ip():
        """获取当前公网IP"""
        try:
            current_ip = get_current_public_ip()
            if current_ip:
                return jsonify({'success': True, 'ip': current_ip})
            else:
                return jsonify({'success': False, 'message': '无法获取公网IP'}), 500
        except Exception as e:
            logger.error(f"获取IP失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/ip/force_update', methods=['POST'])
    @require_api_key
    def api_force_update_ip():
        """强制更新公网IP到微信可信IP（手动批量更新）"""
        try:
            # 1. 检查登录状态
            auth_info = get_auth_info()
            if not auth_info.get('is_logged_in'):
                return jsonify({'success': False, 'message': '未登录企业微信，请先导入有效的Cookie'}), 401

            # 2. 获取当前公网IP
            current_ip = get_current_public_ip()
            if not current_ip:
                return jsonify({'success': False, 'message': '无法获取当前公网IP'}), 500

            # 3. 获取所有启用的应用
            apps = get_enabled_app_ids()
            if not apps:
                return jsonify({'success': False, 'message': '没有配置启用的应用ID'}), 400
            
            # 更新所有应用
            results = []
            all_success = True
            
            for app in apps:
                app_id = app['app_id']
                app_name = app['app_name']
                old_ip = get_ip_status().get('last_updated_ip', '')
                success, message, trusted_ip = update_ip_for_app(app_id, current_ip, app_name=app_name)
                results.append({'app_id': app_id, 'success': success, 'message': message, 'trusted_ip': trusted_ip})
                # 记录历史
                add_ip_update_history(app_id, app_name, old_ip, current_ip, trusted_ip, 'success' if success else 'failed', message)
                if not success:
                    all_success = False
            
            # 更新数据库状态
            if all_success:
                update_ip_status(current_ip, current_ip, '更新成功')
                # 发送通知
                config = get_system_config()
                webhook_url = config.get('wecom_webhook_url')
                if webhook_url:
                    app_list = '\n'.join([f"• {app['app_name'] or app['app_id']}: {app['trusted_ip'] or current_ip}" for app in results])
                    send_wecom_webhook(
                        webhook_url,
                        f"✅ 企微可信IP批量更新成功\n\n新IP: {current_ip}\n应用数量: {len(apps)}\n应用列表:\n{app_list}\n时间: {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
            else:
                update_ip_status(current_ip, current_ip, '部分更新失败')
                # 发送通知
                config = get_system_config()
                webhook_url = config.get('wecom_webhook_url')
                if webhook_url:
                    failed_apps = [app for app in results if not app['success']]
                    success_apps = [app for app in results if app['success']]
                    failed_list = '\n'.join([f"• {app.get('app_name', app['app_id'])}: {app['message']}" for app in failed_apps])
                    success_list = '\n'.join([f"• {app['app_name'] or app['app_id']}: {app['trusted_ip'] or current_ip}" for app in success_apps])
                    send_wecom_webhook(
                        webhook_url,
                        f"⚠️ 企微可信IP部分更新失败\n\n新IP: {current_ip}\n成功: {len(success_apps)}\n失败: {len(failed_apps)}\n成功列表:\n{success_list}\n\n失败列表:\n{failed_list}\n时间: {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
            
            return jsonify({
                'success': all_success,
                'message': 'IP更新完成',
                'current_ip': current_ip,
                'results': results
            })

        except Exception as e:
            logger.error(f"强制更新IP失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/ip/update_single', methods=['POST'])
    @require_api_key
    def api_update_single_app_ip():
        """更新单个应用的可信IP"""
        try:
            data = request.get_json(silent=True) or {}
            app_id = data.get('app_id')

            if not app_id:
                return jsonify({'success': False, 'message': '缺少应用ID'}), 400

            # 1. 检查登录状态
            auth_info = get_auth_info()
            if not auth_info.get('is_logged_in'):
                return jsonify({'success': False, 'message': '未登录企业微信，请先导入有效的Cookie'}), 401

            # 2. 获取应用信息
            apps = get_app_ids()
            app = next((a for a in apps if a['app_id'] == app_id), None)
            if not app:
                return jsonify({'success': False, 'message': '应用不存在'}), 404

            # 3. 检查应用是否启用
            if not app.get('enabled', True):
                return jsonify({'success': False, 'message': '未启用', 'disabled': True}), 400

            # 4. 获取当前公网IP
            current_ip = get_current_public_ip()
            if not current_ip:
                return jsonify({'success': False, 'message': '无法获取当前公网IP'}), 500

            # 5. 执行更新
            app_name = app['app_name']
            old_ip = get_ip_status().get('last_updated_ip', '')
            success, message, trusted_ip = update_ip_for_app(app_id, current_ip, app_name=app_name)

            # 6. 记录历史
            add_ip_update_history(app_id, app_name, old_ip, current_ip, trusted_ip, 'success' if success else 'failed', message)

            # 7. 更新全局IP状态
            if success:
                update_ip_status(current_ip, current_ip, '更新成功')

            return jsonify({
                'success': success,
                'message': message,
                'app_id': app_id,
                'app_name': app_name,
                'current_ip': current_ip
            })

        except Exception as e:
            logger.error(f"更新单个应用IP失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/logs')
    @require_api_key
    def api_get_logs():
        """获取前台日志内容"""
        try:
            from backend.configmanager import DATA_DIR
            import os
            
            # 读取前台简洁日志文件
            log_file = os.path.join(DATA_DIR, 'weworkiphelper.log')
            if not os.path.exists(log_file):
                return jsonify({'success': True, 'logs': []})
            
            # 读取最后100行日志
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                logs = lines[-100:] if len(lines) > 100 else lines
            
            return jsonify({'success': True, 'logs': logs})
        except Exception as e:
            logger.error(f"获取日志失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/ip-update-history')
    @require_api_key
    def api_get_ip_update_history():
        """获取IP更新历史记录"""
        try:
            from backend.database import get_ip_update_history
            history = get_ip_update_history(limit=50)
            return jsonify({'success': True, 'history': history})
        except Exception as e:
            logger.error(f"获取IP更新历史失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    # ==================== 任务调度 API ====================
    
    @app.route('/api/tasks')
    @require_api_key
    def api_get_tasks():
        """获取任务列表"""
        try:
            scheduler = get_scheduler()
            tasks = scheduler.get_tasks()
            return jsonify({'success': True, 'tasks': tasks})
        except Exception as e:
            logger.error(f"获取任务列表失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/tasks/<task_id>/run', methods=['POST'])
    @require_api_key
    def api_run_task(task_id):
        """立即执行任务"""
        try:
            scheduler = get_scheduler()
            success, message = scheduler.run_task_now(task_id)
            if success:
                return jsonify({'success': True, 'message': message})
            else:
                return jsonify({'success': False, 'message': message}), 400
        except Exception as e:
            logger.error(f"执行任务失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/tasks/<task_id>/cron', methods=['POST'])
    @require_api_key
    def api_update_task_cron(task_id):
        """更新任务cron表达式"""
        try:
            data = request.get_json()
            cron_expression = data.get('cron')
            
            logger.info(f"[API] 收到更新cron请求: task_id={task_id}, cron={cron_expression}")
            
            if not cron_expression:
                return jsonify({'success': False, 'message': 'cron表达式不能为空'}), 400
            
            scheduler = get_scheduler()
            success, message = scheduler.update_task_cron(task_id, cron_expression)
            
            # 获取更新后的任务状态
            tasks = scheduler.get_tasks()
            updated_task = next((t for t in tasks if t['id'] == task_id), None)
            if updated_task:
                logger.info(f"[API] 更新后任务状态: next_run={updated_task.get('next_run')}, time_remaining={updated_task.get('time_remaining')}")
            
            if success:
                # 同时保存到数据库
                task_cron_map = {
                    'login_check': 'login_check_cron',
                    'public_ip_check': 'public_ip_check_cron'
                }
                save_system_config(**{task_cron_map.get(task_id): cron_expression})
                return jsonify({'success': True, 'message': message})
            else:
                return jsonify({'success': False, 'message': message}), 400
        except Exception as e:
            logger.error(f"更新任务cron失败: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
    

