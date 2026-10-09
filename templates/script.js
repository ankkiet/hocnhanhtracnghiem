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
    // Nếu deploy giao diện (Frontend) tách biệt trên các host tĩnh
    API_BASE_URL = PROD_BACKEND_URL;
} else {
    // Được phục vụ bởi backend (ngrok, localhost, IP, domain riêng trỏ về server)
    API_BASE_URL = window.location.origin;
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
window.getHntnLoaderSvgHtml = getHntnLoaderSvgHtml;
window.renderHntnInlineLoader = renderHntnInlineLoader;
window.resetHntnLoader = resetHntnLoader;

// Khởi tạo bộ nhớ tạm để thu gọn mã Base64 ảnh trong Code Editor
let globalEditorImageStorage = {};
let globalEditorImageCounter = 0;

// Lưu trữ danh sách gợi ý sửa lỗi của AI gắn với từng câu hỏi
window.activeAIFeedbacks = {};

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

// Biến quản lý xác thực Google Sign-In
let googleClientId = '';
let googleTokenClient = null;

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
    initGoogleAuth();
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
        mainSubmit.style.display = (currentMode === 'exam') ? 'block' : 'none';
    }
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
    if (mainApp) mainApp.style.display = 'none';
    if (adminBox) adminBox.style.display = 'none';
    if (azotaNav) azotaNav.style.display = 'none';
    if (authBox) {
        authBox.classList.remove('hidden');
        authBox.style.setProperty('display', 'flex', 'important');
        authBox.style.justifyContent = 'center';
        authBox.style.alignItems = 'center';
        authBox.style.minHeight = '85vh';
        authBox.style.width = '100%';
    }

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
    if (mainApp) mainApp.style.display = 'none';
    if (adminBox) adminBox.style.display = 'none';
    if (azotaNav) azotaNav.style.display = 'none';
    if (authBox) {
        authBox.classList.remove('hidden');
        authBox.style.setProperty('display', 'flex', 'important');
        authBox.style.justifyContent = 'center';
        authBox.style.alignItems = 'center';
        authBox.style.minHeight = '85vh';
        authBox.style.width = '100%';
    }

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
        if (res.ok) {
            if (data.status === 'success') {
                localStorage.setItem('auth_token', data.token);
                localStorage.setItem('auth_role', data.role);
                localStorage.setItem('auth_name', data.full_name);
                authToken = data.token;
                authRole = data.role;
                authName = data.full_name;
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
    
    try {
        const res = await fetch(`${API_BASE_URL}/api/auth/check_approval_status?user_id=${currentPendingUserId}`);
        const data = await res.json();
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
    const loginForm = document.getElementById('loginForm');
    if (loginForm) loginForm.style.setProperty('display', 'flex', 'important');
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

        // Mở popup đăng nhập bằng tài khoản Google chính chủ Firebase
        const result = await window.signInWithPopup(window.firebaseAuth, window.googleProvider);
        const user = result.user;
        const idToken = await user.getIdToken();

        // Gửi token về Backend để đồng bộ tài khoản và tạo JWT Token
        const res = await fetch(`${API_BASE_URL}/api/auth/google`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ credential: idToken })
        });

        const data = await res.json();
        if (res.ok) {
            if (data.status === 'success') {
                localStorage.setItem('auth_token', data.token);
                localStorage.setItem('auth_role', data.role);
                localStorage.setItem('auth_name', data.full_name);
                authToken = data.token;
                authRole = data.role;
                authName = data.full_name;
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

function checkAuthState() {
    const urlParams = new URLSearchParams(window.location.search);
    const quizId = urlParams.get('quiz_id') || urlParams.get('id');
    const authBox = document.getElementById('authContainer');
    const azotaNav = document.getElementById('azotaNavbar');
    const mainApp = document.getElementById('mainAppContainer');
    const adminBox = document.getElementById('adminContainer');

    // NẾU CÓ QUIZ ID TRÊN URL (Học sinh mở link làm bài kiểm tra)
    if (quizId) {
        if (authBox) {
            authBox.classList.add('hidden');
            authBox.style.setProperty('display', 'none', 'important');
        }
        if (adminBox) adminBox.style.display = 'none';
        if (mainApp) mainApp.style.display = 'block';
        if (azotaNav) azotaNav.style.display = 'block';

        // Ẩn thanh tab chuyển đổi khi đang thi
        const navLinks = document.getElementById('azotaNavLinks');
        if (navLinks) navLinks.style.display = 'none';

        if (authToken && authName) {
            updateNavbarUser(authName, authRole);
            const sNameInput = document.getElementById('studentNameInput');
            if (sNameInput) sNameInput.value = authName;
        } else {
            // Khách tự do vào làm bài
            const userBadge = document.getElementById('azotaUserBadge');
            if (userBadge) {
                userBadge.innerHTML = `
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-size: 0.9rem; color: #64748b; font-weight: 600;"><i class="ri-user-smile-line"></i> Thí sinh tự do</span>
                </div>`;
            }
        }

        initApp();
        return;
    }

    if (!authToken) {
        if (azotaNav) azotaNav.style.display = 'none';
        if (authBox) {
            authBox.classList.remove('hidden');
            authBox.style.setProperty('display', 'flex', 'important');
            authBox.style.justifyContent = 'center';
            authBox.style.alignItems = 'center';
            authBox.style.minHeight = '85vh';
            authBox.style.width = '100%';
        }
        if (mainApp) mainApp.style.display = 'none';
        if (adminBox) adminBox.style.display = 'none';
        
        const loginForm = document.getElementById('loginForm');
        const registerForm = document.getElementById('registerForm');
        hideRoleScreens();
        if (loginForm) loginForm.style.setProperty('display', 'flex', 'important');
        if (registerForm) registerForm.style.setProperty('display', 'none', 'important');
    } else if (authRole === 'admin') {
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
    } else {
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
        } else if (authRole === 'teacher') {
            document.getElementById('studentDashboard').style.display = 'none';
            document.getElementById('teacherDashboard').style.display = 'block';
            loadTeacherQuizzes();
        }
        initApp();
    }
}

function updateNavbarUser(name, role) {
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
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    if (!loginForm || !registerForm) return;

    if(type === 'register') {
        loginForm.style.setProperty('display', 'none', 'important');
        registerForm.style.setProperty('display', 'flex', 'important');
    } else {
        loginForm.style.setProperty('display', 'flex', 'important');
        registerForm.style.setProperty('display', 'none', 'important');
    }
}

async function handleLogin() {
    const uInput = document.getElementById('email') || document.getElementById('loginUsername');
    const pInput = document.getElementById('password') || document.getElementById('loginPassword');
    const u = uInput ? uInput.value.trim() : '';
    const p = pInput ? pInput.value.trim() : '';
    if(!u || !p) return alert("Vui lòng nhập đầy đủ email/tên đăng nhập và mật khẩu");
    
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
            hideRoleScreens();
            checkAuthState();
        } else {
            if ((res.status === 403 || data.status === 'pending_approval') && (data.detail || '').includes("chờ Quản trị viên")) {
                showPendingApproval(null, u, u);
            } else {
                alert("Lỗi: " + (data.detail || data.message || "Đăng nhập thất bại."));
            }
        }
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
            alert(data.message || "Đăng ký thành công!");
            if (r === 'teacher') {
                showPendingApproval(null, fn, u);
            } else {
                toggleAuth('login');
            }
        } else { alert("Lỗi: " + (data.detail || "Đăng ký thất bại.")); }
    } catch(e) { alert("Lỗi kết nối máy chủ"); }
}

function logout() {
    localStorage.clear();
    window.location.href = window.location.pathname; // Tải lại trang xóa query param
}

/* ========================================================
   GOOGLE SIGN-IN CLIENT LOGIC (ĐÃ CHUYỂN SANG FIREBASE AUTH)
   ======================================================== */




