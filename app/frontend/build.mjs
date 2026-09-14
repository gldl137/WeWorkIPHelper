#!/usr/bin/env node
/**
 * =============================================================================
 * WeWorkIPHelper 前端构建脚本
 * -----------------------------------------------------------------------------
 * 产物目录（与 EmbyNotifyHub 结构一致）：
 *   frontend/src/**        -> app/backend/static/**       静态资源（js / css）
 *   frontend/templates/**  -> app/backend/templates/**    Jinja 模板
 *
 * 说明：
 *   本项目前端为 Flask 服务端渲染（Jinja 模板 + 原生 JS，模板中通过
 *   onclick 调用全局函数），因此不做打包（打包会破坏全局函数），构建只做
 *   「产物归位 + 引用版本号注入」，以便统一从 backend 目录托管。
 *
 * 用法：
 *   cd app/frontend && npm run build
 * 环境变量：
 *   BUILD_VERSION  自定义产物版本号（默认取构建时间 yyyyMMddHHmm）
 * =============================================================================
 */
import {
    cpSync,
    mkdirSync,
    readFileSync,
    readdirSync,
    rmSync,
    statSync,
    writeFileSync
} from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const APP_DIR = resolve(__dirname, '..');

const SRC_DIR = join(__dirname, 'src');
const TPL_DIR = join(__dirname, 'templates');
const OUT_STATIC = join(APP_DIR, 'backend', 'static');
const OUT_TEMPLATES = join(APP_DIR, 'backend', 'templates');

const version =
    (process.env.BUILD_VERSION || '').trim() ||
    new Date().toISOString().replace(/\D/g, '').slice(0, 12);

const log = (msg) => console.log(`[build-frontend] ${msg}`);

function assertDir(dir, label) {
    let stat;
    try {
        stat = statSync(dir);
    } catch (e) {
        throw new Error(`${label}不存在: ${dir}`);
    }
    if (!stat.isDirectory()) throw new Error(`${label}不是目录: ${dir}`);
}

function copyDir(src, dest) {
    // 尽力清理旧产物。个别环境（删除被回收站/trash 机制接管）会失败，
    // 此时降级为「直接覆盖」，不影响构建结果。
    try {
        rmSync(dest, { recursive: true, force: true });
    } catch (err) {
        console.warn(`[build-frontend] [WARN] 清理旧产物失败，改为直接覆盖: ${String(err.message).split('\n')[0]}`);
    }
    mkdirSync(dest, { recursive: true });
    cpSync(src, dest, { recursive: true, force: true });
}

/** 将模板中所有 ?v=xxx 的版本号替换为本次构建版本（缓存失效） */
function injectVersion(dir) {
    let changed = 0;
    for (const name of readdirSync(dir)) {
        const full = join(dir, name);
        if (statSync(full).isDirectory()) {
            changed += injectVersion(full);
            continue;
        }
        if (!name.endsWith('.html')) continue;

        const html = readFileSync(full, 'utf8');
        const next = html.replace(/(\?v=)[^"'&\s]+/g, `$1${version}`);
        if (next !== html) {
            writeFileSync(full, next, 'utf8');
            changed += 1;
        }
    }
    return changed;
}

try {
    assertDir(SRC_DIR, '前端资源源码目录');
    assertDir(TPL_DIR, '前端模板源码目录');

    log(`构建版本: ${version}`);

    log(`资源: ${SRC_DIR} -> ${OUT_STATIC}`);
    copyDir(SRC_DIR, OUT_STATIC);

    log(`模板: ${TPL_DIR} -> ${OUT_TEMPLATES}`);
    copyDir(TPL_DIR, OUT_TEMPLATES);
    const touched = injectVersion(OUT_TEMPLATES);
    log(`已注入版本号: ${touched} 个模板文件`);

    log('前端构建完成 ✅');
} catch (err) {
    console.error(`[build-frontend] [ERROR] ${err.message}`);
    process.exit(1);
}
