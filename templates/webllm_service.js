// webllm_service.js
// Quản lý Gia sư AI Cục bộ (WebLLM) - Chạy 100% trên trình duyệt học sinh qua Web Worker & WebGPU.
// Hoàn toàn miễn phí, bảo mật và không tốn chi phí máy chủ / API backend.

const CDN_WEBLLM = "https://cdn.jsdelivr.net/npm/@mlc-ai/web-llm/+esm";

export const AVAILABLE_MODELS = [
    {
        id: "Qwen2.5-1.5B-Instruct-q4f16_1-MLC",
        name: "Qwen 2.5 (1.5B)",
        size: "~1.1 GB",
        tag: "Khuyên dùng ⭐",
        desc: "Tiếng Việt cực chuẩn, lập luận sư phạm vững, tối ưu cho học sinh mọi cấp học.",
        recommended: true
    },
    {
        id: "Qwen2.5-0.5B-Instruct-q4f16_1-MLC",
        name: "Qwen 2.5 (0.5B)",
        size: "~350 MB",
        tag: "Siêu nhẹ ⚡",
        desc: "Tải siêu nhanh trong vài giây, chiếm rất ít tài nguyên, phù hợp máy yếu hoặc mạng 3G/4G."
    },
    {
        id: "Llama-3.2-1B-Instruct-q4f16_1-MLC",
        name: "Llama 3.2 (1B)",
        size: "~800 MB",
        tag: "Tốc độ cao 🚀",
        desc: "Mô hình siêu nhẹ thế hệ mới từ Meta AI, tốc độ sinh từ ấn tượng."
    },
    {
        id: "Llama-3-8B-Instruct-q4f32_1-MLC",
        name: "Llama 3 (8B)",
        size: "~4.5 GB",
        tag: "Máy mạnh 💪",
        desc: "Dành cho máy tính có card màn hình rời (GPU >= 6GB VRAM) để có lời giải chuyên sâu nhất."
    }
];

class WebLLMTutorService {
    constructor() {
        this.selectedModelId = localStorage.getItem("hocnhanhtn_webllm_model") || "Qwen2.5-1.5B-Instruct-q4f16_1-MLC";
        this.autoExplainOnMistake = localStorage.getItem("hocnhanhtn_webllm_auto_explain") !== "false"; // Mặc định bật
        this.engine = null;
        this.worker = null;
        this.status = "idle"; // 'idle' | 'loading' | 'ready' | 'generating' | 'error' | 'unsupported'
        this.progressPercent = 0;
        this.progressText = "";
        this.errorMessage = "";
        this.listeners = new Set();
        this.activeGenerationPromise = null;
        this.currentAbortController = null;
        this.isPreloaded = false;
        
        // Kiểm tra WebGPU sớm
        this.checkWebGPU();
    }

    async checkWebGPU() {
        if (!navigator.gpu) {
            this.status = "unsupported";
            this.errorMessage = "Trình duyệt chưa hỗ trợ WebGPU. Cần Chrome / Edge 113+ hoặc bật Hardware Acceleration.";
            this.notify();
            return false;
        }
        try {
            const adapter = await navigator.gpu.requestAdapter();
            if (!adapter) {
                this.status = "unsupported";
                this.errorMessage = "Không tìm thấy GPU phù hợp. Vui lòng kiểm tra cài đặt tăng tốc phần cứng trình duyệt.";
                this.notify();
                return false;
            }
            return true;
        } catch (e) {
            this.status = "unsupported";
            this.errorMessage = e.message || "Lỗi khởi tạo WebGPU.";
            this.notify();
            return false;
        }
    }

    subscribe(fn) {
        this.listeners.add(fn);
        fn(this.getState());
        return () => this.listeners.delete(fn);
    }

    notify() {
        const state = this.getState();
        this.listeners.forEach((fn) => {
            try { fn(state); } catch (e) { console.error(e); }
        });
        this.updatePillUI();
    }