// Hàm trợ giúp trích xuất mã đề thi từ query param (?id=, ?quiz_id=) hoặc URL path (/quiz/...)
function getCurrentQuizId() {
    const urlParams = new URLSearchParams(window.location.search);
    let quizId = urlParams.get('quiz_id') || urlParams.get('id');
    if (!quizId) {
        const path = window.location.pathname.replace(/^\/|\/$/g, '');
        if (path.startsWith('quiz/')) {
            quizId = path.split('/')[1];
        } else if (path && path.length >= 5 && path.length <= 15 && !path.includes('.html') && !path.includes('/')) {
            quizId = path;
        }
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
            const response = await fetch(`${API_BASE_URL}/api/get_quiz/${quizId}?teacher_token=${authToken || ''}`);
            const result = await response.json();
            if (result.status === 'success') {
                document.getElementById('quiz-container').innerHTML = '';
                currentData = normalizeImageUrls(result.data);
                currentData.forEach((q, i) => { q._originalIndex = i; });
                serverData = JSON.parse(JSON.stringify(currentData));
                const serverUpdatedAt = result.updated_at || 0;
                
                // Cập nhật tiêu đề trang web
                if (result.title) {
                    document.title = `${result.title} - HocNhanhTN`;
                }

                // --- Thiết lập Giao diện Dành riêng cho Học sinh ---
                const oldHeader = document.querySelector('.header');
                if (oldHeader) oldHeader.style.display = 'none';
                document.getElementById('studentHeader').style.display = 'none'; // Chỉ hiển thị sau khi bấm Bắt đầu
                document.getElementById('studentQuizTitle').innerText = result.title;
                document.getElementById('studentQCount').innerHTML = `🏷 Số câu: ${currentData.length}` + (result.is_shuffle ? ` <span style="color: var(--success); font-size: 0.85rem; background: #d1fae5; padding: 2px 6px; border-radius: 4px; margin-left: 5px;">🔀 Đã trộn ngẫu nhiên</span>` : '');
                
                currentTimeLimit = result.time_limit || 0;
                const examTimerVal = document.getElementById('examTimerVal');
                if (currentTimeLimit > 0) {
                    document.getElementById('studentTime').innerText = `⏳ Thời gian: ${currentTimeLimit} phút`;
                    if (examTimerVal) examTimerVal.innerText = `${currentTimeLimit}:00`;
                } else {
                    document.getElementById('studentTime').innerText = `⏳ Thời gian: Tự do`;
                    if (examTimerVal) examTimerVal.innerText = `Tự do`;
                }
                updateStudentNameDisplay('Thí sinh');
                
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
                        
                        let localTs = quizProgress.quizUpdatedAt || 0;
                        if (serverUpdatedAt > 0 && localTs < serverUpdatedAt) {
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

                // Kích hoạt nạp ngầm mô hình WebLLM qua Web Worker ngay khi học sinh vào phòng thi (nếu bật tính năng)
                if (window.ENABLE_WEBLLM && window.WebLLMTutor) {
                    window.WebLLMTutor.preload();
                }
            } else { document.getElementById('quiz-container').innerHTML = "<p style='text-align:center;'>Bài thi không tồn tại hoặc đã bị xóa.</p>"; }
        } catch (e) {
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

async function startStudentQuiz() {
    const nameInput = document.getElementById('studentNameInput').value.trim();
    studentName = nameInput;
    
    const quizId = getCurrentQuizId();

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
                    serverData = normalizeImageUrls(result.data);
                    serverData.forEach((q, i) => { q._originalIndex = i; });
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
    resetSubmissionReviewUI();
    document.getElementById('studentHeader').style.display = 'block';
    updateStudentNameDisplay(studentName);
    document.body.classList.add('minimal-mode');
    const mobileBar = document.getElementById('azotaMobileExamBar');
    if (mobileBar && (currentDataMode === 'exam' || currentDataMode === 'practice')) mobileBar.style.setProperty('display', 'flex', 'important');
    if (document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(err => console.log("Fullscreen error:", err));
    }
    
    switchMode(currentDataMode); 
    if (currentDataMode === 'exam' && currentTimeLimit > 0) { startTimer(currentTimeLimit); }
    
    // Đảm bảo WebLLM được nạp ngầm qua Web Worker (nếu bật tính năng)
    if (window.ENABLE_WEBLLM && window.WebLLMTutor) {
        window.WebLLMTutor.preload();
    }
    
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
    resetSubmissionReviewUI();
    const urlParams = new URLSearchParams(window.location.search);
    const quizId = urlParams.get('quiz_id') || urlParams.get('id');
    
    const container = document.getElementById('quiz-container');
    if (container) container.innerHTML = renderHntnInlineLoader('Đang tải dữ liệu mới nhất...', 'Hệ thống đang đồng bộ với máy chủ...', 85);
    
    if (quizId) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/get_quiz/${quizId}?teacher_token=${authToken || ''}`);
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
    
    updateStudentNameDisplay(studentName);
    
    switchMode(mode);
    if (mode === 'exam' && currentTimeLimit > 0) { 
        startTimer(currentTimeLimit); 
    } else {
        clearInterval(timerInterval);
        const timerVal = document.getElementById('examTimerVal');
        if (timerVal) timerVal.innerText = currentTimeLimit > 0 ? `${currentTimeLimit}:00` : 'Tự do';
    }
    
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
        
        // Gửi Ping Real-time ngay lập tức khi học sinh thao tác
        if (isStudentMode && !quizProgress.completed) {
            sendPing();
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
                    <button class="btn-azota-sub" onclick="showQuizAnalytics('${q.id}', '${(q.title || '').replace(/'/g, "\\'")}')" title="Xem phổ điểm">
                        <i class="ri-bar-chart-grouped-line"></i> Điểm
                    </button>
                    <button class="btn-azota-sub" onclick="startMonitoring('${q.id}', '${(q.title || '').replace(/'/g, "\\'")}')" title="Giám sát trực tiếp">
                        <i class="ri-live-line"></i> Giám sát
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

async function loadTeacherQuizzes() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/teacher/quizzes?teacher_token=${authToken}`);
        const data = await res.json();
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

function copyQuizLink(quizId) {
    if (!quizId) return;
    const origin = (window.location.origin && window.location.origin !== "null") ? window.location.origin : "";
    let path = window.location.pathname;
    if (path.endsWith('editor.html')) path = path.replace('editor.html', 'index.html');
    const fullUrl = `${origin}${path}?id=${quizId}`;
    navigator.clipboard.writeText(fullUrl).then(() => {
        showToast("Đã sao chép Link làm bài thi cho học sinh!", 'success');
    }).catch(() => {
        prompt("Copy Link làm bài thi:", fullUrl);
    });
}

function exportQuizDocx(quizId) {
    window.open(`${API_BASE_URL}/api/teacher/export_docx/${quizId}?teacher_token=${authToken}`, '_blank');
}

async function showQuizAnalytics(quizId, quizTitle) {
    try {
        const modal = document.getElementById('analyticsModal');
        const content = document.getElementById('analyticsContent');
        if (!modal || !content) return;
        
        modal.style.display = 'flex';
        content.innerHTML = renderHntnInlineLoader('Đang phân tích dữ liệu bài thi...', 'Hệ thống đang tính toán phổ điểm và thống kê câu hỏi...', 85);
        
        const res = await fetch(`${API_BASE_URL}/api/teacher/quiz_analytics/${quizId}?teacher_token=${authToken}`);
        const data = await res.json();
        
        if (!res.ok || data.status !== 'success') {
            content.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:12px; margin-bottom:15px;">
                    <h3 style="margin:0; color:var(--danger);">⚠️ Lỗi</h3>
                    <button class="btn-outline" style="padding:4px 10px; margin:0;" onclick="closeAnalyticsModal()">Đóng ✕</button>
                </div>
                <p style="color:var(--danger);">${data.detail || 'Không thể tải dữ liệu thống kê.'}</p>
            `;
            return;
        }
        
        if (data.total_submissions === 0) {
            content.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:12px; margin-bottom:15px;">
                    <h3 style="margin:0; color:var(--primary);">📊 Báo cáo Phổ điểm</h3>
                    <button class="btn-outline" style="padding:4px 10px; margin:0;" onclick="closeAnalyticsModal()">Đóng ✕</button>
                </div>
                <div style="text-align:center; padding:30px; color:var(--text-muted);">
                    <h4>${quizTitle}</h4>
                    <p>Chưa có học sinh nào nộp bài kiểm tra này để thống kê.</p>
                </div>
            `;
            return;
        }
        
        let bandsHtml = "";
        const bands = data.score_bands;
        const maxBandVal = Math.max(...Object.values(bands), 1);
        
        for (const [band, count] of Object.entries(bands)) {
            const pct = Math.round((count / data.total_submissions) * 100);
            const barWidth = Math.round((count / maxBandVal) * 100);
            bandsHtml += `
                <div style="margin-bottom: 10px;">
                    <div style="display:flex; justify-content:space-between; font-size:0.85rem; margin-bottom:3px;">
                        <span>Điểm <b>${band}</b></span>
                        <span><b>${count}</b> học sinh (${pct}%)</span>
                    </div>
                    <div style="background:#e2e8f0; border-radius:4px; height:12px; overflow:hidden;">
                        <div style="background:var(--primary); height:100%; width:${barWidth}%; border-radius:4px; transition:width 0.5s;"></div>
                    </div>
                </div>
            `;
        }
        
        let hardestHtml = "";
        if (data.hardest_questions && data.hardest_questions.length > 0) {
            hardestHtml = `
                <div style="margin-top:20px;">
                    <h4 style="color:#b91c1c; margin-bottom:10px;">⚠️ Các câu hỏi học sinh hay làm sai nhất:</h4>
                    <div style="display:flex; flex-direction:column; gap:8px;">
            `;
            data.hardest_questions.forEach(hq => {
                hardestHtml += `
                    <div style="background:#fef2f2; border-left:4px solid #ef4444; padding:10px 12px; border-radius:6px; font-size:0.9rem;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                            <b>Câu ${hq.question_index}</b>
                            <span style="color:#dc2626; font-weight:bold;">Tỷ lệ làm đúng: ${hq.accuracy_rate}% (${hq.correct_count}/${data.total_submissions})</span>
                        </div>
                        <div style="color:#334155;">${hq.question_preview}</div>
                    </div>
                `;
            });
            hardestHtml += `</div></div>`;
        }
        
        content.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:12px; margin-bottom:15px;">
                <div>
                    <h3 style="margin:0; color:var(--primary);">📊 Phổ Điểm & Báo Cáo Phân Tích</h3>
                    <div style="color:var(--text-muted); font-size:0.9rem;">${quizTitle}</div>
                </div>
                <button class="btn-outline" style="padding:4px 10px; margin:0;" onclick="closeAnalyticsModal()">Đóng ✕</button>
            </div>
            
            <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(120px, 1fr)); gap:10px; margin-bottom:20px;">
                <div style="background:#f8fafc; padding:12px; border-radius:8px; text-align:center; border:1px solid var(--border);">
                    <div style="font-size:0.8rem; color:var(--text-muted);">Tổng bài nộp</div>
                    <div style="font-size:1.5rem; font-weight:bold; color:var(--primary);">${data.total_submissions}</div>
                </div>
                <div style="background:#f8fafc; padding:12px; border-radius:8px; text-align:center; border:1px solid var(--border);">
                    <div style="font-size:0.8rem; color:var(--text-muted);">Điểm TB</div>
                    <div style="font-size:1.5rem; font-weight:bold; color:#0284c7;">${data.average_score}</div>
                </div>
                <div style="background:#f8fafc; padding:12px; border-radius:8px; text-align:center; border:1px solid var(--border);">
                    <div style="font-size:0.8rem; color:var(--text-muted);">Điểm cao nhất</div>
                    <div style="font-size:1.5rem; font-weight:bold; color:#059669;">${data.max_score}</div>
                </div>
                <div style="background:#f8fafc; padding:12px; border-radius:8px; text-align:center; border:1px solid var(--border);">
                    <div style="font-size:0.8rem; color:var(--text-muted);">Điểm thấp nhất</div>
                    <div style="font-size:1.5rem; font-weight:bold; color:#e11d48;">${data.min_score}</div>
                </div>
            </div>
            
            <div style="background:#ffffff; border:1px solid var(--border); padding:15px; border-radius:8px; margin-bottom:15px;">
                <h4 style="margin-top:0; margin-bottom:12px; color:var(--text);">📈 Phân bố điểm số (Thang 10):</h4>
                ${bandsHtml}
            </div>
            
            ${hardestHtml}
        `;
    } catch(err) {
        console.error("Lỗi showQuizAnalytics", err);
    }
}

function closeAnalyticsModal() {
    const modal = document.getElementById('analyticsModal');
    if (modal) modal.style.display = 'none';
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

function editQuiz(quizId) {
    window.location.href = `editor.html?id=${encodeURIComponent(quizId)}`;
}

function openStudioNewQuiz() {
    sessionStorage.removeItem('editor_quiz_id');
    sessionStorage.removeItem('editor_quiz_data');
    sessionStorage.removeItem('editor_quiz_title');
    sessionStorage.removeItem('editor_quiz_settings');
    window.location.href = 'editor.html';
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

let monitorEventSource = null;

function startMonitoring(quizId, title) {
    monitoringQuizId = quizId;
    document.getElementById('teacherDashboard').style.display = 'none';
    document.getElementById('monitorDashboard').style.display = 'block';
    document.getElementById('monitorQuizTitle').innerText = "Đang giám sát: " + title;
    
    if (typeof monitorInterval !== 'undefined') clearInterval(monitorInterval);
    
    // Gọi API lấy dữ liệu giám sát
    async function fetchMonitorData() {
        if (!monitoringQuizId) return;
        try {
            const res = await fetch(`${API_BASE_URL}/api/teacher/monitor/${monitoringQuizId}?teacher_token=${authToken}`);
            if (!res.ok) return;
            const data = await res.json();
            if (data.status === 'success') {
                const dataList = Object.values(data.data || {});
                renderMonitorData(dataList);
            }
        } catch(e) {
            console.error("Monitor fetch error:", e);
        }
    }
    
    // Polling mỗi 3 giây
    fetchMonitorData();
    monitorInterval = setInterval(fetchMonitorData, 3000);
}

function stopMonitoring() {
    if (typeof monitorInterval !== 'undefined') clearInterval(monitorInterval);
    monitoringQuizId = null;
    document.getElementById('monitorDashboard').style.display = 'none';
    document.getElementById('teacherDashboard').style.display = 'block';
}

function renderMonitorData(dataList) {
    const tbody = document.getElementById('monitorTableBody');
    if (!dataList || dataList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px; color: var(--text-muted);">Chưa có học sinh nào tham gia...</td></tr>';
        document.getElementById('monitorCount').innerText = `Tổng số: 0 học sinh`;
        return;
    }
    
    dataList.sort((a, b) => {
        if (a.completed !== b.completed) return a.completed ? 1 : -1;
        if (a.is_online !== b.is_online) return a.is_online ? -1 : 1;
        return a.student_name.localeCompare(b.student_name);
    });
    
    tbody.innerHTML = dataList.map(s => {
        let timeStr = (s.time_elapsed && s.time_elapsed > 0) ? formatTime(s.time_elapsed) : '--';
        let scoreStr = '--';
        let correctStr = '--';
        if (s.score !== null) {
            let scaledScore = (s.total_questions > 0) ? ((s.score / s.total_questions) * 10).toFixed(1) : s.score;
            scoreStr = `<span style="font-weight: 800; color: #16a34a; font-size: 1.1rem;">${scaledScore}đ</span>`;
            correctStr = `<span style="font-weight:bold; color:var(--primary);">${s.score} / ${s.total_questions}</span>`;
        }
        
        const detailsObj = btoa(unescape(encodeURIComponent(JSON.stringify(s))));
        
        return `<tr style="border-bottom: 1px solid var(--border); cursor: pointer; transition: background 0.2s;" onmouseover="this.style.background='#f3f4f6'" onmouseout="this.style.background='transparent'" onclick="showStudentDetails('${detailsObj}')">
            <td style="padding: 12px 10px; font-weight: 600;">
                ${escapeHtml(s.student_name)}
                <div style="font-size: 0.8rem; color: #065f46; margin-top: 4px;">✅ Đã nộp bài</div>
            </td>
            <td style="padding: 12px 10px;">${correctStr}</td>
            <td style="padding: 12px 10px;">${timeStr}</td>
            <td style="padding: 12px 10px; text-align: center;">${scoreStr}</td>
        </tr>`;
    }).join('');
    document.getElementById('monitorCount').innerText = `Tổng số: ${dataList.length} học sinh`;
}

window.showStudentDetails = function(b64data) {
    try {
        const s = JSON.parse(decodeURIComponent(escape(atob(b64data))));
        const modal = document.getElementById('studentDetailsModal');
        const body = document.getElementById('studentDetailsBody');
        
        let status = s.completed ? '<span style="color:#065f46; font-weight:bold;">✅ Đã nộp bài</span>' : 
                     (s.is_online ? '<span style="color:#1e40af; font-weight:bold;">🟢 Đang làm bài (Online)</span>' : 
                     '<span style="color:#991b1b; font-weight:bold;">🔴 Mất kết nối (Offline)</span>');
                     
        let scoreStr = (s.completed && s.score !== null) ? `<strong style="color: #16a34a; font-size: 1.2rem;">${((s.score / s.total_questions) * 10).toFixed(1)} điểm</strong> (Đúng ${s.score}/${s.total_questions} câu)` : '<em>Chưa có điểm</em>';
        
        body.innerHTML = `
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed var(--border);">
                <span style="color: var(--text-muted);">Tên học sinh:</span>
                <strong style="font-size: 1.1rem;">${escapeHtml(s.student_name)}</strong>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed var(--border);">
                <span style="color: var(--text-muted);">Trạng thái:</span>
                ${status}
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed var(--border);">
                <span style="color: var(--text-muted);">Thời gian làm bài:</span>
                <strong>${s.time_elapsed > 0 ? formatTime(s.time_elapsed) : '--'}</strong>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0; background: #f8fafc; border-radius: 8px; margin-top: 8px; padding: 12px;">
                <span style="color: var(--text-muted);">Kết quả:</span>
                ${scoreStr}
            </div>
        `;
        
        modal.style.display = 'flex';
    } catch(e) {
        console.error(e);
        alert("Lỗi khi mở chi tiết học sinh.");
    }
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
            if (successMsg) alert(successMsg);
        }
    } catch(e) { alert("Lỗi lưu Key"); }
}

async function loadAdminUsers() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/users?admin_token=${authToken}`);
        const data = await res.json();
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
            document.getElementById('adminUserList').innerHTML = html;
        }
    } catch(e) { alert("Lỗi tải danh sách người dùng"); }
}

