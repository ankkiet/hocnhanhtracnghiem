// Tự động nhận diện môi trường (Localhost vs Production)
let API_BASE_URL = "https://inland-marylin-hocnhanhtn-c3471a95.koyeb.app"; // QUAN TRỌNG: Link Koyeb thật của bạn
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.protocol === 'file:') {
    API_BASE_URL = "http://127.0.0.1:8000";
} else if (window.location.hostname.startsWith('192.168.')) {
    API_BASE_URL = `http://${window.location.hostname}:8000`; // Hỗ trợ test qua mạng LAN (Live Server IP)
}

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
let adminApiKeys = [];
let isShowingTrash = false;

// Khởi tạo bộ nhớ tạm để thu gọn mã Base64 ảnh trong Code Editor
let globalEditorImageStorage = {};
let globalEditorImageCounter = 0;

let authToken = localStorage.getItem('auth_token');
let authRole = localStorage.getItem('auth_role');
let authName = localStorage.getItem('auth_name');

// Sinh ID ngẫu nhiên cho phiên làm việc để phục vụ Giám sát thi
let clientSessionId = sessionStorage.getItem('client_session_id');
if (!clientSessionId) {
    clientSessionId = 'sess_' + Math.random().toString(36).substr(2, 9);
    sessionStorage.setItem('client_session_id', clientSessionId);
}
let heartbeatInterval;

function renderMath() {
    if (currentMode === 'edit') return; // Không render MathJax trong chế độ sửa để bảo toàn mã LaTeX
    if (window.MathJax && typeof window.MathJax.typesetPromise === 'function') {
        MathJax.typesetPromise().catch((err) => console.log('MathJax error:', err));
    } else {
        // Chờ MathJax tải xong (do thẻ script là async)
        setTimeout(renderMath, 500);
    }
}

window.onload = async function() {
    checkAuthState();
};

function escapeHtml(str) {
    if (typeof str !== 'string') return str;
    return str.replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;')
              .replace(/'/g, '&#039;');
}

function checkAuthState() {
    if (!authToken) {
        document.getElementById('authContainer').style.display = 'block';
        document.getElementById('mainAppContainer').style.display = 'none';
        document.getElementById('adminContainer').style.display = 'none';
    } else if (authRole === 'admin') {
        document.getElementById('authContainer').style.display = 'none';
        document.getElementById('mainAppContainer').style.display = 'none';
        document.getElementById('adminContainer').style.display = 'block';
        loadAdminUsers();
        loadAdminSettings();
    } else {
        document.getElementById('authContainer').style.display = 'none';
        document.getElementById('adminContainer').style.display = 'none';
        document.getElementById('mainAppContainer').style.display = 'block';
        
        document.getElementById('currentUserDisplay').innerText = `👤 Xin chào, ${authName} (${authRole === 'teacher' ? 'Giáo viên' : 'Học sinh'})`;
        document.getElementById('studentNameInput').value = authName; // Tự động điền tên học sinh
        
        if (authRole === 'student') {
            document.getElementById('uploadBox').style.display = 'none';
            document.getElementById('studentDashboard').style.display = 'block';
        } else if (authRole === 'teacher') {
            document.getElementById('teacherDashboard').style.display = 'block';
            loadTeacherQuizzes();
        }
        initApp();
    }
}

function toggleAuth(type) {
    if(type === 'register') {
        document.getElementById('loginForm').style.display = 'none';
        document.getElementById('registerForm').style.display = 'block';
    } else {
        document.getElementById('loginForm').style.display = 'block';
        document.getElementById('registerForm').style.display = 'none';
    }
}

async function handleLogin() {
    const u = document.getElementById('loginUsername').value.trim();
    const p = document.getElementById('loginPassword').value.trim();
    if(!u || !p) return alert("Vui lòng nhập đủ thông tin");
    
    try {
        const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username: u, password: p})
        });
        const data = await res.json();
        if(res.ok && data.status === 'success') {
            localStorage.setItem('auth_token', data.token);
            localStorage.setItem('auth_role', data.role);
            localStorage.setItem('auth_name', data.full_name);
            authToken = data.token; authRole = data.role; authName = data.full_name;
            checkAuthState();
        } else { alert("Lỗi: " + data.detail); }
    } catch(e) { 
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
    
    try {
        const res = await fetch(`${API_BASE_URL}/api/auth/register`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username: u, password: p, full_name: fn, role: r})
        });
        const data = await res.json();
        if(res.ok && data.status === 'success') {
            alert("Đăng ký thành công! Vui lòng chờ Quản trị viên duyệt tài khoản.");
            toggleAuth('login');
        } else { alert("Lỗi: " + data.detail); }
    } catch(e) { alert("Lỗi kết nối máy chủ"); }
}

function logout() {
    localStorage.clear();
    window.location.href = window.location.pathname; // Tải lại trang xóa query param
}

async function initApp() {
    const urlParams = new URLSearchParams(window.location.search);
    const quizId = urlParams.get('quiz_id') || urlParams.get('id');
    if (quizId) {
        document.getElementById('uploadBox').style.display = 'none';
        document.getElementById('btnEdit').style.display = 'none'; 
        document.getElementById('quiz-container').innerHTML = "<p style='text-align:center;'>Đang tải dữ liệu bài thi...</p>";
        try {
            const response = await fetch(`${API_BASE_URL}/api/get_quiz/${quizId}?teacher_token=${authToken || ''}`);
            const result = await response.json();
            if (result.status === 'success') {
                currentData = result.data;
                serverData = JSON.parse(JSON.stringify(result.data));
                const serverUpdatedAt = result.updated_at || 0;
                
                // --- Thiết lập Giao diện Dành riêng cho Học sinh ---
                document.querySelector('.header').style.display = 'none';
                document.getElementById('studentHeader').style.display = 'block';
                document.getElementById('studentQuizTitle').innerText = result.title;
                document.getElementById('studentQCount').innerHTML = `🏷 Số câu: ${currentData.length}` + (result.is_shuffle ? ` <span style="color: var(--success); font-size: 0.85rem; background: #d1fae5; padding: 2px 6px; border-radius: 4px; margin-left: 5px;">🔀 Đã trộn ngẫu nhiên</span>` : '');
                
                currentTimeLimit = result.time_limit || 0;
                if (currentTimeLimit > 0) {
                    document.getElementById('studentTime').innerText = `⏳ Thời gian: ${currentTimeLimit} phút`;
                }
                
                document.getElementById('modeSwitch').style.display = 'none'; // Ẩn hoàn toàn các nút công cụ
                
                isShuffleEnabled = result.is_shuffle;
                
                // KHÔI PHỤC TIẾN TRÌNH TỪ CLOUD HOẶC LOCAL STORAGE
                let loadedProgress = null;
                
                // 1. Thử lấy từ Server Cloud trước
                if (authRole === 'student' && authToken) {
                    try {
                        const pRes = await fetch(`${API_BASE_URL}/api/student/get_progress/${quizId}?student_token=${authToken}`);
                        const pData = await pRes.json();
                        if (pData.status === 'success' && pData.data) {
                            loadedProgress = pData.data;
                            localStorage.setItem(`quiz_progress_${quizId}`, JSON.stringify(loadedProgress)); // Backup xuống local
                        }
                    } catch(e) { console.log("Lỗi tải tiến trình cloud", e); }
                }
                
                // 2. Nếu Cloud không có (hoặc rớt mạng), lấy từ bộ nhớ Local
                if (!loadedProgress) {
                    const localP = localStorage.getItem(`quiz_progress_${quizId}`);
                    if (localP) { try { loadedProgress = JSON.parse(localP); } catch(e){} }
                }
                
                if (loadedProgress) {
                    try {
                        quizProgress = loadedProgress;
                        
                        if (quizProgress.quizUpdatedAt && serverUpdatedAt > 0 && quizProgress.quizUpdatedAt < serverUpdatedAt) {
                            alert("⚠️ Đề thi đã được giáo viên cập nhật nội dung/đáp án mới!\nTiến trình làm bài cũ của bạn sẽ được làm mới lại để đảm bảo tính chính xác.");
                            let oldHistory = quizProgress.history || [];
                            let sName = quizProgress.studentName || "";
                            quizProgress = { history: oldHistory, studentName: sName, quizUpdatedAt: serverUpdatedAt };
                            // Bỏ qua shuffledData cũ để hệ thống dùng currentData (data mới nhất)
                        } else {
                            if (quizProgress.studentName) document.getElementById('studentNameInput').value = quizProgress.studentName;
                            if (quizProgress.shuffledData) currentData = quizProgress.shuffledData;
                            if (!quizProgress.quizUpdatedAt) quizProgress.quizUpdatedAt = serverUpdatedAt;
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
                            } else if (Object.keys(quizProgress.answers || {}).length > 0) {
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
                        } else if (Object.keys(quizProgress.answers || {}).length > 0) {
                            document.getElementById('startBtn').innerText = "🚀 Tiếp tục làm bài đang dở";
                        }
                    } catch(e){}
                }
                
                if ((!quizProgress || !quizProgress.shuffledData) && isShuffleEnabled) {
                    shuffleQuiz(true); // Trộn đề ngầm, không render lại ngay
                }
                
                isStudentMode = true;
                currentDataMode = result.mode || 'practice';
                document.getElementById('welcomeScreen').style.display = 'block'; // Hiển thị khung nhập tên
            } else { document.getElementById('quiz-container').innerHTML = "<p style='text-align:center;'>Bài thi không tồn tại hoặc đã bị xóa.</p>"; }
        } catch (e) {
            document.getElementById('quiz-container').innerHTML = `<p style='text-align:center; color: var(--danger);'><b>Không thể truy cập:</b> ${e.message || "Lỗi máy chủ"}</p>`;
            if (e.message) alert(e.message);
        }
    }
};

