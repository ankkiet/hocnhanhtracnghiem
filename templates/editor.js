// ========================================================
// HOCNHANHTN EDITOR STUDIO - JAVASCRIPT CONTROLLER
// ========================================================

// Tự động nhận diện môi trường (Localhost vs Production)
const PROD_BACKEND_URL = "https://inland-marylin-hocnhanhtn-c3471a95.koyeb.app";
let API_BASE_URL = window.location.origin;

const currentHost = window.location.hostname || '';
if (window.location.protocol === 'file:') {
    API_BASE_URL = "http://127.0.0.1:8000";
} else if (
    currentHost.endsWith('.pages.dev') || 
    currentHost.endsWith('.vercel.app') || 
    currentHost.endsWith('.netlify.app') || 
    currentHost.endsWith('.github.io')
) {
    API_BASE_URL = PROD_BACKEND_URL;
} else {
    API_BASE_URL = window.location.origin;
}

if (typeof localStorage !== 'undefined' && localStorage.getItem('CUSTOM_API_BASE_URL')) {
    API_BASE_URL = localStorage.getItem('CUSTOM_API_BASE_URL');
}

// Tự động gửi tín hiệu đánh thức máy chủ Backend ngay khi mở Studio (Chống Sleep / Cold Start)
fetch(`${API_BASE_URL}/api/health`, { method: 'GET', cache: 'no-store' }).catch(() => {});

// Global States
let currentData = [];
let editingQuizId = null;
let editingQuizSettings = {
    title: "Đề thi mới",
    mode: "practice",
    timeLimit: 0,
    isShuffle: false
};
let currentStudioMode = 'edit'; // 'edit' | 'practice' | 'exam'
let globalEditorImageStorage = {};
let globalEditorImageCounter = 0;
window.activeAIFeedbacks = {};

// Auth
let authToken = localStorage.getItem('auth_token') || '';
let authRole = localStorage.getItem('auth_role') || '';

// Practice / Exam test states
let testPracticeAnswers = {};
let testExamAnswers = {};

// Khởi chạy khi DOM sẵn sàng
document.addEventListener('DOMContentLoaded', () => {
    initStudio();
});

async function initStudio() {
    if (!authToken) {
        console.log("Khách trải nghiệm Studio chưa đăng nhập. Sẽ yêu cầu đăng nhập khi Lưu & Xuất bản.");
    }

    setupEditorEvents();
    setupTitleEvents();

    const urlParams = new URLSearchParams(window.location.search);
    const taskId = urlParams.get('task_id') || sessionStorage.getItem('editor_pending_task_id');
    const quizId = urlParams.get('id') || urlParams.get('quiz_id');
    const titleParam = urlParams.get('title') || sessionStorage.getItem('editor_quiz_title');
    const modeParam = urlParams.get('mode') || sessionStorage.getItem('editor_pending_mode');

    if (titleParam) {
        editingQuizSettings.title = titleParam;
        document.getElementById('studioQuizTitle').value = titleParam;
    }

    if (taskId) {
        // Người dùng vừa bấm phân tích file hoặc sinh đề AI ở trang chủ -> Đã chuyển ngay sang Studio!
        await pollStudioTask(taskId, titleParam, modeParam);
    } else if (quizId) {
        // Tải từ cơ sở dữ liệu nếu có ID trên URL
        await loadQuizById(quizId);
    } else {
        // Tải từ Session Storage (hoặc bản lưu nháp trước đó)
        loadQuizFromSession();
    }
}

function resetHntnLoader(container) {
    if (!container) return;
    const svg = container.querySelector('.hntn-loader-svg');
    if (svg && svg.parentNode) {
        const clone = svg.cloneNode(true);
        svg.parentNode.replaceChild(clone, svg);
    }
}

async function pollStudioTask(taskId, initialTitle, mode) {
    const overlay = document.getElementById('studioLoadingOverlay');
    const progressBar = document.getElementById('studioProgressBar');
    const progressPercent = document.getElementById('studioProgressPercent');
    const statusTitle = document.getElementById('studioLoadingStatus');
    const statusSub = document.getElementById('studioLoadingSub');

    if (overlay) {
        resetHntnLoader(overlay);
        overlay.style.display = 'flex';
    }
    
    if (initialTitle) {
        editingQuizSettings.title = initialTitle;
        document.getElementById('studioQuizTitle').value = initialTitle;
    }

    if (statusTitle) {
        statusTitle.innerText = mode === 'ai_generate' ? '🤖 AI đang suy nghĩ và sáng tạo câu hỏi...' : '🤖 AI đang đọc và phân tích tài liệu...';
    }
    if (statusSub) {
        statusSub.innerText = mode === 'ai_generate' 
            ? 'Hệ thống đang sinh câu hỏi, 4 phương án lựa chọn và lời giải thích chi tiết.'
            : 'Hệ thống đang bóc tách từng câu hỏi, đáp án, hình ảnh và công thức toán học.';
    }

    let progress = 15;
    let elapsedSeconds = 0;
    const progressInterval = setInterval(() => {
        elapsedSeconds++;
        if (progress < 90) {
            progress += Math.random() * 2;
            if (progressBar) progressBar.style.width = Math.min(progress, 90) + '%';
            if (progressPercent) progressPercent.innerText = Math.floor(Math.min(progress, 90)) + '%';
        }
        if (statusSub) {
            statusSub.innerText = `Đã xử lý ${elapsedSeconds}s (thường mất 15-30 giây đối với tài liệu dài, vui lòng không tải lại trang)...`;
        }
    }, 1000);

    let consecutive404Count = 0;

    const poll = async () => {
        try {
            const statusRes = await fetch(`${API_BASE_URL}/api/task_status/${taskId}`);
            
            if (statusRes.status === 404) {
                consecutive404Count++;
                if (consecutive404Count < 5) {
                    // Task có thể vừa được tạo hoặc máy chủ đang kích hoạt luồng ngầm, thử lại thêm
                    setTimeout(poll, 3000);
                    return;
                }
                clearInterval(progressInterval);
                sessionStorage.removeItem('editor_pending_task_id');
                sessionStorage.removeItem('editor_pending_mode');
                if (overlay) overlay.style.display = 'none';
                alert("Tiến trình phân tích không tìm thấy hoặc đã quá hạn. Đang mở bản lưu gần nhất.");
                loadQuizFromSession();
                return;
            }

            const statusData = await statusRes.json();
            consecutive404Count = 0; // Đã kết nối thành công, reset bộ đếm

            if (statusData.status === "success") {
                clearInterval(progressInterval);
                if (progressBar) progressBar.style.width = '100%';
                if (progressPercent) progressPercent.innerText = '100%';
                if (statusTitle) statusTitle.innerText = '✅ Phân tích hoàn tất!';
                if (statusSub) statusSub.innerText = 'Đang hiển thị đề thi vào Studio...';
                
                await new Promise(r => setTimeout(r, 400));
                
                // Xóa task ID đã xử lý khỏi sessionStorage
                sessionStorage.removeItem('editor_pending_task_id');
                sessionStorage.removeItem('editor_pending_mode');
                
                // Làm sạch URL (bỏ ?task_id=...) để khi reload không bị lặp lại polling
                window.history.replaceState({}, document.title, 'editor.html');

                // Nạp dữ liệu vào Studio
                currentData = normalizeImageUrls(statusData.data || []);
                editingQuizId = null;
                window.isCurrentQuizPublished = false;
                window.draftImageKeys = statusData.images || extractImageKeysFromClient(currentData);
                sessionStorage.setItem('editor_draft_images', JSON.stringify(window.draftImageKeys));
                
                syncDataToEditor();
                renderPreviewAll();
                updateQCountBadge();
                saveDraftToSession();

                if (overlay) overlay.style.display = 'none';
                showToast("✨ Phân tích hoàn tất! Dữ liệu đã sẵn sàng trong Studio.");
            } else if (statusData.status === "error") {
                clearInterval(progressInterval);
                sessionStorage.removeItem('editor_pending_task_id');
                sessionStorage.removeItem('editor_pending_mode');
                if (overlay) overlay.style.display = 'none';
                alert("Lỗi khi phân tích: " + (statusData.detail || "Không rõ nguyên nhân"));
                loadQuizFromSession();
            } else {
                // Vẫn đang xử lý
                if (statusData.message && statusTitle) {
                    statusTitle.innerText = "🤖 " + statusData.message;
                }
                setTimeout(poll, 2500);
            }
        } catch(err) {
            // Lỗi mạng hoặc server đang thức giấc (Cold Start), tự động thử lại sau 3.5s
            if (statusTitle) statusTitle.innerText = "⏳ Đang kết nối với máy chủ AI...";
            setTimeout(poll, 3500);
        }
    };

    poll();
}

function renderMathJax(targetElement) {
    if (window.MathJax && typeof window.MathJax.typesetPromise === 'function') {
        const targets = targetElement ? [targetElement] : undefined;
        MathJax.typesetPromise(targets).catch((err) => console.log('MathJax error:', err));
    } else {
        setTimeout(() => {
            if (window.MathJax && typeof window.MathJax.typesetPromise === 'function') {
                const targets = targetElement ? [targetElement] : undefined;
                MathJax.typesetPromise(targets).catch((err) => console.log('MathJax error:', err));
            }
        }, 400);
    }
}

