// ========================================================
// HOCNHANHTN EDITOR STUDIO - JAVASCRIPT CONTROLLER
// ========================================================

// Tự động nhận diện môi trường (Localhost vs Production)
let API_BASE_URL = "https://inland-marylin-hocnhanhtn-c3471a95.koyeb.app";
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.protocol === 'file:') {
    API_BASE_URL = "http://127.0.0.1:8000";
} else if (window.location.hostname.startsWith('192.168.')) {
    API_BASE_URL = `http://${window.location.hostname}:8000`;
}

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
        alert("Vui lòng đăng nhập để sử dụng Studio Biên tập Đề thi!");
        window.location.href = "index.html";
        return;
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

async function pollStudioTask(taskId, initialTitle, mode) {
    const overlay = document.getElementById('studioLoadingOverlay');
    const progressBar = document.getElementById('studioProgressBar');
    const progressPercent = document.getElementById('studioProgressPercent');
    const statusTitle = document.getElementById('studioLoadingStatus');
    const statusSub = document.getElementById('studioLoadingSub');

    if (overlay) overlay.style.display = 'flex';
    
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
    const progressInterval = setInterval(() => {
        if (progress < 90) {
            progress += Math.random() * 2;
            if (progressBar) progressBar.style.width = Math.min(progress, 90) + '%';
            if (progressPercent) progressPercent.innerText = Math.floor(Math.min(progress, 90)) + '%';
        }
    }, 700);

    const poll = async () => {
        try {
            const statusRes = await fetch(`${API_BASE_URL}/api/task_status/${taskId}`);
            const statusData = await statusRes.json();

            if (statusData.status === "success") {
                clearInterval(progressInterval);
                if (progressBar) progressBar.style.width = '100%';
                if (progressPercent) progressPercent.innerText = '100%';
                if (statusTitle) statusTitle.innerText = '✅ Phân tích hoàn tất!';
                
                await new Promise(r => setTimeout(r, 500));
                
                // Xóa task ID đã xử lý
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
            } else if (statusRes.status === 404) {
                clearInterval(progressInterval);
                sessionStorage.removeItem('editor_pending_task_id');
                sessionStorage.removeItem('editor_pending_mode');
                if (overlay) overlay.style.display = 'none';
                loadQuizFromSession();
            } else {
                // Vẫn đang xử lý
                if (statusData.message && statusTitle) {
                    statusTitle.innerText = "🤖 " + statusData.message;
                }
                setTimeout(poll, 2500);
            }
        } catch(err) {
            // Lỗi mạng tạm thời, thử lại sau 4s
            setTimeout(poll, 4000);
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
        jsonStr = jsonStr.replace(/https:\/\/pub-4ca74ee0e22a46a39755d1a829865251\.r2\.dev\//g, '/api/images/');
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
function setupEditorEvents() {
    const codeEditor = document.getElementById('codeEditor');
    const codeHighlight = document.getElementById('codeHighlight');
    if (!codeEditor) return;

    let editTimeout;
    codeEditor.addEventListener('input', function() {
        const indicator = document.getElementById('autosaveIndicator');
        if (indicator) indicator.innerText = "⏳ Đang gõ...";

        clearTimeout(editTimeout);
        editTimeout = setTimeout(() => {
            updateSyntaxHighlight();
            currentData = parseEditorText(codeEditor.value);
            renderPreviewAll();
            updateQCountBadge();
            saveDraftToSession();
        }, 300);
    });

    codeEditor.addEventListener('scroll', function() {
        if (codeHighlight) {
            codeHighlight.scrollTop = this.scrollTop;
            codeHighlight.scrollLeft = this.scrollLeft;
        }
    });

    // Auto-complete bằng phím Tab
    codeEditor.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
            e.preventDefault();
            const start = this.selectionStart;
            const end = this.selectionEnd;

            if (start === end) {
                const textBefore = this.value.substring(0, start);
                const cauMatch = textBefore.match(/(?:^|\n)\s*(?:cau|câu)\s*$/i);
                
                if (cauMatch) {
                    const matchedLen = cauMatch[0].length;
                    const replaceStart = start - matchedLen;
                    const qIndex = currentData.length + 1;
                    const template = `\n\nCâu ${qIndex}: \n*A. \nB. \nC. \nD. `;
                    
                    this.value = this.value.substring(0, replaceStart) + template + this.value.substring(end);
                    const newCursorPos = replaceStart + template.indexOf('\n*A.');
                    this.selectionStart = this.selectionEnd = newCursorPos;
                    
                    updateSyntaxHighlight();
                    currentData = parseEditorText(this.value);
                    renderPreviewAll();
                    updateQCountBadge();
                    saveDraftToSession();
                    return;
                }
            }

            // Chèn 4 khoảng trắng nếu không phải từ khóa
            const spaces = "    ";
            this.value = this.value.substring(0, start) + spaces + this.value.substring(end);
            this.selectionStart = this.selectionEnd = start + spaces.length;
            updateSyntaxHighlight();
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
        codeEditor.value = dataToEditorText(currentData);
        updateSyntaxHighlight();
    }
}

// ----------------------------------------------------
// CHUYỂN ĐỔI GIỮA DỮ LIỆU JSON VÀ TEXT CODE
// ----------------------------------------------------
function dataToEditorText(data) {
    let text = "";
    data.forEach((q, i) => {
        if (q.group_title && (i === 0 || q.group_title !== data[i-1].group_title)) {
            text += `${q.group_title.replace(/<br>/gi, '\n')}\n`;
        }
        let qClean = q.question.replace(/^(?:(?:Câu|Bài|Question|Q)\s*\d+\s*[\.\:\-\)]|\d+\s*[\.\:\)])\s*/i, '').replace(/<br>/gi, '\n');
        text += `Câu ${i + 1}: ${qClean}\n`;
        
        q.options.forEach((opt) => {
            let isCorrect = (q.correct_answer === opt);
            let optText = opt.replace(/<br>/gi, '\n');
            if (isCorrect) {
                optText = optText.replace(/^([A-F])([\.\:\)])/i, '*$1$2');
            }
            text += `${optText}\n`;
        });
        text += "\n";
    });
    
    text = text.trim();
    
    // Nén thẻ ảnh vào placeholder [HÌNH_ẢNH_X]
    globalEditorImageStorage = {};
    globalEditorImageCounter = 0;
    
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
    let restoredText = text;
    for (let key in globalEditorImageStorage) {
        restoredText = restoredText.split(key).join(globalEditorImageStorage[key]);
    }
    
    const data = [];
    let currentQ = null;
    const lines = restoredText.split('\n');
    let sharedContext = "";

    const qRegex = /^\s*(Câu|Bài|Question|Q)\s*\d+[\.\:\-\)]/i;
    const optRegex = /^\s*(\*?\s*[A-F])[\.\:\)]/i;
    const groupRegex = /^\s*(PHẦN|PART|CHƯƠNG|BÀI TẬP|I{1,3}\.|IV\.|V\.|VI{0,3}\.)\b/i;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();
        
        if (trimmed === '') continue;

        if (qRegex.test(line)) {
            if (currentQ) data.push(currentQ);
            let qText = line.replace(qRegex, '').trim();
            currentQ = { group_title: sharedContext.trim(), question: qText, options: [], correct_answer: null };
            sharedContext = ""; 
        } else if (optRegex.test(line)) {
            const match = line.match(optRegex);
            const charRaw = match[1].trim().toUpperCase();
            const isCorrect = charRaw.includes('*');
            const char = charRaw.replace('*', '').trim();
            let optContent = line.replace(optRegex, '').trim();
            
            const fullOpt = `${char}. ${optContent}`;
            if (currentQ) {
                currentQ.options.push(fullOpt);
                if (isCorrect) currentQ.correct_answer = fullOpt;
            }
        } else if (groupRegex.test(line)) {
            sharedContext += (sharedContext ? "<br>" : "") + line;
        } else {
            if (currentQ && currentQ.options.length > 0) {
                currentQ.options[currentQ.options.length - 1] += "<br>" + line;
            } else if (currentQ) {
                currentQ.question += (currentQ.question ? "<br>" : "") + line;
            } else {
                sharedContext += (sharedContext ? "<br>" : "") + line;
            }
        }
    }
    if (currentQ) data.push(currentQ);
    
    // Nếu chưa đánh dấu đáp án đúng, mặc định lấy đáp án A
    data.forEach(q => {
        if (!q.correct_answer && q.options.length > 0) {
            q.correct_answer = q.options[0];
        }
    });
    return data;
}

