import re
from pathlib import Path

def test_index_html_has_exam_submit_modal():
    index_path = Path("templates/index.html")
    assert index_path.exists(), "templates/index.html must exist"
    content = index_path.read_text(encoding="utf-8")

    assert 'id="examSubmitConfirmModal"' in content
    assert 'id="examSubmitConfirmTitle"' in content
    assert 'id="examSubmitStatsContainer"' in content
    assert 'id="examSubmitConfirmPromptText"' in content
    assert 'id="btnConfirmSubmitExamFinal"' in content
    assert 'closeExamSubmitModal()' in content
    assert 'confirmAndExecuteSubmit()' in content


def test_script_source_has_submit_modal_and_guards():
    script_path = Path("templates/script.source.js")
    assert script_path.exists(), "templates/script.source.js must exist"
    content = script_path.read_text(encoding="utf-8")

    # Kiểm tra các hàm điều khiển modal
    assert "function showExamSubmitConfirmModal" in content
    assert "function closeExamSubmitModal" in content
    assert "function confirmAndExecuteSubmit" in content

    # Kiểm tra submitExam gọi showExamSubmitConfirmModal
    assert "showExamSubmitConfirmModal({" in content

    # Kiểm tra các guard bảo vệ Anti-cheat không kích hoạt khi modal đang mở
    assert "examSubmitConfirmModal" in content
    # handleExamViolation bỏ qua khi modal nộp bài đang mở
    assert "const submitModal = document.getElementById('examSubmitConfirmModal');" in content

    # Phím Escape đóng modal
    assert "key === 'Escape'" in content


def test_css_has_submit_modal_styles():
    css_path = Path("templates/style.source.css")
    assert css_path.exists(), "templates/style.source.css must exist"
    content = css_path.read_text(encoding="utf-8")

    assert ".exam-submit-modal-overlay" in content
    assert ".exam-submit-modal-card" in content
    assert ".btn-exam-modal-cancel" in content
    assert ".btn-exam-modal-confirm" in content
    assert "z-index: 9999999;" in content


def test_minified_and_static_synced():
    for f in ["templates/script.js", "static/js/script.source.js", "static/js/script.js"]:
        p = Path(f)
        assert p.exists(), f"{f} must exist"
        txt = p.read_text(encoding="utf-8")
        assert "examSubmitConfirmModal" in txt, f"{f} must contain examSubmitConfirmModal"


def test_cookie_consent_disappears_permanently_on_accept():
    index_content = Path("templates/index.html").read_text(encoding="utf-8")
    # Không tự ý add class is-fab khi savedConsent tồn tại
    assert "if (isQuizRoute || savedConsent) {\n    root.style.display = 'none';\n    return;\n  }" in index_content
    # Khi saveAndDone hoàn tất, ẩn hoàn toàn root và không add is-fab
    assert "root.style.display = 'none';" in index_content

    script_content = Path("templates/script.source.js").read_text(encoding="utf-8")
    assert "banner.style.display = 'none';" in script_content
