/**
 * HocNhanhTN - Export Studio Core Logic
 * Tự động đồng bộ và xem trước thời gian thực tài liệu A4 trước khi tải Word/PDF.
 */

(function () {
    'use strict';

    // 1. Cấu hình Backend & Xác thực
    const PROD_BACKEND_URL = "https://inland-marylin-hocnhanhtn-c3471a95.koyeb.app";
    let API_BASE_URL = PROD_BACKEND_URL;
    const currentHost = window.location.hostname || "";
    const isLocal = window.location.protocol === "file:" ||
        currentHost === "localhost" ||
        currentHost === "127.0.0.1" ||
        currentHost.startsWith("192.168.") ||
        currentHost.startsWith("10.") ||
        currentHost.endsWith(".local");

    if (isLocal) {
        API_BASE_URL = (window.location.port === "8000") ? window.location.origin : "http://127.0.0.1:8000";
    } else if (currentHost.includes("koyeb.app") || currentHost.includes("ngrok")) {
        API_BASE_URL = window.location.origin;
    }

    const authToken = localStorage.getItem('teacher_token') || localStorage.getItem('access_token') || '';

    // 2. Trạng thái dữ liệu đề thi & Tùy chọn xuất bản
    let quizData = {
        id: null,
        title: "ĐỀ CƯƠNG ÔN TẬP TRẮC NGHIỆM",
        time_limit: 45,
        school_name: "SỞ GIÁO DỤC VÀ ĐÀO TẠO",
        questions: []
    };

    let exportConfig = {
        target_audience: 'teacher',   // 'teacher' | 'student'
        layout_mode: 'compact',       // 'compact' | 'standard'
        options_layout: 'auto',       // 'auto' | '1' | '2' | '4'
        show_answers: true,
        show_key_table: true,
        show_explains: true,
        include_student_grid: false,
        show_candidate_info: true,
        school_name: "SỞ GIÁO DỤC VÀ ĐÀO TẠO",
        exam_title: "",
        time_limit: 45
    };

    let zoomLevel = 1.0;
    let mathJaxPending = false;
    let debounceTimer = null;

    // 3. Khởi tạo khi DOM tải xong
    document.addEventListener('DOMContentLoaded', () => {
        initUrlParams();
        bindEvents();
        loadQuizData();
    });

    function initUrlParams() {
        const pathParts = window.location.pathname.split('/').filter(Boolean);
        let idFromPath = null;
        if (pathParts[0] === 'export' && pathParts[1]) {
            idFromPath = decodeURIComponent(pathParts[1]);
        }
        const urlParams = new URLSearchParams(window.location.search);
        const idFromQuery = urlParams.get('id') || urlParams.get('quiz_id');
        quizData.id = idFromPath || idFromQuery || null;

        // Đọc các tham số cấu hình nếu truyền qua URL
        if (urlParams.get('audience') === 'student') {
            exportConfig.target_audience = 'student';
            exportConfig.show_answers = false;
            exportConfig.show_key_table = false;
            exportConfig.show_explains = false;
        }
        if (urlParams.get('layout') === 'standard') {
            exportConfig.layout_mode = 'standard';
        }
        if (urlParams.get('options')) {
            exportConfig.options_layout = urlParams.get('options');
        }
    }

    function bindEvents() {
        // Audience Radio Cards
        document.querySelectorAll('input[name="targetAudience"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                setAudience(e.target.value);
            });
        });

        // Layout Radio Cards
        document.querySelectorAll('input[name="layoutMode"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                setLayoutMode(e.target.value);
            });
        });

        // Options Layout Pills
        document.querySelectorAll('.pill-opt').forEach(pill => {
            pill.addEventListener('click', () => {
                document.querySelectorAll('.pill-opt').forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                exportConfig.options_layout = pill.dataset.val;
                renderPreview();
            });
        });

        // Checkbox Toggles
        const chkAnswers = document.getElementById('chkShowAnswers');
        if (chkAnswers) {
            chkAnswers.addEventListener('change', (e) => {
                exportConfig.show_answers = e.target.checked;
                renderPreview();
            });
        }

        const chkKey = document.getElementById('chkShowKeyTable');
        if (chkKey) {
            chkKey.addEventListener('change', (e) => {
                exportConfig.show_key_table = e.target.checked;
                renderPreview();
            });
        }

        const chkExp = document.getElementById('chkShowExplains');
        if (chkExp) {
            chkExp.addEventListener('change', (e) => {
                exportConfig.show_explains = e.target.checked;
                renderPreview();
            });
        }

        const chkGrid = document.getElementById('chkStudentGrid');
        if (chkGrid) {
            chkGrid.addEventListener('change', (e) => {
                exportConfig.include_student_grid = e.target.checked;
                renderPreview();
            });
        }

        const chkCand = document.getElementById('chkCandidateInfo');
        if (chkCand) {
            chkCand.addEventListener('change', (e) => {
                exportConfig.show_candidate_info = e.target.checked;
                renderPreview();
            });
        }

        // Header Metadata Inputs
        const inputSchool = document.getElementById('inputSchoolName');
        if (inputSchool) {
            inputSchool.addEventListener('input', (e) => {
                exportConfig.school_name = e.target.value;
                debouncedRender();
            });
        }

        const inputTitle = document.getElementById('inputExamTitle');
        if (inputTitle) {
            inputTitle.addEventListener('input', (e) => {
                exportConfig.exam_title = e.target.value;
                document.getElementById('navDocTitle').textContent = e.target.value || "Đề thi trắc nghiệm";
                debouncedRender();
            });
        }

        const inputTime = document.getElementById('inputTimeLimit');
        if (inputTime) {
            inputTime.addEventListener('input', (e) => {
                exportConfig.time_limit = parseInt(e.target.value, 10) || 0;
                debouncedRender();
            });
        }

        // Zoom Controls
        const btnZoomIn = document.getElementById('btnZoomIn');
        if (btnZoomIn) btnZoomIn.addEventListener('click', () => adjustZoom(0.1));

        const btnZoomOut = document.getElementById('btnZoomOut');
        if (btnZoomOut) btnZoomOut.addEventListener('click', () => adjustZoom(-0.1));

        const btnZoomReset = document.getElementById('btnZoomReset');
        if (btnZoomReset) btnZoomReset.addEventListener('click', () => setZoom(1.0));

        const btnZoomFit = document.getElementById('btnZoomFit');
        if (btnZoomFit) btnZoomFit.addEventListener('click', fitToWidth);

        // Download Actions
        const btnDocx = document.getElementById('btnDownloadDocx');
        if (btnDocx) btnDocx.addEventListener('click', handleDownloadDocx);

        const btnPdf = document.getElementById('btnPrintPdf');
        if (btnPdf) btnPdf.addEventListener('click', handlePrintPdf);
    }

    function setAudience(audience) {
        exportConfig.target_audience = audience;
        const cardTeacher = document.getElementById('cardAudienceTeacher');
        const cardStudent = document.getElementById('cardAudienceStudent');
        const chkAnswers = document.getElementById('chkShowAnswers');
        const chkKey = document.getElementById('chkShowKeyTable');
        const chkExp = document.getElementById('chkShowExplains');
        const rowGrid = document.getElementById('rowStudentGrid');

        if (audience === 'student') {
            if (cardStudent) cardStudent.classList.add('active');
            if (cardTeacher) cardTeacher.classList.remove('active');

            if (chkAnswers) { chkAnswers.checked = false; chkAnswers.disabled = true; }
            if (chkKey) { chkKey.checked = false; chkKey.disabled = true; }
            if (chkExp) { chkExp.checked = false; chkExp.disabled = true; }
            if (rowGrid) rowGrid.style.display = 'flex';

            exportConfig.show_answers = false;
            exportConfig.show_key_table = false;
            exportConfig.show_explains = false;
        } else {
            if (cardTeacher) cardTeacher.classList.add('active');
            if (cardStudent) cardStudent.classList.remove('active');

            if (chkAnswers) { chkAnswers.checked = true; chkAnswers.disabled = false; }
            if (chkKey) { chkKey.checked = true; chkKey.disabled = false; }
            if (chkExp) { chkExp.checked = true; chkExp.disabled = false; }
            if (rowGrid) rowGrid.style.display = 'none';

            exportConfig.show_answers = true;
            exportConfig.show_key_table = true;
            exportConfig.show_explains = true;
        }
        renderPreview();
    }

    function setLayoutMode(mode) {
        exportConfig.layout_mode = mode;
        const cardCompact = document.getElementById('cardLayoutCompact');
        const cardStandard = document.getElementById('cardLayoutStandard');
        const sheet = document.getElementById('a4Sheet');

        if (mode === 'standard') {
            if (cardStandard) cardStandard.classList.add('active');
            if (cardCompact) cardCompact.classList.remove('active');
            if (sheet) {
                sheet.classList.remove('mode-compact');
                sheet.classList.add('mode-standard');
            }
        } else {
            if (cardCompact) cardCompact.classList.add('active');
            if (cardStandard) cardStandard.classList.remove('active');
            if (sheet) {
                sheet.classList.remove('mode-standard');
                sheet.classList.add('mode-compact');
            }
        }
        renderPreview();
    }

    function debouncedRender() {
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            renderPreview();
        }, 120);
    }

    async function loadQuizData() {
        showLoadingState(true);

        // 1. Kiểm tra dữ liệu được truyền qua sessionStorage (từ Editor hoặc Danh sách)
        if (quizData.id) {
            const cached = sessionStorage.getItem(`export_quiz_${quizData.id}`) || localStorage.getItem(`export_quiz_${quizData.id}`);
            if (cached) {
                try {
                    const parsed = JSON.parse(cached);
                    applyLoadedQuiz(parsed);
                    showLoadingState(false);
                } catch (e) {
                    console.warn("Parse cache error:", e);
                }
            }
        }

        // 2. Kiểm tra dữ liệu tạm 'export_quiz_data' nếu người dùng vừa bấm xuất từ Editor
        const transientData = sessionStorage.getItem('export_quiz_data');
        if (transientData && !quizData.questions.length) {
            try {
                const parsed = JSON.parse(transientData);
                applyLoadedQuiz(parsed);
                showLoadingState(false);
                return;
            } catch (e) {}
        }

        // 3. Gọi API lấy dữ liệu thực tế từ máy chủ
        if (quizData.id) {
            try {
                const tokenParam = authToken ? `?teacher_token=${encodeURIComponent(authToken)}` : '';
                const res = await fetch(`${API_BASE_URL}/api/get_quiz/${encodeURIComponent(quizData.id)}${tokenParam}`);
                if (res.ok) {
                    const json = await res.json();
                    applyLoadedQuiz(json);
                } else {
                    console.warn("Could not fetch quiz from API, status:", res.status);
                    if (!quizData.questions.length) {
                        loadSampleData();
                    }
                }
            } catch (err) {
                console.error("Fetch quiz error:", err);
                if (!quizData.questions.length) {
                    loadSampleData();
                }
            }
        } else if (!quizData.questions.length) {
            loadSampleData();
        }

        showLoadingState(false);
    }

    function applyLoadedQuiz(obj) {
        if (!obj) return;
        let title = "ĐỀ THI TRẮC NGHIỆM";
        let questions = [];
        let timeLimit = 45;

        if (Array.isArray(obj)) {
            questions = obj;
        } else if (typeof obj === 'object') {
            title = obj.title || obj.quiz_title || "ĐỀ THI TRẮC NGHIỆM";
            timeLimit = obj.time_limit || obj.timeLimit || 45;
            if (Array.isArray(obj.data)) {
                questions = obj.data;
            } else if (Array.isArray(obj.questions)) {
                questions = obj.questions;
            } else if (obj.data && typeof obj.data === 'object' && Array.isArray(obj.data.data)) {
                questions = obj.data.data;
            }
        }

        quizData.title = title;
        quizData.questions = questions;
        quizData.time_limit = timeLimit;

        exportConfig.exam_title = title;
        exportConfig.time_limit = timeLimit;

        const navTitle = document.getElementById('navDocTitle');
        if (navTitle) navTitle.textContent = title;

        const inputTitle = document.getElementById('inputExamTitle');
        if (inputTitle) inputTitle.value = title;

        const inputTime = document.getElementById('inputTimeLimit');
        if (inputTime) inputTime.value = timeLimit || 45;

        const qCountBadges = document.querySelectorAll('.stat-qcount');
        qCountBadges.forEach(b => b.textContent = `${questions.length} câu`);

        renderPreview();
    }

    function loadSampleData() {
        quizData.title = "ĐỀ THI THỬ TỐT NGHIỆP THPT (MẪU MINH HỌA)";
        quizData.questions = [
            {
                group_title: "PHẦN I: TRẮC NGHIỆM NHIỀU PHƯƠNG ÁN LỰA CHỌN",
                question: "Cho hàm số \\(y = f(x)\\) có đạo hàm liên tục trên \\(\\mathbb{R}\\) và có bảng xét dấu đạo hàm như sau. Hàm số đã cho đồng biến trên khoảng nào dưới đây?",
                options: [
                    "A. \\((-\\infty; -1)\\)",
                    "B. \\((-1; 2)\\)",
                    "C. \\((2; +\\infty)\\)",
                    "D. \\((-1; +\\infty)\\)"
                ],
                correct_answer: "A",
                explain: "Dựa vào bảng xét dấu, \\(f'(x) > 0\\) trên khoảng \\((-\\infty; -1)\\), do đó hàm số đồng biến trên \\((-\\infty; -1)\\)."
            },
            {
                question: "Trong không gian \\(Oxyz\\), cho mặt cầu \\((S): (x-1)^2 + (y+2)^2 + (z-3)^2 = 16\\). Tọa độ tâm \\(I\\) và bán kính \\(R\\) của mặt cầu là:",
                options: [
                    "A. \\(I(1; -2; 3), R = 4\\)",
                    "B. \\(I(-1; 2; -3), R = 4\\)",
                    "C. \\(I(1; -2; 3), R = 16\\)",
                    "D. \\(I(-1; 2; -3), R = 16\\)"
                ],
                correct_answer: "A",
                explain: "Phương trình mặt cầu có dạng \\((x-a)^2 + (y-b)^2 + (z-c)^2 = R^2\\). Do đó tâm \\(I(1; -2; 3)\\) và \\(R = \\sqrt{16} = 4\\)."
            },
            {
                group_title: "PHẦN II: TRẮC NGHIỆM ĐÚNG SAI",
                type: "true_false",
                question: "Một vật dao động điều hòa theo phương trình \\(x = 5\\cos(2\\pi t + \\frac{\\pi}{3})\\) (cm). Xét tính đúng sai của các mệnh đề sau:",
                options: [
                    "a) Biên độ dao động của vật là \\(5\\text{ cm}\\).",
                    "b) Pha ban đầu của dao động là \\(\\frac{\\pi}{3}\\text{ rad}\\).",
                    "c) Tần số góc của dao động là \\(2\\pi\\text{ rad/s}\\).",
                    "d) Tại thời điểm \\(t = 0\\), vật đang đi qua vị trí cân bằng theo chiều dương."
                ],
                correct_answer: { "a": true, "b": true, "c": true, "d": false },
                explain: "Tại \\(t=0\\), \\(x = 5\\cos(\\pi/3) = 2.5\\text{ cm} > 0\\), vận tốc \\(v = -10\\pi\\sin(\\pi/3) < 0\\) nên vật đi theo chiều âm."
            },
            {
                group_title: "PHẦN III: TRẢ LỜI NGẮN",
                type: "short_answer",
                question: "Tính tích phân \\(I = \\int_{0}^{1} (2x + 1) dx\\).",
                options: [],
                correct_answer: "2",
                explain: "\\(I = [x^2 + x]_{0}^{1} = (1 + 1) - 0 = 2\\)."
            }
        ];
        applyLoadedQuiz(quizData);
    }

    // 4. Hàm Render Bản xem trước A4 (Real-time Preview Engine)
    function renderPreview() {
        const container = document.getElementById('paperContentContainer');
        if (!container) return;

        const isCompact = (exportConfig.layout_mode === 'compact');
        const isTeacher = (exportConfig.target_audience === 'teacher');
        const showAnswers = exportConfig.show_answers;
        const questions = quizData.questions || [];

        let html = '';

        // Header đề thi
        html += `
        <div class="paper-header">
            <div class="paper-header-left">
                <div class="school-name-text">${escapeHtml(exportConfig.school_name || "SỞ GIÁO DỤC VÀ ĐÀO TẠO")}</div>
                <div class="exam-title-text">${escapeHtml(exportConfig.exam_title || quizData.title)}</div>
                ${isTeacher ? `<div class="exam-badge-teacher">[ BẢN GIÁO VIÊN - ĐÁP ÁN & LỜI GIẢI ]</div>` : ''}
            </div>
            <div class="paper-header-right">
                <div class="exam-code-text">ĐỀ KIỂM TRA CHÍNH THỨC</div>
                <div class="exam-time-text">Thời gian làm bài: ${exportConfig.time_limit > 0 ? exportConfig.time_limit + ' phút' : 'Tự do'} | ${questions.length} câu</div>
            </div>
        </div>
        `;

        // Thông tin thí sinh
        if (exportConfig.show_candidate_info) {
            html += `
            <div class="student-info-bar">
                <span>Họ và tên thí sinh: ..............................................................</span>
                <span>SBD: .................</span>
                <span>Lớp: .................</span>
            </div>
            `;
        }

        // Phiếu trả lời trắc nghiệm (cho học sinh điền)
        if (!isTeacher && exportConfig.include_student_grid && questions.length > 0) {
            const totalQ = questions.length;
            const cols = (totalQ > 40) ? 20 : 10;
            const rows = Math.ceil(totalQ / cols);

            html += `
            <div class="student-answer-grid-box">
                <div class="student-answer-grid-title">PHIẾU TRẢ LỜI TRẮC NGHIỆM</div>
                <table class="student-grid-table">
            `;

            for (let r = 0; r < rows; r++) {
                html += `<tr>`;
                for (let c = 0; c < cols; c++) {
                    const qNum = r * cols + c + 1;
                    if (qNum <= totalQ) {
                        html += `<th>${qNum}</th>`;
                    } else {
                        html += `<th></th>`;
                    }
                }
                html += `</tr><tr>`;
                for (let c = 0; c < cols; c++) {
                    const qNum = r * cols + c + 1;
                    html += `<td>${qNum <= totalQ ? '&nbsp;' : ''}</td>`;
                }
                html += `</tr>`;
            }

            html += `</table></div>`;
        }

        // Danh sách câu hỏi
        let currentGroup = null;

        questions.forEach((q, idx) => {
            const groupTitle = (q.group_title || '').trim();
            if (groupTitle && groupTitle !== currentGroup) {
                currentGroup = groupTitle;
                html += `<div class="paper-part-header">${escapeHtml(groupTitle)}</div>`;
            }

            const qNum = idx + 1;
            const qStem = q.question || '';
            const qType = q.type || 'mcq';
            const options = q.options || [];
            const rawCa = q.correct_answer;

            html += `<div class="paper-question-block" id="preview_q_${qNum}">`;
            html += `<div class="q-stem"><strong class="q-num">Câu ${qNum}:</strong> ${formatText(qStem)}</div>`;

            if (qType === 'short_answer') {
                html += `<div class="short-ans-line">`;
                html += `<strong>Đáp số:</strong> `;
                if (showAnswers && rawCa) {
                    html += `<span class="short-ans-correct">${escapeHtml(String(rawCa))}</span>`;
                } else {
                    html += `<span>...................................................................................</span>`;
                }
                html += `</div>`;
            } else if (qType === 'true_false' || (typeof rawCa === 'object' && rawCa !== null)) {
                const caDict = (typeof rawCa === 'object' && rawCa !== null) ? rawCa : {};
                html += `<div class="q-options-container q-options-1col">`;
                options.forEach((opt) => {
                    const optStr = String(opt).trim();
                    const match = optStr.match(/^(\*?\s*([a-dA-D]))([\.\:\)])\s*(.*)/);
                    let label = "";
                    let content = optStr;
                    let subKey = "";
                    if (match) {
                        subKey = match[2].toLowerCase();
                        label = match[1] + match[3] + " ";
                        content = match[4];
                    }

                    let tagHtml = "";
                    if (showAnswers && subKey in caDict) {
                        const val = caDict[subKey];
                        const isD = (val === true || String(val).toLowerCase() === 'đ' || String(val).toLowerCase() === 'd' || String(val) === '1');
                        tagHtml = `<span class="tf-tag ${isD ? 'true' : 'false'}">[ Đúng / Sai ] - ${isD ? 'ĐÚNG' : 'SAI'}</span>`;
                    } else {
                        tagHtml = `<span class="tf-tag neutral">[ Đúng / Sai ]</span>`;
                    }

                    html += `<div class="q-opt-item">`;
                    if (label) html += `<strong class="q-opt-label">${escapeHtml(label)}</strong>`;
                    html += `<span>${formatText(content)}</span> ${tagHtml}`;
                    html += `</div>`;
                });
                html += `</div>`;
            } else {
                // MCQ thông thường
                const colCount = determineColumns(options, exportConfig.options_layout);
                const colClass = (colCount === 4) ? 'q-options-4col' : ((colCount === 2) ? 'q-options-2col' : 'q-options-1col');

                html += `<div class="q-options-container ${colClass}">`;
                options.forEach((opt, optIdx) => {
                    const optStr = String(opt).trim();
                    const isCorr = isOptionCorrect(optIdx, optStr, rawCa);
                    const match = optStr.match(/^(\*?\s*[A-Fa-f][\.\:\)])\s*(.*)/);
                    let label = "";
                    let content = optStr;
                    if (match) {
                        label = match[1] + " ";
                        content = match[2];
                    }

                    const optHighlight = (showAnswers && isCorr) ? 'is-correct' : '';

                    html += `<div class="q-opt-item ${optHighlight}">`;
                    if (label) html += `<strong class="q-opt-label">${escapeHtml(label)}</strong>`;
                    html += `<span>${formatText(content)}</span>`;
                    html += `</div>`;
                });
                html += `</div>`;
            }

            html += `</div>`;
        });

        // Bảng đáp án tổng hợp (cho giáo viên)
        if (exportConfig.show_key_table && questions.length > 0) {
            const totalQ = questions.length;
            const cols = (isCompact && totalQ >= 10) ? 10 : 5;
            const rows = Math.ceil(totalQ / cols);

            html += `
            <div class="paper-key-section">
                <div class="paper-key-title">--- BẢNG ĐÁP ÁN ---</div>
                <table class="paper-key-table">
            `;

            for (let r = 0; r < rows; r++) {
                html += `<tr>`;
                for (let c = 0; c < cols; c++) {
                    const qNum = r * cols + c + 1;
                    html += `<th>${qNum <= totalQ ? 'Câu ' + qNum : ''}</th>`;
                }
                html += `</tr><tr>`;
                for (let c = 0; c < cols; c++) {
                    const qIdx = r * cols + c;
                    if (qIdx < totalQ) {
                        const q = questions[qIdx];
                        const ansDisplay = getAnswerDisplay(q);
                        html += `<td>${escapeHtml(ansDisplay)}</td>`;
                    } else {
                        html += `<td></td>`;
                    }
                }
                html += `</tr>`;
            }

            html += `</table></div>`;
        }

        // Hướng dẫn giải chi tiết (cho giáo viên)
        const hasExplains = questions.some(q => (q.explain || '').trim().length > 0);
        if (exportConfig.show_explains && hasExplains) {
            html += `
            <div class="paper-explains-section">
                <div class="paper-explains-title">HƯỚNG DẪN GIẢI CHI TIẾT</div>
            `;
            questions.forEach((q, idx) => {
                const exp = (q.explain || '').trim();
                if (exp) {
                    html += `
                    <div class="paper-exp-item">
                        <span class="paper-exp-q">Câu ${idx + 1}:</span>
                        <span>${formatText(exp)}</span>
                    </div>
                    `;
                }
            });
            html += `</div>`;
        }

        container.innerHTML = html;

        // Ước tính số trang
        updatePageEstimation();

        // Typeset MathJax
        renderMathJax();
    }

    function determineColumns(options, userChoice) {
        if (!options || !options.length) return 1;
        if (userChoice === '1') return 1;
        if (userChoice === '4' && options.length === 4) return 4;
        if (userChoice === '2' && (options.length === 2 || options.length === 4)) return 2;

        for (let opt of options) {
            const s = String(opt);
            if (s.includes('<img') || s.includes('$$') || s.includes('\\[') || s.includes('\n')) {
                return 1;
            }
        }

        const cleanLen = (opt) => {
            let s = String(opt).replace(/<[^>]+>/g, '').replace(/\\[a-zA-Z]+/g, '').replace(/[\$\(\)\{\}\^\_]/g, '');
            return s.trim().length;
        };

        const maxLen = Math.max(...options.map(cleanLen));
        if (maxLen <= 18 && options.length === 4) return 4;
        if (maxLen <= 38 && (options.length === 2 || options.length === 4)) return 2;
        return 1;
    }

    function isOptionCorrect(optIdx, optText, rawCa) {
        if (rawCa === null || rawCa === undefined) return false;
        const letter = String.fromCharCode(65 + optIdx);
        if (typeof rawCa === 'string') {
            const cleanCa = rawCa.trim().toUpperCase();
            if (cleanCa === letter) return true;
            if (cleanCa.startsWith(letter + '.') || cleanCa.startsWith(letter + ')') || cleanCa.startsWith(letter + ':')) return true;
        }
        if (typeof rawCa === 'number' && rawCa === optIdx) return true;
        if (optText.trim().startsWith('*')) return true;
        return false;
    }

    function getAnswerDisplay(q) {
        const qType = q.type || 'mcq';
        const rawCa = q.correct_answer;
        if (!rawCa && rawCa !== 0) return "-";

        if (qType === 'true_false' || (typeof rawCa === 'object' && rawCa !== null)) {
            if (typeof rawCa === 'object' && rawCa !== null) {
                const parts = ['a', 'b', 'c', 'd'].filter(k => k in rawCa).map(k => `${k}-${rawCa[k] ? 'Đ' : 'S'}`);
                return parts.join(' ') || "-";
            }
            return String(rawCa);
        }

        if (qType === 'short_answer') {
            return String(rawCa);
        }

        if (typeof rawCa === 'number') {
            return String.fromCharCode(65 + rawCa);
        }

        const s = String(rawCa).trim().toUpperCase();
        for (let c of ['A', 'B', 'C', 'D']) {
            if (s.startsWith(c + '.') || s.startsWith(c + ')') || s.startsWith(c + ':') || s === c) {
                return c;
            }
        }
        return s.slice(0, 3);
    }

    function formatText(text) {
        if (!text) return "";
        let s = String(text);
        // Chuyển newline thành <br>
        s = s.replace(/\n/g, '<br>');
        return s;
    }

    function escapeHtml(text) {
        if (!text) return "";
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function renderMathJax() {
        if (!window.MathJax || typeof window.MathJax.typesetPromise !== 'function') return;
        if (mathJaxPending) return;
        mathJaxPending = true;
        const sheet = document.getElementById('a4Sheet');
        if (sheet) {
            window.MathJax.typesetPromise([sheet]).then(() => {
                mathJaxPending = false;
                updatePageEstimation();
            }).catch((err) => {
                console.warn("MathJax typeset error:", err);
                mathJaxPending = false;
            });
        } else {
            mathJaxPending = false;
        }
    }

    function updatePageEstimation() {
        const sheet = document.getElementById('a4Sheet');
        if (!sheet) return;
        const totalHeightPx = sheet.scrollHeight;
        // 1 trang A4 chuẩn tương đương khoảng 1122px (297mm ở 96dpi)
        const a4HeightPx = 1122;
        const estimatedPages = Math.max(1, Math.ceil(totalHeightPx / a4HeightPx));
        const badge = document.getElementById('statEstPages');
        if (badge) {
            badge.textContent = `Ước tính: ~${estimatedPages} trang A4`;
        }
    }

    // 5. Điều khiển Thu phóng (Zoom)
    function adjustZoom(delta) {
        setZoom(zoomLevel + delta);
    }

    function setZoom(val) {
        zoomLevel = Math.max(0.4, Math.min(2.0, Math.round(val * 10) / 10));
        const viewport = document.getElementById('a4Viewport');
        if (viewport) {
            viewport.style.transform = `scale(${zoomLevel})`;
        }
        const label = document.getElementById('zoomLevelLabel');
        if (label) {
            label.textContent = `${Math.round(zoomLevel * 100)}%`;
        }
    }

    function fitToWidth() {
        const previewArea = document.querySelector('.export-preview-area');
        const sheet = document.getElementById('a4Sheet');
        if (!previewArea || !sheet) return;
        const availableWidth = previewArea.clientWidth - 60;
        const sheetWidth = sheet.offsetWidth || 794; // ~210mm in px
        const idealZoom = availableWidth / sheetWidth;
        setZoom(idealZoom);
    }

    // 6. Xử lý Tải file Word (.docx)
    async function handleDownloadDocx() {
        const btn = document.getElementById('btnDownloadDocx');
        const origText = btn ? btn.innerHTML : '';
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = `<i class="ri-loader-4-line ri-spin"></i> Đang tạo file Word...`;
        }

        try {
            // Nếu có quiz_id trên máy chủ, sử dụng GET endpoint chuẩn
            if (quizData.id) {
                const params = new URLSearchParams({
                    teacher_token: authToken || '',
                    target_audience: exportConfig.target_audience,
                    layout_mode: exportConfig.layout_mode,
                    options_layout: exportConfig.options_layout,
                    show_answers: String(exportConfig.show_answers),
                    show_key_table: String(exportConfig.show_key_table),
                    show_explains: String(exportConfig.show_explains),
                    include_student_answer_grid: String(exportConfig.include_student_grid)
                });
                const downloadUrl = `${API_BASE_URL}/api/teacher/export_docx/${encodeURIComponent(quizData.id)}?${params.toString()}`;
                window.location.href = downloadUrl;
                showToast("Đang tải file Word (.docx) về máy...", "success");
            } else {
                // Sử dụng custom payload qua POST
                const payload = {
                    title: exportConfig.exam_title || quizData.title,
                    questions: quizData.questions,
                    time_limit: exportConfig.time_limit,
                    target_audience: exportConfig.target_audience,
                    layout_mode: exportConfig.layout_mode,
                    options_layout: exportConfig.options_layout,
                    show_answers: exportConfig.show_answers,
                    show_key_table: exportConfig.show_key_table,
                    show_explains: exportConfig.show_explains,
                    include_student_answer_grid: exportConfig.include_student_grid
                };

                const res = await fetch(`${API_BASE_URL}/api/teacher/export_docx_custom`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    const blob = await res.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `${(exportConfig.exam_title || 'de_thi').replace(/[^a-zA-Z0-9_\u00C0-\u024F\u1EA0-\u1EF9]/g, '_')}.docx`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    window.URL.revokeObjectURL(url);
                    showToast("Tải file Word (.docx) thành công!", "success");
                } else {
                    const err = await res.json().catch(() => ({}));
                    showToast(err.detail || "Không thể tạo file Word. Vui lòng thử lại.", "error");
                }
            }
        } catch (e) {
            console.error("Export docx error:", e);
            showToast("Lỗi kết nối khi xuất file Word.", "error");
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = origText;
            }
        }
    }

    // 7. Xử lý In & Lưu PDF chuẩn A4
    function handlePrintPdf() {
        showToast("Đang chuẩn bị trang in PDF...", "info");
        // Đặt lại zoom 100% trước khi print để tránh scale sai
        const currentZ = zoomLevel;
        setZoom(1.0);
        setTimeout(() => {
            window.print();
            setZoom(currentZ);
        }, 200);
    }

    function showLoadingState(isLoading) {
        const loader = document.getElementById('exportLoader');
        if (loader) loader.style.display = isLoading ? 'flex' : 'none';
    }

    function showToast(msg, type = "info") {
        const container = document.getElementById('exportToastContainer');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = `export-toast toast-${type}`;
        let icon = 'ri-information-line';
        if (type === 'success') icon = 'ri-checkbox-circle-line';
        if (type === 'error') icon = 'ri-error-warning-line';
        toast.innerHTML = `<i class="${icon}"></i> <span>${escapeHtml(msg)}</span>`;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3200);
    }

    window.adjustZoom = adjustZoom;
    window.setZoom = setZoom;
    window.fitToWidth = fitToWidth;
    window.handleDownloadDocx = handleDownloadDocx;
    window.handlePrintPdf = handlePrintPdf;
})();