// ----------------------------------------------------
// SYNTAX HIGHLIGHTING (MÀU SẮC CHUẨN VS CODE)
// ----------------------------------------------------
function updateSyntaxHighlight() {
    const codeEditor = document.getElementById('codeEditor');
    const codeHighlight = document.getElementById('codeHighlight');
    if (!codeEditor || !codeHighlight) return;
    
    let text = codeEditor.value;
    let escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    
    escaped = escaped.replace(/(\[HÌNH_ẢNH_\d+\])/g, '<span class="hl-image">$1</span>');
    escaped = escaped.replace(/(\\\([\s\S]*?\\\))/g, '<span class="hl-math">$1</span>');
    escaped = escaped.replace(/^(\s*)(Câu|Bài|Question|Q)(\s*\d+[\.\:\-\)])/gim, '$1<span class="hl-question">$2$3</span>');
    escaped = escaped.replace(/^(\s*)(\*\s*[A-F][\.\:\)])/gim, '$1<span class="hl-correct">$2</span>');
    escaped = escaped.replace(/^(\s*)([A-F][\.\:\)])/gim, '$1<span class="hl-option">$2</span>');
    escaped = escaped.replace(/^(\s*)(PHẦN|PART|CHƯƠNG|BÀI TẬP|I{1,3}\.|IV\.|V\.|VI{0,3}\.)(.*)$/gim, '$1<span class="hl-group">$2$3</span>');
    escaped = escaped.replace(/(&lt;\/?(b|i|u|sub|sup|MARK)&gt;)/gi, '<span class="hl-html">$1</span>');
    
    if (escaped.endsWith('\n')) escaped += ' ';
    codeHighlight.innerHTML = escaped;
}