    getState() {
        return {
            status: this.status,
            progressPercent: this.progressPercent,
            progressText: this.progressText,
            selectedModelId: this.selectedModelId,
            autoExplainOnMistake: this.autoExplainOnMistake,
            errorMessage: this.errorMessage,
            models: AVAILABLE_MODELS
        };
    }

    setModel(modelId) {
        if (this.selectedModelId === modelId) return;
        this.selectedModelId = modelId;
        localStorage.setItem("hocnhanhtn_webllm_model", modelId);
        
        // Nếu đã có engine cũ, hủy và tải lại model mới
        if (this.engine) {
            this.engine = null;
            if (this.worker) {
                try { this.worker.terminate(); } catch(e){}
                this.worker = null;
            }
            this.status = "idle";
            this.progressPercent = 0;
            this.progressText = "";
            this.preload();
        } else {
            this.notify();
        }
    }

    setAutoExplainOnMistake(val) {
        this.autoExplainOnMistake = Boolean(val);
        localStorage.setItem("hocnhanhtn_webllm_auto_explain", this.autoExplainOnMistake ? "true" : "false");
        this.notify();
    }

    /**
     * Bắt đầu tải model ngầm qua Web Worker ngay khi học sinh vào phòng thi.
     * Chạy hoàn toàn cách ly trên Worker thread, không block main thread.
     */
    async preload() {
        if (this.status === "ready" && this.engine) {
            return this.engine;
        }
        if (this.loadingPromise) {
            return this.loadingPromise;
        }

        this.loadingPromise = (async () => {
            const isGpuSupported = await this.checkWebGPU();
            if (!isGpuSupported) return null;

            this.status = "loading";
            this.progressPercent = 0;
            this.progressText = "Đang khởi tạo Web Worker ngầm...";
            this.errorMessage = "";
            this.notify();

            try {
                // Import hàm CreateWebWorkerMLCEngine từ CDN WebLLM
                const { CreateWebWorkerMLCEngine } = await import(CDN_WEBLLM);

                if (!this.worker) {
                    this.worker = new Worker("/webllm_worker.js", { type: "module" });
                    this.worker.onerror = (err) => {
                        console.error("[WebLLM Worker Error]", err);
                        this.status = "error";
                        this.errorMessage = "Không thể tải Web Worker. Vui lòng kiểm tra kết nối mạng.";
                        this.notify();
                    };
                }

                this.progressText = "Đang tải dữ liệu mô hình vào bộ nhớ đệm trình duyệt...";
                this.notify();

                // Khởi tạo Engine chạy ngầm
                this.engine = await CreateWebWorkerMLCEngine(this.worker, this.selectedModelId, {
                    initProgressCallback: (report) => {
                        this.progressPercent = Math.min(100, Math.round((report.progress || 0) * 100));
                        this.progressText = report.text || "Đang tải mô hình...";
                        this.notify();
                    }
                });

                this.status = "ready";
                this.progressPercent = 100;
                this.progressText = "Gia sư AI đã sẵn sàng!";
                this.isPreloaded = true;
                this.notify();
                return this.engine;
            } catch (err) {
                console.error("[WebLLM Init Error]", err);
                this.status = "error";
                this.errorMessage = err.message || "Lỗi tải mô hình WebLLM.";
                this.notify();
                return null;
            } finally {
                this.loadingPromise = null;
            }
        })();

        return this.loadingPromise;
    }

    /**
     * Dừng quá trình sinh văn bản đang diễn ra
     */
    async stopGeneration() {
        if (this.engine) {
            try {
                await this.engine.interruptGenerate();
            } catch (e) {
                console.warn("Lỗi interruptGenerate:", e);
            }
        }
        this.status = "ready";
        this.notify();
    }

