# Báo Cáo Đánh Giá RAGAS & Tổng Hợp Minh Chứng — Lab Day 22

**Project LangSmith:** day22-lab  
**Mô hình LLM:** deepseek-chat (DeepSeek V3 qua https://api.deepseek.com)  
**Embeddings:** 	ext-embedding-3-small (1536 chiều)  

---

## 1. Bảng Tổng Hợp Kết Quả RAGAS (50 QA Pairs)

Trích xuất trực tiếp từ file báo cáo định lượng vidence/03_ragas_report.json:

| Chỉ số (Metric) | Prompt V1 (Ngắn gọn / Concise) | Prompt V2 (Chuyên gia / Detailed) | Winner | Tiêu chuẩn Đạt |
| :--- | :---: | :---: | :---: | :---: |
| **Faithfulness** | **0.9773 (97.73%)** ⭐ | **0.9524 (95.24%)** ⭐ | **← V1** | $\ge 0.80$ (Cả 2 đều $\ge 0.90$) |
| **Answer Relevancy** | **0.9228 (92.28%)** | **0.9090 (90.90%)** | **← V1** | — |
| **Context Recall** | **1.0000 (100.0%)** | **1.0000 (100.0%)** | **Hòa (Tied)** | — |
| **Context Precision** | **0.9483 (94.83%)** | **0.9483 (94.83%)** | **Hòa (Tied)** | — |

* **Đạt mục tiêu Lab:** Faithfulness cao nhất đạt **0.9773** ($\ge 0.80$).
* **Điểm thưởng (+3đ):** Cả 2 phiên bản Prompt V1 (0.9773) và V2 (0.9524) đều đạt **Faithfulness $\ge 0.90$**.

---

## 2. Phân Tích & So Sánh Chuyên Sâu (Bonus +2đ)

### 2.1. Tại sao Prompt V1 đạt Faithfulness (0.9773) cao hơn V2 (0.9524)?
* **Đặc tính của Prompt V1:** Prompt V1 chỉ định LLM trả lời ngắn gọn, cô đọng (2-4 câu), chỉ sử dụng đúng các dữ kiện được cung cấp trực tiếp trong context truy xuất mà không suy diễn ngoài lề. Khi số lượng câu sinh ra ít và bám sát từng từ trong context, tỷ lệ các mệnh đề (statements) được hỗ trợ hoàn toàn bởi context đạt mức tối đa (97.73%).
* **Đặc tính của Prompt V2:** Prompt V2 yêu cầu giải thích chi tiết, có cấu trúc logic (3-5 câu). Do câu trả lời dài và phân tích chuyên sâu hơn, LLM có xu hướng đưa thêm các từ nối logic hoặc diễn giải kiến thức bổ trợ, khiến một số mệnh đề nhỏ không thể đối chiếu 1-1 trực tiếp trong đoạn context ngắn, làm chỉ số faithfulness giảm nhẹ (vẫn rất cao ở mức 95.24%).

### 2.2. Về Answer Relevancy (V1: 0.9228 vs V2: 0.9090)
* Prompt V1 trả lời trực diện vào trọng tâm câu hỏi của người dùng, không thêm thông tin râu ria, giúp câu hỏi sinh ngược lại (reverse question generation) từ câu trả lời khớp rất cao với câu hỏi gốc.
* Prompt V2 mở rộng thêm phần giải thích chi tiết và phân loại, dẫn đến phân bố vector câu trả lời rộng hơn một chút.

### 2.3. Về Context Recall (1.0000) và Context Precision (0.9483)
* Cả hai phiên bản đều dùng chung hệ thống truy xuất FAISS VectorStore (=3$) và tập ngữ liệu chuẩn nên Context Recall đạt tuyệt đối 100% và Context Precision đạt mức xuất sắc 94.83%.

---

## 3. Danh Mục Các Minh Chứng (Evidence Files)

1. vidence/01_langsmith_traces.png: Ảnh chụp giao diện LangSmith với $\ge 50$ traces hợp lệ.
2. vidence/02_prompt_hub.png: Ảnh chụp giao diện LangSmith Prompt Hub chứa 2 prompts day22-rag-prompt-v1 và day22-rag-prompt-v2.
3. vidence/02_ab_routing_log.txt: Log console phân luồng tất định 50 truy vấn qua Prompt Hub (V1: 19 câu, V2: 31 câu).
4. vidence/03_ragas_scores.png: Ảnh chụp màn hình terminal kết quả đánh giá RAGAS.
5. vidence/03_ragas_report.json: File JSON xuất kết quả 4 chỉ số RAGAS của cả 2 phiên bản.
6. vidence/04_pii_demo_log.txt: Log demo kiểm thử PII Detector (Email, Phone, SSN, Credit Card) với cơ chế Fix/Redact.
7. vidence/04_json_demo_log.txt: Log demo kiểm thử JSON Formatter (Sửa lỗi Markdown fences, single quotes, trailing commas).
8. vidence/README.md: Tài liệu phân tích định tính & định lượng chi tiết này.