function sendPing() {
    if (!isStudentMode) return;
    const urlParams = new URLSearchParams(window.location.search);
    let quizId = urlParams.get('quiz_id') || urlParams.get('id');
    if (!quizId) {
        const path = window.location.pathname.replace(/^\/|\/$/g, '');
        if (path && path.length >= 5 && path.length <= 10 && !path.includes('.html')) quizId = path;
    }
    if (!quizId) return;
    
    fetch(`${API_BASE_URL}/api/monitor/ping`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            quiz_id: quizId, 
            session_id: clientSessionId, 
            student_name: studentName || 'Đang ẩn danh',
            answers_count: Object.keys(quizProgress.answers || {}).length,
            time_remaining: quizProgress.timeRemaining || 0,
            completed: quizProgress.completed || false
        })
    }).catch(e => {}); // Lỗi mạng (âm thầm bỏ qua không báo popup)
}

async function startStudentQuiz() {
    const nameInput = document.getElementById('studentNameInput').value.trim();
    studentName = nameInput;
    
    const urlParams = new URLSearchParams(window.location.search);
    const quizId = urlParams.get('quiz_id') || urlParams.get('id');

    // Nếu bấm nút khi đã hoàn thành -> Có nghĩa là muốn Xóa lịch sử làm lại từ đầu
    if (quizProgress.completed) {
        const startBtn = document.getElementById('startBtn');
        const originalText = startBtn.innerText;
        startBtn.innerText = "⏳ Đang tải dữ liệu mới...";
        startBtn.disabled = true;
        
        if (quizId) {
            try {
                const response = await fetch(`${API_BASE_URL}/api/get_quiz/${quizId}?teacher_token=${authToken || ''}`);
                const result = await response.json();
                if (result.status === 'success') {
                    serverData = JSON.parse(JSON.stringify(result.data));
                    isShuffleEnabled = result.is_shuffle;
                    quizProgress.quizUpdatedAt = result.updated_at || 0;
                    currentTimeLimit = result.time_limit || 0;
                    currentDataMode = result.mode || 'practice';
                }
            } catch(e) { console.error(e); }
        }

        let oldHistory = quizProgress.history || [];
        let updatedTs = quizProgress.quizUpdatedAt;
        quizProgress = { history: oldHistory, quizUpdatedAt: updatedTs };
        currentData = JSON.parse(JSON.stringify(serverData)); // KHÔI PHỤC DATA MỚI NHẤT TỪ SERVER
        if (isShuffleEnabled) shuffleQuiz(true);
        
        startBtn.innerText = originalText;
        startBtn.disabled = false;
    }
    
    quizProgress.studentName = studentName;
    if (!quizProgress.shuffledData) quizProgress.shuffledData = currentData;
    if (!quizProgress.answers) quizProgress.answers = {};
    quizProgress.completed = false;
    saveProgressToLocal();
    
    document.getElementById('welcomeScreen').style.display = 'none';
    document.getElementById('studentNameDisplay').innerText = `👤 Thí sinh: ${studentName}`;
    document.body.classList.add('minimal-mode');
    document.body.classList.remove('quiz-completed');
    if (document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(err => console.log("Fullscreen error:", err));
    }
    
    switchMode(currentDataMode); 
    if (currentDataMode === 'exam' && currentTimeLimit > 0) { startTimer(currentTimeLimit); }
    
    const quizContainer = document.getElementById('quiz-container');
    if (quizContainer) quizContainer.scrollTo({ top: 0, behavior: 'smooth' });
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    sendPing();
    clearInterval(heartbeatInterval);
    heartbeatInterval = setInterval(sendPing, 10000); // Gửi tín hiệu mỗi 10 giây
}

function restartPractice() {
    fetchLatestDataAndRestart('practice');
}

function restartExam() {
    fetchLatestDataAndRestart('exam');
}

