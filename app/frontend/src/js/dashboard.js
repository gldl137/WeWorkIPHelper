/* =============================================================================
 * 仪表盘：状态卡片 + 定时任务列表
 * 全局暴露：initDashboardPage / refreshDashboardData / forceUpdateIP / runTaskNow
 * ========================================================================== */
(function () {
    'use strict';

    var STATUS_MAP = {
        waiting: { text: '等待中', cls: 'badge-success' },
        running: { text: '执行中', cls: 'badge-warning' },
        paused: { text: '已暂停', cls: 'badge-ghost' }
    };

    var WEEK_NAMES = { 0: '周日', 1: '周一', 2: '周二', 3: '周三', 4: '周四', 5: '周五', 6: '周六', 7: '周日' };

    /* 把 cron 表达式转成易读的中文描述（无法识别时回退显示原文） */
    function describeCron(cron) {
        if (!cron) return '-';
        var parts = String(cron).trim().split(/\s+/);
        if (parts.length < 5) return String(cron);

        var min = parts[0];
        var hour = parts[1];
        var dom = parts[2];
        var month = parts[3];
        var dow = parts[4];

        function stepOf(value) {
            var m = /^\*\/(\d+)$/.exec(value);
            return m ? parseInt(m[1], 10) : null;
        }
        function numOf(value) {
            return /^\d+$/.test(value) ? parseInt(value, 10) : null;
        }

        var minStep = stepOf(min);
        var hourStep = stepOf(hour);
        var mi = numOf(min);
        var h = numOf(hour);
        var daily = dom === '*' && month === '*' && dow === '*';

        if (minStep !== null && hour === '*') return '每' + minStep + '分钟';
        if (hourStep !== null && min === '0') return '每' + hourStep + '小时';
        if (hourStep !== null) return '每' + hourStep + '小时' + (mi !== null ? '（第' + mi + '分）' : '');
        if (min === '0' && hour === '*') return '每小时';
        if (h !== null && daily) {
            if (mi === 0) return '每天' + h + '点';
            if (mi !== null) return '每天' + h + '点' + mi + '分';
        }
        if (h !== null && mi !== null && dow !== '*' && numOf(dow) !== null) {
            var day = WEEK_NAMES[numOf(dow)] || dow;
            return '每' + day + h + '点' + (mi ? mi + '分' : '');
        }
        if (dow !== '*' && numOf(dow) !== null) {
            return '每' + (WEEK_NAMES[numOf(dow)] || dow);
        }
        return String(cron);
    }

    function statusBadge(status) {
        var raw = status || 'waiting';
        var paused = raw.indexOf('paused') === 0;
        var key = paused ? 'paused' : raw;
        var meta = STATUS_MAP[key] || { text: raw, cls: 'badge-ghost' };
        var text = paused && raw.indexOf('未登录') >= 0 ? '未登录' : meta.text;
        return '<span class="badge ' + meta.cls + ' badge-sm">' + window.escapeHtml(text) + '</span>';
    }

    function setText(id, value) {
        var el = document.getElementById(id);
        if (el) el.textContent = value === undefined || value === null || value === '' ? '-' : value;
    }

    function setHtml(id, html) {
        var el = document.getElementById(id);
        if (el) el.innerHTML = html;
    }

    /* ---------------- 系统状态 ---------------- */
    function loadStatus() {
        return window
            .apiJSON('/api/status')
            .then(function (data) {
                if (!data || data.success === false) {
                    window.showToast((data && data.message) || '获取系统状态失败', 'error');
                    return;
                }

                // 登录状态
                var logged = !!data.is_logged_in;
                setHtml(
                    'login-status',
                    '<span class="' + (logged ? 'text-success' : 'text-error') + '">' +
                    (logged ? '已登录' : '未登录') + '</span>'
                );

                setText('last-update', window.formatDateTime(data.last_check_time));
                setText('current-ip', data.current_ip || '获取失败');
                setText('last-updated-ip', data.last_updated_ip || '未更新');
            })
            .catch(function (err) {
                window.showToast('获取系统状态失败: ' + err.message, 'error');
            });
    }

    /* ---------------- 定时任务 ---------------- */
    function renderTaskRow(task) {
        var running = task.status === 'running';
        return (
            '<tr class="row-divider">' +
            '<td class="font-medium">' + window.escapeHtml(task.name || task.id) + '</td>' +
            '<td class="text-sm" title="' + window.escapeHtml(task.cron || '') + '">' +
            window.escapeHtml(describeCron(task.cron)) + '</td>' +
            '<td>' + statusBadge(task.status) + '</td>' +
            '<td class="text-sm text-base-content/70">' + window.escapeHtml(task.time_remaining || '-') + '</td>' +
            '<td class="text-center">' +
            '<button class="btn btn-xs btn-primary" onclick="runTaskNow(\'' + window.escapeHtml(task.id) + '\')"' +
            (running ? ' disabled' : '') + '>' + (running ? '执行中' : '执行') + '</button>' +
            '</td>' +
            '</tr>'
        );
    }

    function renderTaskCard(task) {
        var running = task.status === 'running';
        return (
            '<div class="card bg-base-200 border border-base-content/20">' +
            '<div class="card-body p-4">' +
            '<div class="flex items-center justify-between mb-2">' +
            '<span class="font-semibold">' + window.escapeHtml(task.name || task.id) + '</span>' +
            statusBadge(task.status) +
            '</div>' +
            '<div class="text-sm text-base-content/60 mb-1">周期: ' +
            window.escapeHtml(describeCron(task.cron)) + '</div>' +
            '<div class="text-sm text-base-content/60 mb-3">下次: ' + window.escapeHtml(task.time_remaining || '-') + '</div>' +
            '<button class="btn btn-sm btn-primary" onclick="runTaskNow(\'' + window.escapeHtml(task.id) + '\')"' +
            (running ? ' disabled' : '') + '>' + (running ? '执行中' : '立即执行') + '</button>' +
            '</div></div>'
        );
    }

    function loadTasks() {
        return window
            .apiJSON('/api/tasks')
            .then(function (data) {
                if (!data || data.success === false) {
                    window.showToast((data && data.message) || '获取任务列表失败', 'error');
                    return;
                }
                var tasks = data.tasks || [];

                var tbody = document.getElementById('task-table');
                if (tbody) {
                    tbody.innerHTML = tasks.length
                        ? tasks.map(renderTaskRow).join('')
                        : '<tr><td colspan="5" class="empty-state">暂无定时任务</td></tr>';
                }

                var cards = document.getElementById('task-cards-mobile');
                if (cards) {
                    cards.innerHTML = tasks.length
                        ? tasks.map(renderTaskCard).join('')
                        : '<div class="empty-state">暂无定时任务</div>';
                }
            })
            .catch(function (err) {
                window.showToast('获取任务列表失败: ' + err.message, 'error');
            });
    }

    function runTaskNow(taskId) {
        window.showToast('任务已提交执行...', 'info');
        window
            .apiJSON('/api/tasks/' + encodeURIComponent(taskId) + '/run', { method: 'POST' })
            .then(function (data) {
                window.showToast((data && data.message) || '执行完成', data && data.success ? 'success' : 'error');
                return loadTasks();
            })
            .catch(function (err) {
                window.showToast('执行失败: ' + err.message, 'error');
            });
    }

    /* ---------------- 强制更新 IP ---------------- */
    function forceUpdateIP() {
        if (!window.confirm('确定要立即将当前公网IP更新到所有启用的应用吗？')) return;
        window.showToast('正在更新可信IP...', 'info');
        window
            .apiJSON('/api/ip/force_update', { method: 'POST' })
            .then(function (data) {
                if (data && data.success) {
                    window.showToast('IP 更新成功：' + (data.current_ip || ''), 'success');
                } else {
                    window.showToast((data && data.message) || 'IP 更新失败', 'error');
                }
                return Promise.all([loadStatus(), loadTasks()]);
            })
            .catch(function (err) {
                window.showToast('更新失败: ' + err.message, 'error');
            });
    }

    function refreshDashboardData() {
        window.showToast('正在刷新...', 'info', 1500);
        return Promise.all([loadStatus(), loadTasks()]);
    }

    window.initDashboardPage = function () {
        refreshDashboardData();
    };
    window.refreshDashboardData = refreshDashboardData;
    window.forceUpdateIP = forceUpdateIP;
    window.runTaskNow = runTaskNow;
})();
