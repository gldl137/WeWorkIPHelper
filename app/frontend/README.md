# WeWorkIPHelper 前端源码 (frontend/)

本目录是**前端源码**，构建产物输出到后端目录，由 Flask 统一托管。

## 目录结构

```
frontend/
├─ src/                 # 前端源码
│  ├─ js/               # 原生 JS（utils / dashboard / cookie / apps / settings / main / init）
│  └─ css/              # 自定义样式 style.css
├─ templates/           # Jinja 模板源码（index / base / dashboard / cookie / apps / settings / init）
├─ build.mjs            # 构建脚本（Node，零依赖）
└─ package.json         # 构建入口：npm run build
```

## 构建

```bash
cd app/frontend
npm run build          # 等价于 node build.mjs
```

构建产物：

| 源 | 产物 |
|----|------|
| `frontend/src/**` | `app/backend/static/**` |
| `frontend/templates/**` | `app/backend/templates/**` |

同时会把模板中所有 `?v=xxx` 的版本号替换为本次构建版本（默认取构建时间 `yyyyMMddHHmm`，可用环境变量 `BUILD_VERSION` 覆盖），用于浏览器缓存失效。

## 为什么不用 Vite/Webpack 打包

后端为 Flask 服务端渲染（Jinja 模板），页面内的 DOM 事件大量使用 `onclick="someGlobalFn()"`
的形式，依赖函数处于全局作用域。打包（IIFE/模块化）会使这些全局函数失效，
因此这里只做「产物归位 + 版本号注入」，保持源码与产物行为一致。

## 开发约定

- 改动 `frontend/src` 或 `frontend/templates` 后**必须重新构建**，后端才会读到新内容。
- 也可直接运行 `bash ../scripts/build-frontend.sh`（内部执行 `npm run build`）。
- `app/backend/static` 与 `app/backend/templates` 为构建产物，随仓库提交以便 Docker 直接构建。