async function fetchLatestDataAndRestart(mode) {
    const urlParams = new URLSearchParams(window.location.search);
    const quizId = urlParams.get('quiz_id') || urlParams.get('id');
    
    const container = document.getElementById('quiz-container');
    if (container) container.innerHTML = "<p style='text-align:center; padding: 50px; font-weight: bold; color: var(--primary);'>🔄 Đang tải dữ liệu mới nhất từ máy chủ...</p>";
    
    if (quizId) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/get_quiz/${quizId}?teacher_token=${authToken || ''}`);
            const result = await response.json();
            if (result.status === 'success') {
                serverData = JSON.parse(JSON.stringify(result.data));
                isShuffleEnabled = result.is_shuffle;
                quizProgress.quizUpdatedAt = result.updated_at || 0;
                currentTimeLimit = result.time_limit || 0;
            }
        } catch(e) { console.error("Lỗi cập nhật data mới", e); }
    }
    
    let oldHistory = quizProgress.history || [];
    let updatedTs = quizProgress.quizUpdatedAt;
    quizProgress = { history: oldHistory, studentName: studentName, quizUpdatedAt: updatedTs };
    currentData = JSON.parse(JSON.stringify(serverData)); // KHÔI PHỤC DATA MỚI NHẤT TỪ SERVER
    
    if (isShuffleEnabled) {
        shuffleQuiz(true);
    }
    
    quizProgress.shuffledData = currentData;
    quizProgress.answers = {};
    quizProgress.completed = false;
    saveProgressToLocal();
    
    switchMode(mode);
    if (mode === 'exam' && currentTimeLimit > 0) { startTimer(currentTimeLimit); }
    
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
    document.getElementById('studentNameDisplay').innerText = `👤 Thí sinh: ${studentName}`;
    document.body.classList.add('minimal-mode');
    if (document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(err => console.log("Fullscreen error:", err));
    }
    
    renderData(); 
    submitExam(true); // Gọi chấm điểm nhưng truyền cờ isReview = true để không gửi server
}

async function saveProgressToLocal() {
    const urlParams = new URLSearchParams(window.location.search);
    let quizId = urlParams.get('quiz_id') || urlParams.get('id');
    
    // Hỗ trợ link dạng /AAA-111 (Yêu cầu cấu hình Server Route, Frontend xử lý dự phòng)
    if (!quizId) {
        const path = window.location.pathname.replace(/^\/|\/$/g, '');
        if (path && path.length >= 5 && path.length <= 10 && !path.includes('.html')) {
            quizId = path;
        }
    }
    
    if (quizId) {
        localStorage.setItem(`quiz_progress_${quizId}`, JSON.stringify(quizProgress));
        
        // Đồng bộ ngầm lên Cloud Server nếu là học sinh đang đăng nhập
        if (authRole === 'student' && authToken) {
            fetch(`${API_BASE_URL}/api/student/save_progress`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ student_token: authToken, quiz_id: quizId, progress_data: quizProgress })
            }).catch(e => console.log("Lỗi đồng bộ cloud")); // Không dùng await để tránh giật lag UI
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

async function loadTeacherQuizzes() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/teacher/quizzes?teacher_token=${authToken}`);
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            let html = `<table style="width:100%; border-collapse: collapse; text-align:left; min-width: 600px;">
                <tr style="border-bottom: 2px solid var(--border); color: var(--text-muted);">
                    <th style="padding: 12px 10px;">Tên đề thi</th>
                    <th style="padding: 12px 10px;">Chế độ</th>
                    <th style="padding: 12px 10px;">Số câu</th>
                    <th style="padding: 12px 10px;">Trạng thái</th>
                    <th style="padding: 12px 10px;">Thao tác</th>
                </tr>`;
            
            let hasItems = false;
            data.data.forEach(q => {
                if (isShowingTrash && q.status !== 'trashed') return;
                if (!isShowingTrash && q.status === 'trashed') return;
                
                hasItems = true;
                let modeStr = q.mode === 'exam' ? '📝 Thi thử' : '🎯 Luyện tập';
                let statusBadge = q.status === 'published' ? '<span style="color:var(--success); font-weight:bold;">Đang mở</span>' : 
                                  (q.status === 'trashed' ? '<span style="color:var(--text-muted); font-weight:bold;">Đã xóa</span>' : '<span style="color:var(--danger); font-weight:bold;">Đã khóa</span>');
                let toggleAction = q.status === 'published' ? 'unpublished' : 'published';
                let toggleText = q.status === 'published' ? 'Khóa đề' : 'Mở lại';
                
                let actionButtons = "";
                if (isShowingTrash) {
                    actionButtons = `
                        <button class="btn-outline" style="padding: 4px 8px; font-size: 0.85rem; border-color: var(--success); color: var(--success);" onclick="handleQuizAction('${q.id}', 'restore')">♻️ Khôi phục</button>
                        <button class="btn-outline" style="padding: 4px 8px; font-size: 0.85rem; border-color: var(--danger); color: var(--danger);" onclick="handleQuizAction('${q.id}', 'permanent')">❌ Xóa vĩnh viễn</button>
                    `;
                } else {
                    actionButtons = `
                        <button class="btn-outline" style="padding: 4px 8px; font-size: 0.85rem;" onclick="navigator.clipboard.writeText('${q.id}'); alert('Đã copy mã đề!');">Copy Mã</button>
                        <button class="btn-outline" style="padding: 4px 8px; font-size: 0.85rem;" onclick="navigator.clipboard.writeText('${window.location.origin + window.location.pathname}?id=${q.id}'); alert('Đã copy Link!');">Copy Link</button>
                        <button class="btn-outline" style="padding: 4px 8px; font-size: 0.85rem; border-color: #8b5cf6; color: #8b5cf6;" onclick="startMonitoring('${q.id}', '${q.title}')">📊 Giám sát</button>
                        <button class="btn-outline" style="padding: 4px 8px; font-size: 0.85rem; border-color: var(--primary); color: var(--primary);" onclick="editQuiz('${q.id}')">✏️ Sửa đề</button>
                        <button class="btn-outline" style="padding: 4px 8px; font-size: 0.85rem; border-color: var(--danger); color: var(--danger);" onclick="handleQuizAction('${q.id}', 'trash')">🗑️ Xóa</button>
                        <button class="btn-outline" style="padding: 4px 8px; font-size: 0.85rem;" onclick="toggleQuizStatus('${q.id}', '${toggleAction}')">${toggleText}</button>
                    `;
                }
                
                html += `<tr style="border-bottom: 1px solid var(--border);">
                    <td style="padding: 12px 10px; font-weight: 600; color: var(--primary);">${q.title}</td>
                    <td style="padding: 12px 10px;">${modeStr}</td>
                    <td style="padding: 12px 10px;">${q.question_count}</td>
                    <td style="padding: 12px 10px;">${statusBadge}</td>
                    <td style="padding: 12px 10px;">
                        <div style="display: flex; flex-wrap: wrap; gap: 5px;">
                            ${actionButtons}
                        </div>
                    </td>
                </tr>`;
            });
            
            if (!hasItems) {
                html += `<tr><td colspan="5" style="text-align: center; padding: 20px; color: var(--text-muted);">${isShowingTrash ? 'Thùng rác trống.' : 'Chưa có đề thi nào.'}</td></tr>`;
            }
            
            html += `</table>`;
            document.getElementById('teacherQuizList').innerHTML = html;
        }
    } catch(e) { console.error("Lỗi tải danh sách đề", e); }
}

async function handleQuizAction(quizId, action) {
    let msg = "";
    if (action === 'trash') msg = "Bạn có chắc chắn muốn đưa đề thi này vào thùng rác?";
    if (action === 'permanent') msg = "Bạn có chắc chắn muốn XÓA VĨNH VIỄN đề thi này không? Hành động này không thể khôi phục!";
    if (action === 'restore') msg = "Bạn muốn khôi phục đề thi này (sẽ ở trạng thái khóa)?";
    
    if (msg && !confirm(msg)) return;
    
    try {
        const res = await fetch(`${API_BASE_URL}/api/teacher/quiz_action`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ teacher_token: authToken, quiz_id: quizId, action: action })
        });
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            if (action === 'trash') alert("Đã đưa vào thùng rác!");
            if (action === 'permanent') alert("Đã xóa vĩnh viễn!");
            if (action === 'restore') alert("Đã khôi phục thành công!");
            loadTeacherQuizzes();
        } else {
            alert("Lỗi: " + data.detail);
        }
    } catch(e) {
        alert("Lỗi kết nối máy chủ");
    }
}

async function editQuiz(quizId) {
    document.getElementById('quiz-container').innerHTML = "<p style='text-align:center;'>Đang tải dữ liệu bài thi...</p>";
    try {
        const response = await fetch(`${API_BASE_URL}/api/get_quiz/${quizId}?teacher_token=${authToken || ''}`);
        const result = await response.json();
        if (result.status === 'success') {
            currentData = result.data;
            serverData = JSON.parse(JSON.stringify(result.data));
            editingQuizId = quizId;
            
            // Lưu tạm cấu hình cũ để lát mở Modal sẽ tự động điền
            window.tempQuizSettings = {
                title: result.title,
                mode: result.mode,
                timeLimit: result.time_limit,
                isShuffle: result.is_shuffle
            };
            
            document.body.classList.add('editor-fullscreen');
            document.getElementById('uploadBox').style.display = 'none';
            document.getElementById('teacherDashboard').style.display = 'none';
            
            switchMode('edit');
            document.getElementById('saveBtn').style.display = 'block';
            document.getElementById('saveBtn').innerText = "⚙️ Cập nhật & Cấu hình Xuất bản";
            document.getElementById('backDashboardBtn').style.display = 'block';
            document.getElementById('aiCustomPrompt').style.display = 'block';
            document.getElementById('btnAICheck').style.display = 'block';
            
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } else { alert("Không tìm thấy đề thi."); }
    } catch (e) { alert("Lỗi tải đề thi."); }
}

async function toggleQuizStatus(quizId, newStatus) {
    try {
        const res = await fetch(`${API_BASE_URL}/api/teacher/toggle_publish`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ teacher_token: authToken, quiz_id: quizId, status: newStatus })
        });
        if (res.ok) loadTeacherQuizzes();
    } catch(e) {}
}

let monitorInterval;
let monitoringQuizId = null;

function startMonitoring(quizId, title) {
    monitoringQuizId = quizId;
    document.getElementById('teacherDashboard').style.display = 'none';
    document.getElementById('monitorDashboard').style.display = 'block';
    document.getElementById('monitorQuizTitle').innerText = "Đang giám sát: " + title;
    fetchMonitorData();
    monitorInterval = setInterval(fetchMonitorData, 5000); // Lấy dữ liệu 5s/lần
}

function stopMonitoring() {
    clearInterval(monitorInterval);
    monitoringQuizId = null;
    document.getElementById('monitorDashboard').style.display = 'none';
    document.getElementById('teacherDashboard').style.display = 'block';
}

