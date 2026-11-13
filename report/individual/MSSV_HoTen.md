# Báo cáo cá nhân — Day 06: Data Ingestion Engineering

## Thông tin học viên

- **MSSV:** 2S202603633
- **Họ tên:** Nguyễn Đức Minh
- **Chủ đề:** Data Ingestion, Chunking, Embedding, Vector Search và Retrieval Evaluation

## 1. Dữ liệu và Pipeline

### 1.1. Nguồn dữ liệu

Dự án sử dụng tài liệu `aimlBook_30_trang.pdf` gồm 30 trang, tập trung vào Artificial Intelligence và Knowledge Representation.

Theo kết quả CP3, hệ thống xử lý thành công 30 trang và không ghi nhận trang rỗng hoặc lỗi trích xuất.

Nguồn gốc và quyền phân phối tài liệu cần được xác nhận trong manifest; báo cáo không mặc định tài liệu có giấy phép phân phối công khai.

### 1.2. Kiến trúc pipeline

Pipeline được xây dựng theo quy trình:

`PDF → Text Extraction → Normalization → Chunking → Embedding → PostgreSQL/pgvector → Similarity Search → Evaluation`

Các thành phần chính:

- **Text Extraction:** Trích xuất văn bản theo từng trang PDF.
- **Normalization:** Chuẩn hóa nội dung trước khi chia chunk.
- **Chunking:** Thử nghiệm fixed-size và paragraph-aware.
- **Embedding:** Sử dụng `sentence-transformers/all-MiniLM-L6-v2`, vector 384 chiều.
- **Vector Database:** PostgreSQL 16.16 và pgvector 0.8.7 theo log môi trường.
- **Retrieval:** Cosine similarity, trả về top-3 kết quả.
- **Evaluation:** Đánh giá độ chính xác, tính mạch lạc, metadata và grounding.

Embedding được chạy local, không phát sinh phí API embedding được ghi nhận. Chi phí phần cứng, RAM, CPU và điện năng chưa được đo.

## 2. Cấu hình thử nghiệm

### 2.1. Ba chiến lược ingestion

| Strategy | Chunking | Configuration | Metadata filter |
|---|---|---|---|
| A | Fixed-size | 800 ký tự, overlap 120 | Không |
| B | Paragraph-aware | Tối đa 800 ký tự | Không |
| C | Paragraph-aware | Giống B | Có filter theo section |

Strategy C sử dụng cùng chunking và embedding với B. Điểm khác biệt chính là áp dụng metadata filter khi câu hỏi yêu cầu.

### 2.2. Thống kê chunk

| Metric | Strategy A | Strategy B/C |
|---|---:|---:|
| Chunk count | 84 | 82 |
| Minimum length | 165 | 2 |
| Maximum length | 800 | 799 |
| Average length | 691.3 | 636.1 |
| Index time | ~3.3 s | ~2.8 s (B) |

Strategy B/C tạo ít hơn 2 chunks so với A, tương đương khoảng 2.4%.

Tuy nhiên, chunk ngắn nhất chỉ có 2 ký tự, cho thấy paragraph-aware chunking chưa xử lý tốt tất cả các trường hợp. Đây là hạn chế về chất lượng phân đoạn cần cải thiện.

Thời gian index trên chỉ phản ánh các lần chạy CP4 đã ghi nhận, không phải benchmark latency đầy đủ. Strategy C chưa có thời gian index riêng.

### 2.3. Benchmark dataset

Bộ benchmark gồm 20 câu hỏi:

- Development set: Q01–Q15, gồm 15 câu.
- Test set: Q16–Q20, gồm 5 câu.
- Có 3 câu yêu cầu metadata filter: 2 câu dev và 1 câu test.

Quy tắc chọn chiến lược được xác định trước khi đánh giá test:

1. Ưu tiên Evidence Hit@3 trên dev.
2. Dùng Evidence Hit@1 làm tiêu chí phụ.
3. Không thay đổi chiến lược dựa trên kết quả test.

