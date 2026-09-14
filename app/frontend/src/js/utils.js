/* =============================================================================
 * 通用工具：页面数据、认证 token、API 封装、Toast、全屏登录界面
 * 全局暴露：AppState / apiFetch / apiJSON / showToast / showLoginScreen
 *           escapeHtml / formatDateTime
 * ========================================================================== */
(function () {
    'use strict';

    var TOKEN_KEY = 'wework_api_token';

    /* ---------------- 页面注入数据（base.html 的 #app-data） ---------------- */
    function readAppData() {
        var el = document.getElementById('app-data');
        if (!el) {
            return { apiToken: '', needInit: false, webhookUrl: '' };
        }
        function parse(value, fallback) {
            if (value === undefined || value === null || value === '') return fallback;
            try {
                return JSON.parse(value);
            } catch (e) {
                return value;
            }
        }
        return {
            apiToken: parse(el.dataset.apiToken, '') || '',
            needInit: parse(el.dataset.needInit, false) === true,
            webhookUrl: parse(el.dataset.webhookUrl, '') || ''
        };
    }

    var APP_DATA = readAppData();

    function getToken() {
        // 只使用登录（/api/verify_password）换取的随机 token，
        // 不回退到页面注入值 —— 避免把管理密码作为请求头明文发送。
        return localStorage.getItem(TOKEN_KEY) || '';
    }

    function setToken(token) {
        if (token) localStorage.setItem(TOKEN_KEY, token);
    }

    function clearToken() {
        localStorage.removeItem(TOKEN_KEY);
    }

    /* ---------------- 工具函数 ---------------- */
    function escapeHtml(value) {
        if (value === undefined || value === null) return '';
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function formatDateTime(value) {
        if (!value) return '-';
        var date = value instanceof Date ? value : new Date(value);
        if (isNaN(date.getTime())) return String(value);
        function pad(n) {
            return n < 10 ? '0' + n : '' + n;
        }
        // 形如 2026/4/12 00:19:51
        return (
            date.getFullYear() + '/' + (date.getMonth() + 1) + '/' + date.getDate() +
            ' ' + pad(date.getHours()) + ':' + pad(date.getMinutes()) + ':' + pad(date.getSeconds())
        );
    }

    function showToast(message, type, duration) {
        if (!message) return;
        type = type || 'info';
        duration = duration || 3000;

        var container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }

        var colors = {
            success: '#16a34a',
            error: '#dc2626',
            warning: '#d97706',
            info: '#0284c7'
        };

        var item = document.createElement('div');
        item.className = 'toast-item';
        item.style.background = colors[type] || colors.info;
        item.textContent = message;
        container.appendChild(item);

        setTimeout(function () {
            item.classList.add('out');
            setTimeout(function () {
                if (item.parentNode) item.parentNode.removeChild(item);
            }, 250);
        }, duration);
    }

    /* ---------------- 全屏登录界面 ----------------
     * 未通过鉴权前调用：以不透明全屏层覆盖整个视口，并隐藏应用框架
     * （侧边栏 / 主内容），确保登录界面背后不会出现项目页面内容。
     * 只有登录成功才 resolve(true)，因此调用方可安全地「等登录完成再渲染」。
     */
    var authScreen = null;
    var authResolvers = null;

    function showLoginScreen(message) {
        return new Promise(function (resolve) {
            // 已有登录界面：复用同一结果
            if (authResolvers) {
                authResolvers.push(resolve);
                return;
            }
            authResolvers = [resolve];

            document.body.classList.add('auth-required');

            authScreen = document.createElement('div');
            authScreen.id = 'auth-screen';
            authScreen.innerHTML =
                '<div class="auth-card">' +
                '<div class="auth-logo">' +
                '<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">' +
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />' +
                '</svg></div>' +
                '<h1 class="auth-title">企微 IP 助手</h1>' +
                '<p class="auth-subtitle">' + escapeHtml(message || '请输入管理密码以继续') + '</p>' +
                '<input id="auth-password" type="password" class="input input-bordered w-full auth-input" placeholder="管理密码" autocomplete="current-password" />' +
                '<div id="auth-error" class="auth-error" style="display:none;"></div>' +
                '<button class="btn btn-primary w-full mt-4" id="auth-submit">登 录</button>' +
                '</div>';

            document.body.appendChild(authScreen);

            var input = authScreen.querySelector('#auth-password');
            var submitBtn = authScreen.querySelector('#auth-submit');
            var errorBox = authScreen.querySelector('#auth-error');
            var submitting = false;

            function setError(text) {
                if (!text) {
                    errorBox.style.display = 'none';
                    errorBox.textContent = '';
                    return;
                }
                errorBox.textContent = text;
                errorBox.style.display = 'block';
            }

            function finish(ok) {
                if (authScreen && authScreen.parentNode) authScreen.parentNode.removeChild(authScreen);
                authScreen = null;
                if (ok) document.body.classList.remove('auth-required');

                var resolvers = authResolvers || [];
                authResolvers = null;
                resolvers.forEach(function (fn) {
                    fn(ok);
                });
            }

            function submit() {
                if (submitting) return;
                var password = (input.value || '').trim();
                if (!password) {
                    setError('请输入管理密码');
                    input.focus();
                    return;
                }
                submitting = true;
                setError('');
                submitBtn.disabled = true;
                submitBtn.textContent = '登录中...';

                fetch('/api/verify_password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password: password })
                })
                    .then(function (res) {
                        return res.json().catch(function () {
                            return { success: false, message: '响应解析失败' };
                        });
                    })
                    .then(function (data) {
                        if (data && data.success && data.token) {
                            setToken(data.token);
                            finish(true);
                        } else {
                            setError((data && data.message) || '密码错误');
                            submitting = false;
                            submitBtn.disabled = false;
                            submitBtn.textContent = '登 录';
                            input.select();
                        }
                    })
                    .catch(function (err) {
                        setError('登录失败: ' + err.message);
                        submitting = false;
                        submitBtn.disabled = false;
                        submitBtn.textContent = '登 录';
                    });
            }

            submitBtn.addEventListener('click', submit);
            input.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') submit();
            });
            setTimeout(function () {
                input.focus();
            }, 50);
        });
    }

    /* ---------------- API 封装 ---------------- */
    function apiFetch(url, options, retry) {
        options = options || {};
        if (retry === undefined) retry = true;

        var headers = Object.assign({}, options.headers || {});
        var token = getToken();
        if (token) headers['X-API-KEY'] = token;

        if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(options.body);
        }
        options.headers = headers;

        return fetch(url, options).then(function (res) {
            if (res.status !== 401 || !retry) return res;

            return res
                .clone()
                .json()
                .catch(function () {
                    return {};
                })
                .then(function (payload) {
                    if (payload && payload.admin_token_exists === false) {
                        // 尚未设置管理密码，进入初始化向导
                        clearToken();
                        setTimeout(function () {
                            window.location.href = '/init';
                        }, 400);
                        return res;
                    }

                    // 弹出全屏登录界面（不透明覆盖，背后不显示项目内容）
                    return showLoginScreen(payload && payload.message).then(function (ok) {
                        if (!ok) return res;
                        return apiFetch(url, options, false);
                    });
                });
        });
    }

    function apiJSON(url, options) {
        return apiFetch(url, options).then(function (res) {
            return res
                .json()
                .catch(function () {
                    return { success: false, message: '响应解析失败 (HTTP ' + res.status + ')' };
                });
        });
    }

    window.AppState = {
        APP_DATA: APP_DATA,
        getToken: getToken,
        setToken: setToken,
        clearToken: clearToken
    };
    window.apiFetch = apiFetch;
    window.apiJSON = apiJSON;
    window.showToast = showToast;
    window.showLoginScreen = showLoginScreen;
    window.escapeHtml = escapeHtml;
    window.formatDateTime = formatDateTime;
})();