// ----------------------------------------------------
// TẢI DỮ LIỆU ĐỀ THI
// ----------------------------------------------------
async function loadQuizById(quizId) {
    showToast("⏳ Đang tải dữ liệu bài thi...");
    try {
        const response = await fetch(`${API_BASE_URL}/api/get_quiz/${quizId}?teacher_token=${authToken}`);
        const result = await response.json();
        
        if (result.status === 'success') {
            editingQuizId = quizId;
            window.isCurrentQuizPublished = true;
            sessionStorage.removeItem('editor_draft_images');
            editingQuizSettings = {
                title: result.title || "Đề thi chưa đặt tên",
                mode: result.mode || "practice",
                timeLimit: result.time_limit || 0,
                isShuffle: result.is_shuffle || false
            };
            
            document.getElementById('studioQuizTitle').value = editingQuizSettings.title;
            currentData = normalizeImageUrls(result.data || []);
            
            syncDataToEditor();
            renderPreviewAll();
            updateQCountBadge();

            // Hiển thị nút Copy Link trên thanh điều hướng Studio nếu đề đã xuất bản
            const btnCopy = document.getElementById('btnStudioCopyLink');
            if (btnCopy) btnCopy.style.display = 'inline-flex';
            const deleteLabel = document.getElementById('discardOrDeleteLabel');
            if (deleteLabel) deleteLabel.innerText = "Xóa đề";
            const btnDiscard = document.getElementById('btnDiscardOrDelete');
            if (btnDiscard) btnDiscard.title = "Xóa đề thi này khỏi hệ thống";

            showToast("✅ Đã nạp dữ liệu đề thi thành công!");
        } else {
            alert("Không tìm thấy đề thi hoặc bạn không có quyền chỉnh sửa.");
            window.location.href = "index.html";
        }
    } catch(e) {
        console.error(e);
        alert("Lỗi tải đề thi từ máy chủ.");
    }
}

function loadQuizFromSession() {
    const rawData = sessionStorage.getItem('editor_quiz_data');
    const rawTitle = sessionStorage.getItem('editor_quiz_title');
    const rawSettings = sessionStorage.getItem('editor_quiz_settings');

    if (rawTitle) {
        editingQuizSettings.title = rawTitle;
        document.getElementById('studioQuizTitle').value = rawTitle;
    } else {
        document.getElementById('studioQuizTitle').value = editingQuizSettings.title;
    }

    if (rawSettings) {
        try {
            editingQuizSettings = { ...editingQuizSettings, ...JSON.parse(rawSettings) };
        } catch(e) {}
    }

    if (rawData) {
        try {
            currentData = normalizeImageUrls(JSON.parse(rawData));
        } catch(e) {
            currentData = [];
        }
    }

    // Nếu chưa có dữ liệu nào, tạo khung mẫu ban đầu
    if (!currentData || currentData.length === 0) {
        currentData = [
            {
                group_title: "",
                question: "Nội dung câu hỏi mẫu thứ nhất ở đây?",
                options: [
                    "A. Lựa chọn thứ nhất",
                    "B. Lựa chọn thứ hai (đáp án đúng)",
                    "C. Lựa chọn thứ ba",
                    "D. Lựa chọn thứ tư"
                ],
                correct_answer: "B. Lựa chọn thứ hai (đáp án đúng)"
            }
        ];
    }

    syncDataToEditor();
    renderPreviewAll();
    updateQCountBadge();
    saveDraftToSession();
}

function normalizeImageUrls(data) {
    if (!data) return [];
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

function updateQCountBadge() {
    const badge = document.getElementById('studioQCountBadge');
    if (badge) {
        badge.innerText = `${currentData.length} câu hỏi`;
    }
}

function saveDraftToSession() {
    sessionStorage.setItem('editor_quiz_data', JSON.stringify(currentData));
    sessionStorage.setItem('editor_quiz_title', editingQuizSettings.title);
    sessionStorage.setItem('editor_quiz_settings', JSON.stringify(editingQuizSettings));
    
    const indicator = document.getElementById('autosaveIndicator');
    if (indicator) {
        indicator.innerText = "✓ Đã lưu nháp";
        indicator.style.opacity = "1";
    }
}

// ----------------------------------------------------
// THIẾT LẬP SỰ KIỆN TRÌNH SOẠN THẢO CODE
// ----------------------------------------------------
function getRichEditorText(node) {
    if (!node) return '';
    let result = '';
    for (let child of node.childNodes) {
        if (child.nodeType === Node.TEXT_NODE) {
            result += child.nodeValue;
        } else if (child.nodeType === Node.ELEMENT_NODE) {
            if (child.tagName === 'IMG') {
                result += child.outerHTML;
            } else if (child.tagName === 'BR') {
                result += '\n';
            } else if (child.tagName === 'DIV' || child.tagName === 'P') {
                let inner = getRichEditorText(child);
                result += (result.length > 0 && !result.endsWith('\n') ? '\n' : '') + inner + '\n';
            } else {
                result += getRichEditorText(child);
            }
        }
    }
    return result;
}

function setupEditorEvents() {
    const codeEditor = document.getElementById('codeEditor');
    if (!codeEditor) return;

    let editTimeout;
    codeEditor.addEventListener('input', function() {
        const indicator = document.getElementById('autosaveIndicator');
        if (indicator) indicator.innerText = "⏳ Đang gõ...";

        clearTimeout(editTimeout);
        editTimeout = setTimeout(() => {
            currentData = parseEditorText(getRichEditorText(codeEditor));
            renderPreviewAll();
            updateQCountBadge();
            saveDraftToSession();
        }, 300);
    });

    // Auto-complete bằng phím Tab
    codeEditor.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
            e.preventDefault();
            document.execCommand('insertText', false, '    ');
        }
    });
}

function setupTitleEvents() {
    const titleInput = document.getElementById('studioQuizTitle');
    if (!titleInput) return;

    titleInput.addEventListener('input', function() {
        editingQuizSettings.title = this.value.trim() || "Đề thi chưa đặt tên";
        saveDraftToSession();
    });
}

function syncDataToEditor() {
    const codeEditor = document.getElementById('codeEditor');
    if (codeEditor) {
        codeEditor.innerHTML = dataToEditorText(currentData);
    }
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

// ----------------------------------------------------
// CHUYỂN ĐỔI GIỮA DỮ LIỆU JSON VÀ TEXT CODE
// ----------------------------------------------------
function dataToEditorText(data) {
    let html = "";
    data.forEach((q, i) => {
        if (q.group_title && (i === 0 || q.group_title !== data[i-1].group_title)) {
            html += `<div style="color: #b45309; font-weight: bold; margin-bottom: 5px;">${q.group_title.replace(/<br>/gi, '<br>')}</div>`;
        }
        let qClean = (q.question || '').replace(/^(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])\s*/i, '').replace(/<br>/gi, '<br>');
        html += `<div style="margin-top: 10px;"><span style="color: #2563eb; font-weight: bold;">Câu ${i + 1}: </span>${qClean}</div>`;
        
        let qType = getRealQuestionType(q);
        if (qType === 'true_false') {
            let tfMap = (typeof q.correct_answer === 'object' && q.correct_answer !== null) ? q.correct_answer : {};
            (q.options || []).forEach((opt, oIdx) => {
                let optText = opt.replace(/<br>/gi, '<br>');
                let charMatch = optText.match(/^[a-d]/);
                let char = charMatch ? charMatch[0].toLowerCase() : String.fromCharCode(97 + oIdx);
                let isTrue = (char && tfMap[char] === true) || /^\*[a-d]/.test(optText) || /\[ĐÚNG\]|\(Đúng\)/i.test(optText);
                let cleanOpt = optText.replace(/^\*?[a-d][\)\.\:\-]\s*/, '');
                cleanOpt = cleanOpt.replace(/\[(ĐÚNG|SAI|Đ|S)\]|\((Đúng|Sai|Đ|S)\)/gi, '').trim();
                let prefix = isTrue ? `<span style="color: #059669; font-weight: bold;">*${char}) </span>` : `<span style="color: #0ea5e9; font-weight: bold;">${char}) </span>`;
                html += `<div>${prefix}${cleanOpt}</div>`;
            });
        } else if (qType === 'short_answer') {
            let ca = (q.correct_answer !== undefined && q.correct_answer !== null) ? String(q.correct_answer).trim() : '';
            if (ca) {
                html += `<div><span style="color: #059669; font-weight: bold;">Đáp án: </span>${ca}</div>`;
            }
        } else {
            // MCQ (4 lựa chọn)
            (q.options || []).forEach((opt) => {
                let isCorrect = (q.correct_answer === opt);
                if (!isCorrect && typeof q.correct_answer === 'string' && q.correct_answer.trim()) {
                    let caLetter = (q.correct_answer.trim().match(/\b([A-F])\b/i) || [])[1];
                    let optLetter = (opt.trim().match(/^[A-F]/) || [])[0];
                    if (caLetter && optLetter && caLetter.toUpperCase() === optLetter.toUpperCase()) {
                        isCorrect = true;
                    }
                }
                let optText = opt.replace(/<br>/gi, '<br>');
                if (isCorrect) {
                    optText = optText.replace(/^([A-F])([\.\:\)])/, '<span style="color: #059669; font-weight: bold;">*$1$2</span>');
                } else {
                    optText = optText.replace(/^([A-F])([\.\:\)])/, '<span style="color: #7c3aed; font-weight: bold;">$1$2</span>');
                }
                html += `<div>${optText}</div>`;
            });
        }
        if (q.explain && q.explain.trim()) {
            html += `<div><span style="color: #16a34a; font-style: italic;">Lời giải: </span>${q.explain.replace(/<br>/gi, '<br>')}</div>`;
        }
        html += `<br>`;
    });
    
    // Nén thẻ ảnh vào placeholder [HÌNH_ẢNH_X] - BỎ VÌ DÙNG WYSIWYG
    globalEditorImageStorage = {};
    globalEditorImageCounter = 0;

    return html;
}

