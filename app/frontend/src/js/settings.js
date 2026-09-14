/* =============================================================================
 * 系统设置：密码 / 通知与 Webhook / 定时任务 cron / 可信域名验证
 * 全局暴露：initSettingsPage / updatePassword / updateWebhook / testWebhook
 *           toggleNotification / updateTaskCrons / toggleVerifyService
 *           refreshVerifyFiles / deleteSelectedVerifyFile / handleVerifyFileSelect
 * ========================================================================== */
(function () {
    'use strict';

    var TASK_CRON_FIELDS = {
        login_check: 'task-login-check',
        public_ip_check: 'task-public-ip-check'
    };

    /* ---------------- 配置加载 ---------------- */
    function loadConfig() {
        return window
            .apiJSON('/api/config')
            .then(function (data) {
                if (!data || data.success === false) return;
                var config = data.config || {};

                var webhookInput = document.getElementById('settings-webhook-url');
                if (webhookInput) webhookInput.value = config.wecom_webhook_url || '';

                var notificationSwitch = document.getElementById('notification-enabled');
                var notificationText = document.getElementById('notification-status-text');
                var notificationOn = Number(config.notification_enabled) === 1;
                if (notificationSwitch) notificationSwitch.checked = notificationOn;
                if (notificationText) notificationText.textContent = notificationOn ? '已启用' : '已禁用';

                var verifySwitch = document.getElementById('verify-enabled');
                var verifyText = document.getElementById('verify-status-text');
                var verifyOn = Number(config.verify_enabled) === 1;
                if (verifySwitch) verifySwitch.checked = verifyOn;
                if (verifyText) verifyText.textContent = verifyOn ? '已启用' : '已禁用';

                Object.keys(TASK_CRON_FIELDS).forEach(function (taskId) {
                    var key = TASK_CRON_FIELDS[taskId];
                    var field = document.getElementById(key);
                    if (!field) return;
                    if (taskId === 'login_check') field.value = config.login_check_cron || '0 * * * *';
                    if (taskId === 'public_ip_check') field.value = config.public_ip_check_cron || '*/30 * * * *';
                });

                var verifyAddress = document.getElementById('verify-address');
                if (verifyAddress && !verifyAddress.textContent.trim()) {
                    verifyAddress.textContent = window.location.protocol + '//' + window.location.hostname + ':5001';
                }
            })
            .catch(function (err) {
                window.showToast('加载配置失败: ' + err.message, 'error');
            });
    }

    /* ---------------- 密码 ---------------- */
    function updatePassword(event) {
        if (event) event.preventDefault();
        var newPassword = document.getElementById('settings-new-password');
        var confirmPassword = document.getElementById('settings-confirm-password');
        if (!newPassword || !confirmPassword) return;

        var pwd = (newPassword.value || '').trim();
        var confirm = (confirmPassword.value || '').trim();

        if (pwd.length < 6) {
            window.showToast('密码至少 6 位', 'warning');
            return;
        }
        if (pwd !== confirm) {
            window.showToast('两次输入的密码不一致', 'warning');
            return;
        }
        if (!window.confirm('确定修改管理密码吗？修改后需要重新登录。')) return;

        window
            .apiJSON('/api/config', { method: 'POST', body: { admin_token: pwd } })
            .then(function (data) {
                if (data && data.success) {
                    window.showToast('密码已更新，请重新登录', 'success');
                    window.AppState.clearToken();
                    setTimeout(function () {
                        window.location.reload();
                    }, 1200);
                } else {
                    window.showToast((data && data.message) || '修改失败', 'error');
                }
            })
            .catch(function (err) {
                window.showToast('修改失败: ' + err.message, 'error');
            });
    }

    /* ---------------- 通知 / Webhook ---------------- */
    function updateWebhook(event) {
        if (event) event.preventDefault();
        var input = document.getElementById('settings-webhook-url');
        var notificationSwitch = document.getElementById('notification-enabled');
        var url = input ? (input.value || '').trim() : '';

        if (url && !/^https?:\/\//i.test(url)) {
            window.showToast('Webhook 地址需以 http:// 或 https:// 开头', 'warning');
            return;
        }

        window
            .apiJSON('/api/config', {
                method: 'POST',
                body: {
                    wecom_webhook_url: url,
                    notification_enabled: notificationSwitch && notificationSwitch.checked ? 1 : 0
                }
            })
            .then(function (data) {
                window.showToast((data && data.message) || '配置已保存', data && data.success ? 'success' : 'error');
            })
            .catch(function (err) {
                window.showToast('保存失败: ' + err.message, 'error');
            });
    }

    function toggleNotification() {
        var switchEl = document.getElementById('notification-enabled');
        var textEl = document.getElementById('notification-status-text');
        if (!switchEl) return;
        var enabled = switchEl.checked;
        window
            .apiJSON('/api/notification/toggle', { method: 'POST', body: { enabled: enabled } })
            .then(function (data) {
                var ok = data && data.success;
                if (textEl) textEl.textContent = enabled ? '已启用' : '已禁用';
                if (ok) {
                    window.showToast(enabled ? '通知已启用' : '通知已禁用', 'success', 2000);
                } else {
                    window.showToast((data && data.message) || '操作失败', 'error');
                    switchEl.checked = !enabled;
                    if (textEl) textEl.textContent = !enabled ? '已启用' : '已禁用';
                }
            })
            .catch(function (err) {
                window.showToast('操作失败: ' + err.message, 'error');
            });
    }

    function testWebhook() {
        var input = document.getElementById('settings-webhook-url');
        var url = input ? (input.value || '').trim() : '';
        if (!url) {
            window.showToast('请先填写 Webhook 地址', 'warning');
            return;
        }
        window.showToast('正在发送测试消息...', 'info', 2000);
        window
            .apiJSON('/api/config/test-webhook', { method: 'POST', body: { webhook_url: url } })
            .then(function (data) {
                window.showToast((data && data.message) || '测试完成', data && data.success ? 'success' : 'error');
            })
            .catch(function (err) {
                window.showToast('测试失败: ' + err.message, 'error');
            });
    }

    /* ---------------- 定时任务 cron ---------------- */
    function updateTaskCrons(event) {
        if (event) event.preventDefault();
        var payloads = [];
        var invalid = false;
        Object.keys(TASK_CRON_FIELDS).forEach(function (taskId) {
            var field = document.getElementById(TASK_CRON_FIELDS[taskId]);
            if (!field) return;
            var cron = (field.value || '').trim();
            if (!cron) {
                invalid = true;
                return;
            }
            payloads.push({ taskId: taskId, cron: cron });
        });
        if (invalid) {
            window.showToast('cron 表达式不能为空', 'warning');
            return;
        }

        var chain = Promise.resolve(true);
        payloads.forEach(function (item) {
            chain = chain.then(function (ok) {
                if (!ok) return false;
                return window
                    .apiJSON('/api/tasks/' + encodeURIComponent(item.taskId) + '/cron', {
                        method: 'POST',
                        body: { cron: item.cron }
                    })
                    .then(function (data) {
                        var success = data && data.success;
                        window.showToast(
                            (data && data.message) || (success ? '已保存' : '保存失败'),
                            success ? 'success' : 'error'
                        );
                        return success;
                    });
            });
        });
        chain.catch(function (err) {
            window.showToast('保存失败: ' + err.message, 'error');
        });
    }

    /* ---------------- 可信域名验证 ---------------- */
    function toggleVerifyService() {
        var switchEl = document.getElementById('verify-enabled');
        var textEl = document.getElementById('verify-status-text');
        if (!switchEl) return;
        var enabled = switchEl.checked;
        window
            .apiJSON('/api/verify/toggle', { method: 'POST', body: { enabled: enabled } })
            .then(function (data) {
                var ok = data && data.success;
                if (ok) {
                    if (textEl) textEl.textContent = enabled ? '已启用' : '已禁用';
                    window.showToast(enabled ? '验证服务已启用（重启后生效）' : '验证服务已禁用（重启后生效）', 'success', 2500);
                } else {
                    window.showToast((data && data.message) || '操作失败', 'error');
                    switchEl.checked = !enabled;
                }
            })
            .catch(function (err) {
                window.showToast('操作失败: ' + err.message, 'error');
            });
    }

    function loadVerifyFiles() {
        var list = document.getElementById('verify-files-list');
        if (!list) return;
        list.innerHTML = '<div class="text-base-content/60 text-sm">加载中...</div>';

        window
            .apiJSON('/api/verify/files')
            .then(function (data) {
                if (!data || data.success === false) {
                    list.innerHTML = '<div class="text-error text-sm">' +
                        window.escapeHtml((data && data.message) || '加载失败') + '</div>';
                    return;
                }
                var files = data.files || [];
                if (!files.length) {
                    list.innerHTML = '<div class="text-base-content/60 text-sm">暂无验证文件</div>';
                    return;
                }
                list.innerHTML = files
                    .map(function (name) {
                        return (
                            '<label class="flex items-center gap-3 p-3 rounded-lg bg-base-300/40 border border-base-content/10 cursor-pointer">' +
                            '<input type="checkbox" class="checkbox checkbox-sm verify-file-checkbox" value="' +
                            window.escapeHtml(name) + '" />' +
                            '<span class="font-mono text-sm break-all">' + window.escapeHtml(name) + '</span>' +
                            '</label>'
                        );
                    })
                    .join('');
            })
            .catch(function (err) {
                list.innerHTML = '<div class="text-error text-sm">加载失败: ' + window.escapeHtml(err.message) + '</div>';
            });
    }

    function refreshVerifyFiles() {
        window.showToast('已刷新', 'success', 1500);
        loadVerifyFiles();
    }

    function deleteSelectedVerifyFile() {
        var checked = Array.prototype.slice.call(document.querySelectorAll('.verify-file-checkbox:checked'));
        if (!checked.length) {
            window.showToast('请先选择要删除的文件', 'warning');
            return;
        }
        if (!window.confirm('确定删除选中的 ' + checked.length + ' 个验证文件吗？')) return;

        var chain = Promise.resolve(true);
        checked.forEach(function (box) {
            chain = chain.then(function (ok) {
                if (!ok) return false;
                return window
                    .apiJSON('/api/verify/files/' + encodeURIComponent(box.value), { method: 'DELETE' })
                    .then(function (data) {
                        var success = data && data.success;
                        if (!success) {
                            window.showToast((data && data.message) || '删除失败', 'error');
                        }
                        return success;
                    });
            });
        });
        chain.then(function (ok) {
            if (ok) window.showToast('删除完成', 'success');
            loadVerifyFiles();
        });
    }

    function handleVerifyFileSelect(input) {
        if (!input || !input.files || !input.files.length) return;
        var file = input.files[0];
        if (!/\.txt$/i.test(file.name)) {
            window.showToast('只能上传 .txt 文件', 'warning');
            input.value = '';
            return;
        }

        var formData = new FormData();
        formData.append('file', file);

        window.showToast('正在上传...', 'info', 1500);
        window
            .apiFetch('/api/verify/upload', { method: 'POST', body: formData })
            .then(function (res) {
                return res.json().catch(function () {
                    return { success: false, message: 'HTTP ' + res.status };
                });
            })
            .then(function (data) {
                window.showToast((data && data.message) || '上传完成', data && data.success ? 'success' : 'error');
                loadVerifyFiles();
            })
            .catch(function (err) {
                window.showToast('上传失败: ' + err.message, 'error');
            })
            .then(function () {
                input.value = '';
            });
    }

    /* ---------------- 获取验证文件的方法说明 ---------------- */
    function showVerifyFileHelp() {
        var mask = document.createElement('div');
        mask.className = 'modal-mask';
        mask.innerHTML =
            '<div class="modal-box" style="max-width:620px;">' +
            '<div class="modal-header">' +
            '<h3 class="text-lg font-bold">如何获取可信域名验证文件</h3>' +
            '<button class="btn btn-sm btn-ghost" data-close>✕</button>' +
            '</div>' +
            '<div class="modal-body text-sm leading-7 text-base-content/80">' +
            '<p>1. 登录 <a class="link link-primary" href="https://work.weixin.qq.com" target="_blank" rel="noopener">企业微信管理后台</a>；</p>' +
            '<p>2. 进入「应用管理」，打开需要配置的自建应用（或网站应用）；</p>' +
            '<p>3. 找到「网页授权及JS-SDK」→ 点击「设置可信域名」<span class="text-base-content/50">（不同版本可能在「开发者接口」下）</span>；</p>' +
            '<p>4. 在弹窗中点击「下载文件」，得到一个 <code class="bg-base-300/60 px-1 rounded">WW_verify_xxxxxxxx.txt</code> 文件；</p>' +
            '<p>5. 回到本页，点击「上传」选择该 txt 文件；</p>' +
            '<p>6. 让验证地址可被外网访问：本验证服务默认监听 <code class="bg-base-300/60 px-1 rounded">5001</code> 端口，' +
            '通过域名解析 / 反向代理，使 <code class="bg-base-300/60 px-1 rounded">http://你的域名/WW_verify_xxxxxxxx.txt</code> ' +
            '能返回文件内容；</p>' +
            '<p>7. 回到企业微信后台点击「验证」，通过后即生效。</p>' +
            '<p class="mt-3 text-base-content/60">说明：验证服务会把「验证文件管理」中第一个 .txt 文件的内容直接返回给任意路径的请求，' +
            '因此只需保证该地址能访问即可。</p>' +
            '</div></div>';

        document.body.appendChild(mask);

        function close() {
            if (mask.parentNode) mask.parentNode.removeChild(mask);
        }
        mask.querySelector('[data-close]').addEventListener('click', close);
        // 不做「点击遮罩即关闭」，避免误触导致弹窗消失
    }

    window.initSettingsPage = function () {
        loadConfig();
        loadVerifyFiles();
    };
    window.updatePassword = updatePassword;
    window.updateWebhook = updateWebhook;
    window.toggleNotification = toggleNotification;
    window.testWebhook = testWebhook;
    window.updateTaskCrons = updateTaskCrons;
    window.toggleVerifyService = toggleVerifyService;
    window.refreshVerifyFiles = refreshVerifyFiles;
    window.deleteSelectedVerifyFile = deleteSelectedVerifyFile;
    window.handleVerifyFileSelect = handleVerifyFileSelect;
    window.showVerifyFileHelp = showVerifyFileHelp;
})();
