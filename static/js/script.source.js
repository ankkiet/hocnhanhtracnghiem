// Tự động nhận diện môi trường (Localhost vs Production)
const PROD_BACKEND_URL = "https://inland-marylin-hocnhanhtn-c3471a95.koyeb.app";
let API_BASE_URL = PROD_BACKEND_URL;

const currentHost = window.location.hostname || '';
const isLocal = 
    window.location.protocol === 'file:' ||
    currentHost === 'localhost' || 
    currentHost === '127.0.0.1' || 
    currentHost.startsWith('192.168.') || 
    currentHost.startsWith('10.') || 
    currentHost.endsWith('.local');

if (isLocal) {
    // Chạy cục bộ / offline / máy dev
    API_BASE_URL = (window.location.port === '8000') ? window.location.origin : "http://127.0.0.1:8000";
} else if (currentHost.includes('koyeb.app') || currentHost.includes('ngrok')) {
    // Phục vụ trực tiếp từ server backend hoặc tunnel ngrok
    API_BASE_URL = window.location.origin;
} else {
    // Tất cả tên miền production tĩnh (Cloudflare Pages, hocnhanhtn.online, *.pages.dev, vercel, netlify...)
    API_BASE_URL = PROD_BACKEND_URL;
}

// Hỗ trợ override linh hoạt qua localStorage nếu cần trỏ đến máy chủ khác
if (typeof localStorage !== 'undefined' && localStorage.getItem('CUSTOM_API_BASE_URL')) {
    API_BASE_URL = localStorage.getItem('CUSTOM_API_BASE_URL');
}

// Tự động gửi tín hiệu đánh thức máy chủ Backend ngay khi mở trang (Chống Sleep / Cold Start)
fetch(`${API_BASE_URL}/api/health`, { method: 'GET', cache: 'no-store' }).catch(() => {});

// Cờ tính năng WebLLM (mặc định tắt theo yêu cầu, bật lại bằng cách đặt ENABLE_WEBLLM = true)
window.ENABLE_WEBLLM = (typeof window.ENABLE_WEBLLM !== 'undefined') ? window.ENABLE_WEBLLM : false;

let currentData = [];
let serverData = []; // Lưu trữ dữ liệu gốc mới nhất từ Server để phục hồi khi làm lại
let currentMode = 'edit';
let currentQuestionIndex = 0;
let practiceScore = 0;
let practiceAnswered = false;
let timerInterval;
let currentTimeLimit = 0;
let editingQuizId = null;

let studentName = "";
let startTime = 0;
let isStudentMode = false;
let currentDataMode = 'practice';
let isShuffleEnabled = false;
let quizProgress = {};
let currentQuizServerUpdatedAt = 0;
let adminApiKeys = [];
let isShowingTrash = false;

// UI States
let activeQuizFilter = 'all'; // 'all' | 'published' | 'unpublished' | 'trashed'
let rawTeacherQuizzes = [];
let flaggedQuestions = {}; // { [qIndex]: true/false }

function showToast(message, type = 'info') {
    const container = document.getElementById('azotaToastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `azota-toast toast-${type}`;
    let icon = 'ri-information-line';
    if (type === 'success') icon = 'ri-checkbox-circle-line';
    else if (type === 'error') icon = 'ri-error-warning-line';
    else if (type === 'warning') icon = 'ri-alert-line';
    
    toast.innerHTML = `<i class="${icon}" style="font-size: 1.25rem;"></i> <span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3200);
}
window.showToast = showToast;

// ========================================================
// HOCNHANHTN BRAND LOADER SYSTEM
// ========================================================
function getHntnLoaderSvgHtml(uniqueId = 'hntn_' + Math.random().toString(36).substr(2, 6)) {
    return `<svg class="hntn-loader-svg" viewBox="0 0 500 500" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="pGrad_${uniqueId}" x1="0%" x2="100%" y1="100%" y2="0%">
                <stop offset="0%" stop-color="#2d4af3"></stop>
                <stop offset="50%" stop-color="#2d79f3"></stop>
                <stop offset="100%" stop-color="#00d2ff"></stop>
            </linearGradient>
            <linearGradient id="blGrad_${uniqueId}" x1="0%" x2="100%" y1="0%" y2="100%">
                <stop offset="0%" stop-color="#00b4ff"></stop>
                <stop offset="100%" stop-color="#3b46e8"></stop>
            </linearGradient>
            <linearGradient id="brGrad_${uniqueId}" x1="0%" x2="100%" y1="0%" y2="100%">
                <stop offset="0%" stop-color="#00e5ff"></stop>
                <stop offset="100%" stop-color="#2b59f5"></stop>
            </linearGradient>
            <linearGradient id="cGrad_${uniqueId}" x1="0%" x2="100%" y1="0%" y2="100%">
                <stop offset="0%" stop-color="#00d2ff"></stop>
                <stop offset="50%" stop-color="#2d79f3"></stop>
                <stop offset="100%" stop-color="#1d4ed8"></stop>
            </linearGradient>
            <filter id="glow_${uniqueId}" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3.5" result="blur"></feGaussianBlur>
                <feComposite in="SourceGraphic" in2="blur" operator="over"></feComposite>
            </filter>
            <style>
                @keyframes fadeAndSlideDownDisappear {
                    0% { opacity: 1; transform: translateY(0px); }
                    35% { opacity: 1; transform: translateY(0px); }
                    60% { opacity: 0.5; transform: translateY(35px); }
                    90%, 100% { opacity: 0; transform: translateY(90px); visibility: hidden; }
                }
                .disappearing-elements {
                    animation: fadeAndSlideDownDisappear 1.7s cubic-bezier(0.4, 0, 0.2, 1) forwards;
                }
                @keyframes checkmarkKickUp {
                    0% { transform: translateY(0px) rotate(0deg); }
                    10% { transform: translateY(6px) rotate(-2deg); }
                    24% { transform: translateY(-24px) rotate(5deg) scale(1.05); }
                    40% { transform: translateY(-4px) rotate(1deg); }
                    55%, 100% { transform: translateY(0px) rotate(0deg); }
                }
                @keyframes capKickedJumpSpin {
                    0% { transform: translateY(0px) rotate(0deg) scale(1); }
                    10% { transform: translateY(4px) rotate(-1deg) scale(1.01, 0.98); }
                    26% { transform: translateY(-56px) rotate(90deg) scale(1.12); }
                    48% { transform: translateY(-44px) rotate(240deg) scale(1.08); }
                    68% { transform: translateY(3px) rotate(360deg) scale(0.97, 1.03); }
                    78% { transform: translateY(-5px) rotate(360deg) scale(1.01); }
                    88%, 100% { transform: translateY(0px) rotate(360deg) scale(1); }
                }
                .tick-interactive-group {
                    transform-box: view-box;
                    transform-origin: 250px 280px;
                    animation: checkmarkKickUp 2.2s cubic-bezier(0.34, 1.3, 0.64, 1) infinite;
                    animation-delay: 1.1s;
                }
                .cap-kicked-group {
                    transform-box: view-box;
                    transform-origin: 250px 185px;
                    animation: capKickedJumpSpin 2.2s cubic-bezier(0.34, 1.25, 0.64, 1) infinite;
                    animation-delay: 1.1s;
                }
            </style>
        </defs>
        <g id="loaderGroup_${uniqueId}">
            <g class="disappearing-elements">
                <path d="M 250 372 L 140 334 C 134 332 130 326 130 320 L 130 216 C 130 210 137 206 143 208 L 148 210 L 148 316 L 250 352 L 352 316 L 352 210 L 357 208 C 363 206 370 210 370 216 L 370 320 C 370 326 366 332 360 334 Z" fill="url(#blGrad_${uniqueId})"></path>
                <path d="M 250 354 L 158 322 C 153 320 150 315 150 310 L 150 196 C 150 190 157 186 162 188 L 168 190 L 168 306 L 250 335 L 332 306 L 332 190 L 338 188 C 343 186 350 190 350 196 L 350 310 C 350 315 347 320 342 322 Z" fill="url(#brGrad_${uniqueId})"></path>
                <path d="M 250 336 L 178 310 L 178 198 L 188 202 L 188 298 L 250 320 L 312 298 L 312 202 L 322 198 L 322 310 Z" fill="#2d6ef3" opacity="0.95"></path>
                <path d="M 176 194 C 176 190 180 186 186 188 L 206 195 L 206 312 L 176 302 Z" fill="url(#pGrad_${uniqueId})"></path>
                <path d="M 294 228 L 324 216 L 324 302 L 294 312 Z" fill="url(#brGrad_${uniqueId})"></path>
                <path d="M 366 128 Q 366 146 384 146 Q 366 146 366 164 Q 366 146 348 146 Q 366 146 366 128 Z" fill="#00e5ff"></path>
                <path d="M 326 128 Q 326 138 336 138 Q 326 138 326 148 Q 326 138 316 138 Q 326 138 326 128 Z" fill="#38bdf8"></path>
                <path d="M 364 178 Q 364 188 374 188 Q 364 188 364 198 Q 364 188 354 188 Q 364 188 364 178 Z" fill="#38bdf8"></path>
            </g>
            <g class="tick-interactive-group">
                <path d="M 186 260 L 230 262 L 250 300 C 251 302 254 302 255 300 L 358 160 C 362 154 358 146 350 152 L 250 274 L 226 246 C 224 244 220 244 218 246 L 186 256 Z" fill="url(#pGrad_${uniqueId})" filter="url(#glow_${uniqueId})"></path>
                <path d="M 250 300 L 358 160 C 362 154 358 146 350 152 L 250 274 Z" fill="#00f5ff" opacity="0.6"></path>
            </g>
            <g class="cap-kicked-group">
                <polygon fill="url(#cGrad_${uniqueId})" filter="url(#glow_${uniqueId})" points="250,138 324,168 250,198 176,168"></polygon>
                <polygon fill="#1e40af" opacity="0.9" points="250,198 324,168 324,178 250,208 176,178 176,168"></polygon>
                <path d="M 210 184 L 210 224 C 210 236 226 244 250 244 C 274 244 290 236 290 224 L 290 184 C 278 193 264 198 250 198 C 236 198 222 193 210 184 Z" fill="#1d4ed8"></path>
                <path d="M 292 180 L 302 186 L 302 204 L 298 204 L 298 186 Z" fill="#00e5ff"></path>
                <circle cx="250" cy="168" fill="#00f5ff" r="4.5"></circle>
            </g>
        </g>
    </svg>`;
}

function renderHntnInlineLoader(title = "Đang tải dữ liệu...", subtitle = "", size = 80) {
    const uniqueId = 'inline_' + Math.random().toString(36).substr(2, 6);
    return `
    <div class="hntn-inline-loader">
        <div class="hntn-loader-wrapper" style="width: ${size}px; height: ${size}px; margin-bottom: 12px;">
            <div class="hntn-loader-glow" style="width: ${Math.round(size * 0.75)}px; height: ${Math.round(size * 0.75)}px;"></div>
            ${getHntnLoaderSvgHtml(uniqueId)}
        </div>
        <div class="hntn-inline-title">${title}</div>
        ${subtitle ? `<div class="hntn-inline-sub">${subtitle}</div>` : ''}
    </div>`;
}

function resetHntnLoader(container) {
    if (!container) return;
    const svg = container.querySelector('.hntn-loader-svg');
    if (svg && svg.parentNode) {
        const clone = svg.cloneNode(true);
        svg.parentNode.replaceChild(clone, svg);
    }
}

function showGlobalLoader(options = {}) {
    const title = (typeof options === 'string') ? options : (options.title || "Đang xử lý...");
    const subtitle = (typeof options === 'string') ? "" : (options.subtitle || "Vui lòng chờ trong giây lát...");
    const showProgress = (typeof options === 'object' && options.showProgress === true);
    const progress = (typeof options === 'object' && typeof options.progress === 'number') ? options.progress : 0;
    
    const overlay = document.getElementById('loadingOverlay');
    if (!overlay) return;
    
    const titleEl = document.getElementById('loadingStatusText');
    const subEl = document.getElementById('loadingStatusSub');
    const progText = document.getElementById('progressText');
    const progBar = document.getElementById('progressBar');
    const progContainer = document.getElementById('progressBarContainer') || (progBar ? progBar.parentElement : null);
    
    if (titleEl) titleEl.innerHTML = title;
    if (subEl) {
        subEl.innerHTML = subtitle;
        subEl.style.display = subtitle ? 'block' : 'none';
    }
    
    if (progContainer) {
        progContainer.style.display = showProgress ? 'block' : 'none';
    }
    if (progText) {
        progText.style.display = showProgress ? 'block' : 'none';
        progText.innerText = `${Math.round(progress)}%`;
    }
    if (progBar && showProgress) {
        progBar.style.width = `${Math.round(progress)}%`;
    }
    
    resetHntnLoader(overlay);
    overlay.style.display = 'flex';
}

function updateGlobalLoader(options = {}) {
    const overlay = document.getElementById('loadingOverlay');
    if (!overlay || overlay.style.display === 'none') return;
    
    if (options.title) {
        const titleEl = document.getElementById('loadingStatusText');
        if (titleEl) titleEl.innerHTML = options.title;
    }
    if (options.subtitle !== undefined) {
        const subEl = document.getElementById('loadingStatusSub');
        if (subEl) {
            subEl.innerHTML = options.subtitle;
            subEl.style.display = options.subtitle ? 'block' : 'none';
        }
    }
    if (typeof options.progress === 'number') {
        const progText = document.getElementById('progressText');
        const progBar = document.getElementById('progressBar');
        const progContainer = document.getElementById('progressBarContainer') || (progBar ? progBar.parentElement : null);
        if (progContainer) progContainer.style.display = 'block';
        if (progText) {
            progText.style.display = 'block';
            progText.innerText = `${Math.round(options.progress)}%`;
        }
        if (progBar) {
            progBar.style.width = `${Math.round(options.progress)}%`;
        }
    }
}

function hideGlobalLoader() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}

function hidePageInitialLoader() {
    const preloader = document.getElementById('pageInitialLoader');
    if (!preloader) return;
    preloader.classList.add('hntn-loaded');
    setTimeout(() => {
        if (preloader.parentNode) preloader.parentNode.removeChild(preloader);
    }, 450);
}

window.getHntnLoaderSvgHtml = getHntnLoaderSvgHtml;
window.renderHntnInlineLoader = renderHntnInlineLoader;
window.resetHntnLoader = resetHntnLoader;
window.showGlobalLoader = showGlobalLoader;
window.updateGlobalLoader = updateGlobalLoader;
window.hideGlobalLoader = hideGlobalLoader;
window.hidePageInitialLoader = hidePageInitialLoader;

// Khởi tạo bộ nhớ tạm để thu gọn mã Base64 ảnh trong Code Editor
let globalEditorImageStorage = {};
let globalEditorImageCounter = 0;

// Lưu trữ danh sách gợi ý sửa lỗi của AI gắn với từng câu hỏi
window.activeAIFeedbacks = {};

let authToken = localStorage.getItem('auth_token');
let authRole = localStorage.getItem('auth_role');
let authName = localStorage.getItem('auth_name');

function getTeacherTokenParam() {
    return (authRole === 'teacher' || authRole === 'admin') && authToken ? authToken : '';
}

// Sinh ID ngẫu nhiên cho phiên làm việc để phục vụ Giám sát thi
let clientSessionId = sessionStorage.getItem('client_session_id');
if (!clientSessionId) {
    clientSessionId = 'sess_' + Math.random().toString(36).substr(2, 9);
    sessionStorage.setItem('client_session_id', clientSessionId);
}
let heartbeatInterval;

// Biến quản lý xác thực Google Sign-In
let googleClientId = '';
let googleTokenClient = null;

function renderMath(targetElement) {
    // Nếu không truyền targetElement cụ thể và đang ở chế độ sửa thì bỏ qua để bảo toàn textarea Code Editor
    if (!targetElement && currentMode === 'edit') return;
    
    if (window.MathJax && typeof window.MathJax.typesetPromise === 'function') {
        try {
            if (targetElement && typeof window.MathJax.typesetClear === 'function') {
                window.MathJax.typesetClear([targetElement]);
            }
            const promise = targetElement 
                ? window.MathJax.typesetPromise([targetElement]) 
                : window.MathJax.typesetPromise();
            if (promise && typeof promise.catch === 'function') {
                promise.catch((err) => console.warn('MathJax typeset error:', err));
            }
        } catch (e) {
            console.warn('MathJax invocation error:', e);
        }
    } else if (typeof window.ensureMathJaxLoaded === 'function') {
        window.ensureMathJaxLoaded().then(() => {
            renderMath(targetElement);
        }).catch((err) => console.warn('MathJax lazy load failed:', err));
    } else {
        // Chờ MathJax tải xong (do thẻ script là async)
        setTimeout(() => renderMath(targetElement), 400);
    }
}

// Khởi tạo ngay lập tức khi DOM vừa sẵn sàng (DOMContentLoaded) để loại bỏ hoàn toàn FOUC / độ trễ
document.addEventListener('DOMContentLoaded', function() {
    checkAuthState();
    initGoogleAuth();
    updateAdPassUI();
    initOfflineDetection();
    initKeyboardShortcuts();
});

window.onload = async function() {
    // Đảm bảo đồng bộ lại nếu có tài nguyên tải chậm
    checkAuthState();
    setTimeout(hidePageInitialLoader, 4000);
};

function escapeHtml(str) {
    if (typeof str !== 'string') return str;
    return str.replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;')
              .replace(/'/g, '&#039;');
}

// Hàm chuyển đổi bảng Markdown (| ... | ... |) thành bảng HTML chuyên nghiệp
function renderMarkdownTables(text) {
    if (!text || typeof text !== 'string' || text.indexOf('|') === -1) return text;
    let textNorm = text.replace(/\\n/g, '\n').replace(/<br\s*\/?>/gi, '\n');
    let lines = textNorm.split('\n');
    let result = [];
    let tableLines = [];
    let inTable = false;

    function processTable(tbl) {
        let validRows = tbl.map(l => l.trim()).filter(l => l.includes('|'));
        if (validRows.length < 2) return tbl.join('<br>');
        let rowsData = [];
        let hasSeparator = false;
        for (let r of validRows) {
            let cleaned = r.replace(/^\|/, '').replace(/\|$/, '');
            let cells = cleaned.split('|').map(c => c.trim());
            let isSep = cells.length > 0 && cells.every(c => /^:?-+:?$/.test(c));
            if (isSep) { hasSeparator = true; continue; }
            rowsData.push(cells);
        }
        if (rowsData.length === 0) return tbl.join('<br>');
        let maxCols = Math.max(...rowsData.map(r => r.length));
        let html = '<div class="quiz-table-wrapper" style="overflow-x: auto; margin: 12px 0; display: block;"><table class="quiz-content-table" style="margin: 0 auto; border-collapse: collapse; border: 1.5px solid #cbd5e1; border-radius: 6px; background: #fff; text-align: center;">';
        let startIdx = 0;
        if (hasSeparator && rowsData.length > 0) {
            html += '<thead><tr>';
            for (let c of rowsData[0]) {
                html += '<th style="border: 1px solid #cbd5e1; padding: 6px 14px; background: #f8fafc; font-weight: 600; text-align: center;">' + c + '</th>';
            }
            for (let i = rowsData[0].length; i < maxCols; i++) {
                html += '<th style="border: 1px solid #cbd5e1; padding: 6px 14px; background: #f8fafc;"></th>';
            }
            html += '</tr></thead>';
            startIdx = 1;
        }
        html += '<tbody>';
        for (let i = startIdx; i < rowsData.length; i++) {
            let row = rowsData[i];
            html += '<tr>';
            for (let c of row) {
                html += '<td style="border: 1px solid #cbd5e1; padding: 6px 14px; text-align: center;">' + c + '</td>';
            }
            for (let j = row.length; j < maxCols; j++) {
                html += '<td style="border: 1px solid #cbd5e1; padding: 6px 14px;"></td>';
            }
            html += '</tr>';
        }
        html += '</tbody></table></div>';
        return html;
    }

    for (let line of lines) {
        let stripped = line.trim();
        if (stripped.startsWith('|') || (stripped.endsWith('|') && stripped.includes('|'))) {
            tableLines.push(stripped);
            inTable = true;
        } else {
            if (inTable) {
                result.push(processTable(tableLines));
                tableLines = [];
                inTable = false;
            }
            result.push(line);
        }
    }
    if (inTable) result.push(processTable(tableLines));
    return result.join('\n');
}

// Hàm chuẩn hóa & hiển thị nội dung phong phú (LaTeX, In đậm, In nghiêng, Hình ảnh Base64/URL, Xuống dòng)
function formatRichContent(content) {
    if (content === null || content === undefined) return '';
    let str = String(content).trim();
    if (!str) return '';

    // 0. Nếu chuỗi đã từng bị escape trước đó (vd: &lt;b&gt;, &lt;img ...&gt;), khôi phục lại các thẻ an toàn
    str = str.replace(/&lt;(\/?(?:b|strong|i|em|u|s|sub|sup|span|mark|font|p|div|br|img|table|thead|tbody|tfoot|tr|th|td))\b([^&]*)&gt;/gi, '<$1$2>');

    // 1. Bảo vệ toàn bộ công thức toán LaTeX ($$...$$, \[...\], \(...\), $...$)
    const mathBlocks = [];
    str = str.replace(/\$\$([\s\S]*?)\$\$/g, (m) => {
        mathBlocks.push(m);
        return `\uFFF0MATH${mathBlocks.length - 1}\uFFF1`;
    });
    str = str.replace(/\\\[([\s\S]*?)\\\]/g, (m) => {
        mathBlocks.push(m);
        return `\uFFF0MATH${mathBlocks.length - 1}\uFFF1`;
    });
    str = str.replace(/\\\(([\s\S]*?)\\\)/g, (m) => {
        mathBlocks.push(m);
        return `\uFFF0MATH${mathBlocks.length - 1}\uFFF1`;
    });
    str = str.replace(/\\begin\{(?:array|matrix|pmatrix|bmatrix|cases|aligned|align\*?)\}[\s\S]*?\\end\{(?:array|matrix|pmatrix|bmatrix|cases|aligned|align\*?)\}/gi, (m) => {
        mathBlocks.push(m);
        return `\uFFF0MATH${mathBlocks.length - 1}\uFFF1`;
    });
    str = str.replace(/(^|[^\\])\$([^\$\n]+?)\$/g, (m, prefix, mathContent) => {
        mathBlocks.push(`$${mathContent}$`);
        return `${prefix}\uFFF0MATH${mathBlocks.length - 1}\uFFF1`;
    });

    // 1.5. Chuyển đổi bảng Markdown sang bảng HTML có cấu trúc
    str = renderMarkdownTables(str);

    // 2. Phục hồi ảnh từ bộ nhớ tạm Code Editor nếu có placeholder [HÌNH_ẢNH_X]
    if (typeof globalEditorImageStorage === 'object' && globalEditorImageStorage !== null) {
        for (let key in globalEditorImageStorage) {
            str = str.split(key).join(globalEditorImageStorage[key]);
        }
    }

    // 3. Bảo vệ thẻ <img> (tránh regex ảnh hưởng đến chuỗi Base64 dài)
    const imgBlocks = [];
    str = str.replace(/<img[^>]+src=['"][^'"]+['"][^>]*\/?>/gi, (m) => {
        let safeImg = m;
        if (!/style\s*=/i.test(safeImg)) {
            safeImg = safeImg.replace(/<img/i, '<img style="max-width:100%; max-height:360px; height:auto; border-radius:8px; display:block; margin:8px auto; object-fit:contain;"');
        } else {
            safeImg = safeImg.replace(/style=['"]([^'"]*)['"]/i, (sm, st) => {
                return `style="${st}; max-width:100%; border-radius:8px; object-fit:contain;"`;
            });
        }
        imgBlocks.push(safeImg);
        return `\uFFF0IMG${imgBlocks.length - 1}\uFFF1`;
    });

    // 4. Chuyển đổi cú pháp ảnh Markdown ![alt](url)
    str = str.replace(/!\[([^\]]*)\]\((https?:\/\/[^\s\)]+|data:image\/[^\s\)]+)\)/gi, (m, alt, url) => {
        const imgTag = `<img src="${url}" alt="${alt || ''}" style="max-width:100%; max-height:360px; height:auto; border-radius:8px; display:block; margin:8px auto; object-fit:contain;">`;
        imgBlocks.push(imgTag);
        return `\uFFF0IMG${imgBlocks.length - 1}\uFFF1`;
    });

    // 5. Bảo vệ các thẻ HTML định dạng hợp lệ: <b>, <i>, <u>, <s>, <sub>, <sup>, <span>, <mark>, <font>, <p>, <div>, <br>, <table>
    const tagBlocks = [];
    str = str.replace(/<\/?(?:b|strong|i|em|u|s|strike|sub|sup|span|mark|font|p|div|br|table|thead|tbody|tfoot|tr|th|td)\b[^>]*>/gi, (m) => {
        tagBlocks.push(m);
        return `\uFFF0TAG${tagBlocks.length - 1}\uFFF1`;
    });

    // 6. Thoát các ký tự so sánh < và > còn sót lại trên văn bản thuần (ví dụ: x < 5, 0 < m < 2)
    str = str.replace(/</g, '&lt;').replace(/>/g, '&gt;');

    // 7. Xử lý Markdown formatting trên văn bản thuần:
    str = str.replace(/\*\*([^\*\n]+?)\*\*/g, '<b>$1</b>');
    str = str.replace(/__([^_\n]+?)__/g, '<u>$1</u>');

    // 8. Chuyển đổi xuống dòng: \r\n, \r, \n, \\n -> <br>
    str = str.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>');

    // 9. Phục hồi lại các khối đã bảo vệ
    tagBlocks.forEach((tag, idx) => {
        str = str.split(`\uFFF0TAG${idx}\uFFF1`).join(tag);
    });
    imgBlocks.forEach((img, idx) => {
        str = str.split(`\uFFF0IMG${idx}\uFFF1`).join(img);
    });
    mathBlocks.forEach((math, idx) => {
        str = str.split(`\uFFF0MATH${idx}\uFFF1`).join(math);
    });

    // 10. Lọc bỏ các thẻ nguy hiểm (XSS security)
    str = str.replace(/<\s*(?:script|style|iframe|object|embed|applet)[\s\S]*?<\/\s*(?:script|style|iframe|object|embed|applet)\s*>/gi, '')
             .replace(/<\s*(?:script|style|iframe|object|embed|applet)[^>]*\/?>/gi, '')
             .replace(/\son[a-zA-Z]+\s*=\s*(?:'[^']*'|"[^"]*"|[^\s>]+)/gi, '')
             .replace(/(\b(?:href|src)\s*=\s*['"]?)\s*javascript:[^'"]*/gi, '$1#');

    return str;
}

// Cập nhật tên học sinh lên thanh tiêu đề bài thi (tự động chạy chữ nếu tên quá dài)
function updateStudentNameDisplay(name) {
    const el = document.getElementById('studentNameDisplay');
    if (!el) return;
    const finalName = (name && typeof name === 'string' && name.trim()) ? name.trim() : (quizProgress.studentName || 'Thí sinh');
    
    // Nếu tên dài hơn 12 ký tự -> Chạy chữ mượt mà liên tục (Seamless Loop Ticker)
    if (finalName.length > 12) {
        el.innerHTML = `
            <span class="meta-item-inner" style="display:inline-flex; align-items:center; gap:4px; min-width:0;">
                <i class="ri-user-line" style="flex-shrink:0;"></i>
                <span class="student-name-marquee-box" title="${escapeHtml(finalName)}">
                    <span class="student-name-marquee-track">
                        ${escapeHtml(finalName)} &nbsp;&nbsp;✦&nbsp;&nbsp; ${escapeHtml(finalName)} &nbsp;&nbsp;✦&nbsp;&nbsp;
                    </span>
                </span>
            </span>
        `;
    } else {
        el.innerHTML = `<i class="ri-user-line"></i> <span>${escapeHtml(finalName)}</span>`;
    }
}

// Xóa và ẩn toàn bộ các thành phần hiển thị kết quả / review sau khi nộp bài
function resetSubmissionReviewUI() {
    // 1. Ẩn và làm trống bộ lọc câu hỏi sau nộp bài
    const filterContainer = document.getElementById('reviewFilterBarContainer');
    if (filterContainer) {
        filterContainer.style.display = 'none';
        filterContainer.innerHTML = '';
    }
    // 2. Ẩn tabs chuyển đổi kết quả sau nộp bài
    const tabNav = document.getElementById('resultNavTabs');
    if (tabNav) {
        tabNav.style.display = 'none';
    }
    // 3. Ẩn và làm trống bảng điểm kết quả
    const scoreBoard = document.getElementById('score-board');
    if (scoreBoard) {
        scoreBoard.style.display = 'none';
        scoreBoard.innerHTML = '';
    }
    // 4. Ẩn bảng xếp hạng
    const lb = document.getElementById('leaderboard');
    if (lb) {
        lb.style.display = 'none';
    }
    // 5. Gỡ bỏ trạng thái quiz-completed trên body
    document.body.classList.remove('quiz-completed');
    
    // 6. Đảm bảo layout bài thi hiển thị bình thường
    const examLayout = document.getElementById('azotaExamLayout');
    if (examLayout) {
        examLayout.style.display = '';
    }
    const quizContainer = document.getElementById('quiz-container');
    if (quizContainer) {
        quizContainer.style.display = '';
    }

    // 7. Hiển thị lại nút nộp bài nếu đang ở chế độ exam
    const stickySubmit = document.getElementById('stickySubmitBtn');
    if (stickySubmit) {
        stickySubmit.style.display = (currentMode === 'exam') ? 'inline-flex' : 'none';
    }
    const mainSubmit = document.getElementById('submitBtn');
    if (mainSubmit) {
        mainSubmit.style.display = 'none';
    }

    // 8. Phục hồi thanh điều hướng và nút "Câu tiếp" trên mobile (chỉ hiển thị khi màn hình <= 960px)
    const mobileBar = document.getElementById('azotaMobileExamBar');
    if (mobileBar) {
        if (currentMode !== 'edit' && window.innerWidth <= 960) {
            mobileBar.style.display = 'flex';
        } else {
            mobileBar.style.display = 'none';
        }
    }
    const mobileNextBtn = document.getElementById('mobileNextBtn');
    if (mobileNextBtn) {
        mobileNextBtn.style.display = 'inline-flex';
        mobileNextBtn.innerHTML = 'Câu tiếp <i class="ri-arrow-right-line"></i>';
    }
    toggleMobileNavSheet(false);
}

function initGoogleAuth() {
    console.log("Firebase Authentication initialized.");
}

let currentPendingUserId = null;
let selectedUserRole = 'student';

function selectRoleTab(role) {
    selectedUserRole = role;
    const studentCard = document.getElementById('chooseStudentCard');
    const teacherCard = document.getElementById('chooseTeacherCard');
    const notice = document.getElementById('teacherApprovalNotice');
    const btn = document.getElementById('btnSubmitRoleChoice');
    const btnText = document.getElementById('btnSubmitRoleText');
    const classLabel = document.getElementById('roleClassLabel');
    
    if (role === 'teacher') {
        if (studentCard) {
            studentCard.classList.remove('selected');
            const mark = studentCard.querySelector('.role-check-icon');
            if (mark) mark.className = 'ri-checkbox-blank-circle-line role-check-icon';
        }
        if (teacherCard) {
            teacherCard.classList.add('selected');
            const mark = teacherCard.querySelector('.role-check-icon');
            if (mark) mark.className = 'ri-checkbox-circle-fill role-check-icon';
        }
        if (notice) notice.style.display = 'block';
        if (btn) btn.style.backgroundColor = '#4f46e5';
        if (btnText) btnText.innerHTML = '🛡️ Gửi đăng ký Giáo viên (Chờ duyệt)';
        if (classLabel) classLabel.innerHTML = 'Bộ môn / Trường công tác <span style="font-weight: 400; color: #9ca3af; font-size: 12px;">(Không bắt buộc)</span>';
    } else {
        if (teacherCard) {
            teacherCard.classList.remove('selected');
            const mark = teacherCard.querySelector('.role-check-icon');
            if (mark) mark.className = 'ri-checkbox-blank-circle-line role-check-icon';
        }
        if (studentCard) {
            studentCard.classList.add('selected');
            const mark = studentCard.querySelector('.role-check-icon');
            if (mark) mark.className = 'ri-checkbox-circle-fill role-check-icon';
        }
        if (notice) notice.style.display = 'none';
        if (btn) btn.style.backgroundColor = '#2563eb';
        if (btnText) btnText.innerHTML = '🚀 Hoàn tất & Vào học ngay';
        if (classLabel) classLabel.innerHTML = 'Lớp học / Đơn vị <span style="font-weight: 400; color: #9ca3af; font-size: 12px;">(Không bắt buộc)</span>';
    }
}
window.selectRoleTab = selectRoleTab;

function showRoleSelection(userId, fullName, email, avatar, className, phone, school) {
    currentPendingUserId = userId;

    const authBox = document.getElementById('authContainer');
    const mainApp = document.getElementById('mainAppContainer');
    const adminBox = document.getElementById('adminContainer');
    const azotaNav = document.getElementById('azotaNavbar');
    const pubHeader = document.getElementById('publicHeader');
    const landingHero = document.getElementById('landingHero');
    const landingStats = document.getElementById('landingStats');
    const landingExtra = document.getElementById('publicLandingExtras');

    if (pubHeader) pubHeader.style.display = 'none';
    if (landingHero) landingHero.style.display = 'none';
    if (landingStats) landingStats.style.display = 'none';
    if (landingExtra) landingExtra.style.display = 'none';
    if (mainApp) mainApp.style.display = 'none';
    if (adminBox) adminBox.style.display = 'none';
    if (azotaNav) azotaNav.style.display = 'none';

    if (authBox) {
        authBox.classList.remove('hidden');
        authBox.classList.add('page-mode');
        authBox.style.removeProperty('display');
        authBox.style.display = 'block';
    }

    const dualGrid = document.getElementById('authDualGrid');
    const mobileTabs = document.getElementById('authMobileTabs');
    const pageIntro = document.querySelector('.auth-page-intro');
    if (dualGrid) dualGrid.style.setProperty('display', 'none', 'important');
    if (mobileTabs) mobileTabs.style.setProperty('display', 'none', 'important');
    if (pageIntro) pageIntro.style.setProperty('display', 'none', 'important');

    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const roleCard = document.getElementById('roleSelectionCard');
    const pendingCard = document.getElementById('pendingApprovalCard');
    
    if (loginForm) loginForm.style.setProperty('display', 'none', 'important');
    if (registerForm) registerForm.style.setProperty('display', 'none', 'important');
    if (pendingCard) pendingCard.style.setProperty('display', 'none', 'important');
    
    if (roleCard) {
        roleCard.style.setProperty('display', 'flex', 'important');
        roleCard.classList.remove('hidden');
    }
    
    const nameInput = document.getElementById('roleFullNameInput');
    const classInput = document.getElementById('roleClassNameInput');
    const phoneInput = document.getElementById('rolePhoneInput');
    const schoolInput = document.getElementById('roleSchoolInput');
    const emailElem = document.getElementById('roleUserEmail');

    if (nameInput) nameInput.value = fullName || '';
    if (classInput) classInput.value = className || '';
    if (phoneInput) phoneInput.value = phone || '';
    if (schoolInput) schoolInput.value = school || '';
    if (emailElem) emailElem.innerText = email || '';
    
    const initials = (fullName || email || 'U').charAt(0).toUpperCase();
    const initElem = document.getElementById('roleUserInitials');
    const imgElem = document.getElementById('roleUserImg');
    if (avatar && imgElem) {
        imgElem.src = avatar;
        imgElem.style.display = 'block';
        if (initElem) initElem.style.display = 'none';
    } else {
        if (initElem) {
            initElem.innerText = initials;
            initElem.style.display = 'inline';
        }
        if (imgElem) imgElem.style.display = 'none';
    }

    // Mặc định chọn Học sinh
    selectRoleTab('student');
}
window.showRoleSelection = showRoleSelection;

function showPendingApproval(userId, fullName, email, className, school, phone) {
    if (userId) currentPendingUserId = userId;

    const authBox = document.getElementById('authContainer');
    const mainApp = document.getElementById('mainAppContainer');
    const adminBox = document.getElementById('adminContainer');
    const azotaNav = document.getElementById('azotaNavbar');
    const pubHeader = document.getElementById('publicHeader');
    const landingHero = document.getElementById('landingHero');
    const landingStats = document.getElementById('landingStats');
    const landingExtra = document.getElementById('publicLandingExtras');

    if (pubHeader) pubHeader.style.display = 'none';
    if (landingHero) landingHero.style.display = 'none';
    if (landingStats) landingStats.style.display = 'none';
    if (landingExtra) landingExtra.style.display = 'none';
    if (mainApp) mainApp.style.display = 'none';
    if (adminBox) adminBox.style.display = 'none';
    if (azotaNav) azotaNav.style.display = 'none';

    if (authBox) {
        authBox.classList.remove('hidden');
        authBox.classList.add('page-mode');
        authBox.style.removeProperty('display');
        authBox.style.display = 'block';
    }

    const dualGrid = document.getElementById('authDualGrid');
    const mobileTabs = document.getElementById('authMobileTabs');
    const pageIntro = document.querySelector('.auth-page-intro');
    if (dualGrid) dualGrid.style.setProperty('display', 'none', 'important');
    if (mobileTabs) mobileTabs.style.setProperty('display', 'none', 'important');
    if (pageIntro) pageIntro.style.setProperty('display', 'none', 'important');

    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const roleCard = document.getElementById('roleSelectionCard');
    const pendingCard = document.getElementById('pendingApprovalCard');
    
    if (loginForm) loginForm.style.setProperty('display', 'none', 'important');
    if (registerForm) registerForm.style.setProperty('display', 'none', 'important');
    if (roleCard) roleCard.style.setProperty('display', 'none', 'important');
    
    if (pendingCard) {
        pendingCard.style.setProperty('display', 'flex', 'important');
        pendingCard.classList.remove('hidden');
    }
    
    const nameElem = document.getElementById('pendingTeacherName');
    const emailElem = document.getElementById('pendingTeacherEmail');
    const infoElem = document.getElementById('pendingTeacherInfo');

    if (nameElem) nameElem.innerText = fullName || 'Thầy/Cô';
    if (emailElem) emailElem.innerText = email || '';

    if (infoElem) {
        let details = [];
        if (className) details.push(`Lớp/Môn: <b>${escapeHtml(className)}</b>`);
        if (school) details.push(`Trường: <b>${escapeHtml(school)}</b>`);
        if (phone) details.push(`SĐT: <b>${escapeHtml(phone)}</b>`);
        if (details.length > 0) {
            infoElem.innerHTML = details.join(' &nbsp;&bull;&nbsp; ');
            infoElem.style.display = 'block';
        } else {
            infoElem.style.display = 'none';
        }
    }
}
window.showPendingApproval = showPendingApproval;

function hideRoleScreens() {
    const roleCard = document.getElementById('roleSelectionCard');
    const pendingCard = document.getElementById('pendingApprovalCard');
    if (roleCard) roleCard.style.setProperty('display', 'none', 'important');
    if (pendingCard) pendingCard.style.setProperty('display', 'none', 'important');

    const dualGrid = document.getElementById('authDualGrid');
    const mobileTabs = document.getElementById('authMobileTabs');
    const pageIntro = document.querySelector('.auth-page-intro');
    if (dualGrid) dualGrid.style.removeProperty('display');
    if (pageIntro) pageIntro.style.removeProperty('display');
    if (mobileTabs && window.innerWidth < 992) {
        mobileTabs.style.setProperty('display', 'flex', 'important');
    }
}
window.hideRoleScreens = hideRoleScreens;

async function submitUserProfileAndRole() {
    if (!currentPendingUserId) {
        alert("Lỗi phiên chọn vai trò. Vui lòng thử đăng nhập lại với Google.");
        cancelRoleSelection();
        return;
    }

    const fullName = (document.getElementById('roleFullNameInput')?.value || '').trim();
    const className = (document.getElementById('roleClassNameInput')?.value || '').trim();
    const phone = (document.getElementById('rolePhoneInput')?.value || '').trim();
    const school = (document.getElementById('roleSchoolInput')?.value || '').trim();

    if (!fullName) {
        alert("Vui lòng nhập Họ và Tên của bạn.");
        document.getElementById('roleFullNameInput')?.focus();
        return;
    }

    const btn = document.getElementById('btnSubmitRoleChoice');
    const oldBtnHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="ri-loader-4-line ri-spin"></i> Đang lưu thông tin...`;
    }
    
    showGlobalLoader({
        title: "Đang lưu hồ sơ tài khoản...",
        subtitle: "Đang đồng bộ vai trò và thông tin cá nhân lên hệ thống..."
    });

    try {
        const res = await fetch(`${API_BASE_URL}/api/auth/select_role`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: currentPendingUserId,
                role: selectedUserRole,
                full_name: fullName,
                class_name: className,
                phone: phone,
                school: school
            })
        });
        const data = await res.json();
        hideGlobalLoader();
        if (res.ok) {
            if (data.status === 'success') {
                localStorage.setItem('auth_token', data.token);
                localStorage.setItem('auth_role', data.role);
                localStorage.setItem('auth_name', data.full_name);
                authToken = data.token;
                authRole = data.role;
                authName = data.full_name;
                closeAuthPage(true);
                closeExamLoginModal();
                hideRoleScreens();
                checkAuthState();
                alert(`🎉 Chúc mừng ${data.full_name}! Bạn đã đăng ký thành công với vai trò Học sinh.`);
            } else if (data.status === 'pending_approval') {
                showPendingApproval(currentPendingUserId, data.full_name, data.email, data.class_name, data.school, data.phone);
                alert("⏳ Đã gửi thông tin đăng ký Giáo viên! Tài khoản của bạn đang chờ Quản trị viên (Admin) xét duyệt.");
            }
        } else {
            alert("Lỗi: " + (data.detail || "Không thể lưu thông tin tài khoản"));
        }
    } catch(err) {
        hideGlobalLoader();
        console.error(err);
        alert("Lỗi kết nối khi lưu thông tin");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = oldBtnHtml;
        }
    }
}
window.submitUserProfileAndRole = submitUserProfileAndRole;

async function submitRoleChoice(role) {
    selectRoleTab(role);
    submitUserProfileAndRole();
}
window.submitRoleChoice = submitRoleChoice;

async function checkCurrentApprovalStatus() {
    if (!currentPendingUserId) {
        alert("Không tìm thấy mã tài khoản. Vui lòng thử đăng nhập lại.");
        cancelRoleSelection();
        return;
    }
    
    const btn = document.getElementById('btnCheckApproval');
    if (btn) {
        btn.innerHTML = `<i class="ri-loader-4-line ri-spin"></i> Đang kiểm tra...`;
        btn.disabled = true;
    }
    
    showGlobalLoader({
        title: "Đang kiểm tra phê duyệt...",
        subtitle: "Đang xác thực trạng thái tài khoản từ máy chủ..."
    });

    try {
        const res = await fetch(`${API_BASE_URL}/api/auth/check_approval_status?user_id=${currentPendingUserId}`);
        const data = await res.json();
        hideGlobalLoader();
        if (res.ok) {
            if (data.status === 'approved') {
                localStorage.setItem('auth_token', data.token);
                localStorage.setItem('auth_role', data.role);
                localStorage.setItem('auth_name', data.full_name);
                authToken = data.token;
                authRole = data.role;
                authName = data.full_name;
                hideRoleScreens();
                checkAuthState();
                alert(`🎉 Chúc mừng! Tài khoản Giáo viên của bạn đã được Quản trị viên phê duyệt thành công.`);
            } else {
                alert("⏳ Tài khoản của bạn vẫn đang chờ Quản trị viên xét duyệt. Vui lòng liên hệ Admin (kiet0905478167@gmail.com) nếu cần hỗ trợ gấp.");
            }
        } else {
            alert("Lỗi kiểm tra trạng thái: " + (data.detail || "Không rõ nguyên nhân"));
        }
    } catch(err) {
        hideGlobalLoader();
        alert("Lỗi kết nối máy chủ khi kiểm tra trạng thái");
    } finally {
        if (btn) {
            btn.innerHTML = `<i class="ri-refresh-line"></i> Kiểm tra trạng thái duyệt`;
            btn.disabled = false;
        }
    }
}
window.checkCurrentApprovalStatus = checkCurrentApprovalStatus;

function cancelRoleSelection() {
    currentPendingUserId = null;
    hideRoleScreens();
    const authBox = document.getElementById('authContainer');
    if (authBox && authBox.classList.contains('page-mode')) {
        if (window.innerWidth >= 992) {
            const loginForm = document.getElementById('loginForm');
            const registerForm = document.getElementById('registerForm');
            if (loginForm) loginForm.style.setProperty('display', 'flex', 'important');
            if (registerForm) registerForm.style.setProperty('display', 'flex', 'important');
        } else {
            switchMobileAuthTab('login');
        }
    } else {
        const loginForm = document.getElementById('loginForm');
        if (loginForm) loginForm.style.setProperty('display', 'flex', 'important');
    }
    if (window.firebaseAuth && typeof window.firebaseAuth.signOut === 'function') {
        window.firebaseAuth.signOut().catch(() => {});
    }
}
window.cancelRoleSelection = cancelRoleSelection;

async function triggerGoogleSignIn() {
    try {
        if (!window.signInWithPopup || !window.firebaseAuth || !window.googleProvider) {
            alert("Đang nạp thư viện Firebase Google Sign-In... Vui lòng thử lại sau giây lát.");
            return;
        }

        showGlobalLoader({
            title: "Đang kết nối Google & Firebase...",
            subtitle: "Vui lòng chọn tài khoản trên cửa sổ đăng nhập Google..."
        });

        // Mở popup đăng nhập bằng tài khoản Google chính chủ Firebase
        const result = await window.signInWithPopup(window.firebaseAuth, window.googleProvider);
        const user = result.user;
        const idToken = await user.getIdToken();

        updateGlobalLoader({
            title: "Đang xác thực tài khoản...",
            subtitle: "Đang đồng bộ hồ sơ người dùng với máy chủ..."
        });

        // Gửi token về Backend để đồng bộ tài khoản và tạo JWT Token
        const res = await fetch(`${API_BASE_URL}/api/auth/google`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ credential: idToken })
        });

        const data = await res.json();
        hideGlobalLoader();
        if (res.ok) {
            if (data.status === 'success') {
                localStorage.setItem('auth_token', data.token);
                localStorage.setItem('auth_role', data.role);
                localStorage.setItem('auth_name', data.full_name);
                authToken = data.token;
                authRole = data.role;
                authName = data.full_name;
                closeAuthPage(true);
                closeExamLoginModal();
                hideRoleScreens();
                checkAuthState();

                const roleDesc = data.role === 'admin' ? '🛡️ Quản trị viên (Admin)' : (data.role === 'teacher' ? '👨‍🏫 Giáo viên' : '👨‍🎓 Học sinh');
                alert(`🎉 Đăng nhập thành công với Google!\nXin chào: ${data.full_name}\nVai trò: ${roleDesc}`);
            } else if (data.status === 'needs_role_selection') {
                // Hiển thị giao diện nhập thông tin & chọn vai trò
                showRoleSelection(data.user_id, data.full_name, data.email, data.avatar, data.class_name, data.phone, data.school);
            } else if (data.status === 'pending_approval') {
                // Hiển thị màn hình chờ Quản trị viên duyệt
                showPendingApproval(data.user_id, data.full_name, data.email, data.class_name, data.school, data.phone);
            } else {
                alert("Lỗi: " + (data.message || data.detail || "Không thể xác minh tài khoản."));
            }
        } else {
            alert("Lỗi máy chủ xác thực: " + (data.detail || "Không thể xác minh tài khoản."));
        }
    } catch (err) {
        hideGlobalLoader();
        console.error("Firebase Google Sign-In Error:", err);
        if (err.code === 'auth/popup-closed-by-user') {
            return; // Người dùng chủ động đóng popup
        }
        if (err.code === 'auth/unauthorized-domain') {
            alert("⚠️ Tên miền hiện tại (" + window.location.hostname + ") chưa được cấp phép trong Firebase Auth.\n\n👉 Cách cấp phép:\n1. Mở Firebase Console > Authentication > Settings > Authorized domains\n2. Nhấn 'Add domain' và thêm: " + window.location.hostname);
            return;
        }
        alert("Lỗi đăng nhập Google: " + (err.message || err));
    }
}
window.triggerGoogleSignIn = triggerGoogleSignIn;

function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';
    const icon = btn ? btn.querySelector('i') : null;
    if (icon) {
        icon.className = isPassword ? 'ri-eye-off-line' : 'ri-eye-line';
    }
}
window.togglePasswordVisibility = togglePasswordVisibility;

function setRegisterRole(role) {
    const sel = document.getElementById('regRole');
    if (sel) sel.value = role;
    
    const pillStudent = document.getElementById('rolePillStudent');
    const pillTeacher = document.getElementById('rolePillTeacher');
    if (pillStudent && pillTeacher) {
        if (role === 'teacher') {
            pillStudent.classList.remove('selected');
            pillTeacher.classList.add('selected');
            const iconS = pillStudent.querySelector('.role-pill-check');
            const iconT = pillTeacher.querySelector('.role-pill-check');
            if (iconS) iconS.className = 'ri-checkbox-blank-circle-line role-pill-check';
            if (iconT) iconT.className = 'ri-checkbox-circle-fill role-pill-check';
        } else {
            pillStudent.classList.add('selected');
            pillTeacher.classList.remove('selected');
            const iconS = pillStudent.querySelector('.role-pill-check');
            const iconT = pillTeacher.querySelector('.role-pill-check');
            if (iconS) iconS.className = 'ri-checkbox-circle-fill role-pill-check';
            if (iconT) iconT.className = 'ri-checkbox-blank-circle-line role-pill-check';
        }
    }
}
window.setRegisterRole = setRegisterRole;

function switchMobileAuthTab(tab) {
    const tabLogin = document.getElementById('tabMobileLogin');
    const tabRegister = document.getElementById('tabMobileRegister');
    const loginCard = document.querySelector('.auth-login-card');
    const registerCard = document.querySelector('.auth-register-card');
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');

    if (tab === 'register') {
        if (tabLogin) tabLogin.classList.remove('active');
        if (tabRegister) tabRegister.classList.add('active');
        if (loginCard) loginCard.style.setProperty('display', 'none', 'important');
        if (registerCard) registerCard.style.setProperty('display', 'block', 'important');
        if (loginForm) loginForm.style.setProperty('display', 'none', 'important');
        if (registerForm) registerForm.style.setProperty('display', 'flex', 'important');
        
        const authBox = document.getElementById('authContainer');
        if (authBox && authBox.classList.contains('page-mode')) {
            history.replaceState({ page: 'auth', tab: 'register' }, '', '/register');
        }
    } else {
        if (tabLogin) tabLogin.classList.add('active');
        if (tabRegister) tabRegister.classList.remove('active');
        if (loginCard) loginCard.style.setProperty('display', 'block', 'important');
        if (registerCard) registerCard.style.setProperty('display', 'none', 'important');
        if (loginForm) loginForm.style.setProperty('display', 'flex', 'important');
        if (registerForm) registerForm.style.setProperty('display', 'none', 'important');
        
        const authBox = document.getElementById('authContainer');
        if (authBox && authBox.classList.contains('page-mode')) {
            history.replaceState({ page: 'auth', tab: 'login' }, '', '/login');
        }
    }
}
window.switchMobileAuthTab = switchMobileAuthTab;

function openAuthPage(initialTab = 'login', pushHistory = true) {
    const authBox = document.getElementById('authContainer');
    if (!authBox) return;

    // Nếu đang trong phòng thi kiểm tra thì ưu tiên modal để tránh mất phiên thi
    const urlParams = new URLSearchParams(window.location.search);
    const quizId = urlParams.get('quiz_id') || urlParams.get('id');
    if (quizId) {
        openExamLoginModal();
        return;
    }

    // Ẩn giao diện Landing Page
    const pubHeader = document.getElementById('publicHeader');
    const landingHero = document.getElementById('landingHero');
    const landingStats = document.getElementById('landingStats');
    const landingExtra = document.getElementById('publicLandingExtras');
    const mainApp = document.getElementById('mainAppContainer');
    const adminBox = document.getElementById('adminContainer');

    if (pubHeader) pubHeader.style.display = 'none';
    if (landingHero) landingHero.style.display = 'none';
    if (landingStats) landingStats.style.display = 'none';
    if (landingExtra) landingExtra.style.display = 'none';
    if (mainApp) mainApp.style.display = 'none';
    if (adminBox) adminBox.style.display = 'none';

    // Kích hoạt authContainer ở chế độ Trang Riêng
    authBox.classList.remove('modal-mode');
    authBox.classList.add('page-mode');
    authBox.classList.remove('hidden');
    authBox.style.removeProperty('display');
    authBox.style.display = 'block';

    hideRoleScreens();

    if (window.innerWidth < 992) {
        switchMobileAuthTab(initialTab);
    } else {
        // Desktop: Hiển thị 2 form song song (Login & Register)
        const loginCard = document.querySelector('.auth-login-card');
        const registerCard = document.querySelector('.auth-register-card');
        const loginForm = document.getElementById('loginForm');
        const registerForm = document.getElementById('registerForm');
        const dualGrid = document.getElementById('authDualGrid');
        if (dualGrid) dualGrid.style.removeProperty('display');
        if (loginCard) loginCard.style.removeProperty('display');
        if (registerCard) registerCard.style.removeProperty('display');
        if (loginForm) loginForm.style.setProperty('display', 'flex', 'important');
        if (registerForm) registerForm.style.setProperty('display', 'flex', 'important');
    }

    setTimeout(() => {
        if (initialTab === 'register') {
            const regInput = document.getElementById('regFullName');
            if (regInput && window.innerWidth >= 992) regInput.focus();
        } else {
            const loginInput = document.getElementById('email');
            if (loginInput) loginInput.focus();
        }
    }, 120);

    if (pushHistory) {
        const targetPath = initialTab === 'register' ? '/register' : '/dang-nhap';
        if (window.location.pathname !== targetPath) {
            history.pushState({ page: 'auth', tab: initialTab }, '', targetPath);
        }
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
}
window.openAuthPage = openAuthPage;

function closeAuthPage(updateHistory = true) {
    const authBox = document.getElementById('authContainer');
    if (authBox) {
        authBox.classList.remove('page-mode');
        authBox.classList.remove('modal-mode');
        authBox.classList.add('hidden');
        authBox.style.setProperty('display', 'none', 'important');
    }

    hideRoleScreens();

    const pubHeader = document.getElementById('publicHeader');
    const landingHero = document.getElementById('landingHero');
    const landingStats = document.getElementById('landingStats');
    const landingExtra = document.getElementById('publicLandingExtras');

    if (pubHeader) pubHeader.style.display = 'flex';
    if (landingHero) landingHero.style.display = 'block';
    if (landingStats) landingStats.style.display = 'block';
    if (landingExtra) landingExtra.style.display = 'block';

    if (updateHistory) {
        if (['/dang-nhap', '/login', '/register', '/auth'].includes(window.location.pathname)) {
            history.pushState({ page: 'home' }, '', '/');
        }
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
}
window.closeAuthPage = closeAuthPage;

function openExamLoginModal() {
    const authBox = document.getElementById('authContainer');
    if (!authBox) return;
    authBox.classList.remove('page-mode');
    authBox.classList.add('modal-mode');
    authBox.classList.remove('hidden');
    authBox.style.removeProperty('display');
    authBox.style.display = 'flex';
    
    // Đảm bảo mở form đăng nhập nếu không đang ở quy trình khác
    const roleCard = document.getElementById('roleSelectionCard');
    const pendingCard = document.getElementById('pendingApprovalCard');
    
    if (roleCard && roleCard.style.display !== 'none' && typeof currentPendingUserId !== 'undefined' && currentPendingUserId) {
        // Giữ nguyên roleCard nếu đang chọn vai trò
    } else if (pendingCard && pendingCard.style.display !== 'none') {
        // Giữ nguyên pendingCard nếu đang chờ duyệt
    } else {
        switchMobileAuthTab('login');
    }
}
window.openExamLoginModal = openExamLoginModal;

function closeExamLoginModal() {
    const authBox = document.getElementById('authContainer');
    if (!authBox) return;
    authBox.classList.remove('modal-mode');
    if (!authBox.classList.contains('page-mode')) {
        authBox.classList.add('hidden');
        authBox.style.setProperty('display', 'none', 'important');
    }
}
window.closeExamLoginModal = closeExamLoginModal;

// Đóng modal khi bấm ra ngoài vùng tối hoặc phím ESC
document.addEventListener('click', function(e) {
    const authBox = document.getElementById('authContainer');
    if (authBox && authBox.classList.contains('modal-mode') && e.target === authBox) {
        closeExamLoginModal();
    }
});
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        const authBox = document.getElementById('authContainer');
        if (authBox && authBox.classList.contains('modal-mode')) {
            closeExamLoginModal();
        }
    }
});

window.addEventListener('resize', function() {
    const authBox = document.getElementById('authContainer');
    if (!authBox || !authBox.classList.contains('page-mode')) return;
    
    const roleCard = document.getElementById('roleSelectionCard');
    const pendingCard = document.getElementById('pendingApprovalCard');
    if ((roleCard && roleCard.style.display !== 'none') || (pendingCard && pendingCard.style.display !== 'none')) {
        return;
    }

    const loginCard = document.querySelector('.auth-login-card');
    const registerCard = document.querySelector('.auth-register-card');
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');

    if (window.innerWidth >= 992) {
        if (loginCard) loginCard.style.removeProperty('display');
        if (registerCard) registerCard.style.removeProperty('display');
        if (loginForm) loginForm.style.setProperty('display', 'flex', 'important');
        if (registerForm) registerForm.style.setProperty('display', 'flex', 'important');
    } else {
        const isReg = document.getElementById('tabMobileRegister')?.classList.contains('active');
        switchMobileAuthTab(isReg ? 'register' : 'login');
    }
});

window.addEventListener('popstate', function(e) {
    const path = window.location.pathname;
    const hash = window.location.hash;
    const legalRoutes = ['/privacy', '/terms', '/about', '/contact'];
    if (['/dang-nhap', '/login', '/register', '/auth'].includes(path) || ['#auth', '#login', '#register'].includes(hash)) {
        openAuthPage(path === '/register' || hash === '#register' ? 'register' : 'login', false);
    } else if (legalRoutes.includes(path)) {
        openLegalModal(path.substring(1), false);
    } else if (path === '/' || path === '/index.html') {
        const authBox = document.getElementById('authContainer');
        if (authBox && authBox.classList.contains('page-mode')) {
            closeAuthPage(false);
        }
        closeLegalModal(false);
        checkAuthState();
    } else {
        checkAuthState();
    }
});

function renderGuestNavbarBadge() {
    const userBadge = document.getElementById('azotaUserBadge');
    if (!userBadge) return;
    userBadge.innerHTML = `
        <div style="display:flex; align-items:center; gap:10px;">
            <span style="font-size: 0.88rem; color: #b45309; background: #fef3c7; border: 1px solid #fde68a; padding: 4px 10px; border-radius: 20px; font-weight: 600; display: inline-flex; align-items: center; gap: 5px;">
                <i class="ri-user-smile-line"></i> Thí sinh tự do
            </span>
            <button type="button" class="btn-primary" id="btnExamTopLogin" onclick="openExamLoginModal()" style="padding: 7px 16px; font-size: 0.88rem; font-weight: 700; border-radius: 8px; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 8px rgba(25, 118, 210, 0.25); cursor: pointer;" title="Đăng nhập tài khoản để lưu bài thi vĩnh viễn">
                <i class="ri-login-box-line"></i> Đăng nhập
            </button>
        </div>`;
}

function checkAuthState() {
    const urlParams = new URLSearchParams(window.location.search);
    const quizId = getCurrentQuizId();
    const path = window.location.pathname;
    const hash = window.location.hash;
    const authBox = document.getElementById('authContainer');
    const azotaNav = document.getElementById('azotaNavbar');
    const mainApp = document.getElementById('mainAppContainer');
    const adminBox = document.getElementById('adminContainer');

    // Đảm bảo không bị ám trang chủ trên các route chức năng
    if (path !== '/' || urlParams.has('id') || urlParams.has('quiz_id') || authToken) {
        document.documentElement.classList.add('hntn-not-home-route');
    }

    // 0. ROUTE PHÒNG VỆ: STUDIO BIÊN TẬP (/editor hoặc /editor/{id})
    if (path === '/editor' || path.startsWith('/editor/')) {
        const pathMatch = path.match(/^\/editor\/([^\/?#]+)/);
        const qId = urlParams.get('id') || urlParams.get('quiz_id') || (pathMatch ? pathMatch[1] : null);
        if (qId) {
            window.location.replace('/editor?id=' + encodeURIComponent(qId));
        } else {
            window.location.replace('/editor');
        }
        return;
    }

    // 1. ROUTE: BẢNG XẾP HẠNG (/xep-hang/{ma_de})
    if (path.startsWith('/xep-hang/')) {
        const pubHeader = document.getElementById('publicHeader');
        if (pubHeader) pubHeader.style.display = 'none';
        const landingHero = document.getElementById('landingHero');
        if (landingHero) landingHero.style.display = 'none';
        const landingStats = document.getElementById('landingStats');
        if (landingStats) landingStats.style.display = 'none';
        const landingExtra = document.getElementById('publicLandingExtras');
        if (landingExtra) landingExtra.style.display = 'none';
        if (authBox) {
            authBox.classList.remove('page-mode');
            authBox.classList.remove('modal-mode');
            authBox.classList.add('hidden');
            authBox.style.setProperty('display', 'none', 'important');
        }
        if (adminBox) adminBox.style.display = 'none';
        if (mainApp) mainApp.style.display = 'block';
        hideRoleScreens();
        showLeaderboardOnly();
        hidePageInitialLoader();
        return;
    }

    // 2. ROUTE: KẾT QUẢ & ĐÁP ÁN CHI TIẾT (/ket-qua/{id})
    if (path.startsWith('/ket-qua/')) {
        const subId = path.split('/ket-qua/')[1].split('/')[0];
        hidePageInitialLoader();
        if (subId) {
            openStudentHistoryReview(subId);
        }
    }

    // 3. ROUTE: PHÒNG THI / LÀM BÀI (/thi/{ma_de} hoặc /quiz/{id} hoặc ?id=...)
    const isTeacherRoute = path.startsWith('/giao-vien');
    const isExamPath = path.startsWith('/thi/') || path.startsWith('/quiz/') || (quizId && path === '/' && urlParams.has('id')) || (quizId && !isTeacherRoute && path !== '/lich-su' && path !== '/admin' && path !== '/de-thi' && path !== '/dang-nhap');
    if (isExamPath && quizId) {
        const pubHeader = document.getElementById('publicHeader');
        if (pubHeader) pubHeader.style.display = 'none';
        const landingHero = document.getElementById('landingHero');
        if (landingHero) landingHero.style.display = 'none';
        const landingStats = document.getElementById('landingStats');
        if (landingStats) landingStats.style.display = 'none';
        const landingExtra = document.getElementById('publicLandingExtras');
        if (landingExtra) landingExtra.style.display = 'none';
        if (authBox) {
            authBox.classList.remove('page-mode');
            authBox.classList.remove('modal-mode');
            authBox.classList.add('hidden');
            authBox.style.setProperty('display', 'none', 'important');
        }
        if (adminBox) adminBox.style.display = 'none';
        if (mainApp) mainApp.style.display = 'block';
        if (azotaNav) azotaNav.style.display = 'block';

        // Ẩn thanh tab chuyển đổi khi đang thi
        const navLinks = document.getElementById('azotaNavLinks');
        if (navLinks) navLinks.style.display = 'none';

        const guestNotice = document.getElementById('guestNoticeStrip');
        const stickyGuestBtn = document.getElementById('stickyGuestLoginBtn');

        if (authToken && authName) {
            updateNavbarUser(authName, authRole);
            const sNameInput = document.getElementById('studentNameInput');
            if (sNameInput) sNameInput.value = authName;
            if (guestNotice) guestNotice.style.display = 'none';
            if (stickyGuestBtn) stickyGuestBtn.style.display = 'none';
            studentName = authName;
            updateStudentNameDisplay(authName);
        } else {
            // Khách tự do vào làm bài -> Nút đăng nhập trên cùng bên phải
            renderGuestNavbarBadge();
            if (guestNotice) guestNotice.style.display = 'block';
            if (stickyGuestBtn) stickyGuestBtn.style.display = 'inline-flex';
        }

        if (!currentData || currentData.length === 0) {
            initApp();
        }
        return;
    }

    if (authToken && (['/login', '/register', '/auth', '/dang-nhap'].includes(path))) {
        const targetPath = (authRole === 'admin') ? '/admin' : (authRole === 'teacher' ? '/giao-vien' : '/lich-su');
        history.replaceState(null, '', targetPath);
    }

    if (!authToken) {
        if (azotaNav) azotaNav.style.display = 'none';
        if (mainApp) mainApp.style.display = 'none';
        if (adminBox) adminBox.style.display = 'none';

        const isAuthRoute = (path === '/login' || path === '/register' || path === '/auth' || path === '/dang-nhap' || hash === '#auth' || hash === '#login' || hash === '#register');

        if (isAuthRoute) {
            hidePageInitialLoader();
            openAuthPage(path === '/register' || hash === '#register' ? 'register' : 'login', false);
            return;
        }

        if (path === '/giao-vien' || path.startsWith('/giao-vien/') || path === '/lich-su' || path === '/admin') {
            hidePageInitialLoader();
            if (typeof showToast === 'function') {
                showToast("Vui lòng đăng nhập để truy cập tính năng này.", "info");
            }
            openAuthPage('login', false);
            return;
        }

        const legalRoutes = ['/privacy', '/terms', '/about', '/contact'];
        const matchedLegal = legalRoutes.find(r => path === r || hash === '#' + r.substring(1));
        if (matchedLegal) {
            const tabName = matchedLegal.replace('/', '').replace('#', '');
            setTimeout(() => { openLegalModal(tabName, false); }, 50);
        }

        document.documentElement.classList.remove('hntn-not-home-route', 'hntn-is-quiz-route', 'hntn-is-auth-route', 'hntn-is-teacher-route', 'hntn-is-admin-route');
        const pubHeader = document.getElementById('publicHeader');
        if (pubHeader) pubHeader.style.display = 'flex';
        const landingHero = document.getElementById('landingHero');
        if (landingHero) landingHero.style.display = 'block';
        const landingStats = document.getElementById('landingStats');
        if (landingStats) landingStats.style.display = 'block';
        const landingExtra = document.getElementById('publicLandingExtras');
        if (landingExtra) landingExtra.style.display = 'block';
        if (authBox) {
            authBox.classList.remove('page-mode');
            authBox.classList.remove('modal-mode');
            authBox.classList.add('hidden');
            authBox.style.setProperty('display', 'none', 'important');
        }
        
        hideRoleScreens();
        hidePageInitialLoader();

        if (path === '/de-thi') {
            setTimeout(() => {
                const target = document.getElementById('landingHero') || document.getElementById('heroQuizCodeInput');
                if (target) target.scrollIntoView({ behavior: 'smooth' });
                if (typeof showToast === 'function') {
                    showToast("Khám phá kho đề thi: Nhập mã phòng thi hoặc chọn làm bài trải nghiệm!", "info");
                }
            }, 300);
        }
    } else if (authRole === 'admin') {
        const pubHeader = document.getElementById('publicHeader');
        if (pubHeader) pubHeader.style.display = 'none';
        const landingHero = document.getElementById('landingHero');
        if (landingHero) landingHero.style.display = 'none';
        const landingStats = document.getElementById('landingStats');
        if (landingStats) landingStats.style.display = 'none';
        const landingExtra = document.getElementById('publicLandingExtras');
        if (landingExtra) landingExtra.style.display = 'none';
        if (authBox) {
            authBox.classList.add('hidden');
            authBox.style.setProperty('display', 'none', 'important');
        }
        if (mainApp) mainApp.style.display = 'none';
        if (adminBox) adminBox.style.display = 'block';
        if (azotaNav) {
            azotaNav.style.display = 'block';
            updateNavbarUser(authName, 'admin');
            const navAdmin = document.getElementById('navTabAdmin');
            if (navAdmin) navAdmin.style.display = 'inline-flex';
        }
        loadAdminUsers();
        loadAdminSettings();
        hidePageInitialLoader();
    } else {
        const pubHeader = document.getElementById('publicHeader');
        if (pubHeader) pubHeader.style.display = 'none';
        const landingHero = document.getElementById('landingHero');
        if (landingHero) landingHero.style.display = 'none';
        const landingStats = document.getElementById('landingStats');
        if (landingStats) landingStats.style.display = 'none';
        const landingExtra = document.getElementById('publicLandingExtras');
        if (landingExtra) landingExtra.style.display = 'none';
        if (authBox) {
            authBox.classList.add('hidden');
            authBox.style.setProperty('display', 'none', 'important');
        }
        if (adminBox) adminBox.style.display = 'none';
        if (mainApp) mainApp.style.display = 'block';
        if (azotaNav) {
            azotaNav.style.display = 'block';
            updateNavbarUser(authName, authRole);
        }

        const studentInput = document.getElementById('studentNameInput');
        if (studentInput) studentInput.value = authName;

        if (authRole === 'student') {
            document.getElementById('creationHub').style.display = 'none';
            document.getElementById('teacherDashboard').style.display = 'none';
            document.getElementById('studentDashboard').style.display = 'block';
            const navCreate = document.getElementById('navTabCreate');
            if (navCreate) navCreate.style.display = 'none';
            const navStudio = document.getElementById('navTabStudio');
            if (navStudio) navStudio.style.display = 'none';
            const navDash = document.getElementById('navTabDashboard');
            if (navDash) navDash.innerHTML = '<i class="ri-dashboard-3-line"></i> Góc học tập & Lịch sử';
            loadStudentHistory();
        } else if (authRole === 'teacher') {
            document.getElementById('studentDashboard').style.display = 'none';
            document.getElementById('teacherDashboard').style.display = 'block';
            const navCreate = document.getElementById('navTabCreate');
            if (navCreate) navCreate.style.display = 'inline-flex';
            const navStudio = document.getElementById('navTabStudio');
            if (navStudio) navStudio.style.display = 'inline-flex';
            const navDash = document.getElementById('navTabDashboard');
            if (navDash) navDash.innerHTML = '<i class="ri-dashboard-3-line"></i> Đề thi của tôi';
            loadTeacherQuizzes();

            if (path.startsWith('/giao-vien/de/')) {
                const qId = path.split('/giao-vien/de/')[1].split('/')[0];
                if (qId) {
                    setTimeout(() => { openQuizStats(qId); }, 200);
                }
            }
        }
        hidePageInitialLoader();
        initApp();
    }
}

function updateNavbarUser(name, role) {
    const userBadge = document.getElementById('azotaUserBadge');
    if (userBadge && (!document.getElementById('navUserName') || !document.getElementById('navUserAvatar'))) {
        userBadge.innerHTML = `
            <div class="user-avatar" id="navUserAvatar">U</div>
            <div class="user-info">
                <span class="user-name" id="navUserName">Tài khoản</span>
                <span class="azota-role-pill" id="navUserRole">Học sinh</span>
            </div>
            <button class="btn-azota-sub" style="padding: 6px 12px; margin-left: 8px;" onclick="logout()" title="Đăng xuất khỏi hệ thống">
                <i class="ri-logout-box-r-line"></i> Đăng xuất
            </button>
        `;
    }
    const navName = document.getElementById('navUserName');
    const navAvatar = document.getElementById('navUserAvatar');
    const navRole = document.getElementById('navUserRole');
    if (navName) navName.innerText = name || 'Tài khoản';
    if (navAvatar) navAvatar.innerText = (name || 'U').charAt(0).toUpperCase();
    if (navRole) {
        if (role === 'admin') {
            navRole.innerText = 'Quản trị viên';
            navRole.style.background = '#fef2f2';
            navRole.style.color = '#dc2626';
        } else if (role === 'teacher') {
            navRole.innerText = 'Giáo viên';
            navRole.style.background = '#eff6ff';
            navRole.style.color = '#1d4ed8';
        } else {
            navRole.innerText = 'Học sinh';
            navRole.style.background = '#f0fdf4';
            navRole.style.color = '#15803d';
        }
    }
}

function showDashboardView() {
    document.getElementById('navTabDashboard')?.classList.add('active');
    document.getElementById('navTabCreate')?.classList.remove('active');
    if (authRole === 'student') {
        document.getElementById('studentDashboard').style.display = 'block';
        document.getElementById('creationHub').style.display = 'none';
        loadStudentHistory();
    } else {
        document.getElementById('teacherDashboard').style.display = 'block';
        document.getElementById('creationHub').style.display = 'none';
        loadTeacherQuizzes();
    }
    const examLayout = document.getElementById('azotaExamLayout');
    if (examLayout) examLayout.style.display = 'none';
    document.getElementById('adminContainer').style.display = 'none';
    document.getElementById('mainAppContainer').style.display = 'block';
}

function showCreateView() {
    document.getElementById('navTabCreate')?.classList.add('active');
    document.getElementById('navTabDashboard')?.classList.remove('active');
    document.getElementById('creationHub').style.display = 'grid';
    document.getElementById('teacherDashboard').style.display = 'none';
    document.getElementById('studentDashboard').style.display = 'none';
    const examLayout = document.getElementById('azotaExamLayout');
    if (examLayout) examLayout.style.display = 'none';
}

function showAdminView() {
    document.getElementById('mainAppContainer').style.display = 'none';
    document.getElementById('adminContainer').style.display = 'block';
}

function toggleAuth(type) {
    hideRoleScreens();
    if (window.innerWidth < 992) {
        switchMobileAuthTab(type);
    } else {
        if (type === 'register') {
            const regInput = document.getElementById('regFullName');
            if (regInput) regInput.focus();
        } else {
            const loginInput = document.getElementById('email');
            if (loginInput) loginInput.focus();
        }
    }
}
window.toggleAuth = toggleAuth;

async function handleLogin() {
    const uInput = document.getElementById('email') || document.getElementById('loginUsername');
    const pInput = document.getElementById('password') || document.getElementById('loginPassword');
    const u = uInput ? uInput.value.trim() : '';
    const p = pInput ? pInput.value.trim() : '';
    if(!u || !p) return alert("Vui lòng nhập đầy đủ email/tên đăng nhập và mật khẩu");
    
    showGlobalLoader({
        title: "Đang đăng nhập...",
        subtitle: "Đang xác thực thông tin tài khoản với máy chủ..."
    });

    try {
        const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username: u, password: p})
        });
        const data = await res.json();
        hideGlobalLoader();
        if(res.ok && data.status === 'success') {
            localStorage.setItem('auth_token', data.token);
            localStorage.setItem('auth_role', data.role);
            localStorage.setItem('auth_name', data.full_name);
            authToken = data.token; authRole = data.role; authName = data.full_name;
            closeAuthPage(true);
            closeExamLoginModal();
            hideRoleScreens();
            checkAuthState();
            showToast(`🎉 Đăng nhập thành công! Xin chào ${data.full_name}.`, 'success');
        } else {
            if ((res.status === 403 || data.status === 'pending_approval') && (data.detail || '').includes("chờ Quản trị viên")) {
                showPendingApproval(null, u, u);
            } else {
                alert("Lỗi: " + (data.detail || data.message || "Đăng nhập thất bại."));
            }
        }
    } catch(e) { 
        hideGlobalLoader();
        console.error(e);
        alert(`Lỗi kết nối máy chủ! Backend đang trỏ tới: ${API_BASE_URL}\nHãy đảm bảo bạn đã chạy lệnh: uvicorn main:app --reload`); 
    }
}

async function handleRegister() {
    const u = document.getElementById('regUsername').value.trim();
    const p = document.getElementById('regPassword').value.trim();
    const fn = document.getElementById('regFullName').value.trim();
    const r = document.getElementById('regRole').value;
    if(!u || !p || !fn) return alert("Vui lòng nhập đủ thông tin");
    
    showGlobalLoader({
        title: "Đang tạo tài khoản...",
        subtitle: "Hệ thống đang ghi nhận thông tin đăng ký..."
    });

    try {
        const res = await fetch(`${API_BASE_URL}/api/auth/register`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username: u, password: p, full_name: fn, role: r})
        });
        const data = await res.json();
        hideGlobalLoader();
        if(res.ok && data.status === 'success') {
            alert(data.message || "Đăng ký thành công!");
            if (r === 'teacher') {
                showPendingApproval(null, fn, u);
            } else {
                toggleAuth('login');
                const emailInput = document.getElementById('email');
                if (emailInput) {
                    emailInput.value = u;
                    const pwdInput = document.getElementById('password');
                    if (pwdInput) pwdInput.focus();
                }
            }
        } else { alert("Lỗi: " + (data.detail || "Đăng ký thất bại.")); }
    } catch(e) { 
        hideGlobalLoader();
        alert("Lỗi kết nối máy chủ"); 
    }
}

function logout() {
    const quizId = getCurrentQuizId();
    localStorage.clear();
    if (quizId) {
        window.location.reload();
    } else {
        window.location.href = window.location.pathname; // Tải lại trang xóa query param
    }
}

/* ========================================================
   GOOGLE SIGN-IN CLIENT LOGIC (ĐÃ CHUYỂN SANG FIREBASE AUTH)
   ======================================================== */




// Hàm trợ giúp trích xuất mã đề thi từ query param (?id=, ?quiz_id=) hoặc URL path (/quiz/..., /thi/...)
function getCurrentQuizId() {
    const urlParams = new URLSearchParams(window.location.search);
    let quizId = urlParams.get('quiz_id') || urlParams.get('id');
    if (!quizId) {
        const path = window.location.pathname.replace(/^\/|\/$/g, '');
        const segments = path.split('/');
        const prefix = (segments[0] || '').toLowerCase();
        if (prefix === 'quiz' || prefix === 'thi' || prefix === 'xep-hang') {
            quizId = decodeURIComponent(segments[1] || '');
        } else if (path.startsWith('giao-vien/de/')) {
            quizId = decodeURIComponent(segments[2] || '');
        } else if (path && path.length >= 5 && path.length <= 15 && !path.includes('.html') && !path.includes('/')) {
            const reserved = ['login', 'admin', 'auth', 'register', 'dang-nhap', 'giao-vien', 'lich-su', 'editor', 'privacy', 'terms', 'about', 'contact', 'de-thi'];
            if (!reserved.includes(path.toLowerCase())) {
                quizId = path;
            }
        }
    }
    if (quizId) {
        quizId = quizId.replace(/\.html$/i, '').trim();
    }
    return quizId || null;
}

async function initApp() {
    const quizId = getCurrentQuizId();
    if (quizId) {
        document.getElementById('creationHub').style.display = 'none';
        document.getElementById('btnEdit').style.display = 'none'; 
        document.getElementById('quiz-container').innerHTML = renderHntnInlineLoader('Đang tải dữ liệu bài thi...', 'Vui lòng chờ trong giây lát...', 85);
        try {
            const response = await fetch(`${API_BASE_URL}/api/get_quiz/${quizId}?teacher_token=${getTeacherTokenParam()}`);
            const result = await response.json();
            if (result.status === 'success') {
                document.getElementById('quiz-container').innerHTML = '';
                currentData = normalizeImageUrls(result.data);
                currentData.forEach((q, i) => { q._originalIndex = i; });
                serverData = JSON.parse(JSON.stringify(currentData));
                const serverUpdatedAt = result.updated_at || 0;
                currentQuizServerUpdatedAt = serverUpdatedAt;
                
                // Cập nhật tiêu đề trang web & URL thân thiện kèm slug tiêu đề
                if (result.title) {
                    document.title = `${result.title} - HocNhanhTN`;
                    try {
                        const slug = slugifyVietnamese(result.title);
                        const curPath = window.location.pathname;
                        if (slug && (curPath === `/thi/${quizId}` || curPath === `/thi/${quizId}/` || curPath === `/quiz/${quizId}` || curPath === `/quiz/${quizId}/`)) {
                            history.replaceState({ page: 'exam', quizId: quizId }, '', `/thi/${encodeURIComponent(quizId)}/${slug}`);
                        }
                    } catch(e) {}
                }

                // --- Thiết lập Giao diện Dành riêng cho Học sinh ---
                const oldHeader = document.querySelector('.header');
                if (oldHeader) oldHeader.style.display = 'none';
                document.getElementById('studentHeader').style.display = 'none'; // Chỉ hiển thị sau khi bấm Bắt đầu
                document.getElementById('studentQuizTitle').innerText = result.title;
                const sQCount = document.getElementById('studentQCount');
                if (sQCount) sQCount.style.display = 'none';
                
                currentTimeLimit = parseInt(result.time_limit, 10) || 0;
                currentDataMode = result.mode || 'practice';
                const examTimerVal = document.getElementById('examTimerVal');
                if (currentTimeLimit > 0) {
                    if (examTimerVal) examTimerVal.innerText = `${currentTimeLimit}:00`;
                } else {
                    if (examTimerVal) examTimerVal.innerText = `00:00`;
                }
                const initialDisplayName = (authToken && authName) ? authName : 'Thí sinh';
                updateStudentNameDisplay(initialDisplayName);
                if (authToken && authName) {
                    const sNameInput = document.getElementById('studentNameInput');
                    if (sNameInput && !sNameInput.value) sNameInput.value = authName;
                }
                
                // Cập nhật thông tin đề thi lên thẻ Chào mừng
                const welcomeMsg = document.getElementById('welcomeMsgText');
                if (welcomeMsg) {
                    welcomeMsg.innerHTML = `<span style="font-size: 1.25rem; font-weight: 800; color: #1976d2; display: block; margin-bottom: 6px;">${escapeHtml(result.title)}</span>
                    <span style="display: inline-flex; gap: 14px; font-weight: 600; color: #475569; font-size: 0.95rem;">
                        <span><i class="ri-hashtag"></i> <b>${currentData.length}</b> câu hỏi</span>
                        <span><i class="ri-time-line"></i> <b>${currentTimeLimit > 0 ? currentTimeLimit + ' phút' : 'Tự do'}</b></span>
                        ${result.is_shuffle ? '<span style="color: #059669;"><i class="ri-shuffle-line"></i> Đã đảo câu</span>' : ''}
                    </span>`;
                }
                
                document.getElementById('modeSwitch').style.display = 'none'; // Ẩn hoàn toàn các nút công cụ
                
                isShuffleEnabled = result.is_shuffle;
                
                // KHÔI PHỤC TIẾN TRÌNH TỪ CLOUD HOẶC LOCAL STORAGE
                let localProgress = null;
                const localP = localStorage.getItem(`quiz_progress_${quizId}`);
                if (localP) { try { localProgress = JSON.parse(localP); } catch(e){} }
                
                let cloudProgress = null;
                if (authRole === 'student' && authToken) {
                    try {
                        const pRes = await fetch(`${API_BASE_URL}/api/student/get_progress/${quizId}?student_token=${authToken}`);
                        const pData = await pRes.json();
                        if (pData.status === 'success' && pData.data) {
                            cloudProgress = pData.data;
                        }
                    } catch(e) { console.log("Lỗi tải tiến trình cloud", e); }
                }
                
                let loadedProgress = null;
                if (localProgress && cloudProgress) {
                    const localAnswersCount = Object.keys(localProgress.answers || {}).length;
                    const cloudAnswersCount = Object.keys(cloudProgress.answers || {}).length;
                    loadedProgress = (localAnswersCount >= cloudAnswersCount) ? localProgress : cloudProgress;
                } else {
                    loadedProgress = localProgress || cloudProgress;
                }
                
                if (loadedProgress) {
                    try {
                        let localTs = loadedProgress.quizUpdatedAt || 0;
                        if (localTs > 0 && serverUpdatedAt > 0 && localTs < serverUpdatedAt) {
                            alert("⚠️ Đề thi đã được giáo viên cập nhật nội dung/đáp án mới!\nTiến trình làm bài cũ của bạn sẽ được làm mới lại để đảm bảo tính chính xác.");
                            let oldHistory = loadedProgress.history || [];
                            let sName = loadedProgress.studentName || "";
                            loadedProgress = { history: oldHistory, studentName: sName, quizUpdatedAt: serverUpdatedAt, timeLimit: currentTimeLimit };
                            localStorage.setItem(`quiz_progress_${quizId}`, JSON.stringify(loadedProgress));
                        } else {
                            if (!loadedProgress.quizUpdatedAt) loadedProgress.quizUpdatedAt = serverUpdatedAt;
                        }
                        
                        quizProgress = loadedProgress;
                        
                        // KIỂM TRA ĐIỀU KIỆN RESET THEO YÊU CẦU:
                        // 1. Nếu đề có giới hạn thời gian: chỉ reset khi hết thời gian làm bài kể cả thoát ra
                        // 2. Nếu đề không để thời gian: chỉ reset sau 3 tiếng kể từ khi nhấn vào làm đề
                        let isExpired = false;
                        let expireReason = '';
                        if (!quizProgress.completed && quizProgress.startedAt) {
                            const elapsedMs = Date.now() - quizProgress.startedAt;
                            if (currentTimeLimit > 0) {
                                const totalAllowedMs = currentTimeLimit * 60 * 1000;
                                if (elapsedMs >= totalAllowedMs) {
                                    isExpired = true;
                                    expireReason = 'time_limit';
                                }
                            } else {
                                const threeHoursMs = 3 * 3600 * 1000; // 3 tiếng
                                if (elapsedMs >= threeHoursMs) {
                                    isExpired = true;
                                    expireReason = 'three_hours';
                                }
                            }
                        }
                        
                        if (isExpired) {
                            // Đã hết thời gian cho phép -> Reset tiến trình đang dở
                            let oldHistory = quizProgress.history || [];
                            let sName = quizProgress.studentName || "";
                            quizProgress = { 
                                history: oldHistory, 
                                studentName: sName, 
                                quizUpdatedAt: serverUpdatedAt, 
                                timeLimit: currentTimeLimit 
                            };
                            localStorage.setItem(`quiz_progress_${quizId}`, JSON.stringify(quizProgress));
                            if (expireReason === 'time_limit') {
                                showToast("⏳ Đã hết thời gian làm bài (tính cả khi bạn thoát ra). Bài thi đã được làm mới.", "warning");
                            } else {
                                showToast("⏳ Đã quá 3 tiếng kể từ khi bắt đầu làm đề tự do. Tiến trình làm bài đã được làm mới.", "warning");
                            }
                        } else {
                            // Tiến trình còn hiệu lực -> Phục hồi
                            if (quizProgress.studentName) {
                                studentName = quizProgress.studentName;
                                const sNameInput = document.getElementById('studentNameInput');
                                if (sNameInput) sNameInput.value = studentName;
                            }
                            if (quizProgress.shuffledData) currentData = quizProgress.shuffledData;
                            if (!quizProgress.quizUpdatedAt) quizProgress.quizUpdatedAt = serverUpdatedAt;
                            
                            // Phục hồi trạng thái luyện tập (Đúng / Sai) của từng câu nếu có
                            if (quizProgress.practiceResults && currentData) {
                                currentData.forEach((q, idx) => {
                                    if (quizProgress.practiceResults[idx]) {
                                        q._practiceStatus = quizProgress.practiceResults[idx];
                                        if (quizProgress.answers && quizProgress.answers[idx] !== undefined) {
                                            q.user_answer_practice = quizProgress.answers[idx];
                                        }
                                    }
                                });
                            }
                            
                            // Cập nhật lại thời gian chính xác cho timer theo thời gian thực
                            if (!quizProgress.completed && quizProgress.startedAt) {
                                const elapsedSec = Math.floor((Date.now() - quizProgress.startedAt) / 1000);
                                if (currentTimeLimit > 0) {
                                    quizProgress.timeRemaining = Math.max(0, (currentTimeLimit * 60) - elapsedSec);
                                    quizProgress.timeElapsed = Math.min(currentTimeLimit * 60, elapsedSec);
                                } else {
                                    quizProgress.timeElapsed = elapsedSec;
                                }
                            }
                        }
                        
                        if (quizProgress.history && quizProgress.history.length > 0) {
                            const histSec = document.getElementById('historySection');
                            histSec.style.display = 'block';
                            
                            let hHtml = `<p style="color: var(--success); font-weight: 700; margin-bottom: 10px; font-size: 1.1rem;">✅ Bạn đã làm bài này ${quizProgress.history.length} lần</p>`;
                            hHtml += `<div style="max-height: 150px; overflow-y: auto; margin-bottom: 15px; text-align: left; background: #f9fafb; padding: 10px; border-radius: 8px; border: 1px solid var(--border); font-size: 0.9rem;">`;
                            quizProgress.history.slice().reverse().forEach((h, i) => { // Đảo ngược để lần mới nhất lên đầu
                                hHtml += `<div style="border-bottom: 1px solid #e5e7eb; padding: 8px 0; ${i === quizProgress.history.length - 1 ? 'border-bottom: none;' : ''}">
                                    <strong>Lần ${quizProgress.history.length - i} (${h.mode || 'Thi thử'}):</strong> <span style="color: var(--primary); font-weight: bold;">${h.score} / ${h.total}</span> câu - ⏱ ${formatTime(h.timeElapsed)} <br><span style="color: #6b7280; font-size: 0.8rem;">📅 ${h.date}</span>
                                </div>`;
                            });
                            hHtml += `</div>`;
                            
                            if (quizProgress.completed) {
                                hHtml += `<button class="btn-outline" style="font-size: 1rem; padding: 8px 15px; margin-right: 10px; background: white;" onclick="reviewHistory()">🔍 Xem lại bài làm gần nhất</button>`;
                                document.getElementById('startBtn').innerText = "🔄 Làm lại vòng mới";
                                document.getElementById('startBtn').style.backgroundColor = "var(--text-muted)";
                            } else if (!isExpired && quizProgress.startedAt) {
                                document.getElementById('startBtn').innerText = "🚀 Tiếp tục làm bài đang dở";
                            }
                            histSec.innerHTML = hHtml;
                        } else if (quizProgress.completed) {
                            const histSec = document.getElementById('historySection');
                            histSec.style.display = 'block';
                            histSec.innerHTML = `
                                <p style="color: var(--success); font-weight: 700; margin-bottom: 10px; font-size: 1.1rem;">✅ Hệ thống ghi nhận bạn đã làm bài này trước đó!</p>
                                <p style="margin-bottom: 15px; color: var(--text-muted);">Điểm lần trước: <b style="color: var(--primary); font-size: 1.3rem;">${quizProgress.score} / ${currentData.length}</b></p>
                                <button class="btn-outline" style="font-size: 1rem; padding: 10px 20px; margin-right: 10px; background: white;" onclick="reviewHistory()">🔍 Xem lại bài đã nộp</button>
                            `;
                            document.getElementById('startBtn').innerText = "🔄 Làm lại bài mới (Xóa dữ liệu cũ)";
                            document.getElementById('startBtn').style.backgroundColor = "var(--text-muted)";
                        } else if (!isExpired && quizProgress.startedAt) {
                            document.getElementById('startBtn').innerText = "🚀 Tiếp tục làm bài đang dở";
                        }
                    } catch(e){ console.error("Lỗi phục hồi tiến trình:", e); }
                }
                
                if ((!quizProgress || !quizProgress.shuffledData) && isShuffleEnabled) {
                    shuffleQuiz(true); // Trộn đề ngầm, không render lại ngay
                }
                
                isStudentMode = true;
                currentDataMode = result.mode || 'practice';
                
                // TỰ ĐỘNG KHÔI PHỤC KHI LỠ THOÁT RA (NẾU ĐANG LÀM DỞ, CHƯA HẾT HẠN VÀ KHÔNG BẤM NÚT THOÁT CHỦ ĐỘNG):
                const canAutoResume = quizProgress && !quizProgress.completed && quizProgress.startedAt && !quizProgress.paused;
                if (canAutoResume) {
                    hidePageInitialLoader();
                    updateAdPassUI();
                    if (window.ENABLE_WEBLLM && window.WebLLMTutor) {
                        window.WebLLMTutor.preload();
                    }
                    startStudentQuiz(true); // Tự động vào thẳng lại bài thi đang làm dở
                    showToast("🔄 Đã tự động khôi phục bài thi đang làm dở của bạn!", "info");
                    return;
                }
                
                document.getElementById('welcomeScreen').style.display = 'block'; // Hiển thị khung nhập tên
                updateAdPassUI(); // Cập nhật trạng thái vé 12h làm bài

                // Kích hoạt nạp ngầm mô hình WebLLM qua Web Worker ngay khi học sinh vào phòng thi (nếu bật tính năng)
                if (window.ENABLE_WEBLLM && window.WebLLMTutor) {
                    window.WebLLMTutor.preload();
                }
                hidePageInitialLoader();
            } else { 
                hidePageInitialLoader();
                document.getElementById('quiz-container').innerHTML = "<p style='text-align:center;'>Bài thi không tồn tại hoặc đã bị xóa.</p>"; 
            }
        } catch (e) {
            hidePageInitialLoader();
            document.getElementById('quiz-container').innerHTML = `<p style='text-align:center; color: var(--danger);'><b>Không thể truy cập:</b> ${e.message || "Lỗi máy chủ"}</p>`;
            if (e.message) alert(e.message);
        }
    }
};

function sendPing() {
    if (!quizProgress || quizProgress.completed || !studentName) return;
    
    const quizId = getCurrentQuizId();
    if (!quizId) return;

    // Tính toán số câu đã làm (Answers count)
    const answersCount = Object.keys(quizProgress.answers || {}).length;

    fetch(`${API_BASE_URL}/api/monitor/ping`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            quiz_id: quizId,
            session_id: clientSessionId,
            student_name: studentName,
            answers_count: answersCount,
            time_remaining: quizProgress.timeRemaining || 0,
            completed: false
        })
    }).catch(e => console.error("Ping error:", e));
}

// =========================================================================
// HỆ THỐNG MỞ KHÓA 12H LÀM BÀI QUA QUẢNG CÁO (REWARDED ADS)
// CỜ BẬT/TẮT: Tạm tắt (false) trong giai đoạn chờ Google AdSense xét duyệt.
// Sau khi được duyệt, chỉ cần đổi thành true để tự động kích hoạt lại 100%!
// =========================================================================
window.ENABLE_REWARD_ADS = false;

const AD_PASS_STORAGE_KEY = 'hocnhanhtn_pass_until';
const AD_PASS_DURATION_MS = 12 * 60 * 60 * 1000; // 12 tiếng = 43,200,000 ms
let adCountdownTimer = null;
let isAdSenseScriptLoaded = false;

// Nạp Google AdSense SDK theo nhu cầu - CHỈ KHI Ở LINK LÀM BÀI & KHI BẬT QUẢNG CÁO
function loadAdSenseScriptOnlyForQuiz() {
    if (!window.ENABLE_REWARD_ADS) return; // Tạm tắt khi chưa được Google duyệt
    const quizId = getCurrentQuizId();
    if (!quizId) return; // Tuyệt đối không nạp nếu ở trang chủ, đăng nhập, v.v.
    if (isAdSenseScriptLoaded || document.getElementById('adsense-sdk-script') || document.querySelector('script[src*="pagead2.googlesyndication.com"]')) {
        isAdSenseScriptLoaded = true;
        return;
    }

    try {
        const script = document.createElement('script');
        script.id = 'adsense-sdk-script';
        script.async = true;
        script.src = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5865046257484388";
        script.crossOrigin = "anonymous";
        document.head.appendChild(script);
        isAdSenseScriptLoaded = true;
        console.log("Đã kích hoạt AdSense cho link làm đề thi:", quizId);
    } catch (e) {
        console.warn("Không thể tải AdSense SDK:", e);
    }
}

// Kiểm tra vé 12h còn hiệu lực không
function hasValid12hPass() {
    if (!window.ENABLE_REWARD_ADS) return true; // Khi tắt quảng cáo, luôn coi như có quyền truy cập
    try {
        const expiresAt = localStorage.getItem(AD_PASS_STORAGE_KEY);
        if (!expiresAt) return false;
        const expireTs = parseInt(expiresAt, 10);
        return (!isNaN(expireTs) && Date.now() < expireTs);
    } catch (e) {
        return false;
    }
}

// Cấp quyền 12h vào localStorage
function grant12hPass() {
    try {
        const expireTime = Date.now() + AD_PASS_DURATION_MS;
        localStorage.setItem(AD_PASS_STORAGE_KEY, expireTime.toString());
        updateAdPassUI();
    } catch (e) {
        console.error("Lỗi lưu vé 12h:", e);
    }
}

// Lấy chuỗi thời gian còn lại (VD: "11 giờ 45 phút")
function getRemainingPassTimeStr() {
    try {
        const expiresAt = localStorage.getItem(AD_PASS_STORAGE_KEY);
        if (!expiresAt) return "";
        const diffMs = parseInt(expiresAt, 10) - Date.now();
        if (diffMs <= 0) return "";
        const hours = Math.floor(diffMs / (3600 * 1000));
        const minutes = Math.floor((diffMs % (3600 * 1000)) / (60 * 1000));
        if (hours > 0) return `${hours} giờ ${minutes} phút`;
        return `${minutes} phút`;
    } catch (e) {
        return "";
    }
}

// Cập nhật giao diện badge & banner quảng cáo trên màn hình chờ
function updateAdPassUI() {
    const quizId = getCurrentQuizId();
    const container = document.getElementById('adPassBadgeContainer');
    const lobbyBox = document.getElementById('lobbyAdBox');
    const activeBadge = document.getElementById('adPassActiveBadge');
    const inactiveBadge = document.getElementById('adPassInactiveBadge');
    const timeRemainingEl = document.getElementById('adPassTimeRemaining');

    // NẾU TÍNH NĂNG ĐANG TẮT HOẶC KHÔNG PHẢI LINK LÀM BÀI -> ẨN TOÀN BỘ QUẢNG CÁO & VÉ
    if (!window.ENABLE_REWARD_ADS || !quizId) {
        if (container) container.style.display = 'none';
        if (lobbyBox) lobbyBox.style.display = 'none';
        try {
            document.querySelectorAll('.google-auto-placed, ins.adsbygoogle:not(#modalAdContainer ins):not(#lobbyAdBox ins)').forEach(el => {
                el.style.setProperty('display', 'none', 'important');
            });
        } catch(e) {}
        return;
    }

    // CHỈ KHI BẬT QUẢNG CÁO VÀ Ở LINK LÀM BÀI: Tải SDK và hiển thị
    loadAdSenseScriptOnlyForQuiz();

    if (container) container.style.display = 'block';
    if (lobbyBox) {
        lobbyBox.style.display = 'block';
        try {
            (adsbygoogle = window.adsbygoogle || []).push({});
        } catch(e) {}
    }

    if (hasValid12hPass()) {
        if (timeRemainingEl) timeRemainingEl.innerText = getRemainingPassTimeStr() || "12 giờ";
        if (activeBadge) activeBadge.style.display = 'inline-flex';
        if (inactiveBadge) inactiveBadge.style.display = 'none';
    } else {
        if (activeBadge) activeBadge.style.display = 'none';
        if (inactiveBadge) inactiveBadge.style.display = 'inline-flex';
    }
}

// Mở modal (chỉ khi có quizId và tính năng bật)
function openRewardAdModal() {
    if (!window.ENABLE_REWARD_ADS) return;
    const quizId = getCurrentQuizId();
    if (!quizId) return; // Không mở nếu không ở link bài thi

    loadAdSenseScriptOnlyForQuiz();
    const modal = document.getElementById('rewardAdModal');
    const promptView = document.getElementById('rewardAdPromptView');
    const watchingView = document.getElementById('rewardAdWatchingView');
    if (!modal) return;
    if (promptView) promptView.style.display = 'block';
    if (watchingView) watchingView.style.display = 'none';
    modal.style.display = 'flex';
}

// Đóng modal
function closeRewardAdModal() {
    const modal = document.getElementById('rewardAdModal');
    if (modal) modal.style.display = 'none';
    if (adCountdownTimer) {
        clearInterval(adCountdownTimer);
        adCountdownTimer = null;
    }
}

// Xử lý khi bấm nút "Bắt đầu làm bài thi"
function handleStartQuizWithAdCheck() {
    // NẾU TÍNH NĂNG QUẢNG CÁO ĐANG TẠM ẨN -> CHO HỌC SINH VÀO LÀM BÀI NGAY LẬP TỨC 100%
    if (!window.ENABLE_REWARD_ADS) {
        startStudentQuiz();
        return;
    }
    // Nếu học sinh đã có vé 12h hợp lệ -> Cho vào làm bài ngay lập tức
    if (hasValid12hPass()) {
        startStudentQuiz();
        return;
    }
    // Nếu chưa có vé -> Mở popup xem quảng cáo
    openRewardAdModal();
}

// Khi học sinh chọn xem quảng cáo
function startWatchingAdProcess() {
    const promptView = document.getElementById('rewardAdPromptView');
    const watchingView = document.getElementById('rewardAdWatchingView');
    if (promptView) promptView.style.display = 'none';
    if (watchingView) watchingView.style.display = 'block';

    // Đẩy quảng cáo AdSense vào khung modal nếu có
    try {
        if (window.adsbygoogle && Array.isArray(window.adsbygoogle)) {
            window.adsbygoogle.push({});
        }
    } catch(e) {}

    let totalSeconds = 30;
    let secondsLeft = totalSeconds;
    const countdownText = document.getElementById('adCountdownText');
    const progressBar = document.getElementById('adProgressBar');
    const finishBtn = document.getElementById('btnFinishAd');

    if (countdownText) countdownText.innerText = `${secondsLeft}s`;
    if (progressBar) progressBar.style.width = '0%';
    if (finishBtn) {
        finishBtn.disabled = true;
        finishBtn.style.cursor = 'not-allowed';
        finishBtn.style.background = '#94a3b8';
        finishBtn.innerText = 'Vui lòng xem hết để mở khóa...';
    }

    if (adCountdownTimer) clearInterval(adCountdownTimer);
    adCountdownTimer = setInterval(() => {
        secondsLeft--;
        const progressPercent = Math.round(((totalSeconds - secondsLeft) / totalSeconds) * 100);
        
        if (countdownText) countdownText.innerText = `${secondsLeft}s`;
        if (progressBar) progressBar.style.width = `${progressPercent}%`;

        if (secondsLeft <= 0) {
            clearInterval(adCountdownTimer);
            adCountdownTimer = null;
            if (countdownText) countdownText.innerText = '✓ Hoàn thành!';
            if (progressBar) progressBar.style.width = '100%';
            if (finishBtn) {
                finishBtn.disabled = false;
                finishBtn.style.cursor = 'pointer';
                finishBtn.style.background = 'linear-gradient(135deg, #10b981 0%, #059669 100%)';
                finishBtn.innerText = '✓ Đã mở khóa 12h! Bấm để vào làm bài ngay';
            }
            // Tự động chuyển vào làm bài sau 1.2 giây
            setTimeout(() => {
                finishRewardAndEnterQuiz();
            }, 1200);
        }
    }, 1000);
}

// Hoàn thành nhận thưởng và vào làm bài
function finishRewardAndEnterQuiz() {
    grant12hPass();
    closeRewardAdModal();
    startStudentQuiz();
}

// Bỏ qua khẩn cấp (cho học sinh đang thi gấp)
function bypassAdOnceForEmergency() {
    closeRewardAdModal();
    startStudentQuiz();
}

async function startStudentQuiz(isResume = false) {
    const nameInput = document.getElementById('studentNameInput');
    const inputVal = nameInput ? nameInput.value.trim() : '';
    if (inputVal) {
        studentName = inputVal;
    } else if (quizProgress && quizProgress.studentName) {
        studentName = quizProgress.studentName;
    } else if (authName) {
        studentName = authName;
    } else {
        studentName = 'Thí sinh';
    }
    
    const quizId = getCurrentQuizId();

    // Nếu bấm nút khi đã hoàn thành -> Có nghĩa là muốn Xóa lịch sử làm lại từ đầu
    if (quizProgress && quizProgress.completed && !isResume) {
        const startBtn = document.getElementById('startBtn');
        const originalText = startBtn ? startBtn.innerText : '';
        if (startBtn) {
            startBtn.innerText = "⏳ Đang tải dữ liệu mới...";
            startBtn.disabled = true;
        }
        showGlobalLoader({
            title: "Đang tải dữ liệu bài thi mới...",
            subtitle: "Đang nạp câu hỏi và thiết lập lại lượt thi mới..."
        });
        
        if (quizId) {
            try {
                const response = await fetch(`${API_BASE_URL}/api/get_quiz/${quizId}?teacher_token=${getTeacherTokenParam()}`);
                const result = await response.json();
                if (result.status === 'success') {
                    serverData = normalizeImageUrls(result.data);
                    serverData.forEach((q, i) => { q._originalIndex = i; });
                    isShuffleEnabled = result.is_shuffle;
                    quizProgress.quizUpdatedAt = result.updated_at || 0;
                    currentTimeLimit = parseInt(result.time_limit, 10) || 0;
                    currentDataMode = result.mode || 'practice';
                }
            } catch(e) { console.error(e); }
        }

        let oldHistory = quizProgress.history || [];
        let updatedTs = quizProgress.quizUpdatedAt || currentQuizServerUpdatedAt;
        quizProgress = { 
            history: oldHistory, 
            quizUpdatedAt: updatedTs,
            startedAt: Date.now(),
            timeLimit: currentTimeLimit,
            studentName: studentName,
            answers: {},
            completed: false,
            paused: false
        };
        currentData = JSON.parse(JSON.stringify(serverData)); // KHÔI PHỤC DATA MỚI NHẤT TỪ SERVER
        if (isShuffleEnabled) shuffleQuiz(true);
        quizProgress.shuffledData = currentData;
        
        hideGlobalLoader();
        if (startBtn) {
            startBtn.innerText = originalText;
            startBtn.disabled = false;
        }
    } else {
        // Lần đầu vào hoặc tiếp tục bài làm đang dở
        if (!quizProgress.startedAt) {
            quizProgress.startedAt = Date.now();
        }
        quizProgress.timeLimit = currentTimeLimit;
        quizProgress.quizUpdatedAt = quizProgress.quizUpdatedAt || currentQuizServerUpdatedAt;
        quizProgress.completed = false;
        quizProgress.paused = false;
        if (!quizProgress.answers) quizProgress.answers = {};
        if (!quizProgress.shuffledData) quizProgress.shuffledData = currentData;
    }
    
    quizProgress.studentName = studentName;
    saveProgressToLocal();
    
    document.getElementById('welcomeScreen').style.display = 'none';
    resetSubmissionReviewUI();
    document.getElementById('studentHeader').style.display = 'block';
    updateStudentNameDisplay(studentName);
    document.body.classList.add('minimal-mode');
    toggleMobileNavSheet(false);
    const mobileBar = document.getElementById('azotaMobileExamBar');
    if (mobileBar) {
        if ((currentDataMode === 'exam' || currentDataMode === 'practice') && window.innerWidth <= 960) {
            mobileBar.style.display = 'flex';
        } else {
            mobileBar.style.display = 'none';
        }
    }
    // KHỞI TẠO PHIÊN THI VỚI SERVER VÀ KÍCH HOẠT CHỐNG GIAN LẬN NẾU Ở CHẾ ĐỘ THI THỬ
    if (currentDataMode === 'exam') {
        if (quizId && (!window.currentExamSessionId || !isResume)) {
            try {
                fetch(`${API_BASE_URL}/api/student/start_exam`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        quiz_id: quizId,
                        student_name: studentName,
                        student_token: (typeof authToken !== 'undefined' ? authToken : '')
                    })
                })
                .then(r => r.json())
                .then(res => {
                    if (res && res.status === 'success' && res.data) {
                        window.currentExamSessionId = res.data.session_id;
                        if (quizProgress) quizProgress.sessionId = res.data.session_id;
                    }
                })
                .catch(err => console.warn("Lỗi khởi tạo phiên thi server:", err));
            } catch (err) {
                console.warn(err);
            }
        }
        if (document.documentElement.requestFullscreen) {
            document.documentElement.requestFullscreen().catch(err => console.log("Fullscreen error:", err));
        }
    }
    
    const isContinuing = Boolean(quizProgress.startedAt && (!quizProgress.completed || isResume));
    switchMode(currentDataMode, isContinuing); 
    startTimer(currentTimeLimit);

    if (currentDataMode === 'exam') {
        initExamAntiCheat();
        initExamSessionUnique(quizId);
    } else {
        destroyExamAntiCheat();
        destroyExamSessionUnique();
    }
    
    // Đảm bảo WebLLM được nạp ngầm qua Web Worker (nếu bật tính năng)
    if (window.ENABLE_WEBLLM && window.WebLLMTutor) {
        window.WebLLMTutor.preload();
    }
    
    const quizContainer = document.getElementById('quiz-container');
    if (quizContainer && typeof quizContainer.scrollTo === 'function') quizContainer.scrollTo({ top: 0, behavior: 'smooth' });
    if (typeof window.scrollTo === 'function') window.scrollTo({ top: 0, behavior: 'smooth' });
    
    clearInterval(heartbeatInterval);
}

function restartPractice() {
    fetchLatestDataAndRestart('practice');
}

function restartExam() {
    fetchLatestDataAndRestart('exam');
}

async function fetchLatestDataAndRestart(mode) {
    resetSubmissionReviewUI();
    const quizId = getCurrentQuizId();
    
    const container = document.getElementById('quiz-container');
    if (container) container.innerHTML = renderHntnInlineLoader('Đang tải dữ liệu mới nhất...', 'Hệ thống đang đồng bộ với máy chủ...', 85);
    
    if (quizId) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/get_quiz/${quizId}?teacher_token=${getTeacherTokenParam()}`);
            const result = await response.json();
            if (result.status === 'success') {
                serverData = normalizeImageUrls(result.data);
                serverData.forEach((q, i) => { q._originalIndex = i; });
                isShuffleEnabled = result.is_shuffle;
                quizProgress.quizUpdatedAt = result.updated_at || 0;
                currentTimeLimit = result.time_limit || 0;
            }
        } catch(e) { console.error("Lỗi cập nhật data mới", e); }
    }
    
    let oldHistory = quizProgress.history || [];
    let updatedTs = quizProgress.quizUpdatedAt || currentQuizServerUpdatedAt;
    quizProgress = { 
        history: oldHistory, 
        studentName: studentName, 
        quizUpdatedAt: updatedTs,
        startedAt: Date.now(),
        timeLimit: currentTimeLimit,
        answers: {},
        completed: false,
        paused: false
    };
    currentData = JSON.parse(JSON.stringify(serverData)); // KHÔI PHỤC DATA MỚI NHẤT TỪ SERVER
    
    if (isShuffleEnabled) {
        shuffleQuiz(true);
    }
    
    quizProgress.shuffledData = currentData;
    saveProgressToLocal();
    
    updateStudentNameDisplay(studentName);
    
    switchMode(mode, false);
    document.body.classList.add('minimal-mode');
    document.body.classList.remove('quiz-completed');
    const mobileBar = document.getElementById('azotaMobileExamBar');
    if (mobileBar) {
        if ((mode === 'exam' || mode === 'practice') && window.innerWidth <= 960) {
            mobileBar.style.display = 'flex';
        } else {
            mobileBar.style.display = 'none';
        }
    }
    const mobileNextBtn = document.getElementById('mobileNextBtn');
    if (mobileNextBtn) {
        mobileNextBtn.style.display = 'inline-flex';
        mobileNextBtn.innerHTML = 'Câu tiếp <i class="ri-arrow-right-line"></i>';
    }
    updateNavProgressBadge();
    
    startTimer(currentTimeLimit);
    
    if (container) container.scrollTo({ top: 0, behavior: 'smooth' });
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    sendPing();
}

function reviewHistory() {
    document.getElementById('welcomeScreen').style.display = 'none';
    studentName = quizProgress.studentName;
    currentMode = 'exam'; 
    document.getElementById('modeSwitch').style.display = 'none';
    document.getElementById('studentHeader').style.display = 'block';
    updateStudentNameDisplay(studentName);
    document.body.classList.add('minimal-mode');
    if (document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(err => console.log("Fullscreen error:", err));
    }
    
    renderData(); 
    submitExam(true); // Gọi chấm điểm nhưng truyền cờ isReview = true để không gửi server
}

let cloudSyncTimer = null;
function debouncedSyncCloud(quizId) {
    if (authRole !== 'student' || !authToken || !quizId) return;
    if (cloudSyncTimer) clearTimeout(cloudSyncTimer);
    cloudSyncTimer = setTimeout(() => {
        fetch(`${API_BASE_URL}/api/student/save_progress`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ student_token: authToken, quiz_id: quizId, progress_data: quizProgress })
        }).catch(e => console.log("Lỗi đồng bộ cloud"));
    }, 4000); // Debounce 4 giây gom nhiều thao tác chọn đáp án thành 1 lần lưu
}

async function saveProgressToLocal(syncCloud = true) {
    const quizId = getCurrentQuizId();
    if (quizId) {
        if (!quizProgress.quizUpdatedAt && currentQuizServerUpdatedAt) {
            quizProgress.quizUpdatedAt = currentQuizServerUpdatedAt;
        }
        localStorage.setItem(`quiz_progress_${quizId}`, JSON.stringify(quizProgress));
        
        // Chỉ đồng bộ ngầm lên Cloud Server khi có thay đổi đáp án thực tế (syncCloud = true)
        // Tuyệt đối KHÔNG đồng bộ Cloud theo nhịp đếm giây đồng hồ để tránh đốt Quota Firestore
        if (syncCloud && authRole === 'student' && authToken && !quizProgress.completed) {
            debouncedSyncCloud(quizId);
        }
    }
}

function joinQuizByCode() {
    let code = document.getElementById('joinQuizCode').value.trim();
    if (!code) return alert("Vui lòng nhập mã đề thi!");
    
    // Nếu học sinh lỡ dán cả đường link thì hệ thống tự bóc tách mã ra
    if (code.includes('?id=')) code = code.split('?id=')[1].split('&')[0];
    else if (code.includes('?quiz_id=')) code = code.split('?quiz_id=')[1].split('&')[0];
    else if (code.includes('/')) code = code.substring(code.lastIndexOf('/') + 1);

    window.location.href = `/?id=${code}`;
}

function toggleTrashView() {
    isShowingTrash = !isShowingTrash;
    document.getElementById('btnToggleTrash').innerText = isShowingTrash ? "🔙 Quay lại Danh sách" : "🗑️ Xem Thùng rác";
    loadTeacherQuizzes();
}

function setQuizFilter(filter) {
    activeQuizFilter = filter;
    document.querySelectorAll('.azota-tab-btn').forEach(btn => {
        if (btn.getAttribute('data-filter') === filter) btn.classList.add('active');
        else btn.classList.remove('active');
    });
    renderFilteredQuizzes();
}

function filterTeacherQuizzes() {
    renderFilteredQuizzes();
}

function renderFilteredQuizzes() {
    const grid = document.getElementById('teacherQuizGrid');
    if (!grid) return;
    const searchVal = (document.getElementById('quizSearchInput')?.value || '').toLowerCase().trim();

    let filtered = rawTeacherQuizzes.filter(q => {
        // Status filter
        if (activeQuizFilter === 'published' && q.status !== 'published') return false;
        if (activeQuizFilter === 'unpublished' && q.status !== 'unpublished') return false;
        if (activeQuizFilter === 'trashed' && q.status !== 'trashed') return false;
        if (activeQuizFilter === 'all' && q.status === 'trashed') return false; // Thùng rác chỉ xem khi bấm tab Thùng rác

        // Keyword search filter
        if (searchVal) {
            const titleMatch = (q.title || '').toLowerCase().includes(searchVal);
            const idMatch = (q.id || '').toLowerCase().includes(searchVal);
            if (!titleMatch && !idMatch) return false;
        }
        return true;
    });

    if (filtered.length === 0) {
        grid.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 48px 20px; background: white; border-radius: 12px; border: 1.5px dashed var(--azota-border);">
                <i class="ri-inbox-line" style="font-size: 3rem; color: #94a3b8; display: block; margin-bottom: 12px;"></i>
                <div style="font-size: 1.1rem; font-weight: 700; color: #475569;">Không tìm thấy đề thi phù hợp</div>
                <p style="color: #94a3b8; font-size: 0.9rem; margin-top: 4px;">Hãy thử tìm từ khóa khác hoặc bấm Tạo đề mới.</p>
            </div>
        `;
        return;
    }

    let cardsHtml = "";
    filtered.forEach(q => {
        let isTrashed = (q.status === 'trashed');
        let isPublished = (q.status === 'published');
        let statusBadge = isPublished ? '<span class="quiz-status-pill open"><i class="ri-checkbox-circle-fill"></i> Đang mở</span>' :
                          (isTrashed ? '<span class="quiz-status-pill closed"><i class="ri-delete-bin-line"></i> Đã xóa</span>' :
                                       '<span class="quiz-status-pill closed"><i class="ri-lock-fill"></i> Đã khóa</span>');
        
        let modeIcon = q.mode === 'exam' ? 'ri-file-list-3-line' : 'ri-focus-3-line';
        let modeText = q.mode === 'exam' ? 'Thi thử' : 'Luyện tập';
        let timeText = q.time_limit ? `${q.time_limit} phút` : 'Tự do';
        let toggleAction = isPublished ? 'unpublished' : 'published';
        let toggleIcon = isPublished ? '<i class="ri-lock-line"></i> Khóa' : '<i class="ri-lock-unlock-line"></i> Mở';

        let actionButtons = "";
        if (isTrashed) {
            actionButtons = `
                <div class="azota-btn-row">
                    <button class="btn-azota-sub" style="color: #059669; border-color: #a7f3d0; background: #ecfdf5;" onclick="handleQuizAction('${q.id}', 'restore')">
                        <i class="ri-refresh-line"></i> Khôi phục
                    </button>
                    <button class="btn-azota-sub" style="color: #dc2626; border-color: #fecaca; background: #fef2f2;" onclick="handleQuizAction('${q.id}', 'permanent')">
                        <i class="ri-delete-bin-7-line"></i> Xóa vĩnh viễn
                    </button>
                </div>
            `;
        } else {
            actionButtons = `
                <button class="btn-azota-copy" onclick="copyQuizLink('${q.id}')">
                    <i class="ri-file-copy-line"></i> Sao chép link làm bài
                </button>
                <div class="azota-btn-row">
                    <button class="btn-azota-sub" onclick="copyQuizCode('${q.id}')" title="Sao chép mã đề">
                        <i class="ri-barcode-line"></i> Mã đề
                    </button>
                    <button class="btn-azota-sub" onclick="editQuiz('${q.id}')" title="Chỉnh sửa trong Studio">
                        <i class="ri-edit-line"></i> Sửa
                    </button>
                    <button class="btn-azota-sub" onclick="exportQuizDocx('${q.id}')" title="Tải file Word (.docx)">
                        <i class="ri-file-word-2-line"></i> Word
                    </button>
                    <button class="btn-azota-sub" style="font-weight: 600; color: #0284c7; border-color: #bae6fd; background: #f0f9ff;" onclick="openQuizStats('${q.id}', '${(q.title || '').replace(/'/g, "\\'")}')" title="Thống kê điểm thi & chi tiết bài làm học sinh">
                        <i class="ri-bar-chart-box-line"></i> Thống kê điểm
                    </button>
                    <button class="btn-azota-sub" onclick="toggleQuizStatus('${q.id}', '${toggleAction}')" title="Khóa/Mở đề">
                        ${toggleIcon}
                    </button>
                    <button class="btn-azota-sub" style="color: #ef4444;" onclick="handleQuizAction('${q.id}', 'trash')" title="Chuyển vào thùng rác">
                        <i class="ri-delete-bin-line"></i>
                    </button>
                </div>
            `;
        }

        cardsHtml += `
            <div class="azota-quiz-card" id="card_${q.id}">
                <div class="quiz-card-head">
                    <h3 class="quiz-card-title" title="${escapeHtml(q.title || 'Đề thi')}">${escapeHtml(q.title || 'Đề thi chưa có tên')}</h3>
                    ${statusBadge}
                </div>
                <div class="quiz-card-meta">
                    <span class="quiz-meta-item"><i class="${modeIcon}"></i> ${modeText}</span>
                    <span class="quiz-meta-item"><i class="ri-hashtag"></i> ${q.question_count || 0} câu</span>
                    <span class="quiz-meta-item"><i class="ri-time-line"></i> ${timeText}</span>
                </div>
                <div class="quiz-card-actions">
                    ${actionButtons}
                </div>
            </div>
        `;
    });

    grid.innerHTML = cardsHtml;
}

// ========================================================
// STUDENT LEARNING & EXAM HISTORY MODULE
// ========================================================
let rawStudentHistory = [];
let studentHistoryFilter = 'all';
let currentHistReviewDetail = null;
let currentHistReviewFilter = 'all';

async function syncLocalCompletedQuizzesToCloud() {
    if (!authToken || authRole !== 'student') return;
    const itemsToSync = [];
    try {
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith('quiz_progress_')) {
                const raw = localStorage.getItem(key);
                if (raw) {
                    const prog = JSON.parse(raw);
                    const qid = key.replace('quiz_progress_', '');
                    if (prog.history && Array.isArray(prog.history) && prog.history.length > 0) {
                        prog.history.forEach(h => {
                            itemsToSync.push({
                                quiz_id: qid,
                                quiz_title: prog.title || `Đề thi #${qid}`,
                                score: parseFloat(h.score || 0),
                                total_questions: parseInt(h.total || 10),
                                time_elapsed: parseInt(h.timeElapsed || 0),
                                submitted_at: h.date || '',
                                answers: prog.answers || {}
                            });
                        });
                    } else if (prog.completed) {
                        itemsToSync.push({
                            quiz_id: qid,
                            quiz_title: prog.title || `Đề thi #${qid}`,
                            score: parseFloat(prog.score || 0),
                            total_questions: parseInt(prog.totalQuestions || 10),
                            time_elapsed: parseInt(prog.timeElapsed || 0),
                            submitted_at: prog.updatedAt || '',
                            answers: prog.answers || {}
                        });
                    }
                }
            }
        }
    } catch(e) {}

    if (itemsToSync.length > 0) {
        try {
            await fetch(`${API_BASE_URL}/api/student/sync_history`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    student_token: authToken,
                    history_items: itemsToSync
                })
            });
        } catch(err) {
            console.warn("Lỗi đồng bộ lịch sử cũ:", err);
        }
    }
}

async function loadStudentHistory(forceRefresh = false) {
    if (!authToken || authRole !== 'student') return;
    
    const greetingEl = document.getElementById('studentGreetingName');
    if (greetingEl) greetingEl.innerText = authName || 'Học sinh';

    const container = document.getElementById('studentHistoryList');
    if (!container) return;

    if (forceRefresh || rawStudentHistory.length === 0) {
        container.innerHTML = renderHntnInlineLoader('Đang tải lịch sử làm bài...', 'Hệ thống đang đồng bộ dữ liệu từ đám mây...', 75);
    }

    if (!window._hasSyncedLocalHistory) {
        window._hasSyncedLocalHistory = true;
        await syncLocalCompletedQuizzesToCloud();
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/student/history?student_token=${encodeURIComponent(authToken)}`);
        const data = await res.json();
        if (res.status === 403) {
            console.warn("Phiên đăng nhập học sinh đã hết hạn hoặc không hợp lệ (403).");
            showToast("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.", "warning");
            setTimeout(() => { logout(); }, 1200);
            return;
        }
        if (res.ok && data.status === 'success') {
            rawStudentHistory = data.data || [];
            
            // Tính toán KPIs
            const totalTests = rawStudentHistory.length;
            let sumScaled = 0;
            let maxScaled = 0;
            let passedCount = 0;

            let highCount = 0;
            let passCount = 0;
            let lowCount = 0;

            rawStudentHistory.forEach(item => {
                const totalQ = item.total_questions || 1;
                const scaled = totalQ > 0 ? ((item.score / totalQ) * 10) : 0;
                sumScaled += scaled;
                if (scaled > maxScaled) maxScaled = scaled;
                if (scaled >= 5.0) passedCount++;

                if (scaled >= 8.0) highCount++;
                else if (scaled >= 5.0) passCount++;
                else lowCount++;
            });

            const avgScaled = totalTests > 0 ? (sumScaled / totalTests).toFixed(1) : '--';
            const maxScaledStr = totalTests > 0 ? maxScaled.toFixed(1) : '--';
            const passedRate = totalTests > 0 ? Math.round((passedCount / totalTests) * 100) + '%' : '--%';

            // Cập nhật thẻ KPI
            const elTotal = document.getElementById('statStudentTotalTests');
            const elAvg = document.getElementById('statStudentAvgScore');
            const elMax = document.getElementById('statStudentMaxScore');
            const elRate = document.getElementById('statStudentPassedRate');
            if (elTotal) elTotal.innerText = totalTests;
            if (elAvg) elAvg.innerText = avgScaled;
            if (elMax) elMax.innerText = maxScaledStr;
            if (elRate) elRate.innerText = passedRate;

            // Cập nhật tab số lượng
            const elAll = document.getElementById('filterCountStudentAll');
            const elHigh = document.getElementById('filterCountStudentHigh');
            const elPass = document.getElementById('filterCountStudentPass');
            const elLow = document.getElementById('filterCountStudentLow');
            if (elAll) elAll.innerText = totalTests;
            if (elHigh) elHigh.innerText = highCount;
            if (elPass) elPass.innerText = passCount;
            if (elLow) elLow.innerText = lowCount;

            renderStudentHistoryList();
            if (forceRefresh) {
                showToast("Đã làm mới lịch sử bài thi thành công!", "success");
            }
        } else {
            container.innerHTML = `<div class="student-history-empty"><p style="color: #ef4444;">Không thể tải lịch sử làm bài: ${escapeHtml(data.detail || data.message || 'Lỗi server')}</p></div>`;
        }
    } catch(err) {
        console.error("Lỗi khi tải lịch sử học sinh:", err);
        container.innerHTML = `<div class="student-history-empty"><p style="color: #ef4444;">Lỗi kết nối khi tải lịch sử làm bài. Vui lòng thử lại sau.</p></div>`;
    }
}

function setStudentHistoryFilter(filter) {
    studentHistoryFilter = filter;
    document.querySelectorAll('.azota-filter-tabs .azota-tab-btn').forEach(btn => {
        if (btn.getAttribute('data-filter') === filter) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    renderStudentHistoryList();
}

function filterStudentHistory() {
    renderStudentHistoryList();
}

function formatHistoryDateTime(dateStr) {
    if (!dateStr) return '--';
    try {
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        return d.toLocaleDateString('vi-VN', {
            hour: '2-digit',
            minute: '2-digit',
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        });
    } catch(e) {
        return dateStr;
    }
}

function renderStudentHistoryList() {
    const container = document.getElementById('studentHistoryList');
    if (!container) return;

    const searchInput = document.getElementById('studentHistorySearchInput');
    const qSearch = searchInput ? searchInput.value.trim().toLowerCase() : '';

    let list = rawStudentHistory.slice();

    // Lọc theo search
    if (qSearch) {
        list = list.filter(item => {
            const title = (item.quiz_title || '').toLowerCase();
            const qid = (item.quiz_id || '').toLowerCase();
            return title.includes(qSearch) || qid.includes(qSearch);
        });
    }

    // Lọc theo tab
    if (studentHistoryFilter !== 'all') {
        list = list.filter(item => {
            const totalQ = item.total_questions || 1;
            const scaled = (item.score / totalQ) * 10;
            if (studentHistoryFilter === 'high') return scaled >= 8.0;
            if (studentHistoryFilter === 'pass') return scaled >= 5.0 && scaled < 8.0;
            if (studentHistoryFilter === 'low') return scaled < 5.0;
            return true;
        });
    }

    if (list.length === 0) {
        container.innerHTML = `
            <div class="student-history-empty">
                <div class="student-history-empty-icon">
                    <i class="ri-file-search-line"></i>
                </div>
                <h3 style="margin: 0 0 6px 0; font-size: 1.15rem; color: #1e293b; font-weight: 700;">
                    ${qSearch || studentHistoryFilter !== 'all' ? 'Không tìm thấy bài thi phù hợp' : 'Bạn chưa có bài thi nào được ghi nhận'}
                </h3>
                <p style="margin: 0 0 16px 0; font-size: 0.92rem; color: #64748b; max-width: 440px; margin-left: auto; margin-right: auto;">
                    ${qSearch || studentHistoryFilter !== 'all' ? 'Hãy thử đổi từ khóa tìm kiếm hoặc bấm tab Tất cả.' : 'Hãy nhập mã đề thi ở phía trên hoặc dán link do giáo viên gửi để bắt đầu làm bài và lưu điểm số vào đây nhé!'}
                </p>
                ${(qSearch || studentHistoryFilter !== 'all') ? `<button class="btn-outline" style="background: white;" onclick="document.getElementById('studentHistorySearchInput').value=''; setStudentHistoryFilter('all');"><i class="ri-refresh-line"></i> Đặt lại bộ lọc</button>` : ''}
            </div>
        `;
        return;
    }

    let html = '';
    list.forEach(item => {
        const totalQ = item.total_questions || 1;
        const scaledScore = totalQ > 0 ? ((item.score / totalQ) * 10).toFixed(1) : "0.0";
        const scaledNum = parseFloat(scaledScore);

        let badgeClass = 'medium';
        if (scaledNum >= 8.0) badgeClass = 'high';
        else if (scaledNum < 5.0) badgeClass = 'low';

        const title = escapeHtml(item.quiz_title || `Đề thi #${item.quiz_id}`);
        const dateStr = formatHistoryDateTime(item.submitted_at || item.timestamp);
        const timeStr = formatTime(item.time_elapsed || 0);
        const scoreFraction = `${item.score} / ${totalQ} câu`;

        html += `
            <div class="student-history-card">
                <div class="student-history-left">
                    <div class="student-score-badge ${badgeClass}" title="Điểm quy đổi thang 10">
                        <span class="score-num">${scaledScore}</span>
                        <span class="score-scale">/ 10 điểm</span>
                    </div>
                    <div class="student-history-info">
                        <div class="student-history-title" title="${title}">${title}</div>
                        <div class="student-history-meta">
                            <span style="background: #f1f5f9; padding: 2px 7px; border-radius: 6px; font-weight: 700; color: #475569; font-size: 0.8rem; border: 1px solid #e2e8f0;">
                                <i class="ri-hashtag"></i> ${escapeHtml(item.quiz_id)}
                            </span>
                            <span><i class="ri-checkbox-circle-line" style="color: #10b981;"></i> Đạt: <b>${scoreFraction}</b></span>
                            <span><i class="ri-timer-line" style="color: #0284c7;"></i> Làm trong: <b>${timeStr}</b></span>
                            <span><i class="ri-calendar-line"></i> Nộp lúc: ${dateStr}</span>
                        </div>
                    </div>
                </div>
                <div class="student-history-actions">
                    <button class="btn-history-action btn-history-review" onclick="openStudentHistoryReview('${item.id}')" title="Xem lại bài làm và lời giải">
                        <i class="ri-file-list-3-line"></i> <span>Xem lại bài làm</span>
                    </button>
                    <button class="btn-history-action btn-history-retry" onclick="retakeHistoryQuiz('${escapeHtml(item.quiz_id)}')" title="Làm lại đề thi này">
                        <i class="ri-refresh-line"></i> <span>Làm lại đề</span>
                    </button>
                    <button class="btn-history-action btn-history-delete" onclick="deleteStudentHistoryItem('${item.id}')" title="Xóa bài thi này khỏi lịch sử">
                        <i class="ri-delete-bin-line"></i>
                    </button>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function retakeHistoryQuiz(quizId) {
    if (!quizId) return;
    window.location.href = `/thi/${encodeURIComponent(quizId)}`;
}

async function openStudentHistoryReview(historyId) {
    const modal = document.getElementById('studentHistoryReviewModal');
    if (!modal) return;
    if (historyId && window.location.pathname !== `/ket-qua/${historyId}`) {
        history.pushState({ page: 'history_review', historyId: historyId }, '', `/ket-qua/${historyId}`);
    }

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    const titleEl = document.getElementById('histReviewModalTitle');
    const subEl = document.getElementById('histReviewModalSub');
    const kpiEl = document.getElementById('histReviewKpiSummary');
    const filterEl = document.getElementById('histReviewFilterBar');
    const container = document.getElementById('histReviewQuestionsContainer');
    const btnRetake = document.getElementById('btnHistReviewRetake');

    if (titleEl) titleEl.innerText = "Đang tải dữ liệu bài thi...";
    if (subEl) subEl.innerHTML = "";
    if (kpiEl) kpiEl.innerHTML = "";
    if (filterEl) filterEl.innerHTML = "";
    if (container) {
        container.innerHTML = renderHntnInlineLoader('Đang tải chi tiết bài làm...', 'Hệ thống đang nạp câu hỏi và lời giải chi tiết...', 75);
    }

    try {
        let item = rawStudentHistory.find(x => x.id === historyId);
        if (!item || !item.results || item.results.length === 0) {
            const res = await fetch(`${API_BASE_URL}/api/student/history/${historyId}?student_token=${encodeURIComponent(authToken)}`);
            const d = await res.json();
            if (res.ok && d.status === 'success') {
                item = d.data;
            }
        }

        if (!item) {
            if (container) container.innerHTML = `<div style="text-align: center; color: #ef4444; padding: 30px;">Không tìm thấy thông tin bài thi.</div>`;
            return;
        }

        currentHistReviewDetail = item;
        currentHistReviewFilter = 'all';

        const qTitle = item.quiz_title || `Đề thi #${item.quiz_id}`;
        if (titleEl) titleEl.innerText = qTitle;
        if (subEl) {
            subEl.innerHTML = `
                Mã đề: <b>${escapeHtml(item.quiz_id)}</b> • 
                Thời gian nộp: <b>${formatHistoryDateTime(item.submitted_at || item.timestamp)}</b> • 
                Thời gian làm bài: <b>${formatTime(item.time_elapsed || 0)}</b>
            `;
        }

        if (btnRetake) {
            btnRetake.onclick = () => retakeHistoryQuiz(item.quiz_id);
        }

        renderHistReviewContent();
    } catch(err) {
        console.error("Lỗi xem chi tiết bài làm:", err);
        if (container) {
            container.innerHTML = `<div style="text-align: center; color: #ef4444; padding: 30px;">Lỗi khi tải chi tiết bài làm. Vui lòng thử lại.</div>`;
        }
    }
}

function closeStudentHistoryReviewModal() {
    const modal = document.getElementById('studentHistoryReviewModal');
    if (modal) modal.style.display = 'none';
    document.body.style.overflow = '';
    if (window.location.pathname.startsWith('/ket-qua/')) {
        history.pushState({ page: 'history' }, '', '/lich-su');
    }
}

function setHistReviewFilter(filter) {
    currentHistReviewFilter = filter;
    renderHistReviewContent();
}

function renderHistReviewContent() {
    if (!currentHistReviewDetail) return;
    const item = currentHistReviewDetail;
    const results = item.results || [];
    const totalQues = item.total_questions || results.length || 1;
    const score = item.score || 0;
    const scaledScore = totalQues > 0 ? ((score / totalQues) * 10).toFixed(1) : "0.0";

    let correctCount = 0;
    let wrongCount = 0;
    let skippedCount = 0;

    results.forEach(r => {
        if (r.is_correct) correctCount++;
        else if (r.user_answer === null || r.user_answer === undefined || r.user_answer === '') skippedCount++;
        else wrongCount++;
    });

    // Render KPI
    const kpiEl = document.getElementById('histReviewKpiSummary');
    if (kpiEl) {
        kpiEl.innerHTML = `
            <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: 10px; padding: 12px; text-align: center;">
                <div style="font-size: 0.8rem; color: #64748b; font-weight: 600;">Điểm số (Thang 10)</div>
                <div style="font-size: 1.55rem; font-weight: 900; color: #2563eb; margin-top: 2px;">${scaledScore}</div>
            </div>
            <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 10px; padding: 12px; text-align: center;">
                <div style="font-size: 0.8rem; color: #047857; font-weight: 600;">Số câu đúng</div>
                <div style="font-size: 1.55rem; font-weight: 900; color: #10b981; margin-top: 2px;">${correctCount}</div>
            </div>
            <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 10px; padding: 12px; text-align: center;">
                <div style="font-size: 0.8rem; color: #b91c1c; font-weight: 600;">Số câu sai</div>
                <div style="font-size: 1.55rem; font-weight: 900; color: #ef4444; margin-top: 2px;">${wrongCount}</div>
            </div>
            <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 10px; padding: 12px; text-align: center;">
                <div style="font-size: 0.8rem; color: #b45309; font-weight: 600;">Chưa trả lời</div>
                <div style="font-size: 1.55rem; font-weight: 900; color: #f59e0b; margin-top: 2px;">${skippedCount}</div>
            </div>
        `;
    }

    // Render Filter
    const filterEl = document.getElementById('histReviewFilterBar');
    if (filterEl) {
        filterEl.innerHTML = `
            <span style="font-weight: 700; font-size: 0.88rem; color: #475569; display: flex; align-items: center; gap: 4px;">
                <i class="ri-filter-3-line"></i> Lọc:
            </span>
            <button class="azota-filter-tab ${currentHistReviewFilter === 'all' ? 'active' : ''}" onclick="setHistReviewFilter('all')">
                Tất cả (${results.length})
            </button>
            <button class="azota-filter-tab ${currentHistReviewFilter === 'correct' ? 'active' : ''}" onclick="setHistReviewFilter('correct')">
                <i class="ri-checkbox-circle-fill" style="color: #10b981;"></i> Câu đúng (${correctCount})
            </button>
            <button class="azota-filter-tab ${currentHistReviewFilter === 'wrong' ? 'active' : ''}" onclick="setHistReviewFilter('wrong')">
                <i class="ri-close-circle-fill" style="color: #ef4444;"></i> Câu sai (${wrongCount})
            </button>
            <button class="azota-filter-tab ${currentHistReviewFilter === 'skipped' ? 'active' : ''}" onclick="setHistReviewFilter('skipped')">
                <i class="ri-question-fill" style="color: #f59e0b;"></i> Chưa làm (${skippedCount})
            </button>
        `;
    }

    // Render Questions
    const container = document.getElementById('histReviewQuestionsContainer');
    if (!container) return;

    if (results.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 30px; color: #64748b; background: #f8fafc; border-radius: 10px; border: 1px dashed #cbd5e1;">
                <p style="margin: 0;">Bài thi này được đồng bộ từ bản ghi trước đây, chi tiết từng câu hỏi không còn được lưu trữ đầy đủ.</p>
                <button class="btn-primary" style="margin-top: 14px;" onclick="retakeHistoryQuiz('${escapeHtml(item.quiz_id)}')">
                    <i class="ri-refresh-line"></i> Làm lại đề thi này ngay
                </button>
            </div>
        `;
        return;
    }

    let qHtml = '';
    results.forEach((r, idx) => {
        let status = 'wrong';
        if (r.is_correct) status = 'correct';
        else if (r.user_answer === null || r.user_answer === undefined || r.user_answer === '') status = 'skipped';

        if (currentHistReviewFilter !== 'all' && currentHistReviewFilter !== status) {
            return;
        }

        const qNum = idx + 1;
        const qText = formatRichContent(r.question || `Câu hỏi ${qNum}`);
        const userAns = r.user_answer;
        const correctAns = r.correct_answer;
        const explain = r.explain;
        const earned = r.earned !== undefined ? r.earned : (r.is_correct ? 1.0 : 0.0);

        let statusBadge = '';
        if (status === 'correct') {
            statusBadge = `<span style="background: #ecfdf5; color: #047857; font-size: 0.8rem; font-weight: 700; padding: 3px 8px; border-radius: 6px; border: 1px solid #a7f3d0;"><i class="ri-checkbox-circle-fill"></i> Chính xác (+${earned}đ)</span>`;
        } else if (status === 'skipped') {
            statusBadge = `<span style="background: #fffbeb; color: #b45309; font-size: 0.8rem; font-weight: 700; padding: 3px 8px; border-radius: 6px; border: 1px solid #fde68a;"><i class="ri-question-fill"></i> Chưa trả lời (0đ)</span>`;
        } else {
            statusBadge = `<span style="background: #fef2f2; color: #b91c1c; font-size: 0.8rem; font-weight: 700; padding: 3px 8px; border-radius: 6px; border: 1px solid #fecaca;"><i class="ri-close-circle-fill"></i> Sai (0đ)</span>`;
        }

        // Render options if available
        let optionsHtml = '';
        if (Array.isArray(r.options) && r.options.length > 0) {
            optionsHtml = '<div style="display: flex; flex-direction: column; gap: 8px; margin: 12px 0;">';
            r.options.forEach((opt, optIdx) => {
                const optLetter = String.fromCharCode(65 + optIdx);
                const optText = formatRichContent(opt);
                
                let isUserChoice = matchOptionToTarget(opt, optIdx, userAns);
                let isCorrectOption = matchOptionToTarget(opt, optIdx, correctAns);
                if (status === 'correct' && isUserChoice) {
                    isCorrectOption = true;
                }

                let optBorder = '1px solid #e2e8f0';
                let optBg = '#ffffff';
                let optIcon = '';

                if (isCorrectOption) {
                    optBorder = '2px solid #10b981';
                    optBg = '#f0fdf4';
                    optIcon = '<i class="ri-checkbox-circle-fill" style="color: #10b981; margin-left: auto;"></i>';
                }
                if (isUserChoice && !isCorrectOption) {
                    optBorder = '2px solid #ef4444';
                    optBg = '#fef2f2';
                    optIcon = '<i class="ri-close-circle-fill" style="color: #ef4444; margin-left: auto;"></i>';
                }

                optionsHtml += `
                    <div style="display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-radius: 8px; border: ${optBorder}; background: ${optBg}; font-size: 0.95rem;">
                        <span style="font-weight: 700; width: 24px; height: 24px; border-radius: 50%; background: #f1f5f9; display: inline-flex; align-items: center; justify-content: center; font-size: 0.85rem; flex-shrink: 0;">${optLetter}</span>
                        <div style="flex: 1;">${optText}</div>
                        ${optIcon}
                    </div>
                `;
            });
            optionsHtml += '</div>';
        } else {
            let formattedUserAns = (typeof userAns === 'object' && userAns !== null) ? JSON.stringify(userAns) : String(userAns || 'Chưa trả lời');
            let formattedCorrectAns = (typeof correctAns === 'object' && correctAns !== null) ? JSON.stringify(correctAns) : String(correctAns || '--');
            optionsHtml = `
                <div style="margin: 10px 0; padding: 10px 12px; background: #f8fafc; border-radius: 8px; font-size: 0.92rem; border: 1px solid #e2e8f0;">
                    <div><b>Bạn đã chọn:</b> <span style="color: ${status === 'correct' ? '#10b981' : '#ef4444'}; font-weight: 600;">${escapeHtml(formattedUserAns)}</span></div>
                    <div style="margin-top: 4px;"><b>Đáp án đúng:</b> <span style="color: #10b981; font-weight: 700;">${escapeHtml(formattedCorrectAns)}</span></div>
                </div>
            `;
        }

        let explainHtml = '';
        if (explain && String(explain).trim()) {
            explainHtml = `
                <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 10px 14px; font-size: 0.9rem; color: #92400e; margin-top: 10px;">
                    <div style="font-weight: 700; display: flex; align-items: center; gap: 4px; margin-bottom: 4px;">
                        <i class="ri-lightbulb-fill" style="color: #f59e0b;"></i> Lời giải thích / Hướng dẫn:
                    </div>
                    <div>${formatRichContent(explain)}</div>
                </div>
            `;
        }

        let imgHtml = '';
        if (r.image) {
            imgHtml = `<div style="margin: 8px 0;"><img src="${escapeHtml(r.image)}" alt="Hình câu hỏi" class="quiz-image" style="max-height: 250px; border-radius: 8px; border: 1px solid #e2e8f0;"></div>`;
        }

        qHtml += `
            <div style="background: #ffffff; border: 1.5px solid ${status === 'correct' ? '#bbf7d0' : (status === 'skipped' ? '#fde68a' : '#fecaca')}; border-radius: 12px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
                <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 8px;">
                    <span style="font-weight: 800; font-size: 1rem; color: #1e293b;">Câu ${qNum}:</span>
                    ${statusBadge}
                </div>
                <div style="font-size: 1rem; color: #0f172a; line-height: 1.5;">${qText}</div>
                ${imgHtml}
                ${optionsHtml}
                ${explainHtml}
            </div>
        `;
    });

    container.innerHTML = qHtml || `<div style="text-align: center; padding: 24px; color: #64748b;">Không có câu hỏi nào theo bộ lọc đã chọn.</div>`;
    
    if (window.renderMath) {
        renderMath(container);
    }
}

async function deleteStudentHistoryItem(historyId) {
    if (!historyId || !authToken) return;
    if (!confirm("Bạn có chắc chắn muốn xóa bài thi này khỏi lịch sử không?")) return;

    try {
        const res = await fetch(`${API_BASE_URL}/api/student/history/${historyId}?student_token=${encodeURIComponent(authToken)}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            showToast("Đã xóa bài thi khỏi lịch sử thành công!", "success");
            rawStudentHistory = rawStudentHistory.filter(x => x.id !== historyId);
            loadStudentHistory(false);
        } else {
            alert("Lỗi khi xóa bài thi: " + (data.detail || data.message || "Lỗi không xác định"));
        }
    } catch(err) {
        console.error("Lỗi khi xóa:", err);
        alert("Lỗi kết nối khi xóa bài thi.");
    }
}

async function loadTeacherQuizzes() {
    const grid = document.getElementById('teacherQuizGrid');
    if (grid && (!rawTeacherQuizzes || rawTeacherQuizzes.length === 0)) {
        grid.innerHTML = renderHntnInlineLoader('Đang tải danh sách đề thi...', 'Hệ thống đang đồng bộ dữ liệu giáo viên...', 80);
    }
    try {
        const res = await fetch(`${API_BASE_URL}/api/teacher/quizzes?teacher_token=${authToken}`);
        const data = await res.json();
        if (res.status === 403) {
            console.warn("Phiên đăng nhập giáo viên đã hết hạn hoặc không hợp lệ (403).");
            showToast("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.", "warning");
            setTimeout(() => { logout(); }, 1200);
            return;
        }
        if (res.ok && data.status === 'success') {
            rawTeacherQuizzes = data.data || [];
            
            // Tính toán số liệu thống kê
            let total = 0;
            let openCount = 0;
            let lockedCount = 0;
            let trashCount = 0;
            let totalQues = 0;

            rawTeacherQuizzes.forEach(q => {
                if (q.status === 'trashed') {
                    trashCount++;
                } else {
                    total++;
                    totalQues += (q.question_count || 0);
                    if (q.status === 'published') openCount++;
                    else lockedCount++;
                }
            });

            // Cập nhật dải thống kê
            const elTotal = document.getElementById('statTotalQuizzes');
            const elOpen = document.getElementById('statOpenQuizzes');
            const elLocked = document.getElementById('statLockedQuizzes');
            const elQues = document.getElementById('statTotalQuestions');
            if (elTotal) elTotal.innerText = total;
            if (elOpen) elOpen.innerText = openCount;
            if (elLocked) elLocked.innerText = lockedCount;
            if (elQues) elQues.innerText = totalQues;

            // Cập nhật số đếm trên các Tab lọc
            const fcAll = document.getElementById('filterCountAll');
            const fcPub = document.getElementById('filterCountPublished');
            const fcLock = document.getElementById('filterCountLocked');
            const fcTrash = document.getElementById('filterCountTrash');
            if (fcAll) fcAll.innerText = total;
            if (fcPub) fcPub.innerText = openCount;
            if (fcLock) fcLock.innerText = lockedCount;
            if (fcTrash) fcTrash.innerText = trashCount;

            renderFilteredQuizzes();
        }
    } catch(e) { 
        console.error("Lỗi tải danh sách đề", e); 
        showToast("Lỗi kết nối máy chủ khi tải danh sách đề thi", "error");
    }
}

function copyQuizCode(quizId) {
    if (!quizId) return;
    navigator.clipboard.writeText(quizId).then(() => {
        showToast(`Đã sao chép Mã đề: ${quizId}`, 'success');
    }).catch(() => {
        prompt("Mã đề thi:", quizId);
    });
}

function slugifyVietnamese(text) {
    if (!text || typeof text !== 'string') return '';
    return text
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[đĐ]/g, 'd')
        .replace(/[^a-z0-9\s-]/g, '')
        .trim()
        .replace(/[\s_]+/g, '-')
        .replace(/-+/g, '-')
        .replace(/^-+|-+$/g, '');
}

function getQuizExamUrl(quizId, quizTitle = '') {
    if (!quizId) return '';
    const origin = (window.location.origin && window.location.origin !== "null") ? window.location.origin : "";
    let slug = slugifyVietnamese(quizTitle);
    if (!slug && typeof rawTeacherQuizzes !== 'undefined' && Array.isArray(rawTeacherQuizzes)) {
        const found = rawTeacherQuizzes.find(q => q && q.id === quizId);
        if (found && found.title) {
            slug = slugifyVietnamese(found.title);
        }
    }
    if (!slug && typeof allTeacherQuizzes !== 'undefined' && Array.isArray(allTeacherQuizzes)) {
        const found = allTeacherQuizzes.find(q => q && q.id === quizId);
        if (found && found.title) {
            slug = slugifyVietnamese(found.title);
        }
    }
    if (!slug && typeof currentStatsQuizId !== 'undefined' && currentStatsQuizId === quizId && typeof currentStatsQuizTitle !== 'undefined' && currentStatsQuizTitle) {
        slug = slugifyVietnamese(currentStatsQuizTitle);
    }
    const cleanId = encodeURIComponent(quizId);
    return slug ? `${origin}/thi/${cleanId}/${slug}` : `${origin}/thi/${cleanId}`;
}

function copyQuizLink(quizId, quizTitle = '') {
    if (!quizId) return;
    if (!quizTitle && typeof rawTeacherQuizzes !== 'undefined' && Array.isArray(rawTeacherQuizzes)) {
        const found = rawTeacherQuizzes.find(q => q && q.id === quizId);
        if (found && found.title) quizTitle = found.title;
    }
    const fullUrl = getQuizExamUrl(quizId, quizTitle);
    navigator.clipboard.writeText(fullUrl).then(() => {
        showToast("Đã sao chép Link làm bài thi cho học sinh!", 'success');
    }).catch(() => {
        prompt("Copy Link làm bài thi:", fullUrl);
    });
}

// ========================================================
// MODAL TÙY CHỌN XUẤT FILE WORD (.DOCX) CHUẨN IN ẤN
// ========================================================
let currentExportQuizId = null;

function exportQuizDocx(quizId, quizTitle = "") {
    if (!quizId) {
        window.location.href = '/export';
        return;
    }
    window.location.href = `/export/${encodeURIComponent(quizId)}`;
}

function openExportDocxModal(quizId, quizTitle = "") {
    currentExportQuizId = quizId;
    const modal = document.getElementById('exportDocxModal');
    if (!modal) {
        window.open(`${API_BASE_URL}/api/teacher/export_docx/${encodeURIComponent(quizId)}?teacher_token=${encodeURIComponent(authToken)}`, '_blank');
        return;
    }
    
    const titleEl = document.getElementById('exportDocxQuizTitle');
    if (titleEl) {
        titleEl.textContent = quizTitle || "Đề thi trắc nghiệm";
    }
    
    setDocxAudienceUI('teacher');
    setDocxLayoutUI('compact');
    const optSelect = document.getElementById('docxOptionsLayout');
    if (optSelect) optSelect.value = 'auto';

    modal.style.display = 'flex';
}

function closeExportDocxModal() {
    const modal = document.getElementById('exportDocxModal');
    if (modal) modal.style.display = 'none';
    currentExportQuizId = null;
}

function onDocxAudienceChange(audience) {
    setDocxAudienceUI(audience);
}

function setDocxAudienceUI(audience) {
    const cardTeacher = document.getElementById('cardAudienceTeacher');
    const cardStudent = document.getElementById('cardAudienceStudent');
    const chkAnswers = document.getElementById('docxShowAnswers');
    const chkKeyTable = document.getElementById('docxShowKeyTable');
    const chkExplains = document.getElementById('docxShowExplains');
    const lblGrid = document.getElementById('lblDocxStudentGrid');
    const chkGrid = document.getElementById('docxStudentGrid');

    if (audience === 'student') {
        if (cardStudent) {
            cardStudent.style.borderColor = '#2563eb';
            cardStudent.style.background = '#eff6ff';
            const sTitle = cardStudent.querySelector('span');
            if (sTitle) sTitle.style.color = '#1e40af';
        }
        if (cardTeacher) {
            cardTeacher.style.borderColor = '#e2e8f0';
            cardTeacher.style.background = '#f8fafc';
            const tTitle = cardTeacher.querySelector('span');
            if (tTitle) tTitle.style.color = '#334155';
        }
        const radio = document.querySelector('input[name="docxAudience"][value="student"]');
        if (radio) radio.checked = true;

        if (chkAnswers) { chkAnswers.checked = false; chkAnswers.disabled = true; }
        if (chkKeyTable) { chkKeyTable.checked = false; chkKeyTable.disabled = true; }
        if (chkExplains) { chkExplains.checked = false; chkExplains.disabled = true; }
        if (lblGrid) lblGrid.style.display = 'flex';
        if (chkGrid) chkGrid.checked = false;
    } else {
        if (cardTeacher) {
            cardTeacher.style.borderColor = '#2563eb';
            cardTeacher.style.background = '#eff6ff';
            const tTitle = cardTeacher.querySelector('span');
            if (tTitle) tTitle.style.color = '#1e40af';
        }
        if (cardStudent) {
            cardStudent.style.borderColor = '#e2e8f0';
            cardStudent.style.background = '#f8fafc';
            const sTitle = cardStudent.querySelector('span');
            if (sTitle) sTitle.style.color = '#334155';
        }
        const radio = document.querySelector('input[name="docxAudience"][value="teacher"]');
        if (radio) radio.checked = true;

        if (chkAnswers) { chkAnswers.checked = true; chkAnswers.disabled = false; }
        if (chkKeyTable) { chkKeyTable.checked = true; chkKeyTable.disabled = false; }
        if (chkExplains) { chkExplains.checked = true; chkExplains.disabled = false; }
        if (lblGrid) lblGrid.style.display = 'none';
        if (chkGrid) chkGrid.checked = false;
    }
}

function onDocxLayoutChange(layout) {
    setDocxLayoutUI(layout);
}

function setDocxLayoutUI(layout) {
    const cardCompact = document.getElementById('cardLayoutCompact');
    const cardStandard = document.getElementById('cardLayoutStandard');
    
    if (layout === 'compact') {
        if (cardCompact) {
            cardCompact.style.borderColor = '#16a34a';
            cardCompact.style.background = '#f0fdf4';
            const cTitle = cardCompact.querySelector('span');
            if (cTitle) cTitle.style.color = '#15803d';
        }
        if (cardStandard) {
            cardStandard.style.borderColor = '#e2e8f0';
            cardStandard.style.background = '#f8fafc';
            const sTitle = cardStandard.querySelector('span');
            if (sTitle) sTitle.style.color = '#334155';
        }
        const radio = document.querySelector('input[name="docxLayoutMode"][value="compact"]');
        if (radio) radio.checked = true;
    } else {
        if (cardStandard) {
            cardStandard.style.borderColor = '#16a34a';
            cardStandard.style.background = '#f0fdf4';
            const sTitle = cardStandard.querySelector('span');
            if (sTitle) sTitle.style.color = '#15803d';
        }
        if (cardCompact) {
            cardCompact.style.borderColor = '#e2e8f0';
            cardCompact.style.background = '#f8fafc';
            const cTitle = cardCompact.querySelector('span');
            if (cTitle) cTitle.style.color = '#334155';
        }
        const radio = document.querySelector('input[name="docxLayoutMode"][value="standard"]');
        if (radio) radio.checked = true;
    }
}

async function confirmDownloadDocx() {
    if (!currentExportQuizId) {
        closeExportDocxModal();
        return;
    }
    
    const audienceRadio = document.querySelector('input[name="docxAudience"]:checked');
    const audience = audienceRadio ? audienceRadio.value : 'teacher';
    
    const layoutRadio = document.querySelector('input[name="docxLayoutMode"]:checked');
    const layout = layoutRadio ? layoutRadio.value : 'compact';
    
    const optLayoutSelect = document.getElementById('docxOptionsLayout');
    const optionsLayout = optLayoutSelect ? optLayoutSelect.value : 'auto';
    
    const showAnswers = document.getElementById('docxShowAnswers')?.checked ?? (audience === 'teacher');
    const showKeyTable = document.getElementById('docxShowKeyTable')?.checked ?? (audience === 'teacher');
    const showExplains = document.getElementById('docxShowExplains')?.checked ?? (audience === 'teacher');
    const studentGrid = document.getElementById('docxStudentGrid')?.checked ?? false;
    
    const token = typeof authToken !== 'undefined' ? authToken : '';
    const url = `${API_BASE_URL}/api/teacher/export_docx/${encodeURIComponent(currentExportQuizId)}?teacher_token=${encodeURIComponent(token)}`
        + `&target_audience=${encodeURIComponent(audience)}`
        + `&layout_mode=${encodeURIComponent(layout)}`
        + `&options_layout=${encodeURIComponent(optionsLayout)}`
        + `&show_answers=${showAnswers}`
        + `&show_key_table=${showKeyTable}`
        + `&show_explains=${showExplains}`
        + `&include_student_answer_grid=${studentGrid}`;

    const btnSubmit = document.querySelector('#exportDocxModal .btn-primary');
    const originalBtnHtml = btnSubmit ? btnSubmit.innerHTML : '';
    if (btnSubmit) {
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = '<i class="ri-loader-4-line ri-spin"></i> Đang tạo file Word...';
    }

    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        let filename = `de_thi_${audience}.docx`;
        const disp = response.headers.get('content-disposition');
        if (disp && disp.includes('filename=')) {
            const m = disp.match(/filename=["']?([^"';]+)["']?/);
            if (m && m[1]) filename = m[1];
        }

        const blob = await response.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(blobUrl);

        if (typeof showToast === 'function') {
            showToast("Đã xuất file Word (.docx) thành công!", "success");
        }
        closeExportDocxModal();
    } catch (err) {
        console.warn("Lỗi fetch blob docx, fallback sang mở link trực tiếp:", err);
        window.open(url, '_blank');
        closeExportDocxModal();
    } finally {
        if (btnSubmit) {
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = originalBtnHtml;
        }
    }
}

// ========================================================
// BẢNG THỐNG KÊ ĐIỂM THI & QUẢN LÝ KẾT QUẢ HỌC SINH (KẾT HỢP ĐIỂM & GIÁM SÁT)
// ========================================================
let currentStatsQuizId = null;
let currentStatsQuizTitle = "";
let currentStatsData = null;
let currentStatsActiveSubTab = 'students';
let currentDetailStudent = null;
let currentDetailFilter = 'all';

async function openQuizStats(quizId, quizTitle, forceRefresh = false) {
    if (quizId && window.location.pathname !== `/giao-vien/de/${quizId}`) {
        history.pushState({ page: 'quiz_stats', quizId: quizId }, '', `/giao-vien/de/${quizId}`);
    }
    currentStatsQuizId = quizId;
    currentStatsQuizTitle = quizTitle || 'Thống kê đề thi';
    
    // Ẩn Dashboard giáo viên, mở Bảng thống kê điểm thi
    const teacherDash = document.getElementById('teacherDashboard');
    const statsDash = document.getElementById('quizStatsDashboard');
    if (!statsDash) return;
    
    if (teacherDash) teacherDash.style.display = 'none';
    statsDash.style.display = 'block';
    
    // Cập nhật tiêu đề & mã đề
    const titleEl = document.getElementById('quizStatsTitle');
    if (titleEl) titleEl.innerText = "Thống kê: " + currentStatsQuizTitle;
    
    const subTitleEl = document.getElementById('quizStatsSubtitle');
    if (subTitleEl) subTitleEl.innerHTML = `<i class="ri-file-list-3-line"></i> Mã đề: ${quizId}`;
    
    // Hiển thị trạng thái đang tải
    const loadingArea = document.getElementById('quizStatsLoading');
    const tabStudents = document.getElementById('statsTabContentStudents');
    const tabAnalytics = document.getElementById('statsTabContentAnalytics');
    
    if (loadingArea) {
        loadingArea.style.display = 'block';
        loadingArea.innerHTML = renderHntnInlineLoader('Đang tải dữ liệu điểm thi...', 'Hệ thống đang tổng hợp bài làm và phổ điểm...', 80);
    }
    if (tabStudents) tabStudents.style.display = 'none';
    if (tabAnalytics) tabAnalytics.style.display = 'none';
    
    try {
        let data = null;
        let lastErr = null;
        
        // 1. Cố gắng kết nối qua API_BASE_URL trước (Localhost hoặc Domain hiện tại)
        const primaryUrl = `${API_BASE_URL}/api/teacher/quiz_analytics/${quizId}?teacher_token=${encodeURIComponent(authToken || '')}${forceRefresh ? '&force_refresh=true' : ''}`;
        try {
            const res = await fetch(primaryUrl);
            if (res.ok) {
                data = await res.json();
            } else {
                let errJson = null;
                try { errJson = await res.json(); } catch(e) {}
                lastErr = new Error(errJson?.detail || `Máy chủ phản hồi mã lỗi ${res.status}`);
            }
        } catch(fetchErr) {
            lastErr = fetchErr;
        }

        // 2. Tự động Fallback sang Máy chủ Production Cloud nếu Localhost / URL hiện tại không phản hồi
        if ((!data || data.status !== 'success') && API_BASE_URL !== PROD_BACKEND_URL) {
            try {
                console.warn("Máy chủ hiện tại không phản hồi, tự động chuyển sang Cloud Backend:", PROD_BACKEND_URL);
                const fallbackUrl = `${PROD_BACKEND_URL}/api/teacher/quiz_analytics/${quizId}?teacher_token=${encodeURIComponent(authToken || '')}${forceRefresh ? '&force_refresh=true' : ''}`;
                const resFallback = await fetch(fallbackUrl);
                if (resFallback.ok) {
                    data = await resFallback.json();
                    lastErr = null;
                }
            } catch(fbErr) {
                // Giữ lỗi cuối cùng để thông báo nếu cả 2 đều thất bại
            }
        }
        
        if (loadingArea) loadingArea.style.display = 'none';
        
        if (!data || data.status !== 'success') {
            if (tabStudents) {
                tabStudents.style.display = 'block';
                const errorDetail = lastErr ? lastErr.message : (data?.detail || 'Không thể kết nối máy chủ.');
                tabStudents.innerHTML = `
                    <div style="text-align:center; padding: 40px 20px; color: var(--danger);">
                        <i class="ri-server-line" style="font-size: 2.8rem; color: #ef4444;"></i>
                        <h4 style="margin: 12px 0 6px 0; font-size: 1.15rem; color: var(--text-dark);">Chưa nhận được phản hồi từ máy chủ Backend</h4>
                        <p style="color: var(--text-muted); max-width: 480px; margin: 0 auto 16px auto; font-size: 0.92rem; line-height: 1.5;">
                            Mạng Internet của bạn vẫn hoạt động bình thường. Tuy nhiên máy chủ Backend chưa được khởi động hoặc đang ở trạng thái ngủ (Cold Start).
                            <br><small style="color: #94a3b8;">(${escapeHtml(errorDetail)})</small>
                        </p>
                        <button class="btn-primary" style="padding: 9px 22px; font-weight: 600;" onclick="openQuizStats('${quizId}', '${(quizTitle || '').replace(/'/g, "\\'")}', true)">
                            <i class="ri-refresh-line"></i> Bấm để thử lại ngay
                        </button>
                    </div>
                `;
            }
            return;
        }
        
        currentStatsData = data;
        
        // Cập nhật thời điểm tải mới nhất
        const timeEl = document.getElementById('quizStatsUpdatedTime');
        const nowStr = new Date().toLocaleTimeString('vi-VN');
        if (timeEl) timeEl.innerHTML = `<i class="ri-time-line"></i> Cập nhật lúc: ${nowStr}`;
        
        // Cập nhật các thẻ KPI tổng quan
        const kpiSubs = document.getElementById('kpiTotalSubs');
        const kpiAvg = document.getElementById('kpiAvgScore');
        const kpiMax = document.getElementById('kpiMaxScore');
        const kpiMin = document.getElementById('kpiMinScore');
        
        if (kpiSubs) kpiSubs.innerText = data.total_submissions || 0;
        if (kpiAvg) kpiAvg.innerText = data.total_submissions > 0 ? (data.average_score || 0) + 'đ' : '--';
        if (kpiMax) kpiMax.innerText = data.total_submissions > 0 ? (data.max_score || 0) + 'đ' : '--';
        if (kpiMin) kpiMin.innerText = data.total_submissions > 0 ? (data.min_score || 0) + 'đ' : '--';
        
        // Cập nhật số lượng học sinh trên Tab Header
        const tabStudentCountEl = document.getElementById('statsTabStudentCount');
        if (tabStudentCountEl) tabStudentCountEl.innerText = data.total_submissions || 0;
        
        // Render nội dung cả 2 tab
        renderStatsStudentsTab();
        renderStatsAnalyticsTab();
        
        // Chuyển sang sub-tab đang chọn
        switchStatsSubTab(currentStatsActiveSubTab || 'students');
        
    } catch(err) {
        console.error("openQuizStats error:", err);
        if (loadingArea) loadingArea.style.display = 'none';
        if (tabStudents) {
            tabStudents.style.display = 'block';
            tabStudents.innerHTML = `
                <div style="text-align:center; padding: 40px 20px; color: var(--danger);">
                    <i class="ri-server-line" style="font-size: 2.8rem; color: #f59e0b;"></i>
                    <h4 style="margin: 12px 0 6px 0; font-size: 1.15rem; color: var(--text-dark);">Dịch vụ máy chủ chưa phản hồi</h4>
                    <p style="color: var(--text-muted); max-width: 480px; margin: 0 auto 16px auto; font-size: 0.92rem; line-height: 1.5;">
                        Mạng Internet của bạn vẫn hoạt động bình thường. Máy chủ Backend đang được khởi động lại hoặc chưa sẵn sàng. Vui lòng thử lại sau vài giây.
                        <br><small style="color: #94a3b8;">(${escapeHtml(err.message || 'Lỗi kết nối')})</small>
                    </p>
                    <button class="btn-primary" style="padding: 9px 22px; font-weight: 600;" onclick="openQuizStats('${quizId}', '${(quizTitle || '').replace(/'/g, "\\'")}', true)">
                        <i class="ri-refresh-line"></i> Bấm để thử lại ngay
                    </button>
                </div>
            `;
        }
    }
}

function switchStatsSubTab(tabName) {
    currentStatsActiveSubTab = tabName;
    const tabStudentsBtn = document.getElementById('tabBtnStatsStudents');
    const tabAnalyticsBtn = document.getElementById('tabBtnStatsAnalytics');
    const tabStudentsContent = document.getElementById('statsTabContentStudents');
    const tabAnalyticsContent = document.getElementById('statsTabContentAnalytics');
    
    if (tabName === 'analytics') {
        if (tabStudentsBtn) tabStudentsBtn.classList.remove('active');
        if (tabAnalyticsBtn) tabAnalyticsBtn.classList.add('active');
        if (tabStudentsContent) tabStudentsContent.style.display = 'none';
        if (tabAnalyticsContent) tabAnalyticsContent.style.display = 'block';
    } else {
        if (tabStudentsBtn) tabStudentsBtn.classList.add('active');
        if (tabAnalyticsBtn) tabAnalyticsBtn.classList.remove('active');
        if (tabStudentsContent) tabStudentsContent.style.display = 'block';
        if (tabAnalyticsContent) tabAnalyticsContent.style.display = 'none';
    }
}

function closeQuizStats() {
    const statsDash = document.getElementById('quizStatsDashboard');
    const teacherDash = document.getElementById('teacherDashboard');
    if (statsDash) statsDash.style.display = 'none';
    if (teacherDash) teacherDash.style.display = 'block';
    currentStatsQuizId = null;
    if (window.location.pathname.startsWith('/giao-vien/de/')) {
        history.pushState({ page: 'teacher' }, '', '/giao-vien');
    }
}

function refreshQuizStatsNow() {
    if (!currentStatsQuizId) return;
    const btn = document.getElementById('btnRefreshStats');
    if (btn) {
        btn.innerHTML = `<i class="ri-loader-4-line ri-spin"></i> <span>Đang làm mới...</span>`;
        btn.disabled = true;
    }
    openQuizStats(currentStatsQuizId, currentStatsQuizTitle, true).finally(() => {
        if (btn) {
            btn.innerHTML = `<i class="ri-refresh-line"></i> <span>Làm mới</span>`;
            btn.disabled = false;
        }
    });
}

function renderStatsStudentsTab() {
    const tbody = document.getElementById('statsStudentsTableBody');
    if (!tbody || !currentStatsData) return;
    
    const students = currentStatsData.students || [];
    if (students.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 40px 20px; color: var(--text-muted);">
                    <div style="font-size: 2.2rem; color: #cbd5e1; margin-bottom: 8px;"><i class="ri-user-unfollow-line"></i></div>
                    <div style="font-weight: 700; font-size: 1.05rem; color: var(--text-dark);">Chưa có học sinh nào nộp bài</div>
                    <div style="font-size: 0.88rem; margin-top: 4px;">Chia sẻ link đề thi hoặc mã đề cho học sinh để bắt đầu nhận bài làm.</div>
                </td>
            </tr>
        `;
        return;
    }
    
    filterStatsStudentsTable();
}

function filterStatsStudentsTable() {
    const tbody = document.getElementById('statsStudentsTableBody');
    if (!tbody || !currentStatsData) return;
    
    const students = currentStatsData.students || [];
    const searchVal = (document.getElementById('statsStudentSearchInput')?.value || '').toLowerCase().trim();
    
    let filtered = students.filter(s => {
        if (!searchVal) return true;
        return (s.student_name || '').toLowerCase().includes(searchVal);
    });
    
    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 24px; color: var(--text-muted);">
                    Không tìm thấy học sinh nào khớp với từ khóa "<strong>${escapeHtml(searchVal)}</strong>"
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = filtered.map((s, index) => {
        const origIndex = students.indexOf(s);
        const timeStr = (s.time_elapsed && s.time_elapsed > 0) ? formatTime(s.time_elapsed) : '--';
        const scoreBadge = `<span style="display: inline-block; padding: 4px 10px; border-radius: 8px; font-weight: 800; font-size: 1.05rem; background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0;">${s.scaled_score}đ</span>`;
        const correctStr = `<span style="font-weight: 700; color: #1e293b;">${s.raw_score} / ${s.total_questions}</span>`;
        const dateStr = s.submitted_at || '--';
        
        return `
            <tr style="border-bottom: 1px solid var(--border); cursor: pointer; transition: background 0.15s;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background='transparent'" onclick="showStudentStatsDetail(${origIndex})">
                <td style="padding: 12px; text-align: center; font-weight: 700; color: var(--text-muted);">${index + 1}</td>
                <td style="padding: 12px; font-weight: 700; color: var(--text-dark);">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div style="width: 32px; height: 32px; border-radius: 50%; background: #e0f2fe; color: #0284c7; display: flex; align-items: center; justify-content: center; font-size: 0.85rem; font-weight: 700; flex-shrink: 0;">
                            ${(s.student_name || 'H').charAt(0).toUpperCase()}
                        </div>
                        <div>
                            <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                                <span>${escapeHtml(s.student_name)}</span>
                                ${s.is_guest 
                                    ? `<span style="font-size: 0.72rem; font-weight: 600; background: #fef3c7; color: #b45309; padding: 2px 7px; border-radius: 6px; border: 1px solid #fde68a;" title="Thí sinh tự do (Tự động xóa sau 24h)"><i class="ri-time-line"></i> Tự do (24h)</span>` 
                                    : `<span style="font-size: 0.72rem; font-weight: 600; background: #ecfdf5; color: #047857; padding: 2px 7px; border-radius: 6px; border: 1px solid #a7f3d0;" title="Học sinh có tài khoản chính thức"><i class="ri-shield-user-line"></i> Chính thức</span>`}
                                ${((s.tab_switch_count && s.tab_switch_count > 0) || (s.cheat_flags && s.cheat_flags.length > 0))
                                    ? `<span style="font-size: 0.72rem; font-weight: 700; background: #fee2e2; color: #b91c1c; padding: 2px 7px; border-radius: 6px; border: 1px solid #fca5a5;" title="Ghi nhận rời màn hình thi ${s.tab_switch_count || 1} lần"><i class="ri-alarm-warning-fill"></i> Rời tab ${s.tab_switch_count || 1} lần</span>`
                                    : ''}
                            </div>
                            <div style="font-size: 0.78rem; font-weight: normal; color: var(--text-muted); margin-top: 2px;">
                                <i class="ri-calendar-line"></i> ${dateStr}
                            </div>
                        </div>
                    </div>
                </td>
                <td style="padding: 12px; text-align: center;">${scoreBadge}</td>
                <td style="padding: 12px; text-align: center;">${correctStr}</td>
                <td style="padding: 12px; text-align: center; color: #475569; font-weight: 600;">${timeStr}</td>
                <td style="padding: 12px; text-align: center;" onclick="event.stopPropagation()">
                    <button class="btn-outline" style="padding: 5px 12px; border-radius: 6px; font-size: 0.82rem; font-weight: 600; color: var(--primary); border-color: #cbd5e1;" onclick="showStudentStatsDetail(${origIndex})">
                        <i class="ri-eye-line"></i> Chi tiết
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function renderStatsAnalyticsTab() {
    const container = document.getElementById('statsAnalyticsContainer');
    if (!container || !currentStatsData) return;
    
    const data = currentStatsData;
    if (data.total_submissions === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 40px 20px; color: var(--text-muted);">
                <i class="ri-bar-chart-2-line" style="font-size: 2.5rem; color: #cbd5e1;"></i>
                <h4 style="margin: 10px 0; color: var(--text-dark);">Chưa có dữ liệu phổ điểm</h4>
                <p>Cần ít nhất 1 bài nộp để tổng hợp biểu đồ phổ điểm và phân tích câu hỏi khó.</p>
            </div>
        `;
        return;
    }
    
    // 1. Phổ điểm
    let bandsHtml = "";
    const bands = data.score_bands || {};
    const maxBandVal = Math.max(...Object.values(bands), 1);
    
    for (const [band, count] of Object.entries(bands)) {
        const pct = Math.round((count / data.total_submissions) * 100);
        const barWidth = Math.round((count / maxBandVal) * 100);
        bandsHtml += `
            <div style="margin-bottom: 12px;">
                <div style="display:flex; justify-content:space-between; font-size:0.88rem; margin-bottom:4px;">
                    <span style="font-weight: 600; color: #334155;">Thang điểm <b>${band}</b></span>
                    <span style="color: #64748b;"><b>${count}</b> học sinh (${pct}%)</span>
                </div>
                <div style="background:#e2e8f0; border-radius:6px; height:14px; overflow:hidden;">
                    <div style="background: linear-gradient(90deg, #1976d2 0%, #3b82f6 100%); height:100%; width:${barWidth}%; border-radius:6px; transition:width 0.5s;"></div>
                </div>
            </div>
        `;
    }
    
    // 2. Các câu hỏi học sinh hay làm sai nhất
    let hardestHtml = "";
    if (data.hardest_questions && data.hardest_questions.length > 0) {
        hardestHtml = `
            <div style="margin-top: 24px;">
                <h4 style="color: #b91c1c; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                    <i class="ri-alarm-warning-line"></i> Top câu hỏi học sinh hay làm sai nhất:
                </h4>
                <div style="display:flex; flex-direction:column; gap:10px;">
        `;
        data.hardest_questions.forEach(hq => {
            hardestHtml += `
                <div style="background:#fef2f2; border-left:4px solid #ef4444; padding:12px 14px; border-radius:8px; font-size:0.9rem;">
                    <div style="display:flex; justify-content:space-between; align-items: center; margin-bottom:6px; flex-wrap: wrap; gap: 6px;">
                        <span style="font-weight: 800; color: #991b1b; font-size: 0.95rem;">Câu ${hq.question_index}</span>
                        <span style="color:#dc2626; font-weight:700; background: #fee2e2; padding: 2px 8px; border-radius: 6px;">
                            Tỷ lệ làm đúng: ${hq.accuracy_rate}% (${hq.correct_count}/${data.total_submissions})
                        </span>
                    </div>
                    <div style="color:#334155; line-height: 1.4;">${escapeHtml(hq.question_preview)}</div>
                </div>
            `;
        });
        hardestHtml += `</div></div>`;
    }
    
    // 3. Toàn bộ câu hỏi
    let allQStatsHtml = "";
    if (data.question_stats && data.question_stats.length > 0) {
        allQStatsHtml = `
            <div style="margin-top: 24px;">
                <h4 style="color: #1e293b; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                    <i class="ri-list-check-2"></i> Thống kê tỷ lệ đúng toàn bộ đề thi:
                </h4>
                <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 8px;">
        `;
        data.question_stats.forEach(qs => {
            const isGood = qs.accuracy_rate >= 70;
            const isMed = qs.accuracy_rate >= 40 && qs.accuracy_rate < 70;
            const bg = isGood ? '#f0fdf4' : (isMed ? '#fefce8' : '#fef2f2');
            const border = isGood ? '#bbf7d0' : (isMed ? '#fef08a' : '#fecaca');
            const color = isGood ? '#15803d' : (isMed ? '#a16207' : '#b91c1c');
            
            allQStatsHtml += `
                <div style="background: ${bg}; border: 1px solid ${border}; border-radius: 8px; padding: 8px; text-align: center;">
                    <div style="font-weight: 700; font-size: 0.85rem; color: #1e293b;">Câu ${qs.question_index}</div>
                    <div style="font-weight: 800; font-size: 0.95rem; color: ${color}; margin-top: 2px;">${qs.accuracy_rate}%</div>
                </div>
            `;
        });
        allQStatsHtml += `</div></div>`;
    }
    
    container.innerHTML = `
        <div style="background:#ffffff; border:1px solid var(--border); padding:20px; border-radius:12px; margin-bottom:20px;">
            <h4 style="margin-top:0; margin-bottom:16px; color:var(--text-dark); display: flex; align-items: center; gap: 8px;">
                <i class="ri-line-chart-line" style="color: var(--primary);"></i> Phân bố phổ điểm số (Thang 10)
            </h4>
            ${bandsHtml}
        </div>
        ${hardestHtml}
        ${allQStatsHtml}
    `;
    
    if (typeof renderMath === 'function') renderMath();
}

function showStudentStatsDetail(index) {
    if (!currentStatsData || !currentStatsData.students || !currentStatsData.students[index]) return;
    
    currentDetailStudent = currentStatsData.students[index];
    currentDetailFilter = 'all';
    
    const s = currentDetailStudent;
    const modal = document.getElementById('studentDetailsModal');
    const headerName = document.getElementById('studentDetailsHeaderName');
    const headerSub = document.getElementById('studentDetailsHeaderSub');
    if (!modal) return;
    
    if (headerName) headerName.innerText = s.student_name || 'Học sinh';
    const guestBadge = s.is_guest 
        ? ` • <span style="background: #fef3c7; color: #b45309; font-weight: 700; font-size: 0.75rem; padding: 2px 6px; border-radius: 4px; border: 1px solid #fde68a;"><i class="ri-time-line"></i> Thí sinh tự do (Tự xóa sau 24h)</span>` 
        : ` • <span style="background: #ecfdf5; color: #047857; font-weight: 700; font-size: 0.75rem; padding: 2px 6px; border-radius: 4px; border: 1px solid #a7f3d0;"><i class="ri-shield-user-line"></i> Học sinh chính thức</span>`;
    const cheatBadge = ((s.tab_switch_count && s.tab_switch_count > 0) || (s.cheat_flags && s.cheat_flags.length > 0))
        ? ` • <span style="background: #fee2e2; color: #b91c1c; font-weight: 700; font-size: 0.75rem; padding: 2px 6px; border-radius: 4px; border: 1px solid #fca5a5;"><i class="ri-alarm-warning-fill"></i> Rời tab thi ${s.tab_switch_count || 1} lần</span>`
        : '';
    if (headerSub) headerSub.innerHTML = `Nộp bài lúc: <b>${s.submitted_at || '--'}</b> • Thời gian làm: <b>${formatTime(s.time_elapsed)}</b>${guestBadge}${cheatBadge}`;
    
    modal.style.display = 'flex';
    renderStudentDetailBody();
}

function closeStudentDetailsModal() {
    const modal = document.getElementById('studentDetailsModal');
    if (modal) modal.style.display = 'none';
}

function setStudentDetailFilter(filter) {
    currentDetailFilter = filter;
    renderStudentDetailBody();
}

function renderStudentDetailBody() {
    const body = document.getElementById('studentDetailsBody');
    if (!body || !currentDetailStudent || !currentStatsData) return;
    
    const s = currentDetailStudent;
    const questions = currentStatsData.questions_brief || [];
    const userAnswers = s.answers || {};
    const resultsList = s.results || [];
    
    // Map backend results if available
    const resultsMap = {};
    if (Array.isArray(resultsList)) {
        resultsList.forEach(item => {
            if (item && item.question_index !== undefined) {
                resultsMap[item.question_index] = item;
            }
        });
    }
    
    let correctCount = 0;
    let wrongCount = 0;
    let skippedCount = 0;
    
    // Đánh giá từng câu hỏi
    const evaluatedQuestions = questions.map((q, qIndex) => {
        const qType = q.type || 'mcq';
        const serverItem = resultsMap[qIndex] || resultsMap[String(qIndex)];
        let userAnswer = userAnswers[qIndex] !== undefined ? userAnswers[qIndex] : userAnswers[String(qIndex)];
        let correctAnswer = (serverItem && serverItem.correct_answer !== undefined && serverItem.correct_answer !== null && serverItem.correct_answer !== '')
            ? serverItem.correct_answer 
            : q.correct_answer;
        let explain = (serverItem && serverItem.explain) ? serverItem.explain : (q.explain || '');
        
        let status = 'wrong';
        let earnedScore = 0;
        
        if (serverItem) {
            earnedScore = serverItem.earned !== undefined ? serverItem.earned : (serverItem.is_correct ? 1.0 : 0.0);
            if (serverItem.is_correct) {
                status = 'correct';
            } else if (userAnswer === null || userAnswer === undefined || userAnswer === '' || (typeof userAnswer === 'object' && Object.keys(userAnswer).length === 0)) {
                status = 'skipped';
            } else {
                status = 'wrong';
            }
        } else {
            // Client evaluation fallback
            if (qType === 'true_false') {
                const correctMap = (typeof correctAnswer === 'object' && correctAnswer) ? correctAnswer : {};
                const userMap = (typeof userAnswer === 'object' && userAnswer) ? userAnswer : {};
                let matchCount = 0;
                let userAnswersGiven = 0;
                ['a', 'b', 'c', 'd'].forEach(char => {
                    if (userMap[char] !== undefined) userAnswersGiven++;
                    if (userMap[char] !== undefined && Boolean(userMap[char]) === Boolean(correctMap[char])) {
                        matchCount++;
                    }
                });
                const scale = [0.0, 0.1, 0.25, 0.5, 1.0];
                earnedScore = scale[matchCount] !== undefined ? scale[matchCount] : 0.0;
                if (userAnswersGiven === 0) status = 'skipped';
                else if (matchCount === 4) status = 'correct';
                else status = 'wrong';
            } else if (qType === 'short_answer') {
                let uStr = String(userAnswer || '').trim();
                let cStr = String(correctAnswer || '').trim();
                if (!uStr) {
                    status = 'skipped';
                } else if (evaluateShortAnswerJS(uStr, cStr)) {
                    status = 'correct';
                    earnedScore = 1.0;
                } else {
                    status = 'wrong';
                }
            } else {
                // MCQ
                if (userAnswer === null || userAnswer === undefined || userAnswer === '') {
                    status = 'skipped';
                } else {
                    let oIndex = 0;
                    if (q.options && q.options.length > 0) {
                        oIndex = q.options.indexOf(userAnswer);
                        if (oIndex === -1) oIndex = 0;
                    }
                    if (typeof matchOptionToTarget === 'function' && matchOptionToTarget(userAnswer, oIndex, correctAnswer)) {
                        status = 'correct';
                        earnedScore = 1.0;
                    } else {
                        status = 'wrong';
                    }
                }
            }
        }
        
        if (status === 'correct') correctCount++;
        else if (status === 'skipped') skippedCount++;
        else wrongCount++;
        
        return {
            q,
            qIndex,
            qType,
            userAnswer,
            correctAnswer,
            explain,
            status,
            earnedScore,
            serverItem
        };
    });
    
    // Lọc theo bộ lọc câu hỏi
    const filteredQuestions = evaluatedQuestions.filter(item => {
        if (currentDetailFilter === 'correct') return item.status === 'correct';
        if (currentDetailFilter === 'wrong') return item.status === 'wrong';
        if (currentDetailFilter === 'skipped') return item.status === 'skipped';
        return true;
    });
    
    let html = `
        <div style="background: linear-gradient(135deg, #f0fdf4 0%, #e0f2fe 100%); border: 1.5px solid #bae6fd; border-radius: 14px; padding: 18px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                <div>
                    <div style="font-size: 0.82rem; color: #64748b; font-weight: 600;">KẾT QUẢ BÀI THI</div>
                    <div style="display: flex; align-items: baseline; gap: 8px; margin-top: 2px;">
                        <span style="font-size: 2rem; font-weight: 800; color: #16a34a;">${s.scaled_score}đ</span>
                        <span style="font-size: 1.05rem; font-weight: 700; color: #475569;">/ 10 điểm</span>
                        <span style="font-size: 0.95rem; color: #64748b;">(Đúng ${s.raw_score}/${s.total_questions} câu)</span>
                    </div>
                </div>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <div style="background: #ffffff; padding: 8px 14px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
                        <div style="font-size: 0.75rem; color: #64748b;">Thời gian làm</div>
                        <div style="font-weight: 700; color: #0284c7; font-size: 1.05rem;">${s.time_elapsed > 0 ? formatTime(s.time_elapsed) : '--'}</div>
                    </div>
                    <div style="background: #ffffff; padding: 8px 14px; border-radius: 8px; border: 1px solid #cbd5e1; text-align: center;">
                        <div style="font-size: 0.75rem; color: #64748b;">Tỷ lệ làm đúng</div>
                        <div style="font-weight: 700; color: #15803d; font-size: 1.05rem;">${Math.round((s.scaled_score / 10) * 100)}%</div>
                    </div>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 14px;">
                <div style="background: #dcfce7; border: 1px solid #bbf7d0; padding: 8px; border-radius: 8px; text-align: center;">
                    <span style="font-size: 0.8rem; color: #166534; font-weight: 600;"><i class="ri-checkbox-circle-fill"></i> Đúng:</span>
                    <strong style="color: #15803d; margin-left: 4px;">${correctCount} câu</strong>
                </div>
                <div style="background: #fee2e2; border: 1px solid #fecaca; padding: 8px; border-radius: 8px; text-align: center;">
                    <span style="font-size: 0.8rem; color: #991b1b; font-weight: 600;"><i class="ri-close-circle-fill"></i> Sai:</span>
                    <strong style="color: #dc2626; margin-left: 4px;">${wrongCount} câu</strong>
                </div>
                <div style="background: #f1f5f9; border: 1px solid #e2e8f0; padding: 8px; border-radius: 8px; text-align: center;">
                    <span style="font-size: 0.8rem; color: #475569; font-weight: 600;"><i class="ri-question-fill"></i> Chưa làm:</span>
                    <strong style="color: #64748b; margin-left: 4px;">${skippedCount} câu</strong>
                </div>
            </div>
        </div>
        
        <!-- Filter Bar -->
        <div style="display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap;">
            <button class="azota-filter-tab ${currentDetailFilter === 'all' ? 'active' : ''}" onclick="setStudentDetailFilter('all')" style="padding: 6px 14px; font-size: 0.85rem; border-radius: 20px; font-weight: 600; cursor: pointer;">
                Tất cả (${questions.length})
            </button>
            <button class="azota-filter-tab tab-wrong ${currentDetailFilter === 'wrong' ? 'active' : ''}" onclick="setStudentDetailFilter('wrong')" style="padding: 6px 14px; font-size: 0.85rem; border-radius: 20px; font-weight: 600; cursor: pointer;">
                <i class="ri-close-circle-fill" style="color: #ef4444;"></i> Câu sai (${wrongCount})
            </button>
            <button class="azota-filter-tab tab-correct ${currentDetailFilter === 'correct' ? 'active' : ''}" onclick="setStudentDetailFilter('correct')" style="padding: 6px 14px; font-size: 0.85rem; border-radius: 20px; font-weight: 600; cursor: pointer;">
                <i class="ri-checkbox-circle-fill" style="color: #10b981;"></i> Câu đúng (${correctCount})
            </button>
        </div>
        
        <!-- Question List -->
        <div style="display: flex; flex-direction: column; gap: 14px;">
    `;
    
    if (filteredQuestions.length === 0) {
        html += `
            <div style="text-align: center; padding: 30px; color: var(--text-muted); background: #f8fafc; border-radius: 12px; border: 1px dashed var(--border);">
                Không có câu hỏi nào trong mục lọc này.
            </div>
        `;
    } else {
        filteredQuestions.forEach(item => {
            const { q, qIndex, qType, userAnswer, correctAnswer, explain, status, earnedScore, serverItem } = item;
            
            let statusBadge = '';
            let cardBorder = '#e2e8f0';
            if (status === 'correct') {
                statusBadge = `<span style="background: #dcfce7; color: #15803d; font-weight: 700; font-size: 0.78rem; padding: 3px 8px; border-radius: 6px; border: 1px solid #bbf7d0;"><i class="ri-checkbox-circle-fill"></i> ĐÚNG (+${earnedScore}đ)</span>`;
                cardBorder = '#bbf7d0';
            } else if (status === 'skipped') {
                statusBadge = `<span style="background: #fef3c7; color: #b45309; font-weight: 700; font-size: 0.78rem; padding: 3px 8px; border-radius: 6px; border: 1px solid #fde68a;"><i class="ri-question-fill"></i> CHƯA LÀM (0đ)</span>`;
                cardBorder = '#fde68a';
            } else {
                statusBadge = `<span style="background: #fee2e2; color: #b91c1c; font-weight: 700; font-size: 0.78rem; padding: 3px 8px; border-radius: 6px; border: 1px solid #fecaca;"><i class="ri-close-circle-fill"></i> SAI (0đ)</span>`;
                cardBorder = '#fecaca';
            }
            
            let typeBadge = '';
            if (qType === 'true_false') typeBadge = '<span style="background: #e0f2fe; color: #0369a1; padding: 2px 7px; border-radius: 5px; font-size: 0.75rem; font-weight: 600;">Đúng/Sai</span>';
            else if (qType === 'short_answer') typeBadge = '<span style="background: #fef3c7; color: #92400e; padding: 2px 7px; border-radius: 5px; font-size: 0.75rem; font-weight: 600;">Trả lời ngắn</span>';
            else typeBadge = '<span style="background: #f1f5f9; color: #475569; padding: 2px 7px; border-radius: 5px; font-size: 0.75rem; font-weight: 600;">Trắc nghiệm</span>';
            
            let groupTitleHtml = q.group_title ? `<div style="background: #fef9c3; padding: 6px 10px; border-radius: 6px; margin-bottom: 8px; font-size: 0.85rem; font-weight: 600; color: #854d0e;">${formatRichContent(q.group_title)}</div>` : '';
            
            // Làm sạch tiền tố "Câu X:" nếu câu hỏi đã có sẵn
            let cleanQ = (q.question || '').replace(/^(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])\s*/i, '');
            let imageHtml = '';
            if (q.image && String(q.image).trim()) {
                let imgUrl = String(q.image).trim();
                // Chỉ hiển thị ảnh riêng nếu trong nội dung câu hỏi chưa chứa đường dẫn ảnh này
                if (!cleanQ.includes(imgUrl)) {
                    imageHtml = `<div style="margin: 10px 0; text-align: center;"><img src="${escapeHtml(imgUrl)}" style="max-width: 100%; max-height: 320px; border-radius: 8px; border: 1px solid #e2e8f0; display: inline-block;"></div>`;
                }
            }
            
            let answerBodyHtml = '';
            
            if (qType === 'mcq') {
                const options = q.options || [];
                
                // 1. Xác định đáp án đúng trong danh sách options
                let correctIndex = -1;
                options.forEach((opt, oIdx) => {
                    if (matchOptionToTarget(opt, oIdx, correctAnswer)) {
                        correctIndex = oIdx;
                    }
                });

                // 2. Xác định duy nhất 1 phương án học sinh đã chọn (chống lỗi hiển thị trùng lặp khi xáo trộn đề)
                let userPickIndex = -1;
                if (userAnswer !== null && userAnswer !== undefined && userAnswer !== '') {
                    options.forEach((opt, oIdx) => {
                        if (matchOptionToTarget(opt, oIdx, userAnswer)) {
                            userPickIndex = oIdx;
                        }
                    });
                }

                // Chốt chặn an toàn: nếu status là 'correct'
                if (status === 'correct') {
                    if (correctIndex === -1 && userPickIndex !== -1) correctIndex = userPickIndex;
                    if (userPickIndex === -1 && correctIndex !== -1) userPickIndex = correctIndex;
                }

                answerBodyHtml = `<div style="display: flex; flex-direction: column; gap: 6px; margin-top: 10px;">`;
                options.forEach((opt, oIdx) => {
                    const char = String.fromCharCode(65 + oIdx);
                    let isThisCorrect = (oIdx === correctIndex);
                    const isThisUserPick = (oIdx === userPickIndex);
                    if (status === 'correct' && isThisUserPick) {
                        isThisCorrect = true;
                    }
                    
                    let optBg = '#ffffff';
                    let optBorder = '#e2e8f0';
                    let optColor = '#334155';
                    let badgeHtml = '';
                    
                    if (isThisCorrect && isThisUserPick) {
                        optBg = '#f0fdf4';
                        optBorder = '#16a34a';
                        optColor = '#14532d';
                        badgeHtml = `<span style="margin-left: auto; background: #dcfce7; color: #15803d; padding: 2px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 700;"><i class="ri-check-double-line"></i> Học sinh chọn đúng</span>`;
                    } else if (isThisCorrect) {
                        optBg = '#f0fdf4';
                        optBorder = '#16a34a';
                        optColor = '#14532d';
                        badgeHtml = `<span style="margin-left: auto; background: #dcfce7; color: #15803d; padding: 2px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 700;"><i class="ri-check-line"></i> Đáp án đúng</span>`;
                    } else if (isThisUserPick) {
                        optBg = '#fef2f2';
                        optBorder = '#ef4444';
                        optColor = '#7f1d1d';
                        badgeHtml = `<span style="margin-left: auto; background: #fee2e2; color: #b91c1c; padding: 2px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 700;"><i class="ri-close-line"></i> Học sinh đã chọn</span>`;
                    }
                    
                    const optText = String(opt || '').replace(/^[A-F][\.\:\)]\s*/i, '');
                    answerBodyHtml += `
                        <div style="display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-radius: 8px; border: 1.5px solid ${optBorder}; background: ${optBg}; color: ${optColor}; font-size: 0.9rem;">
                            <div style="width: 24px; height: 24px; border-radius: 6px; background: ${isThisCorrect ? '#16a34a' : (isThisUserPick ? '#ef4444' : '#e2e8f0')}; color: ${isThisCorrect || isThisUserPick ? '#ffffff' : '#475569'}; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.8rem; flex-shrink: 0;">
                                ${char}
                            </div>
                            <div style="flex: 1; line-height: 1.4;">${formatRichContent(optText)}</div>
                            ${badgeHtml}
                        </div>
                    `;
                });
                answerBodyHtml += `</div>`;
            } else if (qType === 'true_false') {
                const userMap = (typeof userAnswer === 'object' && userAnswer) ? userAnswer : {};
                const correctMap = (typeof correctAnswer === 'object' && correctAnswer) ? correctAnswer : {};
                const options = q.options || ['a) Ý 1', 'b) Ý 2', 'c) Ý 3', 'd) Ý 4'];
                
                answerBodyHtml = `
                    <div style="margin-top: 10px; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden;">
                        <table style="width: 100%; border-collapse: collapse; font-size: 0.88rem;">
                            <thead>
                                <tr style="background: #f8fafc; border-bottom: 1px solid #e2e8f0; color: #475569;">
                                    <th style="padding: 8px 10px; text-align: left;">Ý kiến / Mệnh đề</th>
                                    <th style="padding: 8px 10px; text-align: center; width: 100px;">Học sinh chọn</th>
                                    <th style="padding: 8px 10px; text-align: center; width: 90px;">Đáp án đúng</th>
                                    <th style="padding: 8px 10px; text-align: center; width: 60px;">Kết quả</th>
                                </tr>
                            </thead>
                            <tbody>
                `;
                ['a', 'b', 'c', 'd'].forEach((char, cIdx) => {
                    const optText = options[cIdx] ? String(options[cIdx]).replace(/^[a-d][\)\.\:\s]+/i, '') : `Ý ${char.toUpperCase()}`;
                    const uVal = userMap[char];
                    const cVal = correctMap[char];
                    const uText = uVal === true || String(uVal).toLowerCase() === 'true' || String(uVal) === 'Đúng' ? 'Đúng' : (uVal === false || String(uVal).toLowerCase() === 'false' || String(uVal) === 'Sai' ? 'Sai' : '--');
                    const cText = cVal === true || String(cVal).toLowerCase() === 'true' || String(cVal) === 'Đúng' ? 'Đúng' : 'Sai';
                    const isMatch = uVal !== undefined && (Boolean(uVal) === Boolean(cVal));
                    
                    answerBodyHtml += `
                        <tr style="border-bottom: 1px solid #f1f5f9;">
                            <td style="padding: 8px 10px;"><b>${char})</b> ${formatRichContent(optText)}</td>
                            <td style="padding: 8px 10px; text-align: center; font-weight: 600; color: ${uText === 'Đúng' ? '#0369a1' : (uText === 'Sai' ? '#b45309' : '#94a3b8')};">${uText}</td>
                            <td style="padding: 8px 10px; text-align: center; font-weight: 700; color: #15803d;">${cText}</td>
                            <td style="padding: 8px 10px; text-align: center;">${isMatch ? '<i class="ri-check-line" style="color:#16a34a; font-weight:bold;"></i>' : '<i class="ri-close-line" style="color:#ef4444; font-weight:bold;"></i>'}</td>
                        </tr>
                    `;
                });
                answerBodyHtml += `</tbody></table></div>`;
            } else {
                // Short answer
                const uStr = String(userAnswer || '').trim();
                const cStr = String(correctAnswer || '').trim();
                answerBodyHtml = `
                    <div style="display: flex; gap: 12px; margin-top: 10px; flex-wrap: wrap;">
                        <div style="flex: 1; min-width: 180px; background: ${status === 'correct' ? '#f0fdf4' : '#fef2f2'}; border: 1.5px solid ${status === 'correct' ? '#bbf7d0' : '#fecaca'}; padding: 10px 14px; border-radius: 8px;">
                            <div style="font-size: 0.78rem; color: #64748b; font-weight: 600;">HỌC SINH ĐIỀN:</div>
                            <div style="font-size: 1.05rem; font-weight: 700; color: ${status === 'correct' ? '#15803d' : '#b91c1c'}; margin-top: 2px;">
                                ${formatRichContent(uStr || '(Chưa nhập câu trả lời)')}
                            </div>
                        </div>
                        <div style="flex: 1; min-width: 180px; background: #f0fdf4; border: 1.5px solid #bbf7d0; padding: 10px 14px; border-radius: 8px;">
                            <div style="font-size: 0.78rem; color: #64748b; font-weight: 600;">ĐÁP ÁN ĐÚNG CỦA ĐỀ:</div>
                            <div style="font-size: 1.05rem; font-weight: 700; color: #15803d; margin-top: 2px;">
                                ${formatRichContent(cStr)}
                            </div>
                        </div>
                    </div>
                `;
            }
            
            let explainHtml = '';
            if (explain && String(explain).trim()) {
                explainHtml = `
                    <div style="margin-top: 10px; background: #f8fafc; border-left: 3px solid #0284c7; padding: 10px 14px; border-radius: 6px; font-size: 0.88rem; color: #334155;">
                        <strong style="color: #0284c7; display: flex; align-items: center; gap: 4px; margin-bottom: 4px;">
                            <i class="ri-lightbulb-line"></i> Lời giải chi tiết:
                        </strong>
                        <div style="line-height: 1.5;">${formatRichContent(explain)}</div>
                    </div>
                `;
            }
            
            html += `
                <div style="background: #ffffff; border: 1.5px solid ${cardBorder}; border-radius: 12px; padding: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.03);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 6px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-weight: 800; font-size: 0.95rem; color: #1e293b;">Câu ${qIndex + 1}</span>
                            ${typeBadge}
                        </div>
                        <div>${statusBadge}</div>
                    </div>
                    ${groupTitleHtml}
                    <div style="color: #1e293b; font-size: 0.95rem; line-height: 1.5; font-weight: 500;">
                        ${formatRichContent(cleanQ)}
                    </div>
                    ${imageHtml}
                    ${answerBodyHtml}
                    ${explainHtml}
                </div>
            `;
        });
    }
    
    html += `</div>`;
    body.innerHTML = html;
    
    if (typeof renderMath === 'function') {
        renderMath(body);
        setTimeout(() => renderMath(body), 100);
    }
}

// Hàm tương thích ngược
function showQuizAnalytics(quizId, quizTitle) {
    openQuizStats(quizId, quizTitle);
}

function closeAnalyticsModal() {
    closeQuizStats();
}

async function handleQuizAction(quizId, action) {
    let msg = "";
    if (action === 'trash') msg = "Bạn có chắc chắn muốn đưa đề thi này vào thùng rác?";
    if (action === 'permanent') msg = "Bạn có chắc chắn muốn XÓA VĨNH VIỄN đề thi này không? Hành động này không thể khôi phục!";
    if (action === 'restore') msg = "Bạn muốn khôi phục đề thi này (sẽ ở trạng thái khóa)?";
    
    if (msg && !confirm(msg)) return;
    
    showGlobalLoader({
        title: "Đang cập nhật đề thi...",
        subtitle: "Hệ thống đang lưu thay đổi vào cơ sở dữ liệu..."
    });

    try {
        const res = await fetch(`${API_BASE_URL}/api/teacher/quiz_action`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ teacher_token: authToken, quiz_id: quizId, action: action })
        });
        const data = await res.json();
        hideGlobalLoader();
        if (res.ok && data.status === 'success') {
            if (action === 'trash') alert("Đã đưa vào thùng rác!");
            if (action === 'permanent') alert("Đã xóa vĩnh viễn!");
            if (action === 'restore') alert("Đã khôi phục thành công!");
            loadTeacherQuizzes();
        } else {
            alert("Lỗi: " + data.detail);
        }
    } catch(e) {
        hideGlobalLoader();
        alert("Lỗi kết nối máy chủ");
    }
}

function editQuiz(quizId) {
    if (!quizId) return;
    window.location.href = `/editor?id=${encodeURIComponent(quizId)}`;
}

function openStudioNewQuiz() {
    sessionStorage.removeItem('editor_quiz_id');
    sessionStorage.removeItem('editor_quiz_data');
    sessionStorage.removeItem('editor_quiz_title');
    sessionStorage.removeItem('editor_quiz_settings');
    window.location.href = 'editor.html';
}

async function toggleQuizStatus(quizId, newStatus) {
    showGlobalLoader({
        title: "Đang đổi trạng thái đề thi...",
        subtitle: "Hệ thống đang lưu cài đặt..."
    });
    try {
        const res = await fetch(`${API_BASE_URL}/api/teacher/toggle_publish`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ teacher_token: authToken, quiz_id: quizId, status: newStatus })
        });
        hideGlobalLoader();
        if (res.ok) loadTeacherQuizzes();
    } catch(e) {
        hideGlobalLoader();
    }
}

// Các hàm tương thích ngược với Giám sát cũ (đã được hợp nhất vào openQuizStats)
function startMonitoring(quizId, title) {
    openQuizStats(quizId, title);
}

function stopMonitoring() {
    closeQuizStats();
}

window.showStudentDetails = function(b64data) {
    try {
        const s = JSON.parse(decodeURIComponent(escape(atob(b64data))));
        currentDetailStudent = s;
        const modal = document.getElementById('studentDetailsModal');
        if (modal) {
            renderStudentDetailBody();
            modal.style.display = 'flex';
        }
    } catch(e) {
        console.error(e);
    }
};

async function loadAdminSettings() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/get_api_key?admin_token=${authToken}`);
        const data = await res.json();
        if(res.ok && data.status === 'success') {
            adminApiKeys = data.api_keys || [];
            renderApiKeyList();
        }
    } catch(e) {}

    // Tải cấu hình Google Client ID
    try {
        const resG = await fetch(`${API_BASE_URL}/api/admin/get_google_client_id?admin_token=${authToken}`);
        const dataG = await resG.json();
        if (resG.ok && dataG.status === 'success') {
            const inputG = document.getElementById('adminGoogleClientId');
            if (inputG) {
                inputG.value = dataG.client_id || '';
            }
        }
    } catch(e) {}

    // Tải theo dõi chi phí và quota Gemini
    loadAdminGeminiStats();
}

async function saveAdminGoogleClientId() {
    const inputG = document.getElementById('adminGoogleClientId');
    if (!inputG) return;
    const cid = inputG.value.trim();
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/set_google_client_id`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ admin_token: authToken, client_id: cid })
        });
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            googleClientId = cid;
            setupGoogleSignInServices();
            alert("Đã lưu Google Client ID thành công!");
        } else {
            alert("Lỗi: " + (data.detail || "Không thể lưu Client ID"));
        }
    } catch(e) {
        alert("Lỗi kết nối máy chủ khi lưu Google Client ID");
    }
}


function renderApiKeyList() {
    const list = document.getElementById('apiKeyList');
    list.innerHTML = '';
    if (adminApiKeys.length === 0) {
        list.innerHTML = '<span style="color: var(--danger); font-size: 0.9rem;">Chưa có API Key nào được lưu.</span>';
        return;
    }
    adminApiKeys.forEach((key, index) => {
        const maskedKey = key.length > 15 ? key.substring(0, 8) + '...' + key.substring(key.length - 4) : key;
        list.innerHTML += `
            <div style="display: flex; justify-content: space-between; align-items: center; background: #f9fafb; padding: 10px 15px; border-radius: 8px; border: 1px solid var(--border);">
                <span style="font-family: monospace; font-size: 0.95rem;">${maskedKey}</span>
                <button class="btn-outline" style="padding: 4px 10px; font-size: 0.85rem; color: var(--danger); border-color: var(--danger);" onclick="removeApiKey(${index})">Xóa</button>
            </div>
        `;
    });
}

async function addApiKey() {
    const input = document.getElementById('newApiKeyInput');
    const newKey = input.value.trim();
    if (!newKey) return alert("Vui lòng nhập API Key hợp lệ!");
    if (adminApiKeys.includes(newKey)) return alert("Key này đã tồn tại trong danh sách!");
    
    adminApiKeys.push(newKey);
    input.value = '';
    await saveAdminApiKeys("Đã thêm API Key thành công!");
}

async function removeApiKey(index) {
    if (!confirm("Bạn có chắc chắn muốn xóa Key này không?")) return;
    adminApiKeys.splice(index, 1);
    await saveAdminApiKeys("Đã xóa API Key thành công!");
}

async function saveAdminApiKeys(successMsg) {
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/set_api_key`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({admin_token: authToken, api_keys: adminApiKeys})
        });
        if(res.ok) {
            renderApiKeyList();
            loadAdminGeminiStats();
            if (successMsg) alert(successMsg);
        }
    } catch(e) { alert("Lỗi lưu Key"); }
}

// THEO DÕI QUOTA & CHI PHÍ GEMINI TRONG TRANG ADMIN
async function loadAdminGeminiStats() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/gemini_stats?admin_token=${authToken}`);
        const data = await res.json();
        if (res.ok && data.status === 'success' && data.metrics) {
            const m = data.metrics;
            const today = m.today || {};
            const allTime = m.all_time || {};

            // Update KPI cards
            const statCallsToday = document.getElementById('statCallsToday');
            if (statCallsToday) statCallsToday.innerText = today.total_calls || 0;
            const statAllTimeCalls = document.getElementById('statAllTimeCalls');
            if (statAllTimeCalls) statAllTimeCalls.innerText = `Tổng lịch sử: ${allTime.total_calls || 0} lượt`;

            const statSuccessRate = document.getElementById('statSuccessRate');
            if (statSuccessRate) statSuccessRate.innerText = `${today.success_rate || 100}%`;
            const statSuccessCount = document.getElementById('statSuccessCount');
            if (statSuccessCount) statSuccessCount.innerText = `${today.success_calls || 0} lượt thành công`;

            const statErrors429 = document.getElementById('statErrors429');
            if (statErrors429) statErrors429.innerText = today.error_429 || 0;
            
            const keyStatuses = m.key_statuses || [];
            const warningCount = keyStatuses.filter(k => k.status === 'warning_429' || k.status === 'exhausted').length;
            const statWarningKeys = document.getElementById('statWarningKeys');
            if (statWarningKeys) statWarningKeys.innerText = `${warningCount} key quá tải`;

            const statCostToday = document.getElementById('statCostToday');
            if (statCostToday) statCostToday.innerText = `$${(today.estimated_cost_usd || 0).toFixed(4)}`;
            const statCostVnd = document.getElementById('statCostVnd');
            if (statCostVnd) statCostVnd.innerText = `${(today.estimated_cost_vnd || 0).toLocaleString()} VNĐ`;

            // Keys table
            const keysTbody = document.getElementById('geminiKeysTableBody');
            if (keysTbody) {
                keysTbody.innerHTML = '';
                if (keyStatuses.length === 0) {
                    keysTbody.innerHTML = '<tr><td colspan="7" style="padding: 15px; text-align: center; color: #94a3b8;">Chưa có API key nào được lưu trong hệ thống.</td></tr>';
                } else {
                    keyStatuses.forEach((k, idx) => {
                        let statusBadge = '<span style="background: #dcfce7; color: #15803d; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.8rem;">Ổn định (Healthy)</span>';
                        if (k.status === 'exhausted') {
                            statusBadge = '<span style="background: #fee2e2; color: #b91c1c; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.8rem;">⚠️ Hết Quota (Exhausted)</span>';
                        } else if (k.status === 'warning_429') {
                            statusBadge = '<span style="background: #fef3c7; color: #b45309; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.8rem;">⚡ Sắp đầy / Có lỗi 429</span>';
                        }
                        const tr = document.createElement('tr');
                        tr.style.borderBottom = '1px solid #f1f5f9';
                        tr.innerHTML = `
                            <td style="padding: 8px 12px; font-weight: 600; color: #64748b;">${idx + 1}</td>
                            <td style="padding: 8px 12px; font-family: monospace; font-weight: 700; color: #334155;">${escapeHtml(k.masked_key)}</td>
                            <td style="padding: 8px 12px;">${statusBadge}</td>
                            <td style="padding: 8px 12px; font-weight: 600; color: #2563eb;">${k.calls_today || 0}</td>
                            <td style="padding: 8px 12px; font-weight: 600; color: ${k.errors_429_today > 0 ? '#dc2626' : '#64748b'};">${k.errors_429_today || 0}</td>
                            <td style="padding: 8px 12px; color: #64748b; font-size: 0.82rem;">${k.last_used ? new Date(k.last_used).toLocaleTimeString() : 'Chưa dùng'}</td>
                            <td style="padding: 8px 12px; text-align: center;">
                                <button type="button" class="btn-outline" style="padding: 3px 8px; font-size: 0.78rem; border-radius: 4px;" onclick="pingGeminiKey('${escapeHtml(k.key)}', this)">Ping</button>
                            </td>
                        `;
                        keysTbody.appendChild(tr);
                    });
                }
            }

            // Daily history table
            const dailyTbody = document.getElementById('geminiDailyTableBody');
            if (dailyTbody) {
                dailyTbody.innerHTML = '';
                const dailyHistory = m.daily_history || [];
                if (dailyHistory.length === 0) {
                    dailyTbody.innerHTML = '<tr><td colspan="6" style="padding: 15px; text-align: center; color: #94a3b8;">Chưa có dữ liệu gọi API theo ngày.</td></tr>';
                } else {
                    dailyHistory.forEach(d => {
                        const tr = document.createElement('tr');
                        tr.style.borderBottom = '1px solid #f1f5f9';
                        let errRateColor = d.error_rate > 20 ? '#dc2626' : (d.error_rate > 5 ? '#f59e0b' : '#15803d');
                        tr.innerHTML = `
                            <td style="padding: 8px 12px; font-weight: 600; color: #334155;">${d.date}</td>
                            <td style="padding: 8px 12px; font-weight: 700; color: #2563eb;">${d.total_calls}</td>
                            <td style="padding: 8px 12px; color: #15803d; font-weight: 600;">${d.success_calls}</td>
                            <td style="padding: 8px 12px; color: ${d.error_429 > 0 ? '#dc2626' : '#64748b'}; font-weight: 600;">${d.error_429}</td>
                            <td style="padding: 8px 12px; color: #64748b;">${d.other_errors}</td>
                            <td style="padding: 8px 12px; font-weight: 700; color: ${errRateColor};">${d.error_rate}%</td>
                        `;
                        dailyTbody.appendChild(tr);
                    });
                }
            }
        }
    } catch(e) {
        console.error("loadAdminGeminiStats error:", e);
    }
}

async function pingGeminiKey(apiKey, btnElement) {
    if (!apiKey) return;
    const oldText = btnElement ? btnElement.innerHTML : '';
    if (btnElement) {
        btnElement.disabled = true;
        btnElement.innerHTML = '<i class="ri-loader-4-line ri-spin"></i>';
    }
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/ping_gemini_key`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                admin_token: authToken,
                api_key: apiKey
            })
        });
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            alert(`✅ Kết quả kiểm tra Key:\n- Trạng thái: ${data.result}\n- Phản hồi: ${data.message}\n- Độ trễ: ${data.latency_ms || 0}ms`);
            loadAdminGeminiStats();
        } else {
            alert(`⚠️ Kết quả kiểm tra Key:\n- Trạng thái: ${data.result || 'Lỗi'}\n- Chi tiết: ${data.detail || data.message || 'Không thể kết nối'}`);
        }
    } catch(e) {
        alert("Lỗi kết nối khi ping Gemini API Key: " + e.message);
    } finally {
        if (btnElement) {
            btnElement.disabled = false;
            btnElement.innerHTML = oldText || 'Ping';
        }
    }
}

async function loadAdminUsers() {
    const listEl = document.getElementById('adminUserList');
    if (listEl) {
        listEl.innerHTML = renderHntnInlineLoader('Đang tải danh sách tài khoản...', 'Hệ thống đang truy vấn cơ sở dữ liệu...', 80);
    }
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/users?admin_token=${authToken}`);
        const data = await res.json();
        if (res.status === 403) {
            console.warn("Phiên đăng nhập quản trị viên đã hết hạn hoặc không hợp lệ (403).");
            showToast("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.", "warning");
            setTimeout(() => { logout(); }, 1200);
            return;
        }
        if(res.ok && data.status === 'success') {
            let html = `<table style="width:100%; border-collapse: collapse; text-align:left; font-size: 0.9rem;">
                <tr style="border-bottom: 2px solid var(--border); color: var(--text-muted); background: #f8fafc;">
                    <th style="padding: 12px 10px;">Tài khoản / Email</th>
                    <th style="padding: 12px 10px;">Họ tên</th>
                    <th style="padding: 12px 10px;">Vai trò</th>
                    <th style="padding: 12px 10px;">Lớp / Môn</th>
                    <th style="padding: 12px 10px;">SĐT & Trường</th>
                    <th style="padding: 12px 10px;">Trạng thái</th>
                    <th style="padding: 12px 10px; text-align: right;">Thao tác</th>
                </tr>`;
            data.data.forEach(u => {
                let roleStr = u.role === 'teacher' ? '<span style="color:#4f46e5; font-weight:700;">👨‍🏫 Giáo viên</span>' : (u.role === 'student' ? '<span style="color:#059669; font-weight:600;">👨‍🎓 Học sinh</span>' : '<span style="color:#dc2626; font-weight:700;">🛡️ Admin</span>');
                let statStr = u.status === 'approved' 
                    ? '<span style="display:inline-block; padding:3px 8px; border-radius:12px; background:#dcfce7; color:#15803d; font-weight:700; font-size:0.8rem;">Đã duyệt</span>' 
                    : '<span style="display:inline-block; padding:3px 8px; border-radius:12px; background:#fef3c7; color:#b45309; font-weight:700; font-size:0.8rem;">⏳ Chờ duyệt</span>';
                
                let extraInfo = [];
                if (u.phone) extraInfo.push(`📞 ${escapeHtml(u.phone)}`);
                if (u.school) extraInfo.push(`🏫 ${escapeHtml(u.school)}`);
                let extraHtml = extraInfo.length > 0 ? extraInfo.join('<br>') : '<span style="color:#94a3b8;">-</span>';
                let classHtml = u.class_name ? `<span style="font-weight:600; color:#334155;">${escapeHtml(u.class_name)}</span>` : '<span style="color:#94a3b8;">-</span>';

                let btn = u.status === 'pending' ? `<button class="btn-success" style="width:auto; margin:0; padding: 6px 12px; font-size:0.85rem; font-weight:700; background:#10b981; color:white; border:none; border-radius:8px; cursor:pointer;" onclick="approveUser('${u.id}')"><i class="ri-check-line"></i> Duyệt</button>` : '';
                let resetBtn = u.role !== 'admin' ? `<button class="btn-outline" style="width:auto; margin:0 0 0 6px; padding: 5px 10px; font-size:0.82rem; color: var(--primary); border-color: var(--primary); border-radius:8px;" onclick="resetUserPassword('${u.id}', '${u.username}')">Đổi MK</button>` : '';
                let delBtn = u.role !== 'admin' ? `<button class="btn-outline" style="width:auto; margin:0 0 0 6px; padding: 5px 10px; font-size:0.82rem; color: var(--danger); border-color: var(--danger); border-radius:8px;" onclick="deleteUser('${u.id}')">Xóa</button>` : '';
                html += `<tr style="border-bottom: 1px solid var(--border);">
                    <td style="padding: 12px 10px; font-weight: 600; word-break: break-all;">${escapeHtml(u.email || u.username || '')}</td>
                    <td style="padding: 12px 10px; font-weight: 600;">${escapeHtml(u.full_name || '')}</td>
                    <td style="padding: 12px 10px;">${roleStr}</td>
                    <td style="padding: 12px 10px;">${classHtml}</td>
                    <td style="padding: 12px 10px; font-size:0.85rem; color:#475569;">${extraHtml}</td>
                    <td style="padding: 12px 10px;">${statStr}</td>
                    <td style="padding: 12px 10px; text-align: right; white-space: nowrap;">${btn} ${resetBtn} ${delBtn}</td>
                </tr>`;
            });
            html += `</table>`;
            if (listEl) listEl.innerHTML = html;
        }
    } catch(e) { 
        alert("Lỗi tải danh sách người dùng"); 
    }
}

async function approveUser(uid) {
    showGlobalLoader({
        title: "Đang phê duyệt tài khoản...",
        subtitle: "Hệ thống đang mở khóa quyền giáo viên..."
    });
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/approve`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({admin_token: authToken, user_id: uid}) });
        hideGlobalLoader();
        if(res.ok) {
            alert("✅ Đã phê duyệt tài khoản thành công!");
            loadAdminUsers();
        } else {
            alert("Lỗi khi duyệt tài khoản");
        }
    } catch(e) {
        hideGlobalLoader();
        alert("Lỗi kết nối máy chủ");
    }
}

async function deleteUser(uid) {
    if(!confirm("Bạn có chắc chắn muốn xóa tài khoản này?")) return;
    showGlobalLoader({
        title: "Đang xóa tài khoản...",
        subtitle: "Đang gỡ bỏ hồ sơ khỏi hệ thống..."
    });
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/delete`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({admin_token: authToken, user_id: uid}) });
        hideGlobalLoader();
        if(res.ok) loadAdminUsers();
    } catch(e) {
        hideGlobalLoader();
    }
}

async function resetUserPassword(uid, username) {
    const newPwd = prompt(`Nhập mật khẩu mới cho tài khoản "${username}":`);
    if (newPwd === null) return; // Nhấn Hủy
    
    showGlobalLoader({
        title: "Đang cập nhật mật khẩu...",
        subtitle: "Hệ thống đang mã hóa và lưu mật khẩu mới..."
    });
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/reset_password`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ admin_token: authToken, user_id: uid, new_password: newPwd.trim() })
        });
        const data = await res.json();
        hideGlobalLoader();
        if (res.ok && data.status === 'success') {
            alert(`Đã đổi mật khẩu cho tài khoản "${username}" thành công!`);
        } else {
            alert("Lỗi: " + data.detail);
        }
    } catch(e) {
        hideGlobalLoader();
        alert("Lỗi kết nối máy chủ");
    }
}

async function changeAdminPassword() {
    const oldPwd = document.getElementById('adminOldPwd').value.trim();
    const newPwd = document.getElementById('adminNewPwd').value.trim();
    if (!oldPwd || !newPwd) return alert("Vui lòng nhập đủ mật khẩu cũ và mới!");
    
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/change_password`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ admin_token: authToken, old_password: oldPwd, new_password: newPwd })
        });
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            alert("Đổi mật khẩu thành công! Vui lòng đăng nhập lại với mật khẩu mới.");
            logout();
        } else {
            alert("Lỗi: " + data.detail);
        }
    } catch(e) {
        alert("Lỗi kết nối máy chủ");
    }
}

async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files[0]) { alert("Vui lòng chọn file .docx hoặc .pdf!"); return; }
    
    const file = fileInput.files[0];
    const selectedFileName = file.name || "";
    let detectedTitle = selectedFileName.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ").trim();
    if (!detectedTitle) detectedTitle = "Đề thi mới";
    
    const formData = new FormData();
    formData.append("file", file);
    
    const useAI = document.getElementById('useAIToggle') ? document.getElementById('useAIToggle').checked : true;
    formData.append("use_ai", useAI);
    
    // Hiển thị trạng thái khởi tạo nhanh
    const loadingOverlay = document.getElementById('loadingOverlay');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const statusText = document.getElementById('loadingStatusText');
    
    if (loadingOverlay) {
        resetHntnLoader(loadingOverlay);
        loadingOverlay.style.display = 'flex';
        progressBar.style.width = '35%';
        progressText.innerText = '35%';
        statusText.innerText = '⚙️ Đang gửi file lên máy chủ và mở Studio...';
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/upload`, { method: 'POST', body: formData });
        const result = await response.json();
        
        if (result.status === "processing") {
            // Chuyển hướng NGAY LẬP TỨC sang trang Studio riêng để phân tích!
            sessionStorage.removeItem('editor_quiz_id');
            sessionStorage.removeItem('editor_quiz_data');
            sessionStorage.setItem('editor_quiz_title', detectedTitle);
            sessionStorage.setItem('editor_pending_task_id', result.task_id);
            sessionStorage.setItem('editor_pending_mode', useAI ? 'ai' : 'python');

            window.location.href = `editor.html?task_id=${encodeURIComponent(result.task_id)}&title=${encodeURIComponent(detectedTitle)}&use_ai=${useAI}`;
        } else if (result.status === "success") {
            const normalizedData = normalizeImageUrls(result.data || []);
            sessionStorage.removeItem('editor_quiz_id');
            sessionStorage.removeItem('editor_pending_task_id');
            sessionStorage.setItem('editor_quiz_data', JSON.stringify(normalizedData));
            sessionStorage.setItem('editor_quiz_title', detectedTitle);
            sessionStorage.setItem('editor_quiz_settings', JSON.stringify({
                title: detectedTitle,
                mode: 'practice',
                timeLimit: 0,
                isShuffle: false
            }));
            window.location.href = 'editor.html';
        } else { 
            if (loadingOverlay) loadingOverlay.style.display = 'none';
            alert("Lỗi: " + (result.detail || "Không thể tải file lên")); 
        }
    } catch (e) { 
        if (loadingOverlay) loadingOverlay.style.display = 'none';
        alert("Lỗi kết nối máy chủ! Có thể Server đang khởi động lại (Cold Start), hãy thử lại trong ít giây."); 
    }
}

function applyUploadData(dataArray, fileName = "") {
    const normalizedData = normalizeImageUrls(dataArray || []);
    
    let detectedTitle = "Đề thi mới";
    if (fileName) {
        detectedTitle = fileName.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ").trim();
    } else if (normalizedData.length > 0 && normalizedData[0].group_title) {
        detectedTitle = normalizedData[0].group_title.replace(/<br>/gi, ' ').trim();
    }
    
    // Lưu dữ liệu vào Session Storage để trang Studio riêng tải lên
    sessionStorage.setItem('editor_quiz_data', JSON.stringify(normalizedData));
    sessionStorage.setItem('editor_quiz_title', detectedTitle);
    sessionStorage.setItem('editor_quiz_settings', JSON.stringify({
        title: detectedTitle,
        mode: 'practice',
        timeLimit: 0,
        isShuffle: false
    }));
    sessionStorage.removeItem('editor_quiz_id');

    // Chuyển hướng sang trang riêng (Studio Biên tập & Soát lỗi Đề thi)
    window.location.href = 'editor.html';
}

async function generateQuizWithAI() {
    const promptStr = document.getElementById('aiGenPrompt').value.trim();
    const count = parseInt(document.getElementById('aiGenCount').value) || 5;
    const diff = document.getElementById('aiGenDiff').value;

    if (!promptStr) return alert("Vui lòng nhập chủ đề hoặc nội dung để AI tạo đề!");
    if (count < 1 || count > 50) return alert("Số lượng câu hỏi nên từ 1 đến 50!");

    const loadingOverlay = document.getElementById('loadingOverlay');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const statusText = document.getElementById('loadingStatusText');
    
    let detectedTitle = promptStr.length > 50 ? promptStr.substring(0, 50) + "..." : promptStr;

    if (loadingOverlay) {
        resetHntnLoader(loadingOverlay);
        loadingOverlay.style.display = 'flex';
        progressBar.style.width = '35%';
        progressText.innerText = '35%';
        statusText.innerText = '🤖 Đang khởi tạo và chuyển sang Studio...';
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/generate_quiz_ai`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ prompt: promptStr, num_questions: count, difficulty: diff })
        });
        const result = await response.json();
        
        if (response.ok && (result.status === "processing" || result.status === "success")) {
            if (result.status === "processing") {
                // Chuyển hướng NGAY LẬP TỨC sang Studio riêng để AI xử lý ngầm!
                sessionStorage.removeItem('editor_quiz_id');
                sessionStorage.removeItem('editor_quiz_data');
                sessionStorage.setItem('editor_quiz_title', detectedTitle);
                sessionStorage.setItem('editor_pending_task_id', result.task_id);
                sessionStorage.setItem('editor_pending_mode', 'ai_generate');

                window.location.href = `editor.html?task_id=${encodeURIComponent(result.task_id)}&title=${encodeURIComponent(detectedTitle)}&mode=ai_generate`;
            } else {
                const normalizedData = normalizeImageUrls(result.data || []);
                sessionStorage.removeItem('editor_quiz_id');
                sessionStorage.removeItem('editor_pending_task_id');
                sessionStorage.setItem('editor_quiz_data', JSON.stringify(normalizedData));
                sessionStorage.setItem('editor_quiz_title', detectedTitle);
                sessionStorage.setItem('editor_quiz_settings', JSON.stringify({
                    title: detectedTitle,
                    mode: 'practice',
                    timeLimit: 0,
                    isShuffle: false
                }));
                window.location.href = 'editor.html';
            }
        } else {
            if (loadingOverlay) loadingOverlay.style.display = 'none';
            alert("Lỗi AI: " + (result.detail || "Không thể tạo đề"));
        }
    } catch(e) {
        if (loadingOverlay) loadingOverlay.style.display = 'none';
        alert("Lỗi kết nối máy chủ! " + e.message);
    }
}

function backToDashboard() {
    currentData = [];
    editingQuizId = null;
    window.tempQuizSettings = null;
    document.body.classList.remove('editor-fullscreen');
    document.getElementById('quiz-container').innerHTML = '';
    document.getElementById('modeSwitch').style.display = 'none';
    document.getElementById('saveBtn').style.display = 'none';
    document.getElementById('aiCustomPrompt').style.display = 'none';
    document.getElementById('aiCustomPrompt').value = '';
    const qpIndex = document.getElementById('aiQuickPromptsIndex');
    if (qpIndex) qpIndex.style.display = 'none';
    window.activeAIFeedbacks = {};
    document.getElementById('btnAICheck').style.display = 'none';
    document.getElementById('aiFeedbackBox').style.display = 'none';
    document.getElementById('backDashboardBtn').style.display = 'none';
    document.getElementById('creationHub').style.display = 'flex';
    document.getElementById('teacherDashboard').style.display = 'block';
    loadTeacherQuizzes();
}

function openPublishModal() {
    const pubHeader = document.getElementById('publicHeader');
    if (pubHeader) pubHeader.style.display = 'none';
    const landingHero = document.getElementById('landingHero');
    if (landingHero) landingHero.style.display = 'none';
    const landingStats = document.getElementById('landingStats');
    if (landingStats) landingStats.style.display = 'none';
    const landingExtra = document.getElementById('publicLandingExtras');
    if (landingExtra) landingExtra.style.display = 'none';

    document.getElementById('publishModal').style.display = 'flex';
    if (editingQuizId && window.tempQuizSettings) {
        document.getElementById('modalQuizTitle').value = window.tempQuizSettings.title || "";
        document.getElementById('modalQuizMode').value = window.tempQuizSettings.mode || "practice";
        document.getElementById('modalQuizTime').value = window.tempQuizSettings.timeLimit || "";
        document.getElementById('modalQuizShuffle').checked = window.tempQuizSettings.isShuffle || false;
    } else {
        document.getElementById('modalQuizTitle').value = "";
        document.getElementById('modalQuizMode').value = "practice";
        document.getElementById('modalQuizTime').value = "";
        document.getElementById('modalQuizShuffle').checked = false;
    }
}

function closePublishModal() {
    document.getElementById('publishModal').style.display = 'none';
}

async function confirmPublish() {
    const title = document.getElementById('modalQuizTitle').value.trim();
    if (!title) return alert("Vui lòng nhập tên bài kiểm tra!");
    
    const mode = document.getElementById('modalQuizMode').value;
    const timeLimit = parseInt(document.getElementById('modalQuizTime').value) || 0;
    const isShuffle = document.getElementById('modalQuizShuffle').checked;
    
    const btn = document.getElementById('btnConfirmPublish');
    btn.innerText = "⏳ Đang xử lý...";
    btn.disabled = true;
    
    showGlobalLoader({
        title: "Đang lưu & xuất bản đề thi...",
        subtitle: "Đang đồng bộ dữ liệu đề thi lên cơ sở dữ liệu..."
    });

    try {
        const payload = { 
            title: title, data: currentData, mode: mode, time_limit: timeLimit, 
            is_shuffle: isShuffle, creator_id: authToken, status: "published" 
        };
        if (editingQuizId) payload.quiz_id = editingQuizId;

        const payloadString = JSON.stringify(payload);
        const payloadSizeKB = new Blob([payloadString]).size / 1024;
        
        if (payloadSizeKB > 900) {
            alert(`⚠️ CẢNH BÁO: Đề thi của bạn có kích thước khá lớn (${Math.round(payloadSizeKB)} KB), chủ yếu do chứa nhiều hình ảnh. Việc lưu có thể bị lỗi nếu vượt quá giới hạn 1MB của cơ sở dữ liệu.\n\nKhuyên bạn nên nén/thu nhỏ kích thước ảnh trong file Word trước khi tải lên.`);
        }

        const response = await fetch(`${API_BASE_URL}/api/save_quiz`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: payloadString
        });
        const result = await response.json();
        hideGlobalLoader();
        if (result.status === 'success') {
            closePublishModal();
            const shareLink = window.location.origin + window.location.pathname + "?id=" + result.quiz_id;
            prompt(`Lưu thành công!\nMã đề: ${result.quiz_id}\n\nCopy đường link gọn gàng bên dưới để gửi học sinh:`, shareLink);
            editingQuizId = result.quiz_id;
            window.tempQuizSettings = { title, mode, timeLimit, isShuffle };
            
            if (confirm("Đã xuất bản thành công! Bạn có muốn quay về màn hình Quản lý không?")) {
                backToDashboard();
            }
        } else {
            alert("Lỗi lưu đề thi: " + (result.detail || result.message || "Không thể lưu đề"));
        }
    } catch (e) { 
        hideGlobalLoader();
        alert("Lỗi khi kết nối với máy chủ cơ sở dữ liệu!"); 
    }
    btn.innerText = "🚀 Lưu & Xuất bản";
    btn.disabled = false;
}

function normalizeImageUrls(data) {
    if (!data) return data;
    try {
        let jsonStr = JSON.stringify(data);
        // 1. Chuyển đổi link R2 public direct (thường bị Cloudflare chặn 403) sang endpoint an toàn của backend
        jsonStr = jsonStr.replace(/https:\/\/pub-[a-zA-Z0-9]+\.r2\.dev\//g, `${API_BASE_URL}/api/images/`);
        
        // 2. Chuyển đường dẫn tương đối /api/images/... thành URL tuyệt đối ${API_BASE_URL}/api/images/...
        // Đảm bảo hoạt động hoàn hảo trên Cloudflare Pages (tránh lỗi 404 do Cloudflare Pages không phục vụ ảnh)
        jsonStr = jsonStr.replace(/(["'])\/api\/images\//g, `$1${API_BASE_URL}/api/images/`);
        
        // 3. Khử trùng lặp nếu API_BASE_URL bị nối lặp
        if (API_BASE_URL) {
            const escapedBase = API_BASE_URL.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const dupRegex = new RegExp(`(?:${escapedBase})+/api/images/`, 'g');
            jsonStr = jsonStr.replace(dupRegex, `${API_BASE_URL}/api/images/`);
        }
        return JSON.parse(jsonStr);
    } catch(e) {
        return data;
    }
}

async function checkQuizWithAI() {
    const btn = document.getElementById('btnAICheck');
    const customPrompt = document.getElementById('aiCustomPrompt').value.trim();
    if (btn) {
        btn.innerText = "⏳ Đang rà soát và thống kê toàn bộ đề thi (10-20s)...";
        btn.disabled = true;
    }

    showGlobalLoader({
        title: "🤖 AI đang rà soát & chuẩn hóa đề thi...",
        subtitle: "Đang phân tích từng câu hỏi, kiểm tra tính đúng đắn của đáp án và công thức (10-20s)..."
    });

    try {
        const res = await fetch(`${API_BASE_URL}/api/teacher/check_quiz_ai`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({teacher_token: authToken, quiz_data: currentData, custom_prompt: customPrompt})
        });
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            document.getElementById('aiFeedbackBox').style.display = 'block';
            const statsContainer = document.getElementById('aiFeedbackStats');
            const btnApplyAll = document.getElementById('btnApplyAllAI');

            window.activeAIFeedbacks = {};
            window.activeAINewQuizData = (Array.isArray(data.new_quiz_data) && data.new_quiz_data.length > 0) ? data.new_quiz_data : null;
            window.activeAISummary = data.summary || "";

            if (Array.isArray(data.feedback) && data.feedback.length > 0) {
                data.feedback.forEach(item => {
                    window.activeAIFeedbacks[item.question_index] = item;
                });

                const stats = data.stats || {
                    total_questions: currentData.length,
                    valid_questions: Math.max(0, currentData.length - data.feedback.length),
                    error_count: data.feedback.length,
                    accuracy_rate: Math.round(((currentData.length - data.feedback.length) / currentData.length) * 100),
                    category_counts: { delete: 0, restructure: 0, explanation: 0, latex: 0, knowledge: 0, answer: 0, grammar_typo: 0, format: 0 }
                };

                let summaryHtml = data.summary ? `
                    <div class="ai-summary-banner">
                        <div class="ai-summary-title"><i class="ri-sparkling-fill"></i> Tóm tắt phản hồi từ AI:</div>
                        <div class="ai-summary-text">${escapeHtml(data.summary)}</div>
                    </div>
                ` : '';

                let catChipsHtml = '<div class="ai-cat-chips">';
                if (stats.category_counts?.delete > 0) {
                    catChipsHtml += `<span class="ai-cat-chip ai-cat-delete">🗑️ Yêu cầu xóa: <b>${stats.category_counts.delete}</b></span>`;
                }
                if (stats.category_counts?.restructure > 0) {
                    catChipsHtml += `<span class="ai-cat-chip ai-cat-restructure">🔄 Đổi kết cấu: <b>${stats.category_counts.restructure}</b></span>`;
                }
                if (stats.category_counts?.explanation > 0) {
                    catChipsHtml += `<span class="ai-cat-chip ai-cat-explain">💡 Bổ sung lời giải: <b>${stats.category_counts.explanation}</b></span>`;
                }
                if (stats.category_counts?.latex > 0) {
                    catChipsHtml += `<span class="ai-cat-chip ai-cat-latex">📐 Công thức LaTeX: <b>${stats.category_counts.latex}</b></span>`;
                }
                catChipsHtml += `
                    <span class="ai-cat-chip ai-cat-knowledge">🧠 Kiến thức: <b>${stats.category_counts?.knowledge || 0}</b></span>
                    <span class="ai-cat-chip ai-cat-answer">🎯 Đáp án: <b>${stats.category_counts?.answer || 0}</b></span>
                    <span class="ai-cat-chip ai-cat-grammar">✍️ Chính tả / Diễn đạt: <b>${stats.category_counts?.grammar_typo || 0}</b></span>
                    <span class="ai-cat-chip ai-cat-format">📐 Định dạng: <b>${stats.category_counts?.format || 0}</b></span>
                </div>`;

                // Render Bảng Thống kê
                let statsHtml = `
                    ${summaryHtml}
                    <div class="ai-stat-grid">
                        <div class="ai-stat-card">
                            <span class="ai-stat-label">Tổng số câu ban đầu</span>
                            <span class="ai-stat-val" style="color: #2563eb;">${stats.total_questions}</span>
                        </div>
                        <div class="ai-stat-card">
                            <span class="ai-stat-label">Số câu đạt chuẩn</span>
                            <span class="ai-stat-val" style="color: #10b981;">${stats.valid_questions}</span>
                        </div>
                        <div class="ai-stat-card">
                            <span class="ai-stat-label">Yêu cầu / Cần sửa</span>
                            <span class="ai-stat-val" style="color: #ef4444;">${stats.error_count}</span>
                        </div>
                        <div class="ai-stat-card">
                            <span class="ai-stat-label">Tỷ lệ chính xác</span>
                            <span class="ai-stat-val" style="color: #9333ea;">${stats.accuracy_rate}%</span>
                        </div>
                    </div>
                    ${catChipsHtml}
                `;
                statsContainer.innerHTML = statsHtml;

                renderAIFeedbackList();

                if (btnApplyAll) {
                    btnApplyAll.style.display = 'inline-block';
                    btnApplyAll.innerHTML = '<i class="ri-flashlight-line"></i> Áp dụng TẤT CẢ thay đổi';
                }

                // Render lại khung Xem trước
                renderPreviewAll();
            } else if (Array.isArray(data.feedback) && data.feedback.length === 0) {
                let summaryHtml = data.summary ? `
                    <div class="ai-summary-banner" style="margin-bottom: 20px;">
                        <div class="ai-summary-title"><i class="ri-sparkling-fill"></i> Tóm tắt phản hồi từ AI:</div>
                        <div class="ai-summary-text">${escapeHtml(data.summary)}</div>
                    </div>
                ` : '';

                statsContainer.innerHTML = `
                    ${summaryHtml}
                    <div style="text-align: center; padding: 25px 10px;">
                        <div style="font-size: 3rem; margin-bottom: 10px;">🎉</div>
                        <h3 style="margin: 0; color: #059669;">Tuyệt vời! Đề thi đạt chuẩn 100% không phát hiện lỗi!</h3>
                        <p style="margin: 6px 0 0 0; color: #64748b;">Toàn bộ câu hỏi, đáp án và định dạng đều hoàn hảo và sẵn sàng xuất bản.</p>
                    </div>
                `;
                document.getElementById('aiFeedbackContent').innerHTML = '';
                if (btnApplyAll) btnApplyAll.style.display = 'none';
            } else {
                statsContainer.innerHTML = '';
                document.getElementById('aiFeedbackContent').innerHTML = (typeof data.feedback === 'string') ? data.feedback.replace(/\n/g, '<br>') : 'Phản hồi không hợp lệ.';
                if (btnApplyAll) btnApplyAll.style.display = 'none';
            }

            document.getElementById('aiFeedbackBox').scrollIntoView({behavior: 'smooth', block: 'start'});
        } else {
            alert("Lỗi AI: " + (data.detail || "Không thể phân tích đề thi"));
        }
    } catch(e) {
        alert("Lỗi kết nối tới máy chủ khi gọi AI.");
    } finally {
        hideGlobalLoader();
        if (btn) {
            btn.innerText = "🤖 AI Kiểm tra lỗi & Phân tích Đề thi";
            btn.disabled = false;
        }
    }
}

function renderAIFeedbackList() {
    const contentContainer = document.getElementById('aiFeedbackContent');
    const btnApplyAll = document.getElementById('btnApplyAllAI');
    if (!contentContainer) return;

    const remainingKeys = Object.keys(window.activeAIFeedbacks || {});
    if (remainingKeys.length === 0) {
        contentContainer.innerHTML = `
            <div style="text-align: center; padding: 20px 10px;">
                <div style="font-size: 2.2rem; color: #10b981; margin-bottom: 6px;"><i class="ri-checkbox-circle-fill"></i></div>
                <h3 style="margin: 0; color: #059669;">Tất cả yêu cầu và lỗi đã được xử lý hoàn tất!</h3>
                <p style="margin: 4px 0 0 0; color: #64748b;">Dữ liệu đề thi đã được cập nhật và đồng bộ toàn diện.</p>
            </div>
        `;
        if (btnApplyAll) btnApplyAll.style.display = 'none';
        return;
    }

    let errorListHtml = `
        <h4 style="margin: 15px 0 10px 0; color: #475569; font-size: 0.95rem; text-transform: uppercase;">
            📍 Danh sách các câu cần xử lý (${remainingKeys.length} câu):
        </h4>
        <div class="ai-error-list-container">
    `;

    const sortedIndices = remainingKeys.map(Number).sort((a, b) => a - b);
    sortedIndices.forEach(qIdx => {
        const item = window.activeAIFeedbacks[qIdx];
        if (!item) return;

        const isDelete = item.action === 'delete' || item.category === 'delete';
        const isRestructure = item.action === 'restructure' || item.category === 'restructure';
        const isExplain = item.category === 'explanation';
        const isLatex = item.category === 'latex';

        const catClass = isDelete ? 'ai-cat-delete' :
                         (isRestructure ? 'ai-cat-restructure' :
                         (isExplain ? 'ai-cat-explain' :
                         (isLatex ? 'ai-cat-latex' :
                         (item.category === 'knowledge' ? 'ai-cat-knowledge' :
                         (item.category === 'answer' ? 'ai-cat-answer' :
                         (item.category === 'grammar_typo' ? 'ai-cat-grammar' : 'ai-cat-format'))))));

        let actionBtnHtml = '';
        if (isDelete) {
            actionBtnHtml = `<button class="btn-ai-delete" onclick="applyAIDelete(${qIdx})"><i class="ri-delete-bin-line"></i> Xóa câu</button>`;
        } else if (isRestructure) {
            actionBtnHtml = `<button class="btn-ai-restructure" onclick="applyAISuggestion(${qIdx})"><i class="ri-swap-line"></i> Đổi kết cấu</button>`;
        } else if (isExplain) {
            actionBtnHtml = `<button class="btn-ai-explain" onclick="applyAISuggestion(${qIdx})"><i class="ri-lightbulb-line"></i> Bổ sung lời giải</button>`;
        } else {
            actionBtnHtml = `<button class="btn-primary" style="padding: 6px 12px; font-size: 0.85rem; background: #9333ea;" onclick="applyAISuggestion(${qIdx})">✨ Sửa câu này</button>`;
        }

        errorListHtml += `
            <div class="ai-error-item" id="ai_summary_item_${qIdx}">
                <div style="flex: 1; min-width: 260px;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                        <span style="font-weight: 800; color: #6b21a8; font-size: 1rem;">Câu ${qIdx + 1}</span>
                        <span class="ai-cat-chip ${catClass}" style="padding: 2px 8px; font-size: 0.75rem;">${item.category_name || (isDelete ? 'Yêu cầu xóa câu' : 'Lỗi')}</span>
                    </div>
                    <div style="font-size: 0.9rem; color: ${isDelete ? '#dc2626; font-weight: 500;' : '#475569;'}">${escapeHtml(item.reason)}</div>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <button class="btn-outline" style="padding: 6px 12px; font-size: 0.85rem; border-color: #9333ea; color: #9333ea;" onclick="jumpToQuestionCard(${qIdx})">🎯 Tới Câu ${qIdx + 1}</button>
                    ${actionBtnHtml}
                </div>
            </div>
        `;
    });

    errorListHtml += `</div>`;
    contentContainer.innerHTML = errorListHtml;
    if (btnApplyAll) btnApplyAll.style.display = 'inline-block';
}

function jumpToQuestionCard(qIndex) {
    const targetCard = document.getElementById(`preview_q_${qIndex}`);
    if (targetCard) {
        targetCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        targetCard.classList.remove('ai-target-highlight');
        void targetCard.offsetWidth; // Kích hoạt reflow
        targetCard.classList.add('ai-target-highlight');
        setTimeout(() => {
            targetCard.classList.remove('ai-target-highlight');
        }, 3600);
    }
    // Đồng bộ cuộn Editor
    scrollToQuestionInEditor(qIndex);
}

function applyAllAISuggestions() {
    if (!window.activeAIFeedbacks || Object.keys(window.activeAIFeedbacks).length === 0) {
        alert("Không có đề xuất sửa đổi nào cần áp dụng.");
        return;
    }

    const count = Object.keys(window.activeAIFeedbacks).length;
    if (!confirm(`Bạn có chắc muốn tự động áp dụng TẤT CẢ ${count} thay đổi từ AI (xóa câu, đổi kết cấu, sửa nội dung)?`)) {
        return;
    }

    if (Array.isArray(window.activeAINewQuizData) && window.activeAINewQuizData.length > 0) {
        currentData = JSON.parse(JSON.stringify(window.activeAINewQuizData));
    } else {
        // Áp dụng từ dưới lên theo index giảm dần để không bị lệch thứ tự khi xóa
        const sortedIndices = Object.keys(window.activeAIFeedbacks).map(Number).sort((a, b) => b - a);
        for (const qIdx of sortedIndices) {
            const fb = window.activeAIFeedbacks[qIdx];
            if (!fb) continue;
            if (fb.action === 'delete' || fb.category === 'delete') {
                currentData.splice(qIdx, 1);
            } else if (fb.corrected_data && currentData[qIdx]) {
                const origGroup = currentData[qIdx].group_title;
                currentData[qIdx] = {
                    ...fb.corrected_data,
                    group_title: fb.corrected_data.group_title !== undefined ? fb.corrected_data.group_title : origGroup
                };
            }
        }
    }

    window.activeAIFeedbacks = {};
    window.activeAINewQuizData = null;

    const codeEditor = document.getElementById('codeEditor');
    if (codeEditor) {
        codeEditor.value = dataToEditorText(currentData);
        updateSyntaxHighlight();
    }

    renderPreviewAll();
    renderAIFeedbackList();

    const btnApplyAll = document.getElementById('btnApplyAllAI');
    if (btnApplyAll) btnApplyAll.style.display = 'none';

    document.getElementById('aiFeedbackStats').innerHTML = `
        <div style="text-align: center; padding: 20px 10px;">
            <div style="font-size: 2.5rem; margin-bottom: 8px;">✨</div>
            <h3 style="margin: 0; color: #9333ea;">Đã áp dụng thành công tất cả thay đổi!</h3>
            <p style="margin: 4px 0 0 0; color: #64748b;">Dữ liệu đề thi và trình soạn thảo Code đã được cập nhật hoàn tất.</p>
        </div>
    `;
    alert(`Đã áp dụng toàn bộ thay đổi thành công!`);
}

function applyAIDelete(question_index) {
    if (!confirm(`Bạn có chắc chắn muốn XÓA Câu ${question_index + 1}? Câu hỏi này sẽ bị loại bỏ khỏi đề thi.`)) return;

    currentData.splice(question_index, 1);

    // Cập nhật lại chỉ số các câu hỏi còn lại trong activeAIFeedbacks
    delete window.activeAIFeedbacks[question_index];
    const newFeedbacks = {};
    for (const key in window.activeAIFeedbacks) {
        const k = parseInt(key);
        if (k > question_index) {
            const item = window.activeAIFeedbacks[k];
            item.question_index = k - 1;
            newFeedbacks[k - 1] = item;
        } else {
            newFeedbacks[k] = window.activeAIFeedbacks[k];
        }
    }
    window.activeAIFeedbacks = newFeedbacks;
    window.activeAINewQuizData = null;

    const codeEditor = document.getElementById('codeEditor');
    if (codeEditor) {
        codeEditor.value = dataToEditorText(currentData);
        updateSyntaxHighlight();
    }

    renderPreviewAll();
    renderAIFeedbackList();
}

function applyAISuggestion(question_index) {
    const aiData = window.activeAIFeedbacks[question_index];
    if (!aiData) return;

    if (aiData.action === 'delete' || aiData.category === 'delete') {
        return applyAIDelete(question_index);
    }
    
    const corrected_data = aiData.corrected_data;
    if (currentData[question_index] && corrected_data) {
        const originalGroupTitle = currentData[question_index].group_title;

        currentData[question_index] = {
            ...corrected_data,
            group_title: corrected_data.group_title !== undefined ? corrected_data.group_title : originalGroupTitle
        };

        delete window.activeAIFeedbacks[question_index];
        window.activeAINewQuizData = null;

        const codeEditor = document.getElementById('codeEditor');
        if (codeEditor) {
            codeEditor.value = dataToEditorText(currentData);
            updateSyntaxHighlight();
        }

        renderPreviewAll();
        renderAIFeedbackList();

        const previewQuestion = document.getElementById(`preview_q_${question_index}`);
        if (previewQuestion) {
            previewQuestion.scrollIntoView({ behavior: 'smooth', block: 'center' });
            previewQuestion.style.transition = 'background-color 1s ease';
            previewQuestion.style.backgroundColor = '#d1fae5'; // Nháy màu xanh lá cây
            setTimeout(() => {
                previewQuestion.style.backgroundColor = '';
            }, 2000);
        }
    } else {
        alert(`Lỗi: Không tìm thấy câu hỏi với chỉ số ${question_index}.`);
    }
}

function dismissAISuggestion(question_index) {
    delete window.activeAIFeedbacks[question_index];
    window.activeAINewQuizData = null;
    renderPreviewAll();
    renderAIFeedbackList();
}

function renderData() {
    const container = document.getElementById('quiz-container');
    container.innerHTML = '';
    if (currentData.length === 0) { container.innerHTML = "<div class='card'>Không tìm thấy câu hỏi nào. Vui lòng kiểm tra lại định dạng file Word.</div>"; return; }
    
    resetSubmissionReviewUI();
    
    // Mở rộng Container khi ở chế độ chỉnh sửa
    const mainAppContainer = document.getElementById('mainAppContainer');
    if (currentMode === 'edit') {
        mainAppContainer.classList.add('wide-container');
    } else {
        mainAppContainer.classList.remove('wide-container');
    }

    if (currentMode === 'edit') {
        container.innerHTML = `
            <!-- TAB CHUYỂN ĐỔI CHẾ ĐỘ XEM TRÊN ĐIỆN THOẠI (INDEX) -->
            <div class="index-mobile-editor-tabs" id="indexMobileEditorTabs">
                <button type="button" class="index-m-tab-btn active" id="idxTabCode" onclick="switchIndexMobileEditorTab('code')">
                    <i class="ri-code-s-slash-line"></i> Soạn thảo Code
                </button>
                <button type="button" class="index-m-tab-btn" id="idxTabPreview" onclick="switchIndexMobileEditorTab('preview')">
                    <i class="ri-eye-line"></i> Xem trước Học sinh
                </button>
            </div>
            <div class="split-layout idx-tab-code" id="indexSplitLayout">
                <div class="preview-pane" id="preview-pane" style="padding: 0;">
                    <div style="background: #f8fafc; padding: 15px 20px; font-weight: 700; color: #0f172a; border-bottom: 1px solid #e2e8f0; position: sticky; top: 0; z-index: 10; display: flex; justify-content: space-between; align-items: center;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 1.3rem;">👁️</span> XEM TRƯỚC (GIAO DIỆN HỌC SINH)
                        </div>
                    </div>
                    <div id="preview-content" style="padding: 20px;"></div>
                </div>
                <div class="editor-pane" id="editor-pane" style="display: flex; flex-direction: column; padding: 0; background: #ffffff; overflow: hidden; border: 1px solid #e2e8f0;">
                    <div style="background: #f8fafc; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 10; border-bottom: 1px solid #e2e8f0;">
                        <div style="font-weight: 700; color: #0f172a; display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 1.3rem;">💻</span> HOCNHANHTN CODE EDITOR
                        </div>
                        <div style="display: flex; gap: 10px;">
                            <button style="padding: 6px 14px; font-size: 0.85rem; font-weight: 600; background: #0e639c; border: none; color: white; border-radius: 4px; cursor: pointer; transition: background 0.2s;" onmouseover="this.style.background='#1177bb'" onmouseout="this.style.background='#0e639c'" onclick="insertTextToEditor('\\n\\nCâu mới: \\nA. \\nB. \\nC. \\nD. ')">➕ Thêm Câu hỏi</button>
                        </div>
                    </div>
                    <div style="background: #f1f5f9; padding: 10px 20px; font-size: 0.9rem; color: #334155; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; gap: 8px;">
                        <span>💡 <b>Mẹo:</b> Gõ <code>Câu</code> và nhấn <b>Tab</b> để tạo nhanh khung câu hỏi. Click câu hỏi bên trái để tự động cuộn đến đoạn Code tương ứng.</span>
                    </div>
                    <div style="flex-grow: 1; position: relative; background: #ffffff;">
                        <style>
                            .editor-font {
                                font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
                                font-size: 15px;
                                line-height: 1.8;
                                padding: 20px 20px 60px 20px;
                                box-sizing: border-box;
                                white-space: pre-wrap;
                                word-wrap: break-word;
                                margin: 0;
                                border: none;
                            }
                            #codeHighlight {
                                position: absolute;
                                top: 0; left: 0; right: 0; bottom: 0;
                                color: #333333;
                                overflow: hidden;
                                pointer-events: none;
                            }
                            #codeEditor {
                                position: absolute;
                                top: 0; left: 0; right: 0; bottom: 0;
                                background: transparent;
                                color: transparent;
                                caret-color: #000000;
                                resize: none;
                                outline: none;
                                overflow-y: auto;
                            }
                        #codeEditor::selection { background: rgba(0, 120, 215, 0.25); color: transparent; }
                            #codeEditor::-webkit-scrollbar { width: 14px; }
                            #codeEditor::-webkit-scrollbar-track { background: #f8fafc; }
                            #codeEditor::-webkit-scrollbar-thumb { background: #cbd5e1; border: 4px solid #f8fafc; border-radius: 8px; }
                            #codeEditor::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
                            
                            /* Syntax Colors (Chuẩn VS Code Light Theme) */
                            .hl-question { color: #0000ff; font-weight: bold; }
                            .hl-option { color: #af00db; font-weight: bold; }
                            .hl-correct { color: #059669; font-weight: bold; }
                            .hl-image { color: #a31515; }
                            .hl-math { color: #267f99; }
                            .hl-group { color: #795e26; font-weight: bold; }
                            .hl-html { color: #808080; }
                        </style>
                        <div id="codeHighlight" class="editor-font"></div>
                        <textarea id="codeEditor" class="editor-font" spellcheck="false"></textarea>
                    </div>
                </div>
            </div>
        `;
        const previewContent = document.getElementById('preview-content');
        const codeEditor = document.getElementById('codeEditor');

        codeEditor.value = dataToEditorText(currentData);
        updateSyntaxHighlight();
        renderPreviewAll();

        let editTimeout;
        codeEditor.addEventListener('input', function() {
            clearTimeout(editTimeout);
            editTimeout = setTimeout(() => {
                updateSyntaxHighlight(); // Đưa vào timeout để chống lag khi gõ nhanh (Debounce)
                currentData = parseEditorText(this.value);
                renderPreviewAll();
            }, 300);
        });
        
        codeEditor.addEventListener('scroll', function() {
            const codeHighlight = document.getElementById('codeHighlight');
            if (codeHighlight) {
                codeHighlight.scrollTop = this.scrollTop;
                codeHighlight.scrollLeft = this.scrollLeft;
            }
        });
        
        // TÍNH NĂNG AUTO-COMPLETE BẰNG PHÍM TAB
        codeEditor.addEventListener('keydown', function(e) {
            if (e.key === 'Tab') {
                e.preventDefault(); // Chặn hành vi chuyển tab mặc định của trình duyệt
                const start = this.selectionStart;
                const end = this.selectionEnd;
                
                if (start === end) {
                    const textBefore = this.value.substring(0, start);
                    // Bắt từ khóa "cau" hoặc "câu" ở cuối đoạn text (trước con trỏ)
                    const match = textBefore.match(/(?:^|\n)\s*(cau|câu)$/i);
                    
                    if (match) {
                        // Tự động tính số thứ tự câu tiếp theo
                        const qCount = (this.value.match(/^(?:Câu|Bài|Question|Q)\s*\d+/gim) || []).length + 1;
                        const snippet = `Câu ${qCount}: \nA. \nB. \nC. \nD. `;
                        const replaceStart = start - match[1].length;
                        
                        this.value = this.value.substring(0, replaceStart) + snippet + this.value.substring(end);
                        
                        // Đặt con trỏ chuột ngay sau chữ "Câu X: "
                        const newCursorPos = replaceStart + `Câu ${qCount}: `.length;
                        this.selectionStart = this.selectionEnd = newCursorPos;
                        
                        updateSyntaxHighlight();
                        currentData = parseEditorText(this.value);
                        renderPreviewAll();
                        return; // Kết thúc sớm nếu đã Auto-complete
                    }
                }
                
                // Nếu không gõ "Câu", thực hiện thụt lề (indent) 4 khoảng trắng như VS Code
                this.value = this.value.substring(0, start) + "    " + this.value.substring(end);
                this.selectionStart = this.selectionEnd = start + 4;
                updateSyntaxHighlight();
            }
        });
    } else if (currentMode === 'practice') {
        // CHẾ ĐỘ LUYỆN TẬP: HIỂN THỊ TỪNG CÂU MỘT (HẾT CÂU NÀY ĐẾN CÂU KHÁC)
        const examLayout = document.getElementById('azotaExamLayout');
        if (examLayout) examLayout.style.display = '';
        const sideCol = document.getElementById('azotaSideExamCol');
        if (sideCol) sideCol.style.display = '';

        const examLegends = document.querySelectorAll('.azota-nav-legend-exam');
        examLegends.forEach(el => el.style.setProperty('display', 'none', 'important'));
        const practiceStats = document.querySelectorAll('.azota-practice-stats');
        practiceStats.forEach(el => el.style.setProperty('display', 'grid', 'important'));
        const restartBtns = document.querySelectorAll('.btn-azota-restart-practice');
        restartBtns.forEach(btn => btn.style.setProperty('display', 'flex', 'important'));
        const submitNavBtns = document.querySelectorAll('.btn-azota-submit-big');
        submitNavBtns.forEach(btn => {
            btn.innerHTML = `<i class="ri-check-double-line"></i> NỘP BÀI & XEM TỔNG KẾT`;
        });

        renderPracticeQuestion();

    } else {
        // CHẾ ĐỘ THI THỬ (EXAM): HIỂN THỊ TOÀN BỘ CÂU HỎI CUỘN DỌC TỪ TRÊN XUỐNG DƯỚI
        const examLayout = document.getElementById('azotaExamLayout');
        if (examLayout) examLayout.style.display = '';
        const sideCol = document.getElementById('azotaSideExamCol');
        if (sideCol) sideCol.style.display = '';

        let htmlBuilder = "";
        let navGridHtml = "";
        let answeredCount = 0;

        currentData.forEach((q, qIndex) => {
            let groupTitleHtml = q.group_title ? `<div style="background: #fef9c3; padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; font-size: 0.9rem; font-weight: 600; color: #854d0e;">${formatRichContent(q.group_title)}</div>` : '';
            
            let qType = getRealQuestionType(q);
            let typeBadge = '';
            if (qType === 'true_false') {
                typeBadge = '<span style="background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; margin-left: 8px; border: 1px solid #bae6fd;">Đúng / Sai</span>';
            } else if (qType === 'short_answer') {
                typeBadge = '<span style="background: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; margin-left: 8px; border: 1px solid #fde68a;">Trả lời ngắn</span>';
            }

            let cleanQText = (q.question || '').replace(/^(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])\s*/i, '');
            let isFlagged = !!flaggedQuestions[qIndex];

            let boxHtml = `
                <div class="card question-box azota-question-card" id="question_box_${qIndex}">
                    ${groupTitleHtml}
                    <div class="azota-q-header">
                        <span class="azota-q-num">Câu ${qIndex + 1} ${typeBadge}</span>
                        <button type="button" class="btn-flag-q ${isFlagged ? 'flagged' : ''}" id="flag_btn_${qIndex}" onclick="toggleFlagQuestion(${qIndex})">
                            <i class="ri-flag-${isFlagged ? 'fill' : 'line'}"></i> ${isFlagged ? 'Đang phân vân' : 'Đánh dấu xem lại'}
                        </button>
                    </div>
                    <div class="question-title azota-q-text">${formatRichContent(cleanQText)}</div>
            `;

            let ansVal = quizProgress && quizProgress.answers ? quizProgress.answers[qIndex] : undefined;
            let isAnswered = ansVal !== undefined && ansVal !== '' && (typeof ansVal !== 'object' || Object.keys(ansVal).length > 0);
            if (isAnswered) answeredCount++;

            navGridHtml += `
                <button type="button" class="azota-nav-num nav-num-btn nav-num-${qIndex} ${isAnswered ? 'answered' : ''} ${isFlagged ? 'flagged' : ''}" id="nav_num_${qIndex}" data-qindex="${qIndex}" onclick="scrollToQuestion(${qIndex})" title="Chuyển đến Câu ${qIndex + 1}">
                    ${qIndex + 1}
                </button>
            `;

            if (qType === 'true_false') {
                boxHtml += `<div class="azota-tf-container">`;
                let userAnsObj = (quizProgress && quizProgress.answers && typeof quizProgress.answers[qIndex] === 'object') ? quizProgress.answers[qIndex] : {};
                (q.options || []).forEach((opt, oIndex) => {
                    let charMatch = opt.match(/^[a-d]/);
                    let char = charMatch ? charMatch[0].toLowerCase() : String.fromCharCode(97 + oIndex);
                    let optClean = opt.replace(/^[a-d][\.\:\)]\s*/, '');
                    let val = userAnsObj[char];
                    boxHtml += `
                        <div class="azota-tf-row" id="exam_tf_${qIndex}_${char}">
                            <div class="azota-tf-statement">
                                <span class="azota-tf-badge">${char}</span>
                                <span>${optClean}</span>
                            </div>
                            <div class="azota-tf-actions">
                                <button type="button" class="azota-tf-btn ${val === true ? 'selected-true' : ''}" onclick="selectExamTF(${qIndex}, '${char}', true)">Đúng</button>
                                <button type="button" class="azota-tf-btn ${val === false ? 'selected-false' : ''}" onclick="selectExamTF(${qIndex}, '${char}', false)">Sai</button>
                            </div>
                        </div>`;
                });
                boxHtml += `</div></div>`;
            } else if (qType === 'short_answer') {
                let userSA = (quizProgress && quizProgress.answers && typeof quizProgress.answers[qIndex] === 'string') ? quizProgress.answers[qIndex] : '';
                boxHtml += `
                    <div class="azota-sa-box" role="region" aria-label="Khu vực trả lời câu hỏi ngắn">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <span style="font-weight: 600; font-size: 0.9rem; color: var(--azota-text-muted);">✍️ Nhập câu trả lời ngắn:</span>
                            <span style="font-size: 0.78rem; color: #10b981; font-weight: 600;"><i class="ri-shield-check-line"></i> Bàn phím số an toàn</span>
                        </div>
                        <input type="text" class="azota-sa-input" id="exam_sa_${qIndex}" value="${escapeHtml(userSA)}" 
                               placeholder="Nhập đáp số (VD: 2.5 hoặc -10 hoặc 3/4)..." 
                               inputmode="decimal" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"
                               onkeydown="handleSaKeydown(event, this, 'exam_sa_${qIndex}_guard_warn')"
                               oninput="handleSaInput(event, this, ${qIndex}, 'sa_preview_${qIndex}')" 
                               aria-label="Câu trả lời ngắn cho câu ${qIndex + 1}">
                        <div class="azota-sa-guard-warn" id="exam_sa_${qIndex}_guard_warn">
                            <i class="ri-error-warning-fill"></i> Đã chặn ký tự lạ. Chế độ an toàn chỉ nhận số và phép tính toán học.
                        </div>
                        <div class="azota-math-preview ${userSA ? 'active' : ''}" id="sa_preview_${qIndex}">
                            <span class="preview-label">Xem trước:</span>
                            <span class="preview-render" id="sa_render_${qIndex}">${userSA ? '$' + escapeHtml(userSA) + '$' : ''}</span>
                        </div>
                        ${renderCustomKeypadHtml(`exam_sa_${qIndex}`, `sa_preview_${qIndex}`, qIndex)}
                    </div></div>`;
            } else {
                boxHtml += `<div class="azota-opt-list">`;
                (q.options || []).forEach((opt, oIndex) => {
                    let char = opt.match(/^[A-F]/i) ? opt.match(/^[A-F]/i)[0].toUpperCase() : String.fromCharCode(65 + oIndex);
                    let savedOpt = quizProgress && quizProgress.answers ? quizProgress.answers[qIndex] : null;
                    let isChecked = Boolean(savedOpt && (savedOpt === opt || matchOptionToTarget(opt, oIndex, savedOpt)));
                    boxHtml += `
                        <label class="option-practice azota-opt-item ${isChecked ? 'selected' : ''}" id="exam_opt_${qIndex}_${oIndex}">
                            <input type="radio" name="exam_${qIndex}" value="${escapeHtml(opt)}" onchange="selectExamOption(${qIndex}, ${oIndex})" ${isChecked ? 'checked' : ''} style="display:none;">
                            <span class="opt-badge azota-opt-badge">${char}</span>
                            <span class="opt-text">${opt.replace(/^[A-F][\.\:\)]\s*/i, '')}</span>
                        </label>`;
                });
                boxHtml += `</div></div>`;
            }
            htmlBuilder += boxHtml;
        });

        container.innerHTML = htmlBuilder;
        renderMath(container);

        const navGrid = document.getElementById('azotaNavGrid');
        if (navGrid) navGrid.innerHTML = navGridHtml;
        const mobileNavGrid = document.getElementById('azotaMobileNavGrid');
        if (mobileNavGrid) mobileNavGrid.innerHTML = navGridHtml;
        updateNavProgressBadge();

        const examLegends = document.querySelectorAll('.azota-nav-legend-exam');
        examLegends.forEach(el => el.style.setProperty('display', 'flex', 'important'));
        const practiceStats = document.querySelectorAll('.azota-practice-stats');
        practiceStats.forEach(el => el.style.setProperty('display', 'none', 'important'));
        const restartBtns = document.querySelectorAll('.btn-azota-restart-practice');
        restartBtns.forEach(btn => btn.style.setProperty('display', 'none', 'important'));
        const submitNavBtns = document.querySelectorAll('.btn-azota-submit-big');
        submitNavBtns.forEach(btn => {
            btn.innerHTML = `<i class="ri-check-double-line"></i> NỘP BÀI THI`;
        });
        const mobileNextBtn = document.getElementById('mobileNextBtn');
        if (mobileNextBtn) {
            mobileNextBtn.style.display = 'inline-flex';
            mobileNextBtn.innerHTML = 'Câu tiếp <i class="ri-arrow-down-line"></i>';
            mobileNextBtn.onclick = mobileNextQuestionAction;
        }
    }
    document.getElementById('aiCustomPrompt').style.display = currentMode === 'edit' ? 'block' : 'none';
    const qpIndexToggle = document.getElementById('aiQuickPromptsIndex');
    if (qpIndexToggle) qpIndexToggle.style.display = currentMode === 'edit' ? 'flex' : 'none';
    document.getElementById('btnAICheck').style.display = currentMode === 'edit' ? 'block' : 'none';
    if (currentMode !== 'edit') document.getElementById('aiFeedbackBox').style.display = 'none';
    const mobileBar = document.getElementById('azotaMobileExamBar');
    if (currentMode === 'edit') {
        const sideCol = document.getElementById('azotaSideExamCol');
        if (sideCol) sideCol.style.setProperty('display', 'none', 'important');
        if (mobileBar) mobileBar.style.display = 'none';
    } else {
        const sideCol = document.getElementById('azotaSideExamCol');
        if (sideCol) sideCol.style.display = '';
        if (mobileBar && currentMode !== 'edit') {
            if (window.innerWidth <= 960) {
                mobileBar.style.display = 'flex';
            } else {
                mobileBar.style.display = 'none';
            }
        }
    }
    const mainSubmit = document.getElementById('submitBtn');
    if (mainSubmit) mainSubmit.style.display = 'none';
}

// ========================================================
// HÀM XỬ LÝ CHẾ ĐỘ LUYỆN TẬP (TỪNG CÂU MỘT - HẾT CÂU NÀY ĐẾN CÂU KHÁC)
// ========================================================
function renderPracticeQuestion() {
    const container = document.getElementById('quiz-container');
    if (!container) return;
    container.innerHTML = '';

    if (currentQuestionIndex >= currentData.length) {
        submitExam();
        return;
    }

    const q = currentData[currentQuestionIndex];
    if (!q) return;

    const qType = getRealQuestionType(q);
    const savedStatus = q._practiceStatus || (quizProgress && quizProgress.practiceResults && quizProgress.practiceResults[currentQuestionIndex]);
    const hasAnswered = Boolean(savedStatus);
    const userAns = q.user_answer_practice || (quizProgress && quizProgress.answers && quizProgress.answers[currentQuestionIndex]);
    practiceAnswered = hasAnswered;
    window.currentPracticeTF = (typeof userAns === 'object' && userAns) ? { ...userAns } : {};

    const box = document.createElement('div');
    box.className = 'card question-box azota-question-card';
    box.id = `practice_box_${currentQuestionIndex}`;

    let groupTitleHtml = q.group_title ? `<div style="background: #fef9c3; padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; font-size: 0.9rem; font-weight: 600; color: #854d0e;">${formatRichContent(q.group_title)}</div>` : '';
    let typeBadge = '';
    if (qType === 'true_false') {
        typeBadge = '<span style="background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; margin-left: 8px; border: 1px solid #bae6fd;">Đúng / Sai</span>';
    } else if (qType === 'short_answer') {
        typeBadge = '<span style="background: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; margin-left: 8px; border: 1px solid #fde68a;">Trả lời ngắn</span>';
    }

    let cleanQText = (q.question || '').replace(/^(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])\s*/i, '');

    let innerHtml = `
        ${groupTitleHtml}
        <div class="azota-q-header">
            <span class="azota-q-num">Câu ${currentQuestionIndex + 1} / ${currentData.length} ${typeBadge}</span>
        </div>
        <div class="question-title azota-q-text">${formatRichContent(cleanQText)}</div>
    `;

    if (qType === 'true_false') {
        innerHtml += `<div class="azota-tf-container" style="margin-top: 15px;">`;
        const correctMap = (typeof q.correct_answer === 'object' && q.correct_answer) ? q.correct_answer : {};
        (q.options || []).forEach((opt, oIndex) => {
            let charMatch = opt.match(/^[a-d]/);
            let char = charMatch ? charMatch[0].toLowerCase() : String.fromCharCode(97 + oIndex);
            let optClean = opt.replace(/^[a-d][\.\:\)]\s*/, '');
            let isUserTrue = (window.currentPracticeTF[char] === true);
            let isUserFalse = (window.currentPracticeTF[char] === false);
            let correctVal = correctMap[char];

            let btnTClass = 'azota-tf-btn';
            let btnFClass = 'azota-tf-btn';
            if (hasAnswered) {
                if (correctVal === true) btnTClass += ' correct-state';
                else if (correctVal === false) btnFClass += ' correct-state';
                if (isUserTrue && correctVal !== true) btnTClass += ' wrong-state selected-true';
                else if (isUserTrue) btnTClass += ' selected-true';
                if (isUserFalse && correctVal !== false) btnFClass += ' wrong-state selected-false';
                else if (isUserFalse) btnFClass += ' selected-false';
            } else {
                if (isUserTrue) btnTClass += ' selected-true';
                if (isUserFalse) btnFClass += ' selected-false';
            }

            innerHtml += `
                <div class="azota-tf-row" id="pract_tf_${char}">
                    <div class="azota-tf-statement">
                        <span class="azota-tf-badge">${char}</span>
                        <span>${optClean}</span>
                    </div>
                    <div class="azota-tf-actions">
                        <button type="button" class="${btnTClass}" id="pract_tf_btn_${char}_t" ${hasAnswered ? 'disabled' : `onclick="selectPracticeTF('${char}', true)"`}>Đúng</button>
                        <button type="button" class="${btnFClass}" id="pract_tf_btn_${char}_f" ${hasAnswered ? 'disabled' : `onclick="selectPracticeTF('${char}', false)"`}>Sai</button>
                    </div>
                </div>`;
        });
        innerHtml += `</div>
        <div style="text-align: right; margin-top: 14px;">
            <button id="pract_tf_check_btn" class="btn-primary" style="${hasAnswered ? 'display:none;' : ''} padding: 10px 24px; font-size: 0.95rem; margin: 0;" onclick="checkPracticeTF()">Kiểm tra đáp án</button>
        </div>`;
    } else if (qType === 'short_answer') {
        const isCorrectSA = evaluateShortAnswerJS(userAns, q.correct_answer);

        innerHtml += `
            <div class="azota-sa-box" style="margin-top: 15px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-weight: 600; font-size: 0.9rem; color: var(--azota-text-muted);">✍️ Nhập câu trả lời ngắn của bạn:</span>
                    <span style="font-size: 0.78rem; color: #10b981; font-weight: 600;"><i class="ri-shield-check-line"></i> Bàn phím số an toàn</span>
                </div>
                <div style="display: flex; gap: 8px; margin-bottom: 8px;">
                    <input type="text" class="azota-sa-input ${hasAnswered ? (isCorrectSA ? 'correct' : 'incorrect') : ''}" 
                           id="pract_sa_input" 
                           value="${escapeHtml(String(userAns || ''))}" 
                           placeholder="Điền đáp số hoặc kết quả..." 
                           ${hasAnswered ? 'disabled' : ''} 
                           inputmode="decimal" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"
                           onkeydown="handleSaKeydown(event, this, 'pract_sa_guard_warn'); if(event.key==='Enter') checkPracticeShortAnswer();"
                           oninput="handleSaInput(event, this, currentQuestionIndex, 'pract_sa_preview')">
                    <button id="pract_sa_check_btn" class="btn-primary" style="${hasAnswered ? 'display:none;' : ''} margin: 0; padding: 10px 22px; flex-shrink: 0;" onclick="checkPracticeShortAnswer()">Kiểm tra</button>
                </div>
                <div class="azota-sa-guard-warn" id="pract_sa_guard_warn">
                    <i class="ri-error-warning-fill"></i> Đã chặn ký tự lạ. Chế độ an toàn chỉ nhận số và phép tính toán học.
                </div>
                <div class="azota-math-preview ${userAns ? 'active' : ''}" id="pract_sa_preview" style="${userAns ? 'display:flex;' : 'display:none;'}">
                    <span class="preview-label">Xem trước:</span>
                    <span class="preview-render" id="pract_sa_render">${userAns ? '$' + escapeHtml(String(userAns)) + '$' : ''}</span>
                </div>
                ${hasAnswered ? '' : renderCustomKeypadHtml('pract_sa_input', 'pract_sa_preview', currentQuestionIndex)}
            </div>`;
    } else {
        // MCQ Options xếp từng dòng từ trên xuống dưới
        innerHtml += `<div class="azota-opt-list" style="margin-top: 15px;">`;
        (q.options || []).forEach((opt, oIndex) => {
            let char = opt.match(/^[A-F]/i) ? opt.match(/^[A-F]/i)[0].toUpperCase() : String.fromCharCode(65 + oIndex);
            let isUserChosen = hasAnswered && (userAns === opt || matchOptionToTarget(opt, oIndex, userAns));
            let isCorrectOpt = matchOptionToTarget(opt, oIndex, q.correct_answer);

            let optClass = 'option-practice azota-opt-item';
            if (hasAnswered) {
                if (isUserChosen) optClass += ' selected';
                if (isCorrectOpt) optClass += ' correct';
                else if (isUserChosen && !isCorrectOpt) optClass += ' incorrect';
            }

            innerHtml += `
                <label class="${optClass}" id="pract_opt_${oIndex}" 
                       ${hasAnswered ? '' : `onclick="checkPracticeAnswer(${oIndex})"`} 
                       style="${hasAnswered ? 'cursor: default;' : 'cursor: pointer;'}">
                    <input type="radio" name="pract_radio" value="${escapeHtml(opt)}" ${hasAnswered ? 'disabled' : ''} ${isUserChosen ? 'checked' : ''} style="display:none;">
                    <span class="opt-badge azota-opt-badge">${char}</span>
                    <span class="opt-text">${opt.replace(/^[A-F][\.\:\)]\s*/i, '')}</span>
                </label>`;
        });
        innerHtml += `</div>`;
    }

    // Feedback area
    let feedbackContent = '';
    if (hasAnswered) {
        feedbackContent = renderPracticeFeedbackHtml(q, currentQuestionIndex);
    }
    innerHtml += `<div id="pract_feedback" class="pract-q-feedback">${feedbackContent}</div>`;

    box.innerHTML = innerHtml;
    container.appendChild(box);

    // Desktop Next Question Button bar
    const isLast = (currentQuestionIndex === currentData.length - 1);
    const btnWrapper = document.createElement('div');
    btnWrapper.style.display = 'flex';
    btnWrapper.style.justifyContent = 'flex-end';
    btnWrapper.style.marginTop = '14px';
    btnWrapper.style.paddingBottom = '30px';
    btnWrapper.innerHTML = `
        <button id="nextBtn" class="btn-primary desktop-only-submit" 
                style="${hasAnswered ? 'display:inline-flex;' : 'display:none;'} align-items:center; gap:8px; padding: 12px 28px; border-radius: 12px; font-weight: 700; font-size: 1rem; box-shadow: 0 4px 14px rgba(37,99,235,0.25);" 
                onclick="nextPracticeQuestion()">
            ${isLast ? 'Xem kết quả tổng kết <i class="ri-check-double-line"></i>' : 'Câu tiếp theo <i class="ri-arrow-right-line"></i>'}
        </button>
    `;
    container.appendChild(btnWrapper);

    renderMath(container);
    updatePracticeNavStatus();

    // Mobile next btn
    const mobileNextBtn = document.getElementById('mobileNextBtn');
    if (mobileNextBtn) {
        mobileNextBtn.style.display = 'inline-flex';
        mobileNextBtn.innerHTML = isLast ? 'Kết quả <i class="ri-check-double-line"></i>' : 'Câu tiếp <i class="ri-arrow-right-line"></i>';
        mobileNextBtn.onclick = mobileNextQuestionAction;
    }
}

function checkPracticeAnswer(oIndex) {
    if (practiceAnswered) return;
    practiceAnswered = true;

    const q = currentData[currentQuestionIndex];
    if (!q) return;
    const userAns = q.options[oIndex];
    q.user_answer_practice = userAns;
    const isCorrect = matchOptionToTarget(userAns, oIndex, q.correct_answer);
    q._practiceStatus = isCorrect ? 'correct' : 'wrong';

    if (isCorrect) practiceScore++;

    if (!quizProgress.practiceResults) quizProgress.practiceResults = {};
    quizProgress.practiceResults[currentQuestionIndex] = q._practiceStatus;
    if (!quizProgress.answers) quizProgress.answers = {};
    quizProgress.answers[currentQuestionIndex] = userAns;
    quizProgress.practiceIndex = currentQuestionIndex;
    quizProgress.practiceScore = practiceScore;
    if (isStudentMode) saveProgressToLocal();

    // Cập nhật giao diện các options
    q.options.forEach((opt, idx) => {
        const lbl = document.getElementById(`pract_opt_${idx}`);
        if (lbl) {
            lbl.onclick = null;
            lbl.style.cursor = 'default';
            const input = lbl.querySelector('input');
            if (input) input.disabled = true;
            if (idx === oIndex) lbl.classList.add('selected');
            if (matchOptionToTarget(opt, idx, q.correct_answer)) lbl.classList.add('correct');
            else if (idx === oIndex && !isCorrect) lbl.classList.add('incorrect');
        }
    });

    const feedback = document.getElementById('pract_feedback');
    if (feedback) {
        feedback.innerHTML = renderPracticeFeedbackHtml(q, currentQuestionIndex);
        renderMath(feedback);
        attachWebLLMTutorToFeedback(feedback, q, userAns, !isCorrect);
    }

    updatePracticeNavStatus();
    showNextQuestionButton();
}

function selectPracticeTF(char, isTrue) {
    if (!window.currentPracticeTF) window.currentPracticeTF = {};
    window.currentPracticeTF[char] = isTrue;

    const btnT = document.getElementById(`pract_tf_btn_${char}_t`);
    const btnF = document.getElementById(`pract_tf_btn_${char}_f`);
    if (btnT && btnF) {
        btnT.classList.toggle('selected-true', isTrue === true);
        btnF.classList.toggle('selected-false', isTrue === false);
    }
}

function checkPracticeTF() {
    if (practiceAnswered) return;
    practiceAnswered = true;

    const q = currentData[currentQuestionIndex];
    if (!q) return;
    const userAnswers = window.currentPracticeTF || {};
    q.user_answer_practice = userAnswers;
    const correctMap = (typeof q.correct_answer === 'object' && q.correct_answer) ? q.correct_answer : {};

    let matchCount = 0;
    const totalOpts = (q.options || []).length || 4;
    (q.options || []).forEach((opt, oIndex) => {
        let charMatch = opt.match(/^[a-d]/);
        let char = charMatch ? charMatch[0].toLowerCase() : String.fromCharCode(97 + oIndex);
        const btnT = document.getElementById(`pract_tf_btn_${char}_t`);
        const btnF = document.getElementById(`pract_tf_btn_${char}_f`);
        const isCorrectVal = correctMap[char];
        const userVal = userAnswers[char];
        const isMatched = (userVal !== undefined && Boolean(userVal) === Boolean(isCorrectVal));
        if (isMatched) matchCount++;

        if (btnT && btnF) {
            btnT.disabled = true;
            btnF.disabled = true;
            if (isCorrectVal === true) btnT.classList.add('correct-state');
            else if (isCorrectVal === false) btnF.classList.add('correct-state');
            if (userVal === true && !isMatched) btnT.classList.add('wrong-state');
            else if (userVal === false && !isMatched) btnF.classList.add('wrong-state');
        }
    });

    const checkBtn = document.getElementById('pract_tf_check_btn');
    if (checkBtn) checkBtn.disabled = true;

    // Bareme GDPT 2018
    const tfScale = [0.0, 0.1, 0.25, 0.5, 1.0];
    const earned = tfScale[matchCount] !== undefined ? tfScale[matchCount] : 0.0;
    practiceScore += earned;
    practiceScore = Math.round(practiceScore * 100) / 100;

    const isFullCorrect = (matchCount === totalOpts);
    q._practiceStatus = isFullCorrect ? 'correct' : 'wrong';

    if (!quizProgress.practiceResults) quizProgress.practiceResults = {};
    quizProgress.practiceResults[currentQuestionIndex] = q._practiceStatus;
    if (!quizProgress.answers) quizProgress.answers = {};
    quizProgress.answers[currentQuestionIndex] = userAnswers;
    quizProgress.practiceIndex = currentQuestionIndex;
    quizProgress.practiceScore = practiceScore;
    if (isStudentMode) saveProgressToLocal();

    const feedback = document.getElementById('pract_feedback');
    if (feedback) {
        feedback.innerHTML = renderPracticeFeedbackHtml(q, currentQuestionIndex, matchCount, earned);
        renderMath(feedback);
        attachWebLLMTutorToFeedback(feedback, q, userAnswers, !isFullCorrect);
    }

    updatePracticeNavStatus();
    showNextQuestionButton();
}

function checkPracticeShortAnswer() {
    if (practiceAnswered) return;
    practiceAnswered = true;

    const q = currentData[currentQuestionIndex];
    if (!q) return;
    const inputEl = document.getElementById('pract_sa_input');
    const userVal = inputEl ? inputEl.value.trim() : '';
    q.user_answer_practice = userVal;

    const isCorrect = evaluateShortAnswerJS(userVal, q.correct_answer);

    if (isCorrect) practiceScore += 1;
    if (inputEl) {
        inputEl.disabled = true;
        if (isCorrect) inputEl.classList.add('correct');
        else inputEl.classList.add('incorrect');
    }
    const checkBtn = document.getElementById('pract_sa_check_btn');
    if (checkBtn) checkBtn.disabled = true;

    q._practiceStatus = isCorrect ? 'correct' : 'wrong';

    if (!quizProgress.practiceResults) quizProgress.practiceResults = {};
    quizProgress.practiceResults[currentQuestionIndex] = q._practiceStatus;
    if (!quizProgress.answers) quizProgress.answers = {};
    quizProgress.answers[currentQuestionIndex] = userVal;
    quizProgress.practiceIndex = currentQuestionIndex;
    quizProgress.practiceScore = practiceScore;
    if (isStudentMode) saveProgressToLocal();

    const feedback = document.getElementById('pract_feedback');
    if (feedback) {
        feedback.innerHTML = renderPracticeFeedbackHtml(q, currentQuestionIndex, null, isCorrect ? 1 : 0);
        renderMath(feedback);
        attachWebLLMTutorToFeedback(feedback, q, userVal, !isCorrect);
    }

    updatePracticeNavStatus();
    showNextQuestionButton();
}

function nextPracticeQuestion() {
    if (currentQuestionIndex >= currentData.length - 1) {
        submitExam();
        return;
    }
    currentQuestionIndex++;
    if (isStudentMode && quizProgress) {
        quizProgress.practiceIndex = currentQuestionIndex;
        saveProgressToLocal();
    }
    renderPracticeQuestion();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function jumpToPracticeQuestion(qIndex) {
    if (qIndex < 0 || qIndex >= currentData.length) return;
    currentQuestionIndex = qIndex;
    if (isStudentMode && quizProgress) {
        quizProgress.practiceIndex = currentQuestionIndex;
        saveProgressToLocal();
    }
    toggleMobileNavSheet(false);
    renderPracticeQuestion();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderPracticeFeedbackHtml(q, qIndex, matchCount, earned) {
    const qType = getRealQuestionType(q);
    const status = q._practiceStatus || (quizProgress && quizProgress.practiceResults && quizProgress.practiceResults[qIndex]);
    let msgHtml = '';
    
    if (qType === 'true_false') {
        const mc = (matchCount !== undefined) ? matchCount : 0;
        const pts = (earned !== undefined) ? earned : (mc === 4 ? 1.0 : (mc === 3 ? 0.5 : (mc === 2 ? 0.25 : (mc === 1 ? 0.1 : 0))));
        msgHtml = `<div class="pract-feedback-msg ${mc === 4 ? 'correct' : 'wrong'}">
            <i class="${mc === 4 ? 'ri-checkbox-circle-fill' : 'ri-error-warning-fill'}"></i>
            <span>${mc === 4 ? '🎉 Đúng toàn bộ 4 ý (+1.0 điểm)!' : `📝 Bạn đúng ${mc}/4 ý (+${pts} điểm)`}</span>
        </div>`;
    } else if (qType === 'short_answer') {
        const isCorr = (status === 'correct');
        msgHtml = `<div class="pract-feedback-msg ${isCorr ? 'correct' : 'wrong'}">
            <i class="${isCorr ? 'ri-checkbox-circle-fill' : 'ri-close-circle-fill'}"></i>
            <span>${isCorr ? '✅ Trả lời chính xác (+1.0 điểm)!' : `❌ Chưa chính xác! Đáp án đúng là: <u>${escapeHtml(String(q.correct_answer || ''))}</u>`}</span>
        </div>`;
    } else {
        const isCorr = (status === 'correct');
        let correctAnswerDisplay = q.correct_answer ? q.correct_answer.replace(/^[A-F][\.\:\)]\s*/i, '') : "Chưa xác định";
        msgHtml = `<div class="pract-feedback-msg ${isCorr ? 'correct' : 'wrong'}">
            <i class="${isCorr ? 'ri-checkbox-circle-fill' : 'ri-close-circle-fill'}"></i>
            <span>${isCorr ? '✅ Trả lời chính xác!' : `❌ Sai rồi! Đáp án đúng là: <b>${escapeHtml(correctAnswerDisplay)}</b>`}</span>
        </div>`;
    }

    if (q.explain) {
        msgHtml += `<div class="pract-explain-box">💡 <b>Lời giải chi tiết:</b><br>${formatRichContent(q.explain)}</div>`;
    }
    return msgHtml;
}

function updatePracticeNavStatus() {
    let correctCount = 0;
    let wrongCount = 0;
    const totalCount = currentData ? currentData.length : 0;

    let navGridHtml = '';
    (currentData || []).forEach((q, idx) => {
        const status = q._practiceStatus || (quizProgress && quizProgress.practiceResults && quizProgress.practiceResults[idx]);
        let statusClass = 'unanswered';
        if (status === 'correct') {
            correctCount++;
            statusClass = 'practice-correct';
        } else if (status === 'wrong') {
            wrongCount++;
            statusClass = 'practice-wrong';
        }
        if (idx === currentQuestionIndex) {
            statusClass += ' practice-current';
        }

        navGridHtml += `
            <button type="button" class="azota-nav-num nav-num-btn nav-num-${idx} ${statusClass}" 
                    id="nav_num_${idx}" data-qindex="${idx}" 
                    onclick="jumpToPracticeQuestion(${idx})" 
                    title="Câu ${idx + 1}: ${status === 'correct' ? 'Đúng' : (status === 'wrong' ? 'Sai' : 'Chưa làm')}">
                ${idx + 1}
            </button>
        `;
    });

    const remainingCount = Math.max(0, totalCount - (correctCount + wrongCount));

    // Cập nhật DOM
    const navGrid = document.getElementById('azotaNavGrid');
    if (navGrid) navGrid.innerHTML = navGridHtml;
    const mobileNavGrid = document.getElementById('azotaMobileNavGrid');
    if (mobileNavGrid) mobileNavGrid.innerHTML = navGridHtml;

    // Cập nhật badge tiêu đề
    const navProgressBadge = document.getElementById('navProgressBadge');
    if (navProgressBadge) {
        navProgressBadge.innerText = `${correctCount + wrongCount}/${totalCount}`;
    }

    // Cập nhật các giá trị thống kê
    document.querySelectorAll('.p-stat-correct-val').forEach(el => el.innerText = correctCount);
    document.querySelectorAll('.p-stat-wrong-val').forEach(el => el.innerText = wrongCount);
    document.querySelectorAll('.p-stat-remaining-val').forEach(el => el.innerText = remainingCount);

    // Cập nhật mobile bar & sheet badge
    const mobileNavBadge = document.getElementById('mobileNavBadge');
    if (mobileNavBadge) {
        mobileNavBadge.innerHTML = `<span style="color:#10b981; font-weight:700;">${correctCount} Đúng</span> &bull; <span style="color:#ef4444; font-weight:700;">${wrongCount} Sai</span>`;
    }
    const mobileSheetBadge = document.getElementById('mobileSheetProgressBadge');
    if (mobileSheetBadge) {
        mobileSheetBadge.innerText = `${correctCount + wrongCount}/${totalCount}`;
    }

    const mobileNextBtn = document.getElementById('mobileNextBtn');
    if (mobileNextBtn) {
        const isLast = (currentQuestionIndex === currentData.length - 1);
        mobileNextBtn.innerHTML = isLast ? 'Kết quả <i class="ri-check-double-line"></i>' : 'Câu tiếp <i class="ri-arrow-right-line"></i>';
    }
}

function confirmRestartPractice() {
    const isDoing = (currentData || []).some(q => q._practiceStatus);
    const msg = isDoing 
        ? "Bạn có chắc chắn muốn làm lại bài luyện tập từ đầu không?\nToàn bộ kết quả câu đúng/sai hiện tại sẽ được làm mới."
        : "Làm lại bài luyện tập từ đầu?";
    if (!confirm(msg)) return;

    practiceScore = 0;
    currentQuestionIndex = 0;
    practiceAnswered = false;
    window.currentPracticeTF = {};
    (currentData || []).forEach(q => {
        delete q.user_answer_practice;
        delete q._practiceStatus;
    });

    if (quizProgress) {
        quizProgress.answers = {};
        quizProgress.practiceResults = {};
        quizProgress.practiceScore = 0;
        quizProgress.practiceIndex = 0;
        quizProgress.completed = false;
        quizProgress.startedAt = Date.now();
        if (isStudentMode) saveProgressToLocal();
    }

    toggleMobileNavSheet(false);
    renderPracticeQuestion();
    showToast("Đã làm mới bài luyện tập từ đầu!", "success");
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showPracticeReview() {
    submitExam(true);
}

// ========================================================
// HÀM XỬ LÝ LÀM BÀI TRONG CHẾ ĐỘ THI THỬ (EXAM) & ĐIỀU HƯỚNG
// ========================================================
function selectExamTF(qIndex, char, isTrue) {
    if (!quizProgress.answers) quizProgress.answers = {};
    if (typeof quizProgress.answers[qIndex] !== 'object' || quizProgress.answers[qIndex] === null) {
        quizProgress.answers[qIndex] = {};
    }
    quizProgress.answers[qIndex][char] = isTrue;
    
    const row = document.getElementById(`exam_tf_${qIndex}_${char}`);
    if (row) {
        const btns = row.querySelectorAll('.azota-tf-btn');
        if (btns.length >= 2) {
            btns[0].classList.toggle('selected-true', isTrue === true);
            btns[1].classList.toggle('selected-false', isTrue === false);
        }
    }
    if (isStudentMode) saveProgressToLocal();
    document.querySelectorAll(`.nav-num-${qIndex}`).forEach(btn => btn.classList.add('answered'));
    updateNavProgressBadge();
}
window.selectExamTF = selectExamTF;

function selectExamShortAnswer(qIndex, val) {
    if (!quizProgress.answers) quizProgress.answers = {};
    quizProgress.answers[qIndex] = val;
    if (isStudentMode) saveProgressToLocal();
    const isAnswered = val && val.trim();
    document.querySelectorAll(`.nav-num-${qIndex}`).forEach(btn => {
        if (isAnswered) btn.classList.add('answered');
        else btn.classList.remove('answered');
    });
    updateNavProgressBadge();
}
window.selectExamShortAnswer = selectExamShortAnswer;

function selectExamOption(qIndex, oIndex) {
    currentData[qIndex].options.forEach((_, idx) => {
        const lbl = document.getElementById(`exam_opt_${qIndex}_${idx}`);
        if (lbl) lbl.classList.remove('selected');
    });
    const selectedLbl = document.getElementById(`exam_opt_${qIndex}_${oIndex}`);
    if (selectedLbl) selectedLbl.classList.add('selected');
    
    if (!quizProgress.answers) quizProgress.answers = {};
    quizProgress.answers[qIndex] = currentData[qIndex].options[oIndex];
    if (isStudentMode) saveProgressToLocal();

    // Đánh dấu số câu tương ứng trên cả 2 Bảng câu hỏi (Desktop & Mobile)
    document.querySelectorAll(`.nav-num-${qIndex}`).forEach(btn => btn.classList.add('answered'));

    updateNavProgressBadge();
}
window.selectExamOption = selectExamOption;

function updateNavProgressBadge() {
    const answeredCount = Object.keys(quizProgress.answers || {}).length;
    const totalCount = currentData ? currentData.length : 0;
    const badge = document.getElementById('navProgressBadge');
    if (badge) badge.innerText = `${answeredCount}/${totalCount}`;
    
    const mobileBadge = document.getElementById('mobileNavBadge');
    if (mobileBadge) mobileBadge.innerText = `${answeredCount}/${totalCount} đã làm`;
    
    const mobileSheetBadge = document.getElementById('mobileSheetProgressBadge');
    if (mobileSheetBadge) mobileSheetBadge.innerText = `${answeredCount}/${totalCount}`;
}
window.updateNavProgressBadge = updateNavProgressBadge;

function toggleFlagQuestion(qIndex) {
    flaggedQuestions[qIndex] = !flaggedQuestions[qIndex];
    const isFlagged = flaggedQuestions[qIndex];
    const flagBtn = document.getElementById(`flag_btn_${qIndex}`);
    if (flagBtn) {
        if (isFlagged) {
            flagBtn.classList.add('flagged');
            flagBtn.innerHTML = `<i class="ri-flag-fill"></i> Đang phân vân`;
        } else {
            flagBtn.classList.remove('flagged');
            flagBtn.innerHTML = `<i class="ri-flag-line"></i> Đánh dấu xem lại`;
        }
    }
    document.querySelectorAll(`.nav-num-${qIndex}`).forEach(btn => {
        if (isFlagged) btn.classList.add('flagged');
        else btn.classList.remove('flagged');
    });

    // Lưu bền vững trạng thái phân vân vào LocalStorage để không bao giờ bị mất
    if (!quizProgress.flagged) quizProgress.flagged = {};
    quizProgress.flagged[qIndex] = isFlagged;
    if (typeof saveProgressToLocal === 'function') {
        saveProgressToLocal(false);
    }
}
window.toggleFlagQuestion = toggleFlagQuestion;

function scrollToQuestion(qIndex) {
    toggleMobileNavSheet(false);
    const qBox = document.getElementById(`question_box_${qIndex}`);
    if (qBox) {
        const header = document.getElementById('studentHeader');
        const headerHeight = (header && header.style.display !== 'none') ? header.offsetHeight : 60;
        const targetTop = qBox.getBoundingClientRect().top + window.pageYOffset - headerHeight - 12;
        window.scrollTo({
            top: targetTop,
            behavior: 'smooth'
        });
    }
}
window.scrollToQuestion = scrollToQuestion;

function toggleMobileNavSheet(isOpen) {
    const sheet = document.getElementById('azotaMobileNavSheet');
    const overlay = document.getElementById('azotaMobileNavOverlay');
    if (!sheet || !overlay) return;
    
    const shouldOpen = (isOpen !== undefined) ? isOpen : !sheet.classList.contains('open');
    if (shouldOpen) {
        sheet.classList.add('open');
        overlay.classList.add('open');
        document.body.style.overflow = 'hidden';
    } else {
        sheet.classList.remove('open');
        overlay.classList.remove('open');
        document.body.style.overflow = '';
    }
}
window.toggleMobileNavSheet = toggleMobileNavSheet;

function attachWebLLMTutorToFeedback(containerEl, q, userAnswer, isMistake) {
    if (!window.ENABLE_WEBLLM || !window.WebLLMTutor || !containerEl) return;
    
    const aiBox = document.createElement('div');
    aiBox.className = 'webllm-feedback-container';
    containerEl.appendChild(aiBox);
    
    const explainBtn = window.WebLLMTutor.createExplainButton(() => {
        window.WebLLMTutor.renderExplainCard(aiBox, q, userAnswer, isMistake);
        explainBtn.style.display = 'none';
    }, isMistake);
    
    containerEl.appendChild(explainBtn);
    
    // Tự động giải thích khi học sinh làm sai nếu bật cấu hình
    if (isMistake && window.WebLLMTutor.autoExplainOnMistake) {
        window.WebLLMTutor.renderExplainCard(aiBox, q, userAnswer, true);
        explainBtn.style.display = 'none';
    }
}
window.attachWebLLMTutorToFeedback = attachWebLLMTutorToFeedback;

function shuffleQuiz(noRender = false) {
    // QUAN TRỌNG: Ghi nhớ chỉ số gốc TRƯỚC khi trộn để submitExam gửi đúng index cho server
    // Chỉ gán lần đầu (nếu chưa có), tránh ghi đè khi người dùng trộn lại nhiều lần
    currentData.forEach((q, idx) => {
        if (q._originalIndex === undefined) q._originalIndex = idx;
        if (!q._originalOptions && Array.isArray(q.options)) q._originalOptions = [...q.options];
        if (q._originalCorrectAnswer === undefined) q._originalCorrectAnswer = q.correct_answer;
    });

    for (let i = currentData.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [currentData[i], currentData[j]] = [currentData[j], currentData[i]];
    }
    currentData.forEach(q => {
        // 1. Chuẩn hóa lại số thứ tự câu hỏi (Xóa "Câu X:" cũ nếu có)
        q.question = q.question.replace(/^(?:(?:Câu|Bài|Question|Q)\s*\d+\s*[\.\:\-\)]|\d+\s*[\.\:\)])\s*/i, '');
        
        // 2. Chỉ trộn ngẫu nhiên các đáp án cho dạng câu hỏi MCQ có options
        const isMcq = (!q.type || q.type === 'mcq') && Array.isArray(q.options) && q.options.length > 0;
        if (isMcq) {
            // Xác định chính xác đáp án đúng TRƯỚC khi trộn
            let originalCorrectIndex = -1;
            q.options.forEach((opt, idx) => {
                 if (matchOptionToTarget(opt, idx, q.correct_answer)) originalCorrectIndex = idx;
            });
            if (originalCorrectIndex === -1 && /^[A-D]$/i.test(q.correct_answer)) {
                originalCorrectIndex = q.correct_answer.toUpperCase().charCodeAt(0) - 65;
            }
            if (originalCorrectIndex === -1 && /^\d+$/.test(q.correct_answer)) {
                let parsedIdx = parseInt(q.correct_answer, 10);
                if (parsedIdx >= 0 && parsedIdx < q.options.length) {
                    originalCorrectIndex = parsedIdx;
                }
            }
            let correctTextContent = originalCorrectIndex >= 0 && originalCorrectIndex < q.options.length ? q.options[originalCorrectIndex] : null;

            for (let i = q.options.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [q.options[i], q.options[j]] = [q.options[j], q.options[i]];
            }
            
            // 3. Đánh lại nhãn A, B, C, D và cập nhật đáp án đúng theo vị trí mới
            let newCorrect = null;
            q.options = q.options.map((opt, oIndex) => {
                let isThisCorrect = (correctTextContent !== null && opt === correctTextContent);
                let cleanOpt = opt.replace(/^[A-F][\.\:\)]\s*/i, '');
                let newOpt = String.fromCharCode(65 + oIndex) + ". " + cleanOpt;
                if (isThisCorrect) newCorrect = newOpt;
                return newOpt;
            });
            if (newCorrect) q.correct_answer = newCorrect;
        }
    });
    currentQuestionIndex = 0;
    practiceScore = 0;
    if (!noRender) renderData();
}


function switchMode(mode, isResuming = false) {
    currentMode = mode;
    document.getElementById('btnEdit').className = mode === 'edit' ? 'btn-outline active' : 'btn-outline';
    document.getElementById('btnPractice').className = mode === 'practice' ? 'btn-outline active' : 'btn-outline';
    document.getElementById('btnExam').className = mode === 'exam' ? 'btn-outline active' : 'btn-outline';
    document.getElementById('btnShuffle').style.display = mode === 'edit' ? 'none' : 'inline-block';
    
    // Dọn dẹp các thành phần sau nộp bài và timer khi chuyển chế độ hoặc làm lại bài
    resetSubmissionReviewUI();
    clearInterval(timerInterval);

    if (mode === 'exam') {
        if (document.body.classList.contains('minimal-mode') && !document.body.classList.contains('quiz-completed')) {
            initExamAntiCheat();
            const qId = getCurrentQuizId();
            if (qId) initExamSessionUnique(qId);
        }
    } else {
        // Chế độ Luyện tập hoặc Sửa: Tắt toàn bộ chống gian lận
        destroyExamAntiCheat();
        destroyExamSessionUnique();
    }
    const timerDisplay = document.getElementById('timerDisplay');
    if (timerDisplay) timerDisplay.style.display = 'none';
    if (isStudentMode) {
        if (!isResuming || !quizProgress.startedAt) {
            startTime = Date.now();
            quizProgress.startedAt = startTime;
        } else {
            startTime = quizProgress.startedAt;
        }
        quizProgress.completed = false;
    }
    if (!isResuming) {
        currentQuestionIndex = 0;
        practiceScore = 0;
    } else {
        currentQuestionIndex = quizProgress.practiceIndex || 0;
        practiceScore = quizProgress.practiceScore || 0;
    }
    if (window.ENABLE_WEBLLM && mode === 'practice' && window.WebLLMTutor) {
        window.WebLLMTutor.preload();
    }
    const idxFloatBtn = document.getElementById('indexMobileFloatToggle');
    if (idxFloatBtn) {
        idxFloatBtn.style.display = (mode === 'edit' && window.innerWidth <= 860) ? 'inline-flex' : 'none';
    }
    renderData();
}

// ----------------------------------------------------
// HÀM NHẬN DIỆN LOẠI CÂU HỎI CHUẨN XÁC 100% (CHUẨN GDPT 2018)
// ----------------------------------------------------
function getRealQuestionType(q) {
    if (!q) return 'mcq';
    const opts = Array.isArray(q.options) ? q.options : [];
    const mcqCount = opts.filter(o => /^\s*(?:(?:<MARK>\s*|<u>\s*)*\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*(?:<\/MARK>\s*|<\/u>\s*)*)?(?:<MARK>\s*|<u>\s*)*(?:\*\s*)?\(?\[?(\*?[A-F])(?:\s*<\/u>)*(?:\s*<\/MARK>)*[\.\:\)]/.test(String(o).trim())).length;
    const tfCount = opts.filter(o => /^\s*(?:(?:<MARK>\s*|<u>\s*)*\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*(?:<\/MARK>\s*|<\/u>\s*)*)?(?:<MARK>\s*|<u>\s*)*(?:\*\s*)?\(?\[?(\*?[a-d])(?:\s*<\/u>)*(?:\s*<\/MARK>)*[\)\.\:\-\]\/]/.test(String(o).trim())).length;

    // 1. Nếu có từ 2 phương án chữ in hoa A, B, C, D trở lên -> 100% BẮT BUỘC là MCQ
    if (mcqCount >= 2 && mcqCount >= tfCount) return 'mcq';
    // 2. Nếu có từ 2 ý chữ thường a), b), c), d) trở lên -> 100% BẮT BUỘC là Đúng / Sai
    if (tfCount >= 2 && tfCount > mcqCount) return 'true_false';

    // 3. Nếu là loại câu hỏi đã chỉ định rõ ràng và không mâu thuẫn với phương án
    const t = String(q.type || '').toLowerCase();
    if (t === 'true_false' || t === 'tf' || t === 'dung_sai') {
        if (mcqCount === 0) return 'true_false';
    }
    if (t === 'short_answer' || t === 'sa' || t === 'tra_loi_ngan') {
        if (mcqCount === 0 && tfCount < 2) return 'short_answer';
    }
    if (t === 'mcq') return 'mcq';

    // 4. Nếu có đáp án dạng object Đúng/Sai và không có phương án A-D
    if (typeof q.correct_answer === 'object' && q.correct_answer !== null && Object.keys(q.correct_answer).length > 0) {
        if (mcqCount === 0) return 'true_false';
    }

    // 5. Nếu không có phương án nào và có đáp án chuỗi -> Trả lời ngắn
    if (opts.length === 0 && q.correct_answer) return 'short_answer';

    return 'mcq';
}

function dataToEditorText(data) {
    let text = "";
    data.forEach((q, i) => {
        if (q.group_title && (i === 0 || q.group_title !== data[i-1].group_title)) {
            text += `${q.group_title.replace(/<br>/gi, '\n')}\n`;
        }
        let qClean = (q.question || '').replace(/^(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])\s*/i, '').replace(/<br>/gi, '\n');
        text += `Câu ${i + 1}: ${qClean}\n`;
        
        let qType = getRealQuestionType(q);
        if (qType === 'true_false') {
            let tfMap = (typeof q.correct_answer === 'object' && q.correct_answer !== null) ? q.correct_answer : {};
            (q.options || []).forEach((opt, oIdx) => {
                let optText = opt.replace(/<br>/gi, '\n');
                let charMatch = optText.match(/^[a-d]/);
                let char = charMatch ? charMatch[0].toLowerCase() : String.fromCharCode(97 + oIdx);
                let isTrue = (char && tfMap[char] === true) || /^\*[a-d]/.test(optText) || /\[ĐÚNG\]|\(Đúng\)/i.test(optText);
                let cleanOpt = optText.replace(/^\*?[a-d][\)\.\:\-]\s*/, '');
                cleanOpt = cleanOpt.replace(/\[(ĐÚNG|SAI|Đ|S)\]|\((Đúng|Sai|Đ|S)\)/gi, '').trim();
                let prefix = isTrue ? `*${char}) ` : `${char}) `;
                text += `${prefix}${cleanOpt}\n`;
            });
        } else if (qType === 'short_answer') {
            let ca = (q.correct_answer !== undefined && q.correct_answer !== null) ? String(q.correct_answer).trim() : '';
            if (ca) {
                text += `Đáp án: ${ca}\n`;
            }
        } else {
            // MCQ (4 lựa chọn)
            (q.options || []).forEach((opt) => {
                let isCorrect = matchOptionToTarget(opt, 0, q.correct_answer);
                if (!isCorrect && typeof q.correct_answer === 'string' && q.correct_answer.trim()) {
                    let caLetter = (q.correct_answer.trim().match(/\b([A-F])\b/i) || [])[1];
                    let optLetter = (opt.trim().match(/^[A-F]/) || [])[0];
                    if (caLetter && optLetter && caLetter.toUpperCase() === optLetter.toUpperCase()) {
                        isCorrect = true;
                    }
                }
                let optText = opt.replace(/<br>/gi, '\n');
                if (isCorrect) {
                    optText = optText.replace(/^([A-F])([\.\:\)])/, '*$1$2'); // Đánh dấu sao cho đáp án đúng
                }
                text += `${optText}\n`;
            });
        }
        if (q.explain && q.explain.trim()) {
            text += `Lời giải: ${q.explain.replace(/<br>/gi, '\n')}\n`;
        }
        text += "\n";
    });
    
    text = text.trim();
    
    // Xóa bộ nhớ cũ mỗi lần generate lại code cho editor
    globalEditorImageStorage = {};
    globalEditorImageCounter = 0;
    
    // Tìm toàn bộ thẻ <img> (Base64 hoặc URL /api/images/...) và thay bằng [HÌNH_ẢNH_X]
    const imgRegex = /<img[^>]+src=['"][^'"]+['"][^>]*\/?>/gi;
    text = text.replace(imgRegex, (match) => {
        let existingKey = Object.keys(globalEditorImageStorage).find(key => globalEditorImageStorage[key] === match);
        if (existingKey) return existingKey;
        
        globalEditorImageCounter++;
        let placeholder = `[HÌNH_ẢNH_${globalEditorImageCounter}]`;
        globalEditorImageStorage[placeholder] = match;
        return placeholder;
    });
    
    return text;
}

function parseEditorText(text) {
    // Trả lại mã Base64 thật cho các thẻ [HÌNH_ẢNH_X] trước khi bóc tách
    let restoredText = text;
    for (let key in globalEditorImageStorage) {
        restoredText = restoredText.split(key).join(globalEditorImageStorage[key]);
    }
    
    const data = [];
    let currentQ = null;
    const lines = restoredText.split('\n');
    let sharedContext = "";

    const qRegex = /^\s*(Câu|Bài|Question|Q)\s*\d+[\.\:\-\)]/i;
    // Phương án Trắc nghiệm nhiều lựa chọn (MCQ): BẮT BUỘC là CHỮ IN HOA A-F (A., B., C., D. hoặc A), B), C), D))
    const mcqOptRegex = /^\s*(?:(?:<MARK>\s*|<u>\s*)*\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*(?:<\/MARK>\s*|<\/u>\s*)*)?(?:<MARK>\s*|<u>\s*)*(?:\*\s*)?\(?\[?(\*?[A-F])(?:\s*<\/u>)*(?:\s*<\/MARK>)*[\.\:\)]/;
    // Phương án Trắc nghiệm Đúng / Sai (TF): BẮT BUỘC là CHỮ THƯỜNG a-d (a), b), c), d) hoặc a., b., c., d.)
    const tfOptRegex = /^\s*(?:(?:<MARK>\s*|<u>\s*)*\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*(?:<\/MARK>\s*|<\/u>\s*)*)?(?:<MARK>\s*|<u>\s*)*(?:\*\s*)?\(?\[?(\*?[a-d])(?:\s*<\/u>)*(?:\s*<\/MARK>)*[\)\.\:\-\]\/]/;
    const shortAnsRegex = /^\s*(?:Đáp án|Đáp số|ĐS|Kết quả|Ans|Answer)\s*[\:\-\=]\s*(.*)$/i;
    const explainRegex = /^\s*(?:Lời giải|Hướng dẫn giải|Giải thích|HDG|Explain)\s*[\:\-\=]\s*(.*)$/i;
    const groupRegex = /^\s*(PHẦN|PART|CHƯƠNG|BÀI TẬP|I{1,3}\.|IV\.|V\.|VI{0,3}\.)\b/i;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();
        
        if (trimmed === '') continue;

        if (qRegex.test(line)) {
            if (currentQ) data.push(currentQ);
            let qText = line.replace(qRegex, '').trim();
            currentQ = { type: 'mcq', group_title: sharedContext.trim(), question: qText, options: [], correct_answer: null, explain: '' };
            sharedContext = ""; 
        } else if (mcqOptRegex.test(line)) {
            // 1. ƯU TIÊN TUYỆT ĐỐI CHO MCQ KHI PHƯƠNG ÁN LÀ CHỮ IN HOA A, B, C, D
            if (!currentQ) {
                currentQ = { type: 'mcq', group_title: sharedContext.trim(), question: '', options: [], correct_answer: null, explain: '' };
                sharedContext = "";
            }
            currentQ.type = 'mcq';
            const match = line.match(mcqOptRegex);
            const charRaw = match[1].trim().toUpperCase();
            const char = charRaw.replace('*', '').trim();
            
            // Nhận diện đáp án đúng MCQ: dấu *, thẻ <u>, thẻ <MARK>, tick, nhãn [ĐÚNG]
            const isCorrect = charRaw.includes('*')
                || /<\/?(?:MARK|u)>/i.test(line)
                || /[✓✔☑]/i.test(line)
                || /\[(ĐÚNG|DUNG|Đ|TRUE|T)\]|\((Đúng|Dung|Đ|True|T)\)/i.test(line);

            let optContent = line.replace(mcqOptRegex, '').trim();
            let cleanContent = optContent.replace(/<\/?(?:MARK|u)>/gi, '')
                                         .replace(/\[(ĐÚNG|DUNG|SAI|Đ|S|TRUE|FALSE|T|F)\]|\((Đúng|Dung|Sai|Đ|S|True|False|T|F)\)|[✓✔☑✗✘]/gi, '')
                                         .trim();
            
            const fullOpt = `${char}. ${cleanContent}`;
            currentQ.options.push(fullOpt);
            if (isCorrect) currentQ.correct_answer = fullOpt;
        } else if (tfOptRegex.test(line)) {
            // 2. DẠNG ĐÚNG / SAI KHI PHƯƠNG ÁN LÀ CHỮ THƯỜNG a), b), c), d)
            if (!currentQ) {
                currentQ = { type: 'true_false', group_title: sharedContext.trim(), question: '', options: [], correct_answer: {}, explain: '' };
                sharedContext = "";
            }
            currentQ.type = 'true_false';
            if (typeof currentQ.correct_answer !== 'object' || currentQ.correct_answer === null) {
                currentQ.correct_answer = {};
            }
            const match = line.match(tfOptRegex);
            const charRaw = match[1].trim().toLowerCase();
            const char = charRaw.replace('*', '').trim();
            
            // Nhận diện đánh dấu Đúng/Sai theo chuẩn HocNhanhTN Cách 3 (gạch chân, *, thẻ <MARK>, tick)
            const isLeadingStar = charRaw.includes('*') || /^\s*[\(\[]?\s*\*\s*[a-d]/.test(line);
            const isUnderlined = /<\/?u>/i.test(line);
            const isMarked = /<\/?MARK>/i.test(line);
            const hasCorrectTag = /\[(ĐÚNG|DUNG|Đ|TRUE|T)\]|\((Đúng|Dung|Đ|True|T)\)|[✓✔☑]/i.test(line);
            const hasFalseTag = /\[(SAI|S|FALSE|F)\]|\((Sai|S|False|F)\)|[✗✘]/i.test(line);
            
            let isTrue = isLeadingStar || isUnderlined || isMarked || hasCorrectTag;
            if (hasFalseTag) isTrue = false;

            // Làm sạch nội dung phương án và giữ lại nhãn ma trận HocNhanhTN nếu có
            let optContent = line.replace(/\[(ĐÚNG|DUNG|SAI|Đ|S|TRUE|FALSE|T|F)\]|\((Đúng|Dung|Sai|Đ|S|True|False|T|F)\)|[✓✔☑✗✘]/gi, '').trim();
            let azotaTag = "";
            const mTag = optContent.match(/^\s*(?:<MARK>\s*|<u>\s*)*(\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\])\s*(?:<\/MARK>\s*|<\/u>\s*)*/i);
            if (mTag) {
                azotaTag = mTag[1].trim();
                optContent = optContent.substring(mTag[0].length).trim();
            }
            optContent = optContent.replace(/^\s*(?:<MARK>\s*)*(?:<u>\s*)*(?:\*\s*)?[\(\[]?[a-d](?:\s*<\/u>)*(?:\s*<\/MARK>)*[\)\.\:\-\]\/](?:\s*<\/u>)*(?:\s*<\/MARK>)*\s*/, '').trim();
            if (!azotaTag) {
                const mTagPost = optContent.match(/^\s*(\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\])\s*(.*)/i);
                if (mTagPost) {
                    azotaTag = mTagPost[1].trim();
                    optContent = mTagPost[2].trim();
                }
            }
            optContent = optContent.replace(/<\/?(?:MARK|u)>/gi, '').replace(/^\*+\s*/g, '').trim();
            if (azotaTag) {
                optContent = `${azotaTag} ${optContent}`.trim();
            }

            const fullOpt = `${char}) ${optContent}`;
            currentQ.options.push(fullOpt);
            currentQ.correct_answer[char] = isTrue;
        } else if (currentQ && currentQ.type === 'true_false' && (trimmed.match(/\b(Đ|S|Đúng|Sai|True|False)\b/gi) || []).length === 4) {
            // Chuỗi 4 chữ Đ/S từ bảng đáp án ngang HocNhanhTN
            const seq = trimmed.match(/\b(Đ|S|Đúng|Sai|True|False)\b/gi);
            ['a', 'b', 'c', 'd'].forEach((k, idx) => {
                currentQ.correct_answer[k] = ['đ', 'đúng', 'true'].includes(seq[idx].toLowerCase());
            });
        } else if (shortAnsRegex.test(line)) {
            if (currentQ) {
                const ansMatch = line.match(shortAnsRegex);
                const ansContent = (ansMatch[1] || "").trim();

                const mcqOptsCount = (currentQ.options || []).filter(opt => /^\s*(?:(?:<MARK>\s*|<u>\s*)*\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*(?:<\/MARK>\s*|<\/u>\s*)*)?(?:<MARK>\s*|<u>\s*)*(?:\*\s*)?\(?\[?(\*?[A-F])(?:\s*<\/u>)*(?:\s*<\/MARK>)*[\.\:\)]/.test(opt)).length;
                const tfOptsCount = (currentQ.options || []).filter(opt => /^\s*(?:(?:<MARK>\s*|<u>\s*)*\[\s*\d*\s*\,?\s*(?:NB|TH|VD|VDC)\s*\]\s*(?:<\/MARK>\s*|<\/u>\s*)*)?(?:<MARK>\s*|<u>\s*)*(?:\*\s*)?\(?\[?(\*?[a-d])(?:\s*<\/u>)*(?:\s*<\/MARK>)*[\)\.\:\-\]\/]/.test(opt)).length;

                const isTfAns = /(?:[a-d][\.\:\)\/\-\s]*(?:Đ|S|Đúng|Sai)|(?:Đ|S|Đúng|Sai)\s*[\,\;\-]\s*(?:Đ|S|Đúng|Sai))/i.test(ansContent)
                    || ((ansContent.match(/\b(Đ|S|Đúng|Sai)\b/gi) || []).length >= 3);

                if (mcqOptsCount >= 2 || (currentQ.type === 'mcq' && currentQ.options.length >= 2)) {
                    // ƯU TIÊN TUYỆT ĐỐI CHO MCQ: KHÔNG BAO GIỜ CHUYỂN SANG ĐÚNG/SAI HAY TRẢ LỜI NGẮN
                    currentQ.type = 'mcq';
                    const letterM = ansContent.match(/(?:^|[\s\:\.\(\[\,])([A-F])(?:[\.\:\)\s\-\]\,]|$)/i);
                    if (letterM) {
                        const targetLetter = letterM[1].toUpperCase();
                        const matchedOpt = currentQ.options.find(opt => opt.trim().toUpperCase().startsWith(targetLetter + '.') || opt.trim().toUpperCase().startsWith(targetLetter + ')'));
                        if (matchedOpt) {
                            currentQ.correct_answer = matchedOpt;
                        }
                    } else {
                        const matchedOpt = currentQ.options.find(opt => opt.toLowerCase().includes(ansContent.toLowerCase()));
                        if (matchedOpt) {
                            currentQ.correct_answer = matchedOpt;
                        }
                    }
                } else if (isTfAns || tfOptsCount >= 2 || currentQ.type === 'true_false') {
                    currentQ.type = 'true_false';
                    const tfDict = (typeof currentQ.correct_answer === 'object' && currentQ.correct_answer !== null) ? currentQ.correct_answer : { a: true, b: false, c: true, d: false };
                    ['a', 'b', 'c', 'd'].forEach(k => {
                        const m = ansContent.match(new RegExp("(?:^|[\\s,;\\(\\[])" + k + "[\\.\\:\\-\\)\\s=]*([^\\s,;\\/]+)", "i"));
                        if (m) {
                            const v = m[1].toLowerCase();
                            tfDict[k] = ['đ', 'đúng', 'dung', 'true', 't', '1'].includes(v);
                        }
                    });
                    const seq = ansContent.match(/\b(Đ|S|Đúng|Sai|True|False)\b/gi);
                    if (seq && seq.length === 4) {
                        ['a', 'b', 'c', 'd'].forEach((k, idx) => {
                            tfDict[k] = ['đ', 'đúng', 'true'].includes(seq[idx].toLowerCase());
                        });
                    }
                    currentQ.correct_answer = tfDict;
                } else {
                    currentQ.type = 'short_answer';
                    currentQ.options = [];
                    currentQ.correct_answer = ansContent;
                }
            }
        } else if (explainRegex.test(line)) {
            if (currentQ) {
                const expMatch = line.match(explainRegex);
                currentQ.explain = (currentQ.explain ? currentQ.explain + "<br>" : "") + expMatch[1].trim();
            }
        } else if (groupRegex.test(line)) {
            sharedContext += (sharedContext ? "<br>" : "") + line;
        } else {
            if (currentQ && currentQ.explain) {
                currentQ.explain += "<br>" + line;
            } else if (currentQ && currentQ.options.length > 0) {
                currentQ.options[currentQ.options.length - 1] += "<br>" + line;
            } else if (currentQ) {
                currentQ.question += (currentQ.question ? "<br>" : "") + line;
            } else {
                sharedContext += (sharedContext ? "<br>" : "") + line;
            }
        }
    }
    if (currentQ) data.push(currentQ);
    
    // Chuẩn hóa loại câu hỏi và đáp án mặc định
    data.forEach(q => {
        const realType = getRealQuestionType(q);
        q.type = realType;
        if (realType === 'mcq') {
            if (!q.correct_answer || typeof q.correct_answer === 'object') {
                q.correct_answer = q.options[0] || null;
            }
        } else if (realType === 'true_false') {
            if (typeof q.correct_answer !== 'object' || !q.correct_answer) {
                q.correct_answer = { a: true, b: false, c: true, d: false };
            }
        } else if (realType === 'short_answer') {
            q.options = [];
            if (!q.correct_answer) q.correct_answer = "";
        }
    });
    return data;
}

function renderPreviewAll() {
    const previewContent = document.getElementById('preview-content');
    if (!previewContent) return;
    previewContent.innerHTML = '';
    
    currentData.forEach((q, qIndex) => {
        const prevBox = document.createElement('div');
        prevBox.className = 'question-box';
        prevBox.id = `preview_q_${qIndex}`;
        prevBox.style.marginBottom = '24px';
        prevBox.style.cursor = 'pointer';
        prevBox.title = 'Nhấn để nhảy tới mã Code của câu này';
        prevBox.onclick = () => scrollToQuestionInEditor(qIndex);
        
        let hasError = window.activeAIFeedbacks && window.activeAIFeedbacks[qIndex];
        if (hasError) {
            prevBox.style.borderColor = '#c084fc';
            prevBox.style.boxShadow = '0 4px 12px rgba(147, 51, 234, 0.08)';
        }

        let html = "";
        let groupTitleHtml = q.group_title ? `<div style="background: #fef9c3; padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; font-size: 0.9rem; font-weight: 600; color: #854d0e;">${q.group_title.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>` : '';
        let qClean = (q.question || '').replace(/^(?:(?:Câu|Bài|Question|Q)\s*\d+\s*[\.\:\-\)]|\d+\s*[\.\:\)])\s*/i, '');
        
        let qType = getRealQuestionType(q);
        let typeBadge = '';
        if (qType === 'true_false') {
            typeBadge = '<span style="background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; margin-left: 8px; border: 1px solid #bae6fd;">Đúng / Sai</span>';
        } else if (qType === 'short_answer') {
            typeBadge = '<span style="background: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; margin-left: 8px; border: 1px solid #fde68a;">Trả lời ngắn</span>';
        }

        let aiSuggestedBadge = '';
        if (q.is_ai_suggested) {
            aiSuggestedBadge = `
                <span class="badge-ai-suggested" style="background: #fffbeb; color: #b45309; border: 1px solid #f59e0b; padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; margin-left: 8px; display: inline-flex; align-items: center; gap: 4px;" title="${escapeHtml(q.ai_suggestion_note || 'AI đề xuất, cần giáo viên xác nhận')}">
                    <i class="ri-sparkling-fill" style="color: #d97706;"></i> AI đề xuất, cần giáo viên xác nhận
                    <button type="button" onclick="confirmAISuggestedAnswer(${qIndex}, event)" style="margin-left: 6px; background: #d97706; color: #fff; border: none; border-radius: 4px; padding: 1px 6px; font-size: 0.72rem; cursor: pointer; font-weight: 600;" title="Xác nhận đáp án này đúng và gỡ cảnh báo">Xác nhận</button>
                </span>
            `;
        }

        html += `${groupTitleHtml}<div class="question-title" style="display: flex; align-items: center; flex-wrap: wrap; gap: 6px;">Câu ${qIndex + 1}: ${qClean.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')} ${typeBadge} ${aiSuggestedBadge}</div>`;

        if (qType === 'true_false') {
            let tfMap = (typeof q.correct_answer === 'object' && q.correct_answer !== null) ? q.correct_answer : {};
            html += `<div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px;">`;
            (q.options || []).forEach((opt, oIndex) => {
                let charMatch = opt.match(/^[a-d]/);
                let char = charMatch ? charMatch[0].toLowerCase() : String.fromCharCode(97 + oIndex);
                let isTrue = tfMap[char] === true;
                let optClean = opt.replace(/^[a-d][\.\:\)]\s*/, '');
                html += `
                    <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;">
                        <div style="display: flex; align-items: flex-start; gap: 8px; flex: 1;">
                            <span style="display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; background: #e2e8f0; color: #334155; font-weight: 700; border-radius: 6px; font-size: 0.85rem; flex-shrink: 0;">${char}</span>
                            <span style="font-size: 0.95rem; color: #1e293b;">${optClean}</span>
                        </div>
                        <div style="display: flex; gap: 6px; margin-left: 10px; flex-shrink: 0;">
                            <span style="padding: 2px 8px; border-radius: 6px; font-size: 0.8rem; font-weight: 700; border: 1px solid ${isTrue ? '#86efac' : '#cbd5e1'}; background: ${isTrue ? '#dcfce7' : '#ffffff'}; color: ${isTrue ? '#15803d' : '#94a3b8'};">Đúng</span>
                            <span style="padding: 2px 8px; border-radius: 6px; font-size: 0.8rem; font-weight: 700; border: 1px solid ${!isTrue ? '#fca5a5' : '#cbd5e1'}; background: ${!isTrue ? '#fee2e2' : '#ffffff'}; color: ${!isTrue ? '#b91c1c' : '#94a3b8'};">Sai</span>
                        </div>
                    </div>`;
            });
            html += `</div>`;
        } else if (qType === 'short_answer') {
            let caVal = (q.correct_answer !== undefined && q.correct_answer !== null) ? String(q.correct_answer) : 'Chưa nhập đáp án';
            html += `
                <div style="display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: #f8fafc; border: 1.5px dashed #cbd5e1; border-radius: 8px; margin-bottom: 10px;">
                    <span style="font-weight: 700; color: #0284c7; font-size: 0.95rem;">✍️ Đáp án ngắn:</span>
                    <span style="font-weight: 700; font-size: 1.05rem; background: #dcfce7; color: #15803d; padding: 3px 12px; border-radius: 6px; border: 1px solid #86efac;">${escapeHtml(caVal)}</span>
                </div>`;
        } else {
            (q.options || []).forEach((opt, oIndex) => {
                let isCorrect = matchOptionToTarget(opt, oIndex, q.correct_answer);
                html += `<label class="option-practice ${isCorrect ? 'correct selected' : ''}" style="cursor: default;">
                            <input type="radio" disabled ${isCorrect ? 'checked' : ''}>
                            <span class="opt-badge">${opt.match(/^[A-F]/i) ? opt.match(/^[A-F]/i)[0].toUpperCase() : String.fromCharCode(65 + oIndex)}</span>
                            <span class="opt-text">${opt.replace(/^[A-F][\.\:\)]\s*/i, '')}</span>
                        </label>`;
            });
        }

        if (q.explain && q.explain.trim()) {
            html += `<div style="margin-top: 8px; padding: 8px 12px; background: #f1f5f9; border-left: 3px solid #64748b; border-radius: 6px; font-size: 0.9rem; color: #334155;">
                <b>💡 Lời giải:</b> ${q.explain.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}
            </div>`;
        }

        // KIỂM TRA CHÉO ĐÁP ÁN: CẢNH BÁO NẾU AI GIẢI KHÁC ĐÁP ÁN GỐC
        if (q.has_cross_check_warning && q.cross_check_info) {
            let info = q.cross_check_info;
            let tAns = typeof info.teacher_answer === 'object' ? JSON.stringify(info.teacher_answer) : String(info.teacher_answer || 'Chưa rõ');
            let aiAns = typeof info.ai_answer === 'object' ? JSON.stringify(info.ai_answer) : String(info.ai_answer || 'Chưa rõ');
            let aiExp = info.ai_explain || '';
            
            html += `
                <div class="cross-check-warning-box" style="margin-top: 12px; margin-bottom: 8px; padding: 12px 14px; background: #fff7ed; border: 1.5px solid #fdba74; border-radius: 8px;" onclick="event.stopPropagation();">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                        <span style="font-weight: 700; color: #c2410c; display: flex; align-items: center; gap: 6px; font-size: 0.92rem;">
                            <i class="ri-alert-fill" style="color: #ea580c; font-size: 1.15rem;"></i>
                            CẢNH BÁO KIỂM TRA CHÉO: AI giải khác đáp án của Giáo viên!
                        </span>
                        <span style="font-size: 0.78rem; background: #ffedd5; color: #9a3412; padding: 2px 8px; border-radius: 4px; font-weight: 700;">Cần rà soát</span>
                    </div>
                    <div style="font-size: 0.88rem; color: #7c2d12; margin-bottom: 10px; line-height: 1.5;">
                        <div><b>Đáp án hiện tại (Giáo viên / Gốc):</b> <span style="background: #fed7aa; color: #7c2d12; padding: 2px 8px; border-radius: 4px; font-weight: 700;">${escapeHtml(tAns)}</span></div>
                        <div style="margin-top: 5px;"><b>Đáp án do AI độc lập giải:</b> <span style="background: #bbf7d0; color: #166534; padding: 2px 8px; border-radius: 4px; font-weight: 700;">${escapeHtml(aiAns)}</span></div>
                        ${aiExp ? `<div style="margin-top: 8px; font-size: 0.85rem; color: #431407; background: #ffffff; padding: 8px 10px; border-radius: 6px; border: 1px dashed #fdba74;"><b>💡 Lời giải độc lập của AI:</b> ${aiExp.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>` : ''}
                    </div>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                        <button type="button" class="btn-primary" style="padding: 5px 12px; font-size: 0.82rem; background: #ea580c; border: none; border-radius: 6px; cursor: pointer;" onclick="acceptAICrossCheckAnswer(${qIndex}); event.stopPropagation();">
                            <i class="ri-check-line"></i> Dùng đáp án AI giải
                        </button>
                        <button type="button" class="btn-outline" style="padding: 5px 12px; font-size: 0.82rem; border-radius: 6px; background: #fff; cursor: pointer;" onclick="dismissAICrossCheck(${qIndex}); event.stopPropagation();">
                            <i class="ri-close-line"></i> Giữ đáp án Giáo viên & Bỏ qua
                        </button>
                    </div>
                </div>
            `;
        }

        // TOOLBAR MỖI CÂU HỎI (SINH CÂU TƯƠNG TỰ)
        html += `
            <div class="q-card-footer" style="display: flex; justify-content: flex-end; align-items: center; gap: 8px; margin-top: 10px; padding-top: 8px; border-top: 1px dashed #e2e8f0;" onclick="event.stopPropagation();">
                <button type="button" class="btn-outline" style="padding: 4px 10px; font-size: 0.82rem; border-radius: 6px; display: inline-flex; align-items: center; gap: 4px; color: #6366f1; border-color: #c7d2fe; background: #eef2ff;" onclick="openSimilarModal(${qIndex}); event.stopPropagation();" title="Sinh các câu hỏi tương tự từ câu này để luyện tập">
                    <i class="ri-file-copy-2-line"></i> Sinh câu tương tự
                </button>
            </div>
        `;

        prevBox.innerHTML = html;
        
        // KIỂM TRA VÀ CHÈN UI GỢI Ý CỦA AI VÀO NGAY DƯỚI CÂU HỎI
        if (hasError) {
            const aiData = window.activeAIFeedbacks[qIndex];
            const isDelete = aiData.action === 'delete' || aiData.category === 'delete';
            const isRestructure = aiData.action === 'restructure' || aiData.category === 'restructure';

            const isExplain = aiData.category === 'explanation';
            const isLatex = aiData.category === 'latex';

            const catClass = isDelete ? 'ai-cat-delete' :
                             (isRestructure ? 'ai-cat-restructure' :
                             (isExplain ? 'ai-cat-explain' :
                             (isLatex ? 'ai-cat-latex' :
                             (aiData.category === 'knowledge' ? 'ai-cat-knowledge' :
                             (aiData.category === 'answer' ? 'ai-cat-answer' :
                             (aiData.category === 'grammar_typo' ? 'ai-cat-grammar' : 'ai-cat-format'))))));

            const aiDiv = document.createElement('div');
            aiDiv.onclick = (e) => e.stopPropagation();

            if (isDelete) {
                aiDiv.style.cssText = 'margin-top: 15px; padding: 14px; background: #fef2f2; border: 1.5px solid #fca5a5; border-radius: 10px; cursor: default;';
                aiDiv.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 1.2rem;">🗑️</span>
                            <strong style="color: #dc2626;">Yêu cầu xóa câu hỏi:</strong>
                            <span class="ai-cat-chip ${catClass}" style="padding: 2px 8px; font-size: 0.75rem;">${aiData.category_name || 'Yêu cầu xóa câu'}</span>
                        </div>
                    </div>
                    <div style="color: #991b1b; font-size: 0.92rem; font-weight: 500; margin-bottom: 10px;">
                        ${escapeHtml(aiData.reason || 'Người làm đề yêu cầu loại bỏ câu hỏi này.')}
                    </div>
                    <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
                        <button class="btn-ai-delete" onclick="applyAIDelete(${qIndex})"><i class="ri-delete-bin-line"></i> Xác nhận xóa câu này</button>
                        <button class="btn-outline" style="padding: 6px 12px; font-size: 0.85rem; border-color: #cbd5e1; color: #475569; border-radius: 6px;" onclick="dismissAISuggestion(${qIndex})">Bỏ qua</button>
                    </div>
                `;
            } else if (isRestructure) {
                aiDiv.style.cssText = 'margin-top: 15px; padding: 14px; background: #faf5ff; border: 1.5px solid #d8b4fe; border-radius: 10px; cursor: default;';
                let corrected = aiData.corrected_data || {};
                let targetType = corrected.type || 'true_false';
                let targetTypeName = targetType === 'true_false' ? 'Đúng / Sai' : (targetType === 'short_answer' ? 'Trả lời ngắn' : 'Trắc nghiệm 4 lựa chọn');

                let previewRestructure = '';
                if (targetType === 'true_false' && Array.isArray(corrected.options)) {
                    let tfMap = typeof corrected.correct_answer === 'object' && corrected.correct_answer ? corrected.correct_answer : {};
                    previewRestructure = `<div style="font-size: 0.88rem; background: #ffffff; padding: 10px; border-radius: 8px; border: 1px solid #e9d5ff; margin-bottom: 8px;">
                        <div style="font-weight: 700; color: #7e22ce; margin-bottom: 6px;">🔄 Kết cấu Đúng/Sai mới:</div>`;
                    corrected.options.forEach((opt, oIdx) => {
                        let ch = ['a', 'b', 'c', 'd'][oIdx] || 'a';
                        let isT = tfMap[ch] === true;
                        previewRestructure += `<div style="display: flex; justify-content: space-between; padding: 3px 0; border-bottom: 1px dashed #f3e8ff;">
                            <span>${escapeHtml(opt)}</span>
                            <span style="font-weight: 700; color: ${isT ? '#16a34a' : '#dc2626'};">${isT ? 'Đúng' : 'Sai'}</span>
                        </div>`;
                    });
                    previewRestructure += `</div>`;
                } else if (targetType === 'short_answer') {
                    previewRestructure = `<div style="font-size: 0.88rem; background: #ffffff; padding: 8px 12px; border-radius: 8px; border: 1px solid #e9d5ff; color: #7e22ce; margin-bottom: 8px;">
                        <b>✍️ Đáp án ngắn mới:</b> <span style="font-weight: 700; color: #15803d; background: #dcfce7; padding: 2px 8px; border-radius: 4px;">${escapeHtml(String(corrected.correct_answer || ''))}</span>
                    </div>`;
                }

                let explainText = corrected.explain ? `<div style="margin-top: 6px; font-size: 0.88rem; color: #475569;"><b>💡 Giải thích:</b> ${escapeHtml(corrected.explain)}</div>` : '';

                aiDiv.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 1.2rem;">🔄</span>
                            <strong style="color: #7e22ce;">Thay đổi kết cấu (${targetTypeName}):</strong>
                            <span class="ai-cat-chip ${catClass}" style="padding: 2px 8px; font-size: 0.75rem;">${aiData.category_name || 'Thay đổi kết cấu'}</span>
                        </div>
                    </div>
                    <div style="color: #6b21a8; font-size: 0.92rem; font-weight: 500; margin-bottom: 8px;">
                        ${escapeHtml(aiData.reason)}
                    </div>
                    ${previewRestructure}
                    ${explainText}
                    <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
                        <button class="btn-ai-restructure" onclick="applyAISuggestion(${qIndex})"><i class="ri-check-line"></i> Áp dụng đổi kết cấu</button>
                        <button class="btn-outline" style="padding: 6px 12px; font-size: 0.85rem; border-color: #cbd5e1; color: #475569; border-radius: 6px;" onclick="dismissAISuggestion(${qIndex})">Bỏ qua</button>
                    </div>
                `;
            } else if (isExplain) {
                aiDiv.style.cssText = 'margin-top: 15px; padding: 14px; background: #f0fdf4; border: 1.5px solid #86efac; border-radius: 10px; cursor: default;';
                let corrected = aiData.corrected_data || {};
                let explainText = (corrected.explain || aiData.reason || '').trim();

                aiDiv.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 1.25rem;">💡</span>
                            <strong style="color: #15803d;">Đề xuất bổ sung lời giải chi tiết:</strong>
                            <span class="ai-cat-chip ai-cat-explain" style="padding: 2px 8px; font-size: 0.75rem;">${escapeHtml(aiData.category_name || 'Bổ sung lời giải')}</span>
                        </div>
                    </div>
                    <div style="color: #166534; font-size: 0.92rem; font-weight: 500; margin-bottom: 8px;">
                        ${escapeHtml(aiData.reason)}
                    </div>
                    ${explainText ? `
                        <div style="margin-top: 8px; padding: 10px 14px; background: #ffffff; border-radius: 8px; font-size: 0.9rem; color: #1e293b; line-height: 1.6; border: 1px solid #dcfce7; border-left: 4px solid #10b981;">
                            <b style="color: #15803d;">💡 Nội dung lời giải:</b><br>
                            ${explainText.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}
                        </div>
                    ` : ''}
                    <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
                        <button class="btn-ai-explain" onclick="applyAISuggestion(${qIndex})"><i class="ri-lightbulb-line"></i> Xác nhận thêm lời giải này</button>
                        <button class="btn-outline" style="padding: 6px 12px; font-size: 0.85rem; border-color: #cbd5e1; color: #475569; border-radius: 6px;" onclick="dismissAISuggestion(${qIndex})">Bỏ qua</button>
                    </div>
                `;
            } else {
                aiDiv.style.cssText = 'margin-top: 15px; padding: 14px; background: #faf5ff; border: 1.5px solid #d8b4fe; border-radius: 10px; cursor: default;';
                let corrected = aiData.corrected_data || {};
                let correctedAnswerText = typeof corrected.correct_answer === 'object' ? JSON.stringify(corrected.correct_answer) : (corrected.correct_answer || '');
                let explainText = corrected.explain ? `<div style="margin-top: 6px; font-size: 0.88rem; color: #475569;"><b>💡 Giải thích:</b> ${escapeHtml(corrected.explain)}</div>` : '';

                aiDiv.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 1.2rem;">🤖</span>
                            <strong style="color: #9333ea;">AI Phát hiện vấn đề:</strong>
                            <span class="ai-cat-chip ${catClass}" style="padding: 2px 8px; font-size: 0.75rem;">${aiData.category_name || 'Cần sửa'}</span>
                        </div>
                    </div>
                    <div style="color: #dc2626; font-size: 0.92rem; font-weight: 600; margin-bottom: 8px;">
                        ${escapeHtml(aiData.reason)}
                    </div>
                    ${correctedAnswerText ? `<div style="font-size: 0.88rem; background: #f0fdf4; padding: 6px 10px; border-radius: 6px; border: 1px solid #bbf7d0; color: #166534; margin-bottom: 8px;">
                        <b>✨ Đề xuất đáp án đúng:</b> ${escapeHtml(correctedAnswerText)}
                    </div>` : ''}
                    ${explainText}
                    <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
                        <button class="btn-primary" style="padding: 6px 14px; font-size: 0.85rem; background: #9333ea; border: none; border-radius: 6px;" onclick="applyAISuggestion(${qIndex})">✨ Tự động sửa câu này</button>
                        <button class="btn-outline" style="padding: 6px 12px; font-size: 0.85rem; border-color: #cbd5e1; color: #475569; border-radius: 6px;" onclick="dismissAISuggestion(${qIndex})">❌ Bỏ qua</button>
                    </div>
                `;
            }
            prevBox.appendChild(aiDiv);
        }
        
        previewContent.appendChild(prevBox);
    });

    if (window.MathJax && typeof window.MathJax.typesetPromise === 'function') {
        MathJax.typesetPromise([previewContent]).catch((err) => console.log('MathJax error:', err));
    }
}

// ----------------------------------------------------
// MOBILE SEGMENTED TABS CHO TRÌNH SOẠN THẢO TRÊN TRANG CHÍNH
// ----------------------------------------------------
function switchIndexMobileEditorTab(tab) {
    const tabCode = document.getElementById('idxTabCode');
    const tabPreview = document.getElementById('idxTabPreview');
    const splitLayout = document.getElementById('indexSplitLayout');
    const floatBtn = document.getElementById('indexMobileFloatToggle');
    if (!splitLayout) return;

    if (tab === 'preview') {
        splitLayout.classList.remove('idx-tab-code');
        splitLayout.classList.add('idx-tab-preview');
        if (tabCode) tabCode.classList.remove('active');
        if (tabPreview) tabPreview.classList.add('active');
        if (floatBtn) floatBtn.innerHTML = '<i class="ri-code-s-slash-line"></i> <span>Soạn thảo</span>';
        renderPreviewAll();
    } else {
        splitLayout.classList.remove('idx-tab-preview');
        splitLayout.classList.add('idx-tab-code');
        if (tabCode) tabCode.classList.add('active');
        if (tabPreview) tabPreview.classList.remove('active');
        if (floatBtn) floatBtn.innerHTML = '<i class="ri-eye-line"></i> <span>Xem trước</span>';
    }
}

function toggleIndexMobileEditorTab() {
    const splitLayout = document.getElementById('indexSplitLayout');
    if (!splitLayout) return;
    if (splitLayout.classList.contains('idx-tab-preview')) {
        switchIndexMobileEditorTab('code');
    } else {
        switchIndexMobileEditorTab('preview');
    }
}

function scrollToQuestionInEditor(qIndex) {
    if (window.innerWidth <= 860) {
        switchIndexMobileEditorTab('code');
    }
    const editor = document.getElementById('codeEditor');
    if (!editor) return;
    
    const text = editor.value;
    const lines = text.split('\n');
    const qRegex = /^\s*(Câu|Bài|Question|Q)\s*\d+[\.\:\-\)]/i;
    
    let currentQCount = -1;
    let charOffset = 0;
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line.trim() !== '') {
            if (qRegex.test(line)) {
                currentQCount++;
                if (currentQCount === qIndex) {
                    editor.focus();
                    editor.setSelectionRange(charOffset, charOffset + line.length);
                    
                    // Thuật toán cuộn mượt: Tính tọa độ Y tuyệt đối dựa trên tỷ lệ ký tự
                    // Cách này miễn nhiễm với lỗi Word-wrap và cực kỳ ổn định trên mọi trình duyệt
                    const scrollRatio = charOffset / text.length;
                    const targetScroll = editor.scrollHeight * scrollRatio;
                    
                    // Đẩy thanh cuộn đến đúng mục tiêu, trừ lùi 56px (~1.5cm) để tạo khoảng thở ở mép trên
                    editor.scrollTop = targetScroll - 56;
                    return;
                }
            }
        }
        charOffset += line.length + 1; // +1 là đếm khoảng trắng của ký tự xuống dòng (\n)
    }
}

function startTimer(minutes) {
    clearInterval(timerInterval);
    const limitMinutes = parseInt(minutes, 10) || 0;
    
    const timerDisplay = document.getElementById('timerDisplay');
    const stickyTimer = document.getElementById('examStickyTimer');
    const examTimerVal = document.getElementById('examTimerVal');
    
    if (isStudentMode) {
        if (timerDisplay) timerDisplay.style.display = 'none';
        if (stickyTimer) {
            stickyTimer.style.setProperty('display', 'inline-flex', 'important');
            stickyTimer.style.animation = 'none';
        }
    } else {
        if (timerDisplay) timerDisplay.style.display = 'block';
        if (stickyTimer) {
            stickyTimer.style.setProperty('display', 'inline-flex', 'important');
            stickyTimer.style.animation = 'none';
        }
    }
    
    if (isStudentMode && quizProgress && quizProgress.startedAt) {
        startTime = quizProgress.startedAt;
    } else if (!startTime) {
        startTime = Date.now();
        if (isStudentMode && quizProgress) quizProgress.startedAt = startTime;
    }
    
    if (limitMinutes > 0) {
        // --- CHẾ ĐỘ 1: ĐẾM NGƯỢC (COUNTDOWN KHI CÓ GIỚI HẠN THỜI GIAN) ---
        // QUY TẮC: Thời gian tính theo thời gian thực (wall-clock) kể cả khi thoát ra
        const totalSeconds = limitMinutes * 60;
        let timeRemaining = totalSeconds;
        
        if (isStudentMode && quizProgress && quizProgress.startedAt && !quizProgress.completed) {
            const elapsed = Math.floor((Date.now() - quizProgress.startedAt) / 1000);
            timeRemaining = Math.max(0, totalSeconds - elapsed);
        } else if (isStudentMode && quizProgress && typeof quizProgress.timeRemaining === 'number' && quizProgress.timeRemaining > 0 && !quizProgress.completed) {
            timeRemaining = Math.min(quizProgress.timeRemaining, totalSeconds);
        }
        
        function updateDisplayCountdown() {
            const h = Math.floor(timeRemaining / 3600);
            const m = Math.floor((timeRemaining % 3600) / 60).toString().padStart(2, '0');
            const s = (timeRemaining % 60).toString().padStart(2, '0');
            const displayStr = h > 0 ? `${h}:${m}:${s}` : `${m}:${s}`;
            
            if (timerDisplay) timerDisplay.innerText = `⏳ ${displayStr}`;
            if (examTimerVal) examTimerVal.innerText = displayStr;
            
            if (timeRemaining <= 60 && timeRemaining > 0) {
                if (timerDisplay) timerDisplay.style.animation = "pulse-red 1s infinite";
                if (stickyTimer) stickyTimer.style.animation = "pulse-red 1s infinite";
            } else {
                if (stickyTimer) stickyTimer.style.animation = "none";
                if (timerDisplay) timerDisplay.style.animation = "none";
            }
        }
        
        updateDisplayCountdown();
        
        if (timeRemaining <= 0) {
            showToast("⏳ Đã hết thời gian làm bài! Hệ thống tự động nộp bài.", "warning");
            submitExam();
            return;
        }
        
        timerInterval = setInterval(() => {
            if (isStudentMode && quizProgress && quizProgress.startedAt) {
                const elapsed = Math.floor((Date.now() - quizProgress.startedAt) / 1000);
                timeRemaining = Math.max(0, totalSeconds - elapsed);
            } else {
                timeRemaining--;
            }
            if (isStudentMode) {
                quizProgress.timeRemaining = timeRemaining;
                quizProgress.timeElapsed = Math.max(0, totalSeconds - Math.max(0, timeRemaining));
                if (timeRemaining % 5 === 0) saveProgressToLocal(false); // Lưu LocalStorage ngầm, không gọi Cloud
            }
            if (timeRemaining <= 0) {
                clearInterval(timerInterval);
                timeRemaining = 0;
                updateDisplayCountdown();
                showToast("⏳ Đã hết thời gian làm bài! Hệ thống tự động nộp bài.", "warning");
                submitExam();
                return;
            }
            updateDisplayCountdown();
        }, 1000);
    } else {
        // --- CHẾ ĐỘ 2: BẤM GIỜ ĐẾM TIẾN (STOPWATCH KHI KHÔNG GIỚI HẠN THỜI GIAN) ---
        // QUY TẮC: Chỉ reset sau 3 tiếng kể từ khi nhấn vào làm đề nếu đề không để thời gian (3 tiếng = 10800s)
        const THREE_HOURS_SEC = 3 * 3600;
        let timeElapsed = 0;
        if (isStudentMode && quizProgress && quizProgress.startedAt && !quizProgress.completed) {
            timeElapsed = Math.floor((Date.now() - quizProgress.startedAt) / 1000);
        } else if (startTime > 0) {
            timeElapsed = Math.floor((Date.now() - startTime) / 1000);
        }
        
        function updateDisplayCountUp() {
            const h = Math.floor(timeElapsed / 3600);
            const m = Math.floor((timeElapsed % 3600) / 60).toString().padStart(2, '0');
            const s = (timeElapsed % 60).toString().padStart(2, '0');
            const displayStr = h > 0 ? `${h}:${m}:${s}` : `${m}:${s}`;
            
            if (timerDisplay) timerDisplay.innerText = `⏱️ ${displayStr}`;
            if (examTimerVal) examTimerVal.innerText = displayStr;
        }
        
        updateDisplayCountUp();
        
        if (timeElapsed >= THREE_HOURS_SEC) {
            showToast("⏳ Đã quá 3 tiếng kể từ khi bắt đầu làm đề! Hệ thống tự động nộp bài.", "warning");
            submitExam();
            return;
        }
        
        timerInterval = setInterval(() => {
            if (isStudentMode && quizProgress && quizProgress.startedAt) {
                timeElapsed = Math.floor((Date.now() - quizProgress.startedAt) / 1000);
            } else {
                timeElapsed++;
            }
            if (isStudentMode) {
                quizProgress.timeElapsed = timeElapsed;
                if (timeElapsed % 5 === 0) saveProgressToLocal(false);
            }
            if (timeElapsed >= THREE_HOURS_SEC) {
                clearInterval(timerInterval);
                timeElapsed = THREE_HOURS_SEC;
                updateDisplayCountUp();
                showToast("⏳ Đã quá 3 tiếng kể từ khi bắt đầu làm đề! Hệ thống tự động nộp bài.", "warning");
                submitExam();
                return;
            }
            updateDisplayCountUp();
        }, 1000);
    }
}

function formatTime(seconds) {
    const total = Math.max(0, parseInt(seconds, 10) || 0);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    if (h > 0) return `${h} giờ ${m} phút ${s} giây`;
    if (m > 0) return `${m} phút ${s} giây`;
    return `${s} giây`;
}

function formatTimeCompact(seconds) {
    const total = Math.max(0, parseInt(seconds, 10) || 0);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    if (h > 0) return `${h}h ${m}p ${s.toString().padStart(2, '0')}s`;
    if (m > 0) return `${m}p ${s.toString().padStart(2, '0')}s`;
    return `${s}s`;
}



// --- BỘ LỌC CÂU HỎI SAU KHI NỘP BÀI (TẤT CẢ / CÂU SAI / CÂU ĐÚNG / CHƯA LÀM) ---
function filterReviewQuestions(filterType) {
    document.querySelectorAll('.azota-filter-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.filter === filterType);
    });
    const cards = document.querySelectorAll('.review-question-card');
    cards.forEach(card => {
        const status = card.dataset.resultStatus;
        if (filterType === 'all') {
            card.style.display = 'block';
        } else if (filterType === 'wrong') {
            card.style.display = (status === 'wrong') ? 'block' : 'none';
        } else if (filterType === 'correct') {
            card.style.display = (status === 'correct') ? 'block' : 'none';
        } else if (filterType === 'skipped') {
            card.style.display = (status === 'skipped') ? 'block' : 'none';
        }
    });
}

// Hàm chuẩn hóa text phương án để so khớp chính xác: loại bỏ HTML, ký hiệu LaTeX và khoảng trắng thừa
function normalizeOptionCompareText(s) {
    if (!s) return '';
    return String(s)
        .replace(/<[^>]+>/g, '')
        .replace(/\\\(|\\\)|[\$]/g, '')
        .replace(/[\u00a0\u200b\s]+/g, ' ')
        .trim()
        .toLowerCase();
}

// --- HÀM SO KHỚP CHÍNH XÁC ĐÁP ÁN (HỖ TRỢ CẢ KÝ TỰ A,B,C,D VÀ NỘI DUNG OPTION) ---
function matchOptionToTarget(opt, oIndex, target) {
    if (target === null || target === undefined || target === '') return false;
    const optStr = String(opt || '').trim();
    const tgtStr = String(target).trim();
    if (!optStr || !tgtStr) return false;

    // 1. So khớp chuỗi trực tiếp
    if (optStr.toLowerCase() === tgtStr.toLowerCase()) return true;

    // Regex phát hiện trường hợp CHỈ có chữ cái đại diện (A, B, C, D, E, F hoặc A., B., *A,...)
    const reOnlyLetter = /^\*?\s*(?:<[^>]+>\s*)*([A-Fa-f])[\.\:\)]?\s*$/;
    // Regex phát hiện tiền tố chữ cái có nội dung theo sau
    const rePrefix = /^\*?\s*(?:<[^>]+>\s*)*([A-Fa-f])(?:[\.\:\)]\s*|\s+)/;

    // 2. Tách chữ cái và clean text của Option
    let optChar = null;
    let cleanOpt = '';
    const optMatchOnly = optStr.match(reOnlyLetter);
    if (optMatchOnly) {
        optChar = optMatchOnly[1].toUpperCase();
        cleanOpt = '';
    } else {
        const optMatch = optStr.match(rePrefix);
        if (optMatch) {
            optChar = optMatch[1].toUpperCase();
            cleanOpt = normalizeOptionCompareText(optStr.substring(optMatch[0].length));
        } else {
            optChar = String.fromCharCode(65 + oIndex);
            cleanOpt = normalizeOptionCompareText(optStr);
        }
    }

    // 3. Tách chữ cái và clean text của Target
    let tgtChar = null;
    let cleanTgt = '';
    const tgtMatchOnly = tgtStr.match(reOnlyLetter);
    if (tgtMatchOnly) {
        tgtChar = tgtMatchOnly[1].toUpperCase();
        cleanTgt = '';
    } else {
        const tgtMatch = tgtStr.match(rePrefix);
        if (tgtMatch) {
            tgtChar = tgtMatch[1].toUpperCase();
            cleanTgt = normalizeOptionCompareText(tgtStr.substring(tgtMatch[0].length));
        } else {
            tgtChar = null;
            cleanTgt = normalizeOptionCompareText(tgtStr);
            if (/^\d+$/.test(tgtStr) && parseInt(tgtStr, 10) === oIndex) {
                return true;
            }
        }
    }

    // 4. Ưu tiên so khớp nội dung văn bản nếu cả 2 đều có nội dung text rõ ràng
    if (cleanOpt && cleanTgt) {
        if (cleanOpt === cleanTgt) return true;
        return false;
    }

    // 5. Nếu 1 trong 2 chỉ là chữ cái đơn (ví dụ target là 'C', 'C.' hoặc opt là 'C')
    if (tgtChar && optChar && tgtChar === optChar) {
        return true;
    }

    return false;
}

// Biến lưu trạng thái tab kết quả hiện tại ('review' hoặc 'leaderboard')

// --- HÀM XÁC ĐỊNH CHÍNH XÁC VỊ TRÍ ĐÁP ÁN ĐÚNG & LỰA CHỌN CỦA HỌC SINH (HỖ TRỢ ĐẢO PHƯƠNG ÁN) ---
function resolveMcqIndices(q, userAnswer, correctAnswer, serverItem, status) {
    let revUserPickIdx = -1;
    let revCorrectIdx = -1;
    const opts = q.options || [];

    // 1. Xác định lựa chọn của học sinh trong opts hiện tại
    opts.forEach((opt, oIdx) => {
        if (matchOptionToTarget(opt, oIdx, userAnswer)) revUserPickIdx = oIdx;
    });

    // 2. Xác định nội dung đáp án đúng chuẩn (text content)
    let correctContent = '';
    const origOpts = (serverItem && Array.isArray(serverItem.options) && serverItem.options.length > 0)
        ? serverItem.options
        : (q._originalOptions || opts);
    const sAns = (serverItem && serverItem.correct_answer !== undefined && serverItem.correct_answer !== null && serverItem.correct_answer !== '')
        ? serverItem.correct_answer
        : (q._originalCorrectAnswer || q.correct_answer || correctAnswer);

    if (origOpts && origOpts.length > 0) {
        let origCorrectIdx = -1;
        origOpts.forEach((opt, oIdx) => {
            if (matchOptionToTarget(opt, oIdx, sAns)) origCorrectIdx = oIdx;
        });
        if (origCorrectIdx === -1 && typeof sAns === 'string') {
            const mLetter = sAns.match(/^\*?\s*(?:<[^>]+>\s*)*([A-Fa-f])[\.\:\)]?\s*$/);
            if (mLetter) {
                const idx = mLetter[1].toUpperCase().charCodeAt(0) - 65;
                if (idx >= 0 && idx < origOpts.length) origCorrectIdx = idx;
            }
        }
        if (origCorrectIdx === -1 && typeof sAns === 'number' && sAns >= 0 && sAns < origOpts.length) {
            origCorrectIdx = sAns;
        }
        if (origCorrectIdx >= 0 && origCorrectIdx < origOpts.length) {
            correctContent = normalizeOptionCompareText(origOpts[origCorrectIdx].replace(/^\*?\s*(?:<[^>]+>\s*)*[A-Fa-f][\.\:\)]\s*/, ''));
        }
    }

    if (!correctContent && typeof sAns === 'string') {
        correctContent = normalizeOptionCompareText(sAns.replace(/^\*?\s*(?:<[^>]+>\s*)*[A-Fa-f][\.\:\)]\s*/, ''));
    }

    // 3. Tìm vị trí của phương án đúng trong opts đang hiển thị (bất kể đã đảo hay chưa)
    if (correctContent) {
        opts.forEach((opt, oIdx) => {
            const cleanOpt = normalizeOptionCompareText(opt.replace(/^\*?\s*(?:<[^>]+>\s*)*[A-Fa-f][\.\:\)]\s*/, ''));
            if (cleanOpt === correctContent) revCorrectIdx = oIdx;
        });
    }

    if (revCorrectIdx === -1) {
        opts.forEach((opt, oIdx) => {
            if (matchOptionToTarget(opt, oIdx, q.correct_answer || correctAnswer)) revCorrectIdx = oIdx;
        });
    }

    // 4. Đồng bộ tuyệt đối: Nếu bài thi chấm ĐÚNG -> vị trí đúng bắt buộc trùng với lựa chọn của học sinh
    if (status === 'correct') {
        if (revUserPickIdx !== -1) {
            revCorrectIdx = revUserPickIdx;
        } else if (revCorrectIdx !== -1) {
            revUserPickIdx = revCorrectIdx;
        }
    }

    // 5. Tính ký tự chữ cái hiển thị (A, B, C, D...)
    let userCharDisplay = '';
    let correctCharDisplay = '';
    if (revUserPickIdx >= 0 && revUserPickIdx < opts.length) {
        const m = opts[revUserPickIdx].match(/^[A-F]/i);
        userCharDisplay = m ? m[0].toUpperCase() : String.fromCharCode(65 + revUserPickIdx);
    }
    if (revCorrectIdx >= 0 && revCorrectIdx < opts.length) {
        const m = opts[revCorrectIdx].match(/^[A-F]/i);
        correctCharDisplay = m ? m[0].toUpperCase() : String.fromCharCode(65 + revCorrectIdx);
    }
    if (status === 'correct') {
        if (!correctCharDisplay && userCharDisplay) correctCharDisplay = userCharDisplay;
        if (!userCharDisplay && correctCharDisplay) userCharDisplay = correctCharDisplay;
    }

    return { revUserPickIdx, revCorrectIdx, userCharDisplay, correctCharDisplay };
}

window.currentResultView = 'review';

// --- HÀM CHUYỂN ĐỔI TAB SAU KHI NỘP BÀI: XEM LỜI GIẢI <-> BẢNG XẾP HẠNG ---
function switchResultView(viewType, autoScroll = true) {
    window.currentResultView = viewType;
    const tabNav = document.getElementById('resultNavTabs');
    const tabReview = document.getElementById('tabBtnReview');
    const tabLb = document.getElementById('tabBtnLeaderboard');
    const lb = document.getElementById('leaderboard');
    const filterContainer = document.getElementById('reviewFilterBarContainer');
    const examLayout = document.getElementById('azotaExamLayout');
    const quizContainer = document.getElementById('quiz-container');

    if (tabNav) tabNav.style.display = 'flex';

    if (viewType === 'leaderboard') {
        if (tabReview) tabReview.classList.remove('active');
        if (tabLb) tabLb.classList.add('active');
        if (filterContainer) filterContainer.style.display = 'none';
        if (quizContainer) quizContainer.style.display = 'none';
        if (examLayout) examLayout.style.display = 'none';
        if (lb) {
            lb.style.display = 'block';
            if (autoScroll) {
                setTimeout(() => {
                    const headerOffset = 90;
                    const elementPosition = lb.getBoundingClientRect().top;
                    const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
                    window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
                }, 60);
            }
        }
        const urlParams = new URLSearchParams(window.location.search);
        const quizId = urlParams.get('quiz_id') || urlParams.get('id');
        fetchLeaderboard(quizId);
    } else {
        // 'review' view
        if (tabReview) tabReview.classList.add('active');
        if (tabLb) tabLb.classList.remove('active');
        if (lb) lb.style.display = 'none';
        if (filterContainer) filterContainer.style.display = 'block';
        if (examLayout) examLayout.style.display = 'block';
        if (quizContainer) quizContainer.style.display = 'block';
        if (autoScroll) {
            setTimeout(() => {
                if (filterContainer) {
                    const headerOffset = 90;
                    const elementPosition = filterContainer.getBoundingClientRect().top;
                    const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
                    window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
                }
            }, 60);
        }
    }
}

function showLeaderboardOnly() {
    document.getElementById('welcomeScreen').style.display = 'none';
    
    const azotaNav = document.getElementById('azotaNavbar');
    if (azotaNav) azotaNav.style.display = 'none';
    const azotaFooter = document.getElementById('azotaFooter');
    if (azotaFooter) azotaFooter.style.display = 'none';

    const lb = document.getElementById('leaderboard');
    if (lb) {
        lb.style.display = 'block';
        lb.style.marginTop = '20px';
    }

    const lbBackBtn = document.getElementById('lbBackBtn');
    if (lbBackBtn) lbBackBtn.style.display = 'inline-flex';

    const quizId = getCurrentQuizId();
    if (quizId && window.location.pathname !== `/xep-hang/${quizId}`) {
        history.pushState({ page: 'leaderboard', quizId: quizId }, '', `/xep-hang/${quizId}`);
    }
    fetchLeaderboard(quizId);
}

function hideLeaderboardOnly() {
    const lb = document.getElementById('leaderboard');
    if (lb) lb.style.display = 'none';
    
    const lbBackBtn = document.getElementById('lbBackBtn');
    if (lbBackBtn) lbBackBtn.style.display = 'none';

    const azotaNav = document.getElementById('azotaNavbar');
    if (azotaNav && (authToken || !window.isCurrentQuizPublished)) azotaNav.style.display = 'block';

    const azotaFooter = document.getElementById('azotaFooter');
    if (azotaFooter) azotaFooter.style.display = 'block';

    document.getElementById('welcomeScreen').style.display = 'block';
    updateAdPassUI();
    const quizId = getCurrentQuizId();
    if (quizId && window.location.pathname.startsWith('/xep-hang/')) {
        history.pushState({ page: 'exam', quizId: quizId }, '', `/thi/${quizId}`);
    }
}

// --- HÀM TẢI LẠI BẢNG XẾP HẠNG KHI BẤM NÚT REFRESH ---
async function refreshLeaderboardBtn() {
    const btn = document.getElementById('lbRefreshBtn');
    if (btn) btn.classList.add('rotating');
    const urlParams = new URLSearchParams(window.location.search);
    const quizId = urlParams.get('quiz_id') || urlParams.get('id');
    await fetchLeaderboard(quizId);
    setTimeout(() => {
        if (btn) btn.classList.remove('rotating');
    }, 600);
}

// --- HÀM TẢI VÀ RENDER BẢNG XẾP HẠNG THÀNH TÍCH PHÒNG THI ---
async function fetchLeaderboard(quizId) {
    const lb = document.getElementById('leaderboard');
    const lbList = document.getElementById('leaderboardList');
    const podiumEl = document.getElementById('leaderboardPodium');
    const badgeEl = document.getElementById('lbTotalParticipants');
    const tabLbBadge = document.getElementById('tabLbCount');
    if (!lb || !lbList) return;

    try {
        let listData = [];
        if (quizId) {
            try {
                const response = await fetch(`${API_BASE_URL}/api/leaderboard/${quizId}`);
                if (response.ok) {
                    const result = await response.json();
                    if (result.status === 'success' && Array.isArray(result.data)) {
                        listData = result.data;
                    }
                }
            } catch(e) {
                console.warn("Không kết nối được server leaderboard, dùng dữ liệu cục bộ:", e);
            }
        }

        // Tên học sinh hiện tại và kết quả
        const currentStudent = (studentName && studentName.trim()) || 'Học sinh';
        const myScore = (quizProgress && quizProgress.score !== undefined) ? quizProgress.score : (practiceScore || 0);
        const myTime = (quizProgress && quizProgress.timeElapsed) ? quizProgress.timeElapsed : (startTime > 0 ? Math.floor((Date.now() - startTime) / 1000) : 45);

        // Nếu danh sách từ server rỗng và học sinh đã làm xong, tạo bản ghi của chính học sinh để luôn hiển thị
        const hasCompleted = (quizProgress && quizProgress.completed) || (myScore > 0 && startTime > 0);
        
        if (listData.length === 0) {
            if (hasCompleted) {
                listData = [{
                    student_name: currentStudent,
                    score: myScore,
                    time_elapsed: myTime
                }];
            }
        } else {
            // Kiểm tra xem học sinh hiện tại đã có trong danh sách chưa
            if (hasCompleted) {
                const found = listData.some(item => item.student_name && item.student_name.trim().toLowerCase() === currentStudent.toLowerCase());
                if (!found) {
                    listData.push({
                        student_name: currentStudent,
                        score: myScore,
                        time_elapsed: myTime
                    });
                    listData.sort((a, b) => b.score - a.score || a.time_elapsed - b.time_elapsed);
                }
            }
        }

        // Chỉ lấy và hiển thị đúng Top 5 người cao điểm nhất
        listData = listData.slice(0, 5);

        // Cập nhật số lượng thí sinh
        if (badgeEl) badgeEl.innerText = `Top ${listData.length} xuất sắc nhất`;
        if (tabLbBadge) tabLbBadge.innerText = `Top 5`;

        // Render Podium Top 1-3
        if (podiumEl) {
            if (listData.length >= 2) {
                podiumEl.style.display = 'flex';
                const rank1 = listData[0];
                const rank2 = listData[1];
                const rank3 = listData.length >= 3 ? listData[2] : null;

                const getLBScore = (item) => {
                    let t = item.total_questions || currentData.length;
                    return t > 0 ? ((item.score / t) * 10).toFixed(1) + 'đ' : item.score + 'đ';
                };

                let podiumHtml = `
                    <div class="azota-podium-slot rank-2">
                        <div class="azota-podium-avatar">🥈</div>
                        <div class="azota-podium-name" title="${escapeHtml(rank2.student_name)}">${escapeHtml(rank2.student_name)}</div>
                        <div class="azota-podium-score">${getLBScore(rank2)}</div>
                        <div class="azota-podium-time">${formatTime(rank2.time_elapsed)}</div>
                        <div class="azota-podium-bar">2</div>
                    </div>
                    <div class="azota-podium-slot rank-1">
                        <div class="azota-podium-avatar"><span class="azota-podium-crown">👑</span>🥇</div>
                        <div class="azota-podium-name" title="${escapeHtml(rank1.student_name)}">${escapeHtml(rank1.student_name)}</div>
                        <div class="azota-podium-score">${getLBScore(rank1)}</div>
                        <div class="azota-podium-time">${formatTime(rank1.time_elapsed)}</div>
                        <div class="azota-podium-bar">1</div>
                    </div>
                `;
                if (rank3) {
                    podiumHtml += `
                        <div class="azota-podium-slot rank-3">
                            <div class="azota-podium-avatar">🥉</div>
                            <div class="azota-podium-name" title="${escapeHtml(rank3.student_name)}">${escapeHtml(rank3.student_name)}</div>
                            <div class="azota-podium-score">${getLBScore(rank3)}</div>
                            <div class="azota-podium-time">${formatTime(rank3.time_elapsed)}</div>
                            <div class="azota-podium-bar">3</div>
                        </div>
                    `;
                }
                podiumEl.innerHTML = podiumHtml;
            } else if (listData.length === 1) {
                podiumEl.style.display = 'flex';
                const rank1 = listData[0];
                const getLBScore = (item) => {
                    let t = item.total_questions || currentData.length;
                    return t > 0 ? ((item.score / t) * 10).toFixed(1) + 'đ' : item.score + 'đ';
                };
                podiumEl.innerHTML = `
                    <div class="azota-podium-slot rank-1" style="margin: 0 auto; min-width: 180px;">
                        <div class="azota-podium-avatar"><span class="azota-podium-crown">👑</span>🥇</div>
                        <div class="azota-podium-name" title="${escapeHtml(rank1.student_name)}">${escapeHtml(rank1.student_name)}</div>
                        <div class="azota-podium-score">${getLBScore(rank1)}</div>
                        <div class="azota-podium-time" title="${formatTime(rank1.time_elapsed)}">${formatTimeCompact(rank1.time_elapsed)}</div>
                        <div class="azota-podium-bar">Quán quân</div>
                    </div>
                `;
            } else {
                podiumEl.style.display = 'none';
            }
        }

        // Render Bảng danh sách thí sinh
        let tableHtml = `
            <div class="azota-lb-table-wrap">
                <table class="azota-lb-table">
                    <thead>
                        <tr>
                            <th class="col-rank" style="text-align: center;">Hạng</th>
                            <th class="col-name">Thí sinh</th>
                            <th class="col-score" style="text-align: center;">Điểm số</th>
                            <th class="col-time" style="text-align: right;">Thời gian</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        listData.forEach((item, index) => {
            let rank = index + 1;
            let medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : rank;
            let isMe = Boolean(currentStudent && item.student_name.trim().toLowerCase() === currentStudent.trim().toLowerCase());
            
            let itemTotalQ = item.total_questions || currentData.length;
            let scaledScoreItem = itemTotalQ > 0 ? ((item.score / itemTotalQ) * 10).toFixed(1) : item.score;
            
            tableHtml += `
                <tr class="${isMe ? 'is-current-user' : ''}">
                    <td class="col-rank" style="text-align: center;">
                        <span class="azota-lb-rank-badge ${rank <= 3 ? 'top' : ''}">${medal}</span>
                    </td>
                    <td class="col-name">
                        <span class="lb-student-name">${escapeHtml(item.student_name)}</span>
                        ${isMe ? '<span class="azota-lb-you-tag">Bạn</span>' : ''}
                    </td>
                    <td class="col-score" style="text-align: center;">
                        <span class="lb-score-main">${item.score}</span>
                        <span class="lb-score-sub">/${itemTotalQ} (${scaledScoreItem}đ)</span>
                    </td>
                    <td class="col-time" style="text-align: right;">
                        <span class="lb-time-text" title="${formatTime(item.time_elapsed)}">
                            <i class="ri-time-line"></i> ${formatTimeCompact(item.time_elapsed)}
                        </span>
                    </td>
                </tr>
            `;
        });

        tableHtml += `</tbody></table></div>`;
        lbList.innerHTML = tableHtml;
    } catch(err) {
        console.warn("Lỗi tải bảng xếp hạng:", err);
    }
}

// --- HÀM RENDER TOÀN BỘ KẾT QUẢ, ĐÁP ÁN, LỜI GIẢI VÀ GIA SƯ AI SAU KHI NỘP BÀI ---
function renderSubmissionReview(score, totalQues, totalTimeElapsed, userAnswers, resultsList) {
    // 1. Tạo Map kết quả từ Backend nếu có
    const resultsMap = {};
    if (Array.isArray(resultsList)) {
        resultsList.forEach(item => {
            resultsMap[item.question_index] = item;
        });
    }

    let correctCount = 0;
    let wrongCount = 0;
    let skippedCount = 0;

    // Đánh giá chi tiết từng câu hỏi trong đề
    const evaluatedQuestions = currentData.map((q, qIndex) => {
        const qType = getRealQuestionType(q);
        const origIdx = (q._originalIndex !== undefined) ? q._originalIndex : qIndex;
        const serverItem = resultsMap[origIdx];
        let userAnswer = userAnswers[qIndex];
        let correctAnswer = (serverItem && serverItem.correct_answer !== undefined && serverItem.correct_answer !== null && serverItem.correct_answer !== '') 
            ? serverItem.correct_answer 
            : q.correct_answer;
        let explain = (serverItem && serverItem.explain) ? serverItem.explain : (q.explain || '');

        // Đồng bộ ngược lại vào q trong currentData để các hàm khác (MathJax, re-render, review) đều có đủ data
        if (serverItem) {
            if (serverItem.correct_answer !== undefined && !q.correct_answer) {
                q.correct_answer = serverItem.correct_answer;
            }
            if (serverItem.explain && !q.explain) {
                q.explain = serverItem.explain;
            }
        }
        
        let status = 'wrong'; // 'correct', 'wrong', 'skipped'
        let earnedScore = 0;

        if (serverItem) {
            earnedScore = serverItem.earned !== undefined ? serverItem.earned : (serverItem.is_correct ? 1.0 : 0.0);
            
            if (qType === 'true_false') {
                if (userAnswer === null || userAnswer === undefined || userAnswer === '' || (typeof userAnswer === 'object' && Object.keys(userAnswer).length === 0)) {
                    status = 'skipped';
                } else if (earnedScore === 1.0) {
                    status = 'correct';
                } else {
                    status = 'wrong';
                }
            } else {
                if (serverItem.is_correct) {
                    status = 'correct';
                } else if (userAnswer === null || userAnswer === undefined || userAnswer === '' || (typeof userAnswer === 'object' && Object.keys(userAnswer).length === 0)) {
                    status = 'skipped';
                } else {
                    status = 'wrong';
                }
            }
        } else {
            // Tự chấm điểm chuẩn GD&ĐT
            if (qType === 'true_false') {
                const correctMap = (typeof correctAnswer === 'object' && correctAnswer) ? correctAnswer : {};
                const userMap = (typeof userAnswer === 'object' && userAnswer) ? userAnswer : {};
                let matchCount = 0;
                let userAnswersGiven = 0;
                ['a', 'b', 'c', 'd'].forEach(char => {
                    if (userMap[char] !== undefined) userAnswersGiven++;
                    if (userMap[char] !== undefined && Boolean(userMap[char]) === Boolean(correctMap[char])) {
                        matchCount++;
                    }
                });
                const scale = [0.0, 0.1, 0.25, 0.5, 1.0];
                earnedScore = scale[matchCount] !== undefined ? scale[matchCount] : 0.0;
                if (userAnswersGiven === 0) status = 'skipped';
                else if (matchCount === 4) status = 'correct';
                else status = 'wrong';
            } else if (qType === 'short_answer') {
                let uStr = String(userAnswer || '').trim();
                let cStr = String(correctAnswer || '').trim();
                if (!uStr) {
                    status = 'skipped';
                } else if (evaluateShortAnswerJS(uStr, cStr)) {
                    status = 'correct';
                    earnedScore = 1.0;
                } else {
                    status = 'wrong';
                }
            } else {
                // MCQ 4 lựa chọn: Chuẩn hóa so khớp đáp án
                if (userAnswer === null || userAnswer === undefined || userAnswer === '') {
                    status = 'skipped';
                } else {
                    let oIndex = 0;
                    if (q.options && q.options.length > 0) {
                        oIndex = q.options.indexOf(userAnswer);
                        if (oIndex === -1) oIndex = 0;
                    }
                    if (matchOptionToTarget(userAnswer, oIndex, correctAnswer)) {
                        status = 'correct';
                        earnedScore = 1.0;
                    } else {
                        status = 'wrong';
                    }
                }
            }
        }

        if (status === 'correct') correctCount++;
        else if (status === 'skipped') skippedCount++;
        else wrongCount++;

        return {
            q,
            qIndex,
            qType,
            userAnswer,
            correctAnswer,
            explain,
            status,
            earnedScore,
            serverItem
        };
    });

    const scaledScore = totalQues > 0 ? ((score / totalQues) * 10).toFixed(1) : "0.0";

    // Phân tích kết quả theo từng phần cấu trúc đề GDPT 2018 và câu phân vân
    let mcqTotal = 0, mcqCorrect = 0;
    let tfTotal = 0, tfCorrect = 0;
    let saTotal = 0, saCorrect = 0;
    let flaggedTotal = 0, flaggedCorrect = 0;
    let reviewPaletteHtml = '';

    evaluatedQuestions.forEach((item) => {
        const { qIndex, qType, status } = item;
        const isFlag = !!flaggedQuestions[qIndex];
        const isCorrect = (status === 'correct');
        if (isFlag) {
            flaggedTotal++;
            if (isCorrect) flaggedCorrect++;
        }

        if (qType === 'true_false') {
            tfTotal++;
            if (isCorrect) tfCorrect++;
        } else if (qType === 'short_answer') {
            saTotal++;
            if (isCorrect) saCorrect++;
        } else {
            mcqTotal++;
            if (isCorrect) mcqCorrect++;
        }

        reviewPaletteHtml += `
            <button type="button" class="azota-review-num ${status} ${isFlag ? 'flagged' : ''}" onclick="scrollToReviewQuestion(${qIndex})" title="Câu ${qIndex + 1}: ${status === 'correct' ? 'Đúng' : (status === 'wrong' ? 'Sai' : 'Chưa làm')}${isFlag ? ' (Đã phân vân)' : ''}">
                ${qIndex + 1}
            </button>
        `;
    });

    // 2. Render Score Board
    const scoreBoard = document.getElementById('score-board');
    scoreBoard.style.display = 'block';
    scoreBoard.innerHTML = `
        <div class="azota-result-card">
            <div class="azota-score-circle">
                <span class="big-num">${scaledScore}</span>
                <span class="scale">Điểm / 10</span>
            </div>
            <h2 class="azota-result-title">
                ${score >= totalQues * 0.8 ? '🎉 Kết Quả Xuất Sắc!' : (score >= totalQues * 0.5 ? '👏 Bạn Đã Hoàn Thành Bài Thi!' : '💪 Cần Cố Gắng Thêm Lần Sau!')}
            </h2>
            <p class="azota-result-subtitle">
                Bạn đạt <b>${score}</b> trên tổng số <b>${totalQues}</b> điểm của đề thi.
            </p>
            ${(window.examTabSwitchCount > 0 || (quizProgress && quizProgress.tabSwitchCount > 0)) ? `
                <div style="display:inline-flex; align-items:center; gap:6px; margin: 4px auto 14px; padding:6px 14px; border-radius:8px; background:#fff1f2; border:1px solid #fecaca; color:#be123c; font-size:0.88rem; font-weight:700;">
                    <i class="ri-alarm-warning-fill"></i> Ghi nhận rời tab / chuyển màn hình: ${window.examTabSwitchCount || quizProgress.tabSwitchCount} lần
                </div>
            ` : ''}

            <div class="azota-result-grid">
                <div class="azota-res-tile green">
                    <div class="val">${correctCount}</div>
                    <div class="desc"><i class="ri-checkbox-circle-line"></i> Số câu đúng</div>
                </div>
                <div class="azota-res-tile red">
                    <div class="val">${wrongCount}</div>
                    <div class="desc"><i class="ri-close-circle-line"></i> Số câu sai</div>
                </div>
                <div class="azota-res-tile gray">
                    <div class="val">${skippedCount}</div>
                    <div class="desc"><i class="ri-question-line"></i> Chưa làm</div>
                </div>
                <div class="azota-res-tile blue tile-time">
                    <div class="val" title="${formatTime(totalTimeElapsed)}">${formatTimeCompact(totalTimeElapsed)}</div>
                    <div class="desc"><i class="ri-time-line"></i> Thời gian</div>
                </div>
            </div>

            <!-- Thống kê tỷ lệ hoàn thành theo từng phần cấu trúc đề GDPT 2018 -->
            <div class="azota-res-breakdown">
                ${mcqTotal > 0 ? `
                    <div class="azota-res-breakdown-card">
                        <div class="part-name"><i class="ri-list-check-2"></i> Phần I: Trắc nghiệm</div>
                        <div class="part-stat">${mcqCorrect} / ${mcqTotal} câu</div>
                        <div class="part-rate">Đạt ${Math.round((mcqCorrect / mcqTotal) * 100)}%</div>
                    </div>` : ''}
                ${tfTotal > 0 ? `
                    <div class="azota-res-breakdown-card">
                        <div class="part-name"><i class="ri-checkbox-multiple-line"></i> Phần II: Đúng / Sai</div>
                        <div class="part-stat">${tfCorrect} / ${tfTotal} câu</div>
                        <div class="part-rate">Đạt ${Math.round((tfCorrect / tfTotal) * 100)}%</div>
                    </div>` : ''}
                ${saTotal > 0 ? `
                    <div class="azota-res-breakdown-card">
                        <div class="part-name"><i class="ri-edit-line"></i> Phần III: Trả lời ngắn</div>
                        <div class="part-stat">${saCorrect} / ${saTotal} câu</div>
                        <div class="part-rate">Đạt ${Math.round((saCorrect / saTotal) * 100)}%</div>
                    </div>` : ''}
            </div>

            ${flaggedTotal > 0 ? `
                <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 10px; padding: 10px 14px; font-size: 0.88rem; color: #92400e; margin: 12px 0; display: flex; align-items: center; gap: 8px; text-align: left;">
                    <i class="ri-flag-fill" style="color: #d97706; font-size: 1.15rem; flex-shrink: 0;"></i>
                    <span>Bạn đã đánh dấu phân vân <b>${flaggedTotal}</b> câu, trong đó làm đúng <b>${flaggedCorrect}/${flaggedTotal}</b> câu (${Math.round((flaggedCorrect / flaggedTotal) * 100)}%).</span>
                </div>` : ''}

            <!-- Bản đồ câu hỏi tương tác (Interactive Question Palette) -->
            <div style="margin: 14px 0 18px 0; text-align: left;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 0.88rem; font-weight: 700; color: #475569;"><i class="ri-grid-line"></i> Bản đồ câu hỏi (Nhấn để cuộn nhanh):</span>
                    <span style="font-size: 0.78rem; color: #64748b;">🟢 Đúng &bull; 🔴 Sai &bull; ⚪ Chưa làm</span>
                </div>
                <div class="azota-review-palette">
                    ${reviewPaletteHtml}
                </div>
            </div>

            <!-- Các nút hành động chính -->
            <div class="result-action-btns">
                <button type="button" class="btn-primary result-btn-primary" onclick="switchResultView('review')">
                    <i class="ri-file-list-3-line"></i> <span>Xem chi tiết đáp án & lời giải</span>
                </button>
                <div class="result-btn-row">
                    <button type="button" class="btn-outline result-btn-lb" onclick="switchResultView('leaderboard')">
                        <i class="ri-trophy-fill"></i> <span>Bảng xếp hạng</span>
                    </button>
                    <button type="button" class="btn-outline result-btn-retry" onclick="${currentMode === 'practice' ? 'restartPractice()' : 'restartExam()'}">
                        <i class="ri-refresh-line"></i> <span>Làm lại đề</span>
                    </button>
                </div>
                <button type="button" class="btn-outline result-btn-exit" onclick="exitMinimalMode()">
                    <i class="ri-logout-box-r-line"></i> <span>Thoát phòng thi</span>
                </button>
            </div>
        </div>
    `;

    // Render BỘ LỌC CÂU HỎI vào reviewFilterBarContainer (nằm ngay dưới tabs)
    const filterContainer = document.getElementById('reviewFilterBarContainer');
    if (filterContainer) {
        filterContainer.style.display = 'block';
        filterContainer.innerHTML = `
            <div class="azota-review-filter-bar">
                <span class="filter-title"><i class="ri-filter-3-line"></i> Lọc:</span>
                <button type="button" class="azota-filter-tab active" data-filter="all" onclick="filterReviewQuestions('all')">
                    Tất cả <span class="tab-count">${totalQues}</span>
                </button>
                <button type="button" class="azota-filter-tab tab-wrong" data-filter="wrong" onclick="filterReviewQuestions('wrong')">
                    <i class="ri-close-circle-fill" style="color: #ef4444;"></i> Câu sai <span class="tab-count">${wrongCount}</span>
                </button>
                <button type="button" class="azota-filter-tab tab-correct" data-filter="correct" onclick="filterReviewQuestions('correct')">
                    <i class="ri-checkbox-circle-fill" style="color: #10b981;"></i> Câu đúng <span class="tab-count">${correctCount}</span>
                </button>
                <button type="button" class="azota-filter-tab tab-skipped" data-filter="skipped" onclick="filterReviewQuestions('skipped')">
                    <i class="ri-question-fill" style="color: #f59e0b;"></i> Chưa làm <span class="tab-count">${skippedCount}</span>
                </button>
            </div>
        `;
    }

    // Cập nhật tab số lượng câu hỏi
    const tabReviewCount = document.getElementById('tabReviewCount');
    if (tabReviewCount) tabReviewCount.innerText = `${totalQues} câu`;
    const tabNav = document.getElementById('resultNavTabs');
    if (tabNav) tabNav.style.display = 'flex';

    // 3. Render TOÀN BỘ CÂU HỎI VÀO #quiz-container (Từ câu 1 đến câu N)
    const container = document.getElementById('quiz-container');
    container.innerHTML = '';

    evaluatedQuestions.forEach((item) => {
        const { q, qIndex, qType, userAnswer, correctAnswer, explain, status, earnedScore, serverItem } = item;
        const card = document.createElement('div');
        card.className = `review-question-card status-${status}`;
        card.id = `review_q_${qIndex}`;
        card.dataset.resultStatus = status;

        let groupTitleHtml = q.group_title ? `<div style="background: #fef9c3; padding: 8px 12px; border-radius: 8px; margin-bottom: 12px; font-size: 0.9rem; font-weight: 600; color: #854d0e;">${q.group_title.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>` : '';

        let typeBadge = '';
        if (qType === 'true_false') {
            typeBadge = '<span style="background: #e0f2fe; color: #0369a1; padding: 3px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; border: 1px solid #bae6fd;">Đúng / Sai</span>';
        } else if (qType === 'short_answer') {
            typeBadge = '<span style="background: #fef3c7; color: #92400e; padding: 3px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; border: 1px solid #fde68a;">Trả lời ngắn</span>';
        } else {
            typeBadge = '<span style="background: #f1f5f9; color: #475569; padding: 3px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; border: 1px solid #e2e8f0;">Trắc nghiệm 4 lựa chọn</span>';
        }

        let statusBadge = '';
        if (status === 'correct') {
            statusBadge = `<span class="review-status-badge correct"><i class="ri-checkbox-circle-fill"></i> Đúng (+${earnedScore}đ)</span>`;
        } else if (status === 'skipped') {
            statusBadge = `<span class="review-status-badge skipped"><i class="ri-question-fill"></i> Chưa trả lời (0đ)</span>`;
        } else {
            statusBadge = `<span class="review-status-badge wrong"><i class="ri-close-circle-fill"></i> Sai (+${earnedScore}đ)</span>`;
        }

        // Tìm chữ cái đáp án đúng và lựa chọn của học sinh cho câu MCQ (hỗ trợ cả xáo trộn phương án)
        let correctCharDisplay = '';
        let userCharDisplay = '';
        let revCorrectIdx = -1;
        let revUserPickIdx = -1;

        if (qType === 'mcq') {
            const mcqRes = resolveMcqIndices(q, userAnswer, correctAnswer, serverItem, status);
            revCorrectIdx = mcqRes.revCorrectIdx;
            revUserPickIdx = mcqRes.revUserPickIdx;
            userCharDisplay = mcqRes.userCharDisplay;
            correctCharDisplay = mcqRes.correctCharDisplay;
        }

        // Tóm tắt kết quả nhanh trên mỗi câu hỏi
        let summaryBannerHtml = '';
        if (qType === 'mcq') {
            if (status === 'correct') {
                const displayChar = correctCharDisplay || userCharDisplay || '';
                summaryBannerHtml = `
                    <div class="review-quick-banner is-correct">
                        <i class="ri-checkbox-circle-fill" style="font-size: 1.15rem;"></i> 
                        <span>Chính xác! Bạn đã chọn đúng đáp án <b>${displayChar}</b></span>
                    </div>
                `;
            } else if (status === 'skipped') {
                summaryBannerHtml = `
                    <div class="review-quick-banner is-skipped">
                        <i class="ri-question-fill" style="font-size: 1.15rem;"></i> 
                        <span>Chưa trả lời! Đáp án đúng là: <b class="highlight-correct">${correctCharDisplay || ''}</b></span>
                    </div>
                `;
            } else {
                summaryBannerHtml = `
                    <div class="review-quick-banner is-wrong">
                        <i class="ri-close-circle-fill" style="font-size: 1.15rem;"></i> 
                        <span>Lựa chọn của bạn: <b class="highlight-wrong">${userCharDisplay || '(Chưa chọn)'}</b> &nbsp;|&nbsp; Đáp án chính xác: <b class="highlight-correct">${correctCharDisplay || ''}</b></span>
                    </div>
                `;
            }
        }

        let cleanQText = (q.question || '').replace(/^(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])\s*/i, '');
        let cardHtml = `
            ${groupTitleHtml}
            <div class="review-q-header">
                <div class="review-q-number">
                    <span>Câu ${qIndex + 1} / ${totalQues}</span>
                    ${typeBadge}
                </div>
                <div>${statusBadge}</div>
            </div>
            <div class="review-q-text">${cleanQText.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>
            ${summaryBannerHtml}
        `;

        if (qType === 'true_false') {
            const correctMap = (typeof correctAnswer === 'object' && correctAnswer) ? correctAnswer : {};
            const userMap = (typeof userAnswer === 'object' && userAnswer) ? userAnswer : {};
            
            cardHtml += `<div class="review-tf-list">`;
            ['a', 'b', 'c', 'd'].forEach((char, oIndex) => {
                let optText = (q.options && q.options[oIndex]) ? q.options[oIndex].replace(/^[a-d][\.\:\)]\s*/i, '') : `Ý kiến ${char.toUpperCase()}`;
                let isCorrectVal = (correctMap[char] !== undefined) ? correctMap[char] : correctMap[String(oIndex)];
                let userVal = (userMap[char] !== undefined) ? userMap[char] : userMap[String(oIndex)];
                let isMatch = (userVal !== undefined && Boolean(userVal) === Boolean(isCorrectVal));
                let tfState = (userVal === undefined) ? 'is-skipped' : (isMatch ? 'is-correct' : 'is-wrong');
                
                cardHtml += `
                    <div class="review-tf-item ${tfState}">
                        <div class="review-tf-text">
                            <b class="review-tf-char">${char})</b> <span>${optText}</span>
                        </div>
                        <div class="review-tf-badges">
                            <span class="review-tf-user-pick ${userVal === undefined ? 'skipped' : (isMatch ? 'correct' : 'wrong')}">
                                Bạn chọn: <b>${userVal === true ? 'Đúng' : (userVal === false ? 'Sai' : 'Chưa chọn')}</b>
                            </span>
                            <span class="review-tf-correct-ans">
                                Đáp án: <b>${isCorrectVal === true ? 'Đúng' : 'Sai'}</b>
                            </span>
                            <span class="review-tf-icon">${userVal === undefined ? '⚠️' : (isMatch ? '✅' : '❌')}</span>
                        </div>
                    </div>
                `;
            });
            cardHtml += `</div>`;
        } else if (qType === 'short_answer') {
            const uStr = String(userAnswer || '').trim();
            const cStr = String(correctAnswer || '').trim();
            const isMatch = (status === 'correct');
            
            cardHtml += `
                <div class="review-sa-box ${isMatch ? 'is-correct' : (uStr ? 'is-wrong' : 'is-skipped')}">
                    <div class="review-sa-row">
                        <span class="review-sa-label">Câu trả lời của bạn:</span> 
                        <span class="review-sa-val ${isMatch ? 'correct' : (uStr ? 'wrong' : 'skipped')}">${escapeHtml(uStr) || '(Chưa điền)'}</span>
                        <span class="review-sa-icon">${isMatch ? '✅' : (uStr ? '❌' : '⚠️')}</span>
                    </div>
                    <div class="review-sa-row">
                        <span class="review-sa-label">Đáp án chính xác:</span> 
                        <span class="review-sa-val correct highlight">${escapeHtml(cStr)}</span>
                    </div>
                </div>
            `;
        } else {
            // MCQ 4 lựa chọn: Dùng trực tiếp revCorrectIdx và revUserPickIdx đã đồng bộ chính xác
            cardHtml += `<div class="review-opt-list">`;
            (q.options || []).forEach((opt, oIndex) => {
                let char = opt.match(/^[A-F]/i) ? opt.match(/^[A-F]/i)[0].toUpperCase() : String.fromCharCode(65 + oIndex);
                let isThisCorrect = (oIndex === revCorrectIdx);
                let isThisUserPick = (oIndex === revUserPickIdx);
                
                let optClass = 'review-opt-item';
                let tagHtml = '';
                
                if (isThisCorrect && isThisUserPick) {
                    optClass += ' is-correct';
                    tagHtml = `<span class="review-opt-tag tag-correct"><i class="ri-check-double-line"></i> Bạn đã chọn đúng</span>`;
                } else if (isThisCorrect) {
                    optClass += ' is-correct';
                    tagHtml = `<span class="review-opt-tag tag-correct"><i class="ri-check-line"></i> Đáp án đúng</span>`;
                } else if (isThisUserPick) {
                    optClass += ' is-user-wrong';
                    tagHtml = `<span class="review-opt-tag tag-wrong"><i class="ri-close-line"></i> Bạn đã chọn</span>`;
                }

                cardHtml += `
                    <div class="${optClass}">
                        <div class="review-opt-badge">${char}</div>
                        <div class="review-opt-content">${opt.replace(/^[A-F][\.\:\)]\s*/i, '')}</div>
                        ${tagHtml}
                    </div>
                `;
            });
            cardHtml += `</div>`;
        }

        // Khung Lời giải chi tiết
        if (explain && explain.trim() !== '') {
            cardHtml += `
                <div class="review-explain-box">
                    <div class="review-explain-title"><i class="ri-lightbulb-fill"></i> Hướng dẫn giải chi tiết:</div>
                    <div class="review-explain-body">${explain.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>
                </div>
            `;
        } else if (correctCharDisplay) {
            cardHtml += `
                <div class="review-explain-box fallback">
                    <div class="review-explain-title"><i class="ri-information-fill"></i> Thông tin đáp án:</div>
                    <div class="review-explain-body">Đáp án chính xác của câu hỏi này là: <b>${correctCharDisplay}</b></div>
                </div>
            `;
        }

        card.innerHTML = cardHtml;

        // Tích hợp Gia sư ảo AI WebLLM cho từng câu hỏi (nếu bật tính năng)
        if (window.ENABLE_WEBLLM && window.WebLLMTutor) {
            const aiBox = document.createElement('div');
            aiBox.className = 'webllm-feedback-container';
            card.appendChild(aiBox);
            
            const isMistake = (status !== 'correct');
            const explainBtn = window.WebLLMTutor.createExplainButton(() => {
                window.WebLLMTutor.renderExplainCard(aiBox, q, userAnswer, isMistake);
                explainBtn.style.display = 'none';
            }, isMistake);
            explainBtn.style.marginTop = '12px';
            card.appendChild(explainBtn);
        }

        container.appendChild(card);
    });

    renderMath(container);
}

// --- HÀM NỘP BÀI THI & CHẤM ĐIỂM HOÀN CHỈNH (CHO CẢ LUYỆN TẬP VÀ THI THỬ) ---
async function submitExam(isReview = false) {
    clearInterval(timerInterval);
    const timerDisplay = document.getElementById('timerDisplay');
    if (timerDisplay) timerDisplay.style.display = 'none';
    
    if (!isReview) {
        showGlobalLoader({
            title: "Đang nộp bài & chấm điểm...",
            subtitle: "Hệ thống đang so khớp kết quả và lưu bài thi..."
        });
    }

    try {
        let sessionTime = startTime > 0 ? Math.floor((Date.now() - startTime) / 1000) : 0;
        let totalTimeElapsed = 0;
        if (isReview) {
            totalTimeElapsed = (quizProgress && quizProgress.timeElapsed) || 0;
        } else {
            if (currentTimeLimit > 0 && quizProgress && typeof quizProgress.timeRemaining === 'number') {
                totalTimeElapsed = Math.max(1, (currentTimeLimit * 60) - Math.max(0, quizProgress.timeRemaining));
            } else if (quizProgress && typeof quizProgress.timeElapsed === 'number' && quizProgress.timeElapsed > 0) {
                totalTimeElapsed = quizProgress.timeElapsed;
            } else {
                totalTimeElapsed = sessionTime > 0 ? sessionTime : 1;
            }
        }
        let score = 0;
    
    // 1. Thu thập câu trả lời của học sinh (hỗ trợ cả Luyện tập và Thi thử)
    let userAnswers = {};
    currentData.forEach((q, qIndex) => {
        let qType = q.type || 'mcq';
        if (isReview && quizProgress && quizProgress.answers) {
            userAnswers[qIndex] = quizProgress.answers[qIndex];
        } else {
            if (currentMode === 'practice') {
                // Trong chế độ Luyện tập: Lấy câu trả lời đã lưu của từng câu
                if (q.user_answer_practice !== undefined) {
                    userAnswers[qIndex] = q.user_answer_practice;
                } else if (qIndex === currentQuestionIndex) {
                    // Nếu đang làm dở câu hiện tại
                    if (qType === 'true_false') {
                        userAnswers[qIndex] = window.currentPracticeTF || {};
                    } else if (qType === 'short_answer') {
                        const saInput = document.getElementById('pract_sa_input');
                        userAnswers[qIndex] = saInput ? saInput.value.trim() : '';
                    } else {
                        const checked = document.querySelector('input[name="pract_radio"]:checked');
                        if (checked && q.options) {
                            const optLabels = document.querySelectorAll('#quiz-container .option-practice');
                            optLabels.forEach((lbl, oIdx) => {
                                if (lbl.querySelector('input:checked')) userAnswers[qIndex] = q.options[oIdx];
                            });
                        }
                    }
                } else if (quizProgress && quizProgress.answers && quizProgress.answers[qIndex] !== undefined) {
                    userAnswers[qIndex] = quizProgress.answers[qIndex];
                } else {
                    userAnswers[qIndex] = null;
                }
            } else {
                // Trong chế độ Thi thử
                if (qType === 'true_false') {
                    userAnswers[qIndex] = (quizProgress && quizProgress.answers && quizProgress.answers[qIndex]) || {};
                } else if (qType === 'short_answer') {
                    const saInput = document.getElementById(`exam_sa_${qIndex}`);
                    userAnswers[qIndex] = saInput ? saInput.value.trim() : ((quizProgress && quizProgress.answers && quizProgress.answers[qIndex]) || '');
                } else {
                    const selected = document.querySelector(`input[name="exam_${qIndex}"]:checked`);
                    userAnswers[qIndex] = selected ? selected.value : ((quizProgress && quizProgress.answers && quizProgress.answers[qIndex]) || null);
                }
            }
        }
    });

    const urlParams = new URLSearchParams(window.location.search);
    const quizId = urlParams.get('quiz_id') || urlParams.get('id');
    let backendResults = null;
    let verifiedScore = null;

    // 2. Chấm điểm phía Server nếu có kết nối và có mã đề thi
    if (!isReview && quizId) {
        try {
            // QUAN TRỌNG: Chuyển đổi đáp án từ chỉ số ĐÃ TRỘN sang chỉ số GỐC
            // để Backend so khớp đúng câu hỏi với đáp án tương ứng
            const serverAnswers = {};
            currentData.forEach((q, qIndex) => {
                const origIdx = (q._originalIndex !== undefined) ? q._originalIndex : qIndex;
                if (userAnswers[qIndex] !== undefined) {
                    serverAnswers[origIdx] = userAnswers[qIndex];
                }
            });

            const res = await fetch(`${API_BASE_URL}/api/student/submit_exam`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    quiz_id: quizId,
                    student_name: studentName || 'Học sinh',
                    student_token: authToken || '',
                    answers: serverAnswers,
                    time_elapsed: totalTimeElapsed,
                    session_id: window.currentExamSessionId || (quizProgress && quizProgress.sessionId) || '',
                    tab_switch_count: window.examTabSwitchCount || (quizProgress && quizProgress.tabSwitchCount) || 0
                })
            });
            const resData = await res.json();
            if (res.ok && resData.status === 'success') {
                verifiedScore = resData.score;
                backendResults = resData.results;
            }
        } catch(err) {
            console.warn("Lỗi kết nối server chấm điểm, sử dụng cơ chế chấm điểm cục bộ:", err);
        }
    }

    // 3. Fallback chấm điểm cục bộ nếu không có kết quả từ server
    if (verifiedScore !== null) {
        score = verifiedScore;
    } else {
        currentData.forEach((q, qIndex) => {
            let userAnswer = userAnswers[qIndex];
            let qType = getRealQuestionType(q);
            
            if (qType === 'true_false') {
                let correctMap = (typeof q.correct_answer === 'object' && q.correct_answer) ? q.correct_answer : {};
                let userMap = (typeof userAnswer === 'object' && userAnswer) ? userAnswer : {};
                let matchCount = 0;
                let keys = Object.keys(correctMap);
                if (keys.length === 0) keys = ['a', 'b', 'c', 'd']; // Fallback
                keys.forEach(char => {
                    let isCorrectVal = correctMap[char];
                    let userVal = userMap[char];
                    if (userVal !== undefined && Boolean(userVal) === Boolean(isCorrectVal)) {
                        matchCount++;
                    }
                });
                // Thang điểm chuẩn Bộ GD&ĐT cho câu Đúng/Sai 4 ý
                const tfScale = {0: 0, 1: 0.1, 2: 0.25, 3: 0.5, 4: 1.0};
                let earned = (matchCount in tfScale) ? tfScale[matchCount] : (keys.length > 0 ? matchCount / keys.length : 0.0);
                score += earned;
            } else if (qType === 'short_answer') {
                if (evaluateShortAnswerJS(userAnswer, q.correct_answer)) score += 1;
            } else {
                let oIndex = 0;
                if (q.options && q.options.length > 0) {
                    oIndex = q.options.indexOf(userAnswer);
                    if (oIndex === -1) oIndex = 0;
                }
                if (matchOptionToTarget(userAnswer, oIndex, q.correct_answer)) score += 1;
            }
        });
        score = Math.round(score * 100) / 100;
    }

    // 4. Cập nhật các trạng thái nút bấm và giao diện
    const submitBtn = document.getElementById('submitBtn');
    if (submitBtn) submitBtn.style.display = 'none';
    const stickySubmit = document.getElementById('stickySubmitBtn');
    if (stickySubmit) stickySubmit.style.display = 'none';
    const sideCol = document.getElementById('azotaSideExamCol');
    if (sideCol) sideCol.style.setProperty('display', 'none', 'important');
    const mobileBar = document.getElementById('azotaMobileExamBar');
    if (mobileBar) mobileBar.style.setProperty('display', 'none', 'important');
    toggleMobileNavSheet(false);
    document.body.classList.add('quiz-completed');
    destroyExamAntiCheat();
    destroyExamSessionUnique();

    // 5. Render toàn bộ Bảng điểm tổng kết và Danh sách tất cả câu hỏi có giải thích
    renderSubmissionReview(score, currentData.length, totalTimeElapsed, userAnswers, backendResults);

    // 6. Lưu tiến trình làm bài vào Storage và gọi Bảng xếp hạng
    if (!isReview && isStudentMode && studentName) { 
        if (!quizProgress.answers) quizProgress.answers = {};
        Object.assign(quizProgress.answers, userAnswers);
        quizProgress.completed = true;
        quizProgress.score = score;
        quizProgress.timeElapsed = totalTimeElapsed;
        
        if (!quizProgress.history) quizProgress.history = [];
        quizProgress.history.push({
            score: score,
            total: currentData.length,
            timeElapsed: totalTimeElapsed,
            date: new Date().toLocaleString('vi-VN'),
            mode: currentMode === 'practice' ? 'Luyện tập' : 'Thi thử'
        });
        
        saveProgressToLocal();
        sendPing();
    }

    // Luôn tải bảng xếp hạng sau khi nộp bài
    await fetchLeaderboard(quizId);
    switchResultView('review');

        showToast("🎉 Đã nộp bài thành công!", "success");

        // 7. Cuộn trang mượt mà lên đầu để xem kết quả
        const quizContainer = document.getElementById('quiz-container');
        if (quizContainer) quizContainer.scrollTo({ top: 0, behavior: 'smooth' });
        window.scrollTo({ top: 0, behavior: 'smooth' });
    } finally {
        hideGlobalLoader();
    }
}

function exitMinimalMode() {
    destroyExamAntiCheat();
    destroyExamSessionUnique();
    const isCompleted = document.body.classList.contains('quiz-completed');
    const msg = isCompleted 
        ? "Bạn có muốn quay về Trang chủ & Bảng điểm không?" 
        : "Bạn có muốn tạm dừng và thoát khỏi giao diện làm bài không? (Tiến trình của bạn vẫn được bảo lưu)";
    if (confirm(msg)) {
        document.body.classList.remove('minimal-mode');
        document.body.classList.remove('quiz-completed');
        const mobileBar = document.getElementById('azotaMobileExamBar');
        if (mobileBar) mobileBar.style.display = 'none';
        toggleMobileNavSheet(false);
        if (document.fullscreenElement) {
            document.exitFullscreen().catch(err => console.log(err));
        }
        if (isCompleted) {
            window.location.href = '/';
        } else {
            if (quizProgress && !quizProgress.completed) {
                quizProgress.paused = true;
                saveProgressToLocal();
            }
            window.location.reload();
        }
    }
}

// Hàm hỗ trợ chèn nhanh text vào khung Code Editor
function insertTextToEditor(text) {
    const editor = document.getElementById('codeEditor');
    if (!editor) return;
    
    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    const val = editor.value;
    
    editor.value = val.substring(0, start) + text + val.substring(end);
    editor.selectionStart = editor.selectionEnd = start + text.length;
    editor.focus();
    
    updateSyntaxHighlight();
    currentData = parseEditorText(editor.value);
    renderPreviewAll();
}

// Hàm xử lý Highlight Code (Syntax Highlighting)
function updateSyntaxHighlight() {
    const codeEditor = document.getElementById('codeEditor');
    const codeHighlight = document.getElementById('codeHighlight');
    if (!codeEditor || !codeHighlight) return;
    
    let text = codeEditor.value;
    let escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    
    // Đổi màu các keyword và pattern
    escaped = escaped.replace(/(\[HÌNH_ẢNH_\d+\])/g, '<span class="hl-image">$1</span>');
    escaped = escaped.replace(/(\\\([\s\S]*?\\\))/g, '<span class="hl-math">$1</span>');
    escaped = escaped.replace(/^(\s*)(Câu|Bài|Question|Q)(\s*\d+[\.\:\-\)])/gim, '$1<span class="hl-question">$2$3</span>');
    escaped = escaped.replace(/^(\s*)(\*\s*[A-F][\.\:\)])/gim, '$1<span class="hl-correct">$2</span>');
    escaped = escaped.replace(/^(\s*)([A-F][\.\:\)])/gim, '$1<span class="hl-option">$2</span>');
    escaped = escaped.replace(/^(\s*)(PHẦN|PART|CHƯƠNG|BÀI TẬP|I{1,3}\.|IV\.|V\.|VI{0,3}\.)(.*)$/gim, '$1<span class="hl-group">$2$3</span>');
    escaped = escaped.replace(/(&lt;\/?(b|i|u|sub|sup|MARK)&gt;)/gi, '<span class="hl-html">$1</span>');
    
    // Fix lỗi mất padding-bottom khi người dùng gõ Enter xuống dòng mới nhất
    if (escaped.endsWith('\n')) escaped += ' ';
    
    codeHighlight.innerHTML = escaped;
}

// --- XỬ LÝ NÚT CÂU TIẾP TRÊN MOBILE BOTTOM BAR ---
window.mobileNextQuestionAction = function() {
    if (currentMode === 'practice') {
        const isLast = (currentQuestionIndex === currentData.length - 1);
        if (!practiceAnswered) {
            showToast("Vui lòng trả lời câu hỏi trước khi sang câu tiếp theo!", "info");
            return;
        }
        if (isLast) {
            submitExam();
        } else {
            nextPracticeQuestion();
        }
    } else {
        // Trong chế độ thi thử (exam) - cuộn tới câu hỏi tiếp theo
        const questions = document.querySelectorAll('.question-box');
        let targetIndex = -1;
        let currentIndex = 0;
        
        for (let i = 0; i < questions.length; i++) {
            const rect = questions[i].getBoundingClientRect();
            // Nếu câu hỏi đang nằm phần trên của màn hình
            if (rect.top > 0 && rect.top < window.innerHeight / 2) {
                currentIndex = i;
                break;
            } else if (rect.top >= window.innerHeight / 2) {
                currentIndex = Math.max(0, i - 1);
                break;
            }
        }

        targetIndex = currentIndex + 1;
        if (targetIndex < questions.length) {
            const yOffset = -80; // Trừ hao khoảng cách header dính
            const element = questions[targetIndex];
            const y = element.getBoundingClientRect().top + window.pageYOffset + yOffset;
            window.scrollTo({ top: y, behavior: 'smooth' });
        } else {
            toggleMobileNavSheet(true);
            showToast("Bạn đã đến cuối đề thi. Nhấn NỘP BÀI THI NGAY trong bảng điều hướng!", "info");
        }
    }
};

function showNextQuestionButton() {
    const isLast = (currentQuestionIndex === currentData.length - 1);
    const nextBtn = document.getElementById('nextBtn');
    if (nextBtn) {
        nextBtn.style.display = 'inline-flex';
        nextBtn.innerHTML = isLast ? 'Xem kết quả tổng kết <i class="ri-check-double-line"></i>' : 'Câu tiếp theo <i class="ri-arrow-right-line"></i>';
        setTimeout(() => {
            // Chỉ cuộn tới nút này nếu trên desktop (nút này visible)
            if (window.innerWidth > 960) {
                nextBtn.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }, 100);
    }
    const mobileNextBtn = document.getElementById('mobileNextBtn');
    if (mobileNextBtn) {
        mobileNextBtn.innerHTML = isLast ? 'Kết quả <i class="ri-check-double-line"></i>' : 'Câu tiếp <i class="ri-arrow-right-line"></i>';
    }
}

// Hàm hiển thị màn hình đăng nhập cho thí sinh tự do khi đang ở trang làm bài
window.forceShowLogin = function() {
    const mainApp = document.getElementById('mainApp');
    if (mainApp) mainApp.style.setProperty('display', 'none', 'important');
    
    const azotaNavLinks = document.getElementById('azotaNavLinks');
    if (azotaNavLinks) azotaNavLinks.style.display = 'flex'; // Cho phép chuyển qua lại Đăng nhập / Đăng ký
    
    const authBox = document.getElementById('authBox');
    if (authBox) {
        authBox.classList.remove('hidden');
        authBox.style.setProperty('display', 'flex', 'important');
        authBox.style.justifyContent = 'center';
        authBox.style.alignItems = 'center';
        authBox.style.minHeight = '85vh';
        authBox.style.width = '100%';
    }
    
    const loginForm = document.getElementById('loginForm');
    if (loginForm) loginForm.style.setProperty('display', 'flex', 'important');
    
    const registerForm = document.getElementById('registerForm');
    if (registerForm) registerForm.style.setProperty('display', 'none', 'important');
};

// =========================================================================
// ĐIỀU KHIỂN MODAL PHÁP LÝ & BẢO MẬT (PRIVACY POLICY, TERMS, ABOUT, CONTACT)
// =========================================================================
function openLegalModal(tab = 'privacy', pushHistory = true) {
    const modal = document.getElementById('legalModal');
    if (!modal) return;
    modal.style.display = 'flex';
    switchLegalTab(tab, false);
    if (pushHistory && ['privacy', 'terms', 'about', 'contact'].includes(tab)) {
        if (window.location.pathname !== '/' + tab) {
            history.pushState({ modal: 'legal', tab: tab }, '', '/' + tab);
        }
    }
}

function closeLegalModal(updateHistory = true) {
    const modal = document.getElementById('legalModal');
    if (modal) modal.style.display = 'none';
    if (updateHistory && ['/privacy', '/terms', '/about', '/contact'].includes(window.location.pathname)) {
        history.pushState(null, '', '/');
    }
}

function switchLegalTab(tabName, updateHistory = true) {
    const tabs = ['privacy', 'terms', 'about', 'contact'];
    const titleMap = {
        'privacy': 'Chính sách bảo mật (Privacy Policy)',
        'terms': 'Điều khoản dịch vụ & Sử dụng (Terms)',
        'about': 'Giới thiệu về Dự án HocNhanhTN (About)',
        'contact': 'Liên hệ & Đóng góp ý kiến (Contact)'
    };

    const titleEl = document.getElementById('legalModalTitle');
    if (titleEl && titleMap[tabName]) {
        titleEl.innerText = titleMap[tabName];
    }

    tabs.forEach(t => {
        const btn = document.getElementById(`tabBtn${t.charAt(0).toUpperCase() + t.slice(1)}`);
        const content = document.getElementById(`legalContent${t.charAt(0).toUpperCase() + t.slice(1)}`);
        
        if (btn) {
            if (t === tabName) {
                btn.style.background = '#ffffff';
                btn.style.color = '#2563eb';
            } else {
                btn.style.background = 'transparent';
                btn.style.color = '#64748b';
            }
        }
        if (content) {
            content.style.display = (t === tabName) ? 'block' : 'none';
        }
    });

    if (updateHistory && tabs.includes(tabName) && window.location.pathname !== '/' + tabName) {
        history.replaceState({ modal: 'legal', tab: tabName }, '', '/' + tabName);
    }
}

// =========================================================================
// BẢO LƯU TIẾN TRÌNH TỨC THÌ KHI HỌC SINH TẮT TRÌNH DUYỆT HOẶC ĐỔI TRANG
// =========================================================================
window.addEventListener('beforeunload', () => {
    if (isStudentMode && quizProgress && !quizProgress.completed && quizProgress.startedAt) {
        const quizId = getCurrentQuizId();
        if (quizId) {
            if (currentTimeLimit > 0) {
                const elapsed = Math.floor((Date.now() - quizProgress.startedAt) / 1000);
                quizProgress.timeRemaining = Math.max(0, (currentTimeLimit * 60) - elapsed);
                quizProgress.timeElapsed = Math.min(currentTimeLimit * 60, elapsed);
            } else {
                quizProgress.timeElapsed = Math.floor((Date.now() - quizProgress.startedAt) / 1000);
            }
            try {
                localStorage.setItem(`quiz_progress_${quizId}`, JSON.stringify(quizProgress));
            } catch(e) {}
        }
    }
});

window.addEventListener('pagehide', () => {
    if (isStudentMode && quizProgress && !quizProgress.completed && quizProgress.startedAt) {
        const quizId = getCurrentQuizId();
        if (quizId) {
            try {
                localStorage.setItem(`quiz_progress_${quizId}`, JSON.stringify(quizProgress));
            } catch(e) {}
        }
    }
});

/* =========================================================================
   TÍNH NĂNG TRẢI NGHIỆM ĐỀ THI MẪU & ĐIỀU HƯỚNG CÔNG KHAI (CHUẨN GOOGLE ADSENSE)
   ========================================================================= */

function focusLoginForm(tab = 'login') {
    openAuthPage(tab);
}
window.focusLoginForm = focusLoginForm;

function startDemoQuiz() {
    const demoQuiz = {
        title: "Đề thi thử mẫu chuẩn GDPT 2018 - Môn Toán & Khoa học",
        time_limit: 15,
        mode: "practice",
        is_shuffle: false,
        data: [
            {
                question: "Cho hàm số $y = f(x)$ liên tục trên $\\mathbb{R}$ và có đạo hàm $f'(x) = x(x-1)(x+2)^2$. Số điểm cực trị của hàm số đã cho là:",
                options: [
                    "A. 1 điểm",
                    "B. 2 điểm",
                    "C. 3 điểm",
                    "D. 0 điểm"
                ],
                correct_answer: "B. 2 điểm",
                explain: "Ta có: $f'(x) = 0 \\Leftrightarrow x = 0$ hoặc $x = 1$ hoặc $x = -2$. Vì nghiệm $x = -2$ là nghiệm bội chẵn nên đạo hàm không đổi dấu khi đi qua điểm này. Do đó hàm số chỉ đổi dấu qua 2 điểm $x = 0$ và $x = 1$, suy ra hàm số có đúng 2 điểm cực trị.",
                type: "mcq"
            },
            {
                question: "Trong không gian $Oxyz$, cho mặt phẳng $(P): 2x - 3y + z - 5 = 0$. Một vectơ pháp tuyến của mặt phẳng $(P)$ là:",
                options: [
                    "A. $\\vec{n} = (2; -3; 1)$",
                    "B. $\\vec{n} = (2; 3; 1)$",
                    "C. $\\vec{n} = (2; -3; -5)$",
                    "D. $\\vec{n} = (-2; -3; 1)$"
                ],
                correct_answer: "A. $\\vec{n} = (2; -3; 1)$",
                explain: "Phương trình tổng quát mặt phẳng $Ax + By + Cz + D = 0$ có một vectơ pháp tuyến là $\\vec{n} = (A; B; C) = (2; -3; 1)$.",
                type: "mcq"
            },
            {
                question: "Một vật dao động điều hòa theo phương trình $x = 5\\cos(4\\pi t)$ (cm). Tần số dao động của vật là:",
                options: [
                    "A. 2 Hz",
                    "B. 4 Hz",
                    "C. 0,5 Hz",
                    "D. $4\\pi$ Hz"
                ],
                correct_answer: "A. 2 Hz",
                explain: "Tần số góc $\\omega = 4\\pi\\text{ rad/s}$. Tần số dao động: $f = \\frac{\\omega}{2\\pi} = \\frac{4\\pi}{2\\pi} = 2\\text{ Hz}$.",
                type: "mcq"
            },
            {
                question: "Theo định hướng Chương trình GDPT 2018 áp dụng cho kỳ thi tốt nghiệp THPT, cấu trúc đề thi trắc nghiệm bao gồm các dạng thức nào?",
                options: [
                    "A. Trắc nghiệm nhiều lựa chọn, Trắc nghiệm Đúng/Sai và Trắc nghiệm trả lời ngắn.",
                    "B. Chỉ gồm 40 câu hỏi trắc nghiệm 4 lựa chọn A, B, C, D truyền thống.",
                    "C. Chỉ gồm câu hỏi tự luận dài và câu hỏi ghép nối.",
                    "D. Toàn bộ là câu hỏi điền từ vào chỗ trống đơn giản."
                ],
                correct_answer: "A. Trắc nghiệm nhiều lựa chọn, Trắc nghiệm Đúng/Sai và Trắc nghiệm trả lời ngắn.",
                explain: "Cấu trúc đề thi mới gồm 3 dạng thức trắc nghiệm: Phần I (Trắc nghiệm nhiều lựa chọn), Phần II (Trắc nghiệm Đúng/Sai gồm 4 ý), Phần III (Trắc nghiệm trả lời ngắn) giúp đánh giá toàn diện năng lực học sinh.",
                type: "mcq"
            },
            {
                question: "Hệ thống HocNhanhTN hỗ trợ giáo viên chuyển đổi trực tiếp những định dạng tài liệu nào sang đề thi trực tuyến?",
                options: [
                    "A. Tệp tài liệu Word (.docx) và PDF chuẩn GDPT 2018, bảo toàn trọn vẹn công thức LaTeX và hình ảnh.",
                    "B. Chỉ nhận tệp văn bản thô không dấu (.txt).",
                    "C. Bắt buộc nhập liệu thủ công từng câu hỏi.",
                    "D. Chỉ nhận các tệp ảnh chụp màn hình chất lượng thấp."
                ],
                correct_answer: "A. Tệp tài liệu Word (.docx) và PDF chuẩn GDPT 2018, bảo toàn trọn vẹn công thức LaTeX và hình ảnh.",
                explain: "HocNhanhTN tích hợp trí tuệ nhân tạo và bộ bóc tách chuyên sâu, cho phép giáo viên tải trực tiếp tệp Word (.docx) hoặc PDF có sẵn để tạo đề thi hoàn chỉnh trong vài giây.",
                type: "mcq"
            }
        ]
    };

    // 1. Ẩn khối Landing Page & Header công khai
    const pubHeader = document.getElementById('publicHeader');
    if (pubHeader) pubHeader.style.display = 'none';
    const landingHero = document.getElementById('landingHero');
    if (landingHero) landingHero.style.display = 'none';
    const landingStats = document.getElementById('landingStats');
    if (landingStats) landingStats.style.display = 'none';
    const authBox = document.getElementById('authContainer');
    if (authBox) authBox.style.setProperty('display', 'none', 'important');
    const landingExtra = document.getElementById('publicLandingExtras');
    if (landingExtra) landingExtra.style.display = 'none';
    const welcomeScreen = document.getElementById('welcomeScreen');
    if (welcomeScreen) welcomeScreen.style.display = 'none';

    // 2. Kích hoạt giao diện phòng thi tối giản (Student Minimal Mode)
    document.documentElement.classList.add('hntn-not-home-route', 'hntn-is-quiz-route');
    document.body.classList.add('minimal-mode');
    try {
        if (!window.location.search.includes('id=')) {
            history.pushState(null, '', '/?id=demo');
        }
    } catch(e) {}
    const mainApp = document.getElementById('mainAppContainer');
    if (mainApp) mainApp.style.display = 'block';
    const studentHeader = document.getElementById('studentHeader');
    if (studentHeader) studentHeader.style.display = 'block';
    const azotaNav = document.getElementById('azotaNavbar');
    if (azotaNav) azotaNav.style.display = 'none';
    const hub = document.getElementById('creationHub');
    if (hub) hub.style.display = 'none';
    const btnEdit = document.getElementById('btnEdit');
    if (btnEdit) btnEdit.style.display = 'none';

    const titleEl = document.getElementById('studentQuizTitle');
    if (titleEl) titleEl.innerText = demoQuiz.title;
    document.title = `${demoQuiz.title} - HocNhanhTN`;

    studentName = "Thí sinh trải nghiệm";
    updateStudentNameDisplay(studentName);

    // 3. Nạp dữ liệu câu hỏi mẫu
    currentData = JSON.parse(JSON.stringify(demoQuiz.data));
    currentData.forEach((q, i) => { q._originalIndex = i; });
    serverData = JSON.parse(JSON.stringify(currentData));
    currentTimeLimit = demoQuiz.time_limit || 15;
    currentDataMode = 'practice';
    isStudentMode = true;

    // 4. Khởi tạo trạng thái và render giao diện làm bài
    currentQuestionIndex = 0;
    practiceScore = 0;
    practiceAnswered = false;
    resetSubmissionReviewUI();
    switchMode('practice');

    // 5. Kích hoạt MathJax hiển thị công thức Toán chuẩn nét
    if (typeof renderMath === 'function') {
        renderMath(document.getElementById('quiz-container'));
        setTimeout(() => {
            renderMath(document.getElementById('quiz-container'));
        }, 150);
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
    showToast("🎉 Đang mở bài thi mẫu chuẩn GDPT 2018! Bấm chọn đáp án để xem kết quả và lời giải.", "info");
}
window.startDemoQuiz = startDemoQuiz;

// Lắng nghe URL hash để mở chính sách trực tiếp (#privacy, #terms, #about, #contact)
(function initPolicyHashRouting() {
    function handleHash() {
        const h = (window.location.hash || '').replace('#', '').toLowerCase();
        if (['privacy', 'terms', 'about', 'contact'].includes(h)) {
            if (typeof openLegalModal === 'function') openLegalModal(h);
        }
    }
    if (document.readyState === 'loading') {
        window.addEventListener('DOMContentLoaded', handleHash);
    } else {
        handleHash();
    }
    window.addEventListener('hashchange', handleHash);
})();

// ==========================================
// TIỆN ÍCH TRANG CHỦ MỚI: VÀO PHÒNG THI NHANH & CÂU HỎI TƯƠNG TÁC HERO
// ==========================================
function joinQuizByCode() {
    const input = document.getElementById('heroQuizCodeInput');
    if (!input) return;
    const val = input.value.trim();
    if (!val) {
        input.focus();
        if (typeof showToast === 'function') {
            showToast("Vui lòng nhập mã đề thi hoặc dán đường liên kết phòng thi.", "warning");
        } else {
            alert("Vui lòng nhập mã đề thi hoặc dán đường liên kết phòng thi.");
        }
        return;
    }
    let quizId = val;
    try {
        if (val.startsWith('http://') || val.startsWith('https://')) {
            const parsed = new URL(val);
            quizId = parsed.searchParams.get('quiz_id') || parsed.searchParams.get('id') || parsed.pathname.split('/').filter(Boolean).pop() || val;
        } else if (val.includes('/quiz/')) {
            quizId = val.split('/quiz/').pop().split('?')[0].split('#')[0];
        }
    } catch(e) {}
    window.location.href = '/thi/' + encodeURIComponent(quizId);
}
window.joinQuizByCode = joinQuizByCode;

function handleHeroDemoChoice(btn, isCorrect, explanation) {
    const card = document.getElementById('heroInteractiveQuizCard');
    if (!card) return;
    const allOptions = card.querySelectorAll('.hero-quiz-option');
    allOptions.forEach(opt => {
        opt.classList.remove('selected', 'correct', 'incorrect');
        opt.setAttribute('aria-pressed', 'false');
    });
    btn.classList.add('selected');
    btn.setAttribute('aria-pressed', 'true');
    const feedbackBox = document.getElementById('heroQuizFeedback');
    if (isCorrect) {
        btn.classList.add('correct');
        if (feedbackBox) {
            feedbackBox.className = 'hero-quiz-feedback correct';
            feedbackBox.innerHTML = `
                <div class="feedback-badge"><i class="ri-checkbox-circle-fill"></i> Chính xác! Tuyệt vời 🎉</div>
                <div class="feedback-text">${explanation}</div>
                <button type="button" class="btn-hero-launch-full" onclick="startDemoQuiz()">
                    <i class="ri-play-circle-fill"></i> Làm bài thi mẫu đầy đủ (5 câu có chấm điểm) <i class="ri-arrow-right-line"></i>
                </button>
            `;
            feedbackBox.style.display = 'block';
        }
    } else {
        btn.classList.add('incorrect');
        if (feedbackBox) {
            feedbackBox.className = 'hero-quiz-feedback incorrect';
            feedbackBox.innerHTML = `
                <div class="feedback-badge"><i class="ri-close-circle-fill"></i> Chưa chính xác!</div>
                <div class="feedback-text">Gợi ý: Nghiệm $x = -2$ là nghiệm bội chẵn nên đạo hàm $f'(x)$ không đổi dấu khi đi qua điểm này. Hãy thử chọn lại đáp án <b>B</b> xem sao nhé!</div>
            `;
            feedbackBox.style.display = 'block';
        }
    }
    if (window.MathJax && window.MathJax.typesetPromise) {
        window.MathJax.typesetPromise([feedbackBox]).catch(function(){});
    }
}
window.handleHeroDemoChoice = handleHeroDemoChoice;


// Gán nhanh câu lệnh mẫu cho AI rà soát
function setAIQuickPrompt(text) {
    const input = document.getElementById('aiCustomPrompt');
    if (input) {
        input.value = text;
        input.focus();
    }
}


// ========================================================
// NÂNG CẤP UX TOÀN DIỆN (TASK G):
// 1. Phím tắt thông minh cho học sinh (Accessible Keyboard Navigation)
// 2. Bàn phím ký hiệu toán nhanh & Live Math Preview
// 3. Giám sát kết nối mạng Online/Offline tự động
// 4. Skeleton loader tải đề tức thì
// 5. Cuộn nhanh đến câu hỏi trong màn hình xem lại kết quả
// ========================================================


// ========================================================
// BÀN PHÍM RIÊNG CHUYÊN BIỆT CHO CÂU TRẢ LỜI NGẮN (GDPT 2018)
// ========================================================

// 1. So khớp thông minh câu trả lời ngắn chuẩn Bộ GD&ĐT
function evaluateShortAnswerJS(userAns, correctAns) {
    if (userAns === null || userAns === undefined || correctAns === null || correctAns === undefined) return false;
    function clean(s) {
        let t = String(s || '').trim();
        t = t.replace(/<[^>]+>/g, '').replace(/\\\(|\\\)|[\$]/g, '');
        t = t.replace(/[−–—]/g, '-').replace(/[\s\u00a0\u200b]+/g, '');
        t = t.replace(/^(?:x|y|z|t|kếtquả|đápsố|ans|answer|ketqua|dapso)[:=]\s*/i, '');
        return t.toLowerCase();
    }
    const u = clean(userAns);
    const c = clean(correctAns);
    if (!u || !c) return false;
    if (u === c) return true;

    // So sánh số thực (chuẩn hóa dấu phẩy)
    const uNum = parseFloat(u.replace(',', '.'));
    const cNum = parseFloat(c.replace(',', '.'));
    if (!isNaN(uNum) && !isNaN(cNum) && !u.includes('/') && !c.includes('/')) {
        if (Math.abs(uNum - cNum) < 1e-6) return true;
    }

    // So sánh phân số cơ bản
    function parseFrac(str) {
        if (!str.includes('/')) return null;
        const parts = str.split('/');
        if (parts.length === 2) {
            const num = parseFloat(parts[0].replace(',', '.'));
            const den = parseFloat(parts[1].replace(',', '.'));
            if (!isNaN(num) && !isNaN(den) && Math.abs(den) > 1e-9) return num / den;
        }
        return null;
    }
    const uFrac = parseFrac(u);
    const cFrac = parseFrac(c);
    const uVal = uFrac !== null ? uFrac : (!isNaN(uNum) ? uNum : null);
    const cVal = cFrac !== null ? cFrac : (!isNaN(cNum) ? cNum : null);
    if (uVal !== null && cVal !== null && Math.abs(uVal - cVal) < 1e-6) return true;

    return false;
}
window.evaluateShortAnswerJS = evaluateShortAnswerJS;

// 2. Chèn ký tự từ bàn phím riêng vào ô input
function keypadInsertChar(inputId, previewId, char, qIndex) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const start = (input.selectionStart !== undefined) ? input.selectionStart : input.value.length;
    const end = (input.selectionEnd !== undefined) ? input.selectionEnd : input.value.length;
    const oldVal = input.value;
    
    // Kiểm tra tính hợp lệ: Không cho phép nhập 2 dấu chấm liên tiếp
    if (char === '.' && (oldVal.slice(start - 1, start) === '.' || oldVal.slice(start, start + 1) === '.')) {
        return;
    }

    input.value = oldVal.substring(0, start) + char + oldVal.substring(end);
    let newCursorPos = start + char.length;
    if (char.includes('{}')) {
        newCursorPos = start + char.indexOf('{}') + 1;
    }
    input.focus();
    if (input.setSelectionRange) input.setSelectionRange(newCursorPos, newCursorPos);
    
    syncSaInputState(input, qIndex, previewId);
}
window.keypadInsertChar = keypadInsertChar;

// 3. Xóa lùi 1 ký tự (Backspace)
function keypadBackspace(inputId, previewId, qIndex) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const start = (input.selectionStart !== undefined) ? input.selectionStart : input.value.length;
    const end = (input.selectionEnd !== undefined) ? input.selectionEnd : input.value.length;
    const oldVal = input.value;
    
    if (start === end) {
        if (start === 0) return;
        input.value = oldVal.substring(0, start - 1) + oldVal.substring(end);
        input.focus();
        if (input.setSelectionRange) input.setSelectionRange(start - 1, start - 1);
    } else {
        input.value = oldVal.substring(0, start) + oldVal.substring(end);
        input.focus();
        if (input.setSelectionRange) input.setSelectionRange(start, start);
    }
    syncSaInputState(input, qIndex, previewId);
}
window.keypadBackspace = keypadBackspace;

// 4. Xóa sạch toàn bộ (Clear)
function keypadClear(inputId, previewId, qIndex) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.value = '';
    input.focus();
    syncSaInputState(input, qIndex, previewId);
}
window.keypadClear = keypadClear;

// 5. Đảo dấu âm/dương (+/-)
function keypadToggleSign(inputId, previewId, qIndex) {
    const input = document.getElementById(inputId);
    if (!input) return;
    let val = input.value.trim();
    if (!val) {
        input.value = '-';
    } else if (val.startsWith('-')) {
        input.value = val.substring(1);
    } else {
        input.value = '-' + val;
    }
    input.focus();
    const len = input.value.length;
    if (input.setSelectionRange) input.setSelectionRange(len, len);
    syncSaInputState(input, qIndex, previewId);
}
window.keypadToggleSign = keypadToggleSign;

// 6. Chuyển đổi trạng thái Khóa số an toàn
window._saSafeModeMap = window._saSafeModeMap || {};
function keypadToggleSafeMode(inputId, btn) {
    const isCurrentlySafe = window._saSafeModeMap[inputId] !== false;
    window._saSafeModeMap[inputId] = !isCurrentlySafe;
    const isNowSafe = window._saSafeModeMap[inputId];
    if (btn) {
        btn.classList.toggle('active', isNowSafe);
        btn.innerHTML = isNowSafe 
            ? '<i class="ri-lock-2-line"></i> Khóa số: BẬT' 
            : '<i class="ri-lock-unlock-line"></i> Nhập tự do';
        btn.title = isNowSafe 
            ? 'Đang chặn ký tự lạ và chữ cái không mong muốn' 
            : 'Đang cho phép gõ tự do cả chữ cái';
    }
    const warnEl = document.getElementById(`${inputId}_guard_warn`);
    if (warnEl) warnEl.classList.remove('active');
}
window.keypadToggleSafeMode = keypadToggleSafeMode;

// 7. Thu gọn / Mở rộng bàn phím
function keypadToggleCollapse(kpId, btn) {
    const kp = document.getElementById(kpId);
    if (!kp) return;
    const isCollapsed = kp.classList.toggle('collapsed');
    if (btn) {
        btn.innerHTML = isCollapsed 
            ? '<i class="ri-keyboard-line"></i> Hiện bàn phím ▾' 
            : '<i class="ri-keyboard-line"></i> Thu gọn ▴';
    }
}
window.keypadToggleCollapse = keypadToggleCollapse;

// 8. Đồng bộ trạng thái input khi có thay đổi
function syncSaInputState(input, qIndex, previewId) {
    input.dispatchEvent(new Event('input', { bubbles: true }));
    if (qIndex !== undefined && qIndex !== null && typeof selectExamShortAnswer === 'function') {
        selectExamShortAnswer(qIndex, input.value);
    }
    if (previewId && typeof updateMathPreview === 'function') {
        updateMathPreview(input.value, previewId);
    }
}

// 9. Bộ lọc phím cứng (Physical Keyboard Guard)
function handleSaKeydown(e, input, warnId) {
    const inputId = input.id;
    const isSafe = window._saSafeModeMap[inputId] !== false;
    if (!isSafe) return;

    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const allowedKeys = [
        'Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown',
        'Tab', 'Enter', 'Escape', 'Home', 'End'
    ];
    if (allowedKeys.includes(e.key)) return;

    const allowedChars = /^[0-9\.\,\-\s\/\+\*\^\(\)\\\{\}]$/;
    if (allowedChars.test(e.key)) {
        if (e.key === '.' && input.value.slice(-1) === '.') {
            e.preventDefault();
        }
        return;
    }

    e.preventDefault();
    triggerSaGuardWarning(input, warnId);
}
window.handleSaKeydown = handleSaKeydown;

function triggerSaGuardWarning(input, warnId) {
    input.classList.remove('guard-flash');
    void input.offsetWidth;
    input.classList.add('guard-flash');

    const warnEl = document.getElementById(warnId);
    if (warnEl) {
        warnEl.classList.add('active');
        clearTimeout(warnEl._timer);
        warnEl._timer = setTimeout(() => {
            warnEl.classList.remove('active');
        }, 2200);
    }
}

// 10. Xử lý sự kiện input & paste để dọn sạch ký tự lạ
function handleSaInput(e, input, qIndex, previewId) {
    const inputId = input.id;
    const isSafe = window._saSafeModeMap[inputId] !== false;
    let val = input.value;

    if (isSafe && val) {
        val = val.replace(/[−–—]/g, '-');
        val = val.replace(/[^0-9\.\,\-\s\/\+\*\^\(\)\\\{\}\w]/g, '');
        val = val.replace(/\.{2,}/g, '.');
        if (val !== input.value) {
            input.value = val;
        }
    }

    if (qIndex !== undefined && qIndex !== null && typeof selectExamShortAnswer === 'function') {
        selectExamShortAnswer(qIndex, input.value);
    }
    if (previewId && typeof updateMathPreview === 'function') {
        updateMathPreview(input.value, previewId);
    }
}
window.handleSaInput = handleSaInput;

// 11. Render HTML Bàn phím ảo riêng biệt
function renderCustomKeypadHtml(inputId, previewId, qIndex) {
    const kpId = `${inputId}_keypad`;
    return `
        <div class="hntn-keypad-header">
            <span class="hntn-keypad-title">
                <i class="ri-keyboard-box-line" style="color: #2563eb;"></i> Bàn phím số & toán
            </span>
            <div class="hntn-keypad-actions">
                <button type="button" class="hntn-kp-toggle-btn active" id="${inputId}_safebtn" onclick="keypadToggleSafeMode('${inputId}', this)" title="Chế độ an toàn: Chặn nhập nhầm chữ cái và ký tự lạ">
                    <i class="ri-lock-2-line"></i> Khóa số: BẬT
                </button>
                <button type="button" class="hntn-kp-toggle-btn" onclick="keypadToggleCollapse('${kpId}', this)">
                    <i class="ri-keyboard-line"></i> Thu gọn ▴
                </button>
            </div>
        </div>
        <div class="hntn-custom-keypad" id="${kpId}" role="toolbar" aria-label="Bàn phím nhập đáp án ngắn">
            <div class="hntn-kp-math-row">
                <button type="button" class="hntn-kp-math-btn" onclick="keypadInsertChar('${inputId}', '${previewId}', '/', ${qIndex})" title="Phân số (a/b)">a/b</button>
                <button type="button" class="hntn-kp-math-btn" onclick="keypadInsertChar('${inputId}', '${previewId}', '\\\\sqrt{}', ${qIndex})" title="Căn bậc hai">√x</button>
                <button type="button" class="hntn-kp-math-btn" onclick="keypadInsertChar('${inputId}', '${previewId}', '^2', ${qIndex})" title="Bình phương">x²</button>
                <button type="button" class="hntn-kp-math-btn" onclick="keypadInsertChar('${inputId}', '${previewId}', '\\\\pi', ${qIndex})" title="Số Pi">π</button>
                <button type="button" class="hntn-kp-math-btn" onclick="keypadInsertChar('${inputId}', '${previewId}', '(', ${qIndex})" title="Mở ngoặc">(</button>
                <button type="button" class="hntn-kp-math-btn" onclick="keypadInsertChar('${inputId}', '${previewId}', ')', ${qIndex})" title="Đóng ngoặc">)</button>
            </div>
            <div class="hntn-kp-numpad">
                <button type="button" class="hntn-kp-key key-num" onclick="keypadInsertChar('${inputId}', '${previewId}', '7', ${qIndex})">7</button>
                <button type="button" class="hntn-kp-key key-num" onclick="keypadInsertChar('${inputId}', '${previewId}', '8', ${qIndex})">8</button>
                <button type="button" class="hntn-kp-key key-num" onclick="keypadInsertChar('${inputId}', '${previewId}', '9', ${qIndex})">9</button>
                <button type="button" class="hntn-kp-key key-backspace" onclick="keypadBackspace('${inputId}', '${previewId}', ${qIndex})" title="Xóa 1 ký tự">⌫</button>

                <button type="button" class="hntn-kp-key key-num" onclick="keypadInsertChar('${inputId}', '${previewId}', '4', ${qIndex})">4</button>
                <button type="button" class="hntn-kp-key key-num" onclick="keypadInsertChar('${inputId}', '${previewId}', '5', ${qIndex})">5</button>
                <button type="button" class="hntn-kp-key key-num" onclick="keypadInsertChar('${inputId}', '${previewId}', '6', ${qIndex})">6</button>
                <button type="button" class="hntn-kp-key key-clear" onclick="keypadClear('${inputId}', '${previewId}', ${qIndex})" title="Xóa toàn bộ">C</button>

                <button type="button" class="hntn-kp-key key-num" onclick="keypadInsertChar('${inputId}', '${previewId}', '1', ${qIndex})">1</button>
                <button type="button" class="hntn-kp-key key-num" onclick="keypadInsertChar('${inputId}', '${previewId}', '2', ${qIndex})">2</button>
                <button type="button" class="hntn-kp-key key-num" onclick="keypadInsertChar('${inputId}', '${previewId}', '3', ${qIndex})">3</button>
                <button type="button" class="hntn-kp-key key-sign" onclick="keypadToggleSign('${inputId}', '${previewId}', ${qIndex})" title="Đảo dấu âm / dương">±</button>

                <button type="button" class="hntn-kp-key key-num" onclick="keypadInsertChar('${inputId}', '${previewId}', '0', ${qIndex})">0</button>
                <button type="button" class="hntn-kp-key key-op" onclick="keypadInsertChar('${inputId}', '${previewId}', '.', ${qIndex})" title="Dấu thập phân">.</button>
                <button type="button" class="hntn-kp-key key-op" onclick="keypadInsertChar('${inputId}', '${previewId}', ',', ${qIndex})" title="Dấu phẩy">,</button>
                <button type="button" class="hntn-kp-key key-op" onclick="keypadInsertChar('${inputId}', '${previewId}', '-', ${qIndex})" title="Dấu trừ">-</button>
            </div>
        </div>
    `;
}
window.renderCustomKeypadHtml = renderCustomKeypadHtml;

function renderMathToolbarHtml(inputId, previewId) {
    const symbols = [
        { label: '√x', insert: '\\sqrt{}' },
        { label: 'a/b', insert: '\\frac{}{}' },
        { label: 'x²', insert: '^2' },
        { label: 'xⁿ', insert: '^{}' },
        { label: 'π', insert: '\\pi' },
        { label: '±', insert: '\\pm' },
        { label: '≤', insert: '\\le' },
        { label: '≥', insert: '\\ge' },
        { label: '≠', insert: '\\ne' },
        { label: '×', insert: '\\times' },
        { label: '÷', insert: '\\div' },
        { label: '°', insert: '^\\circ' },
        { label: 'Δ', insert: '\\Delta' },
        { label: 'α', insert: '\\alpha' },
        { label: 'β', insert: '\\beta' },
        { label: '∞', insert: '\\infty' }
    ];
    let btns = symbols.map(s => 
        `<button type="button" class="azota-math-btn" onclick="insertMathSymbol('${inputId}', '${previewId}', '${s.insert}')" title="Chèn ký hiệu ${s.label}">${s.label}</button>`
    ).join('');
    return `<div class="azota-math-toolbar">${btns}</div>`;
}
window.renderMathToolbarHtml = renderMathToolbarHtml;

function insertMathSymbol(inputElemId, previewId, symbol) {
    const input = document.getElementById(inputElemId);
    if (!input) return;
    const start = (input.selectionStart !== undefined) ? input.selectionStart : input.value.length;
    const end = (input.selectionEnd !== undefined) ? input.selectionEnd : input.value.length;
    const oldVal = input.value;
    input.value = oldVal.substring(0, start) + symbol + oldVal.substring(end);
    
    // Đặt con trỏ thông minh (nếu chèn cặp ngoặc {} thì trỏ vào giữa)
    let newCursorPos = start + symbol.length;
    if (symbol.includes('{}')) {
        newCursorPos = start + symbol.indexOf('{}') + 1;
    }
    input.focus();
    if (input.setSelectionRange) input.setSelectionRange(newCursorPos, newCursorPos);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    updateMathPreview(input.value, previewId);
}
window.insertMathSymbol = insertMathSymbol;

function updateMathPreview(val, previewId) {
    const previewBox = document.getElementById(previewId);
    if (!previewBox) return;
    const trimmed = String(val || '').trim();
    if (!trimmed) {
        previewBox.classList.remove('active');
        previewBox.style.display = 'none';
        return;
    }
    previewBox.classList.add('active');
    previewBox.style.display = 'flex';
    const renderTarget = previewBox.querySelector('.preview-render');
    if (renderTarget) {
        renderTarget.innerHTML = `$${trimmed}$`;
        if (window.MathJax && MathJax.typesetPromise) {
            MathJax.typesetPromise([renderTarget]).catch(() => {});
        }
    }
}
window.updateMathPreview = updateMathPreview;

function initOfflineDetection() {
    function updateOnlineStatus(isOnline) {
        let banner = document.getElementById('hntnOfflineBanner');
        if (!banner) return;
        if (!isOnline) {
            banner.classList.remove('online-recovered');
            banner.innerHTML = `<i class="ri-wifi-off-line"></i> <span>Mất kết nối Internet - Đã kích hoạt chế độ Offline. Mọi câu trả lời của bạn vẫn được lưu an toàn trên máy!</span>`;
            banner.style.display = 'flex';
        } else {
            banner.classList.add('online-recovered');
            banner.innerHTML = `<i class="ri-wifi-line"></i> <span>Đã kết nối lại Internet - Tiếp tục đồng bộ bài làm an toàn!</span>`;
            banner.style.display = 'flex';
            setTimeout(() => {
                if (banner && banner.classList.contains('online-recovered')) {
                    banner.style.display = 'none';
                }
            }, 3500);
        }
    }

    window.addEventListener('offline', () => updateOnlineStatus(false));
    window.addEventListener('online', () => updateOnlineStatus(true));
}
window.initOfflineDetection = initOfflineDetection;

function initKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
        if (tag === 'input' || tag === 'textarea' || (e.target && e.target.isContentEditable)) return;
        if (typeof currentMode !== 'undefined' && currentMode === 'edit') return;
        
        const quizContainer = document.getElementById('quiz-container');
        if (!quizContainer || quizContainer.style.display === 'none') return;

        const key = e.key.toUpperCase();

        const optKeys = { '1': 0, '2': 1, '3': 2, '4': 3, 'A': 0, 'B': 1, 'C': 2, 'D': 3 };
        if (key in optKeys) {
            const optIndex = optKeys[key];
            handleKeyboardSelectOption(optIndex);
        } else if (key === 'F') {
            handleKeyboardToggleFlag();
        } else if (key === 'ARROWDOWN' || key === 'J' || key === 'N') {
            handleKeyboardNavQuestion(1);
        } else if (key === 'ARROWUP' || key === 'K' || key === 'P') {
            handleKeyboardNavQuestion(-1);
        }
    });
}
window.initKeyboardShortcuts = initKeyboardShortcuts;

function getFocusedQuestionIndex() {
    if (typeof currentMode !== 'undefined' && currentMode === 'practice') {
        return typeof currentQuestionIndex !== 'undefined' ? currentQuestionIndex : 0;
    }
    const qCards = document.querySelectorAll('.azota-question-card');
    if (!qCards.length) return 0;
    const headerHeight = 90;
    for (let i = 0; i < qCards.length; i++) {
        const rect = qCards[i].getBoundingClientRect();
        if (rect.bottom > headerHeight + 60 && rect.top < window.innerHeight * 0.6) {
            return i;
        }
    }
    return 0;
}

function handleKeyboardSelectOption(optIndex) {
    const qIndex = getFocusedQuestionIndex();
    if (!currentData || !currentData[qIndex]) return;
    const q = currentData[qIndex];
    const qType = typeof getRealQuestionType === 'function' ? getRealQuestionType(q) : 'mcq';
    
    if (typeof currentMode !== 'undefined' && currentMode === 'practice') {
        if (qType === 'mcq' && typeof checkPracticeAnswer === 'function') {
            checkPracticeAnswer(optIndex);
        }
    } else {
        if (qType === 'mcq' && typeof selectExamOption === 'function') {
            selectExamOption(qIndex, optIndex);
            const lbl = document.getElementById(`exam_opt_${qIndex}_${optIndex}`);
            if (lbl) {
                lbl.classList.add('selected');
                lbl.focus();
            }
        }
    }
}

function handleKeyboardToggleFlag() {
    const qIndex = getFocusedQuestionIndex();
    if (typeof toggleFlagQuestion === 'function') {
        toggleFlagQuestion(qIndex);
        const isFlag = !!flaggedQuestions[qIndex];
        if (typeof showToast === 'function') {
            showToast(isFlag ? `🚩 Đã đánh dấu phân vân Câu ${qIndex + 1}` : `Đã bỏ đánh dấu Câu ${qIndex + 1}`, "info");
        }
    }
}

function handleKeyboardNavQuestion(direction) {
    if (typeof currentMode !== 'undefined' && currentMode === 'practice') {
        if (direction > 0 && typeof nextPracticeQuestion === 'function') nextPracticeQuestion();
        else if (direction < 0 && typeof prevPracticeQuestion === 'function') prevPracticeQuestion();
    } else {
        const curr = getFocusedQuestionIndex();
        const next = Math.max(0, Math.min(currentData.length - 1, curr + direction));
        if (typeof scrollToQuestion === 'function') scrollToQuestion(next);
    }
}

function renderQuizSkeleton() {
    const container = document.getElementById('quiz-container');
    if (!container) return;
    let html = '';
    for (let i = 0; i < 3; i++) {
        html += `
            <div class="hntn-skeleton-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <div class="hntn-shimmer" style="width: 130px; height: 28px;"></div>
                    <div class="hntn-shimmer" style="width: 110px; height: 28px;"></div>
                </div>
                <div class="hntn-shimmer" style="width: 92%; height: 20px; margin-bottom: 10px;"></div>
                <div class="hntn-shimmer" style="width: 65%; height: 20px; margin-bottom: 22px;"></div>
                <div style="display: flex; flex-direction: column; gap: 10px;">
                    <div class="hntn-shimmer" style="width: 100%; height: 48px; border-radius: 8px;"></div>
                    <div class="hntn-shimmer" style="width: 100%; height: 48px; border-radius: 8px;"></div>
                    <div class="hntn-shimmer" style="width: 100%; height: 48px; border-radius: 8px;"></div>
                    <div class="hntn-shimmer" style="width: 100%; height: 48px; border-radius: 8px;"></div>
                </div>
            </div>
        `;
    }
    container.innerHTML = html;
}
window.renderQuizSkeleton = renderQuizSkeleton;

function scrollToReviewQuestion(qIndex) {
    if (typeof switchResultView === 'function') {
        switchResultView('review', false);
    }

    const card = document.getElementById(`review_q_${qIndex}`);
    if (card && card.style.display === 'none') {
        if (typeof filterReviewQuestions === 'function') {
            filterReviewQuestions('all');
        } else {
            card.style.display = 'block';
        }
    }

    setTimeout(() => {
        const targetCard = document.getElementById(`review_q_${qIndex}`);
        if (!targetCard) return;

        targetCard.style.display = 'block';
        const header = document.getElementById('studentHeader');
        const hOffset = (header && header.style.display !== 'none') ? header.offsetHeight : 70;
        const rect = targetCard.getBoundingClientRect();
        const scrollY = window.pageYOffset !== undefined ? window.pageYOffset : (document.documentElement || document.body.parentNode || document.body).scrollTop;
        const targetTop = rect.top + scrollY - hOffset - 15;

        window.scrollTo({ top: Math.max(0, targetTop), behavior: 'smooth' });

        targetCard.style.transition = 'box-shadow 0.3s ease, border-color 0.3s ease, transform 0.2s ease';
        targetCard.style.boxShadow = '0 0 0 3px #3b82f6, 0 10px 25px -5px rgba(59, 130, 246, 0.25)';
        targetCard.style.borderColor = '#3b82f6';
        targetCard.style.transform = 'translateY(-2px)';
        setTimeout(() => {
            targetCard.style.boxShadow = '';
            targetCard.style.borderColor = '';
            targetCard.style.transform = '';
        }, 1800);
    }, 50);
}
window.scrollToReviewQuestion = scrollToReviewQuestion;

// ----------------------------------------------------
// TÍNH NĂNG AI THÔNG MINH: GỢI Ý ĐÁP ÁN, KIỂM TRA CHÉO & SINH CÂU TƯƠNG TỰ
// ----------------------------------------------------

function syncDataToEditorSafe() {
    if (typeof syncDataToEditor === 'function') {
        syncDataToEditor();
    } else {
        const codeEditor = document.getElementById('codeEditor');
        if (codeEditor) {
            if (typeof dataToEditorText === 'function') {
                if (codeEditor.tagName === 'TEXTAREA' || codeEditor.value !== undefined) {
                    codeEditor.value = dataToEditorText(currentData);
                } else {
                    codeEditor.innerHTML = dataToEditorText(currentData);
                }
            }
            if (typeof updateSyntaxHighlight === 'function') updateSyntaxHighlight();
        }
    }
}

window.confirmAISuggestedAnswer = function(qIndex, event) {
    if (event) event.stopPropagation();
    if (!currentData[qIndex]) return;
    delete currentData[qIndex].is_ai_suggested;
    delete currentData[qIndex].ai_suggestion_note;
    syncDataToEditorSafe();
    renderPreviewAll();
    if (typeof saveDraftToSession === 'function') saveDraftToSession();
    showToast("Đã xác nhận đáp án do AI đề xuất!");
};

window.runCrossCheckAI = async function() {
    const btn = document.getElementById('btnCrossCheckAI');
    if (!currentData || currentData.length === 0) {
        alert("Chưa có câu hỏi nào trong đề để kiểm tra chéo!");
        return;
    }
    const origHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="ri-loader-4-line ri-spin"></i> Đang đối chiếu...';
    }
    if (typeof showStudioLoader === 'function') {
        showStudioLoader({
            title: "⚖️ AI đang giải độc lập & kiểm tra chéo đáp án...",
            subtitle: "AI độc lập giải lại từng câu hỏi không nhìn trước đáp án gốc để tìm kiếm sai sót (10-30s)..."
        });
    }
    try {
        const res = await fetch(`${API_BASE_URL}/api/teacher/cross_check_answers`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                teacher_token: authToken,
                quiz_data: currentData
            })
        });
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            currentData = data.quiz_data || currentData;
            const mismatches = data.mismatches_found || 0;
            syncDataToEditorSafe();
            renderPreviewAll();
            if (typeof saveDraftToSession === 'function') saveDraftToSession();
            if (mismatches > 0) {
                alert(`⚠️ Phát hiện ${mismatches} câu hỏi có đáp án AI giải KHÁC với đáp án ban đầu! Vui lòng rà soát các thẻ cảnh báo màu cam.`);
            } else {
                showToast("Tuyệt vời! 100% đáp án khớp với kết quả AI giải độc lập.");
            }
        } else {
            alert("Lỗi kiểm tra chéo: " + (data.detail || "Không thể thực hiện kiểm tra chéo"));
        }
    } catch(err) {
        console.error("Cross-check error:", err);
        alert("Lỗi mạng khi kiểm tra chéo đáp án.");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = origHtml || '<i class="ri-scales-3-line"></i> Kiểm tra chéo đáp án';
        }
        if (typeof hideStudioLoader === 'function') hideStudioLoader();
    }
};
window.crossCheckQuizAnswers = window.runCrossCheckAI;

window.acceptAICrossCheckAnswer = function(qIndex) {
    if (!currentData[qIndex] || !currentData[qIndex].cross_check_info) return;
    const info = currentData[qIndex].cross_check_info;
    const aiAns = info.ai_answer;
    if (aiAns !== undefined && aiAns !== null) {
        const qType = getRealQuestionType(currentData[qIndex]);
        if (qType === 'mcq' && Array.isArray(currentData[qIndex].options)) {
            let foundOpt = currentData[qIndex].options.find(opt => {
                let optLetter = (opt.trim().match(/^[A-F]/i) || [])[0];
                return opt === aiAns || (optLetter && optLetter.toUpperCase() === String(aiAns).trim().toUpperCase());
            });
            currentData[qIndex].correct_answer = foundOpt || aiAns;
        } else {
            currentData[qIndex].correct_answer = aiAns;
        }
        if (info.ai_explain && (!currentData[qIndex].explain || currentData[qIndex].explain.trim().length === 0)) {
            currentData[qIndex].explain = info.ai_explain;
        }
    }
    delete currentData[qIndex].has_cross_check_warning;
    delete currentData[qIndex].cross_check_info;
    syncDataToEditorSafe();
    renderPreviewAll();
    if (typeof saveDraftToSession === 'function') saveDraftToSession();
    showToast("Đã cập nhật sang đáp án do AI giải!");
};

window.dismissAICrossCheck = function(qIndex) {
    if (!currentData[qIndex]) return;
    delete currentData[qIndex].has_cross_check_warning;
    delete currentData[qIndex].cross_check_info;
    renderPreviewAll();
    if (typeof saveDraftToSession === 'function') saveDraftToSession();
    showToast("Đã giữ lại đáp án của Giáo viên.");
};

let activeSimilarBaseIndex = null;
let activeGeneratedSimilarQuestions = [];

window.openSimilarModal = function(qIndex) {
    if (!currentData[qIndex]) return;
    activeSimilarBaseIndex = qIndex;
    activeGeneratedSimilarQuestions = [];
    
    const modal = document.getElementById('similarQuestionModal');
    const preview = document.getElementById('similarBaseQPreview');
    const resContainer = document.getElementById('simResultsContainer');
    const addBtn = document.getElementById('btnAddSimilarToQuiz');
    const runBtn = document.getElementById('btnRunGenerateSimilar');

    const baseQ = currentData[qIndex];
    let qClean = (baseQ.question || '').replace(/^(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])\s*/i, '');
    let optsHtml = '';
    if (Array.isArray(baseQ.options)) {
        optsHtml = `<div style="margin-top: 6px; display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-size: 0.85rem; color: #475569;">
            ${baseQ.options.map(o => `<div>• ${escapeHtml(o)}</div>`).join('')}
        </div>`;
    }
    let ansHtml = baseQ.correct_answer ? `<div style="margin-top: 6px; font-size: 0.85rem; font-weight: 600; color: #16a34a;">Đáp án: ${escapeHtml(typeof baseQ.correct_answer === 'object' ? JSON.stringify(baseQ.correct_answer) : String(baseQ.correct_answer))}</div>` : '';

    if (preview) {
        preview.innerHTML = `
            <div style="font-weight: 700; color: #1e293b; margin-bottom: 4px;">Câu gốc (Câu ${qIndex + 1}):</div>
            <div style="color: #334155; line-height: 1.4;">${escapeHtml(qClean)}</div>
            ${optsHtml}
            ${ansHtml}
        `;
    }

    if (resContainer) resContainer.style.display = 'none';
    if (addBtn) addBtn.style.display = 'none';
    if (runBtn) {
        runBtn.disabled = false;
        runBtn.innerHTML = '<i class="ri-sparkling-fill"></i> Tạo ngay với AI';
    }

    if (modal) {
        modal.style.display = 'flex';
        if (window.MathJax && typeof window.MathJax.typesetPromise === 'function') {
            window.MathJax.typesetPromise([preview]).catch(() => {});
        }
    }
};

window.closeSimilarModal = function() {
    const modal = document.getElementById('similarQuestionModal');
    if (modal) modal.style.display = 'none';
};

window.submitGenerateSimilar = async function() {
    if (activeSimilarBaseIndex === null || !currentData[activeSimilarBaseIndex]) {
        alert("Không tìm thấy câu hỏi gốc để sinh tương tự.");
        return;
    }
    const modeRadio = document.querySelector('input[name="simMode"]:checked');
    const mode = modeRadio ? modeRadio.value : 'change_numbers';
    const count = parseInt(document.getElementById('simCountSelect')?.value || '3', 10);
    const difficulty = document.getElementById('simDifficultySelect')?.value || 'keep';

    const runBtn = document.getElementById('btnRunGenerateSimilar');
    const resContainer = document.getElementById('simResultsContainer');
    const genList = document.getElementById('simGeneratedList');
    const addBtn = document.getElementById('btnAddSimilarToQuiz');

    if (runBtn) {
        runBtn.disabled = true;
        runBtn.innerHTML = '<i class="ri-loader-4-line ri-spin"></i> Đang sinh câu hỏi...';
    }

    try {
        const payload = {
            teacher_token: authToken || '',
            base_question: currentData[activeSimilarBaseIndex],
            question: currentData[activeSimilarBaseIndex],
            count: count,
            mode: mode,
            difficulty: difficulty
        };
        const res = await fetch(`${API_BASE_URL}/api/teacher/generate_similar_questions`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        const similarList = (Array.isArray(data.similar_questions) && data.similar_questions) || (Array.isArray(data.data) && data.data);
        if (res.ok && data.status === 'success' && similarList) {
            activeGeneratedSimilarQuestions = similarList;
            if (genList) {
                genList.innerHTML = '';
                activeGeneratedSimilarQuestions.forEach((sq, idx) => {
                    let sqCard = document.createElement('div');
                    sqCard.style.cssText = 'padding: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 0.9rem;';
                    let opts = Array.isArray(sq.options) ? sq.options.map(o => `<div style="padding: 2px 0;">• ${escapeHtml(o)}</div>`).join('') : '';
                    let ans = sq.correct_answer ? `<div style="margin-top: 6px; font-weight: 700; color: #16a34a;">Đáp án: ${escapeHtml(typeof sq.correct_answer === 'object' ? JSON.stringify(sq.correct_answer) : String(sq.correct_answer))}</div>` : '';
                    let exp = sq.explain ? `<div style="margin-top: 4px; font-size: 0.85rem; color: #64748b;"><b>Lời giải:</b> ${escapeHtml(sq.explain)}</div>` : '';
                    
                    sqCard.innerHTML = `
                        <div style="font-weight: 700; color: #7c3aed; margin-bottom: 4px;">Câu tương tự #${idx + 1}:</div>
                        <div style="color: #1e293b; margin-bottom: 6px;">${escapeHtml(sq.question || '')}</div>
                        ${opts ? `<div style="margin-left: 8px; color: #475569;">${opts}</div>` : ''}
                        ${ans}
                        ${exp}
                    `;
                    genList.appendChild(sqCard);
                });
                if (window.MathJax && typeof window.MathJax.typesetPromise === 'function') {
                    window.MathJax.typesetPromise([genList]).catch(() => {});
                }
            }
            if (resContainer) resContainer.style.display = 'block';
            if (addBtn) addBtn.style.display = 'inline-flex';
            showToast(`Đã sinh xong ${activeGeneratedSimilarQuestions.length} câu hỏi tương tự!`);
        } else {
            let errMsg = data.detail || data.message || "Không nhận được phản hồi";
            if (typeof errMsg === 'object') {
                try {
                    errMsg = Array.isArray(errMsg) ? errMsg.map(e => e.msg || JSON.stringify(e)).join(', ') : JSON.stringify(errMsg);
                } catch(e) {}
            }
            alert("Lỗi khi sinh câu hỏi tương tự: " + errMsg);
        }
    } catch(err) {
        console.error("Generate similar error:", err);
        alert("Lỗi kết nối khi sinh câu hỏi tương tự.");
    } finally {
        if (runBtn) {
            runBtn.disabled = false;
            runBtn.innerHTML = '<i class="ri-sparkling-fill"></i> Tạo lại';
        }
    }
};

window.applySimilarQuestionsToQuiz = function() {
    if (!activeGeneratedSimilarQuestions || activeGeneratedSimilarQuestions.length === 0) {
        alert("Chưa có câu hỏi tương tự nào được sinh.");
        return;
    }
    let insertIndex = activeSimilarBaseIndex !== null ? activeSimilarBaseIndex + 1 : currentData.length;
    currentData.splice(insertIndex, 0, ...activeGeneratedSimilarQuestions);
    
    syncDataToEditorSafe();
    renderPreviewAll();
    if (typeof updateQCountBadge === 'function') updateQCountBadge();
    if (typeof saveDraftToSession === 'function') saveDraftToSession();
    closeSimilarModal();
    showToast(`Đã thêm ${activeGeneratedSimilarQuestions.length} câu hỏi mới vào đề thi!`);
};


// ========================================================
// HỆ THỐNG BẢO MẬT & CHỐNG GIAN LẬN THI THỬ (EXAM ANTI-CHEAT)
// CHỈ ÁP DỤNG DUY NHẤT TRONG CHẾ ĐỘ THI THỬ (EXAM MODE)
// KHÔNG ÁP DỤNG TRONG CHẾ ĐỘ LUYỆN TẬP HOẶC BIÊN SOẠN
// ========================================================
window.currentExamSessionId = null;
window.examTabSwitchCount = 0;
window.examAwayTimeTotal = 0;
window.examClientInstanceId = null;
window.examBroadcastChannel = null;
window.examAntiCheatActive = false;
window._examLeaveTimestamp = null;
window._examListeners = {};
window._examSessionHeartbeat = null;

function initExamAntiCheat() {
    // CHỈ áp dụng trong chế độ Thi thử (exam) và khi đang ở giao diện phòng thi (minimal-mode)
    if (currentMode !== 'exam' || !document.body.classList.contains('minimal-mode') || document.body.classList.contains('quiz-completed')) {
        destroyExamAntiCheat();
        return;
    }

    if (window.examAntiCheatActive) return;
    window.examAntiCheatActive = true;
    document.body.classList.add('exam-mode');

    window.examTabSwitchCount = (quizProgress && quizProgress.tabSwitchCount) || 0;
    window._examLeaveTimestamp = null;

    // 1. Chặn menu ngữ cảnh (chuột phải)
    const onContextMenu = (e) => {
        if (!window.examAntiCheatActive || currentMode !== 'exam' || document.body.classList.contains('quiz-completed')) return;
        e.preventDefault();
        showToast("⚠️ Chế độ thi thử: Không cho phép mở menu chuột phải!", "warning");
        return false;
    };

    // 2. Chặn sao chép (copy/cut)
    const onCopyCut = (e) => {
        if (!window.examAntiCheatActive || currentMode !== 'exam' || document.body.classList.contains('quiz-completed')) return;
        const target = e.target;
        if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
            return;
        }
        e.preventDefault();
        showToast("⚠️ Chế độ thi thử: Không cho phép sao chép nội dung câu hỏi!", "warning");
        return false;
    };

    // 3. Chặn dán vào các vùng ngoài ô trả lời tự luận
    const onPaste = (e) => {
        if (!window.examAntiCheatActive || currentMode !== 'exam' || document.body.classList.contains('quiz-completed')) return;
        const target = e.target;
        if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
            return;
        }
        e.preventDefault();
        return false;
    };

    // 4. Chặn bôi đen câu hỏi trong đề thi
    const onSelectStart = (e) => {
        if (!window.examAntiCheatActive || currentMode !== 'exam' || document.body.classList.contains('quiz-completed')) return;
        const target = e.target;
        if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
            return;
        }
        e.preventDefault();
        return false;
    };

    // 5. Chặn F12, DevTools và các tổ hợp phím tắt (Ctrl+Shift+I/J/C, Ctrl+U, Ctrl+S, Ctrl+P)
    const onKeyDown = (e) => {
        if (!window.examAntiCheatActive || currentMode !== 'exam' || document.body.classList.contains('quiz-completed')) return;
        const key = e.key || '';
        const keyCode = e.keyCode || e.which;
        const ctrlOrCmd = e.ctrlKey || e.metaKey;

        // F12
        if (key === 'F12' || keyCode === 123) {
            e.preventDefault();
            e.stopPropagation();
            showToast("⚠️ Chế độ thi thử: Phím F12 bị vô hiệu hóa!", "warning");
            return false;
        }

        // Ctrl+Shift+I / J / C (DevTools)
        if (ctrlOrCmd && e.shiftKey && ['I', 'i', 'J', 'j', 'C', 'c'].includes(key)) {
            e.preventDefault();
            e.stopPropagation();
            showToast("⚠️ Chế độ thi thử: Không cho phép mở công cụ nhà phát triển!", "warning");
            return false;
        }

        // Ctrl+U (Xem mã nguồn trang)
        if (ctrlOrCmd && (key === 'u' || key === 'U')) {
            e.preventDefault();
            e.stopPropagation();
            showToast("⚠️ Chế độ thi thử: Không cho phép xem mã nguồn trang!", "warning");
            return false;
        }

        // Ctrl+S (Lưu trang) / Ctrl+P (In trang)
        if (ctrlOrCmd && ['s', 'S', 'p', 'P'].includes(key)) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }
    };

    // 6. Phát hiện chuyển tab hoặc rời cửa sổ (visibilitychange & blur/focus)
    const onVisibilityChange = () => {
        if (!window.examAntiCheatActive || currentMode !== 'exam' || document.body.classList.contains('quiz-completed')) return;
        if (document.visibilityState === 'hidden') {
            window._examLeaveTimestamp = Date.now();
        } else if (document.visibilityState === 'visible') {
            if (window._examLeaveTimestamp) {
                const awayDurationMs = Date.now() - window._examLeaveTimestamp;
                window._examLeaveTimestamp = null;
                if (awayDurationMs >= 800) {
                    const awaySeconds = Math.max(1, Math.round(awayDurationMs / 1000));
                    window.examAwayTimeTotal = (window.examAwayTimeTotal || 0) + awaySeconds;
                    handleExamViolation('tab_switch', `Bạn vừa rời tab thi trong ${awaySeconds} giây!`);
                }
            }
        }
    };

    const onWindowBlur = () => {
        if (!window.examAntiCheatActive || currentMode !== 'exam' || document.body.classList.contains('quiz-completed')) return;
        if (!window._examLeaveTimestamp) {
            window._examLeaveTimestamp = Date.now();
        }
    };

    const onWindowFocus = () => {
        if (!window.examAntiCheatActive || currentMode !== 'exam' || document.body.classList.contains('quiz-completed')) return;
        if (window._examLeaveTimestamp) {
            const awayDurationMs = Date.now() - window._examLeaveTimestamp;
            window._examLeaveTimestamp = null;
            if (awayDurationMs >= 800) {
                const awaySeconds = Math.max(1, Math.round(awayDurationMs / 1000));
                window.examAwayTimeTotal = (window.examAwayTimeTotal || 0) + awaySeconds;
                handleExamViolation('window_blur', `Bạn vừa chuyển cửa sổ hoặc rời màn hình làm bài trong ${awaySeconds} giây!`);
            }
        }
    };

    // 7. Giám sát toàn màn hình (fullscreenchange)
    const onFullscreenChange = () => {
        if (!window.examAntiCheatActive || currentMode !== 'exam' || document.body.classList.contains('quiz-completed')) return;
        if (!document.fullscreenElement) {
            handleExamViolation('fullscreen_exit', 'Bạn vừa thoát khỏi chế độ toàn màn hình bài thi!');
        }
    };

    window._examListeners = {
        contextmenu: onContextMenu,
        copy: onCopyCut,
        cut: onCopyCut,
        paste: onPaste,
        selectstart: onSelectStart,
        keydown: onKeyDown,
        visibilitychange: onVisibilityChange,
        blur: onWindowBlur,
        focus: onWindowFocus,
        fullscreenchange: onFullscreenChange,
        webkitfullscreenchange: onFullscreenChange
    };

    document.addEventListener('contextmenu', onContextMenu, true);
    document.addEventListener('copy', onCopyCut, true);
    document.addEventListener('cut', onCopyCut, true);
    document.addEventListener('paste', onPaste, true);
    document.addEventListener('selectstart', onSelectStart, true);
    window.addEventListener('keydown', onKeyDown, true);
    document.addEventListener('visibilitychange', onVisibilityChange);
    window.addEventListener('blur', onWindowBlur);
    window.addEventListener('focus', onWindowFocus);
    document.addEventListener('fullscreenchange', onFullscreenChange);
    document.addEventListener('webkitfullscreenchange', onFullscreenChange);
}

function destroyExamAntiCheat() {
    window.examAntiCheatActive = false;
    document.body.classList.remove('exam-mode');

    if (window._examListeners) {
        if (window._examListeners.contextmenu) document.removeEventListener('contextmenu', window._examListeners.contextmenu, true);
        if (window._examListeners.copy) document.removeEventListener('copy', window._examListeners.copy, true);
        if (window._examListeners.cut) document.removeEventListener('cut', window._examListeners.cut, true);
        if (window._examListeners.paste) document.removeEventListener('paste', window._examListeners.paste, true);
        if (window._examListeners.selectstart) document.removeEventListener('selectstart', window._examListeners.selectstart, true);
        if (window._examListeners.keydown) window.removeEventListener('keydown', window._examListeners.keydown, true);
        if (window._examListeners.visibilitychange) document.removeEventListener('visibilitychange', window._examListeners.visibilitychange);
        if (window._examListeners.blur) window.removeEventListener('blur', window._examListeners.blur);
        if (window._examListeners.focus) window.removeEventListener('focus', window._examListeners.focus);
        if (window._examListeners.fullscreenchange) document.removeEventListener('fullscreenchange', window._examListeners.fullscreenchange);
        if (window._examListeners.webkitfullscreenchange) document.removeEventListener('webkitfullscreenchange', window._examListeners.webkitfullscreenchange);
        window._examListeners = {};
    }

    closeExamViolationModal();
}

function handleExamViolation(reason, msg) {
    if (!window.examAntiCheatActive || currentMode !== 'exam' || document.body.classList.contains('quiz-completed')) return;

    window.examTabSwitchCount = (window.examTabSwitchCount || 0) + 1;
    if (quizProgress) {
        quizProgress.tabSwitchCount = window.examTabSwitchCount;
        saveProgressToLocal();
    }

    const count = window.examTabSwitchCount;
    const maxViolations = 3;

    if (count >= maxViolations) {
        closeExamViolationModal();
        alert(`🚨 VI PHẠM QUY CHẾ THI!\n\nBạn đã rời khỏi màn hình thi ${count} lần (vượt quá giới hạn ${maxViolations} lần cho phép).\n\nHệ thống tự động thu bài và nộp kết quả ngay bây giờ.`);
        submitExam(false);
        return;
    }

    showExamViolationModal(count, maxViolations, msg);
}

function showExamViolationModal(count, maxViolations, detailMsg) {
    const modal = document.getElementById('examViolationModal');
    if (!modal) return;

    const countEl = document.getElementById('examViolationCount');
    if (countEl) countEl.innerText = `${count} / ${maxViolations}`;

    const descEl = document.getElementById('examViolationDesc');
    if (descEl) {
        const remaining = maxViolations - count;
        descEl.innerHTML = `
            ${detailMsg ? `<div style="font-size: 0.95rem; color: #dc2626; font-weight: 700; margin-bottom: 8px;"><i class="ri-error-warning-fill"></i> ${escapeHtml(detailMsg)}</div>` : ''}
            <div>Thí sinh không được phép chuyển tab, mở ứng dụng khác hoặc thoát chế độ toàn màn hình trong suốt thời gian làm bài thi thử.</div>
            <div style="margin-top: 8px; font-weight: 700; color: #b91c1c;">Bạn còn <b>${remaining}</b> lần cảnh báo trước khi bài thi bị tự động nộp!</div>
        `;
    }

    modal.style.display = 'flex';
}

function dismissExamViolationModal() {
    closeExamViolationModal();
    if (currentMode === 'exam' && !document.fullscreenElement && document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(() => {});
    }
}

function closeExamViolationModal() {
    const modal = document.getElementById('examViolationModal');
    if (modal) modal.style.display = 'none';
}

// ========================================================
// QUẢN TRỊ PHIÊN THI DUY NHẤT (SESSION EXAM UNIQUE)
// ========================================================
function initExamSessionUnique(quizId) {
    if (!quizId || currentMode !== 'exam') return;

    if (!window.examClientInstanceId) {
        window.examClientInstanceId = 'inst_' + Date.now() + '_' + Math.random().toString(36).substr(2, 7);
    }
    const currentInst = window.examClientInstanceId;
    const storageKey = `hntn_exam_active_${quizId}`;

    // 1. Kiểm tra trạng thái tab đang hoạt động từ localStorage
    try {
        const raw = localStorage.getItem(storageKey);
        if (raw) {
            const data = JSON.parse(raw);
            const now = Date.now();
            if (data && data.instanceId && data.instanceId !== currentInst && (now - (data.ts || 0) < 15000)) {
                showExamSessionConflictModal();
            }
        }
    } catch (e) {
        console.warn("Storage check error:", e);
    }

    // 2. Thiết lập kênh BroadcastChannel để phát hiện xung đột thời gian thực
    try {
        if (window.BroadcastChannel) {
            if (window.examBroadcastChannel) {
                window.examBroadcastChannel.close();
            }
            window.examBroadcastChannel = new BroadcastChannel(`hntn_exam_channel_${quizId}`);
            
            window.examBroadcastChannel.postMessage({
                type: 'EXAM_TAB_OPENED',
                instanceId: currentInst,
                sessionId: window.currentExamSessionId
            });

            window.examBroadcastChannel.onmessage = (event) => {
                const msg = event.data;
                if (!msg || !window.examAntiCheatActive || currentMode !== 'exam' || document.body.classList.contains('quiz-completed')) return;

                if (msg.type === 'EXAM_TAB_OPENED' && msg.instanceId !== currentInst) {
                    window.examBroadcastChannel.postMessage({
                        type: 'EXAM_TAB_ALREADY_ACTIVE',
                        instanceId: currentInst,
                        sessionId: window.currentExamSessionId
                    });
                } else if (msg.type === 'EXAM_TAB_ALREADY_ACTIVE' && msg.instanceId !== currentInst) {
                    showExamSessionConflictModal();
                } else if (msg.type === 'EXAM_SESSION_CLAIMED' && msg.instanceId !== currentInst) {
                    showExamSessionConflictModal();
                }
            };
        }
    } catch (e) {
        console.warn("BroadcastChannel error:", e);
    }

    // 3. Heartbeat định kỳ cập nhật quyền sở hữu phiên
    clearInterval(window._examSessionHeartbeat);
    window._examSessionHeartbeat = setInterval(() => {
        if (!window.examAntiCheatActive || currentMode !== 'exam' || document.body.classList.contains('quiz-completed')) {
            clearInterval(window._examSessionHeartbeat);
            return;
        }
        try {
            localStorage.setItem(storageKey, JSON.stringify({
                instanceId: currentInst,
                sessionId: window.currentExamSessionId,
                ts: Date.now()
            }));
        } catch (e) {}
    }, 4000);
}

function showExamSessionConflictModal() {
    const modal = document.getElementById('examSessionConflictModal');
    if (modal) modal.style.display = 'flex';
}

function closeExamSessionConflictModal() {
    const modal = document.getElementById('examSessionConflictModal');
    if (modal) modal.style.display = 'none';
}

function claimExamSessionHere() {
    const quizId = getCurrentQuizId();
    if (!quizId) return;

    closeExamSessionConflictModal();
    if (!window.examClientInstanceId) {
        window.examClientInstanceId = 'inst_' + Date.now() + '_' + Math.random().toString(36).substr(2, 7);
    }
    const currentInst = window.examClientInstanceId;
    const storageKey = `hntn_exam_active_${quizId}`;

    try {
        localStorage.setItem(storageKey, JSON.stringify({
            instanceId: currentInst,
            sessionId: window.currentExamSessionId,
            ts: Date.now()
        }));
        if (window.examBroadcastChannel) {
            window.examBroadcastChannel.postMessage({
                type: 'EXAM_SESSION_CLAIMED',
                instanceId: currentInst,
                sessionId: window.currentExamSessionId
            });
        }
    } catch (e) {}

    showToast("✅ Đã chuyển phiên làm bài sang tab hiện tại!", "success");
    if (!document.fullscreenElement && document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(() => {});
    }
}

function destroyExamSessionUnique() {
    const quizId = getCurrentQuizId();
    if (quizId) {
        try {
            localStorage.removeItem(`hntn_exam_active_${quizId}`);
        } catch (e) {}
    }
    clearInterval(window._examSessionHeartbeat);
    if (window.examBroadcastChannel) {
        try {
            window.examBroadcastChannel.close();
        } catch (e) {}
        window.examBroadcastChannel = null;
    }
    closeExamSessionConflictModal();
}

window.openDedicatedExportPageFromIndex = function() {
    const targetUrl = currentExportQuizId ? `/export/${encodeURIComponent(currentExportQuizId)}` : '/export';
    window.open(targetUrl, '_blank');
    if (typeof closeExportDocxModal === 'function') closeExportDocxModal();
};
