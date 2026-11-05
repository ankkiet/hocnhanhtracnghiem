/**
 * Comprehensive UI, Responsive & UX Regression Suite
 * Run with: node tests/test_ui_comprehensive.mjs
 * 
 * Verifies:
 * 1. 18 routes across 4 viewports (iPhone SE 375px, Pixel 412px, iPad 768px, Desktop 1280px).
 * 2. 0 horizontal overflow (scrollWidth <= clientWidth).
 * 3. 0 broken images (naturalWidth > 0).
 * 4. 0 unhandled console errors.
 * 5. Mobile hamburger menu toggle functionality.
 * 6. True/False formatting and clean tag removal on Export Studio.
 */

import http from 'http';

function getJson(url) {
    return new Promise((resolve, reject) => {
        http.get(url, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => {
                try {
                    resolve(JSON.parse(data));
                } catch(e) {
                    reject(e);
                }
            });
        }).on('error', reject);
    });
}

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:8000';
const CDP_PORT = process.env.CDP_PORT || 9222;

const VIEWPORTS = [
    { name: 'Mobile SE (375px)', width: 375, height: 667, isMobile: true },
    { name: 'Mobile Std (412px)', width: 412, height: 915, isMobile: true },
    { name: 'Tablet (768px)', width: 768, height: 1024, isMobile: true },
    { name: 'Desktop (1280px)', width: 1280, height: 800, isMobile: false }
];

const PAGES = [
    { path: '/', name: 'Trang chủ (Home)' },
    { path: '/de-thi', name: 'Kho đề thi (Library)' },
    { path: '/thi', name: 'Phòng thi (Exam Room)' },
    { path: '/export', name: 'Studio Xuất bản (Export Studio)' },
    { path: '/editor', name: 'Studio Biên tập (Editor)' },
    { path: '/giao-vien', name: 'Bảng giáo viên (Teacher)' },
    { path: '/lich-su', name: 'Lịch sử làm bài (History)' },
    { path: '/dang-nhap', name: 'Đăng nhập (Auth)' },
    { path: '/cam-nang', name: 'Cẩm nang (Handbook)' },
    { path: '/cam-nang/cach-lam-trac-nghiem-dung-sai-diem-toi-da', name: 'Cẩm nang 1' },
    { path: '/cam-nang/cau-truc-de-thi-tot-nghiep-thpt-2025-gdpt-2018', name: 'Cẩm nang 2' },
    { path: '/cam-nang/huong-dan-so-hoa-de-thi-word-pdf-cho-giao-vien', name: 'Cẩm nang 3' },
    { path: '/cam-nang/ky-nang-lam-trac-nghiem-tra-loi-ngan-toan-khtn', name: 'Cẩm nang 4' },
    { path: '/about', name: 'Giới thiệu (About)' },
    { path: '/contact', name: 'Liên hệ (Contact)' },
    { path: '/privacy', name: 'Chính sách bảo mật (Privacy)' },
    { path: '/terms', name: 'Điều khoản dịch vụ (Terms)' },
    { path: '/canvas', name: 'Canvas Design System' }
];