async function approveUser(uid) {
    try {
        const res = await fetch(`${API_BASE_URL}/api/admin/approve`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({admin_token: authToken, user_id: uid}) });
        if(res.ok) {
            alert("✅ Đã phê duyệt tài khoản thành công!");
            loadAdminUsers();
        } else {
            alert("Lỗi khi duyệt tài khoản");
        }
    } catch(e) {
        alert("Lỗi kết nối máy chủ");
    }
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
    window.activeAIFeedbacks = {};
    document.getElementById('btnAICheck').style.display = 'none';
    document.getElementById('aiFeedbackBox').style.display = 'none';
    document.getElementById('backDashboardBtn').style.display = 'none';
    document.getElementById('creationHub').style.display = 'flex';
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
    btn.innerText = "⏳ Đang rà soát và thống kê toàn bộ đề thi (10-20s)...";
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
                    catChipsHtml += `<span class="ai-cat-chip ai-cat-delete">🗑️ Yêu cầu xóa: <b>${stats.category_counts.delete}</b></span>`;
                }
                if (stats.category_counts?.restructure > 0) {
                    catChipsHtml += `<span class="ai-cat-chip ai-cat-restructure">🔄 Đổi kết cấu: <b>${stats.category_counts.restructure}</b></span>`;
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
    }
    btn.innerText = "🤖 AI Kiểm tra lỗi & Phân tích Đề thi";
    btn.disabled = false;
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

        const catClass = isDelete ? 'ai-cat-delete' :
                         (isRestructure ? 'ai-cat-restructure' :
                         (item.category === 'knowledge' ? 'ai-cat-knowledge' :
                         (item.category === 'answer' ? 'ai-cat-answer' :
                         (item.category === 'grammar_typo' ? 'ai-cat-grammar' : 'ai-cat-format'))));

        let actionBtnHtml = '';
        if (isDelete) {
            actionBtnHtml = `<button class="btn-ai-delete" onclick="applyAIDelete(${qIdx})"><i class="ri-delete-bin-line"></i> Xóa câu</button>`;
        } else if (isRestructure) {
            actionBtnHtml = `<button class="btn-ai-restructure" onclick="applyAISuggestion(${qIdx})"><i class="ri-swap-line"></i> Đổi kết cấu</button>`;
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

    if (currentMode === 'practice') {
        renderPracticeQuestion();
        return;
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
    } else {
        // CHẾ ĐỘ THI THỬ / EXAM MODE
        const examLayout = document.getElementById('azotaExamLayout');
        if (examLayout) examLayout.style.display = '';
        const sideCol = document.getElementById('azotaSideExamCol');
        if (sideCol) sideCol.style.display = '';

        let htmlBuilder = "";
        let navGridHtml = "";
        let answeredCount = 0;

        currentData.forEach((q, qIndex) => {
            let groupTitleHtml = q.group_title ? `<div style="background: #fef9c3; padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; font-size: 0.9rem; font-weight: 600; color: #854d0e;">${q.group_title.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>` : '';
            
            let isAnswered = quizProgress && quizProgress.answers && (quizProgress.answers[qIndex] !== undefined && quizProgress.answers[qIndex] !== '');
            if (isAnswered) answeredCount++;
            let isFlagged = !!flaggedQuestions[qIndex];

            // Render nút tương ứng trên Bảng câu hỏi (Desktop side palette & Mobile drawer)
            navGridHtml += `
                <button type="button" class="azota-nav-num nav-num-btn nav-num-${qIndex} ${isAnswered ? 'answered' : ''} ${isFlagged ? 'flagged' : ''}" id="nav_num_${qIndex}" data-qindex="${qIndex}" onclick="scrollToQuestion(${qIndex})" title="Chuyển đến Câu ${qIndex + 1}">
                    ${qIndex + 1}
                </button>
            `;

            let qType = getRealQuestionType(q);
            let typeBadge = '';
            if (qType === 'true_false') {
                typeBadge = '<span style="background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; margin-left: 8px; border: 1px solid #bae6fd;">Đúng / Sai</span>';
            } else if (qType === 'short_answer') {
                typeBadge = '<span style="background: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 700; margin-left: 8px; border: 1px solid #fde68a;">Trả lời ngắn</span>';
            }

            let cleanQText = (q.question || '').replace(/^(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])\s*/i, '');
            let boxHtml = `
                <div class="card question-box azota-question-card" id="question_box_${qIndex}">
                    ${groupTitleHtml}
                    <div class="azota-q-header">
                        <span class="azota-q-num">Câu ${qIndex + 1} ${typeBadge}</span>
                        <button type="button" class="btn-flag-q ${isFlagged ? 'flagged' : ''}" id="flag_btn_${qIndex}" onclick="toggleFlagQuestion(${qIndex})">
                            <i class="ri-flag-${isFlagged ? 'fill' : 'line'}"></i> ${isFlagged ? 'Đang phân vân' : 'Đánh dấu xem lại'}
                        </button>
                    </div>
                    <div class="question-title azota-q-text">${cleanQText.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>
            `;

            if (qType === 'true_false') {
                // Giao diện trắc nghiệm Đúng / Sai
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
                // Giao diện trắc nghiệm Trả lời ngắn
                let userSA = (quizProgress && quizProgress.answers && typeof quizProgress.answers[qIndex] === 'string') ? quizProgress.answers[qIndex] : '';
                boxHtml += `
                    <div class="azota-sa-box">
                        <div style="font-weight: 600; margin-bottom: 8px; color: var(--azota-text-muted);">✍️ Nhập câu trả lời ngắn của bạn:</div>
                        <input type="text" class="azota-sa-input" id="exam_sa_${qIndex}" value="${escapeHtml(userSA)}" placeholder="Điền đáp số hoặc kết quả..." oninput="selectExamShortAnswer(${qIndex}, this.value)">
                    </div></div>`;
            } else {
                // Giao diện MCQ 4 lựa chọn
                boxHtml += `<div class="azota-opt-list">`;
                (q.options || []).forEach((opt, oIndex) => {
                    let char = opt.match(/^[A-F]/i) ? opt.match(/^[A-F]/i)[0].toUpperCase() : String.fromCharCode(65 + oIndex);
                    let isChecked = quizProgress && quizProgress.answers && quizProgress.answers[qIndex] === opt;
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
        const navGrid = document.getElementById('azotaNavGrid');
        if (navGrid) navGrid.innerHTML = navGridHtml;
        const mobileNavGrid = document.getElementById('azotaMobileNavGrid');
        if (mobileNavGrid) mobileNavGrid.innerHTML = navGridHtml;
        updateNavProgressBadge();
    }
    document.getElementById('aiCustomPrompt').style.display = currentMode === 'edit' ? 'block' : 'none';
    document.getElementById('btnAICheck').style.display = currentMode === 'edit' ? 'block' : 'none';
    if (currentMode !== 'edit') document.getElementById('aiFeedbackBox').style.display = 'none';
    const mobileBar = document.getElementById('azotaMobileExamBar');
    if (currentMode === 'edit') {
        const sideCol = document.getElementById('azotaSideExamCol');
        if (sideCol) sideCol.style.setProperty('display', 'none', 'important');
        if (mobileBar) mobileBar.style.display = 'none';
    } else {
        if (currentMode !== 'exam') {
            const sideCol = document.getElementById('azotaSideExamCol');
            if (sideCol) sideCol.style.setProperty('display', 'none', 'important');
        } else {
            const sideCol = document.getElementById('azotaSideExamCol');
            if (sideCol) sideCol.style.setProperty('display', 'block', 'important');
        }
        if (mobileBar && isStudentMode) {
            mobileBar.style.setProperty('display', 'flex', 'important');
        }
    }
    document.getElementById('submitBtn').style.display = currentMode === 'exam' ? 'block' : 'none';
    renderMath(container);
}

function renderPracticeQuestion() {
    const container = document.getElementById('quiz-container');
    container.innerHTML = '';
    
    if (currentQuestionIndex >= currentData.length) {
        submitExam();
        return;
    }

    practiceAnswered = false;
    window.currentPracticeTF = {};
    const q = currentData[currentQuestionIndex];
    const qType = getRealQuestionType(q);
    const box = document.createElement('div');
    box.className = 'card question-box';
    
    let groupTitleHtml = q.group_title ? `<div style="background: #fef9c3; padding: 8px 12px; border-radius: 8px; margin-bottom: 10px; font-size: 0.9rem; font-weight: 600; color: #854d0e;">${q.group_title.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}</div>` : '';
    let typeBadge = '';
    if (qType === 'true_false') {
        typeBadge = ' <span style="background:#e0f2fe; color:#0369a1; padding:2px 8px; border-radius:6px; font-size:0.8rem; font-weight:700;">Đúng / Sai</span>';
    } else if (qType === 'short_answer') {
        typeBadge = ' <span style="background:#fef3c7; color:#92400e; padding:2px 8px; border-radius:6px; font-size:0.8rem; font-weight:700;">Trả lời ngắn</span>';
    }

    let cleanQText = (q.question || '').replace(/^(?:(?:\[|\()?\s*(?:Câu|Bài|Question|Q)\s*\d+[\.\:\-\/\)]?\s*(?:\]|\))?|\d+[\.\:\)\/])\s*/i, '');
    box.innerHTML += `${groupTitleHtml}<div class="question-title">Câu ${currentQuestionIndex + 1} / ${currentData.length}: ${cleanQText.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')}${typeBadge}</div>`;
    
    if (qType === 'true_false') {
        box.innerHTML += `<div style="display: flex; flex-direction: column; gap: 10px; margin-top: 15px;">`;
        (q.options || []).forEach((opt, oIndex) => {
            let charMatch = opt.match(/^[a-d]/);
            let char = charMatch ? charMatch[0].toLowerCase() : String.fromCharCode(97 + oIndex);
            let optClean = opt.replace(/^[a-d][\.\:\)]\s*/, '');
            box.innerHTML += `
                <div class="azota-tf-row" id="pract_tf_${char}" style="display:flex; align-items:center; justify-content:space-between; padding:10px 14px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px;">
                    <div style="flex:1; margin-right:12px; font-size:0.95rem; color:#1e293b;">
                        <b style="color:var(--azota-primary); margin-right:6px;">${char})</b> ${optClean}
                    </div>
                    <div class="azota-tf-btn-group" style="display:flex; gap:6px;">
                        <button type="button" class="azota-tf-btn" id="pract_tf_btn_${char}_t" onclick="selectPracticeTF('${char}', true)">Đúng</button>
                        <button type="button" class="azota-tf-btn" id="pract_tf_btn_${char}_f" onclick="selectPracticeTF('${char}', false)">Sai</button>
                    </div>
                </div>`;
        });
        box.innerHTML += `</div>
        <div style="margin-top: 15px; text-align: right;">
            <button id="pract_tf_check_btn" class="btn-primary" onclick="checkPracticeTF()" style="padding: 9px 20px; margin: 0;">Kiểm tra đáp án</button>
        </div>`;
    } else if (qType === 'short_answer') {
        box.innerHTML += `
            <div style="margin-top: 15px; display: flex; flex-direction: column; gap: 10px;">
                <div style="display: flex; gap: 8px;">
                    <input type="text" id="pract_sa_input" class="azota-sa-input" placeholder="Nhập câu trả lời ngắn của bạn..." style="flex: 1; padding: 12px 14px; font-size: 1rem; border: 2px solid #cbd5e1; border-radius: 8px;" onkeydown="if(event.key==='Enter') checkPracticeShortAnswer()">
                    <button id="pract_sa_check_btn" class="btn-primary" style="margin: 0; padding: 10px 20px;" onclick="checkPracticeShortAnswer()">Kiểm tra</button>
                </div>
            </div>`;
    } else {
        (q.options || []).forEach((opt, oIndex) => {
            let char = opt.match(/^[A-F]/i) ? opt.match(/^[A-F]/i)[0].toUpperCase() : String.fromCharCode(65 + oIndex);
            box.innerHTML += `
                <label class="option-practice" id="pract_opt_${oIndex}">
                    <input type="radio" name="pract_radio" onclick="checkPracticeAnswer(${oIndex})">
                    <span class="opt-badge">${char}</span>
                    <span class="opt-text">${opt.replace(/^[A-F][\.\:\)]\s*/i, '')}</span>
                </label>`;
        });
    }
    
    box.innerHTML += `<div id="pract_feedback" style="margin-top:20px; font-weight:600; font-size:1.05rem;"></div>`;
    
    container.appendChild(box);
    
    // Đưa nút ra khỏi khung câu hỏi, đẩy xuống dưới 1 chút và dạt sang phải
    const btnWrapper = document.createElement('div');
    btnWrapper.style.textAlign = 'right';
    btnWrapper.style.marginTop = '10px';
    btnWrapper.style.paddingBottom = '30px'; // Thêm khoảng đệm cho riêng nút bấm
    btnWrapper.innerHTML = `<button id="nextBtn" class="btn-primary desktop-only-submit" style="display:none; padding: 10px 24px; border-radius: 8px; font-weight: 600; font-size: 1rem; box-shadow: 0 2px 8px rgba(0,0,0,0.15);" onclick="nextPracticeQuestion()">Câu tiếp ➔</button>`;
    container.appendChild(btnWrapper);
    renderMath();
}


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
            flagBtn.innerHTML = `<i class="ri-flag-line"></i> Đánh dấu`;
        }
    }
    document.querySelectorAll(`.nav-num-${qIndex}`).forEach(btn => {
        if (isFlagged) btn.classList.add('flagged');
        else btn.classList.remove('flagged');
    });
}

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
    
    if (q.explain) {
        feedback.innerHTML += `<div style="margin-top:10px; padding:10px 14px; background:#f0fdf4; border-left:4px solid #22c55e; border-radius:6px; font-size:0.95rem; color:#166534;">💡 <b>Lời giải:</b> ${q.explain}</div>`;
    }
    
    // Tích hợp Gia sư ảo AI cục bộ (WebLLM)
    attachWebLLMTutorToFeedback(feedback, q, q.user_answer_practice, !isCorrect);
    
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
    const userAnswers = window.currentPracticeTF || {};
    q.user_answer_practice = userAnswers;
    const correctMap = (typeof q.correct_answer === 'object' && q.correct_answer) ? q.correct_answer : {};
    
    let matchCount = 0;
    ['a', 'b', 'c', 'd'].forEach(char => {
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
            else btnF.classList.add('correct-state');
            if (userVal === true && !isMatched) btnT.classList.add('wrong-state');
            else if (userVal === false && !isMatched) btnF.classList.add('wrong-state');
        }
    });
    
    const checkBtn = document.getElementById('pract_tf_check_btn');
    if (checkBtn) checkBtn.disabled = true;
    
    // Scale GDPT 2018
    const tfScale = [0.0, 0.1, 0.25, 0.5, 1.0];
    const earned = tfScale[matchCount] !== undefined ? tfScale[matchCount] : 0.0;
    practiceScore += earned;
    practiceScore = Math.round(practiceScore * 100) / 100;
    
    const feedback = document.getElementById('pract_feedback');
    feedback.innerHTML = `<span style="color: ${matchCount === 4 ? 'var(--success)' : '#d97706'}; font-weight:700;">
        ${matchCount === 4 ? '🎉 Đúng toàn bộ 4 ý (+1.0 điểm)!' : `📝 Bạn đúng ${matchCount}/4 ý (+${earned} điểm)`}
    </span>`;
    if (q.explain) {
        feedback.innerHTML += `<div style="margin-top:10px; padding:10px 14px; background:#f0fdf4; border-left:4px solid #22c55e; border-radius:6px; font-size:0.95rem; color:#166534;">💡 <b>Lời giải:</b> ${q.explain}</div>`;
    }
    
    // Tích hợp Gia sư ảo AI cục bộ (WebLLM)
    attachWebLLMTutorToFeedback(feedback, q, q.user_answer_practice, matchCount < 4);
    
    showNextQuestionButton();
}