function parseEditorText(text) {
    let restoredText = text;
    
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
            currentQ = {
                type: 'mcq',
                group_title: sharedContext.trim(),
                question: qText,
                options: [],
                correct_answer: null,
                explain: ''
            };
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
                || /^\s*\*/.test(line)
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

function updateSyntaxHighlight() {
    // Đã loại bỏ do chuyển sang giao diện WYSIWYG
}

function formatSubscriptsAndFormulas(text) {
    if (!text || typeof text !== 'string') return text;
    const placeholders = [];
    let safe = text.replace(/(\[IMG_\d+\]|\[HÌNH_ẢNH_\d+\])/g, (m) => {
        placeholders.push(m);
        return `XYZPH${placeholders.length - 1}XYZ`;
    });
    safe = safe.replace(/(\\\[[\s\S]*?\\\]|\\\(.*?\\\)|\$\$[\s\S]*?\$\$|\$[^\$]+?\$)/g, (m) => {
        placeholders.push(m);
        return `XYZPH${placeholders.length - 1}XYZ`;
    });
    safe = safe.replace(/(<[^>]+>)/g, (m) => {
        placeholders.push(m);
        return `XYZPH${placeholders.length - 1}XYZ`;
    });

    // CH_2 -> CH<sub>2</sub>, H_2O -> H<sub>2</sub>O, C_nH_{2n+2} -> C<sub>n</sub>H<sub>2n+2</sub>
    safe = safe.replace(/([A-Za-z0-9\)\>\]])_\{([^}]+)\}/g, '$1<sub>$2</sub>');
    safe = safe.replace(/([A-Za-z0-9\)\>\]])_([0-9]+)/g, '$1<sub>$2</sub>');
    safe = safe.replace(/([A-Z][a-z]?|\b[uvxyzmkn])_([a-z0-9]+)/g, '$1<sub>$2</sub>');
    safe = safe.replace(/([A-Za-z0-9\)\>\]])\^\{([^}]+)\}/g, '$1<sup>$2</sup>');
    safe = safe.replace(/([A-Za-z0-9\)\>\]])\^([0-9\+\-]+)/g, '$1<sup>$2</sup>');

    for (let i = placeholders.length - 1; i >= 0; i--) {
        safe = safe.split(`XYZPH${i}XYZ`).join(placeholders[i]);
    }
    return safe;
}

