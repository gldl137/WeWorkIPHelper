/* =============================================================================
 * 应用管理：添加 / 列表 / 启用开关 / 删除 / 名称编辑 / 单独更新可信IP
 * 全局暴露：initAppsPage / addApp / showAppIdHelp / toggleApp / deleteApp
 *           updateAppIP / editAppName
 * ========================================================================== */
(function () {
    'use strict';

    function loadApps() {
        return window
            .apiJSON('/api/apps')
            .then(function (data) {
                var tbody = document.getElementById('apps-table');
                if (!tbody) return;

                if (!data || data.success === false) {
                    tbody.innerHTML = '<tr><td colspan="5" class="empty-state">' +
                        window.escapeHtml((data && data.message) || '获取应用列表失败') + '</td></tr>';
                    return;
                }

                var apps = data.apps || [];
                if (!apps.length) {
                    tbody.innerHTML = '<tr><td colspan="5" class="empty-state">暂无应用，请先添加</td></tr>';
                    return;
                }

                tbody.innerHTML = apps
                    .map(function (app) {
                        var enabled = app.enabled === 1 || app.enabled === true;
                        var appId = window.escapeHtml(app.app_id);
                        return (
                            '<tr class="row-divider">' +
                            '<td class="text-center">' +
                            '<input type="checkbox" class="toggle toggle-success toggle-sm"' +
                            (enabled ? ' checked' : '') +
                            ' onchange="toggleApp(\'' + appId + '\')" />' +
                            '</td>' +
                            '<td><span class="editable-name" onclick="editAppName(\'' + appId + '\', \'' +
                            window.escapeHtml(app.app_name || '').replace(/'/g, "\\'") + '\')">' +
                            window.escapeHtml(app.app_name || '(未命名)') + '</span></td>' +
                            '<td class="font-mono text-sm">' + appId + '</td>' +
                            '<td class="text-sm text-base-content/70">' +
                            window.escapeHtml(app.remark || '-') +
                            (app.trusted_ip
                                ? '<div class="text-xs text-success mt-1">可信IP: ' +
                                  window.escapeHtml(app.trusted_ip) + '</div>'
                                : '') +
                            '</td>' +
                            '<td class="text-center whitespace-nowrap">' +
                            '<button class="btn btn-xs btn-info mr-1" onclick="updateAppIP(\'' + appId + '\')">更新IP</button>' +
                            '<button class="btn btn-xs btn-error" onclick="deleteApp(\'' + appId + '\')">删除</button>' +
                            '</td>' +
                            '</tr>'
                        );
                    })
                    .join('');
            })
            .catch(function (err) {
                window.showToast('获取应用列表失败: ' + err.message, 'error');
            });
    }

    function addApp() {
        var nameInput = document.getElementById('app-name-input');
        var idInput = document.getElementById('app-id-input');
        var remarkInput = document.getElementById('app-remark-input');
        if (!nameInput || !idInput) return;

        var appName = (nameInput.value || '').trim();
        var appId = (idInput.value || '').trim();
        var remark = remarkInput ? (remarkInput.value || '').trim() : '';

        if (!appName) {
            window.showToast('请输入应用名称', 'warning');
            nameInput.focus();
            return;
        }
        if (!appId) {
            window.showToast('请输入应用ID', 'warning');
            idInput.focus();
            return;
        }

        window
            .apiJSON('/api/apps', { method: 'POST', body: { app_id: appId, app_name: appName, remark: remark } })
            .then(function (data) {
                if (data && data.success) {
                    window.showToast('应用已添加', 'success');
                    nameInput.value = '';
                    idInput.value = '';
                    if (remarkInput) remarkInput.value = '';
                    loadApps();
                } else {
                    window.showToast((data && data.message) || '添加失败', 'error');
                }
            })
            .catch(function (err) {
                window.showToast('添加失败: ' + err.message, 'error');
            });
    }

    function toggleApp(appId) {
        window
            .apiJSON('/api/apps/' + encodeURIComponent(appId) + '/toggle', { method: 'POST' })
            .then(function (data) {
                window.showToast((data && data.message) || '状态已更新', data && data.success ? 'success' : 'error');
                loadApps();
            })
            .catch(function (err) {
                window.showToast('操作失败: ' + err.message, 'error');
                loadApps();
            });
    }

    function deleteApp(appId) {
        if (!window.confirm('确定删除应用 ' + appId + ' 吗？')) return;
        window
            .apiJSON('/api/apps/' + encodeURIComponent(appId), { method: 'DELETE' })
            .then(function (data) {
                window.showToast((data && data.message) || '已删除', data && data.success ? 'success' : 'error');
                loadApps();
            })
            .catch(function (err) {
                window.showToast('删除失败: ' + err.message, 'error');
            });
    }

    function editAppName(appId, currentName) {
        var name = window.prompt('修改应用名称', currentName || '');
        if (name === null) return;
        name = name.trim();
        if (!name) {
            window.showToast('应用名称不能为空', 'warning');
            return;
        }
        window
            .apiJSON('/api/apps/' + encodeURIComponent(appId), { method: 'PUT', body: { app_name: name } })
            .then(function (data) {
                window.showToast((data && data.message) || '名称已更新', data && data.success ? 'success' : 'error');
                loadApps();
            })
            .catch(function (err) {
                window.showToast('更新失败: ' + err.message, 'error');
            });
    }

    function updateAppIP(appId) {
        window.showToast('正在更新可信IP...', 'info');
        window
            .apiJSON('/api/ip/update_single', { method: 'POST', body: { app_id: appId } })
            .then(function (data) {
                window.showToast((data && data.message) || '更新完成', data && data.success ? 'success' : 'error');
                loadApps();
            })
            .catch(function (err) {
                window.showToast('更新失败: ' + err.message, 'error');
            });
    }

    function showAppIdHelp() {
        var mask = document.createElement('div');
        mask.className = 'modal-mask';
        mask.innerHTML =
            '<div class="modal-box" style="max-width:560px;">' +
            '<div class="modal-header"><h3 class="text-lg font-bold">如何获取应用ID</h3>' +
            '<button class="btn btn-sm btn-ghost" data-close>✕</button></div>' +
            '<div class="modal-body text-sm leading-7 text-base-content/80">' +
            '<p>1. 登录 <a class="link link-primary" href="https://work.weixin.qq.com" target="_blank">企业微信管理后台</a>；</p>' +
            '<p>2. 进入「应用管理」，打开目标应用；</p>' +
            '<p>3. 浏览器地址栏中 <code>app/</code> 后面的一串数字即为应用ID，例如：</p>' +
            '<p class="mt-2"><code class="bg-base-300/60 px-2 py-1 rounded">https://work.weixin.qq.com/wework_admin/frame#apps/app/5629501477633217/...</code></p>' +
            '<p class="mt-2 text-warning">注意：是企业微信「应用ID」，不是 AgentId。</p>' +
            '</div></div>';
        document.body.appendChild(mask);
        function close() {
            if (mask.parentNode) mask.parentNode.removeChild(mask);
        }
        mask.querySelector('[data-close]').addEventListener('click', close);
        // 不做「点击遮罩即关闭」，避免误触导致弹窗消失
    }

    window.initAppsPage = function () {
        loadApps();
    };
    window.addApp = addApp;
    window.showAppIdHelp = showAppIdHelp;
    window.toggleApp = toggleApp;
    window.deleteApp = deleteApp;
    window.editAppName = editAppName;
    window.updateAppIP = updateAppIP;
})();
