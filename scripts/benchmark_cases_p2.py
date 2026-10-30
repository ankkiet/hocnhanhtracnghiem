"""
Định nghĩa 40 bộ test cases chuẩn thực tế cho Benchmark Suite của HocNhanhTN.
Phần 2: Lịch sử, Địa lý, GDCD - KTPL, Tin học, Ngữ văn, Định dạng đặc biệt (17 files)
Tổng cộng: 23 (Phần 1) + 17 (Phần 2) = 40 files
"""

BENCHMARK_CASES_P2 = [
    # =========================================================================
    # 6. LỊCH SỬ (4 files: 3 DOCX + 1 PDF)
    # =========================================================================
    {
        "file_id": "docx_lichsu_01_gach_chan",
        "file_name": "lichsu_01_gach_chan.docx",
        "format_type": "docx",
        "subject": "Lịch sử",
        "style": "underline",
        "style_description": "Lịch sử Việt Nam 1930 - 1945, đáp án đúng gạch chân trong câu",
        "tags": ["lich_su", "underline", "cach_mang_thang_tam"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Đảng Cộng sản Việt Nam ra đời vào đầu năm 1930 là kết quả của sự kết hợp giữa",
                "options": [
                    "A. chủ nghĩa Mác - Lênin với phong trào công nhân và phong trào yêu nước.",
                    "B. chủ nghĩa Mác - Lênin với phong trào nông dân.",
                    "C. phong trào công nhân với phong trào dân chủ tư sản.",
                    "D. phong trào yêu nước với tư tưởng Tam dân của Tôn Trung Sơn."
                ],
                "correct_answer": "A. chủ nghĩa Mác - Lênin với phong trào công nhân và phong trào yêu nước."
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Hội nghị thành lập Đảng Cộng sản Việt Nam (đầu năm 1930) do ai chủ trì?",
                "options": ["A. Trần Phú", "B. Nguyễn Ái Quốc", "C. Lê Hồng Phong", "D. Hà Huy Tập"],
                "correct_answer": "B. Nguyễn Ái Quốc"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Mặt trận Việt Minh được thành lập vào thời gian nào?",
                "options": ["A. Tháng 5 năm 1941", "B. Tháng 11 năm 1939", "C. Tháng 1 năm 1941", "D. Tháng 8 năm 1945"],
                "correct_answer": "A. Tháng 5 năm 1941"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Bản Tuyên ngôn Độc lập do Chủ tịch Hồ Chí Minh đọc tại Quảng trường Ba Đình vào ngày",
                "options": ["A. 19/8/1945", "B. 2/9/1945", "C. 23/8/1945", "D. 30/8/1945"],
                "correct_answer": "B. 2/9/1945"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Cách mạng tháng Tám năm 1945 ở Việt Nam đã lật đổ ách thống trị của",
                "options": [
                    "A. phát xít Nhật và thực dân Pháp.",
                    "B. đế quốc Mỹ và chính quyền tay sai.",
                    "C. thực dân Anh và quân Trung Hoa Dân quốc.",
                    "D. thực dân Bồ Đào Nha."
                ],
                "correct_answer": "A. phát xít Nhật và thực dân Pháp."
            }
        ]
    },
    {
        "file_id": "docx_lichsu_02_bang_dap_an_table",
        "file_name": "lichsu_02_bang_dap_an_table.docx",
        "format_type": "docx",
        "subject": "Lịch sử",
        "style": "bottom_table",
        "style_description": "Lịch sử Kháng chiến chống Mỹ, không đánh dấu trong câu, Bảng đáp án Table cuối đề",
        "tags": ["lich_su", "bottom_table", "khang_chien_chong_my"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Chiến thắng nào của quân dân miền Nam đã mở ra phong trào 'Tìm Mỹ mà đánh, lùng ngụy mà diệt'?",
                "options": ["A. Chiến thắng Vạn Tường (1965)", "B. Chiến thắng Ấp Bắc (1963)", "C. Chiến thắng Bình Giã (1964)", "D. Chiến thắng Ba Gia (1965)"],
                "correct_answer": "A. Chiến thắng Vạn Tường (1965)"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Chiến dịch nào đã kết thúc thắng lợi cuộc kháng chiến chống Mỹ, cứu nước của nhân dân ta?",
                "options": ["A. Chiến dịch Tây Nguyên", "B. Chiến dịch Huế - Đà Nẵng", "C. Chiến dịch Hồ Chí Minh", "D. Chiến dịch Đường 9 - Nam Lào"],
                "correct_answer": "C. Chiến dịch Hồ Chí Minh"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Hiệp định Pari về chấm dứt chiến tranh, lập lại hòa bình ở Việt Nam được ký kết vào năm nào?",
                "options": ["A. 1972", "B. 1973", "C. 1974", "D. 1975"],
                "correct_answer": "B. 1973"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Trận 'Điện Biên Phủ trên không' diễn ra vào thời gian nào?",
                "options": ["A. Tháng 12/1972", "B. Tháng 10/1972", "C. Tháng 1/1973", "D. Tháng 5/1972"],
                "correct_answer": "A. Tháng 12/1972"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Chiến lược 'Chiến tranh đặc biệt' (1961 - 1965) của đế quốc Mỹ ở miền Nam Việt Nam có công thức cơ bản là",
                "options": [
                    "A. quân đội Sài Gòn + cố vấn Mỹ + vũ khí Mỹ.",
                    "B. quân viễn chinh Mỹ + quân đội Sài Gòn.",
                    "C. quân viễn chinh Mỹ + quân đồng minh của Mỹ.",
                    "D. quân đội Sài Gòn + hỏa lực không quân Mỹ."
                ],
                "correct_answer": "A. quân đội Sài Gòn + cố vấn Mỹ + vũ khí Mỹ."
            }
        ]
    },
    {
        "file_id": "docx_lichsu_03_gdpt2018",
        "file_name": "lichsu_03_gdpt2018.docx",
        "format_type": "docx",
        "subject": "Lịch sử",
        "style": "gdpt_2018",
        "style_description": "Lịch sử chuẩn GDPT 2018: Phần I MCQ 3 câu, Phần II Đúng/Sai 2 câu phân tích đoạn tư liệu lịch sử",
        "tags": ["lich_su", "gdpt_2018", "tu_lieu_lich_su"],
        "questions": [
            {
                "question_number": 1,
                "part": 1,
                "type": "mcq",
                "question": "Tổ chức Hiệp hội các quốc gia Đông Nam Á (ASEAN) được thành lập tại Bangkok (Thái Lan) vào năm nào?",
                "options": ["A. 1967", "B. 1975", "C. 1995", "D. 1999"],
                "correct_answer": "A. 1967"
            },
            {
                "question_number": 2,
                "part": 1,
                "type": "mcq",
                "question": "Việt Nam chính thức trở thành thành viên thứ 7 của ASEAN vào năm nào?",
                "options": ["A. 1992", "B. 1995", "C. 1997", "D. 1998"],
                "correct_answer": "B. 1995"
            },
            {
                "question_number": 3,
                "part": 1,
                "type": "mcq",
                "question": "Nguyên tắc cơ bản nào sau đây được ghi nhận trong Hiến chương ASEAN?",
                "options": [
                    "A. Không can thiệp vào công việc nội bộ của nhau",
                    "B. Xây dựng liên minh quân sự chung",
                    "C. Sử dụng đồng tiền chung",
                    "D. Bãi bỏ hoàn toàn biên giới quốc gia"
                ],
                "correct_answer": "A. Không can thiệp vào công việc nội bộ của nhau"
            },
            {
                "question_number": 1,
                "part": 2,
                "type": "true_false",
                "question": "Đọc đoạn tư liệu sau đây: 'Toàn thể dân tộc Việt Nam quyết đem tất cả tinh thần và lực lượng, tính mạng và của cải để giữ vững quyền tự do, độc lập ấy.' (Tuyên ngôn Độc lập, 1945). Xét các mệnh đề:",
                "options": [
                    "a) Đoạn trích khẳng định ý chí sắt đá của nhân dân Việt Nam trong việc bảo vệ nền độc lập dân tộc",
                    "b) Văn bản này được đọc tại thủ đô Hà Nội sau khi Cách mạng tháng Tám thành công trọn vẹn",
                    "c) Tuyên ngôn Độc lập năm 1945 tuyên bố xóa bỏ hoàn toàn chế độ phong kiến tồn tại hàng nghìn năm ở Việt Nam",
                    "d) Bản Tuyên ngôn Độc lập chỉ có ý nghĩa đối với nội bộ nước Việt Nam, không có giá trị quốc tế"
                ],
                "correct_answer": {"a": True, "b": True, "c": True, "d": False}
            },
            {
                "question_number": 2,
                "part": 2,
                "type": "true_false",
                "question": "Về quá trình mở rộng và phát triển của ASEAN từ 5 nước sáng lập thành 10 nước thành viên:",
                "options": [
                    "a) Sự gia nhập của Việt Nam năm 1995 đã mở đầu cho việc kết nạp các nước còn lại trên bán đảo Đông Dương",
                    "b) ASEAN đã thành lập Cộng đồng ASEAN với 3 trụ cột vững chắc vào cuối năm 2015",
                    "c) Mọi quyết định của ASEAN đều phải đạt được sự đồng thuận tuyệt đối của tất cả các quốc gia thành viên",
                    "d) ASEAN là một tổ chức liên minh phòng thủ quân sự tương tự như NATO ở châu Âu"
                ],
                "correct_answer": {"a": True, "b": True, "c": True, "d": False}
            }
        ]
    },
    {
        "file_id": "pdf_lichsu_01_on_tap",
        "file_name": "lichsu_01_on_tap.pdf",
        "format_type": "pdf",
        "subject": "Lịch sử",
        "style": "bottom_text",
        "style_description": "PDF đề ôn tập Lịch sử thế giới hiện đại có bảng đáp án text cuối đề",
        "tags": ["lich_su", "pdf", "the_gioi_hien_dai"],
        "answer_text_block": "1-C   2-A   3-D   4-B   5-A",
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Hội nghị Ianta (tháng 2/1945) có sự tham gia của nguyên thủ ba cường quốc nào?",
                "options": ["A. Liên Xô, Mỹ, Pháp", "B. Mỹ, Anh, Pháp", "C. Liên Xô, Mỹ, Anh", "D. Mỹ, Anh, Trung Quốc"],
                "correct_answer": "C. Liên Xô, Mỹ, Anh"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Mục đích tối cao của tổ chức Liên hợp quốc khi thành lập là",
                "options": [
                    "A. duy trì hòa bình và an ninh thế giới.",
                    "B. thúc đẩy phát triển kinh tế toàn cầu.",
                    "C. ngăn chặn sự phát triển của chủ nghĩa xã hội.",
                    "D. hỗ trợ tài chính cho các nước nghèo."
                ],
                "correct_answer": "A. duy trì hòa bình và an ninh thế giới."
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Chiến tranh lạnh chính thức kết thúc vào thời điểm nào?",
                "options": ["A. Năm 1975", "B. Năm 1985", "C. Năm 1989", "D. Năm 1991"],
                "correct_answer": "D. Năm 1991"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Năm 1960 được lịch sử ghi nhận là 'Năm châu Phi' vì có bao nhiêu quốc gia giành được độc lập?",
                "options": ["A. 15 quốc gia", "B. 17 quốc gia", "C. 20 quốc gia", "D. 25 quốc gia"],
                "correct_answer": "B. 17 quốc gia"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Xu thế phát triển chung của thế giới sau khi Chiến tranh lạnh chấm dứt là",
                "options": [
                    "A. hòa bình, ổn định và hợp tác phát triển kinh tế.",
                    "B. chạy đua vũ trang và căng thẳng quân sự.",
                    "C. đối đầu gay gắt giữa hai khối tư bản và xã hội chủ nghĩa.",
                    "D. chia rẽ sâu sắc về địa chính trị."
                ],
                "correct_answer": "A. hòa bình, ổn định và hợp tác phát triển kinh tế."
            }
        ]
    },

    # =========================================================================
    # 7. ĐỊA LÝ (4 files: 3 DOCX + 1 PDF)
    # =========================================================================
    {
        "file_id": "docx_diali_01_boi_do",
        "file_name": "diali_01_boi_do.docx",
        "format_type": "docx",
        "subject": "Địa lý",
        "style": "red",
        "style_description": "Địa lý tự nhiên Việt Nam, đáp án đúng tô chữ ĐỎ (#FF0000)",
        "tags": ["dia_ly", "red_font", "tu_nhien_viet_nam"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Nước ta nằm hoàn toàn trong vùng nội chí tuyến của bán cầu nào?",
                "options": ["A. Bán cầu Tây", "B. Bán cầu Nam", "C. Bán cầu Bắc", "D. Bán cầu Đông và Nam"],
                "correct_answer": "C. Bán cầu Bắc"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Đặc điểm nổi bật của địa hình nước ta là",
                "options": [
                    "A. đồng bằng chiếm phần lớn diện tích.",
                    "B. đồi núi chiếm 3/4 diện tích lãnh thổ.",
                    "C. chỉ có dạng địa hình núi cao hiểm trở.",
                    "D. địa hình bằng phẳng không có bậc."
                ],
                "correct_answer": "B. đồi núi chiếm 3/4 diện tích lãnh thổ."
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Gió mùa Đông Bắc hoạt động mạnh mẽ nhất ở miền khí hậu nào của nước ta?",
                "options": ["A. Miền Bắc", "B. Miền Nam", "C. Tây Nguyên", "D. Duyên hải Nam Trung Bộ"],
                "correct_answer": "A. Miền Bắc"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Nhóm đất chiếm diện tích lớn nhất ở vùng đồi núi nước ta là",
                "options": ["A. đất feralit.", "B. đất phù sa.", "C. đất xám bạc màu.", "D. đất cát ven biển."],
                "correct_answer": "A. đất feralit."
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Sông ngòi nước ta có đặc điểm nổi bật là",
                "options": [
                    "A. mạng lưới sông ngòi thưa thớt, ít nước.",
                    "B. mạng lưới sông ngòi dày đặc, nhiều nước, giàu phù sa.",
                    "C. sông có độ dốc thấp, không có tiềm năng thủy điện.",
                    "D. dòng chảy không phụ thuộc vào chế độ mưa."
                ],
                "correct_answer": "B. mạng lưới sông ngòi dày đặc, nhiều nước, giàu phù sa."
            }
        ]
    },
    {
        "file_id": "docx_diali_02_loi_giai",
        "file_name": "diali_02_loi_giai.docx",
        "format_type": "docx",
        "subject": "Địa lý",
        "style": "underline",
        "style_description": "Địa lý kinh tế các vùng, đáp án gạch chân kèm khối 'Lời giải chi tiết:'",
        "tags": ["dia_ly", "underline", "explain_block", "kinh_te_vung"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Thế mạnh nổi bật nhất của vùng Tây Nguyên trong nông nghiệp là",
                "options": [
                    "A. trồng cây lương thực lúa nước.",
                    "B. trồng cây công nghiệp lâu năm.",
                    "C. nuôi trồng thủy sản nước ngọt.",
                    "D. phát triển chăn nuôi lợn lấy thịt."
                ],
                "correct_answer": "B. trồng cây công nghiệp lâu năm.",
                "explain": "Tây Nguyên có diện tích đất đỏ bazan rộng lớn, khí hậu cận xích đạo phân hóa mưa nắng thuận lợi cho cây công nghiệp lâu năm như cà phê, cao su, hồ tiêu."
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Vùng Đồng bằng sông Cửu Long là vùng sản xuất lương thực lớn nhất nước ta nhờ có",
                "options": [
                    "A. diện tích đất phù sa rộng lớn và nguồn nước dồi dào.",
                    "B. mật độ dân số thấp nhất cả nước.",
                    "C. khí hậu có mùa đông lạnh.",
                    "D. cơ giới hóa cao nhất thế giới."
                ],
                "correct_answer": "A. diện tích đất phù sa rộng lớn và nguồn nước dồi dào.",
                "explain": "Đồng bằng sông Cửu Long có diện tích đất phù sa ngọt rộng lớn của sông Tiền và sông Hậu bồi đắp, khí hậu ấm áp quanh năm."
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Vùng kinh tế dẫn đầu cả nước về quy mô GDP và giá trị sản xuất công nghiệp là",
                "options": ["A. Vùng Đông Nam Bộ", "B. Vùng Trung du miền núi Bắc Bộ", "C. Vùng Bắc Trung Bộ", "D. Vùng Tây Nguyên"],
                "correct_answer": "A. Vùng Đông Nam Bộ",
                "explain": "Đông Nam Bộ chiếm tỷ trọng cao nhất về GDP công nghiệp, thu hút nhiều vốn đầu tư trực tiếp nước ngoài (FDI)."
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Than đá của nước ta tập trung trữ lượng lớn nhất tại tỉnh nào?",
                "options": ["A. Quảng Ninh", "B. Thái Nguyên", "C. Lạng Sơn", "D. Cao Bằng"],
                "correct_answer": "A. Quảng Ninh",
                "explain": "Bể than Quảng Ninh là vùng mỏ than antraxit lớn nhất và chất lượng tốt nhất nước ta."
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Khó khăn lớn nhất về mặt tự nhiên đối với sản xuất nông nghiệp ở vùng Duyên hải Nam Trung Bộ là",
                "options": [
                    "A. hạn hán kéo dài và bão lũ thất thường.",
                    "B. sương muối và rét đậm kéo dài.",
                    "C. thiếu ánh sáng mặt trời quanh năm.",
                    "D. diện tích ngập mặn bao phủ toàn vùng."
                ],
                "correct_answer": "A. hạn hán kéo dài và bão lũ thất thường.",
                "explain": "Duyên hải Nam Trung Bộ có mùa khô kéo dài, hiện tượng sa mạc hóa cục bộ và thường xuyên chịu ảnh hưởng của bão đổ bộ vào cuối năm."
            }
        ]
    },
    {
        "file_id": "docx_diali_03_gdpt2018",
        "file_name": "diali_03_gdpt2018.docx",
        "format_type": "docx",
        "subject": "Địa lý",
        "style": "gdpt_2018",
        "style_description": "Địa lý chuẩn GDPT 2018: Phần I MCQ, Phần II Đúng/Sai, Phần III Trả lời ngắn số liệu",
        "tags": ["dia_ly", "gdpt_2018", "dan_cu_do_thi"],
        "questions": [
            {
                "question_number": 1,
                "part": 1,
                "type": "mcq",
                "question": "Quá trình đô thị hóa ở nước ta hiện nay đang có chuyển biến tích cực thể hiện ở",
                "options": [
                    "A. tỉ lệ dân thành thị ngày càng tăng.",
                    "B. đô thị hóa diễn ra hoàn toàn tự phát.",
                    "C. không có sự phân hóa giữa các vùng.",
                    "D. giảm mạnh số lượng các đô thị."
                ],
                "correct_answer": "A. tỉ lệ dân thành thị ngày càng tăng."
            },
            {
                "question_number": 2,
                "part": 1,
                "type": "mcq",
                "question": "Ngành du lịch biển nước ta phát triển nhanh chóng nhờ vào lợi thế nào?",
                "options": [
                    "A. Nhiều bãi biển đẹp, khí hậu nắng ấm và nhiều đảo ven bờ",
                    "B. Không có bão lũ thiên tai",
                    "C. Mức sống dân cư cao nhất thế giới",
                    "D. Rừng rậm rạp bao bọc ven biển"
                ],
                "correct_answer": "A. Nhiều bãi biển đẹp, khí hậu nắng ấm và nhiều đảo ven bờ"
            },
            {
                "question_number": 1,
                "part": 2,
                "type": "true_false",
                "question": "Cho bảng số liệu về dân số và diện tích của nước ta qua các năm. Xét các nhận định:",
                "options": [
                    "a) Mật độ dân số trung bình của nước ta thuộc nhóm cao trên thế giới",
                    "b) Dân cư nước ta phân bố đồng đều giữa đồng bằng và miền núi",
                    "c) Đồng bằng sông Hồng có mật độ dân số cao nhất cả nước",
                    "d) Chuyển dịch cơ cấu lao động theo ngành đang diễn ra theo hướng giảm tỷ trọng nông - lâm - thủy sản"
                ],
                "correct_answer": {"a": True, "b": False, "c": True, "d": True}
            },
            {
                "question_number": 2,
                "part": 2,
                "type": "true_false",
                "question": "Về vấn đề khai thác thế mạnh kinh tế biển ở nước ta:",
                "options": [
                    "a) Nước ta có vùng biển rộng lớn với diện tích khoảng 1 triệu km2 trên Biển Đông",
                    "b) Ngành khai thác dầu khí tập trung chủ yếu ở thềm lục địa phía Bắc",
                    "c) Việc xây dựng các cảng biển nước sâu gắn liền với các khu kinh tế ven biển",
                    "d) Khai thác hải sản xa bờ giúp vừa nâng cao hiệu quả kinh tế vừa bảo vệ chủ quyền biển đảo"
                ],
                "correct_answer": {"a": True, "b": False, "c": True, "d": True}
            },
            {
                "question_number": 1,
                "part": 3,
                "type": "short_answer",
                "question": "Năm 2023, dân số nước ta đạt 100,3 triệu người, diện tích tự nhiên là 331.212 km2. Tính mật độ dân số nước ta năm 2023 (người/km2, làm tròn số nguyên).",
                "options": [],
                "correct_answer": "303"
            },
            {
                "question_number": 2,
                "part": 3,
                "type": "short_answer",
                "question": "Một tỉnh có diện tích 5000 km2, sản lượng lúa đạt 2,5 triệu tấn. Năng suất lúa trung bình trên 1 ha gieo trồng (biết diện tích gieo trồng lúa là 400.000 ha) là bao nhiêu tạ/ha? (1 tấn = 10 tạ).",
                "options": [],
                "correct_answer": "62.5"
            }
        ]
    },
    {
        "file_id": "pdf_diali_01_kiem_tra",
        "file_name": "diali_01_kiem_tra.pdf",
        "format_type": "pdf",
        "subject": "Địa lý",
        "style": "bottom_text",
        "style_description": "PDF kiểm tra Địa lý Khí hậu & Sông ngòi có bảng đáp án text cuối đề",
        "tags": ["dia_ly", "pdf", "khi_hau"],
        "answer_text_block": "1.B   2.C   3.A   4.D   5.B",
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Tính chất nhiệt đới ẩm gió mùa của khí hậu nước ta được quy định bởi",
                "options": [
                    "A. địa hình đồi núi chiếm ưu thế.",
                    "B. vị trí địa lý trong vùng nội chí tuyến và tác động của các khối khí gió mùa.",
                    "C. diện tích đất liền hẹp ngang kéo dài.",
                    "D. sự phát triển của hệ thống rừng nhiệt đới ẩm."
                ],
                "correct_answer": "B. vị trí địa lý trong vùng nội chí tuyến và tác động của các khối khí gió mùa."
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Hằng năm, nước ta nhận được lượng bức xạ mặt trời lớn do",
                "options": [
                    "A. có nhiều núi cao.",
                    "B. nằm gần đường xích đạo và góc nhập xạ lớn quanh năm.",
                    "C. góc nhập xạ lớn và hai lần mặt trời lên thiên đỉnh trong năm.",
                    "D. chịu ảnh hưởng của bão biển."
                ],
                "correct_answer": "C. góc nhập xạ lớn và hai lần mặt trời lên thiên đỉnh trong năm."
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Hệ thống sông có mạng lưới phân lưu dạng nan quạt ở miền Bắc nước ta là",
                "options": ["A. Sông Hồng", "B. Sông Thái Bình", "C. Sông Mã", "D. Sông Cả"],
                "correct_answer": "A. Sông Hồng"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Vùng có mùa mưa lệch hẳn về thu - đông ở nước ta là",
                "options": ["A. Bắc Bộ", "B. Nam Bộ", "C. Tây Nguyên", "D. Duyên hải miền Trung"],
                "correct_answer": "D. Duyên hải miền Trung"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Đai cao cận nhiệt đới gió mùa trên núi ở nước ta xuất hiện từ độ cao nào ở miền Bắc?",
                "options": ["A. Từ 300 - 400 m", "B. Từ 600 - 700 m", "C. Từ 900 - 1000 m", "D. Từ 2600 m trở lên"],
                "correct_answer": "B. Từ 600 - 700 m"
            }
        ]
    },

    # =========================================================================
    # 8. GIÁO DỤC KINH TẾ & PHÁP LUẬT / GDCD (3 files: 2 DOCX + 1 PDF)
    # =========================================================================
    {
        "file_id": "docx_gdcd_01_tinh_huong_phap_luat",
        "file_name": "gdcd_01_tinh_huong_phap_luat.docx",
        "format_type": "docx",
        "subject": "Giáo dục Kinh tế và Pháp luật",
        "style": "underline",
        "style_description": "Câu hỏi tình huống pháp luật dài nhiều dòng, có các nhân vật Ông A Bà B, đáp án gạch chân",
        "tags": ["gdcd", "ktpl", "tinh_huong_dai", "underline"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Anh A và chị B cùng nộp hồ sơ xin việc vào công ty X. Dù có trình độ chuyên môn cao hơn nhưng chị B bị giám đốc loại chỉ vì là phụ nữ. Giám đốc công ty X đã vi phạm quyền bình đẳng nào dưới đây của công dân?",
                "options": [
                    "A. Bình đẳng trong kinh doanh.",
                    "B. Bình đẳng trong lao động.",
                    "C. Bình đẳng về quyền sở hữu tài sản.",
                    "D. Bình đẳng trong việc kết hôn."
                ],
                "correct_answer": "B. Bình đẳng trong lao động."
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Ông H là chủ nhà hàng xả nước thải chưa qua xử lý ra dòng suối gần khu dân cư gây ô nhiễm môi trường nghiêm trọng. Khi bị cán bộ môi trường lập biên bản, ông H đã dùng tiền hối lộ để bỏ qua vi phạm. Hành vi của ông H thuộc hình thức vi phạm pháp luật nào sau đây?",
                "options": [
                    "A. Vi phạm kỷ luật và vi phạm dân sự.",
                    "B. Vi phạm hành chính và vi phạm hình sự.",
                    "C. Chỉ vi phạm dân sự.",
                    "D. Không vi phạm pháp luật."
                ],
                "correct_answer": "B. Vi phạm hành chính và vi phạm hình sự."
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Anh C phát hiện đại lý phân phối thuốc tân dược của bà M bán thuốc hết hạn sử dụng nên đã gửi đơn tố cáo tới cơ quan quản lý thị trường. Anh C đã thực hiện quyền nào dưới đây của công dân?",
                "options": ["A. Quyền khiếu nại", "B. Quyền tố cáo", "C. Quyền tự do kinh doanh", "D. Quyền ứng cử"],
                "correct_answer": "B. Quyền tố cáo"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Trong cuộc bầu cử đại biểu Quốc hội, bà T vì bận việc riêng đã nhờ con trai mình là anh V bỏ phiếu hộ cho mình. Hành vi này của bà T đã vi phạm nguyên tắc bầu cử nào?",
                "options": ["A. Nguyên tắc phổ thông", "B. Nguyên tắc bình đẳng", "C. Nguyên tắc trực tiếp", "D. Nguyên tắc bỏ phiếu kín"],
                "correct_answer": "C. Nguyên tắc trực tiếp"
            }
        ]
    },
    {
        "file_id": "docx_gdcd_02_gdpt2018_dung_sai",
        "file_name": "gdcd_02_gdpt2018_dung_sai.docx",
        "format_type": "docx",
        "subject": "Giáo dục Kinh tế và Pháp luật",
        "style": "gdpt_2018",
        "style_description": "KT&PL chuẩn GDPT 2018: Phần I MCQ 3 câu, Phần II Đúng/Sai 2 câu đánh giá hành vi pháp luật",
        "tags": ["gdcd", "ktpl", "gdpt_2018", "true_false"],
        "questions": [
            {
                "question_number": 1,
                "part": 1,
                "type": "mcq",
                "question": "Quy luật kinh tế nào dưới đây điều tiết sản xuất và lưu thông hàng hóa thông qua sự biến động của giá cả thị trường?",
                "options": ["A. Quy luật giá trị", "B. Quy luật cạnh tranh", "C. Quy luật cung - cầu", "D. Quy luật lưu thông tiền tệ"],
                "correct_answer": "C. Quy luật cung - cầu"
            },
            {
                "question_number": 2,
                "part": 1,
                "type": "mcq",
                "question": "Hệ thống các quy tắc xử sự chung do Nhà nước ban hành và được bảo đảm thực hiện bằng quyền lực Nhà nước là",
                "options": ["A. đạo đức xã hội.", "B. pháp luật.", "C. phong tục tập quán.", "D. điều lệ tổ chức."],
                "correct_answer": "B. pháp luật."
            },
            {
                "question_number": 3,
                "part": 1,
                "type": "mcq",
                "question": "Công dân từ đủ bao nhiêu tuổi trở lên có quyền bầu cử đại biểu Quốc hội và Hội đồng nhân dân các cấp?",
                "options": ["A. Đủ 16 tuổi", "B. Đủ 18 tuổi", "C. Đủ 20 tuổi", "D. Đủ 21 tuổi"],
                "correct_answer": "B. Đủ 18 tuổi"
            },
            {
                "question_number": 1,
                "part": 2,
                "type": "true_false",
                "question": "Về quyền tự do kinh doanh và nghĩa vụ đóng thuế của công dân:",
                "options": [
                    "a) Công dân có quyền kinh doanh bất kì ngành nghề nào mà pháp luật không cấm",
                    "b) Người kinh doanh có nghĩa vụ nộp thuế đầy đủ và đúng thời hạn theo quy định của Luật Thuế",
                    "c) Doanh nghiệp được phép tự do sản xuất hàng giả, hàng nhái nếu đem lại lợi nhuận cao",
                    "d) Nhà nước khuyến khích các hoạt động kinh doanh bảo vệ môi trường và tạo việc làm cho xã hội"
                ],
                "correct_answer": {"a": True, "b": True, "c": False, "d": True}
            },
            {
                "question_number": 2,
                "part": 2,
                "type": "true_false",
                "question": "Về quyền bất khả xâm phạm về thân thể và quyền được pháp luật bảo hộ về tính mạng, sức khỏe, danh dự, nhân phẩm:",
                "options": [
                    "a) Không ai bị bắt nếu không có quyết định của Tòa án hoặc phê chuẩn của Viện kiểm sát, trừ trường hợp phạm tội quả tang",
                    "b) Mọi hành vi tự ý vào chỗ ở của người khác khi chưa được cho phép đều là vi phạm pháp luật",
                    "c) Bạn bè thân thiết có quyền tùy tiện bêu riếu hình ảnh xúc phạm danh dự người khác trên mạng xã hội",
                    "d) Công dân có quyền tự vệ chính đáng khi tính mạng của mình bị đe dọa trái pháp luật"
                ],
                "correct_answer": {"a": True, "b": True, "c": False, "d": True}
            }
        ]
    },
    {
        "file_id": "pdf_gdcd_01_de_thi",
        "file_name": "gdcd_01_de_thi.pdf",
        "format_type": "pdf",
        "subject": "Giáo dục Kinh tế và Pháp luật",
        "style": "bottom_text",
        "style_description": "PDF đề thi KT&PL Pháp luật và đời sống, bảng đáp án text cuối đề",
        "tags": ["gdcd", "ktpl", "pdf"],
        "answer_text_block": "1-A   2-C   3-B   4-D   5-A",
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Hình thức thực hiện pháp luật nào trong đó cá nhân, tổ chức chủ động làm những gì mà pháp luật quy định phải làm?",
                "options": ["A. Thi hành pháp luật", "B. Sử dụng pháp luật", "C. Tuân thủ pháp luật", "D. Áp dụng pháp luật"],
                "correct_answer": "A. Thi hành pháp luật"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Người điều khiển xe mô tô không đội mũ bảo hiểm khi tham gia giao thông là hành vi",
                "options": ["A. không sử dụng pháp luật.", "B. không áp dụng pháp luật.", "C. không tuân thủ pháp luật.", "D. không thi hành pháp luật."],
                "correct_answer": "C. không tuân thủ pháp luật."
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Năng lực của chủ thể thực hiện hành vi vi phạm pháp luật và phải chịu trách nhiệm pháp lý phụ thuộc vào",
                "options": ["A. hoàn cảnh gia đình.", "B. độ tuổi và khả năng nhận thức, điều khiển hành vi.", "C. chức vụ trong xã hội.", "D. mức thu nhập cá nhân."],
                "correct_answer": "B. độ tuổi và khả năng nhận thức, điều khiển hành vi."
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Bất kì công dân nào vi phạm pháp luật đều phải bị xử lý theo quy định của pháp luật thể hiện công dân bình đẳng về",
                "options": ["A. quyền lợi.", "B. nghĩa vụ.", "C. nhu cầu.", "D. trách nhiệm pháp lý."],
                "correct_answer": "D. trách nhiệm pháp lý."
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Mọi hành vi xâm phạm đến tính mạng, sức khỏe, danh dự của người khác đều bị xử lý nghiêm minh theo",
                "options": ["A. pháp luật hình sự hoặc hành chính.", "B. quy tắc tôn giáo.", "C. lệ làng.", "D. dư luận xã hội."],
                "correct_answer": "A. pháp luật hình sự hoặc hành chính."
            }
        ]
    },

    # =========================================================================
    # 9. TIN HỌC (3 files: 2 DOCX + 1 PDF)
    # =========================================================================
    {
        "file_id": "docx_tinhoc_01_code_python",
        "file_name": "tinhoc_01_code_python.docx",
        "format_type": "docx",
        "subject": "Tin học",
        "style": "underline",
        "style_description": "Tin học Lập trình Python, câu hỏi có chứa đoạn mã code, đáp án đúng gạch chân",
        "tags": ["tin_hoc", "code_snippet", "python", "underline"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Cho đoạn mã Python sau:\nx = 10\ny = 3\nprint(x % y)\nKết quả in ra màn hình là gì?",
                "options": ["A. 3", "B. 1", "C. 0", "D. 3.33"],
                "correct_answer": "B. 1"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Trong Python, câu lệnh nào sau đây dùng để duyệt qua các số nguyên từ 0 đến 4?",
                "options": ["A. for i in range(5):", "B. for i in range(0, 4):", "C. loop i to 5:", "D. while i < 4:"],
                "correct_answer": "A. for i in range(5):"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Cho danh sách a = [10, 20, 30, 40]. Giá trị của a[2] là bao nhiêu?",
                "options": ["A. 10", "B. 20", "C. 30", "D. 40"],
                "correct_answer": "C. 30"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Hàm nào trong Python được sử dụng để lấy độ dài của một chuỗi hoặc danh sách?",
                "options": ["A. size()", "B. length()", "C. count()", "D. len()"],
                "correct_answer": "D. len()"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Biểu thức điều kiện trong Python:\nx = 5\nif x > 3 and x < 10:\n    print('True')\nelse:\n    print('False')\nMàn hình hiển thị kết quả nào?",
                "options": ["A. True", "B. False", "C. None", "D. Error"],
                "correct_answer": "A. True"
            }
        ]
    },
    {
        "file_id": "docx_tinhoc_02_gdpt2018",
        "file_name": "tinhoc_02_gdpt2018.docx",
        "format_type": "docx",
        "subject": "Tin học",
        "style": "gdpt_2018",
        "style_description": "Tin học chuẩn GDPT 2018: Hệ CSDL, Mạng máy tính, Phần III tính giá trị thuật toán",
        "tags": ["tin_hoc", "gdpt_2018", "csdl_sql"],
        "questions": [
            {
                "question_number": 1,
                "part": 1,
                "type": "mcq",
                "question": "Khóa chính (Primary Key) trong một bảng cơ sở dữ liệu quan hệ có đặc điểm quan trọng nhất là",
                "options": [
                    "A. giá trị không được trùng lặp và không được rỗng (NULL).",
                    "B. bắt buộc phải là kiểu dữ liệu số nguyên.",
                    "C. có thể chứa nhiều giá trị giống nhau.",
                    "D. chỉ được đặt tên là ID."
                ],
                "correct_answer": "A. giá trị không được trùng lặp và không được rỗng (NULL)."
            },
            {
                "question_number": 2,
                "part": 1,
                "type": "mcq",
                "question": "Giao thức truyền tải siêu văn bản an toàn được sử dụng trên các trang web có mã hóa SSL/TLS là",
                "options": ["A. HTTP", "B. FTP", "C. HTTPS", "D. SMTP"],
                "correct_answer": "C. HTTPS"
            },
            {
                "question_number": 1,
                "part": 2,
                "type": "true_false",
                "question": "Về an toàn thông tin và bảo mật trên không gian mạng:",
                "options": [
                    "a) Mật khẩu mạnh nên bao gồm chữ hoa, chữ thường, chữ số và ký tự đặc biệt",
                    "b) Xác thực 2 yếu tố (2FA) giúp tăng cường bảo mật cho tài khoản cá nhân",
                    "c) Nhấp vào các liên kết lạ trong email không rõ nguồn gốc là hoàn toàn an toàn",
                    "d) Phần mềm diệt virus có thể giúp ngăn ngừa mã độc hại xâm nhập vào máy tính"
                ],
                "correct_answer": {"a": True, "b": True, "c": False, "d": True}
            },
            {
                "question_number": 2,
                "part": 2,
                "type": "true_false",
                "question": "Về ngôn ngữ truy vấn cơ sở dữ liệu SQL:",
                "options": [
                    "a) Câu lệnh SELECT dùng để truy vấn và trích xuất dữ liệu từ các bảng",
                    "b) Mệnh đề WHERE được dùng để lọc các bản ghi thỏa mãn điều kiện nhất định",
                    "c) Câu lệnh DELETE dùng để tạo mới một bảng cơ sở dữ liệu",
                    "d) Mệnh đề ORDER BY dùng để sắp xếp kết quả trả về theo thứ tự tăng hoặc giảm dần"
                ],
                "correct_answer": {"a": True, "b": True, "c": False, "d": True}
            },
            {
                "question_number": 1,
                "part": 3,
                "type": "short_answer",
                "question": "Cho thuật toán tính tổng: S = 0; for i in range(1, 6): S += i. Giá trị cuối cùng của biến S là bao nhiêu?",
                "options": [],
                "correct_answer": "15"
            },
            {
                "question_number": 2,
                "part": 3,
                "type": "short_answer",
                "question": "Một tệp hình ảnh có kích thước 2 MB. Đổi dung lượng tệp đó ra đơn vị Kilobyte (KB). (Quy ước: 1 MB = 1024 KB).",
                "options": [],
                "correct_answer": "2048"
            }
        ]
    },
    {
        "file_id": "pdf_tinhoc_01_kiem_tra",
        "file_name": "tinhoc_01_kiem_tra.pdf",
        "format_type": "pdf",
        "subject": "Tin học",
        "style": "bottom_text",
        "style_description": "PDF kiểm tra Tin học Cấu trúc dữ liệu & Thuật toán, có bảng đáp án text cuối đề",
        "tags": ["tin_hoc", "pdf", "thuat_toan"],
        "answer_text_block": "1-C   2-B   3-A   4-D   5-B",
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "question": "Thuật toán tìm kiếm nhị phân (Binary Search) chỉ áp dụng được trên danh sách nào?",
                "options": [
                    "A. Danh sách bất kì chưa được sắp xếp",
                    "B. Danh sách có số phần tử là số chẵn",
                    "C. Danh sách đã được sắp xếp theo thứ tự",
                    "D. Danh sách chứa toàn số nguyên dương"
                ],
                "correct_answer": "C. Danh sách đã được sắp xếp theo thứ tự"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "question": "Độ phức tạp thời gian trung bình của thuật toán sắp xếp nhanh (Quick Sort) là",
                "options": ["A. O(n)", "B. O(n log n)", "C. O(n^2)", "D. O(log n)"],
                "correct_answer": "B. O(n log n)"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "question": "Cấu trúc dữ liệu hàng đợi (Queue) hoạt động theo nguyên tắc nào sau đây?",
                "options": ["A. FIFO (Vào trước ra trước)", "B. LIFO (Vào sau ra trước)", "C. Ngẫu nhiên", "D. Ưu tiên số lớn hơn"],
                "correct_answer": "A. FIFO (Vào trước ra trước)"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "question": "Trong hệ nhị phân, số thập phân 13 được biểu diễn tương ứng là",
                "options": ["A. 1010", "B. 1100", "C. 1110", "D. 1101"],
                "correct_answer": "D. 1101"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "question": "Một byte trong kiến trúc máy tính bao gồm bao nhiêu bit?",
                "options": ["A. 4 bit", "B. 8 bit", "C. 16 bit", "D. 32 bit"],
                "correct_answer": "B. 8 bit"
            }
        ]
    },

    # =========================================================================
    # 10. NGỮ VĂN & ĐỊNH DẠNG ĐẶC BIỆT (3 files: 3 DOCX)
    # =========================================================================
    {
        "file_id": "docx_nguvan_01_doc_hieu",
        "file_name": "nguvan_01_doc_hieu.docx",
        "format_type": "docx",
        "subject": "Ngữ văn",
        "style": "underline",
        "style_description": "Ngữ văn Đọc hiểu ngữ liệu trích dẫn thơ/văn xuôi (group_title chung), 4 câu hỏi trắc nghiệm dưới bài, đáp án gạch chân",
        "tags": ["ngu_van", "doc_hieu", "group_title", "underline"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "group_title": "Đọc đoạn trích sau và trả lời các câu hỏi:\n\n'Sống trong đời sống cần có một tấm lòng\nĐể làm gì em biết không?\nĐể gió cuốn đi, để gió cuốn đi...'\n(Trích 'Để gió cuốn đi' - Trịnh Công Sơn)",
                "question": "Phương thức biểu đạt chính được sử dụng trong đoạn trích trên là gì?",
                "options": ["A. Tự sự", "B. Biểu cảm", "C. Thuyết minh", "D. Nghị luận"],
                "correct_answer": "B. Biểu cảm"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "group_title": "Đọc đoạn trích sau và trả lời các câu hỏi:\n\n'Sống trong đời sống cần có một tấm lòng\nĐể làm gì em biết không?\nĐể gió cuốn đi, để gió cuốn đi...'\n(Trích 'Để gió cuốn đi' - Trịnh Công Sơn)",
                "question": "Biện pháp tu từ cú pháp nổi bật trong câu 'Để gió cuốn đi, để gió cuốn đi...' là",
                "options": ["A. Điệp ngữ", "B. Nhân hóa", "C. Hoán dụ", "D. So sánh"],
                "correct_answer": "A. Điệp ngữ"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "group_title": "Đọc đoạn trích sau và trả lời các câu hỏi:\n\n'Sống trong đời sống cần có một tấm lòng\nĐể làm gì em biết không?\nĐể gió cuốn đi, để gió cuốn đi...'\n(Trích 'Để gió cuốn đi' - Trịnh Công Sơn)",
                "question": "Hình ảnh 'tấm lòng' trong đoạn trích mang ý nghĩa biểu tượng cho điều gì?",
                "options": [
                    "A. Lòng nhân ái, sự bao dung và tình yêu thương con người",
                    "B. Sự toan tính vụ lợi cá nhân",
                    "C. Nỗi buồn bi quan tuyệt vọng",
                    "D. Sức mạnh thể chất"
                ],
                "correct_answer": "A. Lòng nhân ái, sự bao dung và tình yêu thương con người"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "group_title": "Đọc đoạn trích sau và trả lời các câu hỏi:\n\n'Sống trong đời sống cần có một tấm lòng\nĐể làm gì em biết không?\nĐể gió cuốn đi, để gió cuốn đi...'\n(Trích 'Để gió cuốn đi' - Trịnh Công Sơn)",
                "question": "Thông điệp ý nghĩa sâu sắc nhất mà tác giả muốn gửi gắm qua lời ca là gì?",
                "options": [
                    "A. Hãy sống cống hiến yêu thương mà không đòi hỏi đền đáp",
                    "B. Cuộc đời là vô nghĩa như gió cuốn",
                    "C. Nên giữ kín tình cảm của mình",
                    "D. Hãy tìm nơi thanh thản tránh xa xã hội"
                ],
                "correct_answer": "A. Hãy sống cống hiến yêu thương mà không đòi hỏi đền đáp"
            }
        ]
    },
    {
        "file_id": "docx_format_edge_case_numbering",
        "file_name": "format_edge_case_numbering.docx",
        "format_type": "docx",
        "subject": "Định dạng đặc biệt",
        "style": "underline",
        "style_description": "Tiền tố câu hỏi không chuẩn: '1.', '2/', 'Bài 3:', 'Question 4.', 'Q5:', đáp án gạch chân",
        "tags": ["edge_case", "numbering", "irregular_prefix", "underline"],
        "questions": [
            {
                "question_number": 1,
                "prefix": "1. ",
                "type": "mcq",
                "question": "Số nguyên tố chẵn duy nhất trong tập hợp số nguyên tố là",
                "options": ["A. 0", "B. 2", "C. 4", "D. 6"],
                "correct_answer": "B. 2"
            },
            {
                "question_number": 2,
                "prefix": "2/ ",
                "type": "mcq",
                "question": "Thủ đô của nước Cộng hòa Xã hội Chủ nghĩa Việt Nam là thành phố nào?",
                "options": ["A. TP. Hồ Chí Minh", "B. Đà Nẵng", "C. Hà Nội", "D. Hải Phòng"],
                "correct_answer": "C. Hà Nội"
            },
            {
                "question_number": 3,
                "prefix": "Bài 3: ",
                "type": "mcq",
                "question": "Nguyên tố hóa học nào phổ biến nhất trong vỏ Trái Đất?",
                "options": ["A. Oxi (O)", "B. Silic (Si)", "C. Nhôm (Al)", "D. Sắt (Fe)"],
                "correct_answer": "A. Oxi (O)"
            },
            {
                "question_number": 4,
                "prefix": "Question 4. ",
                "type": "mcq",
                "question": "Which planet in our solar system is known as the Red Planet?",
                "options": ["A. Venus", "B. Mars", "C. Jupiter", "D. Saturn"],
                "correct_answer": "B. Mars"
            },
            {
                "question_number": 5,
                "prefix": "Q5: ",
                "type": "mcq",
                "question": "Đơn vị đo cường độ dòng điện trong hệ SI là gì?",
                "options": ["A. Vôn (V)", "B. Ampe (A)", "C. Ôm (Ω)", "D. Oát (W)"],
                "correct_answer": "B. Ampe (A)"
            }
        ]
    },
    {
        "file_id": "docx_format_edge_case_no_space_options",
        "file_name": "format_edge_case_no_space_options.docx",
        "format_type": "docx",
        "subject": "Định dạng đặc biệt",
        "style": "bottom_table",
        "style_description": "Các phương án ngắn phân tách không có dòng mới, có Bảng đáp án Table ở cuối trang",
        "tags": ["edge_case", "bottom_table", "short_options"],
        "questions": [
            {
                "question_number": 1,
                "type": "mcq",
                "layout": "single_line",
                "question": "Năm 2024 là năm nhuận có bao nhiêu ngày?",
                "options": ["A. 365", "B. 366", "C. 364", "D. 360"],
                "correct_answer": "B. 366"
            },
            {
                "question_number": 2,
                "type": "mcq",
                "layout": "single_line",
                "question": "Hình tam giác đều có số trục đối xứng là",
                "options": ["A. 1", "B. 2", "C. 3", "D. 0"],
                "correct_answer": "C. 3"
            },
            {
                "question_number": 3,
                "type": "mcq",
                "layout": "single_line",
                "question": "Một giờ bằng bao nhiêu giây?",
                "options": ["A. 3600", "B. 60", "C. 1200", "D. 2400"],
                "correct_answer": "A. 3600"
            },
            {
                "question_number": 4,
                "type": "mcq",
                "layout": "single_line",
                "question": "Trong bảng tuần hoàn, chu kỳ 1 gồm bao nhiêu nguyên tố?",
                "options": ["A. 8", "B. 2", "C. 18", "D. 32"],
                "correct_answer": "B. 2"
            },
            {
                "question_number": 5,
                "type": "mcq",
                "layout": "single_line",
                "question": "Âm thanh không truyền được trong môi trường nào?",
                "options": ["A. Chân không", "B. Không khí", "C. Nước", "D. Thép"],
                "correct_answer": "A. Chân không"
            }
        ]
    }
]