// ----------------------------------------------------
// RENDER KHUNG XEM TRƯỚC (GIAO DIỆN HỌC SINH)
// ----------------------------------------------------
function renderPreviewAll() {
    const previewContent = document.getElementById('preview-content');
    if (!previewContent) return;
    previewContent.innerHTML = '';
    
    if (currentData.length === 0) {
        previewContent.innerHTML = "<p style='text-align: center; color: var(--studio-text-muted);'>Chưa có câu hỏi nào trong đề thi.</p>";
        return;
    }

    let stats = {
        total: currentData.length,
        mcq4: 0,
        mcq3: 0,
        mcqOther: 0,
        tf: 0,
        short: 0
    };
    
    currentData.forEach(q => {
        let qType = getRealQuestionType(q);
        if (qType === 'true_false') stats.tf++;
        else if (qType === 'short_answer') stats.short++;
        else {
            let optCount = (q.options || []).length;
            if (optCount === 4) stats.mcq4++;
            else if (optCount === 3) stats.mcq3++;
            else stats.mcqOther++;
        }
    });

    const statsBox = document.createElement('div');
    statsBox.style.cssText = "background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px 16px; margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center;";
    statsBox.innerHTML = `
        <div style="font-weight: 700; color: #1e293b; width: 100%; margin-bottom: 4px;"><i class="ri-pie-chart-2-fill" style="color: #3b82f6;"></i> Thống kê đề thi</div>
        <div style="background: #e2e8f0; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; color: #334155;">Tổng số: ${stats.total} câu</div>
        ${stats.mcq4 > 0 ? `<div style="background: #dbeafe; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; color: #1d4ed8;">Trắc nghiệm 4 ĐA: ${stats.mcq4}</div>` : ''}
        ${stats.mcq3 > 0 ? `<div style="background: #dbeafe; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; color: #1d4ed8;">Trắc nghiệm 3 ĐA: ${stats.mcq3}</div>` : ''}
        ${stats.mcqOther > 0 ? `<div style="background: #dbeafe; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; color: #1d4ed8;">Trắc nghiệm khác: ${stats.mcqOther}</div>` : ''}
        ${stats.tf > 0 ? `<div style="background: #e0f2fe; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; color: #0369a1;">Đúng/Sai: ${stats.tf}</div>` : ''}
        ${stats.short > 0 ? `<div style="background: #fef3c7; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; color: #92400e;">Trả lời ngắn: ${stats.short}</div>` : ''}
    `;
    previewContent.appendChild(statsBox);

    currentData.forEach((q, qIndex) => {
        const prevBox = document.createElement('div');
        prevBox.className = 'question-box';
        prevBox.id = `preview_q_${qIndex}`;
        prevBox.style.marginBottom = '20px';
        prevBox.style.cursor = 'pointer';
        prevBox.title = 'Nhấn để cuộn đến mã Code của câu này';
        prevBox.onclick = () => scrollToQuestionInEditor(qIndex);
        
        let hasError = window.activeAIFeedbacks && window.activeAIFeedbacks[qIndex];
        if (hasError) {
            prevBox.style.borderColor = '#c084fc';
            prevBox.style.boxShadow = '0 4px 12px rgba(147, 51, 234, 0.1)';
        }

        let html = "";
        let groupTitleHtml = q.group_title ? `<div style="background: #fef9c3; padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; font-size: 0.9rem; font-weight: 600; color: #854d0e;">${formatSubscriptsAndFormulas(q.group_title).replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>` : '';
        let qClean = (q.question || '').replace(/^(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])\s*/i, '');
        let formattedQ = formatSubscriptsAndFormulas(qClean).replace(/(?:\r\n|\r|\n|\\n)/g, '<br>');
        
        let qType = getRealQuestionType(q);
        let typeBadge = '';
        if (qType === 'true_false') {
            typeBadge = '<span style="background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; margin-left: 8px; border: 1px solid #bae6fd;">Đúng / Sai</span>';
        } else if (qType === 'short_answer') {
            typeBadge = '<span style="background: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; margin-left: 8px; border: 1px solid #fde68a;">Trả lời ngắn</span>';
        }

        html += `${groupTitleHtml}<div class="question-title" style="font-size: 1.05rem; font-weight: 700; margin-bottom: 12px;">Câu ${qIndex + 1}: ${formattedQ} ${typeBadge}</div>`;
        
        if (qType === 'true_false') {
            // Giao diện xem trước cho câu hỏi Đúng / Sai
            let tfMap = (typeof q.correct_answer === 'object' && q.correct_answer !== null) ? q.correct_answer : {};
            html += `<div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px;">`;
            (q.options || []).forEach((opt, oIndex) => {
                let charMatch = opt.match(/^[a-d]/);
                let char = charMatch ? charMatch[0].toLowerCase() : String.fromCharCode(97 + oIndex);
                let isTrue = tfMap[char] === true;
                let optClean = formatSubscriptsAndFormulas(opt.replace(/^[a-d][\.\:\)]\s*/, ''));
                html += `
                    <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;">
                        <div style="display: flex; align-items: flex-start; gap: 8px; flex: 1;">
                            <span style="display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; background: #e2e8f0; color: #334155; font-weight: 700; border-radius: 6px; font-size: 0.85rem; flex-shrink: 0;">${char}</span>
                            <span style="font-size: 0.95rem; color: #1e293b;">${optClean}</span>
                        </div>
                        <div style="display: flex; gap: 6px; margin-left: 10px; flex-shrink: 0;">
                            <span style="padding: 2px 8px; border-radius: 6px; font-size: 0.8rem; font-weight: 700; border: 1px solid ${isTrue ? '#86efac' : '#cbd5e1'}; background: ${isTrue ? '#dcfce7' : '#ffffff'}; color: ${isTrue ? '#15803d' : '#94a3b8'}; cursor: pointer; transition: 0.2s;" onclick="changeTfAnswer(${qIndex}, '${char}', true); event.stopPropagation();" title="Chọn làm đáp án đúng">Đúng</span>
                            <span style="padding: 2px 8px; border-radius: 6px; font-size: 0.8rem; font-weight: 700; border: 1px solid ${!isTrue ? '#fca5a5' : '#cbd5e1'}; background: ${!isTrue ? '#fee2e2' : '#ffffff'}; color: ${!isTrue ? '#b91c1c' : '#94a3b8'}; cursor: pointer; transition: 0.2s;" onclick="changeTfAnswer(${qIndex}, '${char}', false); event.stopPropagation();" title="Chọn làm đáp án sai">Sai</span>
                        </div>
                    </div>`;
            });
            html += `</div>`;
        } else if (qType === 'short_answer') {
            // Giao diện xem trước cho câu hỏi Trả lời ngắn
            let caVal = (q.correct_answer !== undefined && q.correct_answer !== null) ? String(q.correct_answer) : 'Chưa nhập đáp án';
            html += `
                <div style="display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: #f8fafc; border: 1.5px dashed #cbd5e1; border-radius: 8px; margin-bottom: 10px;">
                    <span style="font-weight: 700; color: #0284c7; font-size: 0.95rem;">✍️ Đáp án ngắn:</span>
                    <span style="font-weight: 700; font-size: 1.05rem; background: #dcfce7; color: #15803d; padding: 3px 12px; border-radius: 6px; border: 1px solid #86efac;">${escapeHtml(caVal)}</span>
                </div>`;
        } else {
            // MCQ (4 lựa chọn)
            (q.options || []).forEach((opt, oIndex) => {
                let isCorrect = q.correct_answer === opt;
                if (!isCorrect && typeof q.correct_answer === 'string' && q.correct_answer.trim()) {
                    let caLetter = (q.correct_answer.trim().match(/\b([A-F])\b/i) || [])[1];
                    let optLetter = (opt.trim().match(/^[A-F]/i) || [])[0];
                    if (caLetter && optLetter && caLetter.toUpperCase() === optLetter.toUpperCase()) {
                        isCorrect = true;
                    }
                }
                let optClean = formatSubscriptsAndFormulas(opt.replace(/^[A-F][\.\:\)]\s*/i, ''));
                html += `<label class="option-practice ${isCorrect ? 'correct selected' : ''}" style="cursor: pointer; padding: 10px 14px; margin-bottom: 8px;" onclick="changeCorrectAnswer(${qIndex}, ${oIndex}); event.stopPropagation();" title="Bấm để chọn làm đáp án đúng">
                            <input type="radio" disabled ${isCorrect ? 'checked' : ''}>
                            <span class="opt-badge">${opt.match(/^[A-F]/i) ? opt.match(/^[A-F]/i)[0].toUpperCase() : String.fromCharCode(65 + oIndex)}</span>
                            <span class="opt-text">${optClean}</span>
                        </label>`;
            });
        }

        // Lời giải chi tiết
        if (q.explain && q.explain.trim()) {
            html += `<div style="margin-top: 8px; padding: 8px 12px; background: #f1f5f9; border-left: 3px solid #64748b; border-radius: 6px; font-size: 0.9rem; color: #334155;">
                <b>💡 Lời giải:</b> ${formatSubscriptsAndFormulas(q.explain).replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}
            </div>`;
        }
        
        prevBox.innerHTML = html;
        
        // Chèn thẻ AI gợi ý sửa lỗi / xóa câu / đổi kết cấu nếu có
        if (hasError) {
            const aiData = window.activeAIFeedbacks[qIndex];
            const isDelete = aiData.action === 'delete' || aiData.category === 'delete';
            const isRestructure = aiData.action === 'restructure' || aiData.category === 'restructure';

            const catClass = isDelete ? 'ai-cat-delete' :
                             (isRestructure ? 'ai-cat-restructure' :
                             (aiData.category === 'knowledge' ? 'ai-cat-knowledge' :
                             (aiData.category === 'answer' ? 'ai-cat-answer' :
                             (aiData.category === 'grammar_typo' ? 'ai-cat-grammar' : 'ai-cat-format'))));

            const aiDiv = document.createElement('div');
            aiDiv.onclick = (e) => e.stopPropagation();

            if (isDelete) {
                aiDiv.style.cssText = 'margin-top: 14px; padding: 14px; background: #fef2f2; border: 1.5px solid #fca5a5; border-radius: 10px; cursor: default;';
                aiDiv.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <i class="ri-delete-bin-line" style="color: #dc2626; font-size: 1.15rem;"></i>
                            <strong style="color: #dc2626;">Yêu cầu xóa câu hỏi:</strong>
                            <span class="ai-cat-chip ${catClass}" style="padding: 2px 8px; font-size: 0.75rem;">${aiData.category_name || 'Yêu cầu xóa câu'}</span>
                        </div>
                    </div>
                    <div style="color: #991b1b; font-size: 0.92rem; font-weight: 500; margin-bottom: 10px; line-height: 1.5;">
                        ${escapeHtml(aiData.reason || 'Người làm đề yêu cầu loại bỏ câu hỏi này.')}
                    </div>
                    <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
                        <button class="btn-ai-delete" onclick="applyAIDelete(${qIndex})">
                            <i class="ri-delete-bin-line"></i> Xác nhận xóa câu này
                        </button>
                        <button class="btn-studio-outline" style="padding: 6px 12px; font-size: 0.85rem; border-radius: 6px;" onclick="dismissAISuggestion(${qIndex})">
                            Bỏ qua
                        </button>
                    </div>
                `;
            } else if (isRestructure) {
                aiDiv.style.cssText = 'margin-top: 14px; padding: 14px; background: #faf5ff; border: 1.5px solid #d8b4fe; border-radius: 10px; cursor: default;';
                let corrected = aiData.corrected_data || {};
                let targetType = corrected.type || 'true_false';
                let targetTypeName = targetType === 'true_false' ? 'Đúng / Sai' : (targetType === 'short_answer' ? 'Trả lời ngắn' : 'Trắc nghiệm 4 lựa chọn');

                let previewRestructure = '';
                if (targetType === 'true_false' && Array.isArray(corrected.options)) {
                    let tfMap = typeof corrected.correct_answer === 'object' && corrected.correct_answer ? corrected.correct_answer : {};
                    previewRestructure = `<div style="font-size: 0.88rem; background: #ffffff; padding: 10px; border-radius: 8px; border: 1px solid #e9d5ff; margin-bottom: 8px;">
                        <div style="font-weight: 700; color: #7e22ce; margin-bottom: 6px;"><i class="ri-checkbox-multiple-line"></i> Kết cấu Đúng/Sai mới:</div>`;
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
                            <i class="ri-swap-line" style="color: #7e22ce; font-size: 1.15rem;"></i>
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
                        <button class="btn-ai-restructure" onclick="applyAISuggestion(${qIndex})">
                            <i class="ri-check-line"></i> Áp dụng đổi kết cấu
                        </button>
                        <button class="btn-studio-outline" style="padding: 6px 12px; font-size: 0.85rem; border-radius: 6px;" onclick="dismissAISuggestion(${qIndex})">
                            Bỏ qua
                        </button>
                    </div>
                `;
            } else {
                aiDiv.style.cssText = 'margin-top: 14px; padding: 14px; background: #faf5ff; border: 1.5px solid #d8b4fe; border-radius: 10px; cursor: default;';
                let corrected = aiData.corrected_data || {};
                let correctedAnswerText = typeof corrected.correct_answer === 'object' ? JSON.stringify(corrected.correct_answer) : (corrected.correct_answer || '');
                let explainText = corrected.explain ? `<div style="margin-top: 6px; font-size: 0.88rem; color: #475569;"><b>💡 Giải thích:</b> ${escapeHtml(corrected.explain)}</div>` : '';

                aiDiv.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <i class="ri-sparkling-fill" style="color: #9333ea; font-size: 1.15rem;"></i>
                            <strong style="color: #9333ea;">AI Phát hiện vấn đề:</strong>
                            <span class="ai-cat-chip ${catClass}" style="padding: 2px 8px; font-size: 0.75rem;">${aiData.category_name || 'Cần sửa'}</span>
                        </div>
                    </div>
                    <div style="color: #dc2626; font-size: 0.92rem; font-weight: 600; margin-bottom: 8px;">
                        ${escapeHtml(aiData.reason)}
                    </div>
                    ${correctedAnswerText ? `<div style="font-size: 0.88rem; background: #f0fdf4; padding: 6px 10px; border-radius: 6px; border: 1px solid #bbf7d0; color: #166534; margin-bottom: 8px;">
                        <i class="ri-checkbox-circle-line" style="vertical-align: middle;"></i> <b>Đề xuất đáp án đúng:</b> ${escapeHtml(correctedAnswerText)}
                    </div>` : ''}
                    ${explainText}
                    <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
                        <button class="btn-primary" style="padding: 6px 14px; font-size: 0.85rem; background: #9333ea; border: none; border-radius: 6px;" onclick="applyAISuggestion(${qIndex})">
                            <i class="ri-magic-line"></i> Tự động sửa câu này
                        </button>
                        <button class="btn-studio-outline" style="padding: 6px 12px; font-size: 0.85rem; border-radius: 6px;" onclick="dismissAISuggestion(${qIndex})">
                            Bỏ qua
                        </button>
                    </div>
                `;
            }
            prevBox.appendChild(aiDiv);
        }

        previewContent.appendChild(prevBox);
    });
    
    renderMathJax(previewContent);
}

function scrollToQuestionInEditor(qIndex) {
    if (window.innerWidth <= 860) {
        switchStudioMobileTab('code');
    }
    const editor = document.getElementById('codeEditor');
    if (!editor) return;
    
    const spans = editor.querySelectorAll('span');
    let targetMatch = null;
    let currentQ = 0;
    
    for (let span of spans) {
        if (/Câu\s+\d+:/i.test(span.innerText)) {
            if (currentQ === qIndex) {
                targetMatch = span;
                break;
            }
            currentQ++;
        }
    }
    
    if (targetMatch) {
        targetMatch.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        const parent = targetMatch.parentElement || targetMatch;
        const origBg = parent.style.backgroundColor;
        parent.style.transition = 'background-color 0.3s';
        parent.style.backgroundColor = '#fef08a';
        setTimeout(() => { 
            parent.style.backgroundColor = origBg; 
        }, 1500);
    }
}

// Thay đổi đáp án từ giao diện Xem trước
window.changeCorrectAnswer = function(qIndex, oIndex) {
    if (!currentData[qIndex] || !currentData[qIndex].options) return;
    currentData[qIndex].correct_answer = currentData[qIndex].options[oIndex];
    syncDataToEditor();
    renderPreviewAll();
    saveDraftToSession();
    showToast("Đã cập nhật đáp án đúng!");
};

window.changeTfAnswer = function(qIndex, char, isTrue) {
    if (!currentData[qIndex]) return;
    if (typeof currentData[qIndex].correct_answer !== 'object' || currentData[qIndex].correct_answer === null) {
        currentData[qIndex].correct_answer = {};
    }
    currentData[qIndex].correct_answer[char.toLowerCase()] = isTrue;
    syncDataToEditor();
    renderPreviewAll();
    saveDraftToSession();
    showToast("Đã cập nhật đáp án Đúng/Sai!");
};

function insertQuestionTemplate() {
    const editor = document.getElementById('codeEditor');
    if (!editor) return;
    
    const nextQNum = currentData.length + 1;
    const template = `<br><br>Câu ${nextQNum}: Nội dung câu hỏi mới ở đây?<br>*A. Đáp án đúng thứ nhất<br>B. Đáp án thứ hai<br>C. Đáp án thứ ba<br>D. Đáp án thứ tư<br>`;
    
    editor.innerHTML += template;
    editor.scrollTop = editor.scrollHeight;
    editor.focus();
    
    currentData = parseEditorText(getRichEditorText(editor));
    renderPreviewAll();
    updateQCountBadge();
    saveDraftToSession();
    showToast(`Đã thêm Câu ${nextQNum}!`);
}

function formatEditorCode() {
    syncDataToEditor();
    renderPreviewAll();
    showToast("Đã chuẩn hóa định dạng đề thi!");
}

// ----------------------------------------------------
// TÍNH NĂNG AI RÀ SOÁT & THỐNG KÊ LỖI
// ----------------------------------------------------
function toggleAIPanel(forceState) {
    const panel = document.getElementById('aiFeedbackBox');
    if (!panel) return;
    
    if (forceState !== undefined) {
        panel.style.display = forceState ? 'block' : 'none';
    } else {
        panel.style.display = (panel.style.display === 'none' || !panel.style.display) ? 'block' : 'none';
    }
    
    if (panel.style.display === 'block') {
        panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

async function runAICheck() {
    const btn = document.getElementById('btnAICheck');
    const customPrompt = document.getElementById('aiCustomPrompt').value.trim();
    
    btn.innerText = "⏳ Đang quét đề thi (10-20s)...";
    btn.disabled = true;

    try {
        const res = await fetch(`${API_BASE_URL}/api/teacher/check_quiz_ai`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                teacher_token: authToken,
                quiz_data: currentData,
                custom_prompt: customPrompt
            })
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
                    category_counts: { delete: 0, restructure: 0, knowledge: 0, answer: 0, grammar_typo: 0, format: 0 }
                };

                let summaryHtml = data.summary ? `
                    <div class="ai-summary-banner">
                        <div class="ai-summary-title"><i class="ri-sparkling-fill"></i> Tóm tắt phản hồi từ AI:</div>
                        <div class="ai-summary-text">${escapeHtml(data.summary)}</div>
                    </div>
                ` : '';

                let catChipsHtml = '<div class="ai-cat-chips">';
                if (stats.category_counts?.delete > 0) {
                    catChipsHtml += `<span class="ai-cat-chip ai-cat-delete"><i class="ri-delete-bin-line"></i> Yêu cầu xóa: <b>${stats.category_counts.delete}</b></span>`;
                }
                if (stats.category_counts?.restructure > 0) {
                    catChipsHtml += `<span class="ai-cat-chip ai-cat-restructure"><i class="ri-swap-line"></i> Đổi kết cấu: <b>${stats.category_counts.restructure}</b></span>`;
                }
                catChipsHtml += `
                    <span class="ai-cat-chip ai-cat-knowledge"><i class="ri-brain-line"></i> Kiến thức: <b>${stats.category_counts?.knowledge || 0}</b></span>
                    <span class="ai-cat-chip ai-cat-answer"><i class="ri-close-circle-line"></i> Đáp án: <b>${stats.category_counts?.answer || 0}</b></span>
                    <span class="ai-cat-chip ai-cat-grammar"><i class="ri-spell-check-line"></i> Chính tả / Diễn đạt: <b>${stats.category_counts?.grammar_typo || 0}</b></span>
                    <span class="ai-cat-chip ai-cat-format"><i class="ri-ruler-line"></i> Định dạng: <b>${stats.category_counts?.format || 0}</b></span>
                </div>`;

                let statsHtml = `
                    ${summaryHtml}
                    <div class="ai-stat-grid">
                        <div class="ai-stat-card">
                            <span class="ai-stat-label">Số câu ban đầu</span>
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
                        <div style="font-size: 3rem; color: #10b981; margin-bottom: 10px;"><i class="ri-checkbox-circle-fill"></i></div>
                        <h3 style="margin: 0; color: #059669;">Tuyệt vời! Đề thi đạt chuẩn 100% không phát hiện lỗi!</h3>
                        <p style="margin: 6px 0 0 0; color: #64748b;">Toàn bộ câu hỏi, đáp án và định dạng đều hoàn hảo và sẵn sàng xuất bản.</p>
                    </div>
                `;
                document.getElementById('aiFeedbackContent').innerHTML = '';
                if (btnApplyAll) btnApplyAll.style.display = 'none';
            }
        } else {
            alert("Lỗi AI: " + (data.detail || "Không thể phân tích đề thi"));
        }
    } catch(e) {
        alert("Lỗi kết nối tới máy chủ khi gọi AI.");
    } finally {
        btn.innerHTML = '<i class="ri-search-eye-line"></i> Chạy AI Quét lỗi';
        btn.disabled = false;
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
            <i class="ri-list-check-2" style="color: #9333ea;"></i> Danh sách các câu cần xử lý (${remainingKeys.length} câu):
        </h4>
        <div class="ai-error-list-container">
    `;

    // Sắp xếp danh sách câu tăng dần theo question_index
    const sortedIndices = remainingKeys.map(Number).sort((a, b) => a - b);
    sortedIndices.forEach(qIdx => {
        const item = window.activeAIFeedbacks[qIdx];
        if (!item) return;

        const isDelete = item.action === 'delete' || item.category === 'delete';
        const isRestructure = item.action === 'restructure' || item.category === 'restructure';

        const catClass = isDelete ? 'ai-cat-delete' :
                         (isRestructure ? 'ai-cat-restructure' :
                         (item.category === 'knowledge' ? 'ai-cat-knowledge' :
                         (item.category === 'answer' ? 'ai-cat-answer' :
                         (item.category === 'grammar_typo' ? 'ai-cat-grammar' : 'ai-cat-format'))));

        let actionBtnHtml = '';
        if (isDelete) {
            actionBtnHtml = `<button class="btn-ai-delete" onclick="applyAIDelete(${qIdx})"><i class="ri-delete-bin-line"></i> Xóa câu này</button>`;
        } else if (isRestructure) {
            actionBtnHtml = `<button class="btn-ai-restructure" onclick="applyAISuggestion(${qIdx})"><i class="ri-swap-line"></i> Đổi kết cấu</button>`;
        } else {
            actionBtnHtml = `<button class="btn-studio-primary" style="padding: 6px 12px; font-size: 0.85rem; background: #9333ea;" onclick="applyAISuggestion(${qIdx})"><i class="ri-magic-line"></i> Sửa câu này</button>`;
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
                    <button class="btn-studio-outline" style="padding: 6px 12px; font-size: 0.85rem;" onclick="jumpToQuestionCard(${qIdx})"><i class="ri-focus-2-line"></i> Tới Câu ${qIdx + 1}</button>
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
        void targetCard.offsetWidth;
        targetCard.classList.add('ai-target-highlight');
        setTimeout(() => {
            targetCard.classList.remove('ai-target-highlight');
        }, 3600);
    }
    scrollToQuestionInEditor(qIndex);
}

function applyAllAISuggestions() {
    if (!window.activeAIFeedbacks || Object.keys(window.activeAIFeedbacks).length === 0) return;
    const count = Object.keys(window.activeAIFeedbacks).length;
    if (!confirm(`Bạn có chắc muốn áp dụng TẤT CẢ ${count} thay đổi từ AI (xóa câu, đổi kết cấu, sửa nội dung)?`)) return;

    if (Array.isArray(window.activeAINewQuizData) && window.activeAINewQuizData.length > 0) {
        currentData = JSON.parse(JSON.stringify(window.activeAINewQuizData));
    } else {
        // Áp dụng từ dưới lên (chỉ số cao xuống thấp) để tránh lệch index khi xóa câu
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

    syncDataToEditor();
    renderPreviewAll();
    saveDraftToSession();
    renderAIFeedbackList();

    const btnApplyAll = document.getElementById('btnApplyAllAI');
    if (btnApplyAll) btnApplyAll.style.display = 'none';

    document.getElementById('aiFeedbackStats').innerHTML = `
        <div style="text-align: center; padding: 20px 10px;">
            <div style="font-size: 2.5rem; color: #9333ea; margin-bottom: 8px;"><i class="ri-sparkling-fill"></i></div>
            <h3 style="margin: 0; color: #9333ea;">Đã áp dụng thành công tất cả thay đổi!</h3>
            <p style="margin: 4px 0 0 0; color: #64748b;">Dữ liệu đề thi và trình soạn thảo Code đã được cập nhật hoàn tất.</p>
        </div>
    `;
    showToast(`Đã áp dụng tất cả thay đổi thành công!`);
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
    window.activeAINewQuizData = null; // Huỷ bỏ snapshot hàng loạt vì dữ liệu đã thay đổi cục bộ

    syncDataToEditor();
    renderPreviewAll();
    saveDraftToSession();
    renderAIFeedbackList();

    showToast(`Đã xóa Câu ${question_index + 1}!`);
}

function applyAISuggestion(question_index) {
    const aiData = window.activeAIFeedbacks[question_index];
    if (!aiData) return;

    if (aiData.action === 'delete' || aiData.category === 'delete') {
        return applyAIDelete(question_index);
    }

    const corrected = aiData.corrected_data;
    if (!corrected) return;

    const origGroup = currentData[question_index] ? currentData[question_index].group_title : "";
    
    currentData[question_index] = {
        ...corrected,
        group_title: corrected.group_title !== undefined ? corrected.group_title : origGroup
    };

    delete window.activeAIFeedbacks[question_index];
    window.activeAINewQuizData = null;

    syncDataToEditor();
    renderPreviewAll();
    saveDraftToSession();
    renderAIFeedbackList();

    const isRestructure = aiData.action === 'restructure' || aiData.category === 'restructure';
    showToast(`Đã ${isRestructure ? 'đổi kết cấu' : 'sửa'} xong Câu ${question_index + 1}!`);
}

function dismissAISuggestion(question_index) {
    delete window.activeAIFeedbacks[question_index];
    window.activeAINewQuizData = null;
    renderPreviewAll();
    renderAIFeedbackList();
}

// ----------------------------------------------------
// MOBILE SEGMENTED TABS (SOẠN THẢO CODE / XEM TRƯỚC)
// ----------------------------------------------------
function switchStudioMobileTab(tab) {
    const tabCode = document.getElementById('mTabCode');
    const tabPreview = document.getElementById('mTabPreview');
    const splitView = document.getElementById('splitEditorView');
    const floatBtn = document.getElementById('studioMobileFloatToggle');
    if (!splitView) return;

    if (tab === 'preview') {
        splitView.classList.remove('mobile-tab-code');
        splitView.classList.add('mobile-tab-preview');
        if (tabCode) tabCode.classList.remove('active');
        if (tabPreview) tabPreview.classList.add('active');
        if (floatBtn) floatBtn.innerHTML = '<i class="ri-code-s-slash-line"></i> <span>Soạn thảo</span>';
        renderPreviewAll();
    } else {
        splitView.classList.remove('mobile-tab-preview');
        splitView.classList.add('mobile-tab-code');
        if (tabCode) tabCode.classList.add('active');
        if (tabPreview) tabPreview.classList.remove('active');
        if (floatBtn) floatBtn.innerHTML = '<i class="ri-eye-line"></i> <span>Xem trước</span>';
    }
}

function toggleStudioMobileTab() {
    const splitView = document.getElementById('splitEditorView');
    if (!splitView) return;
    if (splitView.classList.contains('mobile-tab-preview')) {
        switchStudioMobileTab('code');
    } else {
        switchStudioMobileTab('preview');
    }
}

// ----------------------------------------------------
// CHẾ ĐỘ LÀM THỬ (PRACTICE / EXAM TEST)
// ----------------------------------------------------
function switchStudioMode(mode) {
    currentStudioMode = mode;

    document.getElementById('pillModeEdit').className = mode === 'edit' ? 'studio-mode-pill active' : 'studio-mode-pill';
    document.getElementById('pillModePractice').className = mode === 'practice' ? 'studio-mode-pill active' : 'studio-mode-pill';
    document.getElementById('pillModeExam').className = mode === 'exam' ? 'studio-mode-pill active' : 'studio-mode-pill';

    const splitView = document.getElementById('splitEditorView');
    const testView = document.getElementById('interactiveTestView');
    const mobileTabs = document.getElementById('studioMobileViewTabs');
    const floatBtn = document.getElementById('studioMobileFloatToggle');

    if (mode === 'edit') {
        splitView.style.display = '';
        testView.style.display = 'none';
        if (mobileTabs) mobileTabs.style.display = '';
        if (floatBtn && window.innerWidth <= 860) floatBtn.style.display = 'inline-flex';
        renderPreviewAll();
    } else {
        splitView.style.display = 'none';
        testView.style.display = 'block';
        if (mobileTabs) mobileTabs.style.display = 'none';
        if (floatBtn) floatBtn.style.display = 'none';
        renderInteractiveTest(mode);
    }
}

function renderInteractiveTest(mode) {
    const container = document.getElementById('testQuizContainer');
    const titleElem = document.getElementById('testViewTitle');
    const submitArea = document.getElementById('testExamSubmitArea');
    if (!container) return;

    testPracticeAnswers = {};
    testExamAnswers = {};

    titleElem.innerText = mode === 'practice' ? "🎯 Chế độ Luyện tập thử nghiệm" : "📝 Chế độ Thi thử nghiệm";
    submitArea.style.display = mode === 'exam' ? 'block' : 'none';

    let html = "";
    currentData.forEach((q, qIndex) => {
        let groupTitleHtml = q.group_title ? `<div style="background: #fef9c3; padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; font-size: 0.9rem; font-weight: 600; color: #854d0e;">${formatSubscriptsAndFormulas(q.group_title).replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>` : '';
        let qClean = (q.question || '').replace(/^(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])\s*/i, '');
        let formattedQ = formatSubscriptsAndFormulas(qClean).replace(/(?:\r\n|\r|\n|\\n)/g, '<br>');

        html += `
            <div class="question-box" id="test_q_box_${qIndex}" style="background: white; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: var(--shadow); border: 1px solid var(--border);">
                ${groupTitleHtml}
                <div class="question-title" style="font-size: 1.1rem; font-weight: 700; margin-bottom: 15px;">
                    Câu ${qIndex + 1}: ${formattedQ}
                </div>
                <div class="options-container">
        `;

        const qType = getRealQuestionType(q);
        if (qType === 'true_false') {
            (q.options || []).forEach((opt, oIndex) => {
                const charMatch = opt.match(/^[a-d]/);
                const char = charMatch ? charMatch[0].toLowerCase() : String.fromCharCode(97 + oIndex);
                const optContent = formatSubscriptsAndFormulas(opt.replace(/^[a-d][\.\:\)]\s*/, ''));
                html += `
                    <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; margin-bottom: 8px;">
                        <div style="flex: 1; margin-right: 12px; font-size: 0.95rem;"><b>${char})</b> ${optContent}</div>
                        <div style="display: flex; gap: 6px;">
                            <button type="button" class="studio-tf-btn" id="test_tf_${qIndex}_${char}_t" onclick="handleTestTFSelect(${qIndex}, '${char}', true, '${mode}')" style="padding: 4px 12px; border-radius: 6px; border: 1px solid #cbd5e1; background: white; cursor: pointer; font-weight: 600;">Đúng</button>
                            <button type="button" class="studio-tf-btn" id="test_tf_${qIndex}_${char}_f" onclick="handleTestTFSelect(${qIndex}, '${char}', false, '${mode}')" style="padding: 4px 12px; border-radius: 6px; border: 1px solid #cbd5e1; background: white; cursor: pointer; font-weight: 600;">Sai</button>
                        </div>
                    </div>`;
            });
        } else if (qType === 'short_answer') {
            html += `
                <div style="display: flex; gap: 8px; margin-top: 8px;">
                    <input type="text" id="test_sa_${qIndex}" placeholder="Nhập câu trả lời..." style="flex: 1; padding: 10px 14px; border: 1px solid var(--border); border-radius: 8px;" onchange="handleTestSAChange(${qIndex}, this.value)">
                    ${mode === 'practice' ? `<button class="btn-primary" style="margin: 0; padding: 8px 16px;" onclick="handleTestSAPracticeCheck(${qIndex})">Kiểm tra</button>` : ''}
                </div>
                <div id="test_sa_feedback_${qIndex}" style="margin-top: 6px; font-weight: 600;"></div>`;
        } else {
            (q.options || []).forEach((opt, oIndex) => {
                const optChar = opt.match(/^[A-F]/i) ? opt.match(/^[A-F]/i)[0].toUpperCase() : String.fromCharCode(65 + oIndex);
                const optContent = formatSubscriptsAndFormulas(opt.replace(/^[A-F][\.\:\)]\s*/i, ''));

                if (mode === 'practice') {
                    html += `
                        <div class="option-practice" id="test_opt_${qIndex}_${oIndex}" onclick="handleTestPracticeSelect(${qIndex}, ${oIndex})">
                            <span class="opt-badge">${optChar}</span>
                            <span class="opt-text">${optContent}</span>
                        </div>
                    `;
                } else {
                    html += `
                        <label class="option-wrapper" style="display: flex; align-items: center; padding: 12px 14px; border: 1px solid var(--border); border-radius: 8px; margin-bottom: 8px; cursor: pointer; transition: all 0.2s;" id="test_exam_opt_${qIndex}_${oIndex}">
                            <input type="radio" name="test_exam_radio_${qIndex}" style="width: 20px; height: 20px; margin-right: 12px;" onchange="handleTestExamSelect(${qIndex}, ${oIndex})">
                            <span style="font-weight: 700; margin-right: 8px; color: var(--primary);">${optChar}.</span>
                            <span>${optContent}</span>
                        </label>
                    `;
                }
            });
        }

        html += `</div></div>`;
    });

    container.innerHTML = html;

    renderMathJax(container);
}

function handleTestTFSelect(qIndex, char, isTrue, mode) {
    if (mode === 'practice') {
        const q = currentData[qIndex];
        const correctMap = (typeof q.correct_answer === 'object' && q.correct_answer) ? q.correct_answer : {};
        const isMatched = (Boolean(correctMap[char]) === isTrue);
        const btnT = document.getElementById(`test_tf_${qIndex}_${char}_t`);
        const btnF = document.getElementById(`test_tf_${qIndex}_${char}_f`);
        if (btnT && btnF) {
            btnT.style.background = (isTrue && isMatched) ? '#dcfce7' : (isTrue && !isMatched ? '#fee2e2' : 'white');
            btnF.style.background = (!isTrue && isMatched) ? '#dcfce7' : (!isTrue && !isMatched ? '#fee2e2' : 'white');
        }
    } else {
        if (!testExamAnswers[qIndex] || typeof testExamAnswers[qIndex] !== 'object') {
            testExamAnswers[qIndex] = {};
        }
        testExamAnswers[qIndex][char] = isTrue;
        const btnT = document.getElementById(`test_tf_${qIndex}_${char}_t`);
        const btnF = document.getElementById(`test_tf_${qIndex}_${char}_f`);
        if (btnT && btnF) {
            btnT.style.background = isTrue ? '#dbeafe' : 'white';
            btnT.style.borderColor = isTrue ? '#3b82f6' : '#cbd5e1';
            btnF.style.background = !isTrue ? '#dbeafe' : 'white';
            btnF.style.borderColor = !isTrue ? '#3b82f6' : '#cbd5e1';
        }
    }
}

function handleTestSAChange(qIndex, val) {
    testExamAnswers[qIndex] = val;
}

function handleTestSAPracticeCheck(qIndex) {
    const q = currentData[qIndex];
    const inputEl = document.getElementById(`test_sa_${qIndex}`);
    const feedbackEl = document.getElementById(`test_sa_feedback_${qIndex}`);
    const uStr = inputEl ? inputEl.value.trim().toLowerCase().replace(',', '.').replace(/\s+/g, '') : '';
    const cStr = String(q.correct_answer || '').trim().toLowerCase().replace(',', '.').replace(/\s+/g, '');
    const isCorrect = Boolean(uStr && uStr === cStr);
    
    if (feedbackEl) {
        feedbackEl.innerHTML = isCorrect ? 
            `<span style="color: #16a34a;">✅ Chính xác!</span>` : 
            `<span style="color: #dc2626;">❌ Sai rồi. Đáp án đúng là: ${escapeHtml(String(q.correct_answer || ''))}</span>`;
    }
}

function handleTestPracticeSelect(qIndex, oIndex) {
    if (testPracticeAnswers[qIndex] !== undefined) return;
    testPracticeAnswers[qIndex] = oIndex;

    const q = currentData[qIndex];
    if (!q || !q.options) return;
    const selectedOpt = q.options[oIndex];
    const isCorrect = (selectedOpt === q.correct_answer);

    const clickedEl = document.getElementById(`test_opt_${qIndex}_${oIndex}`);
    if (clickedEl) {
        if (isCorrect) {
            clickedEl.classList.add('correct');
        } else {
            clickedEl.classList.add('incorrect');
            // Tìm và highlight đáp án đúng
            q.options.forEach((opt, idx) => {
                if (opt === q.correct_answer) {
                    const corrEl = document.getElementById(`test_opt_${qIndex}_${idx}`);
                    if (corrEl) corrEl.classList.add('correct');
                }
            });
        }
    }
}

function handleTestExamSelect(qIndex, oIndex) {
    testExamAnswers[qIndex] = oIndex;
}

function handleTestExamSubmit() {
    let earnedTotal = 0;
    currentData.forEach((q, qIndex) => {
        const qType = getRealQuestionType(q);
        if (qType === 'true_false') {
            const chosen = testExamAnswers[qIndex] || {};
            const correctMap = (typeof q.correct_answer === 'object' && q.correct_answer) ? q.correct_answer : {};
            let matches = 0;
            ['a', 'b', 'c', 'd'].forEach(char => {
                if (chosen[char] !== undefined && Boolean(chosen[char]) === Boolean(correctMap[char])) matches++;
            });
            const tfScale = [0.0, 0.1, 0.25, 0.5, 1.0];
            earnedTotal += (tfScale[matches] !== undefined ? tfScale[matches] : 0.0);
        } else if (qType === 'short_answer') {
            const userStr = String(testExamAnswers[qIndex] || '').trim().toLowerCase().replace(',', '.').replace(/\s+/g, '');
            const corrStr = String(q.correct_answer || '').trim().toLowerCase().replace(',', '.').replace(/\s+/g, '');
            if (userStr && userStr === corrStr) earnedTotal += 1;
        } else {
            const chosenIdx = testExamAnswers[qIndex];
            if (chosenIdx !== undefined && q.options && q.options[chosenIdx] === q.correct_answer) {
                earnedTotal += 1;
            }
        }
    });

    const score = currentData.length > 0 ? ((earnedTotal / currentData.length) * 10).toFixed(1) : "0.0";
    alert(`🎉 KẾT QUẢ THI THỬ:\n\n- Điểm đạt được: ${earnedTotal.toFixed(2)} / ${currentData.length}\n- Điểm quy đổi: ${score} / 10`);
}

// ----------------------------------------------------
// XUẤT FILE WORD (.DOCX)
// ----------------------------------------------------
async function exportWordDocument() {
    if (!editingQuizId) {
        alert("Vui lòng 'Lưu & Xuất bản' đề thi trước khi tải file Word chuẩn in ấn!");
        openPublishModal();
        return;
    }
    // Tự động lưu cập nhật mới nhất trước khi tải file Word
    showToast("⏳ Đang đồng bộ bản mới nhất...");
    try {
        const payload = {
            quiz_id: editingQuizId,
            title: editingQuizSettings.title || "Đề thi",
            data: currentData,
            mode: editingQuizSettings.mode || "practice",
            time_limit: editingQuizSettings.timeLimit || 0,
            is_shuffle: editingQuizSettings.isShuffle || false,
            creator_id: authToken,
            status: "published"
        };
        await fetch(`${API_BASE_URL}/api/save_quiz`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
    } catch(e) {}
    window.open(`${API_BASE_URL}/api/teacher/export_docx/${editingQuizId}?teacher_token=${authToken}`, '_blank');
}

// ----------------------------------------------------
// MODAL CẤU HÌNH VÀ LƯU XUẤT BẢN
// ----------------------------------------------------
function openPublishModal() {
    const modal = document.getElementById('publishModal');
    if (!modal) return;
    
    document.getElementById('modalQuizTitle').value = editingQuizSettings.title || "";
    document.getElementById('modalQuizMode').value = editingQuizSettings.mode || "practice";
    document.getElementById('modalQuizTime').value = editingQuizSettings.timeLimit || "";
    document.getElementById('modalQuizShuffle').checked = editingQuizSettings.isShuffle || false;

    modal.style.display = 'flex';
}

function closePublishModal() {
    const modal = document.getElementById('publishModal');
    if (modal) modal.style.display = 'none';
}

async function confirmPublishQuiz() {
    const title = document.getElementById('modalQuizTitle').value.trim();
    if (!title) return alert("Vui lòng nhập tên bài kiểm tra!");

    if (!authToken) {
        alert("Vui lòng đăng nhập tài khoản Giáo viên để lưu và xuất bản đề thi!");
        window.location.href = "index.html";
        return;
    }

    const mode = document.getElementById('modalQuizMode').value;
    const timeLimit = parseInt(document.getElementById('modalQuizTime').value) || 0;
    const isShuffle = document.getElementById('modalQuizShuffle').checked;

    const btn = document.getElementById('btnConfirmPublish');
    btn.innerText = "⏳ Đang lưu đề thi...";
    btn.disabled = true;

    try {
        const payload = {
            title: title,
            data: currentData,
            mode: mode,
            time_limit: timeLimit,
            is_shuffle: isShuffle,
            creator_id: authToken,
            status: "published"
        };
        if (editingQuizId) payload.quiz_id = editingQuizId;

        const response = await fetch(`${API_BASE_URL}/api/save_quiz`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();

        if (result.status === 'success') {
            editingQuizId = result.quiz_id;
            window.isCurrentQuizPublished = true;
            window.draftImageKeys = [];
            sessionStorage.removeItem('editor_draft_images');
            sessionStorage.removeItem('editor_pending_task_id');
            editingQuizSettings = { title, mode, timeLimit, isShuffle };
            document.getElementById('studioQuizTitle').value = title;
            saveDraftToSession();

            closePublishModal();
            
            // Hiển thị nút Copy Link trên Studio navbar
            const btnCopy = document.getElementById('btnStudioCopyLink');
            if (btnCopy) btnCopy.style.display = 'inline-flex';
            const deleteLabel = document.getElementById('discardOrDeleteLabel');
            if (deleteLabel) deleteLabel.innerText = "Xóa đề";
            const btnDiscard = document.getElementById('btnDiscardOrDelete');
            if (btnDiscard) btnDiscard.title = "Xóa đề thi này khỏi hệ thống";

            showSuccessModal(result.quiz_id);
        } else {
            alert("Lỗi lưu đề thi: " + (result.detail || "Không rõ nguyên nhân"));
        }
    } catch(e) {
        console.error(e);
        alert("Lỗi khi kết nối với máy chủ!");
    } finally {
        btn.innerText = "🚀 Lưu & Xuất bản ngay";
        btn.disabled = false;
    }
}

function showSuccessModal(quizId) {
    const modal = document.getElementById('successModal');
    if (!modal) return;

    document.getElementById('successQuizCode').innerText = quizId;
    const origin = (window.location.origin && window.location.origin !== "null") ? window.location.origin : "";
    let path = window.location.pathname.replace('editor.html', 'index.html').replace(/\/editor\/?$/, '/index.html');
    if (!path.includes('index.html')) path = path.replace(/\/+$/, '') + '/index.html';
    const fullShareUrl = `${origin}${path}?id=${quizId}`;
    
    document.getElementById('successShareLink').value = fullShareUrl;
    modal.style.display = 'flex';
}

function closeSuccessModal() {
    const modal = document.getElementById('successModal');
    if (modal) modal.style.display = 'none';
}

function copyShareLink() {
    const input = document.getElementById('successShareLink');
    if (!input) return;
    input.select();
    navigator.clipboard.writeText(input.value);
    
    const copyBtn = document.getElementById('btnCopyShareLink');
    const origText = copyBtn.innerText;
    copyBtn.innerText = "✓ Đã copy!";
    copyBtn.style.background = "#10b981";
    setTimeout(() => {
        copyBtn.innerText = origText;
        copyBtn.style.background = "";
    }, 2000);
    showToast("Đã sao chép link chia sẻ!");
}

function copyCurrentStudioLink() {
    if (!editingQuizId) {
        alert("Đề thi này chưa được lưu hoặc xuất bản. Vui lòng bấm 'Lưu & Xuất bản' trước!");
        return;
    }
    const origin = (window.location.origin && window.location.origin !== "null") ? window.location.origin : "";
    let path = window.location.pathname.replace('editor.html', 'index.html').replace(/\/editor\/?$/, '/index.html');
    if (!path.includes('index.html')) path = path.replace(/\/+$/, '') + '/index.html';
    const fullShareUrl = `${origin}${path}?id=${editingQuizId}`;
    
    navigator.clipboard.writeText(fullShareUrl).then(() => {
        showToast("✓ Đã sao chép link đề thi!");
    }).catch(() => {
        prompt("Link làm bài của học sinh:", fullShareUrl);
    });
}

function openTestQuizLink() {
    const input = document.getElementById('successShareLink');
    if (input && input.value) {
        window.open(input.value, '_blank');
    }
}

// ----------------------------------------------------
// ĐIỀU HƯỚNG QUAY LẠI & DỌN DẸP DỮ LIỆU
// ----------------------------------------------------
function extractImageKeysFromClient(data) {
    if (!data) return [];
    try {
        const str = JSON.stringify(data);
        const matches = str.match(/(?:quizzes|temp)\/images\/[a-zA-Z0-9\-_.]+\.(?:png|jpg|jpeg|gif|webp|svg)/gi);
        return matches ? Array.from(new Set(matches)) : [];
    } catch(e) {
        return [];
    }
}

async function discardCurrentDraft() {
    try {
        const storedImages = JSON.parse(sessionStorage.getItem('editor_draft_images') || '[]');
        const currentImages = extractImageKeysFromClient(currentData);
        const allImages = Array.from(new Set([...(window.draftImageKeys || []), ...storedImages, ...currentImages]));
        
        await fetch(`${API_BASE_URL}/api/discard_draft`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ images: allImages, quiz_data: currentData })
        });
    } catch(e) {
        console.warn("Lỗi khi hủy draft:", e);
    } finally {
        sessionStorage.removeItem('editor_quiz_id');
        sessionStorage.removeItem('editor_quiz_data');
        sessionStorage.removeItem('editor_quiz_title');
        sessionStorage.removeItem('editor_quiz_settings');
        sessionStorage.removeItem('editor_draft_images');
        sessionStorage.removeItem('editor_pending_task_id');
        window.draftImageKeys = [];
        window.isCurrentQuizPublished = true;
    }
}