async function fetchMonitorData() {
    if (!monitoringQuizId) return;
    try {
        const res = await fetch(`${API_BASE_URL}/api/teacher/monitor/${monitoringQuizId}?teacher_token=${authToken}`);
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            const tbody = document.getElementById('monitorTableBody');
            if (!data.data || data.data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding: 20px; color: var(--text-muted);">Chưa có học sinh nào tham gia...</td></tr>';
                document.getElementById('monitorCount').innerText = `Tổng số: 0 học sinh`;
                return;
            }
            
            data.data.sort((a, b) => {
                if (a.completed !== b.completed) return a.completed ? 1 : -1;
                if (a.is_online !== b.is_online) return a.is_online ? -1 : 1;
                return a.student_name.localeCompare(b.student_name);
            });
            
            tbody.innerHTML = data.data.map(s => {
                let status = s.completed ? '<span style="background:#d1fae5; color:#065f46; padding:4px 10px; border-radius:12px; font-size:0.85rem; font-weight:bold;">✅ Đã nộp bài</span>' : 
                             (s.is_online ? '<span style="background:#dbeafe; color:#1e40af; padding:4px 10px; border-radius:12px; font-size:0.85rem; font-weight:bold;">🟢 Đang làm</span>' : 
                             '<span style="background:#fee2e2; color:#991b1b; padding:4px 10px; border-radius:12px; font-size:0.85rem; font-weight:bold;">🔴 Mất kết nối</span>');
                let timeStr = s.time_remaining > 0 ? formatTime(s.time_remaining) : '--';
                return `<tr style="border-bottom: 1px solid var(--border);"><td style="padding: 12px 10px; font-weight: 600;">${s.student_name}</td><td style="padding: 12px 10px;">${status}</td><td style="padding: 12px 10px; font-weight:bold; color:var(--primary);">${s.answers_count} câu</td><td style="padding: 12px 10px;">${timeStr}</td></tr>`;
            }).join('');
            document.getElementById('monitorCount').innerText = `Tổng số: ${data.data.length} học sinh`;
        }
    } catch(e) {}
}

async function loadAdminSettings() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/get_api_key?admin_token=${authToken}`);
        const data = await res.json();
        if(res.ok && data.status === 'success') {
            adminApiKeys = data.api_keys || [];
            renderApiKeyList();
        }
    } catch(e) {}
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
            if (successMsg) alert(successMsg);
        }
    } catch(e) { alert("Lỗi lưu Key"); }
}

async function loadAdminUsers() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/users?admin_token=${authToken}`);
        const data = await res.json();
        if(res.ok && data.status === 'success') {
            let html = `<table style="width:100%; border-collapse: collapse; text-align:left;">
                <tr style="border-bottom: 2px solid var(--border); color: var(--text-muted);">
                    <th style="padding: 12px 10px;">Tài khoản</th>
                    <th style="padding: 12px 10px;">Họ tên</th>
                    <th style="padding: 12px 10px;">Vai trò</th>
                    <th style="padding: 12px 10px;">Trạng thái</th>
                    <th style="padding: 12px 10px;">Thao tác</th>
                </tr>`;
            data.data.forEach(u => {
                let roleStr = u.role === 'teacher' ? '👨‍🏫 Giáo viên' : (u.role === 'student' ? '👨‍🎓 Học sinh' : '🛡️ Admin');
                let statStr = u.status === 'approved' ? '<span style="color:var(--success); font-weight:bold;">Đã duyệt</span>' : '<span style="color:var(--danger); font-weight:bold;">Chờ duyệt</span>';
                let btn = u.status === 'pending' ? `<button class="btn-success" style="width:auto; margin:0; padding: 6px 12px; font-size:0.9rem;" onclick="approveUser('${u.id}')">Duyệt</button>` : '';
                let resetBtn = u.role !== 'admin' ? `<button class="btn-outline" style="width:auto; margin:0 0 0 8px; padding: 6px 12px; font-size:0.9rem; color: var(--primary); border-color: var(--primary);" onclick="resetUserPassword('${u.id}', '${u.username}')">Đổi MK</button>` : '';
                let delBtn = u.role !== 'admin' ? `<button class="btn-outline" style="width:auto; margin:0 0 0 8px; padding: 6px 12px; font-size:0.9rem; color: var(--danger); border-color: var(--danger);" onclick="deleteUser('${u.id}')">Xóa</button>` : '';
                html += `<tr style="border-bottom: 1px solid var(--border);">
                    <td style="padding: 12px 10px; font-weight: 600;">${u.username}</td>
                    <td style="padding: 12px 10px;">${u.full_name}</td>
                    <td style="padding: 12px 10px;">${roleStr}</td>
                    <td style="padding: 12px 10px;">${statStr}</td>
                    <td style="padding: 12px 10px;">${btn} ${resetBtn} ${delBtn}</td>
                </tr>`;
            });
            html += `</table>`;
            document.getElementById('adminUserList').innerHTML = html;
        }
    } catch(e) { alert("Lỗi tải danh sách người dùng"); }
}

async function approveUser(uid) {
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/approve`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({admin_token: authToken, user_id: uid}) });
        if(res.ok) loadAdminUsers();
    } catch(e) {}
}

async function deleteUser(uid) {
    if(!confirm("Bạn có chắc chắn muốn xóa tài khoản này?")) return;
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/delete`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({admin_token: authToken, user_id: uid}) });
        if(res.ok) loadAdminUsers();
    } catch(e) {}
}