## 3. Retrieval Accuracy

### 3.1. Định nghĩa chỉ số

**Evidence Hit@1:** Tỷ lệ câu hỏi có bằng chứng đúng ở kết quả xếp hạng đầu tiên.

**Evidence Hit@3:** Tỷ lệ câu hỏi có ít nhất một bằng chứng đúng trong ba kết quả đầu tiên.

**Page Hit@3:** Tỷ lệ câu hỏi có trang chứa bằng chứng xuất hiện trong top-3.

Công thức:

`Hit@k = Số câu truy xuất đúng trong top-k / Tổng số câu hỏi`

Evidence Hit được tính bằng phương pháp so khớp gold evidence đã chuẩn hóa. Do đó, kết quả có thể bị ảnh hưởng bởi việc đoạn gold evidence vượt qua ranh giới chunk.

### 3.2. Kết quả Development Set

| Strategy | Evidence Hit@1 | Evidence Hit@3 | Page Hit@3 |
|---|---:|---:|---:|
| A | 40.0% | 53.3% | 100.0% |
| B | 33.3% | 46.7% | 93.3% |
| C | 33.3% | 46.7% | 93.3% |

Strategy A đạt Evidence Hit@3 cao nhất với 8/15 câu đúng, so với 7/15 của B và C.

### 3.3. Kết quả Test Set

| Strategy | Evidence Hit@1 | Evidence Hit@3 | Page Hit@3 |
|---|---:|---:|---:|
| A | 40.0% | 60.0% | 80.0% |
| B | 40.0% | 40.0% | 100.0% |
| C | 40.0% | 40.0% | 100.0% |

Strategy A đạt Evidence Hit@3 cao nhất trên test với 3/5 câu đúng.

Ngược lại, B/C đạt Page Hit@3 100%, cho thấy hai chiến lược có thể xác định đúng trang nhưng không nhất thiết lấy được đoạn bằng chứng phù hợp.

**Kết luận:** Strategy A được lựa chọn vì có Evidence Hit@3 tốt nhất trên dev. Kết quả test phù hợp với lựa chọn này nhưng không được sử dụng để tối ưu lại chiến lược.

## 4. Chunk Coherence

### 4.1. Phương pháp

Sử dụng `manual_coherence_dev.csv` để đánh giá 10 vị trí nguồn cho từng chiến lược, tổng cộng 30 mẫu.

Thang điểm:

- **0:** Nội dung bị cắt đứt, mất ngữ cảnh quan trọng.
- **1:** Nội dung hiểu được một phần, nhưng ranh giới chunk chưa tốt.
- **2:** Nội dung mạch lạc, có đủ ngữ cảnh và giữ được ý chính.

Công thức:

`Average Coherence = Tổng điểm / Số mẫu đã chấm`

### 4.2. Phân tích định tính

**Strategy A — Fixed-size**

Fixed-size chunking có ưu điểm là kiểm soát kích thước ổn định và sử dụng overlap để giảm mất thông tin ở ranh giới.

Tuy nhiên, một số mẫu trong file đánh giá thể hiện việc cắt giữa câu hoặc giữa từ. Ví dụ, chunk tại trang 4 bắt đầu bằng phần cuối của một từ, trong khi chunk tại trang 10 bắt đầu giữa một từ liên quan đến tài nguyên máy tính.

Điều này làm giảm khả năng hiểu chunk khi được sử dụng độc lập.

**Strategy B/C — Paragraph-aware**

Paragraph-aware hướng đến việc giữ cấu trúc đoạn văn, nhưng giới hạn kích thước vẫn có thể khiến một đoạn bị chia tại vị trí không phù hợp.

Ở Q02, nội dung giải thích pattern recognition bị phân chia giữa hai chunks tại trang 2. Một chunk kết thúc ở phần mở đầu của ý, chunk kế tiếp mới chứa phần giải thích còn lại.

Ngoài ra, độ dài tối thiểu 2 ký tự cho thấy tồn tại chunk không đủ thông tin ngữ nghĩa.