async function handleDiscardOrDelete() {
    if (editingQuizId) {
        const confirmDel = confirm(
            "🗑️ XÁC NHẬN XÓA ĐỀ THI:\n\n" +
            "Bạn có chắc chắn muốn đưa đề thi này vào Thùng rác không?\n" +
            "Học sinh sẽ không thể tiếp tục truy cập bài thi này."
        );
        if (!confirmDel) return;

        try {
            showToast("⏳ Đang chuyển đề thi vào thùng rác...");
            const res = await fetch(`${API_BASE_URL}/api/teacher/quiz_action`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ teacher_token: authToken, quiz_id: editingQuizId, action: 'trash' })
            });
            const data = await res.json();
            if (res.ok && data.status === 'success') {
                alert("Đã đưa đề thi vào thùng rác!");
                window.location.href = "index.html";
            } else {
                alert("Lỗi khi xóa: " + (data.detail || "Không thể xóa đề thi"));
            }
        } catch(e) {
            alert("Lỗi kết nối máy chủ");
        }
        return;
    }

    const confirmDiscard = confirm(
        "⚠️ XÁC NHẬN HỦY BỎ BẢN NHÁP:\n\n" +
        "Toàn bộ câu hỏi và hình ảnh vừa phân tích sẽ bị XÓA VĨNH VIỄN khỏi hệ thống (Database và Cloudflare R2).\n" +
        "Hành động này giúp giải phóng hoàn toàn dung lượng lưu trữ.\n\n" +
        "Bạn có chắc chắn muốn hủy bỏ không?"
    );
    if (!confirmDiscard) return;

    showToast("⏳ Đang dọn sạch dữ liệu và hình ảnh tạm thời...");
    await discardCurrentDraft();
    window.location.href = "index.html";
}