async function resetUserPassword(uid, username) {
    const newPwd = prompt(`Nhập mật khẩu mới cho tài khoản "${username}":`);
    if (newPwd === null) return; // Nhấn Hủy
    
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/reset_password`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ admin_token: authToken, user_id: uid, new_password: newPwd.trim() })
        });
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            alert(`Đã đổi mật khẩu cho tài khoản "${username}" thành công!`);
        } else {
            alert("Lỗi: " + data.detail);
        }
    } catch(e) {
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
    if (!fileInput.files[0]) { alert("Vui lòng chọn file .docx!"); return; }
    
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    
    const useAI = document.getElementById('useAIToggle') ? document.getElementById('useAIToggle').checked : true;
    formData.append("use_ai", useAI);
    
    // Khởi tạo giao diện Progress Bar
    const loadingOverlay = document.getElementById('loadingOverlay');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const statusText = document.getElementById('loadingStatusText');
    
    loadingOverlay.style.display = 'flex';
    progressBar.style.width = '0%';
    progressText.innerText = '0%';
    statusText.innerText = '⚙️ Đang tải file lên máy chủ...';

    // Giả lập tiến trình chạy mượt mà
    let progress = 0;
    let progressInterval = setInterval(() => {
        if (progress < 30) {
            progress += Math.floor(Math.random() * 5) + 2; // Chạy nhanh đoạn đầu
        } else if (progress < 90) {
            if (useAI) {
                statusText.innerText = '🤖 AI đang bóc tách và phân tích câu hỏi...';
            } else {
                statusText.innerText = '⚡ Đang bóc tách bằng thuật toán Python tốc độ cao...';
            }
            progress += Math.floor(Math.random() * 2) + 1; // Chạy chậm dần đoạn giữa
        } else if (progress < 98) {
            statusText.innerText = '✨ Đang hoàn thiện định dạng...';
            progress += 0.2; // Chạy siêu chậm khi gần xong
        }
        if (progress > 98) progress = 98; // Giữ ở mức 98% chờ Server phản hồi
        progressBar.style.width = progress + '%';
        progressText.innerText = Math.floor(progress) + '%';
    }, 600);

    try {
        const response = await fetch(`${API_BASE_URL}/api/upload`, { method: 'POST', body: formData });
        const result = await response.json();
        
        // Nhận được kết quả -> Ép lên 100%
        clearInterval(progressInterval);
        progressBar.style.width = '100%';
        progressText.innerText = '100%';
        statusText.innerText = '✅ Hoàn tất!';
        await new Promise(resolve => setTimeout(resolve, 500)); // Đợi nửa giây cho người dùng thấy 100%
        
        if (result.status === "success") {
            currentData = result.data || [];
            serverData = JSON.parse(JSON.stringify(currentData));
            editingQuizId = null;
            window.tempQuizSettings = null; // Xóa setting cũ
            
            document.body.classList.add('editor-fullscreen');
            document.getElementById('teacherDashboard').style.display = 'none';
            document.getElementById('uploadBox').style.display = 'none';
            
            switchMode('edit');
            document.getElementById('saveBtn').style.display = 'block';
            document.getElementById('saveBtn').innerText = "⚙️ Tiếp tục & Cấu hình Xuất bản";
            if (authRole === 'teacher') document.getElementById('backDashboardBtn').style.display = 'block';
            document.getElementById('aiCustomPrompt').style.display = 'block';
            document.getElementById('btnAICheck').style.display = 'block';
            
            window.scrollTo(0,0);
        } else { alert("Lỗi: " + result.detail); }
    } catch (e) { 
        clearInterval(progressInterval);
        alert("Lỗi kết nối máy chủ! Có thể Server đang khởi động lại (Cold Start), hãy thử lại trong ít giây."); 
    }
    finally {
        clearInterval(progressInterval);
        document.getElementById('loadingOverlay').style.display = 'none';
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
    document.getElementById('btnAICheck').style.display = 'none';
    document.getElementById('aiFeedbackBox').style.display = 'none';
    document.getElementById('backDashboardBtn').style.display = 'none';
    document.getElementById('uploadBox').style.display = 'block';
    document.getElementById('teacherDashboard').style.display = 'block';
    loadTeacherQuizzes();
}

function openPublishModal() {
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
    
    try {
        const payload = { 
            title: title, data: currentData, mode: mode, time_limit: timeLimit, 
            is_shuffle: isShuffle, creator_id: authToken, status: "published" 
        };
        if (editingQuizId) payload.quiz_id = editingQuizId;

        const response = await fetch(`${API_BASE_URL}/api/save_quiz`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (result.status === 'success') {
            closePublishModal();
            const shareLink = window.location.origin + window.location.pathname + "?id=" + result.quiz_id;
            prompt(`Lưu thành công!\nMã đề: ${result.quiz_id}\n\nCopy đường link gọn gàng bên dưới để gửi học sinh:`, shareLink);
            editingQuizId = result.quiz_id;
            window.tempQuizSettings = { title, mode, timeLimit, isShuffle };
            
            if (confirm("Đã xuất bản thành công! Bạn có muốn quay về màn hình Quản lý không?")) {
                backToDashboard();
            }
        }
    } catch (e) { alert("Lỗi khi kết nối với máy chủ cơ sở dữ liệu!"); }
    btn.innerText = "🚀 Lưu & Xuất bản";
    btn.disabled = false;
}

async function checkQuizWithAI() {
    const btn = document.getElementById('btnAICheck');
    const customPrompt = document.getElementById('aiCustomPrompt').value.trim();
    btn.innerText = "⏳ Đang phân tích, vui lòng chờ khoảng 10-20 giây...";
    btn.disabled = true;
    try {
        const res = await fetch(`${API_BASE_URL}/api/teacher/check_quiz_ai`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({teacher_token: authToken, quiz_data: currentData, custom_prompt: customPrompt})
        });
        const data = await res.json();
        if (res.ok && data.status === 'success') {
            document.getElementById('aiFeedbackBox').style.display = 'block';
            let htmlFeedback = '';
            
            if (Array.isArray(data.feedback) && data.feedback.length > 0) {
                // Case 1: AI returns a structured array of corrections
                htmlFeedback = `<p style="margin-top:0; margin-bottom: 15px; font-weight: 600; color: #9333ea;">AI đã phát hiện ${data.feedback.length} vấn đề và đề xuất sửa như sau:</p>`;
                window.lastAIFeedback = data.feedback; // Lưu biến toàn cục để tránh lỗi vỡ HTML
                data.feedback.forEach((item, index) => {
                    htmlFeedback += `
                        <div class="ai-suggestion-item" style="border: 1px solid #d8b4fe; border-radius: 8px; padding: 15px; margin-bottom: 15px; background: #fff;">
                            <p style="margin-top:0;">
                                <strong style="color: var(--primary);">Câu ${item.question_index + 1}:</strong>
                                <span style="color: var(--danger);">${item.reason}</span>
                            </p>
                            <button class="btn-primary" style="padding: 6px 12px; font-size: 0.9rem;" onclick="applyAISuggestion(${index}, this)">✔️ Áp dụng sửa lỗi này</button>
                        </div>
                    `;
                });
            } else if (Array.isArray(data.feedback) && data.feedback.length === 0) {
                htmlFeedback = '✅ Tuyệt vời! AI không phát hiện thấy lỗi nào trong đề thi của bạn.';
            } else {
                htmlFeedback = (typeof data.feedback === 'string') ? data.feedback.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<b>$1</b>') : 'AI trả về định dạng không hợp lệ.';
            }

            document.getElementById('aiFeedbackContent').innerHTML = htmlFeedback;
            document.getElementById('aiFeedbackBox').scrollIntoView({behavior: 'smooth'});
        } else { alert("Lỗi AI: " + data.detail); }
    } catch(e) {
        alert("Lỗi kết nối tới máy chủ.");
    }
    btn.innerText = "🤖 AI Kiểm tra lỗi & Phân tích Đề thi";
    btn.disabled = false;
}

function applyAISuggestion(index, button) {
    const { question_index, corrected_data } = window.lastAIFeedback[index];

    if (currentData[question_index]) {
        const originalGroupTitle = currentData[question_index].group_title;

        currentData[question_index] = {
            ...corrected_data,
            group_title: corrected_data.group_title !== undefined ? corrected_data.group_title : originalGroupTitle
        };

        const codeEditor = document.getElementById('codeEditor');
        if (codeEditor) {
            codeEditor.value = dataToEditorText(currentData);
        }

        renderPreviewAll();

        button.innerText = "✅ Đã áp dụng!";
        button.disabled = true;
        button.style.backgroundColor = "var(--success)";

        const previewQuestion = document.querySelector(`#preview-content .question-box:nth-child(${question_index + 1})`);
        if (previewQuestion) {
            previewQuestion.scrollIntoView({ behavior: 'smooth', block: 'center' });
            previewQuestion.style.transition = 'background-color 1s ease';
            previewQuestion.style.backgroundColor = '#d1fae5';
            setTimeout(() => {
                previewQuestion.style.backgroundColor = '';
            }, 2000);
        }
        
    } else {
        alert(`Lỗi: Không tìm thấy câu hỏi với chỉ số ${question_index}.`);
    }
}