### 4.3. Kết quả và giới hạn

File `manual_coherence_dev.csv` đã có 30 mẫu nhưng các cột `coherence_0_1_2` và `reason` chưa có nhãn đánh giá.

Vì vậy, chưa thể tính điểm coherence trung bình hợp lệ hoặc khẳng định chiến lược nào có coherence cao nhất.

**Đề xuất cải tiến:** Áp dụng minimum chunk length, tránh cắt giữa từ/câu, gộp đoạn quá ngắn với đoạn lân cận và kiểm tra coherence trước khi tạo embedding.

## 5. Metadata Usefulness

### 5.1. Các trường metadata

Pipeline sử dụng các trường:

- `document_id`: Định danh tài liệu.
- `source`: Đường dẫn nguồn.
- `page`: Trang nguồn.
- `page_id`: Định danh trang.
- `section`: Chương hoặc phần nội dung.
- `chunk_index`: Thứ tự chunk.
- `method`: Phương pháp chunking.

Các trường kỹ thuật khác gồm `char_count`, `start_char`, `end_char`, `empty` và `extraction_error`.

### 5.2. Phương pháp đánh giá

Đánh giá metadata theo ba tiêu chí:

**Completeness:** Các trường bắt buộc có tồn tại và có giá trị hợp lệ không.

**Correctness:** `page`, `section`, `source` và các định danh có phản ánh đúng tài liệu gốc không.

**Filter Compliance:** Kết quả trả về có tuân thủ điều kiện filter được yêu cầu không.

File `manual_metadata_test.csv` chứa 45 hàng tương ứng 5 câu test × 3 chiến lược × 3 kết quả truy xuất.

### 5.3. Kết quả filter compliance

Strategy C có kết quả:

| Split | Compliant hits | Compliance |
|---|---:|---:|
| Dev | 6/6 | 100% |
| Test | 3/3 | 100% |
| Total | 9/9 | 100% |

Kết quả cho thấy Strategy C tuân thủ điều kiện filter trong các trường hợp được kiểm tra.

Tuy nhiên, filter compliance không đồng nghĩa với độ chính xác truy xuất hoặc metadata correctness.

### 5.4. Hạn chế

Cột `metadata_correct_0_1` trong CSV vẫn chưa được chấm.

Các trường `start_char` và `end_char` ở paragraph-aware có giá trị null trong traces được kiểm tra, nên không thể dùng trực tiếp để truy vết vị trí ký tự.

Metadata `section` được gán theo trang. Phương pháp này có thể thiếu chính xác nếu một trang chứa nhiều section.

**Kết luận:** Metadata hỗ trợ truy xuất có điều kiện và truy vết nguồn. Strategy C đạt 100% filter compliance trên các mẫu được kiểm tra, nhưng metadata correctness toàn diện vẫn cần xác minh thủ công.

## 6. Grounding Quality

### 6.1. Phương pháp

Đánh giá 5 câu test Q16–Q20 cho cả ba chiến lược, tổng cộng 15 trường hợp.

Thang điểm:

- **0:** Bằng chứng không hỗ trợ câu trả lời.
- **1:** Bằng chứng hỗ trợ một phần.
- **2:** Bằng chứng đầy đủ để trả lời đúng.

Công thức:

`Average Grounding = Tổng điểm grounding / 5`

Grounding đánh giá khả năng hỗ trợ câu trả lời của nội dung truy xuất, không chỉ kiểm tra trang nguồn hoặc exact evidence match.

### 6.2. Phân tích 5 câu test

| Question | A Hit@3 | B Hit@3 | C Hit@3 | Nhận xét |
|---|---:|---:|---:|---|
| Q16 | 1 | 1 | 1 | Cả ba tìm đúng bằng chứng |
| Q17 | 1 | 0 | 0 | A tìm được định nghĩa declarative knowledge |
| Q18 | 1 | 1 | 1 | Cả ba tìm được gold evidence |
| Q19 | 0 | 0 | 0 | Tìm đúng trang nhưng exact match thất bại |
| Q20 | 0 | 0 | 0 | B/C tìm trang 30 ở rank 3; A không tìm được |

