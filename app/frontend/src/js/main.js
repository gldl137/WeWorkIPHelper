/* =============================================================================
 * 应用入口：页面路由 / 导航 / 日志查看 / 退出登录
 * 全局暴露：showPage / handleNavClick / toggleMobileSidebar / closeMobileSidebar
 *           showLogs / handleLogout
 * ========================================================================== */
(function () {
    'use strict';

    var PAGES = {
        dashboard: { title: '仪表盘', template: 'dashboard.html', init: 'initDashboardPage' },
        apps: { title: '应用管理', template: 'apps.html', init: 'initAppsPage' },
        login: { title: '企微登录', template: 'cookie.html', init: 'initCookiePage' },
        settings: { title: '系统设置', template: 'settings.html', init: 'initSettingsPage' }
    };

    var currentPage = null;
    var loading = false;

    /* ---------------- 侧边栏 ---------------- */
    function openMobileSidebar() {
        var nav = document.getElementById('sidebar-nav');
        var overlay = document.getElementById('mobile-overlay');
        if (nav) nav.classList.add('open');
        if (overlay) overlay.classList.add('show');
    }

    function closeMobileSidebar() {
        var nav = document.getElementById('sidebar-nav');
        var overlay = document.getElementById('mobile-overlay');
        if (nav) nav.classList.remove('open');
        if (overlay) overlay.classList.remove('show');
    }

    function toggleMobileSidebar() {
        var nav = document.getElementById('sidebar-nav');
        if (nav && nav.classList.contains('open')) {
            closeMobileSidebar();
        } else {
            openMobileSidebar();
        }
    }

    function setActiveNav(page) {
        var links = document.querySelectorAll('.sidebar-menu-link');
        Array.prototype.forEach.call(links, function (link) {
            link.classList.toggle('active', link.getAttribute('data-page') === page);
        });
    }

    /* ---------------- 页面加载 ---------------- */
    function renderPlaceholder() {
        return (
            '<div class="flex flex-col items-center justify-center min-h-[60vh]">' +
            '<div class="loading-spinner lg"></div>' +
            '<p class="mt-6 text-lg text-base-content/60 animate-pulse">正在加载...</p>' +
            '</div>'
        );
    }

    function showPage(page) {
        if (!PAGES[page]) page = 'dashboard';
        if (loading || page === currentPage) {
            setActiveNav(page);
            return;
        }

        currentPage = page;
        loading = true;
        setActiveNav(page);
        closeMobileSidebar();

        var meta = PAGES[page];
        document.title = '企微 IP 助手 | ' + meta.title;

        if (window.location.hash !== '#' + page) {
            history.replaceState(null, '', '#' + page);
        }

        var container = document.getElementById('page-content');
        if (container) container.innerHTML = renderPlaceholder();

        fetch('/templates/' + meta.template, { cache: 'no-cache' })
            .then(function (res) {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.text();
            })
            .then(function (html) {
                if (container) container.innerHTML = html;
                if (meta.init && typeof window[meta.init] === 'function') {
                    window[meta.init]();
                }
                // 页面内可能带有需要初始化的组件（如开关状态）
                var event = document.createEvent('Event');
                event.initEvent('page:loaded', true, true);
                document.dispatchEvent(event);
            })
            .catch(function (err) {
                if (container) {
                    container.innerHTML =
                        '<div class="empty-state">页面加载失败: ' + window.escapeHtml(err.message) + '</div>';
                }
                window.showToast('页面加载失败: ' + err.message, 'error');
            })
            .then(function () {
                loading = false;
            });
    }

    function handleNavClick(event, page) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        showPage(page);
    }

    /* ---------------- 日志查看 ---------------- */
    function showLogs() {
        var mask = document.createElement('div');
        mask.className = 'modal-mask';
        mask.innerHTML =
            '<div class="modal-box">' +
            '<div class="modal-header">' +
            '<h3 class="text-lg font-bold">系统日志（最近 100 行 · 最新在上）</h3>' +
            '<div class="flex gap-2">' +
            '<button class="btn btn-sm btn-ghost" data-refresh>刷新</button>' +
            '<button class="btn btn-sm btn-ghost" data-close>✕</button>' +
            '</div></div>' +
            '<div class="modal-body"><div class="log-viewer" data-logs>加载中...</div></div>' +
            '</div>';
        document.body.appendChild(mask);

        var logArea = mask.querySelector('[data-logs]');

        function close() {
            if (mask.parentNode) mask.parentNode.removeChild(mask);
        }

        function load() {
            logArea.textContent = '加载中...';
            window
                .apiJSON('/api/logs')
                .then(function (data) {
                    var logs = (data && data.logs) || [];
                    // 接口返回的是文件顺序（旧 -> 新）：反转后最新一条在最上面。
                    // 统一去掉行尾换行再以 \n 拼接，避免首/末行粘连。
                    var ordered = logs
                        .slice()
                        .reverse()
                        .map(function (line) {
                            return String(line).replace(/\r?\n$/, '');
                        });
                    logArea.textContent = ordered.length ? ordered.join('\n') + '\n' : '暂无日志';
                    logArea.scrollTop = 0;
                })
                .catch(function (err) {
                    logArea.textContent = '加载失败: ' + err.message;
                });
        }

        mask.querySelector('[data-close]').addEventListener('click', close);
        mask.querySelector('[data-refresh]').addEventListener('click', load);
        // 不做「点击遮罩即关闭」，避免误触导致弹窗消失；仅通过 ✕ 关闭
        load();
    }

    /* ---------------- 退出登录 ---------------- */
    function handleLogout() {
        if (!window.confirm('确定退出登录吗？（不会清除企业微信 Cookie）')) return;
        window
            .apiJSON('/api/logout', { method: 'POST' })
            .catch(function () {
                /* 忽略接口异常，仍需清除本地状态 */
            })
            .then(function () {
                window.AppState.clearToken();
                window.showToast('已退出登录', 'success', 1200);
                setTimeout(function () {
                    window.location.reload();
                }, 800);
            });
    }

    /* ---------------- 启动 ---------------- */
    function startApp(initialPage) {
        // 首次进入强制加载（绕过 currentPage 去重）
        currentPage = null;
        showPage(initialPage);

        window.addEventListener('hashchange', function () {
            var page = (window.location.hash || '').replace(/^#/, '');
            if (PAGES[page]) showPage(page);
        });

        document.body.classList.add('page-ready');
    }

    function bootstrap() {
        if (window.AppState.APP_DATA.needInit) {
            window.location.href = '/init';
            return;
        }

        var hash = (window.location.hash || '').replace(/^#/, '');
        var initialPage = PAGES[hash] ? hash : 'dashboard';

        // 鉴权通过前不渲染任何项目页面内容：
        // 期间 body 带 auth-required（隐藏侧边栏与主内容）；
        // 若未通过鉴权，utils 会显示全屏登录界面，登录成功后才会继续。
        document.body.classList.add('auth-required');
        window
            .apiJSON('/api/config')
            .catch(function () {
                return { success: false };
            })
            .then(function () {
                document.body.classList.remove('auth-required');
                startApp(initialPage);
            });
    }

    window.showPage = showPage;
    window.handleNavClick = handleNavClick;
    window.toggleMobileSidebar = toggleMobileSidebar;
    window.closeMobileSidebar = closeMobileSidebar;
    window.showLogs = showLogs;
    window.handleLogout = handleLogout;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bootstrap);
    } else {
        bootstrap();
    }
})();