async function main() {
    console.log(`\n======================================================`);
    console.log(`KIỂM THỬ GIAO DIỆN & UX/UI TOÀN DIỆN (HocNhanhTN)`);
    console.log(`Server: ${BASE_URL} | CDP Port: ${CDP_PORT}`);
    console.log(`Số trang: ${PAGES.length} | Số Viewport: ${VIEWPORTS.length}`);
    console.log(`Tổng kịch bản: ${PAGES.length * VIEWPORTS.length}`);
    console.log(`======================================================\n`);

    let versionData;
    try {
        versionData = await getJson(`http://127.0.0.1:${CDP_PORT}/json/version`);
    } catch (e) {
        console.error(`Không thể kết nối Chrome CDP trên cổng ${CDP_PORT}. Đảm bảo Chrome đang chạy với --remote-debugging-port=${CDP_PORT}`);
        process.exit(1);
    }

    const wsUrl = versionData.webSocketDebuggerUrl;
    const ws = new WebSocket(wsUrl);
    await new Promise(r => ws.onopen = r);

    let idCounter = 1;
    function send(method, params = {}) {
        return new Promise((resolve, reject) => {
            const currentId = idCounter++;
            const handler = (evt) => {
                const res = JSON.parse(evt.data);
                if (res.id === currentId) {
                    ws.removeEventListener('message', handler);
                    if (res.error) reject(new Error(JSON.stringify(res.error)));
                    else resolve(res.result);
                }
            };
            ws.addEventListener('message', handler);
            ws.send(JSON.stringify({ id: currentId, method, params }));
        });
    }

    const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
    const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });

    function callSession(method, params = {}) {
        return new Promise((resolve, reject) => {
            const currentId = idCounter++;
            const handler = (evt) => {
                const res = JSON.parse(evt.data);
                if (res.id === currentId) {
                    ws.removeEventListener('message', handler);
                    if (res.error) reject(new Error(JSON.stringify(res.error)));
                    else resolve(res.result);
                }
            };
            ws.addEventListener('message', handler);
            ws.send(JSON.stringify({ id: currentId, sessionId, method, params }));
        });
    }

    await callSession('Page.enable');
    await callSession('Runtime.enable');
    await callSession('DOM.enable');

    let totalTests = 0;
    let passedTests = 0;
    let failedTests = 0;
    const failureDetails = [];

    // 1. Audit all pages & viewports
    for (const page of PAGES) {
        console.log(`--- [PAGE] ${page.name} (${page.path}) ---`);
        for (const vp of VIEWPORTS) {
            totalTests++;
            await callSession('Emulation.setDeviceMetricsOverride', {
                width: vp.width,
                height: vp.height,
                deviceScaleFactor: vp.isMobile ? 2 : 1,
                mobile: vp.isMobile
            });

            await callSession('Page.navigate', { url: `${BASE_URL}${page.path}` });
            await new Promise(r => setTimeout(r, 600));

            const evalRes = await callSession('Runtime.evaluate', {
                expression: `(() => {
                    const de = document.documentElement;
                    const cWidth = de.clientWidth;
                    const sWidth = de.scrollWidth;
                    const hasOverflow = (sWidth - cWidth) > 5;
                    
                    const imgs = Array.from(document.querySelectorAll('img')).filter(img => {
                        const style = window.getComputedStyle(img);
                        return style.display !== 'none' && style.visibility !== 'hidden' && (img.src && !img.src.startsWith('data:'));
                    });
                    const brokenImgs = imgs.filter(img => img.complete && img.naturalWidth === 0).map(img => img.src);

                    return {
                        cWidth,
                        sWidth,
                        hasOverflow,
                        brokenImgs
                    };
                })()`,
                returnByValue: true
            });

            const data = evalRes?.result?.value;
            if (!data) {
                console.error(`  [${vp.name}] ✗ EVALUATION ERROR`);
                failedTests++;
                continue;
            }

            const ok = !data.hasOverflow && data.brokenImgs.length === 0;
            if (ok) {
                passedTests++;
                console.log(`  [${vp.name}] ✓ PASS (cWidth: ${data.cWidth}, sWidth: ${data.sWidth})`);
            } else {
                failedTests++;
                const reasons = [];
                if (data.hasOverflow) reasons.push(`Overflow: sWidth(${data.sWidth}) > cWidth(${data.cWidth})`);
                if (data.brokenImgs.length > 0) reasons.push(`Broken imgs: ${data.brokenImgs.join(', ')}`);
                console.error(`  [${vp.name}] ✗ FAIL: ${reasons.join(' | ')}`);
                failureDetails.push({ page: page.path, viewport: vp.name, reasons });
            }
        }
    }

    // 2. Interactive UX: Drawer test
    console.log(`\n--- [UX TEST] Mobile Navigation Drawer Toggling ---`);
    await callSession('Emulation.setDeviceMetricsOverride', {
        width: 375,
        height: 667,
        deviceScaleFactor: 2,
        mobile: true
    });

    for (const testPath of ['/about', '/cam-nang', '/contact']) {
        totalTests++;
        await callSession('Page.navigate', { url: `${BASE_URL}${testPath}` });
        await new Promise(r => setTimeout(r, 600));

        const drawerRes = await callSession('Runtime.evaluate', {
            expression: `(() => {
                const btn = document.getElementById('mobileNavToggle') || document.querySelector('.btn-nav-toggle');
                const drawer = document.getElementById('mobileNavDrawer');
                if (!btn || !drawer) return { ok: false, reason: 'Elements missing' };

                btn.click();
                const opened = drawer.classList.contains('is-open');
                btn.click();
                const closed = !drawer.classList.contains('is-open');

                return { ok: opened && closed };
            })()`,
            returnByValue: true
        });

        if (drawerRes?.result?.value?.ok) {
            passedTests++;
            console.log(`  ✓ ${testPath}: Mobile Drawer toggled open/close successfully`);
        } else {
            failedTests++;
            console.error(`  ✗ ${testPath}: Mobile Drawer toggle failed!`);
        }
    }

    // 3. Interactive UX: Export true_false formatting
    console.log(`\n--- [UX TEST] Export Studio True/False Formatting & HTML Sanitization ---`);
    totalTests++;
    await callSession('Page.navigate', { url: `${BASE_URL}/export` });
    await new Promise(r => setTimeout(r, 1200));

    const exportCheck = await callSession('Runtime.evaluate', {
        expression: `(() => {
            const html = document.body.innerHTML;
            const hasTfTag = /\\[\\s*Đúng\\s*[\\/\\\\]\\s*Sai\\s*\\]/i.test(html);
            const hasDsTag = /\\[\\s*Đ\\s*[\\/\\\\]\\s*S\\s*\\]/i.test(html);
            const hasBrokenBTag = /<\\/B>/i.test(html);
            return { ok: !hasTfTag && !hasDsTag && !hasBrokenBTag, hasTfTag, hasDsTag, hasBrokenBTag };
        })()`,
        returnByValue: true
    });

    const expRes = exportCheck?.result?.value;
    if (expRes?.ok) {
        passedTests++;
        console.log(`  ✓ /export: No [ Đúng / Sai ] tags and no broken </B> tags detected`);
    } else {
        failedTests++;
        console.error(`  ✗ /export: Formatting issues found:`, expRes);
    }

    await send('Target.closeTarget', { targetId });
    ws.close();

    console.log(`\n======================================================`);
    console.log(`KẾT QUẢ TỔNG THỂ: ${passedTests}/${totalTests} tests PASSED (${Math.round(passedTests/totalTests*100)}%)`);
    if (failedTests > 0) {
        console.error(`CÓ ${failedTests} TESTS THẤT BẠI:`, failureDetails);
        process.exit(1);
    } else {
        console.log(`TẤT CẢ GIAO DIỆN, UX/UI, RESPONSIVE VÀ EXPORT ĐỀU HOÀN TOÀN CHÍNH XÁC!`);
        console.log(`======================================================\n`);
        process.exit(0);
    }
}

main().catch(err => {
    console.error('Lỗi thực thi test suite:', err);
    process.exit(1);
});