function renderData() {
    const container = document.getElementById('quiz-container');
    container.innerHTML = '';
    if (currentData.length === 0) { container.innerHTML = "<div class='card'>Không tìm thấy câu hỏi nào. Vui lòng kiểm tra lại định dạng file Word.</div>"; return; }
    
    document.getElementById('score-board').style.display = 'none';
    
    // Mở rộng Container khi ở chế độ chỉnh sửa
    const mainAppContainer = document.getElementById('mainAppContainer');
    if (currentMode === 'edit') {
        mainAppContainer.classList.add('wide-container');
    } else {
        mainAppContainer.classList.remove('wide-container');
    }

    if (currentMode === 'practice') {
        renderPracticeQuestion();
        return;
    }

    if (currentMode === 'edit') {
        container.innerHTML = `
            <div class="split-layout">
                <div class="preview-pane" id="preview-pane" style="padding: 0;">
                    <div style="background: #f8fafc; padding: 15px 20px; font-weight: 700; color: #0f172a; border-bottom: 1px solid #e2e8f0; position: sticky; top: 0; z-index: 10; display: flex; justify-content: space-between; align-items: center;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 1.3rem;">👁️</span> XEM TRƯỚC (GIAO DIỆN HỌC SINH)
                        </div>
                    </div>
                    <div id="preview-content" style="padding: 20px;"></div>
                </div>
                <div class="editor-pane" id="editor-pane" style="display: flex; flex-direction: column; padding: 0; background: #1e1e1e; overflow: hidden; border: 1px solid #333;">
                    <div style="background: #252526; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 10; border-bottom: 1px solid #333;">
                        <div style="font-weight: 700; color: #cccccc; display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 1.3rem;">💻</span> HOCNHANHTN CODE EDITOR
                        </div>
                        <div style="display: flex; gap: 10px;">
                            <button style="padding: 6px 14px; font-size: 0.85rem; font-weight: 600; background: #0e639c; border: none; color: white; border-radius: 4px; cursor: pointer; transition: background 0.2s;" onmouseover="this.style.background='#1177bb'" onmouseout="this.style.background='#0e639c'" onclick="insertTextToEditor('\\n\\nCâu mới: \\nA. \\nB. \\nC. \\nD. ')">➕ Thêm Câu hỏi</button>
                        </div>
                    </div>
                    <div style="background: #3a3d41; padding: 10px 20px; font-size: 0.9rem; color: #cccccc; border-bottom: 1px solid #333; display: flex; align-items: center; gap: 8px;">
                        <span>💡 <b>Mẹo:</b> Đặt dấu <code>*</code> trước đáp án đúng (VD: <code>*A.</code>). Click câu hỏi bên trái để tự động cuộn đến đoạn Code bên phải.</span>
                    </div>
                    <div style="flex-grow: 1; position: relative; background: #1e1e1e;">
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
                                color: #d4d4d4;
                                overflow: hidden;
                                pointer-events: none;
                            }
                            #codeEditor {
                                position: absolute;
                                top: 0; left: 0; right: 0; bottom: 0;
                                background: transparent;
                                color: transparent;
                                caret-color: #d4d4d4;
                                resize: none;
                                outline: none;
                                overflow-y: auto;
                            }
                            #codeEditor::selection { background: #264f78; color: transparent; }
                            #codeEditor::-webkit-scrollbar { width: 14px; }
                            #codeEditor::-webkit-scrollbar-track { background: #1e1e1e; }
                            #codeEditor::-webkit-scrollbar-thumb { background: #424242; border: 4px solid #1e1e1e; border-radius: 8px; }
                            #codeEditor::-webkit-scrollbar-thumb:hover { background: #4f4f4f; }
                            
                            /* Syntax Colors (Chuẩn VS Code Theme) */
                            .hl-question { color: #569cd6; font-weight: bold; }
                            .hl-option { color: #c586c0; font-weight: bold; }
                            .hl-correct { color: #10b981; font-weight: bold; }
                            .hl-image { color: #ce9178; }
                            .hl-math { color: #4ec9b0; }
                            .hl-group { color: #dcdcaa; font-weight: bold; }
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
    } else {
        // TỐI ƯU HIỆU SUẤT RENDER: Gộp thành 1 chuỗi lớn thay vì appendChild liên tục
        let htmlBuilder = "";
        currentData.forEach((q, qIndex) => {
            let groupTitleHtml = q.group_title ? `<div style="background: #fef9c3; padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; font-size: 0.9rem; font-weight: 600; color: #854d0e;">${q.group_title.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>` : '';
            let boxHtml = `<div class="card question-box" id="question_box_${qIndex}">`;
            boxHtml += `${groupTitleHtml}<div class="question-title">Câu ${qIndex + 1}: ${q.question.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>`;
            q.options.forEach((opt, oIndex) => {
                let char = opt.match(/^[A-F]/i) ? opt.match(/^[A-F]/i)[0].toUpperCase() : String.fromCharCode(65 + oIndex);
                let isChecked = quizProgress && quizProgress.answers && quizProgress.answers[qIndex] === opt;
                boxHtml += `
                    <label class="option-practice ${isChecked ? 'selected' : ''}" id="exam_opt_${qIndex}_${oIndex}">
                    <input type="radio" name="exam_${qIndex}" value="${escapeHtml(opt)}" onchange="selectExamOption(${qIndex}, ${oIndex})" ${isChecked ? 'checked' : ''}>
                        <span class="opt-badge">${char}</span>
                        <span class="opt-text">${opt.replace(/^[A-F][\.\:\)]\s*/i, '')}</span>
                    </label>`;
            });
            boxHtml += `</div>`;
            htmlBuilder += boxHtml;
        });
        container.innerHTML = htmlBuilder;
    }
    document.getElementById('aiCustomPrompt').style.display = currentMode === 'edit' ? 'block' : 'none';
    document.getElementById('btnAICheck').style.display = currentMode === 'edit' ? 'block' : 'none';
    if (currentMode !== 'edit') document.getElementById('aiFeedbackBox').style.display = 'none';
    document.getElementById('submitBtn').style.display = currentMode === 'exam' ? 'block' : 'none';
    renderMath();
}

function renderPracticeQuestion() {
    const container = document.getElementById('quiz-container');
    container.innerHTML = '';
    
    if (currentQuestionIndex >= currentData.length) {
        document.body.classList.add('quiz-completed'); // Mở khóa thanh cuộn toàn trang
        document.getElementById('score-board').style.display = 'block';
        document.getElementById('score-board').innerHTML = `Tiến trình hoàn tất! Bạn đúng <span style="color: var(--primary); font-size: 1.8rem;">${practiceScore}</span> / ${currentData.length} câu. 🎉<br>
            <div style="display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; margin-top: 20px;">
                <button class="btn-outline" onclick="showPracticeReview()" style="background: white; margin: 0;">🔍 Xem chi tiết bài làm</button>
                <button class="btn-primary" onclick="restartPractice()" style="margin: 0;">🔄 Luyện tập lại vòng mới</button>
            </div>`;
        
        if (isStudentMode && studentName && !quizProgress.completed) {
            let timeElapsed = startTime > 0 ? Math.floor((Date.now() - startTime) / 1000) : 0;
            
            quizProgress.completed = true;
            if (!quizProgress.history) quizProgress.history = [];
            quizProgress.history.push({
                score: practiceScore,
                total: currentData.length,
                timeElapsed: timeElapsed,
                date: new Date().toLocaleString('vi-VN'),
                mode: 'Luyện tập'
            });
            saveProgressToLocal();
            submitScoreToServer(practiceScore, currentData.length, timeElapsed);
        }
        return;
    }

    practiceAnswered = false;
    const q = currentData[currentQuestionIndex];
    const box = document.createElement('div');
    box.className = 'card question-box';
    
    let groupTitleHtml = q.group_title ? `<div style="background: #fef9c3; padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; font-size: 0.9rem; font-weight: 600; color: #854d0e;">${q.group_title.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>` : '';
    box.innerHTML += `${groupTitleHtml}<div class="question-title">Câu ${currentQuestionIndex + 1} / ${currentData.length}: ${q.question.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>`;
    
    q.options.forEach((opt, oIndex) => {
        let char = opt.match(/^[A-F]/i) ? opt.match(/^[A-F]/i)[0].toUpperCase() : String.fromCharCode(65 + oIndex);
        box.innerHTML += `
            <label class="option-practice" id="pract_opt_${oIndex}">
                <input type="radio" name="pract_radio" onclick="checkPracticeAnswer(${oIndex})">
                <span class="opt-badge">${char}</span>
                <span class="opt-text">${opt.replace(/^[A-F][\.\:\)]\s*/i, '')}</span>
            </label>`;
    });
    
    box.innerHTML += `<div id="pract_feedback" style="margin-top:20px; font-weight:600; font-size:1.1rem;"></div>`;
    
    container.appendChild(box);
    
    // Đưa nút ra khỏi khung câu hỏi, đẩy xuống dưới 1 chút và dạt sang phải
    const btnWrapper = document.createElement('div');
    btnWrapper.style.textAlign = 'right';
    btnWrapper.style.marginTop = '10px';
    btnWrapper.style.paddingBottom = '30px'; // Thêm khoảng đệm cho riêng nút bấm
    btnWrapper.innerHTML = `<button id="nextBtn" class="btn-primary" style="display:none; padding: 10px 24px; border-radius: 8px; font-weight: 600; font-size: 1rem; box-shadow: 0 2px 8px rgba(0,0,0,0.15);" onclick="nextPracticeQuestion()">Câu tiếp ➔</button>`;
    container.appendChild(btnWrapper);
    renderMath();
}

function selectExamOption(qIndex, oIndex) {
    currentData[qIndex].options.forEach((_, idx) => {
        const lbl = document.getElementById(`exam_opt_${qIndex}_${idx}`);
        if (lbl) lbl.classList.remove('selected');
    });
    const selectedLbl = document.getElementById(`exam_opt_${qIndex}_${oIndex}`);
    if (selectedLbl) selectedLbl.classList.add('selected');
    
    if (isStudentMode) {
        if (!quizProgress.answers) quizProgress.answers = {};
        quizProgress.answers[qIndex] = currentData[qIndex].options[oIndex];
        saveProgressToLocal();
    }
}

function checkPracticeAnswer(oIndex) {
    if (practiceAnswered) return;
    practiceAnswered = true;
    
    const q = currentData[currentQuestionIndex];
    q.user_answer_practice = q.options[oIndex]; // Lưu lại đáp án của học sinh để dùng cho phần xem lại
    const isCorrect = q.options[oIndex] === q.correct_answer;
    
    if (isCorrect) practiceScore++;
    
    q.options.forEach((opt, idx) => {
        const lbl = document.getElementById(`pract_opt_${idx}`);
        lbl.querySelector('input').disabled = true;
        
        if (idx === oIndex) lbl.classList.add('selected'); // Đánh dấu khối đang chọn
        
        if (opt === q.correct_answer) lbl.classList.add('correct');
        else if (idx === oIndex && !isCorrect) lbl.classList.add('incorrect');
    });
    
    const feedback = document.getElementById('pract_feedback');
    let correctAnswerDisplay = q.correct_answer ? q.correct_answer.replace(/^[A-D][\.\:\)]\s*/i, '') : "Chưa xác định";
    feedback.innerHTML = isCorrect ? `<span style="color:var(--success);">✅ Trả lời chính xác!</span>` : `<span style="color:var(--danger);">❌ Sai rồi! Đáp án đúng là: ${correctAnswerDisplay}</span>`;
    
    document.getElementById('nextBtn').style.display = 'inline-block';
    if (currentQuestionIndex === currentData.length - 1) document.getElementById('nextBtn').innerText = 'Xem kết quả tổng kết';
    
    // Tự động cuộn trượt màn hình xuống nút "Câu tiếp" mượt mà
    setTimeout(() => {
        document.getElementById('nextBtn').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 100);
}

function nextPracticeQuestion() {
    currentQuestionIndex++;
    renderPracticeQuestion();
}

function showPracticeReview() {
    const container = document.getElementById('quiz-container');
    container.innerHTML = '';
    
    currentData.forEach((q, qIndex) => {
        const box = document.createElement('div');
        box.className = 'card question-box';
        
        let groupTitleHtml = q.group_title ? `<div style="background: #fef9c3; padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; font-size: 0.9rem; font-weight: 600; color: #854d0e;">${q.group_title.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>` : '';
        box.innerHTML += `${groupTitleHtml}<div class="question-title">Câu ${qIndex + 1}: ${q.question.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>`;
        
        q.options.forEach((opt, oIndex) => {
            let char = opt.match(/^[A-F]/i) ? opt.match(/^[A-F]/i)[0].toUpperCase() : String.fromCharCode(65 + oIndex);
            
            let extraClass = '';
            let isSelected = opt === q.user_answer_practice;
            if (isSelected) extraClass += ' selected ';
            if (opt === q.correct_answer) {
                extraClass += ' correct ';
            } else if (isSelected && opt !== q.correct_answer) {
                extraClass += ' incorrect ';
            }
            
            box.innerHTML += `
                <label class="option-practice ${extraClass.trim()}" style="cursor: default;">
                    <input type="radio" disabled ${isSelected ? 'checked' : ''}>
                    <span class="opt-badge">${char}</span>
                    <span class="opt-text">${opt.replace(/^[A-F][\.\:\)]\s*/i, '')}</span>
                </label>`;
        });
        container.appendChild(box);
    });
    renderMath();
}

function shuffleQuiz(noRender = false) {
    for (let i = currentData.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [currentData[i], currentData[j]] = [currentData[j], currentData[i]];
    }
    currentData.forEach(q => {
        // 1. Chuẩn hóa lại số thứ tự câu hỏi (Xóa "Câu X:" cũ nếu có)
        q.question = q.question.replace(/^(?:(?:Câu|Bài|Question|Q)\s*\d+\s*[\.\:\-\)]|\d+\s*[\.\:\)])\s*/i, '');
        
        // 2. Trộn ngẫu nhiên các đáp án
        for (let i = q.options.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [q.options[i], q.options[j]] = [q.options[j], q.options[i]];
        }
        
        // 3. Đánh lại nhãn A, B, C, D và cập nhật đáp án đúng theo vị trí mới
        let newCorrect = null;
        q.options = q.options.map((opt, oIndex) => {
            let cleanOpt = opt.replace(/^[A-F][\.\:\)]\s*/i, '');
            let newOpt = String.fromCharCode(65 + oIndex) + ". " + cleanOpt;
            if (opt === q.correct_answer) newCorrect = newOpt;
            return newOpt;
        });
        if (newCorrect) q.correct_answer = newCorrect;
    });
    currentQuestionIndex = 0;
    practiceScore = 0;
    if (!noRender) renderData();
}

function switchMode(mode) {
    currentMode = mode;
    document.getElementById('btnEdit').className = mode === 'edit' ? 'btn-outline active' : 'btn-outline';
    document.getElementById('btnPractice').className = mode === 'practice' ? 'btn-outline active' : 'btn-outline';
    document.getElementById('btnExam').className = mode === 'exam' ? 'btn-outline active' : 'btn-outline';
    document.getElementById('btnShuffle').style.display = mode === 'edit' ? 'none' : 'inline-block';
    
    // Ẩn bảng xếp hạng và Timer dọn dẹp khi chuyển chế độ hoặc làm lại bài
    const lb = document.getElementById('leaderboard');
    if (lb) lb.style.display = 'none';
    clearInterval(timerInterval);
    const timerDisplay = document.getElementById('timerDisplay');
    if (timerDisplay) timerDisplay.style.display = 'none';

    document.body.classList.remove('quiz-completed');
    if (isStudentMode) {
        startTime = Date.now(); // Bắt đầu bấm giờ
        quizProgress.completed = false; // Sẵn sàng ghi nhận cho vòng mới
    }
    currentQuestionIndex = 0;
    practiceScore = 0;
    renderData();
}

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
                optText = optText.replace(/^([A-F])([\.\:\)])/i, '*$1$2'); // Đánh dấu sao cho đáp án đúng
            }
            text += `${optText}\n`;
        });
        text += "\n";
    });
    
    text = text.trim();
    
    // Xóa bộ nhớ cũ mỗi lần generate lại code cho editor
    globalEditorImageStorage = {};
    globalEditorImageCounter = 0;
    
    // Tìm toàn bộ thẻ <img> chứa mã Base64 cực dài và thay bằng [HÌNH_ẢNH_X]
    const imgRegex = /<img[^>]+src=['"]data:[^'"]+['"][^>]*>/gi;
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
    
    // Quét lại nếu chưa có đáp án đúng thì lấy mặc định đáp án A
    data.forEach(q => {
        if (!q.correct_answer && q.options.length > 0) { q.correct_answer = q.options[0]; }
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
        prevBox.style.marginBottom = '24px';
        prevBox.style.cursor = 'pointer';
        prevBox.title = 'Nhấn để nhảy tới mã Code của câu này';
        prevBox.onclick = () => scrollToQuestionInEditor(qIndex);
        
        let html = "";
        let groupTitleHtml = q.group_title ? `<div style="background: #fef9c3; padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; font-size: 0.9rem; font-weight: 600; color: #854d0e;">${q.group_title.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>` : '';
        let qClean = q.question.replace(/^(?:(?:Câu|Bài|Question|Q)\s*\d+\s*[\.\:\-\)]|\d+\s*[\.\:\)])\s*/i, '');
        
        html += `${groupTitleHtml}<div class="question-title">Câu ${qIndex + 1}: ${qClean.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>`;
        q.options.forEach((opt, oIndex) => {
            let isCorrect = q.correct_answer === opt;
            html += `<label class="option-practice ${isCorrect ? 'correct selected' : ''}" style="cursor: default;">
                        <input type="radio" disabled ${isCorrect ? 'checked' : ''}>
                        <span class="opt-badge">${opt.match(/^[A-F]/i) ? opt.match(/^[A-F]/i)[0].toUpperCase() : String.fromCharCode(65 + oIndex)}</span>
                        <span class="opt-text">${opt.replace(/^[A-F][\.\:\)]\s*/i, '')}</span>
                    </label>`;
        });
        prevBox.innerHTML = html;
        previewContent.appendChild(prevBox);
    });

    if (window.MathJax && typeof window.MathJax.typesetPromise === 'function') {
        MathJax.typesetPromise([previewContent]).catch((err) => console.log('MathJax error:', err));
    }
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
    let timeRemaining = minutes * 60;
    
    if (isStudentMode && quizProgress && quizProgress.timeRemaining !== undefined && quizProgress.timeRemaining !== null && !quizProgress.completed) {
        timeRemaining = quizProgress.timeRemaining; // Phục hồi đồng hồ
    }
    const timerDisplay = document.getElementById('timerDisplay');
    timerDisplay.style.display = 'block';
    
    function updateDisplay() {
        const m = Math.floor(timeRemaining / 60).toString().padStart(2, '0');
        const s = (timeRemaining % 60).toString().padStart(2, '0');
        timerDisplay.innerText = `⏳ ${m}:${s}`;
        if (timeRemaining <= 60) {
            timerDisplay.style.animation = "pulse-red 1s infinite";
        }
    }
    updateDisplay();
    
    timerInterval = setInterval(() => {
        timeRemaining--;
        if (isStudentMode) {
            quizProgress.timeRemaining = timeRemaining;
            if (timeRemaining % 5 === 0) saveProgressToLocal(); // Cứ 5 giây lưu đồng hồ 1 lần
        }
        if (timeRemaining < 0) {
            clearInterval(timerInterval);
            alert("⏳ Đã hết thời gian làm bài! Hệ thống tự động nộp bài.");
            submitExam();
            return;
        }
        updateDisplay();
    }, 1000);
}

function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m} phút ${s} giây`;
}

async function submitScoreToServer(score, total, time) {
    const urlParams = new URLSearchParams(window.location.search);
    const quizId = urlParams.get('quiz_id') || urlParams.get('id');
    if (!quizId) return;
    try {
        await fetch(`${API_BASE_URL}/api/submit_score`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ quiz_id: quizId, student_name: studentName, score: score, total_questions: total, time_elapsed: time })
        });
        fetchLeaderboard(quizId);
    } catch(e) { console.log(e); }
}

async function fetchLeaderboard(quizId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/leaderboard/${quizId}`);
        const result = await response.json();
        if (result.status === 'success') {
            const lb = document.getElementById('leaderboard');
            const lbList = document.getElementById('leaderboardList');
            lb.style.display = 'block';
            
            let html = `<table style="width:100%; border-collapse: collapse; text-align:left; min-width: 500px;">
                <tr style="border-bottom: 2px solid var(--border); color: var(--text-muted);">
                    <th style="padding: 12px 10px;">Hạng</th>
                    <th style="padding: 12px 10px;">Họ Tên</th>
                    <th style="padding: 12px 10px;">Điểm</th>
                    <th style="padding: 12px 10px;">Thời gian</th>
                </tr>`;
            
            result.data.forEach((item, index) => {
                let rank = index + 1;
                let medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : rank;
                let isMe = item.student_name === studentName;
                html += `
                    <tr style="border-bottom: 1px solid var(--border); ${isMe ? 'background-color: #fef9c3; font-weight:bold;' : ''}">
                        <td style="padding: 12px 10px; font-size: 1.2rem;">${medal}</td>
                        <td style="padding: 12px 10px;">${item.student_name} ${isMe ? '<span style="color:var(--success); font-size:0.8rem;">(Bạn)</span>' : ''}</td>
                        <td style="padding: 12px 10px; color: var(--primary); font-weight: bold; font-size: 1.1rem;">${item.score} / ${currentData.length}</td>
                        <td style="padding: 12px 10px; color: var(--text-muted);">${formatTime(item.time_elapsed)}</td>
                    </tr>`;
            });
            html += `</table>`;
            lbList.innerHTML = html;
        }
    } catch(e) { console.log(e); }
}

function submitExam(isReview = false) {
    clearInterval(timerInterval);
    const timerDisplay = document.getElementById('timerDisplay');
    if (timerDisplay) timerDisplay.style.display = 'none';
    
    let sessionTime = startTime > 0 ? Math.floor((Date.now() - startTime) / 1000) : 0;
    let totalTimeElapsed = isReview ? (quizProgress.timeElapsed || 0) : ((quizProgress.timeElapsed || 0) + sessionTime);
    let score = 0;
    
    currentData.forEach((q, qIndex) => {
        let userAnswer = null;
        if (isReview && quizProgress && quizProgress.answers) {
            userAnswer = quizProgress.answers[qIndex];
        } else {
            const selected = document.querySelector(`input[name="exam_${qIndex}"]:checked`);
            userAnswer = selected ? selected.value : null;
        }
        
        // Tự động check vào đáp án trên giao diện nếu đang xem lại (Review)
        if (isReview && userAnswer) {
            const oIndex = q.options.indexOf(userAnswer);
            if(oIndex !== -1) {
                const r = document.querySelector(`#exam_opt_${qIndex}_${oIndex} input`);
                if(r) r.checked = true;
                const lbl = document.getElementById(`exam_opt_${qIndex}_${oIndex}`);
                if(lbl) lbl.classList.add('selected');
            }
        }
        
        q.options.forEach((opt, oIndex) => {
            document.getElementById(`exam_opt_${qIndex}_${oIndex}`).classList.remove('correct', 'incorrect');
            document.querySelector(`#exam_opt_${qIndex}_${oIndex} input`).disabled = true;
        });
        
        q.options.forEach((opt, oIndex) => {
            if (opt === q.correct_answer) {
                document.getElementById(`exam_opt_${qIndex}_${oIndex}`).classList.add('correct');
            } else if (opt === userAnswer && userAnswer !== q.correct_answer) {
                document.getElementById(`exam_opt_${qIndex}_${oIndex}`).classList.add('incorrect');
            }
        });
        
        if (userAnswer === q.correct_answer) score++;
    });
    
    document.getElementById('submitBtn').style.display = 'none'; // Ẩn nút nộp bài
    document.body.classList.add('quiz-completed'); // Cho phép cuộn trang thoải mái
    
    const scoreBoard = document.getElementById('score-board');
    scoreBoard.style.display = 'block';
    scoreBoard.innerHTML = `Kết quả thi: <span style="color: var(--primary); font-size: 1.8rem;">${score}</span> / ${currentData.length} câu chính xác! 🎉<br>
                            <span style="font-size: 1.1rem; color: var(--text-muted);">⏱ Thời gian: ${formatTime(totalTimeElapsed)}</span><br>
                            <div style="display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; margin-top: 15px;">
                                <button class="btn-outline" style="margin: 0;" onclick="document.getElementById('quiz-container').scrollIntoView({behavior: 'smooth'})">👇 Xem chi tiết sai/đúng</button>
                                <button class="btn-primary" style="margin: 0;" onclick="restartExam()">🔄 Thi lại vòng mới</button>
                            </div>`;
    
    if (!isReview && isStudentMode && studentName) { 
        if (!quizProgress.answers) quizProgress.answers = {};
        currentData.forEach((q, qIndex) => {
            const selected = document.querySelector(`input[name="exam_${qIndex}"]:checked`);
            if (selected) quizProgress.answers[qIndex] = selected.value;
        });
        quizProgress.completed = true;
        quizProgress.score = score;
        quizProgress.timeElapsed = totalTimeElapsed;
        
        if (!quizProgress.history) quizProgress.history = [];
        quizProgress.history.push({
            score: score,
            total: currentData.length,
            timeElapsed: totalTimeElapsed,
            date: new Date().toLocaleString('vi-VN'),
            mode: 'Thi thử'
        });
        
        saveProgressToLocal();
        
        submitScoreToServer(score, currentData.length, totalTimeElapsed); 
        sendPing(); // Gửi ping xác nhận báo Đã hoàn thành
    }
    
    const quizContainer = document.getElementById('quiz-container');
    if (quizContainer) quizContainer.scrollTo({ top: 0, behavior: 'smooth' });
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function exitMinimalMode() {
    if (confirm("Bạn có muốn tạm dừng và thoát khỏi giao diện làm bài không? (Tiến trình của bạn vẫn được bảo lưu)")) {
        document.body.classList.remove('minimal-mode');
        document.body.classList.remove('quiz-completed');
        if (document.fullscreenElement) {
            document.exitFullscreen().catch(err => console.log(err));
        }
        window.location.reload(); // Tải lại trang để reset giao diện và đưa về màn hình Welcome
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