// ----------------------------------------------------
// BỘ CHUẨN HÓA CHỈ SỐ DƯỚI (HÓA HỌC / TOÁN HỌC) CHO GIAO DIỆN
// ----------------------------------------------------
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
        let qClean = q.question.replace(/^(?:(?:Câu|Bài|Question|Q)\s*\d+\s*[\.\:\-\)]|\d+\s*[\.\:\)])\s*/i, '');
        let formattedQ = formatSubscriptsAndFormulas(qClean).replace(/(?:\r\n|\r|\n|\\n)/g, '<br>');
        
        html += `${groupTitleHtml}<div class="question-title" style="font-size: 1.05rem; font-weight: 700; margin-bottom: 12px;">Câu ${qIndex + 1}: ${formattedQ}</div>`;
        
        q.options.forEach((opt, oIndex) => {
            let isCorrect = q.correct_answer === opt;
            let optClean = formatSubscriptsAndFormulas(opt.replace(/^[A-F][\.\:\)]\s*/i, ''));
            html += `<label class="option-practice ${isCorrect ? 'correct selected' : ''}" style="cursor: default; padding: 10px 14px; margin-bottom: 8px;">
                        <input type="radio" disabled ${isCorrect ? 'checked' : ''}>
                        <span class="opt-badge">${opt.match(/^[A-F]/i) ? opt.match(/^[A-F]/i)[0].toUpperCase() : String.fromCharCode(65 + oIndex)}</span>
                        <span class="opt-text">${optClean}</span>
                    </label>`;
        });
        prevBox.innerHTML = html;
        
        // Chèn thẻ AI gợi ý sửa lỗi nếu có
        if (hasError) {
            const aiData = window.activeAIFeedbacks[qIndex];
            const catClass = aiData.category === 'knowledge' ? 'ai-cat-knowledge' :
                             (aiData.category === 'answer' ? 'ai-cat-answer' :
                             (aiData.category === 'grammar_typo' ? 'ai-cat-grammar' : 'ai-cat-format'));

            const aiDiv = document.createElement('div');
            aiDiv.style.cssText = 'margin-top: 14px; padding: 14px; background: #faf5ff; border: 1.5px solid #d8b4fe; border-radius: 10px; cursor: default;';
            aiDiv.onclick = (e) => e.stopPropagation();
            
            let corrected = aiData.corrected_data || {};
            let correctedAnswerText = corrected.correct_answer || '';
            let explainText = corrected.explain ? `<div style="margin-top: 6px; font-size: 0.88rem; color: #475569;"><b>💡 Giải thích:</b> ${corrected.explain}</div>` : '';

            aiDiv.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <i class="ri-sparkling-fill" style="color: #9333ea; font-size: 1.15rem;"></i>
                        <strong style="color: #9333ea;">AI Phát hiện vấn đề:</strong>
                        <span class="ai-cat-chip ${catClass}" style="padding: 2px 8px; font-size: 0.75rem;">${aiData.category_name || 'Cần sửa'}</span>
                    </div>
                </div>
                <div style="color: #dc2626; font-size: 0.92rem; font-weight: 600; margin-bottom: 8px;">
                    ${aiData.reason}
                </div>
                ${correctedAnswerText ? `<div style="font-size: 0.88rem; background: #f0fdf4; padding: 6px 10px; border-radius: 6px; border: 1px solid #bbf7d0; color: #166534; margin-bottom: 8px;">
                    <i class="ri-checkbox-circle-line" style="vertical-align: middle;"></i> <b>Đề xuất đáp án đúng:</b> ${escapeHtml(correctedAnswerText)}
                </div>` : ''}
                ${explainText}
                <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
                    <button class="btn-primary" style="padding: 6px 14px; font-size: 0.85rem; background: #9333ea; border: none; border-radius: 6px;" onclick="applyAISuggestion(${qIndex})">
                        <i class="ri-magic-line"></i> Tự động sửa câu này
                    </button>
                    <button class="btn-outline" style="padding: 6px 12px; font-size: 0.85rem; border-color: #d8b4fe; color: #9333ea; border-radius: 6px;" onclick="dismissAISuggestion(${qIndex})">
                        <i class="ri-close-line"></i> Bỏ qua
                    </button>
                </div>
            `;
            prevBox.appendChild(aiDiv);
        }
        
        previewContent.appendChild(prevBox);
    });

    renderMathJax(previewContent);
}

function scrollToQuestionInEditor(qIndex) {
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
                    
                    const scrollRatio = charOffset / text.length;
                    const targetScroll = editor.scrollHeight * scrollRatio;
                    editor.scrollTop = targetScroll - 50;
                    return;
                }
            }
        }
        charOffset += line.length + 1;
    }
}

function insertQuestionTemplate() {
    const editor = document.getElementById('codeEditor');
    if (!editor) return;
    
    const nextQNum = currentData.length + 1;
    const template = `\n\nCâu ${nextQNum}: Nội dung câu hỏi mới ở đây?\n*A. Đáp án đúng thứ nhất\nB. Đáp án thứ hai\nC. Đáp án thứ ba\nD. Đáp án thứ tư\n`;
    
    editor.value += template;
    editor.scrollTop = editor.scrollHeight;
    editor.focus();
    
    updateSyntaxHighlight();
    currentData = parseEditorText(editor.value);
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
            const contentContainer = document.getElementById('aiFeedbackContent');
            const btnApplyAll = document.getElementById('btnApplyAllAI');

            window.activeAIFeedbacks = {};

            if (Array.isArray(data.feedback) && data.feedback.length > 0) {
                data.feedback.forEach(item => {
                    window.activeAIFeedbacks[item.question_index] = item;
                });

                const stats = data.stats || {
                    total_questions: currentData.length,
                    valid_questions: currentData.length - data.feedback.length,
                    error_count: data.feedback.length,
                    accuracy_rate: Math.round(((currentData.length - data.feedback.length) / currentData.length) * 100),
                    category_counts: { knowledge: 0, answer: 0, grammar_typo: 0, format: 0 }
                };

                let statsHtml = `
                    <div class="ai-stat-grid">
                        <div class="ai-stat-card">
                            <span class="ai-stat-label">Tổng số câu hỏi</span>
                            <span class="ai-stat-val" style="color: #2563eb;">${stats.total_questions}</span>
                        </div>
                        <div class="ai-stat-card">
                            <span class="ai-stat-label">Câu đạt chuẩn 100%</span>
                            <span class="ai-stat-val" style="color: #10b981;">${stats.valid_questions}</span>
                        </div>
                        <div class="ai-stat-card">
                            <span class="ai-stat-label">Phát hiện cần sửa</span>
                            <span class="ai-stat-val" style="color: #ef4444;">${stats.error_count}</span>
                        </div>
                        <div class="ai-stat-card">
                            <span class="ai-stat-label">Tỷ lệ chính xác</span>
                            <span class="ai-stat-val" style="color: #9333ea;">${stats.accuracy_rate}%</span>
                        </div>
                    </div>

                    <div class="ai-cat-chips">
                        <span class="ai-cat-chip ai-cat-knowledge"><i class="ri-brain-line"></i> Kiến thức: <b>${stats.category_counts?.knowledge || 0}</b></span>
                        <span class="ai-cat-chip ai-cat-answer"><i class="ri-close-circle-line"></i> Đáp án: <b>${stats.category_counts?.answer || 0}</b></span>
                        <span class="ai-cat-chip ai-cat-grammar"><i class="ri-spell-check-line"></i> Chính tả / Diễn đạt: <b>${stats.category_counts?.grammar_typo || 0}</b></span>
                        <span class="ai-cat-chip ai-cat-format"><i class="ri-ruler-line"></i> Định dạng: <b>${stats.category_counts?.format || 0}</b></span>
                    </div>
                `;
                statsContainer.innerHTML = statsHtml;

                let errorListHtml = `
                    <h4 style="margin: 15px 0 10px 0; color: #475569; font-size: 0.95rem; text-transform: uppercase;">
                        <i class="ri-list-check-2" style="color: #9333ea;"></i> Danh sách các câu phát hiện vấn đề:
                    </h4>
                    <div class="ai-error-list-container">
                `;

                data.feedback.forEach(item => {
                    const qIdx = item.question_index;
                    const catClass = item.category === 'knowledge' ? 'ai-cat-knowledge' :
                                     (item.category === 'answer' ? 'ai-cat-answer' :
                                     (item.category === 'grammar_typo' ? 'ai-cat-grammar' : 'ai-cat-format'));

                    errorListHtml += `
                        <div class="ai-error-item" id="ai_summary_item_${qIdx}">
                            <div style="flex: 1; min-width: 260px;">
                                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                                    <span style="font-weight: 800; color: #6b21a8; font-size: 1rem;">Câu ${qIdx + 1}</span>
                                    <span class="ai-cat-chip ${catClass}" style="padding: 2px 8px; font-size: 0.75rem;">${item.category_name || 'Lỗi'}</span>
                                </div>
                                <div style="font-size: 0.9rem; color: #475569;">${item.reason}</div>
                            </div>
                            <div style="display: flex; gap: 8px; align-items: center;">
                                <button class="btn-studio-outline" style="padding: 6px 12px; font-size: 0.85rem;" onclick="jumpToQuestionCard(${qIdx})"><i class="ri-focus-2-line"></i> Tới Câu ${qIdx + 1}</button>
                                <button class="btn-studio-primary" style="padding: 6px 12px; font-size: 0.85rem; background: #9333ea;" onclick="applyAISuggestion(${qIdx})"><i class="ri-magic-line"></i> Sửa câu này</button>
                            </div>
                        </div>
                    `;
                });
                errorListHtml += `</div>`;
                contentContainer.innerHTML = errorListHtml;

                if (btnApplyAll) btnApplyAll.style.display = 'inline-block';
                renderPreviewAll();
            } else if (Array.isArray(data.feedback) && data.feedback.length === 0) {
                statsContainer.innerHTML = `
                    <div style="text-align: center; padding: 25px 10px;">
                        <div style="font-size: 3rem; color: #10b981; margin-bottom: 10px;"><i class="ri-checkbox-circle-fill"></i></div>
                        <h3 style="margin: 0; color: #059669;">Tuyệt vời! Đề thi đạt chuẩn 100% không phát hiện lỗi!</h3>
                        <p style="margin: 6px 0 0 0; color: #64748b;">Toàn bộ câu hỏi, đáp án và định dạng đều hoàn hảo và sẵn sàng xuất bản.</p>
                    </div>
                `;
                contentContainer.innerHTML = '';
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
    if (!confirm(`Bạn có chắc muốn tự động sửa toàn bộ ${count} câu lỗi theo đề xuất của AI?`)) return;

    for (let qIndexStr in window.activeAIFeedbacks) {
        const qIndex = parseInt(qIndexStr);
        const aiData = window.activeAIFeedbacks[qIndex];
        if (aiData && currentData[qIndex]) {
            const corrected = aiData.corrected_data;
            const origGroup = currentData[qIndex].group_title;
            currentData[qIndex] = {
                ...corrected,
                group_title: corrected.group_title !== undefined ? corrected.group_title : origGroup
            };
        }
    }

    window.activeAIFeedbacks = {};
    syncDataToEditor();
    renderPreviewAll();
    saveDraftToSession();

    const btnApplyAll = document.getElementById('btnApplyAllAI');
    if (btnApplyAll) btnApplyAll.style.display = 'none';

    document.getElementById('aiFeedbackStats').innerHTML = `
        <div style="text-align: center; padding: 20px 10px;">
            <div style="font-size: 2.5rem; color: #9333ea; margin-bottom: 8px;"><i class="ri-sparkling-fill"></i></div>
            <h3 style="margin: 0; color: #9333ea;">Đã tự động sửa thành công tất cả ${count} câu hỏi!</h3>
            <p style="margin: 4px 0 0 0; color: #64748b;">Dữ liệu đề thi và trình soạn thảo Code đã được cập nhật hoàn tất.</p>
        </div>
    `;
    document.getElementById('aiFeedbackContent').innerHTML = '';
    showToast(`Đã sửa tự động ${count} câu!`);
}

function applyAISuggestion(question_index) {
    const aiData = window.activeAIFeedbacks[question_index];
    if (!aiData) return;

    const corrected = aiData.corrected_data;
    const origGroup = currentData[question_index] ? currentData[question_index].group_title : "";
    
    currentData[question_index] = {
        ...corrected,
        group_title: corrected.group_title !== undefined ? corrected.group_title : origGroup
    };

    delete window.activeAIFeedbacks[question_index];

    syncDataToEditor();
    renderPreviewAll();
    saveDraftToSession();

    const summaryItem = document.getElementById(`ai_summary_item_${question_index}`);
    if (summaryItem) summaryItem.remove();

    showToast(`Đã sửa xong Câu ${question_index + 1}!`);
}

function dismissAISuggestion(question_index) {
    delete window.activeAIFeedbacks[question_index];
    renderPreviewAll();
    const summaryItem = document.getElementById(`ai_summary_item_${question_index}`);
    if (summaryItem) summaryItem.remove();
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

    if (mode === 'edit') {
        splitView.style.display = 'flex';
        testView.style.display = 'none';
        renderPreviewAll();
    } else {
        splitView.style.display = 'none';
        testView.style.display = 'block';
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
        let qClean = q.question.replace(/^(?:(?:Câu|Bài|Question|Q)\s*\d+\s*[\.\:\-\)]|\d+\s*[\.\:\)])\s*/i, '');
        let formattedQ = formatSubscriptsAndFormulas(qClean).replace(/(?:\r\n|\r|\n|\\n)/g, '<br>');

        html += `
            <div class="question-box" id="test_q_box_${qIndex}" style="background: white; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: var(--shadow); border: 1px solid var(--border);">
                ${groupTitleHtml}
                <div class="question-title" style="font-size: 1.1rem; font-weight: 700; margin-bottom: 15px;">
                    Câu ${qIndex + 1}: ${formattedQ}
                </div>
                <div class="options-container">
        `;

        q.options.forEach((opt, oIndex) => {
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

        html += `</div></div>`;
    });

    container.innerHTML = html;

    renderMathJax(container);
}

function handleTestPracticeSelect(qIndex, oIndex) {
    if (testPracticeAnswers[qIndex] !== undefined) return;
    testPracticeAnswers[qIndex] = oIndex;

    const q = currentData[qIndex];
    const selectedOpt = q.options[oIndex];
    const isCorrect = (selectedOpt === q.correct_answer);

    const clickedEl = document.getElementById(`test_opt_${qIndex}_${oIndex}`);
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

function handleTestExamSelect(qIndex, oIndex) {
    testExamAnswers[qIndex] = oIndex;
}

function handleTestExamSubmit() {
    let correctCount = 0;
    currentData.forEach((q, qIndex) => {
        const chosenIdx = testExamAnswers[qIndex];
        if (chosenIdx !== undefined && q.options[chosenIdx] === q.correct_answer) {
            correctCount++;
        }
    });

    const score = ((correctCount / currentData.length) * 10).toFixed(1);
    alert(`🎉 KẾT QUẢ THI THỬ:\n\n- Đúng: ${correctCount} / ${currentData.length} câu\n- Điểm số: ${score} / 10`);
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