**Q16 — Goal-based agents**

Cả ba chiến lược truy xuất đúng đoạn giải thích rằng goal-based agents linh hoạt hơn reflex agents vì có thể điều chỉnh quyết định dựa trên thông tin về mục tiêu.

**Q17 — Declarative knowledge**

Strategy A lấy được chunk trang 24 chứa định nghĩa declarative knowledge là passive knowledge.

B/C truy xuất trang 24 nhưng không đưa đoạn định nghĩa đầy đủ vào top-3.

**Q18**

Cả ba chiến lược đạt automatic Evidence Hit@3. Đây là tín hiệu tích cực về khả năng truy xuất bằng chứng, nhưng không thay thế cho điểm grounding thủ công.

**Q19**

Các chiến lược truy xuất trang 28 chứa nội dung liên quan đến indexing. Tuy nhiên, phép so khớp gold evidence không ghi nhận hit.

Trường hợp này cho thấy exact evidence matching có thể đánh giá thấp khả năng hỗ trợ câu trả lời khi gold evidence có phần ngữ cảnh không nằm trong chunk.

**Q20**

Strategy A không đưa trang 30 vào top-3. B/C đưa trang 30 vào rank 3 nhưng vẫn không khớp gold evidence đầy đủ.

Cần xem nội dung chunk trang 30 trước khi xác nhận khả năng grounding.

### 6.3. Kết quả

File `manual_grounding_test.csv` đã có đủ 15 hàng đánh giá, nhưng `grounding_0_1_2` và `reason` vẫn trống.

Do đó, chưa có điểm grounding trung bình hợp lệ.

**Kết luận:** Strategy A có kết quả automatic Evidence Hit@3 cao nhất, nhưng không thể suy ra điểm grounding trung bình chỉ từ Hit@3. Hai chỉ số đo các khía cạnh khác nhau.

## 7. Data Strategy Impact

### 7.1. So sánh A–B

Strategy A sử dụng fixed-size chunking, trong khi B sử dụng paragraph-aware chunking.

Kết quả cho thấy:

- Số chunks giảm từ 84 xuống 82.
- Average chunk length giảm từ 691.3 xuống 636.1 ký tự.
- Evidence Hit@3 dev giảm từ 53.3% xuống 46.7%.
- Evidence Hit@3 test giảm từ 60.0% xuống 40.0%.
- Page Hit@3 test tăng từ 80.0% lên 100.0%.

Như vậy, paragraph-aware chunking chưa cải thiện độ chính xác bằng chứng trong thử nghiệm này.

Một nguyên nhân có thể là việc phân đoạn làm tách nội dung quan trọng, khiến embedding và retrieval không đưa đúng bằng chứng vào top-3.

### 7.2. So sánh B–C

Strategy B và C sử dụng cùng phương pháp chunking và embedding.

Strategy C bổ sung metadata filtering theo section khi có yêu cầu.

Kết quả:

- Evidence Hit@3 dev: đều 46.7%.
- Evidence Hit@3 test: đều 40.0%.
- Chunk count: đều 82.
- Strategy C đạt 9/9 filter-compliant hits.

Metadata filtering đã đáp ứng điều kiện lọc trên các mẫu được kiểm tra nhưng chưa tạo ra cải thiện về Evidence Hit@3 tổng thể.

Điều này không chứng minh metadata filtering không hữu ích. Tác động có thể phụ thuộc vào số lượng tài liệu, mức độ trùng lặp chủ đề và độ chọn lọc của filter.

### 7.3. Trade-offs

| Yếu tố | A | B | C |
|---|---|---|---|
| Evidence retrieval | Tốt nhất trong thử nghiệm | Thấp hơn A | Bằng B |
| Chunk boundaries | Có thể cắt giữa ý | Cố gắng giữ đoạn | Giống B |
| Chunk count | 84 | 82 | 82 |
| Section filtering | Không | Không | Có |
| Độ phức tạp | Thấp | Trung bình | Cao hơn B |