    /**
     * Làm sạch HTML và ký tự thừa để đưa vào prompt LLM
     */
    cleanText(htmlOrText) {
        if (!htmlOrText) return "";
        let text = String(htmlOrText)
            .replace(/<br\s*[\/]?>/gi, " ")
            .replace(/<[^>]+>/g, " ")
            .replace(/&nbsp;/gi, " ")
            .replace(/&lt;/gi, "<")
            .replace(/&gt;/gi, ">")
            .replace(/&amp;/gi, "&")
            .replace(/\s+/g, " ")
            .trim();
        return text;
    }

    /**
     * Chuẩn bị câu hỏi, đáp án đúng và lựa chọn của học sinh thành văn bản chuẩn
     */
    formatQAData(q, userAnswer) {
        const qType = q.type || 'mcq';
        let questionText = this.cleanText(q.question);
        if (q.group_title) {
            questionText = `[${this.cleanText(q.group_title)}] ` + questionText;
        }

        let correctAnswerText = "";
        let studentAnswerText = "";

        if (qType === 'true_false' || typeof q.correct_answer === 'object') {
            const correctMap = (typeof q.correct_answer === 'object' && q.correct_answer) ? q.correct_answer : {};
            const userMap = (typeof userAnswer === 'object' && userAnswer) ? userAnswer : {};
            
            // Liệt kê các ý a, b, c, d
            const subOptions = (q.options || []).map((opt, idx) => {
                const char = String.fromCharCode(97 + idx);
                const optClean = this.cleanText(opt).replace(/^[a-d][\.\:\)]\s*/i, '');
                return `${char}) ${optClean}`;
            }).join("; ");
            
            questionText += ` (Gồm các ý: ${subOptions})`;

            correctAnswerText = ['a', 'b', 'c', 'd'].map(char => 
                `${char}: ${correctMap[char] === true ? 'Đúng' : (correctMap[char] === false ? 'Sai' : 'Chưa rõ')}`
            ).join(', ');

            studentAnswerText = ['a', 'b', 'c', 'd'].map(char => 
                `${char}: ${userMap[char] === true ? 'Đúng' : (userMap[char] === false ? 'Sai' : 'Chưa chọn')}`
            ).join(', ');

        } else if (qType === 'short_answer') {
            correctAnswerText = this.cleanText(q.correct_answer);
            studentAnswerText = this.cleanText(userAnswer) || "(Học sinh để trống)";
        } else {
            // MCQ
            if (Array.isArray(q.options) && q.options.length > 0) {
                const optStr = q.options.map(o => this.cleanText(o)).join(' | ');
                questionText += ` [Các phương án: ${optStr}]`;
            }
            correctAnswerText = this.cleanText(q.correct_answer);
            studentAnswerText = this.cleanText(userAnswer) || "(Học sinh chưa chọn)";
        }