function checkPracticeShortAnswer() {
    if (practiceAnswered) return;
    practiceAnswered = true;
    const q = currentData[currentQuestionIndex];
    const inputEl = document.getElementById('pract_sa_input');
    const userVal = inputEl ? inputEl.value.trim() : '';
    q.user_answer_practice = userVal;
    
    const uClean = userVal.toLowerCase().replace(',', '.').replace(/\s+/g, '');
    const cClean = String(q.correct_answer || '').trim().toLowerCase().replace(',', '.').replace(/\s+/g, '');
    const isCorrect = Boolean(uClean && uClean === cClean);
    
    if (isCorrect) practiceScore += 1;
    if (inputEl) {
        inputEl.disabled = true;
        if (isCorrect) inputEl.classList.add('correct');
        else inputEl.classList.add('incorrect');
    }
    const checkBtn = document.getElementById('pract_sa_check_btn');
    if (checkBtn) checkBtn.disabled = true;
    
    const feedback = document.getElementById('pract_feedback');
    feedback.innerHTML = isCorrect ? 
        `<span style="color:var(--success); font-weight:700;">✅ Trả lời chính xác (+1.0 điểm)!</span>` : 
        `<span style="color:var(--danger); font-weight:700;">❌ Chưa chính xác! Đáp án đúng là: <u>${escapeHtml(String(q.correct_answer || ''))}</u></span>`;
        
    if (q.explain) {
        feedback.innerHTML += `<div style="margin-top:10px; padding:10px 14px; background:#f0fdf4; border-left:4px solid #22c55e; border-radius:6px; font-size:0.95rem; color:#166534;">💡 <b>Lời giải:</b> ${q.explain}</div>`;
    }
    
    // Tích hợp Gia sư ảo AI cục bộ (WebLLM)
    attachWebLLMTutorToFeedback(feedback, q, q.user_answer_practice, !isCorrect);
    showNextQuestionButton();
}