**Lựa chọn cuối cùng:** Strategy A, theo tiêu chí Evidence Hit@3 trên dev.

## 8. Failure Analysis

### 8.1. Boundary Fragmentation

Các đoạn gold evidence dài có thể vượt qua ranh giới chunk. Khi đó, hệ thống tìm được nội dung liên quan nhưng exact matching vẫn cho kết quả sai.

### 8.2. Retrieval Ranking

Q17 cho thấy việc tìm đúng trang không đảm bảo đoạn bằng chứng cần thiết được xếp trong top-3.

### 8.3. Gold Evidence Normalization

Q19 cho thấy gold evidence có thể chứa ngữ cảnh dư thừa hoặc khác cách chia chunk, làm giảm độ tin cậy của exact-match evaluation.

### 8.4. Metadata Granularity

Gán section theo trang đơn giản nhưng không đảm bảo chính xác khi trang có nhiều phần nội dung.

### 8.5. Benchmark Size

Tập test chỉ gồm 5 câu. Mỗi câu tương ứng 20 điểm phần trăm, nên chênh lệch giữa các chiến lược chưa đủ để khẳng định khả năng tổng quát hóa.

## 9. Đề xuất cải tiến

1. Áp dụng giới hạn độ dài tối thiểu cho paragraph chunks và gộp chunks quá ngắn.
2. Ưu tiên cắt tại ranh giới câu hoặc đoạn hoàn chỉnh.
3. Chuẩn hóa gold evidence thành các đoạn ngắn chứa đủ ý cần kiểm tra.
4. Bổ sung đánh giá semantic evidence matching bên cạnh exact matching.
5. Tăng số lượng câu hỏi benchmark và mở rộng corpus.
6. Kiểm chứng metadata correctness với tài liệu nguồn.
7. Đo retrieval latency, RAM, CPU và chi phí thực tế.
8. Thử nghiệm hybrid search hoặc reranking để cải thiện thứ hạng bằng chứng.

## 10. Kết luận

Dự án đã xây dựng và thử nghiệm pipeline ingestion sử dụng PDF extraction, chunking, embedding và PostgreSQL/pgvector.

Ba chiến lược A, B, C được so sánh trên cùng bộ benchmark gồm 20 câu hỏi.

Strategy A đạt kết quả Evidence Hit@3 tốt nhất:

- **Dev:** 53.3%.
- **Test:** 60.0%.

Strategy B/C đạt Page Hit@3 100% trên test nhưng Evidence Hit@3 chỉ đạt 40.0%.

Strategy C cho thấy khả năng tuân thủ metadata filter với 9/9 hits hợp lệ trong các trường hợp có filter.

Kết quả chứng minh rằng chất lượng ingestion không chỉ phụ thuộc vào số lượng chunks hay khả năng tìm đúng trang, mà còn phụ thuộc vào ranh giới chunk, xếp hạng bằng chứng và độ chính xác của metadata.

**Giới hạn đánh giá:** Các chỉ số coherence trung bình, metadata correctness và grounding trung bình chưa được công bố vì các nhãn đánh giá thủ công chưa hoàn tất. Những nhận xét định tính không được xem là điểm số đã đo.

## 11. Minh chứng và tái lập

Các file minh chứng:

- `benchmark/questions.jsonl`
- `artifacts/cp5/traces_dev.json`
- `artifacts/cp5/traces_test.json`
- `artifacts/cp5/summary_dev.csv`
- `artifacts/cp5/summary_test.csv`
- `artifacts/cp5/manual_coherence_dev.csv`
- `artifacts/cp5/manual_grounding_test.csv`
- `artifacts/cp5/manual_metadata_test.csv`
- `artifacts/experiment_log.csv`

Các lệnh tái lập:

```bash
python scripts/check_benchmark.py
python scripts/run_cp5.py --split dev
python scripts/run_cp5.py --split test
```