        return { questionText, correctAnswerText, studentAnswerText };
    }

    /**
     * Gọi WebLLM cục bộ để giải thích câu hỏi theo prompt quy định
     */
    async explainQuestion({ question, correctAnswer, studentAnswer, onToken, onComplete, onError }) {
        if (!this.engine) {
            const loaded = await this.preload();
            if (!loaded) {
                if (onError) onError(new Error(this.errorMessage || "Không thể khởi tạo mô hình WebLLM"));
                return;
            }
        }

        this.status = "generating";
        this.notify();

        // Prompt chính xác theo yêu cầu người dùng
        const userPrompt = `Câu hỏi là: ${question}. Đáp án đúng là: ${correctAnswer}. Học sinh chọn: ${studentAnswer}. Hãy giải thích cho học sinh hiểu tại sao họ sai và giảng lại kiến thức cơ bản này.`;

        const systemPrompt = `Bạn là Gia sư ảo AI thông minh, tận tâm và thân thiện.
Nhiệm vụ của bạn là:
1. Phân tích rõ ràng vì sao lựa chọn của học sinh chưa chính xác (nêu rõ bẫy câu hỏi hoặc quan niệm sai lầm).
2. Phân tích mạch lạc tại sao đáp án đúng là chính xác (các bước tư duy, công thức hoặc dữ kiện SGK).
3. Giảng lại ngắn gọn, súc tích bản chất kiến thức cơ bản cốt lõi để học sinh hiểu sâu và nhớ lâu.
Trình bày khoa học, dễ hiểu, dùng gạch đầu dòng rõ ràng, công thức toán/hóa để trong dấu $...$ hoặc $$...$$. Luôn có giọng điệu khuyến khích, ân cần.`;

        try {
            const messages = [
                { role: "system", content: systemPrompt },
                { role: "user", content: userPrompt }
            ];

            const stream = await this.engine.chat.completions.create({
                messages,
                stream: true,
                temperature: 0.6,
                max_tokens: 1024
            });

            let fullText = "";
            for await (const chunk of stream) {
                const delta = chunk.choices[0]?.delta?.content || "";
                fullText += delta;
                if (onToken) onToken(delta, fullText);
            }

            this.status = "ready";
            this.notify();
            if (onComplete) onComplete(fullText);
            return fullText;
        } catch (err) {
            console.error("[WebLLM Generation Error]", err);
            this.status = "ready";
            this.notify();
            if (onError) onError(err);
        }
    }

    /**
     * Markdown parser đơn giản & an toàn để format lời giải AI
     */
    renderMarkdown(text) {
        if (!text) return "";
        let escaped = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        // Headers
        escaped = escaped.replace(/^### (.*$)/gim, '<h4 style="margin: 10px 0 6px 0; color: #1e293b; font-size: 1.05rem;">$1</h4>');
        escaped = escaped.replace(/^## (.*$)/gim, '<h3 style="margin: 12px 0 8px 0; color: #0f172a; font-size: 1.15rem;">$1</h3>');
        
        // Bold & Italic
        escaped = escaped.replace(/\*\*\*(.*?)\*\*\*/g, '<b><i>$1</i></b>');
        escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
        escaped = escaped.replace(/\*(.*?)\*/g, '<i>$1</i>');
        
        // Inline code / badge
        escaped = escaped.replace(/`([^`]+)`/g, '<code style="background: #f1f5f9; color: #0284c7; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 0.9em;">$1</code>');

        // Lists
        escaped = escaped.replace(/^\s*[\-\*]\s+(.*$)/gim, '<li style="margin-bottom: 4px;">$1</li>');
        escaped = escaped.replace(/(<li.*<\/li>)/gms, '<ul style="padding-left: 20px; margin: 8px 0;">$1</ul>');

        // Line breaks
        escaped = escaped.replace(/\n\n+/g, '<div style="height: 8px;"></div>');
        escaped = escaped.replace(/\n/g, '<br>');

        return escaped;
    }

    /**
     * Hiển thị Card Lời giải Gia sư AI ngay dưới câu hỏi
     */
    renderExplainCard(containerEl, qData, userAnswer, isWrong = true) {
        if (!containerEl) return;

        const { questionText, correctAnswerText, studentAnswerText } = this.formatQAData(qData, userAnswer);
        const cardId = `webllm_card_${Math.random().toString(36).substring(2, 9)}`;

        const cardHtml = `
            <div id="${cardId}" class="webllm-explain-card" style="margin-top: 14px; border-radius: 12px; background: #ffffff; border: 1.5px solid #818cf8; box-shadow: 0 4px 20px -2px rgba(99, 102, 241, 0.15); overflow: hidden; transition: all 0.3s ease;">
                <!-- Header -->
                <div style="background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); padding: 10px 16px; display: flex; align-items: center; justify-content: space-between; color: white;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 1.25rem;">🤖</span>
                        <span style="font-weight: 700; font-size: 0.95rem; letter-spacing: -0.2px;">Gia sư ảo AI (Chạy cục bộ trên máy)</span>
                        <span class="webllm-model-badge" style="background: rgba(255,255,255,0.2); font-size: 0.75rem; padding: 2px 8px; border-radius: 12px; font-weight: 500;">${this.selectedModelId.split('-')[0]}</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <button type="button" class="webllm-btn-stop" style="display: none; background: rgba(239, 68, 68, 0.85); color: white; border: none; padding: 4px 10px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; cursor: pointer;">⏹ Dừng</button>
                        <button type="button" class="webllm-btn-copy" style="background: rgba(255, 255, 255, 0.15); color: white; border: none; padding: 4px 8px; border-radius: 6px; font-size: 0.8rem; cursor: pointer;" title="Sao chép lời giải">📋</button>
                        <button type="button" class="webllm-btn-close" style="background: transparent; color: white; border: none; font-size: 1.1rem; cursor: pointer; padding: 0 4px;" title="Thu gọn">✕</button>
                    </div>
                </div>

                <!-- Body -->
                <div class="webllm-card-body" style="padding: 16px 18px; font-size: 0.95rem; line-height: 1.65; color: #1e293b;">
                    <!-- Loading skeleton / progress -->
                    <div class="webllm-loading-view" style="display: flex; flex-direction: column; gap: 10px;">
                        <div style="display: flex; align-items: center; gap: 10px; color: #4338ca; font-weight: 600;">
                            <span class="webllm-spinner" style="display: inline-block; width: 18px; height: 18px; border: 2.5px solid #c7d2fe; border-top-color: #4f46e5; border-radius: 50%; animation: webllm-spin 0.8s linear infinite;"></span>
                            <span class="webllm-loading-msg">Gia sư AI đang chuẩn bị lời giải...</span>
                        </div>
                        <div class="webllm-progress-bar-wrap" style="height: 6px; background: #e0e7ff; border-radius: 4px; overflow: hidden; display: none;">
                            <div class="webllm-progress-bar" style="height: 100%; width: 0%; background: linear-gradient(90deg, #6366f1, #a855f7); transition: width 0.3s ease;"></div>
                        </div>
                    </div>

                    <!-- Content Stream -->
                    <div class="webllm-content-view" style="display: none;"></div>
                </div>
            </div>
        `;

        // Chèn vào container
        const existingCard = containerEl.querySelector('.webllm-explain-card');
        if (existingCard) existingCard.remove();

        const wrapper = document.createElement('div');
        wrapper.innerHTML = cardHtml;
        const cardEl = wrapper.firstElementChild;
        containerEl.appendChild(cardEl);

        const stopBtn = cardEl.querySelector('.webllm-btn-stop');
        const copyBtn = cardEl.querySelector('.webllm-btn-copy');
        const closeBtn = cardEl.querySelector('.webllm-btn-close');
        const loadingView = cardEl.querySelector('.webllm-loading-view');
        const loadingMsg = cardEl.querySelector('.webllm-loading-msg');
        const progressBarWrap = cardEl.querySelector('.webllm-progress-bar-wrap');
        const progressBar = cardEl.querySelector('.webllm-progress-bar');
        const contentView = cardEl.querySelector('.webllm-content-view');

        closeBtn.onclick = () => cardEl.remove();

        copyBtn.onclick = () => {
            const rawText = contentView.innerText || "";
            if (rawText) {
                navigator.clipboard.writeText(rawText);
                copyBtn.innerText = "✅";
                setTimeout(() => { copyBtn.innerText = "📋"; }, 1500);
            }
        };

        stopBtn.onclick = () => {
            this.stopGeneration();
            stopBtn.style.display = 'none';
        };

        // Theo dõi quá trình tải nếu model chưa sẵn sàng
        const unsubscribe = this.subscribe((state) => {
            if (state.status === 'loading') {
                progressBarWrap.style.display = 'block';
                progressBar.style.width = `${state.progressPercent}%`;
                loadingMsg.innerText = `Đang tải mô hình WebLLM (${state.progressPercent}%): ${state.progressText}`;
            } else if (state.status === 'unsupported') {
                loadingView.innerHTML = `
                    <div style="color: #b91c1c; background: #fef2f2; padding: 12px; border-radius: 8px; border: 1px solid #fecaca;">
                        <b>⚠️ Không thể chạy Gia sư AI:</b> ${state.errorMessage}<br>
                        <span style="font-size: 0.85rem; color: #7f1d1d; margin-top: 4px; display: inline-block;">
                            Gợi ý: Dùng Google Chrome hoặc Microsoft Edge phiên bản mới nhất và bật Hardware Acceleration.
                        </span>
                    </div>`;
                unsubscribe();
            } else if (state.status === 'error') {
                loadingView.innerHTML = `
                    <div style="color: #b91c1c; background: #fef2f2; padding: 12px; border-radius: 8px;">
                        <b>❌ Lỗi tải AI:</b> ${state.errorMessage}
                    </div>`;
                unsubscribe();
            }
        });

        // Bắt đầu gọi giải thích
        this.explainQuestion({
            question: questionText,
            correctAnswer: correctAnswerText,
            studentAnswer: studentAnswerText,
            onToken: (delta, accumulatedText) => {
                loadingView.style.display = 'none';
                contentView.style.display = 'block';
                stopBtn.style.display = 'inline-block';
                contentView.innerHTML = this.renderMarkdown(accumulatedText) + '<span class="webllm-cursor" style="display:inline-block; width:7px; height:15px; background:#4f46e5; margin-left:3px; vertical-align:middle; animation:webllm-blink 0.8s infinite;"></span>';
            },
            onComplete: (fullText) => {
                unsubscribe();
                loadingView.style.display = 'none';
                contentView.style.display = 'block';
                stopBtn.style.display = 'none';
                contentView.innerHTML = this.renderMarkdown(fullText);
                
                // Render MathJax nếu có công thức toán
                if (window.MathJax && window.MathJax.typesetPromise) {
                    try {
                        window.MathJax.typesetPromise([contentView]).catch(e => console.log(e));
                    } catch(e){}
                }
            },
            onError: (err) => {
                unsubscribe();
                loadingView.style.display = 'none';
                contentView.style.display = 'block';
                stopBtn.style.display = 'none';
                contentView.innerHTML = `<div style="color: #b91c1c;"><b>❌ Đã xảy ra lỗi:</b> ${err.message || err}</div>`;
            }
        });
    }

    /**
     * Tạo nút kích hoạt Gia sư AI để chèn vào giao diện
     */
    createExplainButton(onClickHandler, isMistake = false) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn-webllm-explain';
        btn.style.cssText = `
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 700;
            cursor: pointer;
            border: none;
            transition: all 0.2s ease;
            box-shadow: 0 2px 8px rgba(99, 102, 241, 0.25);
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            color: #ffffff;
            margin-top: 8px;
        `;
        btn.innerHTML = isMistake 
            ? `<span>🤖</span> Xem Gia sư AI giải thích vì sao sai`
            : `<span>💡</span> Xem giải thích chi tiết (Gia sư AI)`;
        
        btn.onmouseover = () => { btn.style.transform = "translateY(-1px)"; btn.style.boxShadow = "0 4px 14px rgba(99, 102, 241, 0.4)"; };
        btn.onmouseout = () => { btn.style.transform = "none"; btn.style.boxShadow = "0 2px 8px rgba(99, 102, 241, 0.25)"; };
        btn.onclick = onClickHandler;
        return btn;
    }

    /**
     * Khởi tạo Floating Status Pill ở góc màn hình để theo dõi WebLLM
     */
    initStatusPill() {
        if (document.getElementById('webllmStatusPill')) return;

        const pill = document.createElement('div');
        pill.id = 'webllmStatusPill';
        pill.className = 'webllm-status-pill';
        pill.innerHTML = `
            <div class="pill-dot"></div>
            <span class="pill-icon">🤖</span>
            <span class="pill-text">Gia sư AI: Cục bộ</span>
        `;
        document.body.appendChild(pill);

        pill.onclick = () => this.openSettingsModal();
        this.updatePillUI();
    }

    updatePillUI() {
        const pill = document.getElementById('webllmStatusPill');
        if (!pill) return;

        const dot = pill.querySelector('.pill-dot');
        const text = pill.querySelector('.pill-text');

        if (this.status === 'unsupported') {
            pill.className = 'webllm-status-pill unsupported';
            text.innerText = 'Gia sư AI: Cần WebGPU';
            pill.title = this.errorMessage;
        } else if (this.status === 'loading') {
            pill.className = 'webllm-status-pill loading';
            text.innerText = `Gia sư AI: Tải ngầm ${this.progressPercent}%`;
            pill.title = this.progressText;
        } else if (this.status === 'ready') {
            pill.className = 'webllm-status-pill ready';
            text.innerText = `Gia sư AI: Sẵn sàng (${this.selectedModelId.split('-')[0]})`;
            pill.title = 'Mô hình đã nạp xong vào WebGPU. Bấm để tùy chỉnh.';
        } else if (this.status === 'generating') {
            pill.className = 'webllm-status-pill generating';
            text.innerText = 'Gia sư AI: Đang giải thích...';
        } else if (this.status === 'error') {
            pill.className = 'webllm-status-pill error';
            text.innerText = 'Gia sư AI: Lỗi tải';
            pill.title = this.errorMessage;
        } else {
            pill.className = 'webllm-status-pill idle';
            text.innerText = 'Gia sư AI: Miễn phí';
            pill.title = 'Bấm để chuẩn bị mô hình hoặc xem cấu hình';
        }
    }

    /**
     * Modal cài đặt mô hình WebLLM & Tùy chọn học tập
     */
    openSettingsModal() {
        let modal = document.getElementById('webllmSettingsModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'webllmSettingsModal';
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal-content" style="max-width: 540px; padding: 24px; border-radius: 16px; background: #ffffff !important; opacity: 1 !important; animation: none !important; box-shadow: 0 20px 50px -10px rgba(0, 0, 0, 0.35); max-height: 90vh; overflow-y: auto;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; border-bottom: 1px solid #e2e8f0; padding-bottom: 12px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 1.5rem;">🤖</span>
                            <h3 style="margin: 0; font-size: 1.2rem; color: #1e293b;">Gia sư AI Cục bộ (WebLLM)</h3>
                        </div>
                        <button type="button" style="background: none; border: none; font-size: 1.3rem; cursor: pointer; color: #64748b;" onclick="window.WebLLMTutor.closeSettingsModal()">✕</button>
                    </div>

                    <div style="background: #eef2ff; border: 1px solid #c7d2fe; padding: 12px 14px; border-radius: 10px; margin-bottom: 18px; font-size: 0.9rem; color: #3730a3; display: flex; align-items: flex-start; gap: 10px;">
                        <span style="font-size: 1.2rem; line-height: 1;">💡</span>
                        <div>
                            <b>Hoàn toàn miễn phí & Riêng tư:</b> Mô hình chạy trực tiếp 100% bằng GPU của trình duyệt của bạn qua WebGPU. Không gửi câu hỏi lên máy chủ trả phí.
                        </div>
                    </div>

                    <div style="margin-bottom: 16px;">
                        <label style="font-weight: 700; display: block; margin-bottom: 8px; font-size: 0.95rem; color: #0f172a;">Chọn mô hình Gia sư AI:</label>
                        <div id="webllmModelList" style="display: flex; flex-direction: column; gap: 8px;"></div>
                    </div>

                    <div style="margin-bottom: 20px; padding: 12px; background: #f8fafc; border-radius: 10px; border: 1px solid #e2e8f0;">
                        <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; font-size: 0.95rem; font-weight: 600; color: #1e293b;">
                            <input type="checkbox" id="webllmAutoExplainCheck" style="width: 18px; height: 18px; cursor: pointer;" onchange="window.WebLLMTutor.setAutoExplainOnMistake(this.checked)">
                            <span>Tự động gợi ý Gia sư AI khi học sinh làm sai câu hỏi</span>
                        </label>
                    </div>

                    <div id="webllmModalStatusArea" style="margin-bottom: 20px; font-size: 0.9rem;"></div>

                    <div style="display: flex; justify-content: flex-end; gap: 10px;">
                        <button type="button" class="btn-outline" style="margin: 0; padding: 10px 18px;" onclick="window.WebLLMTutor.preload()">🔄 Tải lại / Khởi động</button>
                        <button type="button" class="btn-primary" style="margin: 0; padding: 10px 22px;" onclick="window.WebLLMTutor.closeSettingsModal()">Xong</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }

        // Render danh sách models
        const listEl = modal.querySelector('#webllmModelList');
        listEl.innerHTML = AVAILABLE_MODELS.map(m => `
            <div class="webllm-model-card ${this.selectedModelId === m.id ? 'active' : ''}" onclick="window.WebLLMTutor.setModel('${m.id}')" style="display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border: 1.5px solid ${this.selectedModelId === m.id ? '#4f46e5' : '#e2e8f0'}; background: ${this.selectedModelId === m.id ? '#f5f3ff' : '#ffffff'}; border-radius: 10px; cursor: pointer; transition: all 0.2s ease;">
                <div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <b style="font-size: 0.95rem; color: #0f172a;">${m.name}</b>
                        <span style="font-size: 0.75rem; background: ${m.recommended ? '#dcfce7' : '#f1f5f9'}; color: ${m.recommended ? '#166534' : '#475569'}; padding: 2px 6px; border-radius: 6px; font-weight: 600;">${m.tag}</span>
                        <span style="font-size: 0.8rem; color: #64748b;">(${m.size})</span>
                    </div>
                    <div style="font-size: 0.85rem; color: #64748b; margin-top: 2px;">${m.desc}</div>
                </div>
                <div style="font-size: 1.2rem; color: #4f46e5;">${this.selectedModelId === m.id ? '🔘' : '⚪'}</div>
            </div>
        `).join('');

        const checkEl = modal.querySelector('#webllmAutoExplainCheck');
        if (checkEl) checkEl.checked = this.autoExplainOnMistake;

        const statusArea = modal.querySelector('#webllmModalStatusArea');
        if (statusArea) {
            statusArea.innerHTML = `
                <div style="display: flex; justify-content: space-between; color: #475569;">
                    <span>Trạng thái: <b>${this.status.toUpperCase()}</b></span>
                    <span>${this.progressText || ''}</span>
                </div>
            `;
        }

        modal.style.display = 'flex';
    }

    closeSettingsModal() {
        const modal = document.getElementById('webllmSettingsModal');
        if (modal) modal.style.display = 'none';
    }
}

// Khởi tạo Singleton
export const tutorService = new WebLLMTutorService();

// Lấy danh sách hàng đợi cuộc gọi trước khi module nạp xong (nếu có)
const queuedCalls = window.WebLLMQueue || [];

// Chỉ kích hoạt WebLLM khi cờ ENABLE_WEBLLM được bật (Mặc định tạm thời ẩn theo yêu cầu người dùng)
if (window.ENABLE_WEBLLM === true) {
    // Gắn vào window để script.js hoặc HTML dễ dàng truy cập
    window.WebLLMTutor = tutorService;

    // Tự động khởi tạo pill khi DOM sẵn sàng
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => tutorService.initStatusPill());
    } else {
        tutorService.initStatusPill();
    }

    // Xử lý các lệnh gọi đã được xếp hàng đợi (như preload)
    if (Array.isArray(queuedCalls) && queuedCalls.length > 0) {
        queuedCalls.forEach(([method, ...args]) => {
            if (typeof tutorService[method] === 'function') {
                try { tutorService[method](...args); } catch(e){ console.error(e); }
            }
        });
        window.WebLLMQueue = [];
    }
} else {
    console.log("ℹ️ Tính năng WebLLM đang ở chế độ tạm ẩn (ENABLE_WEBLLM = false).");
}
