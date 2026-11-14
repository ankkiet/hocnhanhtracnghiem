/**
 * Thành phần dropdown chọn lựa tùy biến (Custom Rich Select) cho HocNhanhTN.
 * Thay thế hộp <select> nguyên bản của trình duyệt bằng nút bấm và menu nổi hiện đại,
 * vẫn đồng bộ hai chiều với phần tử <select> gốc để đảm bảo tương thích biểu mẫu & sự kiện.
 */
(function (global) {
    'use strict';

    const HC_SELECT_CSS = `
.hc-select-wrap {
    position: relative;
    width: 100%;
}
.hc-select-wrap select.hc-select-native,
.hc-select-native {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    opacity: 0 !important;
    pointer-events: none !important;
    margin: 0 !important;
    padding: 0 !important;
    border: 0 !important;
    clip: rect(0, 0, 0, 0) !important;
    overflow: hidden !important;
}
button.hc-select-trigger {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 9px 12px;
    min-height: 42px;
    background: #ffffff;
    border: 1.5px solid #cbd5e1;
    border-radius: 10px;
    font-family: inherit;
    font-size: 0.86rem;
    font-weight: 600;
    color: #0f172a;
    text-align: left;
    cursor: pointer;
    outline: none;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    transition: border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
    box-sizing: border-box;
}
button.hc-select-trigger:hover {
    border-color: #94a3b8;
    background: #f8fafc;
}
button.hc-select-trigger.is-open,
button.hc-select-trigger:focus-visible {
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
    background: #ffffff;
}
.hc-select-trigger-left {
    display: flex;
    align-items: center;
    gap: 9px;
    min-width: 0;
    flex: 1;
}
.hc-select-icon-badge {
    width: 26px;
    height: 26px;
    border-radius: 7px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.95rem;
    flex-shrink: 0;
}
.hc-select-trigger-text {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.35;
    color: #0f172a;
}
.hc-select-chevron {
    font-size: 1.15rem;
    color: #64748b;
    flex-shrink: 0;
    transition: transform 0.18s ease-out, color 0.15s ease;
}
button.hc-select-trigger.is-open .hc-select-chevron {
    transform: rotate(180deg);
    color: #2563eb;
}
button.hc-select-trigger:hover i,
button.hc-select-option:hover i {
    transform: none !important;
}
button.hc-select-trigger.is-open:hover .hc-select-chevron {
    transform: rotate(180deg) !important;
}
.hc-select-menu {
    position: fixed;
    z-index: 1000000;
    background: #ffffff;
    border: 1.5px solid #e2e8f0;
    border-radius: 12px;
    padding: 6px;
    box-shadow: 0 16px 36px -8px rgba(15, 23, 42, 0.18), 0 6px 14px -4px rgba(15, 23, 42, 0.08);
    max-height: 320px;
    overflow-y: auto;
    box-sizing: border-box;
    animation: hcSelectPopIn 0.14s ease-out;
}
@keyframes hcSelectPopIn {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
}
.hc-select-menu.is-above {
    animation: hcSelectPopUp 0.14s ease-out;
}
@keyframes hcSelectPopUp {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
}
button.hc-select-option {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 9px 11px;
    margin: 0;
    border: none;
    border-radius: 8px;
    background: transparent;
    text-align: left;
    font-family: inherit;
    cursor: pointer;
    transition: background-color 0.12s ease;
    box-sizing: border-box;
}
button.hc-select-option:not(:last-child) {
    margin-bottom: 2px;
}
button.hc-select-option:hover:not(.is-disabled):not(.is-selected),
button.hc-select-option:focus-visible:not(.is-disabled):not(.is-selected) {
    background: #f1f5f9;
    outline: none;
}
button.hc-select-option.is-selected {
    background: #eff6ff;
    outline: none;
}
button.hc-select-option.is-disabled {
    opacity: 0.52;
    cursor: not-allowed;
    background: transparent;
}
.hc-select-opt-main {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    min-width: 0;
    flex: 1;
}
.hc-select-opt-icon {
    width: 28px;
    height: 28px;
    border-radius: 7px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.95rem;
    flex-shrink: 0;
    margin-top: 1px;
}
.hc-select-opt-body {
    min-width: 0;
    flex: 1;
}
.hc-select-opt-title {
    display: block;
    font-size: 0.85rem;
    font-weight: 600;
    color: #0f172a;
    line-height: 1.35;
    white-space: normal;
}
button.hc-select-option.is-selected .hc-select-opt-title {
    color: #1d4ed8;
    font-weight: 700;
}
.hc-select-opt-desc {
    display: block;
    font-size: 0.74rem;
    font-weight: 400;
    color: #64748b;
    line-height: 1.35;
    margin-top: 2px;
    white-space: normal;
}
.hc-select-opt-check {
    font-size: 1.05rem;
    color: #2563eb;
    flex-shrink: 0;
    opacity: 0;
}
button.hc-select-option.is-selected .hc-select-opt-check {
    opacity: 1;
}
.hc-tone-blue { background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }
.hc-tone-emerald { background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }
.hc-tone-amber { background: #fffbeb; color: #d97706; border: 1px solid #fde68a; }
.hc-tone-violet { background: #faf5ff; color: #7e22ce; border: 1px solid #e9d5ff; }
.hc-tone-rose { background: #fff1f2; color: #e11d48; border: 1px solid #fecdd3; }
.hc-tone-slate { background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; }

.hc-select-wrap.hc-select-compact {
    width: auto;
    max-width: 100%;
    display: inline-block;
    vertical-align: middle;
}
button.hc-select-trigger.is-compact {
    min-height: 32px;
    padding: 4px 9px;
    border-radius: 8px;
    font-size: 0.8rem;
    gap: 6px;
}
button.hc-select-trigger.is-compact .hc-select-icon-badge {
    width: 20px;
    height: 20px;
    border-radius: 5px;
    font-size: 0.8rem;
}
button.hc-select-trigger.is-compact .hc-select-chevron {
    font-size: 1rem;
}
.hc-select-wrap.hc-select-pill {
    width: auto;
    flex: 1;
    min-width: 0;
    display: inline-flex;
    align-items: center;
}
.hc-select-wrap.hc-select-pill ~ .azota-sort-chevron {
    display: none !important;
}
button.hc-select-trigger.is-pill {
    min-height: 28px;
    padding: 2px 4px;
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    font-size: 0.84rem;
    font-weight: 700;
    color: #1e293b;
    border-radius: 6px;
    gap: 5px;
}
button.hc-select-trigger.is-pill:hover {
    background: rgba(15, 23, 42, 0.04) !important;
}
button.hc-select-trigger.is-pill.is-open,
button.hc-select-trigger.is-pill:focus-visible {
    box-shadow: none !important;
    background: transparent !important;
}
button.hc-select-trigger.is-pill .hc-select-chevron {
    font-size: 0.98rem;
    color: #94a3b8;
}
button.hc-select-trigger.is-pill.is-open .hc-select-chevron {
    color: #4f46e5;
}

details.modal-accordion-card {
    background: #ffffff;
    border: 1.5px solid #e2e8f0;
    border-radius: 12px;
    padding: 11px 14px;
    font-size: 0.85rem;
    color: #334155;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
}
details.modal-accordion-card > summary {
    list-style: none;
    cursor: pointer;
    user-select: none;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-weight: 700;
    color: #0f172a;
}
details.modal-accordion-card > summary::-webkit-details-marker {
    display: none;
}
details.modal-accordion-card > summary .accordion-chevron {
    font-size: 1.15rem;
    color: #64748b;
    transition: transform 0.18s ease-out, color 0.15s ease;
}
details.modal-accordion-card[open] > summary .accordion-chevron {
    transform: rotate(180deg);
    color: #2563eb;
}
`;

    let activeCtx = null;
    let globalListenersBound = false;

    function ensureHcSelectStyles() {
        if (document.getElementById('hcSelectStyles')) return;
        const styleEl = document.createElement('style');
        styleEl.id = 'hcSelectStyles';
        styleEl.textContent = HC_SELECT_CSS;
        document.head.appendChild(styleEl);
    }

    function closeActiveMenu(restoreFocus) {
        if (!activeCtx) return;
        const ctx = activeCtx;
        activeCtx = null;
        if (ctx.menu && ctx.menu.parentNode) {
            ctx.menu.parentNode.removeChild(ctx.menu);
        }
        ctx.trigger.classList.remove('is-open');
        ctx.trigger.setAttribute('aria-expanded', 'false');
        if (restoreFocus && ctx.trigger && ctx.trigger.isConnected) {
            ctx.trigger.focus();
        }
    }

    function bindGlobalListeners() {
        if (globalListenersBound) return;
        globalListenersBound = true;

        document.addEventListener('pointerdown', function (e) {
            if (!activeCtx) return;
            if (activeCtx.wrap.contains(e.target)) return;
            if (activeCtx.menu && activeCtx.menu.contains(e.target)) return;
            closeActiveMenu(false);
        });

        document.addEventListener('keydown', function (e) {
            if (!activeCtx) return;
            if (e.key === 'Escape') {
                e.preventDefault();
                closeActiveMenu(true);
            }
        });

        window.addEventListener('resize', function () {
            if (activeCtx) closeActiveMenu(false);
        });

        document.addEventListener('scroll', function (e) {
            if (!activeCtx) return;
            if (activeCtx.menu && (e.target === activeCtx.menu || activeCtx.menu.contains(e.target))) {
                return;
            }
            closeActiveMenu(false);
        }, true);
    }

    let anonSelectCounter = 0;

    function positionMenu(trigger, menu) {
        const rect = trigger.getBoundingClientRect();
        const viewportW = window.innerWidth;
        const viewportH = window.innerHeight;
        const menuWidth = Math.min(Math.max(rect.width, 250), viewportW - 16);
        let left = rect.left;
        if (rect.width < 200 && rect.right > viewportW * 0.55) {
            left = rect.right - menuWidth;
        }
        left = Math.max(8, Math.min(left, viewportW - menuWidth - 8));

        menu.style.width = menuWidth + 'px';
        menu.style.left = left + 'px';
        menu.style.top = '0px';
        menu.classList.remove('is-above');

        const menuHeight = Math.min(menu.scrollHeight || 220, 320);
        const spaceBelow = viewportH - rect.bottom - 10;
        const spaceAbove = rect.top - 10;

        if (spaceBelow >= menuHeight || spaceBelow >= spaceAbove) {
            menu.style.top = Math.min(rect.bottom + 6, viewportH - menuHeight - 8) + 'px';
        } else {
            menu.style.top = Math.max(8, rect.top - menuHeight - 6) + 'px';
            menu.classList.add('is-above');
        }
    }

    function initHcCustomSelect(selectOrId, metaMap, options) {
        const sel = typeof selectOrId === 'string'
            ? document.getElementById(selectOrId)
            : selectOrId;
        if (!sel || sel.tagName !== 'SELECT') return null;

        ensureHcSelectStyles();
        bindGlobalListeners();

        const opts = options || sel._hcOptions || {};
        sel._hcMetaMap = metaMap || sel._hcMetaMap || {};
        sel._hcOptions = opts;

        if (sel._hcCtx) {
            sel._hcRender();
            return sel._hcCtx;
        }

        const variant = opts.variant || 'default';
        const wrap = document.createElement('div');
        wrap.className = 'hc-select-wrap'
            + (variant === 'compact' ? ' hc-select-compact' : '')
            + (variant === 'pill' ? ' hc-select-pill' : '');
        sel.parentNode.insertBefore(wrap, sel);
        wrap.appendChild(sel);

        sel.classList.add('hc-select-native');
        sel.setAttribute('tabindex', '-1');
        sel.setAttribute('aria-hidden', 'true');

        const trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'hc-select-trigger'
            + (variant === 'compact' ? ' is-compact' : '')
            + (variant === 'pill' ? ' is-pill' : '');
        trigger.setAttribute('aria-haspopup', 'listbox');
        trigger.setAttribute('aria-expanded', 'false');
        const baseId = sel.id || ('hcSel_' + (++anonSelectCounter));
        trigger.id = baseId + '_hcTrigger';
        wrap.appendChild(trigger);

        const menu = document.createElement('div');
        menu.className = 'hc-select-menu';
        menu.setAttribute('role', 'listbox');

        const nativeDesc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');

        function resolveOptionMeta(val) {
            const map = sel._hcMetaMap || {};
            if (Object.prototype.hasOwnProperty.call(map, val)) {
                return map[val] || {};
            }
            if (opts.fallbackMeta && typeof opts.fallbackMeta === 'function') {
                return opts.fallbackMeta(val) || {};
            }
            return {
                icon: opts.defaultIcon || '',
                tone: opts.defaultTone || 'blue'
            };
        }

        function renderTrigger() {
            const optList = Array.from(sel.options);
            const selectedOpt = optList.find(o => o.value === sel.value) || optList[0];
            const val = selectedOpt ? selectedOpt.value : '';
            const meta = resolveOptionMeta(val);
            const titleText = meta.triggerTitle || meta.title || (selectedOpt ? selectedOpt.textContent : '');
            const toneClass = 'hc-tone-' + (meta.tone || opts.defaultTone || 'blue');
            const showBadge = variant !== 'pill' && !!meta.icon;
            const iconHtml = showBadge
                ? `<span class="hc-select-icon-badge ${toneClass}"><i class="${meta.icon}"></i></span>`
                : '';

            trigger.innerHTML = `
                <span class="hc-select-trigger-left">
                    ${iconHtml}
                    <span class="hc-select-trigger-text"></span>
                </span>
                <i class="ri-arrow-down-s-line hc-select-chevron"></i>
            `;
            const textEl = trigger.querySelector('.hc-select-trigger-text');
            if (textEl) textEl.textContent = titleText;
        }

        function renderMenuItems() {
            menu.innerHTML = '';
            const optList = Array.from(sel.options);
            optList.forEach((opt, index) => {
                const meta = resolveOptionMeta(opt.value);
                const isSelected = opt.value === sel.value;
                const isDisabled = !!opt.disabled;

                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'hc-select-option'
                    + (isSelected ? ' is-selected' : '')
                    + (isDisabled ? ' is-disabled' : '');
                btn.setAttribute('role', 'option');
                btn.setAttribute('aria-selected', isSelected ? 'true' : 'false');
                btn.dataset.value = opt.value;
                btn.dataset.index = String(index);

                const toneClass = 'hc-tone-' + (meta.tone || opts.defaultTone || 'slate');
                const iconClass = meta.icon || opts.defaultIcon || 'ri-checkbox-blank-circle-line';
                const titleText = meta.title || opt.textContent;
                const descText = isDisabled
                    ? (meta.disabledDesc || meta.desc || '')
                    : (meta.desc || '');

                btn.innerHTML = `
                    <span class="hc-select-opt-main">
                        <span class="hc-select-opt-icon ${toneClass}"><i class="${iconClass}"></i></span>
                        <span class="hc-select-opt-body">
                            <span class="hc-select-opt-title"></span>
                            ${descText ? '<span class="hc-select-opt-desc"></span>' : ''}
                        </span>
                    </span>
                    <i class="ri-check-line hc-select-opt-check"></i>
                `;
                btn.querySelector('.hc-select-opt-title').textContent = titleText;
                if (descText) {
                    btn.querySelector('.hc-select-opt-desc').textContent = descText;
                }

                btn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    if (isDisabled) return;
                    if (sel.value !== opt.value) {
                        if (nativeDesc && nativeDesc.set) {
                            nativeDesc.set.call(sel, opt.value);
                        } else {
                            sel.value = opt.value;
                        }
                        sel.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    renderTrigger();
                    closeActiveMenu(true);
                });

                menu.appendChild(btn);
            });
        }

        function renderAll() {
            renderTrigger();
            if (activeCtx && activeCtx.sel === sel) {
                renderMenuItems();
                positionMenu(trigger, menu);
            }
        }

        function openMenu() {
            if (activeCtx && activeCtx.sel === sel) {
                closeActiveMenu(true);
                return;
            }
            closeActiveMenu(false);
            renderMenuItems();
            document.body.appendChild(menu);
            positionMenu(trigger, menu);
            trigger.classList.add('is-open');
            trigger.setAttribute('aria-expanded', 'true');
            activeCtx = { sel, wrap, trigger, menu };

            const selectedBtn = menu.querySelector('.hc-select-option.is-selected');
            if (selectedBtn && typeof selectedBtn.scrollIntoView === 'function') {
                selectedBtn.scrollIntoView({ block: 'nearest' });
            }
        }

        trigger.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            openMenu();
        });

        trigger.addEventListener('keydown', function (e) {
            if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                openMenu();
                const firstEnabled = menu.querySelector('.hc-select-option:not(.is-disabled)');
                if (firstEnabled) firstEnabled.focus();
            }
        });

        menu.addEventListener('keydown', function (e) {
            const enabledOpts = Array.from(menu.querySelectorAll('.hc-select-option:not(.is-disabled)'));
            if (!enabledOpts.length) return;
            const curIdx = enabledOpts.indexOf(document.activeElement);
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                const next = enabledOpts[(curIdx + 1) % enabledOpts.length];
                next.focus();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                const prev = enabledOpts[(curIdx - 1 + enabledOpts.length) % enabledOpts.length];
                prev.focus();
            }
        });

        if (nativeDesc && !sel._hcValueHooked) {
            Object.defineProperty(sel, 'value', {
                get() {
                    return nativeDesc.get.call(this);
                },
                set(v) {
                    nativeDesc.set.call(this, v);
                    if (this._hcRender) this._hcRender();
                },
                configurable: true
            });
            sel._hcValueHooked = true;
        }

        sel.addEventListener('change', renderAll);

        const observer = new MutationObserver(renderAll);
        observer.observe(sel, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['disabled'],
            characterData: true
        });

        sel._hcRender = renderAll;
        sel._hcCtx = { sel, wrap, trigger, menu, render: renderAll };

        renderTrigger();
        return sel._hcCtx;
    }

    const SCORING_MODE_META = {
        auto: {
            title: 'Tự động chia đều theo câu (tổng 10 điểm)',
            desc: 'Chia đều điểm cho tất cả câu hỏi để tổng đạt đúng 10.0 điểm',
            icon: 'ri-pie-chart-2-line',
            tone: 'blue'
        },
        gdpt2018: {
            title: 'Chuẩn Bộ GD&ĐT (GDPT 2018: 3đ - 4đ - 3đ)',
            desc: 'Phần I: 3.0 điểm • Phần II: 4.0 điểm • Phần III: 3.0 điểm',
            disabledDesc: 'Đề cần có phần đúng / sai hoặc trả lời ngắn để dùng chuẩn này',
            icon: 'ri-award-line',
            tone: 'emerald'
        },
        custom: {
            title: 'Tùy chỉnh điểm cho từng phần',
            desc: 'Tự do nhập điểm riêng cho mỗi câu ở từng phần cấu trúc đề',
            icon: 'ri-equalizer-2-line',
            tone: 'violet'
        }
    };

    const QUIZ_MODE_META = {
        practice: {
            title: 'Luyện tập (biết ngay đúng / sai)',
            desc: 'Học sinh xem đáp án đúng và giải thích ngay sau từng câu',
            icon: 'ri-lightbulb-flash-line',
            tone: 'emerald'
        },
        exam: {
            title: 'Thi thử (nộp bài mới chấm điểm)',
            desc: 'Làm xong toàn bộ bài thi mới nộp và xem điểm tổng kết',
            icon: 'ri-file-list-3-line',
            tone: 'blue'
        }
    };

    const MAX_ATTEMPTS_META = {
        '0': {
            title: 'Không giới hạn số lượt làm bài',
            desc: 'Phù hợp để học sinh ôn tập và tự luyện nhiều lần',
            icon: 'ri-infinity-line',
            tone: 'blue'
        },
        '1': {
            title: 'Chỉ được làm 1 lần duy nhất',
            desc: 'Phù hợp cho bài kiểm tra chính thức hoặc thi thử lấy điểm',
            icon: 'ri-lock-2-line',
            tone: 'amber'
        },
        '2': {
            title: 'Tối đa 2 lần làm bài',
            desc: 'Cho phép thí sinh thử lại thêm 1 lần để cải thiện kết quả',
            icon: 'ri-repeat-line',
            tone: 'emerald'
        },
        '3': {
            title: 'Tối đa 3 lần làm bài',
            desc: 'Giới hạn tối đa 3 lượt nộp bài cho mỗi học sinh',
            icon: 'ri-repeat-2-line',
            tone: 'violet'
        }
    };

    const SHOW_SCORE_META = {
        immediate: {
            title: 'Hiển thị điểm ngay sau khi nộp bài',
            desc: 'Học sinh biết ngay tổng điểm đạt được sau khi hoàn thành',
            icon: 'ri-flashlight-line',
            tone: 'emerald'
        },
        after_closed: {
            title: 'Chỉ xem điểm khi hết giờ ca thi',
            desc: 'Công bố điểm đồng loạt sau khi đóng phòng thi',
            icon: 'ri-time-line',
            tone: 'amber'
        },
        hidden: {
            title: 'Ẩn điểm hoàn toàn',
            desc: 'Giáo viên tổng hợp kết quả và công bố sau',
            icon: 'ri-eye-off-line',
            tone: 'slate'
        }
    };

    const SHOW_ANSWERS_META = {
        immediate: {
            title: 'Xem đáp án & giải thích ngay sau khi nộp',
            desc: 'Giúp học sinh tự đối chiếu lỗi sai và rút kinh nghiệm',
            icon: 'ri-checkbox-circle-line',
            tone: 'emerald'
        },
        after_closed: {
            title: 'Chỉ xem đáp án sau khi đóng ca thi',
            desc: 'Tránh lộ đáp án khi ca thi vẫn đang trong thời gian mở',
            icon: 'ri-shield-check-line',
            tone: 'blue'
        },
        never: {
            title: 'Không bao giờ hiển thị đáp án',
            desc: 'Bảo mật hoàn toàn ngân hàng câu hỏi và đáp án',
            icon: 'ri-eye-close-line',
            tone: 'slate'
        }
    };

    const TAB_VIOLATIONS_META = {
        '0': {
            title: 'Chỉ ghi nhận và cảnh báo',
            desc: 'Lưu nhật ký rời màn hình nhưng không tự động thu bài',
            icon: 'ri-notification-3-line',
            tone: 'blue'
        },
        '3': {
            title: 'Tự động thu bài khi chuyển tab quá 3 lần',
            desc: 'Chế độ giám sát nghiêm ngặt cho bài kiểm tra chính thức',
            icon: 'ri-alarm-warning-line',
            tone: 'amber'
        },
        '5': {
            title: 'Tự động thu bài khi chuyển tab quá 5 lần',
            desc: 'Cảnh báo nhiều lần trước khi hệ thống tự động nộp bài',
            icon: 'ri-shield-flash-line',
            tone: 'rose'
        }
    };

    const QUESTION_TYPE_META = {
        mcq: {
            triggerTitle: 'Trắc nghiệm',
            title: 'Trắc nghiệm 4 lựa chọn',
            desc: 'Học sinh chọn 1 đáp án đúng (A, B, C, D)',
            icon: 'ri-list-radio',
            tone: 'blue'
        },
        true_false: {
            triggerTitle: 'Đúng / sai',
            title: 'Trắc nghiệm đúng / sai',
            desc: 'Gồm 4 ý (a, b, c, d), mỗi ý chọn đúng hoặc sai',
            icon: 'ri-checkbox-multiple-line',
            tone: 'emerald'
        },
        short_answer: {
            triggerTitle: 'Trả lời ngắn',
            title: 'Câu hỏi trả lời ngắn',
            desc: 'Thí sinh nhập đáp án số hoặc từ khóa ngắn',
            icon: 'ri-edit-box-line',
            tone: 'amber'
        },
        essay: {
            triggerTitle: 'Tự luận',
            title: 'Câu hỏi tự luận',
            desc: 'Thí sinh trình bày lời giải chi tiết bằng văn bản hoặc ảnh',
            icon: 'ri-quill-pen-line',
            tone: 'violet'
        }
    };

    const SIM_COUNT_META = {
        '1': {
            title: '1 câu hỏi tương tự',
            desc: 'Sinh nhanh 1 biến thể mới để kiểm tra',
            icon: 'ri-file-copy-line',
            tone: 'blue'
        },
        '2': {
            title: '2 câu hỏi tương tự',
            desc: 'Tạo 2 câu luyện tập cùng dạng bài',
            icon: 'ri-file-copy-2-line',
            tone: 'blue'
        },
        '3': {
            title: '3 câu hỏi tương tự',
            desc: 'Gợi ý cân bằng để ghép bộ đề luyện tập',
            icon: 'ri-stack-line',
            tone: 'violet'
        },
        '5': {
            title: '5 câu hỏi tương tự',
            desc: 'Tạo nhanh một nhóm 5 câu củng cố chuyên đề',
            icon: 'ri-sparkling-2-line',
            tone: 'emerald'
        }
    };

    const SIM_DIFFICULTY_META = {
        keep: {
            title: 'Giữ nguyên độ khó',
            desc: 'Bám sát mức độ nhận thức của câu hỏi gốc',
            icon: 'ri-equalizer-line',
            tone: 'blue'
        },
        easier: {
            title: 'Dễ hơn (cơ bản)',
            desc: 'Giảm bước tính toán, phù hợp củng cố nền tảng',
            icon: 'ri-seedling-line',
            tone: 'emerald'
        },
        harder: {
            title: 'Nâng cao (vận dụng)',
            desc: 'Tăng độ biến hóa hoặc lồng ghép điều kiện phụ',
            icon: 'ri-rocket-2-line',
            tone: 'amber'
        }
    };

    const DOCX_LAYOUT_META = {
        auto: {
            triggerTitle: 'Tự động thông minh (1 - 2 - 4 cột)',
            title: 'Tự động thông minh (khuyên dùng)',
            desc: 'Tự căn 4, 2 hoặc 1 cột theo độ dài từng đáp án',
            icon: 'ri-magic-line',
            tone: 'blue'
        },
        '4_col': {
            title: '4 cột trên 1 hàng',
            desc: 'Dồn cả 4 đáp án A, B, C, D cùng một dòng ngang',
            icon: 'ri-layout-grid-line',
            tone: 'emerald'
        },
        '2_col': {
            title: '2 cột (2 đáp án / hàng)',
            desc: 'Chia đều 2 hàng gọn gàng cho câu dài vừa',
            icon: 'ri-layout-column-line',
            tone: 'violet'
        },
        '1_col': {
            title: '1 cột truyền thống',
            desc: 'Mỗi đáp án nằm trên một dòng riêng biệt',
            icon: 'ri-menu-2-line',
            tone: 'slate'
        }
    };

    const AI_DIFF_META = {
        'Dễ': {
            triggerTitle: 'Dễ',
            title: 'Mức độ dễ (nhận biết)',
            desc: 'Câu hỏi ghi nhớ kiến thức cơ bản, ít bước suy luận',
            icon: 'ri-leaf-line',
            tone: 'emerald'
        },
        'Trung bình': {
            triggerTitle: 'Trung bình',
            title: 'Mức độ trung bình (thông hiểu)',
            desc: 'Cân bằng giữa lý thuyết và vận dụng trực tiếp',
            icon: 'ri-scales-3-line',
            tone: 'blue'
        },
        'Khó': {
            triggerTitle: 'Khó',
            title: 'Mức độ khó (vận dụng cao)',
            desc: 'Câu hỏi phân hóa, đòi hỏi tư duy tổng hợp',
            icon: 'ri-fire-line',
            tone: 'amber'
        }
    };

    const QUIZ_SORT_META = {
        updated_desc: {
            triggerTitle: 'Mới sửa đổi / xuất bản',
            title: 'Mới sửa đổi / xuất bản',
            desc: 'Ưu tiên đề vừa chỉnh sửa hoặc xuất bản gần nhất',
            icon: 'ri-history-line',
            tone: 'blue'
        },
        created_desc: {
            triggerTitle: 'Mới tạo nhất',
            title: 'Mới tạo nhất',
            desc: 'Sắp xếp theo thời gian khởi tạo mới nhất',
            icon: 'ri-calendar-event-line',
            tone: 'emerald'
        },
        title_asc: {
            triggerTitle: 'Tên đề thi (A - Z)',
            title: 'Tên đề thi (A - Z)',
            desc: 'Sắp xếp theo thứ tự bảng chữ cái tăng dần',
            icon: 'ri-sort-asc',
            tone: 'violet'
        },
        title_desc: {
            triggerTitle: 'Tên đề thi (Z - A)',
            title: 'Tên đề thi (Z - A)',
            desc: 'Sắp xếp theo thứ tự bảng chữ cái giảm dần',
            icon: 'ri-sort-desc',
            tone: 'slate'
        }
    };

    const STATS_CLASS_META = {
        all: {
            title: 'Tất cả các lớp',
            desc: 'Hiển thị toàn bộ học sinh đã tham gia làm bài',
            icon: 'ri-group-line',
            tone: 'blue'
        }
    };

    const REPORT_TYPE_META = {
        copyright: {
            title: 'Vi phạm bản quyền học liệu (Luật SHTT)',
            desc: 'Sao chép đề thi hoặc tài liệu trái phép chưa được cho phép',
            icon: 'ri-copyright-line',
            tone: 'rose'
        },
        state_secret: {
            title: 'Đề thuộc danh mục bí mật nhà nước',
            desc: 'Đề thi chính thức chưa được cơ quan có thẩm quyền công bố',
            icon: 'ri-shield-keyhole-line',
            tone: 'amber'
        },
        inappropriate_content: {
            title: 'Nội dung không phù hợp môi trường sư phạm',
            desc: 'Vi phạm quy định nội dung theo Nghị định 147/2024/NĐ-CP',
            icon: 'ri-alert-line',
            tone: 'rose'
        },
        wrong_answer: {
            title: 'Sai sót kiến thức / đáp án trong đề thi',
            desc: 'Góp ý sửa lỗi đề bài, công thức hoặc đáp án chưa chính xác',
            icon: 'ri-error-warning-line',
            tone: 'blue'
        }
    };

    const CONTACT_ROLE_META = {
        teacher: {
            title: 'Giáo viên / giảng viên',
            desc: 'Đang soạn đề, giao bài hoặc tổ chức kiểm tra cho lớp',
            icon: 'ri-user-star-line',
            tone: 'blue'
        },
        student: {
            title: 'Học sinh / sinh viên',
            desc: 'Đang làm bài thi, ôn tập hoặc gặp sự cố khi nộp bài',
            icon: 'ri-graduation-cap-line',
            tone: 'emerald'
        },
        parent: {
            title: 'Phụ huynh học sinh',
            desc: 'Theo dõi kết quả học tập hoặc cần tư vấn hỗ trợ',
            icon: 'ri-parent-line',
            tone: 'amber'
        },
        school: {
            title: 'Đại diện trường / cơ sở giáo dục',
            desc: 'Cán bộ quản lý, tổ chuyên môn hoặc đơn vị đào tạo',
            icon: 'ri-building-2-line',
            tone: 'violet'
        },
        other: {
            title: 'Đối tác khác',
            desc: 'Đơn vị truyền thông, tác giả học liệu hoặc khách truy cập',
            icon: 'ri-team-line',
            tone: 'slate'
        }
    };

    const CONTACT_SUBJECT_META = {
        tech_issue: {
            title: 'Báo lỗi kỹ thuật số hóa đề thi',
            desc: 'Gặp trục trặc khi tải đề PDF/Word, AI bóc tách hoặc chấm điểm',
            icon: 'ri-tools-line',
            tone: 'blue'
        },
        copyright: {
            title: 'Khiếu nại bản quyền học liệu (Điều 198b Luật SHTT)',
            desc: 'Yêu cầu xác minh và gỡ bỏ tài liệu thuộc quyền sở hữu trí tuệ',
            icon: 'ri-copyright-line',
            tone: 'rose'
        },
        content_violation: {
            title: 'Báo cáo nội dung đề thi vi phạm (NĐ 147/2024/NĐ-CP)',
            desc: 'Phản ánh đề thi chứa nội dung sai lệch hoặc không phù hợp',
            icon: 'ri-shield-flash-line',
            tone: 'amber'
        },
        pdpd_data_rights: {
            title: 'Trích xuất / xóa dữ liệu cá nhân (NĐ 13/2023/NĐ-CP)',
            desc: 'Thực hiện quyền truy cập, chỉnh sửa hoặc xóa dữ liệu tài khoản',
            icon: 'ri-user-settings-line',
            tone: 'violet'
        },
        feature_request: {
            title: 'Đóng góp ý kiến nâng cấp tính năng',
            desc: 'Đề xuất cải tiến công cụ soạn đề, trộn đề hoặc phòng thi',
            icon: 'ri-lightbulb-line',
            tone: 'emerald'
        },
        partnership: {
            title: 'Đề xuất hợp tác giáo dục',
            desc: 'Trao đổi triển khai hệ thống cho nhà trường, trung tâm',
            icon: 'ri-hand-heart-line',
            tone: 'blue'
        },
        other_inquiry: {
            title: 'Yêu cầu khác',
            desc: 'Các câu hỏi chung hoặc nội dung cần trao đổi trực tiếp',
            icon: 'ri-chat-3-line',
            tone: 'slate'
        }
    };

    function initModalCustomSelects() {
        initHcCustomSelect('modalQuizMode', QUIZ_MODE_META);
        initHcCustomSelect('modalScoringMode', SCORING_MODE_META);
    }

    function initPublishCustomSelects() {
        initHcCustomSelect('selMaxAttempts', MAX_ATTEMPTS_META);
        initHcCustomSelect('selShowScore', SHOW_SCORE_META);
        initHcCustomSelect('selShowAnswers', SHOW_ANSWERS_META);
        initHcCustomSelect('selMaxTabViolations', TAB_VIOLATIONS_META);
        initHcCustomSelect('selScoringMode', SCORING_MODE_META);
    }

    function initEditorExtraCustomSelects() {
        initHcCustomSelect('simCountSelect', SIM_COUNT_META);
        initHcCustomSelect('simDifficultySelect', SIM_DIFFICULTY_META);
        initHcCustomSelect('docxOptionsLayout', DOCX_LAYOUT_META);
    }

    function initDashboardCustomSelects() {
        initHcCustomSelect('aiGenDiff', AI_DIFF_META);
        initHcCustomSelect('quizSortSelect', QUIZ_SORT_META, { variant: 'pill' });
        initHcCustomSelect('statsClassFilterSelect', STATS_CLASS_META, {
            variant: 'compact',
            fallbackMeta: function (val) {
                return {
                    title: 'Lớp ' + val,
                    triggerTitle: val,
                    desc: 'Chỉ hiển thị học sinh thuộc lớp ' + val,
                    icon: 'ri-community-line',
                    tone: 'slate'
                };
            }
        });
        initHcCustomSelect('reportQuizType', REPORT_TYPE_META);
        initEditorExtraCustomSelects();
    }

    function initContactCustomSelects() {
        initHcCustomSelect('contactRole', CONTACT_ROLE_META);
        initHcCustomSelect('contactSubject', CONTACT_SUBJECT_META);
    }

    function initQuestionTypeCustomSelects(containerEl) {
        const root = containerEl || document;
        const selects = root.querySelectorAll('select.hc-qtype-select');
        selects.forEach(function (sel) {
            initHcCustomSelect(sel, QUESTION_TYPE_META, { variant: 'compact' });
        });
    }

    function autoInitAllKnownCustomSelects() {
        initModalCustomSelects();
        initPublishCustomSelects();
        initDashboardCustomSelects();
        initContactCustomSelects();
    }

    if (typeof document !== 'undefined') {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', autoInitAllKnownCustomSelects);
        } else {
            autoInitAllKnownCustomSelects();
        }
    }

    global.HC_SELECT_PRESETS = {
        SCORING_MODE_META,
        QUIZ_MODE_META,
        MAX_ATTEMPTS_META,
        SHOW_SCORE_META,
        SHOW_ANSWERS_META,
        TAB_VIOLATIONS_META,
        QUESTION_TYPE_META,
        SIM_COUNT_META,
        SIM_DIFFICULTY_META,
        DOCX_LAYOUT_META,
        AI_DIFF_META,
        QUIZ_SORT_META,
        STATS_CLASS_META,
        REPORT_TYPE_META,
        CONTACT_ROLE_META,
        CONTACT_SUBJECT_META
    };
    global.initHcCustomSelect = initHcCustomSelect;
    global.initModalCustomSelects = initModalCustomSelects;
    global.initPublishCustomSelects = initPublishCustomSelects;
    global.initEditorExtraCustomSelects = initEditorExtraCustomSelects;
    global.initDashboardCustomSelects = initDashboardCustomSelects;
    global.initContactCustomSelects = initContactCustomSelects;
    global.initQuestionTypeCustomSelects = initQuestionTypeCustomSelects;
    global.autoInitAllKnownCustomSelects = autoInitAllKnownCustomSelects;
})(window);
