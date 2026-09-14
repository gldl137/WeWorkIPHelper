/* =============================================================================
 * 初始化向导（独立页面 /init）
 * 设置管理员密码 -> 写入系统配置 -> 跳转首页
 * ========================================================================== */
(function () {
    'use strict';

    function toast(message, type) {
        var container = document.getElementById('toast-container');
        if (!container) return;
        var item = document.createElement('div');
        item.className = 'toast-item';
        var colors = {
            success: '#16a34a',
            error: '#dc2626',
            warning: '#d97706',
            info: '#0284c7'
        };
        item.style.background = colors[type || 'info'] || colors.info;
        item.textContent = message;
        container.appendChild(item);
        setTimeout(function () {
            if (item.parentNode) item.parentNode.removeChild(item);
        }, 3000);
    }

    document.addEventListener('DOMContentLoaded', function () {
        var form = document.getElementById('init-form');
        var input = document.getElementById('init-admin-token');
        if (!form || !input) return;

        form.addEventListener('submit', function (event) {
            event.preventDefault();

            var password = (input.value || '').trim();
            if (password.length < 6) {
                toast('密码至少 6 位', 'warning');
                input.focus();
                return;
            }

            var button = form.querySelector('button[type="submit"]');
            if (button) button.disabled = true;

            fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ admin_token: password })
            })
                .then(function (res) {
                    return res.json().catch(function () {
                        return { success: false, message: 'HTTP ' + res.status };
                    });
                })
                .then(function (data) {
                    if (data && data.success) {
                        toast('初始化完成，正在进入系统...', 'success');
                        setTimeout(function () {
                            window.location.href = '/';
                        }, 1000);
                    } else {
                        toast((data && data.message) || '初始化失败', 'error');
                        if (button) button.disabled = false;
                    }
                })
                .catch(function (err) {
                    toast('初始化失败: ' + err.message, 'error');
                    if (button) button.disabled = false;
                });
        });
    });
})();
