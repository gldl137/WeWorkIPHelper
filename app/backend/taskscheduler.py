#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务调度器 - 管理定时任务
"""

import threading
import time
from datetime import datetime, timedelta, timezone
from croniter import croniter
from backend.configmanager import logger, ShanghaiTimezone
from backend.database import get_auth_info, save_auth_info, get_ip_status, update_ip_status, get_system_config, get_enabled_app_ids, add_ip_update_history
from backend.ip_updater import update_ip_for_app
from backend.publicipfetcher import get_current_public_ip
from backend.loginchecker import check_login_status
from backend.commonutils import send_wecom_webhook

# 创建本地时区实例
LOCAL_TZ = ShanghaiTimezone()


class TaskScheduler:
    """任务调度器类"""

    def __init__(self):
        self.tasks = {}
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self._startup_checked = False  # 标记是否已完成启动检查

        # 初始化任务
        self._init_tasks()

    def _init_tasks(self):
        """初始化任务配置"""
        # 从数据库读取任务cron配置
        config = get_system_config()

        # 强制使用数据库中的cron配置，没有默认值
        login_check_cron = config.get('login_check_cron')
        public_ip_check_cron = config.get('public_ip_check_cron')

        # 如果数据库中没有配置，则使用默认cron表达式（与数据库默认值保持一致）
        if not login_check_cron:
            login_check_cron = '0 * * * *'
        if not public_ip_check_cron:
            public_ip_check_cron = '*/30 * * * *'

        self.tasks = {
            'login_check': {
                'name': '登录状态检查',
                'cron': login_check_cron,
                'last_run': None,
                'next_run': None,
                'status': 'waiting',
                'handler': self._task_login_check
            },
            'public_ip_check': {
                'name': '公网IP检测',
                'cron': public_ip_check_cron,
                'last_run': None,
                'next_run': None,
                'status': 'waiting',
                'handler': self._task_public_ip_check
            }
        }
        now = datetime.now(LOCAL_TZ)
        for task_id, task in self.tasks.items():
            cron = croniter(task['cron'], now)
            next_run = cron.get_next(datetime)
            # 确保next_run带有时区信息
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=LOCAL_TZ)
            task['next_run'] = next_run

    def _task_login_check(self, silent=False):
        """
        登录状态检查任务
        
        参数:
            silent: 是否为静默模式（启动检查时不发送通知）
        """
        try:
            logger.info("[登录检查] 开始检查登录状态")

            # 直接调用新的登录检查逻辑，访问微信首页
            is_logged_in, message = check_login_status()
            auth_info = get_auth_info()
            was_logged_in = auth_info.get('is_logged_in', False)

            logger.info(f"[登录检查] 当前登录状态: is_logged_in={is_logged_in}, was_logged_in={was_logged_in}, message={message}")

            # 更新数据库中的登录状态
            auth_info['is_logged_in'] = is_logged_in
            auth_info['last_check_time'] = datetime.now(timezone.utc).astimezone().isoformat()
            save_auth_info(auth_info.get('cookies', ''), is_logged_in)

            # 管理其他任务的状态：如果未登录，暂停其他任务；如果已登录，恢复其他任务
            self._manage_task_status_by_login(is_logged_in)

            # 静默模式下不发送通知
            if silent:
                return True, message

            # 非静默模式下，只在登录失效时发送通知
            config = get_system_config()
            webhook_url = config.get('wecom_webhook_url')
            notification_enabled = config.get('notification_enabled', 1)

            # 只在登录失效时（从已登录变为未登录）发送通知
            if was_logged_in and not is_logged_in:
                logger.warning("[登录检查] 检测到登录失效，准备发送通知")
                logger.info(f"[登录检查] 通知配置: webhook_url={webhook_url}, notification_enabled={notification_enabled}")

                if webhook_url and notification_enabled:
                    logger.info("[登录检查] 正在发送登录失效通知")
                    success, notify_message = send_wecom_webhook(
                        webhook_url,
                        f"登录检测失败\n\n原因: {message}\n时间: {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S')}\n通知"
                    )
                    logger.info(f"[登录检查] 通知发送结果: success={success}, message={notify_message}")
                else:
                    logger.warning(f"[登录检查] 通知未发送: webhook_url={webhook_url}, notification_enabled={notification_enabled}")
            else:
                logger.info(f"[登录检查] 登录状态未变化，不发送通知 (was_logged_in={was_logged_in}, is_logged_in={is_logged_in})")

            return True, message
        except Exception as e:
            logger.error(f"[登录检查] 失败: {e}")
            # 异常情况下也发送通知（非静默模式）
            if not silent:
                self._send_notification("登录检测失败", f"错误: {str(e)}")
            return False, str(e)

    def _task_public_ip_check(self):
        """公网IP检测任务 - 检测IP变化并自动更新"""
        try:
            logger.info("[公网IP检测] 开始检测公网IP")
            current_ip = get_current_public_ip()

            if current_ip:
                logger.info(f"[公网IP检测] 检测到公网IP: {current_ip}")

                # 获取上次保存的IP
                ip_status = get_ip_status()
                last_ip = ip_status.get('last_updated_ip')

                # 保存到数据库的当前公网IP字段
                update_ip_status(current_ip=current_ip, update_status=f"检测成功: {current_ip}")
                logger.info(f"[公网IP检测] 已保存到数据库: {current_ip}")

                # 只在IP变化时自动更新
                if current_ip != last_ip:
                    logger.info(f"[公网IP检测] IP已变化: {last_ip} -> {current_ip}")

                    # 检查登录状态
                    auth_info = get_auth_info()
                    if not auth_info.get('is_logged_in'):
                        logger.warning("[公网IP检测] 未登录，跳过自动更新")
                        self._send_notification("公网IP检测成功", f"旧IP: {last_ip}\n新IP: {current_ip}")
                        return True, f"IP变化但未登录: {current_ip}"

                    # 获取所有启用的应用
                    apps = get_enabled_app_ids()
                    if not apps:
                        logger.warning("[公网IP检测] 没有启用的应用")
                        self._send_notification("公网IP检测成功", f"旧IP: {last_ip}\n新IP: {current_ip}")
                        return True, f"IP变化但无应用: {current_ip}"

                    # 自动更新所有应用
                    logger.info(f"[公网IP检测] 开始自动更新 {len(apps)} 个应用")
                    results = []
                    all_success = True
                    success_count = 0
                    failed_count = 0

                    for app in apps:
                        app_id = app['app_id']
                        app_name = app['app_name']
                        success, message, trusted_ip = update_ip_for_app(app_id, current_ip, app_name=app_name)
                        # 记录历史
                        add_ip_update_history(app_id, app_name, last_ip, current_ip, trusted_ip, 'success' if success else 'failed', message)
                        results.append({
                            'app_id': app_id,
                            'app_name': app_name,
                            'success': success,
                            'message': message,
                            'trusted_ip': trusted_ip
                        })
                        if success:
                            success_count += 1
                        else:
                            all_success = False
                            failed_count += 1

                    # 更新数据库状态
                    if all_success:
                        update_ip_status(current_ip, current_ip, '自动更新成功')
                        app_list = '\n'.join([f"• {app['app_name'] or app['app_id']}: {app['trusted_ip'] or current_ip}" for app in results])
                        self._send_notification(
                            "公网IP检测成功",
                            f"旧IP: {last_ip}\n新IP: {current_ip}"
                        )
                    else:
                        update_ip_status(current_ip, current_ip, '部分自动更新失败')
                        failed_apps = [app for app in results if not app['success']]
                        success_apps = [app for app in results if app['success']]
                        failed_list = '\n'.join([f"• {app.get('app_name', app['app_id'])}: {app['message']}" for app in failed_apps])
                        success_list = '\n'.join([f"• {app['app_name'] or app['app_id']}: {app['trusted_ip'] or current_ip}" for app in success_apps])
                        self._send_notification(
                            "公网IP检测失败",
                            f"旧IP: {last_ip}\n新IP: {current_ip}"
                        )

                    return True, f"IP变化并自动更新: {current_ip} (成功:{success_count}, 失败:{failed_count})"
                else:
                    logger.info(f"[公网IP检测] IP未变化: {current_ip}")
                    return True, f"IP未变化: {current_ip}"
            else:
                logger.warning("[公网IP检测] 无法获取公网IP")
                self._send_notification("公网IP检测失败", "原因: 无法获取公网IP")
                return False, "无法获取公网IP"
        except Exception as e:
            logger.error(f"[公网IP检测] 失败: {e}")
            self._send_notification("公网IP检测失败", f"错误: {str(e)}")
            return False, str(e)



    def _send_notification(self, title, content):
        """发送通知的辅助方法"""
        try:
            config = get_system_config()
            webhook_url = config.get('wecom_webhook_url')
            notification_enabled = config.get('notification_enabled', 1)

            if webhook_url and notification_enabled:
                success, message = send_wecom_webhook(
                    webhook_url,
                    f"{title}\n\n{content}\n时间: {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S')}\n通知"
                )
                logger.info(f"[通知] 发送结果: success={success}, message={message}")
            else:
                logger.warning(f"[通知] 未发送: webhook_url={webhook_url}, notification_enabled={notification_enabled}")
        except Exception as e:
            logger.error(f"[通知] 发送失败: {e}")

    def start(self):
        """启动调度器"""
        if self.running:
            return

        self.running = True
        
        # 启动时先执行一次静默登录检查
        if not self._startup_checked:
            logger.info("[启动] 执行启动时登录状态检查")
            self._task_login_check(silent=True)
            self._startup_checked = True
        
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """停止调度器"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

    def _manage_task_status_by_login(self, is_logged_in):
        """根据登录状态管理其他任务的执行状态"""
        try:
            # 不受登录状态限制的任务列表
            independent_tasks = ['login_check', 'public_ip_check']

            if not is_logged_in:
                # 未登录时，暂停除登录检查和公网IP检测外的其他任务
                logger.warning("[任务管理] 检测到未登录状态，暂停需要登录的任务")
                with self.lock:
                    for task_id, task in self.tasks.items():
                        if task_id not in independent_tasks and task['status'] == 'waiting':
                            task['status'] = 'paused'
                            logger.info(f"[任务管理] 暂停任务: {task['name']}")
            else:
                # 已登录时，恢复被暂停的任务
                logger.info("[任务管理] 检测到已登录状态，恢复被暂停的任务")
                with self.lock:
                    for task_id, task in self.tasks.items():
                        if task_id not in independent_tasks and task['status'] == 'paused':
                            task['status'] = 'waiting'
                            logger.info(f"[任务管理] 恢复任务: {task['name']}")
        except Exception as e:
            logger.error(f"[任务管理] 管理任务状态失败: {e}")

    def _should_execute_task(self, task_id):
        """判断任务是否应该执行"""
        # 登录检查和公网IP检测任务总是可以执行（不需要登录）
        if task_id in ['login_check', 'public_ip_check']:
            return True

        # 其他任务只有在已登录状态下才能执行
        auth_info = get_auth_info()
        return auth_info.get('is_logged_in', False)

    def _run_loop(self):
        """主循环"""
        while self.running:
            now = datetime.now(LOCAL_TZ)

            with self.lock:
                for task_id, task in self.tasks.items():
                    if task['status'] == 'waiting' and task['next_run'] and now >= task['next_run']:
                        # 检查任务是否应该执行
                        if not self._should_execute_task(task_id):
                            logger.debug(f"[任务调度] 任务 {task['name']} 当前不允许执行，跳过")
                            # 更新下次执行时间，避免重复检查
                            cron = croniter(task['cron'], now)
                            next_run = cron.get_next(datetime)
                            if next_run.tzinfo is None:
                                next_run = next_run.replace(tzinfo=LOCAL_TZ)
                            task['next_run'] = next_run
                            continue

                        # 执行任务
                        task['status'] = 'running'
                        task['last_run'] = now

                        # 在后台线程中执行
                        threading.Thread(
                            target=self._execute_task,
                            args=(task_id,),
                            daemon=True
                        ).start()

            time.sleep(10)  # 每10秒检查一次

    def _execute_task(self, task_id):
        """执行单个任务"""
        task = self.tasks.get(task_id)
        if not task:
            return

        logger.info(f"[任务] 开始执行: {task['name']}")

        try:
            success, message = task['handler']()
            if success:
                logger.info(f"[任务] {task['name']} 执行成功: {message}")
            else:
                logger.warning(f"[任务] {task['name']} 执行失败: {message}")
        except Exception as e:
            logger.error(f"[任务] {task['name']} 异常: {e}")
            success = False
            message = str(e)
        finally:
            with self.lock:
                task['status'] = 'waiting'
                now = datetime.now(LOCAL_TZ)
                task['last_run'] = now  # 记录本次执行时间
                cron = croniter(task['cron'], now)
                next_run = cron.get_next(datetime)
                if next_run.tzinfo is None:
                    next_run = next_run.replace(tzinfo=LOCAL_TZ)
                task['next_run'] = next_run

    def get_tasks(self):
        """获取所有任务状态"""
        with self.lock:
            result = []
            now = datetime.now(LOCAL_TZ)
            for task_id, task in self.tasks.items():
                # 计算剩余时间
                time_remaining = None
                if task['next_run'] and task['status'] == 'waiting':
                    diff = task['next_run'] - now
                    total_seconds = diff.total_seconds()
                    if total_seconds > 0:
                        hours = int(total_seconds // 3600)
                        minutes = int((total_seconds % 3600) // 60)
                        seconds = int(total_seconds % 60)
                        
                        # 如果超过24小时，显示具体日期时间
                        if hours >= 24:
                            next_run = task['next_run']
                            # 如果是明天，显示"明天 HH:MM"
                            tomorrow = now + timedelta(days=1)
                            if next_run.date() == tomorrow.date():
                                time_remaining = f"明天{next_run.strftime('%H:%M')}"
                            # 如果是今天，显示"今天 HH:MM"
                            elif next_run.date() == now.date():
                                time_remaining = f"今天{next_run.strftime('%H:%M')}"
                            # 否则显示具体日期
                            else:
                                time_remaining = next_run.strftime('%m月%d日%H:%M')
                        elif hours > 0:
                            time_remaining = f"{hours}小时{minutes}分钟"
                        elif minutes > 0:
                            time_remaining = f"{minutes}分钟"
                        else:
                            time_remaining = f"{seconds}秒"
                    else:
                        time_remaining = "即将执行"

                # 对于暂停状态的任务，显示特殊状态信息
                status_display = task['status']

                # 检查是否需要登录的任务在未登录状态下的显示
                auth_info = get_auth_info()
                is_logged_in = auth_info.get('is_logged_in', False)

                # 需要登录的任务列表
                login_required_tasks = []

                if task['status'] == 'paused':
                    # 已暂停的任务
                    if not is_logged_in:
                        status_display = 'paused (未登录)'
                elif task['status'] == 'waiting' and task_id in login_required_tasks and not is_logged_in:
                    # 需要登录但当前未登录的任务，显示为暂停状态
                    status_display = 'paused (未登录)'

                result.append({
                    'id': task_id,
                    'name': task['name'],
                    'cron': task['cron'],
                    'status': status_display,
                    'last_run': task['last_run'].isoformat() if task['last_run'] else None,
                    'next_run': task['next_run'].isoformat() if task['next_run'] else None,
                    'time_remaining': time_remaining
                })
            return result

    def run_task_now(self, task_id):
        """立即执行任务（手动执行）"""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                logger.error(f"[任务] 任务不存在: {task_id}")
                return False, "任务不存在"

            if task['status'] == 'running':
                logger.warning(f"[任务] 任务正在运行中: {task['name']}")
                return False, "任务正在运行中"

            # 检查任务是否应该执行（手动执行也需要检查登录状态）
            if not self._should_execute_task(task_id):
                auth_info = get_auth_info()
                if not auth_info.get('is_logged_in', False):
                    logger.warning(f"[手动执行] 任务 {task['name']} 未登录，无法执行")
                    return False, "未登录状态，无法执行此任务"

            # 更新状态为运行中
            task['status'] = 'running'
            task['last_run'] = datetime.now(LOCAL_TZ)
            logger.info(f"[手动执行] 任务已启动: {task['name']} ({task_id})")

        # 在后台线程中执行
        threading.Thread(
            target=self._execute_task_manual,
            args=(task_id,),
            daemon=True
        ).start()

        return True, "任务已启动"

    def _execute_task_manual(self, task_id):
        """执行手动任务（带通知）"""
        task = self.tasks.get(task_id)
        if not task:
            return

        logger.info(f"[手动执行] 开始执行: {task['name']}")

        try:
            # 手动执行任务，传入参数表示需要发送通知
            if task_id == 'login_check':
                success, message = self._task_login_check(silent=False)
            else:
                success, message = task['handler']()
            
            if success:
                logger.info(f"[手动执行] {task['name']} 执行成功: {message}")
                if task_id == 'login_check':
                    self._send_notification("登录检测成功", f"结果: {message}")
                else:
                    self._send_notification("可信IP更新成功", f"结果: {message}")
            else:
                logger.warning(f"[手动执行] {task['name']} 执行失败: {message}")
                if task_id == 'login_check':
                    self._send_notification("登录检测失败", f"原因: {message}")
                else:
                    self._send_notification("可信IP更新失败", f"原因: {message}")
        except Exception as e:
            logger.error(f"[手动执行] {task['name']} 异常: {e}")
            if task_id == 'login_check':
                self._send_notification("登录检测失败", f"错误: {str(e)}")
            else:
                self._send_notification("可信IP更新失败", f"错误: {str(e)}")
        finally:
            with self.lock:
                task['status'] = 'waiting'
                now = datetime.now(LOCAL_TZ)
                task['last_run'] = now
                cron = croniter(task['cron'], now)
                next_run = cron.get_next(datetime)
                if next_run.tzinfo is None:
                    next_run = next_run.replace(tzinfo=LOCAL_TZ)
                task['next_run'] = next_run

    def update_task_cron(self, task_id, cron_expression):
        """更新任务cron表达式"""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return False, "任务不存在"

            old_cron = task['cron']
            old_next_run = task['next_run']

            # 验证cron表达式
            try:
                now = datetime.now(LOCAL_TZ)
                cron = croniter(cron_expression, now)
                next_run = cron.get_next(datetime)
                # 确保next_run带有时区信息
                if next_run.tzinfo is None:
                    next_run = next_run.replace(tzinfo=LOCAL_TZ)
            except Exception as e:
                return False, f"无效的cron表达式: {str(e)}"

            # 更新cron表达式
            task['cron'] = cron_expression

            # 重新计算下次执行时间（从当前时间开始计算，不从整点开始）
            # 对于 */n 类型的分钟周期，使用相对时间
            if cron_expression.startswith('*/') and cron_expression.endswith(' * * * *'):
                try:
                    n = int(cron_expression.split()[0][2:])
                    next_run = now + timedelta(minutes=n)
                    logger.info(f"[任务] {task['name']} 使用相对时间计算: 当前时间 {now} + {n}分钟 = {next_run}")
                except (ValueError, IndexError):
                    pass  # 如果解析失败，使用原来的next_run

            # 重新计算下次执行时间
            task['next_run'] = next_run

            logger.info(f"[任务] {task['name']} cron已更新: {old_cron} -> {cron_expression}, next_run: {old_next_run} -> {next_run}")

            return True, f"任务 {task['name']} cron表达式已更新"


# 全局调度器实例（懒加载）
_scheduler = None


def get_scheduler():
    """获取调度器实例（懒加载）"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler


def init_scheduler():
    """初始化调度器"""
    scheduler = get_scheduler()
    scheduler.start()