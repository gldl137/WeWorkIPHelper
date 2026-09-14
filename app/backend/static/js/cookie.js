/* =============================================================================
 * 登录凭证（Cookie）管理
 * 全局暴露：initCookiePage / saveCookies / testCookie / refreshSavedCookie
 *           deleteSavedCookie
 * ========================================================================== */
(function () {
    'use strict';

    function renderSavedCookie(data) {
        var display = document.getElementById('saved-cookie-display');
        var timeDisplay = document.getElementById('cookie-time-display');
        if (!display) return;

        var cookies = (data && data.cookies) || '';
        if (cookies) {
            display.innerHTML =
                '<div class="h-full overflow-y-auto whitespace-pre-wrap break-all">' +
                window.escapeHtml(cookies) + '</div>';
        } else {
            display.innerHTML =
                '<div class="flex items-center justify-center h-full text-base-content/50">' +
                '暂无已保存的 Cookie</div>';
        }

        if (timeDisplay) {
            timeDisplay.textContent = data && data.cookie_saved_time
                ? '保存时间：' + window.formatDateTime(data.cookie_saved_time)
                : '';
        }
    }

    function loadSavedCookie() {
        var display = document.getElementById('saved-cookie-display');
        if (display) {
            display.innerHTML =
                '<div class="flex items-center justify-center h-full">' +
                '<span class="loading loading-spinner loading-sm mr-2"></span>加载中...</div>';
        }
        return window
            .apiJSON('/api/status')
            .then(function (data) {
                if (data && data.success === false) {
                    window.showToast(data.message || '读取 Cookie 失败', 'error');
                }
                renderSavedCookie(data || {});
            })
            .catch(function (err) {
                window.showToast('读取 Cookie 失败: ' + err.message, 'error');
            });
    }

    function currentCookieValue() {
        var input = document.getElementById('cookie-input');
        return input ? (input.value || '').trim() : '';
    }

    function saveCookies() {
        var cookies = currentCookieValue();
        if (!cookies) {
            window.showToast('请先粘贴 Cookie', 'warning');
            var input = document.getElementById('cookie-input');
            if (input) input.focus();
            return;
        }
        window
            .apiJSON('/api/save_cookies', { method: 'POST', body: { cookies: cookies } })
            .then(function (data) {
                if (data && data.success) {
                    window.showToast('Cookie 已保存', 'success');
                    document.getElementById('cookie-input').value = '';
                    loadSavedCookie();
                } else {
                    window.showToast((data && data.message) || '保存失败', 'error');
                }
            })
            .catch(function (err) {
                window.showToast('保存失败: ' + err.message, 'error');
            });
    }

    function testCookie() {
        var cookies = currentCookieValue();
        if (cookies) {
            doTest(cookies);
            return;
        }
        // 输入框为空时，测试已保存的 Cookie
        window
            .apiJSON('/api/status')
            .then(function (data) {
                if (data && data.cookies) {
                    doTest(data.cookies);
                } else {
                    window.showToast('请先输入或保存 Cookie', 'warning');
                }
            })
            .catch(function (err) {
                window.showToast('测试失败: ' + err.message, 'error');
            });
    }

    function doTest(cookies) {
        window.showToast('正在测试 Cookie...', 'info', 1500);
        window
            .apiJSON('/api/test_cookies', { method: 'POST', body: { cookies: cookies } })
            .then(function (data) {
                window.showToast((data && data.message) || '测试完成', data && data.success ? 'success' : 'error');
            })
            .catch(function (err) {
                window.showToast('测试失败: ' + err.message, 'error');
            });
    }

    function refreshSavedCookie() {
        window.showToast('已刷新', 'success', 1500);
        loadSavedCookie();
    }

    function deleteSavedCookie() {
        if (!window.confirm('确定删除已保存的 Cookie 吗？删除后需要重新登录企业微信。')) return;
        window
            .apiJSON('/api/clear_cookies', { method: 'POST' })
            .then(function (data) {
                window.showToast((data && data.message) || '已删除', data && data.success ? 'success' : 'error');
                loadSavedCookie();
            })
            .catch(function (err) {
                window.showToast('删除失败: ' + err.message, 'error');
            });
    }

    window.initCookiePage = function () {
        loadSavedCookie();
    };
    window.saveCookies = saveCookies;
    window.testCookie = testCookie;
    window.refreshSavedCookie = refreshSavedCookie;
    window.deleteSavedCookie = deleteSavedCookie;
})();