function nextPracticeQuestion() {
    currentQuestionIndex++;
    renderPracticeQuestion();
}

function showPracticeReview() {
    submitExam(true);
}

function shuffleQuiz(noRender = false) {
    // QUAN TRỌNG: Ghi nhớ chỉ số gốc TRƯỚC khi trộn để submitExam gửi đúng index cho server
    // Chỉ gán lần đầu (nếu chưa có), tránh ghi đè khi người dùng trộn lại nhiều lần
    currentData.forEach((q, idx) => {
        if (q._originalIndex === undefined) q._originalIndex = idx;
    });

    for (let i = currentData.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [currentData[i], currentData[j]] = [currentData[j], currentData[i]];
    }
    currentData.forEach(q => {
        // 1. Chuẩn hóa lại số thứ tự câu hỏi (Xóa "Câu X:" cũ nếu có)
        q.question = q.question.replace(/^(?:(?:Câu|Bài|Question|Q)\s*\d+\s*[\.\:\-\)]|\d+\s*[\.\:\)])\s*/i, '');
        
        // 2. Chỉ trộn ngẫu nhiên các đáp án cho dạng câu hỏi MCQ có options
        const isMcq = (!q.type || q.type === 'mcq') && Array.isArray(q.options) && q.options.length > 0 && typeof q.correct_answer === 'string';
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


function switchMode(mode) {
    currentMode = mode;
    document.getElementById('btnEdit').className = mode === 'edit' ? 'btn-outline active' : 'btn-outline';
    document.getElementById('btnPractice').className = mode === 'practice' ? 'btn-outline active' : 'btn-outline';
    document.getElementById('btnExam').className = mode === 'exam' ? 'btn-outline active' : 'btn-outline';
    document.getElementById('btnShuffle').style.display = mode === 'edit' ? 'none' : 'inline-block';
    
    // Dọn dẹp các thành phần sau nộp bài và timer khi chuyển chế độ hoặc làm lại bài
    resetSubmissionReviewUI();
    clearInterval(timerInterval);
    const timerDisplay = document.getElementById('timerDisplay');
    if (timerDisplay) timerDisplay.style.display = 'none';
    if (isStudentMode) {
        startTime = Date.now(); // Bắt đầu bấm giờ
        quizProgress.completed = false; // Sẵn sàng ghi nhận cho vòng mới
    }
    currentQuestionIndex = 0;
    practiceScore = 0;
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
                let isCorrect = (q.correct_answer === opt);
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

        html += `${groupTitleHtml}<div class="question-title">Câu ${qIndex + 1}: ${qClean.replace(/(?:\r\n|\r|\n|\\n)/g, '<br>')} ${typeBadge}</div>`;

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
                let isCorrect = q.correct_answer === opt;
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

        prevBox.innerHTML = html;
        
        // KIỂM TRA VÀ CHÈN UI GỢI Ý CỦA AI VÀO NGAY DƯỚI CÂU HỎI
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
    let timeRemaining = minutes * 60;
    
    if (isStudentMode && quizProgress && quizProgress.timeRemaining !== undefined && quizProgress.timeRemaining !== null && !quizProgress.completed) {
        timeRemaining = quizProgress.timeRemaining; // Phục hồi đồng hồ
    }
    const timerDisplay = document.getElementById('timerDisplay');
    const stickyTimer = document.getElementById('examStickyTimer');
    if (timerDisplay) timerDisplay.style.display = 'none';
    if (stickyTimer) stickyTimer.style.display = 'flex';
    
    function updateDisplay() {
        const m = Math.floor(timeRemaining / 60).toString().padStart(2, '0');
        const s = (timeRemaining % 60).toString().padStart(2, '0');
        if (timerDisplay) timerDisplay.innerText = `⏳ ${m}:${s}`;
        const examTimerVal = document.getElementById('examTimerVal');
        if (examTimerVal) examTimerVal.innerText = `${m}:${s}`;
        if (timeRemaining <= 60) {
            if (timerDisplay) timerDisplay.style.animation = "pulse-red 1s infinite";
            if (stickyTimer) stickyTimer.style.animation = "pulse-red 1s infinite";
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
            showToast("⏳ Đã hết thời gian làm bài! Hệ thống tự động nộp bài.", "warning");
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

// --- HÀM SO KHỚP CHÍNH XÁC ĐÁP ÁN (HỖ TRỢ CẢ KÝ TỰ A,B,C,D VÀ NỘI DUNG OPTION) ---
function matchOptionToTarget(opt, oIndex, target) {
    if (target === null || target === undefined || target === '') return false;
    const optStr = String(opt || '').trim();
    const tgtStr = String(target).trim();
    if (!optStr || !tgtStr) return false;

    // 1. So khớp chuỗi trực tiếp
    if (optStr.toLowerCase() === tgtStr.toLowerCase()) return true;

    // 2. Chữ cái đại diện của Option ('A', 'B', 'C', 'D'...)
    let optChar = null;
    const rePrefix = /^([A-Fa-f0-9])(?:[\.\:\)]\s*|\s+|$)/i;
    const optMatch = optStr.match(rePrefix);
    if (optMatch) {
        optChar = optMatch[1].toUpperCase();
    } else {
        optChar = String.fromCharCode(65 + oIndex);
    }

    // 3. Chữ cái đại diện của Target
    let tgtChar = null;
    if (tgtStr.length === 1 && /^[A-Fa-f0-9]$/i.test(tgtStr)) {
        tgtChar = tgtStr.toUpperCase();
    } else {
        const tgtMatch = tgtStr.match(rePrefix);
        if (tgtMatch) tgtChar = tgtMatch[1].toUpperCase();
    }

    // Nếu target là chữ cái đơn (ví dụ 'A', 'B', 'A.')
    if (tgtChar && optChar && tgtChar === optChar) {
        return true;
    }

    // 4. So sánh sau khi loại bỏ prefix A. B. C. D.
    const cleanOpt = optStr.replace(/^[A-Fa-f0-9][\.\:\)]\s*/i, '').trim().toLowerCase();
    const cleanTgt = tgtStr.replace(/^[A-Fa-f0-9][\.\:\)]\s*/i, '').trim().toLowerCase();
    if (cleanOpt && cleanTgt && cleanOpt === cleanTgt) {
        return true;
    }

    return false;
}

// Biến lưu trạng thái tab kết quả hiện tại ('review' hoặc 'leaderboard')
window.currentResultView = 'review';

// --- HÀM CHUYỂN ĐỔI TAB SAU KHI NỘP BÀI: XEM LỜI GIẢI <-> BẢNG XẾP HẠNG ---
function switchResultView(viewType) {
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
            setTimeout(() => {
                const headerOffset = 90;
                const elementPosition = lb.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
                window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
            }, 60);
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

    const urlParams = new URLSearchParams(window.location.search);
    const quizId = urlParams.get('quiz_id') || urlParams.get('id');
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

        // Cập nhật số lượng thí sinh
        if (badgeEl) badgeEl.innerText = `${listData.length} thí sinh tham gia`;
        if (tabLbBadge) tabLbBadge.innerText = `${listData.length} thí sinh`;

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
                    <div class="azota-podium-slot rank-1" style="margin: 0 auto; min-width: 220px;">
                        <div class="azota-podium-avatar"><span class="azota-podium-crown">👑</span>🥇</div>
                        <div class="azota-podium-name" title="${escapeHtml(rank1.student_name)}">${escapeHtml(rank1.student_name)}</div>
                        <div class="azota-podium-score">${getLBScore(rank1)}</div>
                        <div class="azota-podium-time">${formatTime(rank1.time_elapsed)}</div>
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
                            <th style="width: 75px; text-align: center;">Hạng</th>
                            <th>Thí sinh</th>
                            <th style="width: 140px; text-align: center;">Điểm số</th>
                            <th style="width: 160px; text-align: right;">Thời gian</th>
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
                    <td style="text-align: center;">
                        <span class="azota-lb-rank-badge ${rank <= 3 ? 'top' : ''}">${medal}</span>
                    </td>
                    <td>
                        <span style="font-weight: 700; color: #1e293b;">${escapeHtml(item.student_name)}</span>
                        ${isMe ? '<span class="azota-lb-you-tag">Bạn</span>' : ''}
                    </td>
                    <td style="text-align: center;">
                        <span style="font-weight: 800; color: #2563eb; font-size: 1.05rem;">${item.score}</span>
                        <span style="font-size: 0.82rem; color: #64748b;"> / ${itemTotalQ} (${scaledScoreItem}đ)</span>
                    </td>
                    <td style="text-align: right; color: #64748b; font-size: 0.9rem;">
                        <i class="ri-time-line" style="vertical-align: middle;"></i> ${formatTime(item.time_elapsed)}
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
        let correctAnswer = q.correct_answer;
        let explain = (serverItem && serverItem.explain) ? serverItem.explain : (q.explain || '');
        
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
                let uStr = String(userAnswer || '').trim().toLowerCase().replace(',', '.').replace(/\s+/g, '');
                let cStr = String(correctAnswer || '').trim().toLowerCase().replace(',', '.').replace(/\s+/g, '');
                if (!uStr) {
                    status = 'skipped';
                } else if (uStr === cStr) {
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
            earnedScore
        };
    });

    const scaledScore = totalQues > 0 ? ((score / totalQues) * 10).toFixed(1) : "0.0";

    // 2. Render Score Board
    const scoreBoard = document.getElementById('score-board');
    scoreBoard.style.display = 'block';
    scoreBoard.innerHTML = `
        <div class="azota-result-card">
            <div class="azota-score-circle">
                <span class="big-num">${scaledScore}</span>
                <span class="scale">Điểm / 10</span>
            </div>
            <h2 style="color: var(--azota-primary); margin: 0 0 8px 0; font-size: 1.6rem; font-weight: 800;">
                ${score >= totalQues * 0.8 ? '🎉 Kết Quả Xuất Sắc!' : (score >= totalQues * 0.5 ? '👏 Bạn Đã Hoàn Thành Bài Thi!' : '💪 Cần Cố Gắng Thêm Lần Sau!')}
            </h2>
            <p style="color: #64748b; font-size: 1.05rem; margin: 0 0 20px 0;">
                Bạn đạt <b>${score}</b> trên tổng số <b>${totalQues}</b> điểm của đề thi.
            </p>

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
                <div class="azota-res-tile blue">
                    <div class="val">${formatTime(totalTimeElapsed)}</div>
                    <div class="desc"><i class="ri-time-line"></i> Thời gian</div>
                </div>
            </div>

            <!-- Các nút hành động chính -->
            <!-- Các nút hành động chính -->
            <div class="result-action-btns">
                <button type="button" class="btn-primary result-btn-primary" onclick="switchResultView('review')">
                    <i class="ri-file-list-3-line"></i> Xem chi tiết đáp án & lời giải
                </button>
                <button type="button" class="btn-outline result-btn-lb" onclick="switchResultView('leaderboard')">
                    <i class="ri-trophy-fill"></i> Bảng xếp hạng phòng thi
                </button>
                <button type="button" class="btn-outline result-btn-retry" onclick="${currentMode === 'practice' ? 'restartPractice()' : 'restartExam()'}">
                    <i class="ri-refresh-line"></i> Làm lại đề này
                </button>
                <button type="button" class="btn-outline result-btn-exit" onclick="exitMinimalMode()">
                    <i class="ri-logout-box-r-line"></i> Thoát
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
                <span class="filter-title"><i class="ri-filter-3-line"></i> Lọc câu hỏi:</span>
                <button type="button" class="azota-filter-tab active" data-filter="all" onclick="filterReviewQuestions('all')">
                    Tất cả <span class="tab-count">${totalQues}</span>
                </button>
                <button type="button" class="azota-filter-tab tab-wrong" data-filter="wrong" onclick="filterReviewQuestions('wrong')">
                    <i class="ri-close-circle-fill" style="color: #ef4444;"></i> Câu làm sai <span class="tab-count">${wrongCount}</span>
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
        const { q, qIndex, qType, userAnswer, correctAnswer, explain, status, earnedScore } = item;
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

        // Tìm chữ cái đáp án đúng và lựa chọn của học sinh cho câu MCQ
        let correctCharDisplay = '';
        let userCharDisplay = '';

        if (qType === 'mcq') {
            (q.options || []).forEach((opt, oIdx) => {
                let char = opt.match(/^[A-F]/i) ? opt.match(/^[A-F]/i)[0].toUpperCase() : String.fromCharCode(65 + oIdx);
                if (matchOptionToTarget(opt, oIdx, correctAnswer)) {
                    correctCharDisplay = char;
                }
                if (matchOptionToTarget(opt, oIdx, userAnswer)) {
                    userCharDisplay = char;
                }
            });
            if (!correctCharDisplay && correctAnswer) {
                let m = String(correctAnswer).match(/^[A-F]/i);
                correctCharDisplay = m ? m[0].toUpperCase() : String(correctAnswer);
            }
            if (!userCharDisplay && userAnswer) {
                let m = String(userAnswer).match(/^[A-F]/i);
                userCharDisplay = m ? m[0].toUpperCase() : String(userAnswer);
            }
        }

        // Tóm tắt kết quả nhanh trên mỗi câu hỏi
        let summaryBannerHtml = '';
        if (qType === 'mcq') {
            if (status === 'correct') {
                summaryBannerHtml = `
                    <div class="review-quick-banner is-correct">
                        <i class="ri-checkbox-circle-fill" style="font-size: 1.15rem;"></i> 
                        <span>Chính xác! Bạn đã chọn đúng đáp án <b>${correctCharDisplay || 'A'}</b></span>
                    </div>
                `;
            } else if (status === 'skipped') {
                summaryBannerHtml = `
                    <div class="review-quick-banner is-skipped">
                        <i class="ri-question-fill" style="font-size: 1.15rem;"></i> 
                        <span>Chưa trả lời! Đáp án đúng là: <b class="highlight-correct">${correctCharDisplay || 'A'}</b></span>
                    </div>
                `;
            } else {
                summaryBannerHtml = `
                    <div class="review-quick-banner is-wrong">
                        <i class="ri-close-circle-fill" style="font-size: 1.15rem;"></i> 
                        <span>Lựa chọn của bạn: <b class="highlight-wrong">${userCharDisplay || '(Chưa chọn)'}</b> &nbsp;|&nbsp; Đáp án chính xác: <b class="highlight-correct">${correctCharDisplay || 'A'}</b></span>
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
            
            cardHtml += `<div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px;">`;
            ['a', 'b', 'c', 'd'].forEach((char, oIndex) => {
                let optText = (q.options && q.options[oIndex]) ? q.options[oIndex].replace(/^[a-d][\.\:\)]\s*/, '') : `Ý kiến ${char.toUpperCase()}`;
                let isCorrectVal = correctMap[char];
                let userVal = userMap[char];
                let isMatch = (userVal !== undefined && Boolean(userVal) === Boolean(isCorrectVal));
                
                cardHtml += `
                    <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; background: #ffffff; border: 1.5px solid ${userVal === undefined ? '#e2e8f0' : (isMatch ? '#86efac' : '#fca5a5')}; border-radius: 12px; gap: 10px; flex-wrap: wrap;">
                        <div style="flex: 1; min-width: 220px; font-size: 0.96rem; color: #1e293b; line-height: 1.5;">
                            <b style="color: var(--azota-primary); margin-right: 6px;">${char})</b> ${optText}
                        </div>
                        <div style="display: flex; align-items: center; gap: 10px; font-size: 0.88rem; flex-shrink: 0;">
                            <span style="color: #64748b;">Bạn chọn: <b style="color: ${userVal === undefined ? '#64748b' : (isMatch ? '#16a34a' : '#dc2626')};">${userVal === true ? 'Đúng' : (userVal === false ? 'Sai' : 'Chưa chọn')}</b></span>
                            <span style="background: #f0fdf4; color: #166534; padding: 3px 10px; border-radius: 6px; font-weight: 700; border: 1px solid #bbf7d0;">Đáp án: ${isCorrectVal === true ? 'Đúng' : 'Sai'}</span>
                            <span style="font-size: 1.1rem;">${userVal === undefined ? '⚠️' : (isMatch ? '✅' : '❌')}</span>
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
                <div style="margin-bottom: 16px; padding: 14px 18px; background: #ffffff; border-radius: 12px; border: 1.5px solid ${isMatch ? '#86efac' : '#e2e8f0'};">
                    <div style="margin-bottom: 8px;">
                        <span style="color: #64748b; font-weight: 600;">Câu trả lời của bạn:</span> 
                        <span style="font-weight: 800; font-size: 1.05rem; color: ${isMatch ? '#16a34a' : '#dc2626'};">${escapeHtml(uStr) || '(Chưa điền câu trả lời)'}</span>
                        ${isMatch ? ' ✅' : (uStr ? ' ❌' : ' ⚠️')}
                    </div>
                    <div>
                        <span style="color: #64748b; font-weight: 600;">Đáp án chính xác:</span> 
                        <span style="font-weight: 800; font-size: 1.05rem; color: #15803d; text-decoration: underline;">${escapeHtml(cStr)}</span>
                    </div>
                </div>
            `;
        } else {
            // MCQ 4 lựa chọn
            cardHtml += `<div class="review-opt-list">`;
            (q.options || []).forEach((opt, oIndex) => {
                let char = opt.match(/^[A-F]/i) ? opt.match(/^[A-F]/i)[0].toUpperCase() : String.fromCharCode(65 + oIndex);
                let isThisCorrect = matchOptionToTarget(opt, oIndex, correctAnswer);
                let isThisUserPick = matchOptionToTarget(opt, oIndex, userAnswer);
                
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
                        <div style="flex: 1; word-break: break-word;">${opt.replace(/^[A-F][\.\:\)]\s*/i, '')}</div>
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
    
    let sessionTime = startTime > 0 ? Math.floor((Date.now() - startTime) / 1000) : 0;
    let totalTimeElapsed = isReview ? (quizProgress.timeElapsed || 0) : ((quizProgress.timeElapsed || 0) + sessionTime);
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
                    time_elapsed: totalTimeElapsed
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
                let uStr = String(userAnswer || '').trim().toLowerCase().replace(',', '.').replace(/\s+/g, '');
                let cStr = String(q.correct_answer || '').trim().toLowerCase().replace(',', '.').replace(/\s+/g, '');
                if (uStr && uStr === cStr) score += 1;
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
}

function exitMinimalMode() {
    if (confirm("Bạn có muốn tạm dừng và thoát khỏi giao diện làm bài không? (Tiến trình của bạn vẫn được bảo lưu)")) {
        document.body.classList.remove('minimal-mode');
        document.body.classList.remove('quiz-completed');
        const mobileBar = document.getElementById('azotaMobileExamBar');
        if (mobileBar) mobileBar.style.display = 'none';
        toggleMobileNavSheet(false);
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

// --- XỬ LÝ NÚT CÂU TIẾP TRÊN MOBILE BOTTOM BAR ---
window.mobileNextQuestionAction = function() {
    if (currentMode === 'practice') {
        const nextBtn = document.getElementById('nextBtn');
        if (nextBtn && nextBtn.style.display !== 'none') {
            nextPracticeQuestion();
        } else {
            if (!practiceAnswered) {
                showToast("Vui lòng trả lời câu hỏi trước khi sang câu tiếp theo!", "error");
            } else {
                nextPracticeQuestion();
            }
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
        nextBtn.style.display = 'inline-block';
        nextBtn.innerText = isLast ? 'Xem kết quả tổng kết' : 'Câu tiếp ➔';
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