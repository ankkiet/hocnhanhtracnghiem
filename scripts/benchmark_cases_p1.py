"""
Định nghĩa 40 bộ test cases chuẩn thực tế cho Benchmark Suite của HocNhanhTN.
Phần 1: Môn Toán học, Vật lý, Hóa học, Sinh học, Tiếng Anh (Tổng cộng 23 files)
"""

BENCHMARK_CASES = [
    # =========================================================================
    # 1. TOÁN HỌC (5 files: 4 DOCX + 1 PDF)
    # =========================================================================
    {
        "file_id": "docx_toan_01_gach_chan",
        "file_name": "toan_01_gach_chan.docx",
        "format_type": "docx",
        "subject": "Toán học",
        "style": "underline",
        "style_description": "Toán giải tích, đáp án gạch chân trực tiếp trong câu, ký hiệu đạo hàm cực trị",
        "tags": ["toan", "underline", "giai_tich"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Cho hàm số y = f(x) có bảng xét dấu đạo hàm f'(x). Hàm số đã cho đồng biến trên khoảng nào dưới đây?",
                "options": ["A. (-∞; -1)", "B. (-1; 1)", "C. (1; +∞)", "D. (-∞; 1)"],
                "correct_answer": "B. (-1; 1)",
                "explain": "Đạo hàm f'(x) > 0 với mọi x thuộc (-1; 1) nên hàm số đồng biến trên (-1; 1)."
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Hàm số y = x^4 - 2x^2 + 3 có bao nhiêu điểm cực trị?",
                "options": ["A. 1", "B. 2", "C. 3", "D. 0"],
                "correct_answer": "C. 3",
                "explain": "Ta có y' = 4x^3 - 4x = 4x(x^2 - 1) = 0 có 3 nghiệm phân biệt đổi dấu, nên có 3 điểm cực trị."
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Đồ thị của hàm số y = (2x + 1)/(x - 1) có tiệm cận đứng là đường thẳng nào sau đây?",
                "options": ["A. x = 1", "B. y = 2", "C. x = -1", "D. y = 1/2"],
                "correct_answer": "A. x = 1",
                "explain": "Mẫu số x - 1 = 0 suy ra x = 1 là đường tiệm cận đứng."
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Tính tích phân I = int_0^1 (2x + 1) dx.",
                "options": ["A. 1", "B. 2", "C. 3", "D. 4"],
                "correct_answer": "B. 2",
                "explain": "Nguyên hàm là x^2 + x, thay cận từ 0 đến 1: (1 + 1) - 0 = 2."
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Trong không gian Oxyz, mặt cầu (S): (x - 1)^2 + (y + 2)^2 + (z - 3)^2 = 16 có bán kính bằng",
                "options": ["A. 16", "B. 4", "C. 8", "D. 2"],
                "correct_answer": "B. 4",
                "explain": "Bán kính R = sqrt(16) = 4."
            }
        ]
    },
    {
        "file_id": "docx_toan_02_bang_dap_an_cuoi",
        "file_name": "toan_02_bang_dap_an_cuoi.docx",
        "format_type": "docx",
        "subject": "Toán học",
        "style": "bottom_table",
        "style_description": "Toán hình học không gian, các câu không đánh dấu, có BẢNG ĐÁP ÁN dạng bảng Word ở cuối bài",
        "tags": ["toan", "bottom_table", "hinh_hoc"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Thể tích V của khối chóp có diện tích đáy B và chiều cao h được tính theo công thức nào dưới đây?",
                "options": ["A. V = 1/3 Bh", "B. V = Bh", "C. V = 1/2 Bh", "D. V = 3Bh"],
                "correct_answer": "A. V = 1/3 Bh"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Khối lập phương có cạnh bằng 3 có thể tích bằng bao nhiêu?",
                "options": ["A. 9", "B. 18", "C. 27", "D. 81"],
                "correct_answer": "C. 27"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Một hình nón có bán kính đáy r = 3 và chiều cao h = 4. Độ dài đường sinh l của hình nón là",
                "options": ["A. 7", "B. 5", "C. 1", "D. sqrt(7)"],
                "correct_answer": "B. 5"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Diện tích mặt cầu có bán kính R = 2 được tính bằng",
                "options": ["A. 8π", "B. 12π", "C. 32π/3", "D. 16π"],
                "correct_answer": "D. 16π"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Trong không gian Oxyz, cho hai điểm A(1; 2; 3) và B(3; 0; 1). Tọa độ trung điểm I của đoạn thẳng AB là",
                "options": ["A. (2; 1; 2)", "B. (4; 2; 4)", "C. (1; -1; -1)", "D. (2; -1; 2)"],
                "correct_answer": "A. (2; 1; 2)"
            }
        ]
    },
    {
        "file_id": "docx_toan_03_gdpt2018_3phan",
        "file_name": "toan_03_gdpt2018_3phan.docx",
        "format_type": "docx",
        "subject": "Toán học",
        "style": "gdpt_2018",
        "style_description": "Đề Toán chuẩn GDPT 2018: Phần I MCQ 4 lựa chọn, Phần II Đúng/Sai 4 ý, Phần III Điền số trả lời ngắn",
        "tags": ["toan", "gdpt_2018", "true_false", "short_answer"],
        "questions": [
            {
                "question_number": 1,
                "part": 1,
                "type": "mcq",
                "question": "Tập nghiệm của bất phương trình log_2(x - 1) < 3 là",
                "options": ["A. (1; 9)", "B. (-∞; 9)", "C. (1; 8)", "D. (9; +∞)"],
                "correct_answer": "A. (1; 9)"
            },
            {
                "question_number": 2,
                "part": 1,
                "type": "mcq",
                "question": "Nghiệm của phương trình 3^(2x - 1) = 27 là",
                "options": ["A. x = 1", "B. x = 2", "C. x = 3", "D. x = 4"],
                "correct_answer": "B. x = 2"
            },
            {
                "question_number": 1,
                "part": 2,
                "type": "true_false",
                "question": "Cho hàm số f(x) = x^3 - 3x + 2. Xét tính đúng sai của các khẳng định sau:",
                "options": [
                    "a) Hàm số f(x) đồng biến trên khoảng (1; +∞)",
                    "b) Giá trị cực đại của hàm số bằng 4",
                    "c) Đồ thị hàm số đi qua điểm M(0; 2)",
                    "d) Phương trình f(x) = 0 có đúng 3 nghiệm phân biệt"
                ],
                "correct_answer": {"a": True, "b": True, "c": True, "d": False}
            },
            {
                "question_number": 2,
                "part": 2,
                "type": "true_false",
                "question": "Trong không gian Oxyz, cho mặt phẳng (P): 2x - y + 2z - 6 = 0 và điểm A(1; 2; 3).",
                "options": [
                    "a) Vectơ pháp tuyến của (P) là n = (2; -1; 2)",
                    "b) Điểm A thuộc mặt phẳng (P)",
                    "c) Khoảng cách từ điểm O(0; 0; 0) đến mặt phẳng (P) bằng 2",
                    "d) Mặt phẳng (Q) song song với (P) có phương trình 2x - y + 2z + 1 = 0"
                ],
                "correct_answer": {"a": True, "b": False, "c": True, "d": True}
            },
            {
                "question_number": 1,
                "part": 3,
                "type": "short_answer",
                "question": "Tìm giá trị lớn nhất của hàm số y = -x^2 + 4x + 5 trên đoạn [0; 3].",
                "options": [],
                "correct_answer": "9"
            },
            {
                "question_number": 2,
                "part": 3,
                "type": "short_answer",
                "question": "Một người gửi tiết kiệm 100 triệu đồng với lãi suất 6%/năm. Hỏi sau 2 năm số tiền lãi người đó nhận được là bao nhiêu triệu đồng? (Làm tròn đến 2 chữ số thập phân)",
                "options": [],
                "correct_answer": "12.36"
            }
        ]
    },
    {
        "file_id": "docx_toan_04_dau_sao_asterisk",
        "file_name": "toan_04_dau_sao_asterisk.docx",
        "format_type": "docx",
        "subject": "Toán học",
        "style": "asterisk",
        "style_description": "Toán số phức và tọa độ, đánh dấu dấu sao * trước đáp án đúng, 4 đáp án trên 1 dòng phân cách Tab",
        "tags": ["toan", "asterisk", "single_line_options"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "layout": "single_line",
                "question": "Số phức liên hợp của số phức z = 3 - 4i là",
                "options": ["A. 3 + 4i", "B. -3 - 4i", "C. -3 + 4i", "D. 4 - 3i"],
                "correct_answer": "A. 3 + 4i"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "layout": "single_line",
                "question": "Môđun của số phức z = 1 + 2i bằng",
                "options": ["A. 5", "B. sqrt(5)", "C. 3", "D. sqrt(3)"],
                "correct_answer": "B. sqrt(5)"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "layout": "single_line",
                "question": "Phần thực của số phức w = (2 + i)(1 - i) là",
                "options": ["A. 1", "B. 2", "C. 3", "D. -1"],
                "correct_answer": "C. 3"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "layout": "single_line",
                "question": "Trong mặt phẳng tọa độ, điểm biểu diễn số phức z = -2 + 5i có tọa độ là",
                "options": ["A. (5; -2)", "B. (2; 5)", "C. (-2; -5)", "D. (-2; 5)"],
                "correct_answer": "D. (-2; 5)"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "layout": "single_line",
                "question": "Tập hợp các điểm biểu diễn số phức z thỏa mãn |z| = 2 là đường tròn có bán kính bằng",
                "options": ["A. 2", "B. 4", "C. 1", "D. sqrt(2)"],
                "correct_answer": "A. 2"
            }
        ]
    },
    {
        "file_id": "pdf_toan_01_chuan_thpt",
        "file_name": "toan_01_chuan_thpt.pdf",
        "format_type": "pdf",
        "subject": "Toán học",
        "style": "bottom_text",
        "style_description": "PDF đề thi thử THPT Quốc gia môn Toán, bảng đáp án text ở cuối đề thi",
        "tags": ["toan", "pdf", "bottom_text"],
        "answer_text_block": "1.B   2.C   3.A   4.D   5.A",
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Cho cấp số cộng (u_n) có u_1 = 3 và công sai d = 2. Số hạng thứ hai u_2 bằng",
                "options": ["A. 6", "B. 5", "C. 1", "D. 8"],
                "correct_answer": "B. 5"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Có bao nhiêu cách chọn 2 học sinh từ một nhóm gồm 10 học sinh?",
                "options": ["A. 20", "B. 90", "C. 45", "D. 100"],
                "correct_answer": "C. 45"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Đạo hàm của hàm số y = 2^x là",
                "options": ["A. y' = 2^x * ln 2", "B. y' = x * 2^(x - 1)", "C. y' = 2^x / ln 2", "D. y' = 2^x"],
                "correct_answer": "A. y' = 2^x * ln 2"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Tập xác định D của hàm số y = log_3(x - 2) là",
                "options": ["A. D = R \\ {2}", "B. D = [2; +∞)", "C. D = (-∞; 2)", "D. D = (2; +∞)"],
                "correct_answer": "D. D = (2; +∞)"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Hàm số nào dưới đây nghịch biến trên toàn bộ tập số thực R?",
                "options": ["A. y = -x^3 - x", "B. y = x^3 + 2x", "C. y = (x - 1)/(x + 1)", "D. y = -x^4 + 2"],
                "correct_answer": "A. y = -x^3 - x"
            }
        ]
    },

    # =========================================================================
    # 2. VẬT LÝ (4 files: 3 DOCX + 1 PDF)
    # =========================================================================
    {
        "file_id": "docx_vatly_01_boi_do",
        "file_name": "vatly_01_boi_do.docx",
        "format_type": "docx",
        "subject": "Vật lý",
        "style": "red",
        "style_description": "Vật lý dao động cơ, đáp án đúng tô chữ màu ĐỎ (#FF0000) trong file Word",
        "tags": ["vat_ly", "red_font", "dao_dong_co"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Một chất điểm dao động điều hòa theo phương trình x = A cos(omega * t + phi). Đại lượng omega được gọi là",
                "options": ["A. pha ban đầu.", "B. tần số góc.", "C. chu kì dao động.", "D. biên độ dao động."],
                "correct_answer": "B. tần số góc."
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Một con lắc lò xo gồm vật nặng khối lượng m và lò xo độ cứng k. Chu kì dao động riêng của con lắc là",
                "options": ["A. T = 2π * sqrt(k/m)", "B. T = 2π * sqrt(m/k)", "C. T = 1/(2π) * sqrt(m/k)", "D. T = sqrt(m/k)"],
                "correct_answer": "B. T = 2π * sqrt(m/k)"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Gia tốc của một vật dao động điều hòa luôn",
                "options": ["A. cùng pha với li độ.", "B. ngược pha với li độ.", "C. sớm pha π/2 so với vận tốc.", "D. trễ pha π/2 so với vận tốc."],
                "correct_answer": "B. ngược pha với li độ."
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Vận tốc cực đại của vật dao động điều hòa với biên độ A và tần số góc omega là",
                "options": ["A. v_max = omega * A", "B. v_max = omega^2 * A", "C. v_max = omega * A^2", "D. v_max = 2 * omega * A"],
                "correct_answer": "A. v_max = omega * A"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Khi một vật dao động điều hòa chuyển động từ vị trí biên về vị trí cân bằng thì",
                "options": ["A. động năng giảm dần, thế năng tăng dần.", "B. vận tốc có độ lớn giảm dần.", "C. thế năng chuyển hóa thành động năng.", "D. cơ năng giảm dần."],
                "correct_answer": "C. thế năng chuyển hóa thành động năng."
            }
        ]
    },
    {
        "file_id": "docx_vatly_02_loi_giai_chi_tiet",
        "file_name": "vatly_02_loi_giai_chi_tiet.docx",
        "format_type": "docx",
        "subject": "Vật lý",
        "style": "underline",
        "style_description": "Vật lý sóng cơ, đáp án gạch chân kèm khối 'Lời giải chi tiết:' dưới mỗi câu hỏi",
        "tags": ["vat_ly", "underline", "explain_block", "song_co"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Bước sóng là khoảng cách giữa hai điểm gần nhau nhất trên cùng một phương truyền sóng mà dao động tại hai điểm đó",
                "options": ["A. ngược pha.", "B. vuông pha.", "C. cùng pha.", "D. lệch pha π/4."],
                "correct_answer": "C. cùng pha.",
                "explain": "Định nghĩa: Bước sóng λ là quãng đường sóng truyền đi trong một chu kì, đồng thời là khoảng cách giữa 2 điểm gần nhất cùng pha trên phương truyền sóng."
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Một sóng cơ truyền với tốc độ v = 10 m/s và tần số f = 50 Hz. Bước sóng có giá trị là",
                "options": ["A. 0,2 m", "B. 5 m", "C. 500 m", "D. 0,5 m"],
                "correct_answer": "A. 0,2 m",
                "explain": "Áp dụng công thức λ = v / f = 10 / 50 = 0,2 m."
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Trong giao thoa sóng cơ trên mặt nước của 2 nguồn kết hợp cùng pha, khoảng cách giữa 2 cực đại liên tiếp trên đoạn nối hai nguồn là",
                "options": ["A. λ", "B. λ/2", "C. λ/4", "D. 2λ"],
                "correct_answer": "B. λ/2",
                "explain": "Hai cực đại giao thoa liên tiếp trên đường thẳng nối hai nguồn cách nhau khoảng λ/2."
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Đặc trưng sinh lý nào dưới đây gắn liền với tần số của âm?",
                "options": ["A. Độ to của âm", "B. Độ cao của âm", "C. Âm sắc", "D. Mức cường độ âm"],
                "correct_answer": "B. Độ cao của âm",
                "explain": "Độ cao của âm là một đặc trưng sinh lý gắn liền với tần số âm."
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Khi có sóng dừng trên một sợi dây đàn hồi có hai đầu cố định, khoảng cách giữa một nút sóng và một bụng sóng liền kề là",
                "options": ["A. λ/4", "B. λ/2", "C. λ", "D. 2λ"],
                "correct_answer": "A. λ/4",
                "explain": "Khoảng cách từ một nút đến một bụng liền kề luôn bằng λ/4."
            }
        ]
    },
    {
        "file_id": "docx_vatly_03_gdpt2018",
        "file_name": "vatly_03_gdpt2018.docx",
        "format_type": "docx",
        "subject": "Vật lý",
        "style": "gdpt_2018",
        "style_description": "Vật lý GDPT 2018 Nhiệt học & Khí lý tưởng: Phần I MCQ, Phần II Đúng/Sai 4 ý, Phần III Trả lời ngắn",
        "tags": ["vat_ly", "gdpt_2018", "nhiet_hoc"],
        "questions": [
            {
                "question_number": 1,
                "part": 1,
                "type": "mcq",
                "question": "Nhiệt độ không tuyệt đối theo thang Kelvin tương ứng với bao nhiêu độ Celsius?",
                "options": ["A. 0 °C", "B. -273,15 °C", "C. 273,15 °C", "D. 100 °C"],
                "correct_answer": "B. -273,15 °C"
            },
            {
                "question_number": 2,
                "part": 1,
                "type": "mcq",
                "question": "Trong quá trình đẳng nhiệt của một lượng khí lý tưởng xác định, áp suất p và thể tích V quan hệ với nhau như thế nào?",
                "options": ["A. Tỉ lệ thuận", "B. Tỉ lệ nghịch", "C. Không phụ thuộc", "D. Tổng p + V không đổi"],
                "correct_answer": "B. Tỉ lệ nghịch"
            },
            {
                "question_number": 1,
                "part": 2,
                "type": "true_false",
                "question": "Một khối khí lý tưởng chứa trong một xilanh có pit-tông di động. Xét tính đúng sai của các nhận định:",
                "options": [
                    "a) Khi nén khí đẳng nhiệt, động năng trung bình của các phân tử khí tăng lên",
                    "b) Trong quá trình đẳng áp, thể tích của khối khí tỉ lệ thuận với nhiệt độ tuyệt đối",
                    "c) Độ biến thiên nội năng của khối khí trong chu trình kín bằng 0",
                    "d) Nếu khối khí nhận nhiệt lượng 100 J và sinh công 40 J thì nội năng tăng 60 J"
                ],
                "correct_answer": {"a": False, "b": True, "c": True, "d": True}
            },
            {
                "question_number": 2,
                "part": 2,
                "type": "true_false",
                "question": "Về mô hình động học phân tử chất khí:",
                "options": [
                    "a) Các phân tử khí chuyển động hỗn loạn không ngừng về mọi phía",
                    "b) Nhiệt độ của khối khí càng cao thì các phân tử chuyển động càng chậm",
                    "c) Khoảng cách giữa các phân tử khí rất lớn so với kích thước của chúng",
                    "d) Lực tương tác giữa các phân tử khí lý tưởng chỉ đáng kể khi chúng va chạm"
                ],
                "correct_answer": {"a": True, "b": False, "c": True, "d": True}
            },
            {
                "question_number": 1,
                "part": 3,
                "type": "short_answer",
                "question": "Một lượng khí ở áp suất 2 atm và thể tích 10 lít được nén đẳng nhiệt đến thể tích 4 lít. Áp suất khí sau khi nén là bao nhiêu atm?",
                "options": [],
                "correct_answer": "5"
            },
            {
                "question_number": 2,
                "part": 3,
                "type": "short_answer",
                "question": "Cần cung cấp một nhiệt lượng bao nhiêu kJ để đun nóng 2 kg nước từ 20 °C lên 70 °C? Biết nhiệt dung riêng của nước c = 4200 J/(kg.K).",
                "options": [],
                "correct_answer": "420"
            }
        ]
    },
    {
        "file_id": "pdf_vatly_01_de_thi_hoc_ky",
        "file_name": "vatly_01_de_thi_hoc_ky.pdf",
        "format_type": "pdf",
        "subject": "Vật lý",
        "style": "bottom_text",
        "style_description": "PDF đề kiểm tra học kỳ Vật lý Dòng điện xoay chiều, có bảng đáp án text cuối đề",
        "tags": ["vat_ly", "pdf", "dong_dien_xoay_chieu"],
        "answer_text_block": "1-C   2-A   3-D   4-B   5-C",
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Điện áp hiệu dụng của mạng điện xoay chiều u = 220sqrt(2)cos(100πt) V có giá trị là",
                "options": ["A. 110 V", "B. 220sqrt(2) V", "C. 220 V", "D. 100 V"],
                "correct_answer": "C. 220 V"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Dòng điện xoay chiều i = I_0 cos(omega * t) chạy qua cuộn cảm thuần có độ tự cảm L. Cảm kháng của cuộn cảm là",
                "options": ["A. Z_L = omega * L", "B. Z_L = 1 / (omega * L)", "C. Z_L = omega / L", "D. Z_L = L / omega"],
                "correct_answer": "A. Z_L = omega * L"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Hiện tượng cộng hưởng điện xảy ra trong đoạn mạch RLC nối tiếp khi thỏa mãn điều kiện nào?",
                "options": ["A. omega * L = R", "B. omega * C = R", "C. omega^2 * L * C = 2", "D. omega^2 * L * C = 1"],
                "correct_answer": "D. omega^2 * L * C = 1"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Hệ số công suất cos(phi) của đoạn mạch xoay chiều RLC nối tiếp được tính bằng",
                "options": ["A. Z / R", "B. R / Z", "C. R / Z_L", "D. Z_C / R"],
                "correct_answer": "B. R / Z"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Máy biến áp là thiết bị có chức năng",
                "options": ["A. biến đổi tần số dòng điện xoay chiều.", "B. biến đổi dòng điện xoay chiều thành một chiều.", "C. biến đổi điện áp dòng điện xoay chiều.", "D. làm tăng công suất dòng điện."],
                "correct_answer": "C. biến đổi điện áp dòng điện xoay chiều."
            }
        ]
    },

    # =========================================================================
    # 3. HÓA HỌC (4 files: 3 DOCX + 1 PDF)
    # =========================================================================
    {
        "file_id": "docx_hoahoc_01_cong_thuc_sub_super",
        "file_name": "hoahoc_01_cong_thuc_sub_super.docx",
        "format_type": "docx",
        "subject": "Hóa học",
        "style": "underline",
        "style_description": "Hóa học hữu cơ, chỉ số hóa học dưới sub (CH3COOC2H5, C6H12O6), đáp án gạch chân",
        "tags": ["hoa_hoc", "underline", "subscript", "este_lipit"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Este etyl axetat có công thức phân tử là",
                "options": ["A. C2H4O2", "B. C3H6O2", "C. C4H8O2", "D. C4H6O2"],
                "correct_answer": "C. C4H8O2"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Chất nào sau đây thuộc loại monosaccarit?",
                "options": ["A. Glucozơ", "B. Saccarozơ", "C. Tinh bột", "D. Xenlulozơ"],
                "correct_answer": "A. Glucozơ"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Chất nào dưới đây là amin bậc một?",
                "options": ["A. CH3-NH-CH3", "B. CH3-NH2", "C. (CH3)3N", "D. (C2H5)2NH"],
                "correct_answer": "B. CH3-NH2"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Thủy phân hoàn toàn este CH3COOCH3 trong dung dịch NaOH đun nóng thu được muối nào?",
                "options": ["A. HCOONa", "B. CH3COONa", "C. C2H5COONa", "D. CH3ONa"],
                "correct_answer": "B. CH3COONa"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Polime nào sau đây được điều chế bằng phản ứng trùng ngưng?",
                "options": ["A. Polietilen", "B. Poli(vinyl clorua)", "C. Nilon-6,6", "D. Polistiren"],
                "correct_answer": "C. Nilon-6,6"
            }
        ]
    },
    {
        "file_id": "docx_hoahoc_02_bang_dap_an_text",
        "file_name": "hoahoc_02_bang_dap_an_text.docx",
        "format_type": "docx",
        "subject": "Hóa học",
        "style": "bottom_text",
        "style_description": "Hóa học vô cơ Kim loại, không đánh dấu trong câu, có dòng text BẢNG ĐÁP ÁN: 1.A 2.D 3.B 4.C 5.A",
        "tags": ["hoa_hoc", "bottom_text", "kim_loai"],
        "answer_text_block": "1.A  2.D  3.B  4.C  5.A",
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Kim loại nào sau đây có tính dẫn điện tốt nhất?",
                "options": ["A. Bạc (Ag)", "B. Đồng (Cu)", "C. Vàng (Au)", "D. Nhôm (Al)"],
                "correct_answer": "A. Bạc (Ag)"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Kim loại nào sau đây là kim loại kiềm thổ?",
                "options": ["A. Natri (Na)", "B. Kali (K)", "C. Nhôm (Al)", "D. Canxi (Ca)"],
                "correct_answer": "D. Canxi (Ca)"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Để bảo vệ vỏ tàu biển bằng thép người ta thường gắn vào vỏ tàu các tấm kim loại nào?",
                "options": ["A. Đồng (Cu)", "B. Kẽm (Zn)", "C. Chì (Pb)", "D. Bạc (Ag)"],
                "correct_answer": "B. Kẽm (Zn)"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Dung dịch chất nào sau đây làm quỳ tím chuyển sang màu đỏ?",
                "options": ["A. NaOH", "B. NaCl", "C. HCl", "D. Ba(OH)2"],
                "correct_answer": "C. HCl"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Khí nào sau đây thoát ra khi cho Fe tác dụng với dung dịch H2SO4 loãng?",
                "options": ["A. H2", "B. SO2", "C. H2S", "D. O2"],
                "correct_answer": "A. H2"
            }
        ]
    },
    {
        "file_id": "docx_hoahoc_03_gdpt2018",
        "file_name": "hoahoc_03_gdpt2018.docx",
        "format_type": "docx",
        "subject": "Hóa học",
        "style": "gdpt_2018",
        "style_description": "Hóa học GDPT 2018 Cân bằng hóa học & Nhiệt hóa học: 3 phần MCQ, Đúng/Sai, Trả lời ngắn",
        "tags": ["hoa_hoc", "gdpt_2018", "can_bang_hoa_hoc"],
        "questions": [
            {
                "question_number": 1,
                "part": 1,
                "type": "mcq",
                "question": "Biểu thức hằng số cân bằng Kc của phản ứng N2(k) + 3H2(k) <=> 2NH3(k) là",
                "options": [
                    "A. Kc = [NH3]^2 / ([N2] * [H2]^3)",
                    "B. Kc = ([N2] * [H2]^3) / [NH3]^2",
                    "C. Kc = [NH3] / ([N2] * [H2])",
                    "D. Kc = [NH3]^2 / ([N2] + [H2]^3)"
                ],
                "correct_answer": "A. Kc = [NH3]^2 / ([N2] * [H2]^3)"
            },
            {
                "question_number": 2,
                "part": 1,
                "type": "mcq",
                "question": "Theo thuyết Bronsted - Lowry, axit là chất có khả năng",
                "options": ["A. cho proton (H+)", "B. nhận proton (H+)", "C. cho electron", "D. nhận electron"],
                "correct_answer": "A. cho proton (H+)"
            },
            {
                "question_number": 1,
                "part": 2,
                "type": "true_false",
                "question": "Cho phản ứng tổng hợp amoniac: N2(k) + 3H2(k) <=> 2NH3(k); Delta_r H_298 = -92 kJ. Xét các nhận định:",
                "options": [
                    "a) Phản ứng thuận là phản ứng tỏa nhiệt",
                    "b) Khi tăng nhiệt độ, cân bằng chuyển dịch theo chiều thuận",
                    "c) Khi tăng áp suất của hệ, cân bằng chuyển dịch sang chiều thuận làm tăng hiệu suất tạo NH3",
                    "d) Chất xúc tác bột sắt giúp làm tăng tốc độ đạt trạng thái cân bằng nhưng không làm chuyển dịch cân bằng"
                ],
                "correct_answer": {"a": True, "b": False, "c": True, "d": True}
            },
            {
                "question_number": 2,
                "part": 2,
                "type": "true_false",
                "question": "Về dung dịch nước và thang đo pH:",
                "options": [
                    "a) Ở 25 °C, tích số ion của nước Kw = [H+] * [OH-] = 1,0 * 10^-14",
                    "b) Dung dịch có pH = 3 có môi trường bazơ",
                    "c) Khi pha loãng dung dịch HCl bằng nước cất thì độ pH của dung dịch tăng dần",
                    "d) Dung dịch muối NaCl trong nước có pH xấp xỉ bằng 7"
                ],
                "correct_answer": {"a": True, "b": False, "c": True, "d": True}
            },
            {
                "question_number": 1,
                "part": 3,
                "type": "short_answer",
                "question": "Tính nồng độ pH của dung dịch HCl 0,001 M ở 25 °C.",
                "options": [],
                "correct_answer": "3"
            },
            {
                "question_number": 2,
                "part": 3,
                "type": "short_answer",
                "question": "Hòa tan hoàn toàn 2,4 gam Mg vào dung dịch HCl dư. Thể tích khí H2 thu được ở điều kiện chuẩn (đkc, 1 mol = 24,79 lít) là bao nhiêu lít? (Làm tròn đến 2 chữ số thập phân)",
                "options": [],
                "correct_answer": "2.48"
            }
        ]
    },
    {
        "file_id": "pdf_hoahoc_01_trac_nghiem",
        "file_name": "hoahoc_01_trac_nghiem.pdf",
        "format_type": "pdf",
        "subject": "Hóa học",
        "style": "bottom_text",
        "style_description": "PDF trắc nghiệm Hóa học vô cơ tổng hợp có bảng đáp án text cuối đề",
        "tags": ["hoa_hoc", "pdf", "vo_co"],
        "answer_text_block": "1-B   2-C   3-A   4-D   5-B",
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Chất khí nào sau đây gây ra hiệu ứng nhà kính mạnh nhất trong khí quyển?",
                "options": ["A. O2", "B. CO2", "C. N2", "D. H2"],
                "correct_answer": "B. CO2"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Kim loại nào sau đây phản ứng mãnh liệt với nước ở nhiệt độ thường?",
                "options": ["A. Fe", "B. Cu", "C. Na", "D. Ag"],
                "correct_answer": "C. Na"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Quặng bauxit là nguyên liệu chính để sản xuất kim loại nào sau đây?",
                "options": ["A. Nhôm (Al)", "B. Sắt (Fe)", "C. Đồng (Cu)", "D. Kẽm (Zn)"],
                "correct_answer": "A. Nhôm (Al)"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Số oxi hóa của nguyên tố lưu huỳnh (S) trong hợp chất H2SO4 là",
                "options": ["A. -2", "B. 0", "C. +4", "D. +6"],
                "correct_answer": "D. +6"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Để khử chua cho đất trồng bị nhiễm phèn, người nông dân thường bón vào đất chất nào?",
                "options": ["A. Muối ăn (NaCl)", "B. Vôi sống (CaO)", "C. Phân đạm ure", "D. Thạch cao"],
                "correct_answer": "B. Vôi sống (CaO)"
            }
        ]
    },

    # =========================================================================
    # 4. SINH HỌC (4 files: 3 DOCX + 1 PDF)
    # =========================================================================
    {
        "file_id": "docx_sinhhoc_01_boi_dam",
        "file_name": "sinhhoc_01_boi_dam.docx",
        "format_type": "docx",
        "subject": "Sinh học",
        "style": "bold",
        "style_description": "Sinh học di truyền học Menđen, đáp án đúng in ĐẬM trong file Word",
        "tags": ["sinh_hoc", "bold", "di_truyen"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Theo quy luật phân li của Menđen, mỗi tính trạng do một cặp alen quy định, các alen tồn tại trong tế bào",
                "options": ["A. hòa lẫn vào nhau.", "B. độc lập và không hòa lẫn vào nhau.", "C. dính liền nhau.", "D. lấn át nhau hoàn toàn."],
                "correct_answer": "B. độc lập và không hòa lẫn vào nhau."
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Cơ thể có kiểu gen nào sau đây được gọi là thể đồng hợp lặn?",
                "options": ["A. Aa", "B. AA", "C. aa", "D. AaBb"],
                "correct_answer": "C. aa"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Phép lai P: Aa x Aa cho đời con F1 có tỉ lệ kiểu gen là",
                "options": ["A. 1 AA : 2 Aa : 1 aa", "B. 3 AA : 1 aa", "C. 1 Aa : 1 aa", "D. 100% Aa"],
                "correct_answer": "A. 1 AA : 2 Aa : 1 aa"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Ở ruồi giấm (Drosophila melanogaster), Morgan phát hiện hiện tượng liên kết gen ở giới tính nào?",
                "options": ["A. Chỉ ruồi cái", "B. Chỉ ruồi đực", "C. Cả ruồi đực và ruồi cái", "D. Không có ở ruồi giấm"],
                "correct_answer": "B. Chỉ ruồi đực"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Một gen có chiều dài 5100 Å thì tổng số nucleotit của gen đó là",
                "options": ["A. 1500", "B. 3000", "C. 4050", "D. 6000"],
                "correct_answer": "B. 3000"
            }
        ]
    },
    {
        "file_id": "docx_sinhhoc_02_phuong_an_1_dong",
        "file_name": "sinhhoc_02_phuong_an_1_dong.docx",
        "format_type": "docx",
        "subject": "Sinh học",
        "style": "asterisk",
        "style_description": "Sinh học tế bào và NST, các phương án A B C D nằm trên cùng 1 dòng, có dấu sao trước đáp án đúng",
        "tags": ["sinh_hoc", "asterisk", "single_line_options"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "layout": "single_line",
                "question": "Bộ nhiễm sắc thể lưỡng bội 2n của loài người bình thường là bao nhiêu chiếc?",
                "options": ["A. 2n = 44", "B. 2n = 46", "C. 2n = 48", "D. 2n = 23"],
                "correct_answer": "B. 2n = 46"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "layout": "single_line",
                "question": "Quá trình nhân đôi ADN diễn ra theo nguyên tắc nào dưới đây?",
                "options": ["A. Bán bảo toàn", "B. Bảo toàn hoàn toàn", "C. Ngẫu nhiên", "D. Phân tán"],
                "correct_answer": "A. Bán bảo toàn"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "layout": "single_line",
                "question": "Mã di truyền mở đầu cho quá trình dịch mã trên mARN là",
                "options": ["A. UAA", "B. UAG", "C. AUG", "D. UGA"],
                "correct_answer": "C. AUG"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "layout": "single_line",
                "question": "Đột biến số lượng NST thể một có công thức nhiễm sắc thể là",
                "options": ["A. 2n + 1", "B. 2n - 1", "C. 3n", "D. 2n - 2"],
                "correct_answer": "B. 2n - 1"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "layout": "single_line",
                "question": "Bào quan nào sau đây đóng vai trò là 'nhà máy' tổng hợp năng lượng ATP của tế bào?",
                "options": ["A. Riboxom", "B. Ti thể", "C. Lưới nội chất", "D. Thể Golgi"],
                "correct_answer": "B. Ti thể"
            }
        ]
    },
    {
        "file_id": "docx_sinhhoc_03_gdpt2018",
        "file_name": "sinhhoc_03_gdpt2018.docx",
        "format_type": "docx",
        "subject": "Sinh học",
        "style": "gdpt_2018",
        "style_description": "Sinh học GDPT 2018 Di truyền phân tử & Quần thể: 3 phần MCQ, Đúng/Sai, Trả lời ngắn",
        "tags": ["sinh_hoc", "gdpt_2018", "di_truyen_hoc"],
        "questions": [
            {
                "question_number": 1,
                "part": 1,
                "type": "mcq",
                "question": "Enzim nào sau đây đóng vai trò tháo xoắn phân tử ADN trong quá trình nhân đôi?",
                "options": ["A. ADN polimeraza", "B. Enzim tháo xoắn (Helicaza)", "C. Ligaza", "D. ARN polimeraza"],
                "correct_answer": "B. Enzim tháo xoắn (Helicaza)"
            },
            {
                "question_number": 2,
                "part": 1,
                "type": "mcq",
                "question": "Dạng đột biến cấu trúc NST nào sau đây làm tăng cường độ biểu hiện của một tính trạng?",
                "options": ["A. Mất đoạn", "B. Lặp đoạn", "C. Đảo đoạn", "D. Chuyển đoạn tương hỗ"],
                "correct_answer": "B. Lặp đoạn"
            },
            {
                "question_number": 1,
                "part": 2,
                "type": "true_false",
                "question": "Xét một gen ở sinh vật nhân sơ có chiều dài 4080 Å, có số nucleotit loại A chiếm 20% tổng số nucleotit. Nhận định:",
                "options": [
                    "a) Tổng số nucleotit của gen bằng 2400",
                    "b) Số nucleotit loại Adenin (A) của gen là 480",
                    "c) Số nucleotit loại Guanin (G) của gen là 720",
                    "d) Tổng số liên kết hiđro của gen là 3120"
                ],
                "correct_answer": {"a": True, "b": True, "c": True, "d": True}
            },
            {
                "question_number": 2,
                "part": 2,
                "type": "true_false",
                "question": "Về cấu trúc và chức năng của các loại ARN trong tế bào:",
                "options": [
                    "a) mARN có chức năng truyền đạt thông tin di truyền từ nhân ra tế bào chất",
                    "b) tARN có bộ ba đối mã (anticodon) khớp bổ sung với codon trên mARN",
                    "c) rARN là thành phần cấu tạo nên riboxom",
                    "d) Cả ba loại ARN đều có cấu trúc mạch kép dạng xoắn đều đặn như ADN"
                ],
                "correct_answer": {"a": True, "b": True, "c": True, "d": False}
            },
            {
                "question_number": 1,
                "part": 3,
                "type": "short_answer",
                "question": "Một quần thể thực vật tự thụ phấn có thành phần kiểu gen ở thế hệ P là: 0,2 AA : 0,8 Aa. Tính tỉ lệ kiểu gen dị hợp Aa ở thế hệ F1.",
                "options": [],
                "correct_answer": "0.4"
            },
            {
                "question_number": 2,
                "part": 3,
                "type": "short_answer",
                "question": "Cơ thể có kiểu gen AaBbCcDd tự thụ phấn có thể tạo ra tối đa bao nhiêu loại kiểu gen khác nhau ở đời con?",
                "options": [],
                "correct_answer": "81"
            }
        ]
    },
    {
        "file_id": "pdf_sinhhoc_01_thi_thu",
        "file_name": "sinhhoc_01_thi_thu.pdf",
        "format_type": "pdf",
        "subject": "Sinh học",
        "style": "bottom_text",
        "style_description": "PDF đề thi thử Sinh học Hệ sinh thái & Tiến hóa, bảng đáp án text cuối trang",
        "tags": ["sinh_hoc", "pdf", "he_sinh_thai"],
        "answer_text_block": "1-D   2-B   3-A   4-C   5-B",
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Sinh vật nào sau đây đóng vai trò là sinh vật sản xuất trong hệ sinh thái?",
                "options": ["A. Nấm hoại sinh", "B. Động vật ăn cỏ", "C. Giun đất", "D. Thực vật quang hợp"],
                "correct_answer": "D. Thực vật quang hợp"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Nhân tố tiến hóa nào sau đây có thể làm thay đổi tần số alen của quần thể theo một hướng xác định?",
                "options": ["A. Đột biến", "B. Chọn lọc tự nhiên", "C. Các yếu tố ngẫu nhiên", "D. Giao phối không ngẫu nhiên"],
                "correct_answer": "B. Chọn lọc tự nhiên"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Mối quan hệ giữa nấm và tảo đơn bào trong địa y là mối quan hệ sinh thái nào?",
                "options": ["A. Cộng sinh", "B. Hội sinh", "C. Ký sinh", "D. Cạnh tranh"],
                "correct_answer": "A. Cộng sinh"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Tháp sinh thái nào sau đây luôn có dạng đáy rộng ở dưới và thu hẹp dần lên trên mà không bị biến dạng?",
                "options": ["A. Tháp số lượng", "B. Tháp sinh khối", "C. Tháp năng lượng", "D. Tháp tuổi"],
                "correct_answer": "C. Tháp năng lượng"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Tập hợp các cá thể cùng loài sống trong một khoảng không gian và thời gian xác định được gọi là",
                "options": ["A. quần xã sinh vật.", "B. quần thể sinh vật.", "C. hệ sinh thái.", "D. sinh quyển."],
                "correct_answer": "B. quần thể sinh vật."
            }
        ]
    },

    # =========================================================================
    # 5. TIẾNG ANH (6 files: 4 DOCX + 2 PDF)
    # =========================================================================
    {
        "file_id": "docx_tienganh_01_reading_passage",
        "file_name": "tienganh_01_reading_passage.docx",
        "format_type": "docx",
        "subject": "Tiếng Anh",
        "style": "underline",
        "style_description": "Tiếng Anh có đoạn văn đọc hiểu chung (group_title) cho 3 câu, tiếp theo là 2 câu ngữ pháp riêng, đáp án gạch chân",
        "tags": ["tieng_anh", "reading_comprehension", "group_title", "underline"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "group_title": "Read the following passage and mark the letter A, B, C, or D on your answer sheet to indicate the correct answer to each of the questions.\n\nRenewable energy is energy derived from natural resources that replenish themselves faster than they are consumed. Sunlight and wind are good examples. Renewable energy sources are plentiful and all around us. Fossil fuels - coal, oil and gas - on the other hand, are non-renewable resources that take hundreds of millions of years to form. Generating renewable energy creates far lower emissions than burning fossil fuels.",
                "question": "What is the main topic of the passage?",
                "options": [
                    "A. The advantages of renewable energy",
                    "B. The formation of coal and oil",
                    "C. The danger of sunlight",
                    "D. Industrial development"
                ],
                "correct_answer": "A. The advantages of renewable energy"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "group_title": "Read the following passage and mark the letter A, B, C, or D on your answer sheet to indicate the correct answer to each of the questions.\n\nRenewable energy is energy derived from natural resources that replenish themselves faster than they are consumed. Sunlight and wind are good examples. Renewable energy sources are plentiful and all around us. Fossil fuels - coal, oil and gas - on the other hand, are non-renewable resources that take hundreds of millions of years to form. Generating renewable energy creates far lower emissions than burning fossil fuels.",
                "question": "According to the passage, fossil fuels take how long to form?",
                "options": [
                    "A. A few years",
                    "B. Hundreds of millions of years",
                    "C. Thousands of years",
                    "D. A few decades"
                ],
                "correct_answer": "B. Hundreds of millions of years"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "group_title": "Read the following passage and mark the letter A, B, C, or D on your answer sheet to indicate the correct answer to each of the questions.\n\nRenewable energy is energy derived from natural resources that replenish themselves faster than they are consumed. Sunlight and wind are good examples. Renewable energy sources are plentiful and all around us. Fossil fuels - coal, oil and gas - on the other hand, are non-renewable resources that take hundreds of millions of years to form. Generating renewable energy creates far lower emissions than burning fossil fuels.",
                "question": "The word 'plentiful' in the passage is closest in meaning to",
                "options": [
                    "A. scarce",
                    "B. abundant",
                    "C. dangerous",
                    "D. expensive"
                ],
                "correct_answer": "B. abundant"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "group_title": "",
                "question": "Mark the letter A, B, C, or D to indicate the correct answer: She ______ to Paris three times this year.",
                "options": [
                    "A. has been",
                    "B. went",
                    "C. was going",
                    "D. had gone"
                ],
                "correct_answer": "A. has been"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "group_title": "",
                "question": "If it ______ tomorrow, we will cancel the picnic in the park.",
                "options": [
                    "A. rained",
                    "B. will rain",
                    "C. rains",
                    "D. would rain"
                ],
                "correct_answer": "C. rains"
            }
        ]
    },
    {
        "file_id": "docx_tienganh_02_stress_phonetics",
        "file_name": "tienganh_02_stress_phonetics.docx",
        "format_type": "docx",
        "subject": "Tiếng Anh",
        "style": "red",
        "style_description": "Tiếng Anh ngữ âm & trọng âm, đáp án tô màu ĐỎ (#FF0000)",
        "tags": ["tieng_anh", "phonetics", "stress", "red_font"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Mark the letter A, B, C, or D to indicate the word whose underlined part differs from the other three in pronunciation:",
                "options": ["A. played", "B. stayed", "C. wanted", "D. loved"],
                "correct_answer": "C. wanted"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Mark the letter A, B, C, or D to indicate the word whose underlined part differs from the other three in pronunciation:",
                "options": ["A. cats", "B. books", "C. maps", "D. dogs"],
                "correct_answer": "D. dogs"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Mark the letter A, B, C, or D to indicate the word that differs from the other three in the position of primary stress:",
                "options": ["A. teacher", "B. student", "C. hotel", "D. doctor"],
                "correct_answer": "C. hotel"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Mark the letter A, B, C, or D to indicate the word that differs from the other three in the position of primary stress:",
                "options": ["A. important", "B. beautiful", "C. dangerous", "D. popular"],
                "correct_answer": "A. important"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Mark the letter A, B, C, or D to indicate the word that differs from the other three in the position of primary stress:",
                "options": ["A. biology", "B. geography", "C. economy", "D. economics"],
                "correct_answer": "D. economics"
            }
        ]
    },
    {
        "file_id": "docx_tienganh_03_synonym_antonym",
        "file_name": "tienganh_03_synonym_antonym.docx",
        "format_type": "docx",
        "subject": "Tiếng Anh",
        "style": "bottom_table",
        "style_description": "Tiếng Anh Từ đồng nghĩa / Trái nghĩa, có Bảng đáp án Table ở cuối bài",
        "tags": ["tieng_anh", "synonym", "antonym", "bottom_table"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Mark the letter A, B, C, or D to indicate the word(s) CLOSEST in meaning to the underlined word: The government decided to ABOLISH the old tax regulation.",
                "options": ["A. cancel", "B. continue", "C. approve", "D. suggest"],
                "correct_answer": "A. cancel"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Mark the letter A, B, C, or D to indicate the word(s) CLOSEST in meaning to the underlined word: She gave a BRILLIANT performance on stage last night.",
                "options": ["A. dull", "B. poor", "C. outstanding", "D. regular"],
                "correct_answer": "C. outstanding"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Mark the letter A, B, C, or D to indicate the word(s) OPPOSITE in meaning to the underlined word: It is DANGEROUS to swim in this river because of strong currents.",
                "options": ["A. risky", "B. safe", "C. hazardous", "D. harmful"],
                "correct_answer": "B. safe"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Mark the letter A, B, C, or D to indicate the word(s) OPPOSITE in meaning to the underlined word: He was very GENEROUS to donate his savings to the hospital.",
                "options": ["A. mean", "B. kind", "C. helpful", "D. friendly"],
                "correct_answer": "A. mean"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Mark the letter A, B, C, or D to indicate the word(s) OPPOSITE in meaning to the underlined word: The company saw a DRAMATIC increase in profits this quarter.",
                "options": ["A. huge", "B. sudden", "C. slight", "D. remarkable"],
                "correct_answer": "C. slight"
            }
        ]
    },
    {
        "file_id": "docx_tienganh_04_soan_bang_2cot",
        "file_name": "tienganh_04_soan_bang_2cot.docx",
        "format_type": "docx",
        "subject": "Tiếng Anh",
        "style": "asterisk",
        "style_description": "Tiếng Anh Giao tiếp hội thoại, đáp án có dấu hoa thị * trước ký tự",
        "tags": ["tieng_anh", "conversation", "asterisk"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "David: 'Would you like some coffee?' - Sarah: '______'",
                "options": [
                    "A. Yes, I'd love to.",
                    "B. No, thanks. I'm full.",
                    "C. It's too late.",
                    "D. Never mind."
                ],
                "correct_answer": "A. Yes, I'd love to."
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Tom: 'Thank you very much for your great assistance.' - Mary: '______'",
                "options": [
                    "A. You're welcome.",
                    "B. No problem at all.",
                    "C. Don't mention it.",
                    "D. All of the above."
                ],
                "correct_answer": "D. All of the above."
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Peter: 'I have passed the university entrance examination!' - Lisa: '______'",
                "options": [
                    "A. Good luck!",
                    "B. Congratulations!",
                    "C. What a pity!",
                    "D. That's a bad idea."
                ],
                "correct_answer": "B. Congratulations!"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Customer: 'Could I try this jacket on?' - Shop assistant: '______'",
                "options": [
                    "A. Yes, of course. The fitting room is over there.",
                    "B. No, you can't buy it.",
                    "C. It is too expensive.",
                    "D. I don't know."
                ],
                "correct_answer": "A. Yes, of course. The fitting room is over there."
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Jack: 'What a lovely garden you have!' - Emily: '______'",
                "options": [
                    "A. It's very kind of you to say so.",
                    "B. No, it isn't nice.",
                    "C. You are right.",
                    "D. I like it too."
                ],
                "correct_answer": "A. It's very kind of you to say so."
            }
        ]
    },
    {
        "file_id": "pdf_tienganh_01_reading_grammar",
        "file_name": "tienganh_01_reading_grammar.pdf",
        "format_type": "pdf",
        "subject": "Tiếng Anh",
        "style": "bottom_text",
        "style_description": "PDF đề thi Tiếng Anh Ngữ pháp & Điền từ, bảng đáp án text cuối đề",
        "tags": ["tieng_anh", "pdf", "grammar"],
        "answer_text_block": "1.B   2.A   3.D   4.C   5.A",
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "The boy ______ won the first prize in the national competition is my neighbor.",
                "options": ["A. which", "B. who", "C. whom", "D. whose"],
                "correct_answer": "B. who"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Although he was extremely tired, ______ to complete the marathon.",
                "options": ["A. he managed", "B. but he managed", "C. so he managed", "D. yet he managed"],
                "correct_answer": "A. he managed"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "She suggested ______ for a picnic in the countryside this weekend.",
                "options": ["A. to go", "B. go", "C. gone", "D. going"],
                "correct_answer": "D. going"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "The heavier the traffic is, ______ it takes to get to work.",
                "options": ["A. the longer time", "B. longer", "C. the longer", "D. the longest"],
                "correct_answer": "C. the longer"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Neither Peter nor his friends ______ present at the conference yesterday.",
                "options": ["A. were", "B. was", "C. are", "D. is"],
                "correct_answer": "A. were"
            }
        ]
    },
    {
        "file_id": "pdf_tienganh_02_chuan_thpt",
        "file_name": "tienganh_02_chuan_thpt.pdf",
        "format_type": "pdf",
        "subject": "Tiếng Anh",
        "style": "bottom_text",
        "style_description": "PDF đề thi thử tốt nghiệp THPT Quốc gia môn Tiếng Anh có bảng đáp án text cuối",
        "tags": ["tieng_anh", "pdf", "thpt"],
        "answer_text_block": "1-A   2-C   3-B   4-D   5-A",
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "You ______ park your car here. It is strictly forbidden by law.",
                "options": ["A. mustn't", "B. needn't", "C. shouldn't", "D. don't have to"],
                "correct_answer": "A. mustn't"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "If I had known your telephone number, I ______ you right after the incident.",
                "options": ["A. will call", "B. would call", "C. would have called", "D. had called"],
                "correct_answer": "C. would have called"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "By the time we arrived at the cinema, the movie ______ for ten minutes.",
                "options": ["A. started", "B. had started", "C. has started", "D. was starting"],
                "correct_answer": "B. had started"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "The new shopping mall ______ next Monday by the city mayor.",
                "options": ["A. opens", "B. will open", "C. is opened", "D. will be opened"],
                "correct_answer": "D. will be opened"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Despite the severe storm, the flight landed ______ at the airport.",
                "options": ["A. safely", "B. safe", "C. safety", "D. safeness"],
                "correct_answer": "A. safely"
            }
        ]
    }
]