async function handleDiscardAndExit() {
    return handleDiscardOrDelete();
}

async function handleBackToDashboard() {
    // Nếu là đề thi mới tải lên chưa xuất bản vào cơ sở dữ liệu
    if (!editingQuizId && !window.isCurrentQuizPublished && currentData && currentData.length > 0) {
        const confirmExit = confirm(
            "⚠️ BẠN CHƯA XUẤT BẢN ĐỀ THI!\n\n" +
            "Nếu quay lại bây giờ mà không xuất bản, toàn bộ câu hỏi và hình ảnh tạm thời sẽ được HỦY BỎ HOÀN TOÀN để tránh làm đầy dữ liệu hệ thống (Database và Cloudflare R2).\n\n" +
            "• Chọn [OK]: Hủy đề & dọn sạch dung lượng để về trang chủ.\n" +
            "• Chọn [Cancel]: Ở lại Studio để tiếp tục chỉnh sửa hoặc xuất bản."
        );
        if (!confirmExit) return;

        showToast("⏳ Đang dọn sạch dữ liệu tạm thời...");
        await discardCurrentDraft();
        window.location.href = "index.html";
        return;
    }
    
    window.location.href = "index.html";
}

// Tự động dọn dẹp R2 nếu người dùng đóng tab / tắt trình duyệt khi chưa xuất bản
window.addEventListener('beforeunload', () => {
    if (!editingQuizId && !window.isCurrentQuizPublished && currentData && currentData.length > 0) {
        const storedImages = JSON.parse(sessionStorage.getItem('editor_draft_images') || '[]');
        const currentImages = extractImageKeysFromClient(currentData);
        const allImages = Array.from(new Set([...(window.draftImageKeys || []), ...storedImages, ...currentImages]));
        if (allImages.length > 0) {
            const payload = JSON.stringify({ images: allImages, quiz_data: currentData });
            const blob = new Blob([payload], { type: 'application/json' });
            navigator.sendBeacon(`${API_BASE_URL}/api/discard_draft`, blob);
        }
    }
});

// ----------------------------------------------------
// TIỆN ÍCH HIỂN THỊ THÔNG BÁO (TOAST)
// ----------------------------------------------------
function showToast(message) {
    const toast = document.getElementById('studioToast');
    if (!toast) return;
    toast.innerText = message;
    toast.style.display = 'block';
    
    setTimeout(() => {
        toast.style.display = 'none';
    }, 2500);
}

function escapeHtml(text) {
    if (!text) return "";
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
