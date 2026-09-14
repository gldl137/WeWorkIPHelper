#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库访问层
所有 sqlite3 操作集中在此
"""

import sqlite3
import secrets
from datetime import datetime, timezone, timedelta
from backend.configmanager import DB_PATH, logger


def init_database():
    """初始化数据库表结构"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. 应用ID表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS app_ids (
                app_id TEXT PRIMARY KEY,
                app_name TEXT DEFAULT '',
                remark TEXT DEFAULT '',
                enabled BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 自动升级旧数据库：为 app_ids 表添加 updated_at 字段（如果不存在）
        try:
            cursor.execute("ALTER TABLE app_ids ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
        except sqlite3.OperationalError:
            pass

        # 自动升级旧数据库：为 app_ids 表添加 remark 字段（如果不存在）
        try:
            cursor.execute("ALTER TABLE app_ids ADD COLUMN remark TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass

        # 自动升级旧数据库：为 app_ids 表添加 trusted_ip 字段（如果不存在）
        try:
            cursor.execute("ALTER TABLE app_ids ADD COLUMN trusted_ip TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass

        # 自动升级旧数据库：为 app_ids 表添加 trusted_ip_updated_at 字段（如果不存在）
        try:
            cursor.execute("ALTER TABLE app_ids ADD COLUMN trusted_ip_updated_at DATETIME")
        except sqlite3.OperationalError:
            pass
        
        # 2. 认证信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auth_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cookies TEXT,
                last_login_time TEXT,
                status TEXT,
                update_time TEXT,
                is_logged_in BOOLEAN DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 自动升级旧数据库：添加 last_login_time 字段（如果不存在）
        try:
            cursor.execute("ALTER TABLE auth_info ADD COLUMN last_login_time TEXT")
        except sqlite3.OperationalError:
            pass
        
        # 3. IP状态表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ip_status (
                id INTEGER PRIMARY KEY DEFAULT 1,
                current_ip TEXT,
                last_updated_ip TEXT,
                update_status TEXT DEFAULT '未更新',
                last_update_time TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 自动升级旧数据库：添加 last_update_time 字段（如果不存在）
        try:
            cursor.execute("ALTER TABLE ip_status ADD COLUMN last_update_time TEXT")
        except sqlite3.OperationalError:
            pass
        
        # 自动升级旧数据库：为 app_ids 表添加 enabled 字段（如果不存在）
        try:
            cursor.execute("ALTER TABLE app_ids ADD COLUMN enabled BOOLEAN DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        
        # 4. 通知配置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notify_config (
                id INTEGER PRIMARY KEY DEFAULT 1,
                notify_url TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 5. 系统配置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_config (
                id INTEGER PRIMARY KEY DEFAULT 1,
                admin_token TEXT,
                wecom_webhook_url TEXT,
                verify_enabled BOOLEAN DEFAULT 1,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 6. 认证Token表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auth_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL
            )
        ''')
        
        # 7. IP更新历史记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ip_update_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_id TEXT,
                app_name TEXT,
                old_ip TEXT,
                new_ip TEXT,
                trusted_ip TEXT,
                status TEXT,
                message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 自动升级旧数据库：添加trusted_ip字段（如果不存在）
        try:
            cursor.execute("ALTER TABLE ip_update_history ADD COLUMN trusted_ip TEXT")
        except sqlite3.OperationalError:
            pass
        
        # 初始化默认记录
        cursor.execute('INSERT OR IGNORE INTO auth_info (id, cookies, is_logged_in) VALUES (1, NULL, 0)')
        cursor.execute('INSERT OR IGNORE INTO ip_status (id, current_ip, last_updated_ip, update_status) VALUES (1, NULL, NULL, "未更新")')
        cursor.execute('INSERT OR IGNORE INTO notify_config (id, notify_url) VALUES (1, NULL)')
        cursor.execute('INSERT OR IGNORE INTO system_config (id, admin_token, wecom_webhook_url) VALUES (1, NULL, NULL)')
        
        # 自动升级旧数据库：添加任务间隔字段（如果不存在）
        try:
            cursor.execute("ALTER TABLE system_config ADD COLUMN login_check_interval INTEGER DEFAULT 30")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("ALTER TABLE system_config ADD COLUMN public_ip_check_interval INTEGER DEFAULT 30")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("ALTER TABLE system_config ADD COLUMN verify_enabled BOOLEAN DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("ALTER TABLE system_config ADD COLUMN notification_enabled BOOLEAN DEFAULT 1")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("ALTER TABLE system_config ADD COLUMN login_check_cron TEXT DEFAULT '0 * * * *'")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("ALTER TABLE system_config ADD COLUMN public_ip_check_cron TEXT DEFAULT '*/30 * * * *'")
        except sqlite3.OperationalError:
            pass
        
        conn.commit()
        conn.close()
        logger.info("数据库初始化完成")
        return True
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        return False


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ==================== 系统配置操作 ====================

def get_system_config():
    """获取系统配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT admin_token, wecom_webhook_url, login_check_interval, public_ip_check_interval, verify_enabled, notification_enabled, login_check_cron, public_ip_check_cron FROM system_config WHERE id = 1')
    config = cursor.fetchone()
    conn.close()
    return {
        'admin_token': config['admin_token'] if config else None,
        'wecom_webhook_url': config['wecom_webhook_url'] if config else None,
        'login_check_interval': config['login_check_interval'] if config else 30,
        'public_ip_check_interval': config['public_ip_check_interval'] if config else 30,
        'verify_enabled': config['verify_enabled'] if config else 1,
        'notification_enabled': config['notification_enabled'] if config else 1,
        'login_check_cron': config['login_check_cron'] if config else '0 * * * *',
        'public_ip_check_cron': config['public_ip_check_cron'] if config else '*/30 * * * *'
    }


def save_system_config(admin_token=None, wecom_webhook_url=None, login_check_interval=None, public_ip_check_interval=None, verify_enabled=None, notification_enabled=None, login_check_cron=None, public_ip_check_cron=None):
    """保存系统配置"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if admin_token is not None:
        cursor.execute(
            'UPDATE system_config SET admin_token = ?, updated_at = ? WHERE id = 1',
            (admin_token, datetime.now(timezone.utc).astimezone())
        )

    if wecom_webhook_url is not None:
        cursor.execute(
            'UPDATE system_config SET wecom_webhook_url = ?, updated_at = ? WHERE id = 1',
            (wecom_webhook_url, datetime.now(timezone.utc).astimezone())
        )

    if verify_enabled is not None:
        cursor.execute(
            'UPDATE system_config SET verify_enabled = ?, updated_at = ? WHERE id = 1',
            (verify_enabled, datetime.now(timezone.utc).astimezone())
        )

    if notification_enabled is not None:
        cursor.execute(
            'UPDATE system_config SET notification_enabled = ?, updated_at = ? WHERE id = 1',
            (notification_enabled, datetime.now(timezone.utc).astimezone())
        )

    if login_check_interval is not None:
        cursor.execute(
            'UPDATE system_config SET login_check_interval = ?, updated_at = ? WHERE id = 1',
            (login_check_interval, datetime.now(timezone.utc).astimezone())
        )

    if public_ip_check_interval is not None:
        cursor.execute(
            'UPDATE system_config SET public_ip_check_interval = ?, updated_at = ? WHERE id = 1',
            (public_ip_check_interval, datetime.now(timezone.utc).astimezone())
        )

    if login_check_cron is not None:
        cursor.execute(
            'UPDATE system_config SET login_check_cron = ?, updated_at = ? WHERE id = 1',
            (login_check_cron, datetime.now(timezone.utc).astimezone())
        )

    if public_ip_check_cron is not None:
        cursor.execute(
            'UPDATE system_config SET public_ip_check_cron = ?, updated_at = ? WHERE id = 1',
            (public_ip_check_cron, datetime.now(timezone.utc).astimezone())
        )

    conn.commit()
    conn.close()


def is_initial_config_needed():
    """检查是否需要初始配置"""
    config = get_system_config()
    return not config['admin_token']


# ==================== 认证Token操作 ====================

def generate_auth_token():
    """生成认证token，有效期7天"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    cursor.execute(
        'INSERT INTO auth_tokens (token, expires_at) VALUES (?, ?)',
        (token, expires_at)
    )
    
    conn.commit()
    conn.close()
    
    logger.info(f"生成认证token，有效期至: {expires_at}")
    return token


def validate_auth_token(token):
    """验证认证token是否有效"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT expires_at FROM auth_tokens WHERE token = ? AND expires_at > ?',
        (token, datetime.now(timezone.utc))
    )
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return True
    else:
        logger.warning(f"无效或过期的token: {token[:10]}...")
        return False


def clear_all_auth_tokens():
    """清空全部认证token（修改管理密码后调用，强制所有会话重新登录）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM auth_tokens')
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted > 0:
        logger.info(f"已清空 {deleted} 个认证token（管理密码已变更）")


def cleanup_expired_tokens():
    """清理过期的认证token"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'DELETE FROM auth_tokens WHERE expires_at < ?',
        (datetime.now(timezone.utc),)
    )
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted_count > 0:
        logger.info(f"清理了 {deleted_count} 个过期token")


# ==================== 认证信息操作 ====================

def get_auth_info():
    """获取认证信息"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT cookies, is_logged_in, last_login_time, updated_at FROM auth_info WHERE id = 1')
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'cookies': row['cookies'],
            'is_logged_in': bool(row['is_logged_in']),
            'last_login_time': row['last_login_time'],
            'updated_at': row['updated_at']
        }
    return {'cookies': None, 'is_logged_in': False, 'last_login_time': None, 'updated_at': None}


def save_auth_info(cookies, is_logged_in=True):
    """保存认证信息"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO auth_info (id, cookies, is_logged_in, last_login_time, updated_at) VALUES (1, ?, ?, ?, ?)",
        (cookies, is_logged_in, datetime.now(timezone.utc).astimezone(), datetime.now(timezone.utc).astimezone())
    )
    conn.commit()
    conn.close()


def clear_auth_info():
    """清除认证信息"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE auth_info SET cookies = NULL, is_logged_in = 0, updated_at = ? WHERE id = 1",
        (datetime.now(timezone.utc).astimezone(),)
    )
    conn.commit()
    conn.close()


# ==================== IP 状态操作 ====================

def get_ip_status():
    """获取IP状态"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT current_ip, last_updated_ip, update_status, last_update_time FROM ip_status WHERE id = 1')
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'current_ip': row['current_ip'],
            'last_updated_ip': row['last_updated_ip'],
            'update_status': row['update_status'],
            'last_update_time': row['last_update_time']
        }
    return {'current_ip': None, 'last_updated_ip': None, 'update_status': '未更新', 'last_update_time': None}


def update_ip_status(current_ip=None, last_updated_ip=None, update_status=None):
    """更新IP状态"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if current_ip is not None:
        updates.append("current_ip = ?")
        params.append(current_ip)
    if last_updated_ip is not None:
        updates.append("last_updated_ip = ?")
        params.append(last_updated_ip)
        # 同时更新 last_update_time
        updates.append("last_update_time = ?")
        params.append(datetime.now(timezone.utc).astimezone().isoformat())
    if update_status is not None:
        updates.append("update_status = ?")
        params.append(update_status)
    
    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).astimezone())
        params.append(1)  # id

        sql = f"UPDATE ip_status SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(sql, params)
        conn.commit()

    conn.close()


# ==================== 应用ID操作 ====================

def get_app_ids():
    """获取所有应用ID"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查表有哪些字段
    cursor.execute("PRAGMA table_info(app_ids)")
    columns = [col[1] for col in cursor.fetchall()]
    has_remark = 'remark' in columns
    has_trusted_ip = 'trusted_ip' in columns

    if has_trusted_ip and has_remark:
        cursor.execute('SELECT app_id, app_name, remark, trusted_ip, trusted_ip_updated_at, enabled FROM app_ids ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        return [{
            'app_id': row['app_id'],
            'app_name': row['app_name'],
            'remark': row['remark'],
            'trusted_ip': row['trusted_ip'] or '',
            'trusted_ip_updated_at': row['trusted_ip_updated_at'] or '',
            'enabled': row['enabled']
        } for row in rows]
    elif has_remark:
        cursor.execute('SELECT app_id, app_name, remark, enabled FROM app_ids ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        return [{
            'app_id': row['app_id'],
            'app_name': row['app_name'],
            'remark': row['remark'],
            'trusted_ip': '',
            'trusted_ip_updated_at': '',
            'enabled': row['enabled']
        } for row in rows]
    else:
        cursor.execute('SELECT app_id, app_name, enabled FROM app_ids ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        return [{
            'app_id': row['app_id'],
            'app_name': row['app_name'],
            'remark': '',
            'trusted_ip': '',
            'trusted_ip_updated_at': '',
            'enabled': row['enabled']
        } for row in rows]


def get_enabled_app_ids():
    """获取所有启用的应用ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT app_id, app_name FROM app_ids WHERE enabled = 1 ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()
    return [{'app_id': row['app_id'], 'app_name': row['app_name']} for row in rows]


def save_app_id(app_id, app_name='', remark=''):
    """保存应用ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).astimezone()
    
    # 检查表是否有 updated_at 字段
    cursor.execute("PRAGMA table_info(app_ids)")
    columns = [col[1] for col in cursor.fetchall()]
    has_updated_at = 'updated_at' in columns
    has_remark = 'remark' in columns
    
    if has_updated_at and has_remark:
        # 新表结构
        cursor.execute(
            'INSERT OR REPLACE INTO app_ids (app_id, app_name, remark, enabled, created_at, updated_at) VALUES (?, ?, ?, 1, COALESCE((SELECT created_at FROM app_ids WHERE app_id = ?), ?), ?)',
            (app_id, app_name, remark, app_id, now, now)
        )
    elif has_remark:
        # 有 remark 但没有 updated_at
        cursor.execute(
            'INSERT OR REPLACE INTO app_ids (app_id, app_name, remark, enabled, created_at) VALUES (?, ?, ?, 1, COALESCE((SELECT created_at FROM app_ids WHERE app_id = ?), ?))',
            (app_id, app_name, remark, app_id, now)
        )
    else:
        # 旧表结构，只有基本字段
        cursor.execute(
            'INSERT OR REPLACE INTO app_ids (app_id, app_name, enabled, created_at) VALUES (?, ?, 1, COALESCE((SELECT created_at FROM app_ids WHERE app_id = ?), ?))',
            (app_id, app_name, app_id, now)
        )
    
    conn.commit()
    conn.close()


def toggle_app_enabled(app_id):
    """切换应用启用状态"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE app_ids SET enabled = NOT enabled WHERE app_id = ?', (app_id,))
    conn.commit()
    conn.close()


def delete_app_id(app_id):
    """删除应用ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM app_ids WHERE app_id = ?', (app_id,))
    conn.commit()
    conn.close()


def update_app_name(app_id, app_name):
    """更新应用名称"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查表是否有 updated_at 字段
    cursor.execute("PRAGMA table_info(app_ids)")
    columns = [col[1] for col in cursor.fetchall()]
    has_updated_at = 'updated_at' in columns

    if has_updated_at:
        cursor.execute(
            'UPDATE app_ids SET app_name = ?, updated_at = ? WHERE app_id = ?',
            (app_name, datetime.now(timezone.utc).astimezone(), app_id)
        )
    else:
        cursor.execute(
            'UPDATE app_ids SET app_name = ? WHERE app_id = ?',
            (app_name, app_id)
        )

    conn.commit()
    conn.close()


def update_app_trusted_ip(app_id, trusted_ip):
    """更新应用的可信IP"""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).astimezone()

    # 检查表是否有 trusted_ip 字段
    cursor.execute("PRAGMA table_info(app_ids)")
    columns = [col[1] for col in cursor.fetchall()]
    has_trusted_ip = 'trusted_ip' in columns

    if has_trusted_ip:
        cursor.execute(
            'UPDATE app_ids SET trusted_ip = ?, trusted_ip_updated_at = ? WHERE app_id = ?',
            (trusted_ip, now, app_id)
        )
        conn.commit()

    conn.close()


# ==================== IP更新历史记录操作 ====================

def add_ip_update_history(app_id, app_name, old_ip, new_ip, trusted_ip, status, message):
    """添加IP更新历史记录"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO ip_update_history (app_id, app_name, old_ip, new_ip, trusted_ip, status, message, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (app_id, app_name, old_ip, new_ip, trusted_ip, status, message, datetime.now(timezone.utc).astimezone())
        )
        conn.commit()
        conn.close()
        logger.info(f"已记录IP更新历史: app_id={app_id}, app_name={app_name}, trusted_ip={trusted_ip}, status={status}")
    except Exception as e:
        logger.error(f"记录IP更新历史失败: {e}")


def get_ip_update_history(limit=20):
    """获取IP更新历史记录"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT app_id, app_name, old_ip, new_ip, trusted_ip, status, message, created_at FROM ip_update_history ORDER BY created_at DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            'app_id': row['app_id'],
            'app_name': row['app_name'],
            'old_ip': row['old_ip'],
            'new_ip': row['new_ip'],
            'trusted_ip': row['trusted_ip'],
            'status': row['status'],
            'message': row['message'],
            'created_at': row['created_at']
        } for row in rows
    ]



