# Dữ liệu và đánh giá — PhishGuard

> Tài liệu để viết báo cáo / trả lời hội đồng. Mọi con số lấy từ `backend/eval/results/REPORT.md`,
> `TEXT_REPORT.md`, `metrics.csv` và file mô hình trong `backend/app/` (lần chạy hiện tại).
> Chạy lại đánh giá thì phải cập nhật lại file này.

---

## 1. Tóm tắt

| | Mô hình tên miền / link | Mô hình email / tin nhắn |
|---|---|---|
| Dataset | **PhiUSIIL Phishing URL Dataset** | **ealvaradob/phishing-dataset** (`texts.json`) |
| Nguồn | UCI Machine Learning Repository, 2024 | Hugging Face, giấy phép Apache-2.0 |
| Link | https://archive.ics.uci.edu/dataset/967 | https://huggingface.co/datasets/ealvaradob/phishing-dataset |
| Ngôn ngữ | Tên miền quốc tế | Email + SMS tiếng Anh |
| Sau làm sạch | 219.036 tên miền (84.244 lừa đảo / 134.792 hợp lệ) | 20.137 văn bản (7.672 lừa đảo) |
| Train / Test | 175.228 / 43.808 | 16.109 / 4.028 |
| Mô hình | Logistic Regression trên n-gram ký tự (3–5 ký tự) | Logistic Regression trên từ + cặp từ |
| Kết quả chính | Luật + ML: Precision 0,986, chặn nhầm 0,6% | F1 0,966, ROC-AUC 0,996, chặn nhầm 1,6% |
| Script | `backend/eval/evaluate.py` | `backend/eval/evaluate_text.py` |
| File mô hình | `backend/app/ml_model.json` (38.783 trọng số) | `backend/app/text_model.json` (20.584 trọng số) |

Cả hai đều chia **80/20 phân tầng theo nhãn**, `random_state=42` (chạy lại ra đúng kết quả cũ).

---

## 2. PhiUSIIL — mô hình tên miền

### 2.1. Dữ liệu gốc
- Khoảng 235 nghìn URL, nhãn trong file: `label = 0` là lừa đảo, `label = 1` là hợp lệ.
- File CSV khoảng 57MB, **không để trong repo** (tải về khi cần chạy lại).

### 2.2. Vấn đề phát hiện khi phân tích dữ liệu
**100% URL hợp lệ trong PhiUSIIL có dạng `https://www.<tên miền>` và không có đường dẫn**, còn URL lừa đảo thì đủ kiểu.
Nếu huấn luyện trên URL đầy đủ, mô hình chỉ cần học mẹo "có `www.` + không có đường dẫn = an toàn" là đạt gần 100%,
nhưng con số đó vô nghĩa khi gặp link thật.

→ **Chỉ dùng tên miền** để huấn luyện và đánh giá.

### 2.3. Các bước làm sạch (`load()` trong `evaluate.py`)
1. Lấy tên máy (hostname) từ URL, chuyển chữ thường.
2. Bỏ tiền tố `www.` và dấu chấm cuối.
3. Bỏ dòng không có dấu chấm (không phải tên miền hợp lệ).
4. Bỏ tên miền **vừa có nhãn lừa đảo vừa có nhãn hợp lệ** (mâu thuẫn).
5. Mỗi tên miền chỉ giữ một dòng (loại trùng).

→ Còn **219.036 tên miền**.

### 2.4. Các phương pháp so sánh (trên tập test 43.808 tên miền)

| Phương pháp | Accuracy | Precision | Recall | F1 | ROC-AUC | Chặn nhầm (FPR) |
|---|---|---|---|---|---|---|
| Bộ luật (ngưỡng 0,3 – đáng ngờ trở lên) | 0,626 | 0,975 | 0,028 | 0,054 | 0,612 | 0,0% |
| Bộ luật (ngưỡng 0,6 – chỉ lừa đảo) | 0,617 | 1,000 | 0,005 | 0,010 | 0,612 | 0,0% |
| ML: Gradient Boosting (18 đặc trưng tự thiết kế) | 0,851 | 0,930 | 0,663 | 0,774 | 0,860 | 3,1% |
| ML: Logistic Regression (n-gram ký tự) | 0,868 | 0,882 | 0,758 | 0,816 | 0,914 | 6,3% |
| **Kết hợp: luật + ML (cách backend dùng)** | **0,858** | **0,986** | **0,641** | **0,776** | **0,848** | **0,6%** |

**Đọc bảng thế nào:**
- **Bộ luật**: gần như không chặn nhầm (Precision rất cao), nhưng bỏ sót nhiều (Recall thấp). Lý do: luật chỉ bắt mẫu rõ ràng
  (giả mạo thương hiệu, đuôi tên miền rẻ, từ khóa dụ dỗ). Đây là chủ đích: thà bỏ sót còn hơn chặn nhầm trang thật.
- **ML một mình**: bắt được nhiều hơn hẳn (Recall 0,758) nhưng chặn nhầm 6,3%, quá cao để dùng một mình.
- **Kết hợp**: ML chỉ là **điểm cộng tối đa +0,3** vào điểm của luật → giữ chặn nhầm ở **0,6%** mà Recall tăng từ 0,028 lên 0,641.
- Chọn Logistic Regression n-gram để triển khai (thay vì Gradient Boosting) vì AUC cao hơn (0,914) và xuất ra được file JSON
  chạy bằng Python thuần → không cần cài scikit-learn trên server.
- Script tự kiểm tra: mô hình JSON trong backend cho kết quả **giống hệt** mô hình scikit-learn.

### 2.5. So sánh với Gemini (mẫu 59 tên miền, cân bằng 2 nhãn)

| Phương pháp | Accuracy | Precision | Recall | F1 | ROC-AUC | Chặn nhầm |
|---|---|---|---|---|---|---|
| Bộ luật | 0,492 | 0,000 | 0,000 | 0,000 | 0,567 | 0,0% |
| ML n-gram | **0,797** | 0,909 | 0,667 | 0,769 | 0,921 | 6,9% |
| Gemini (chỉ xem URL) | **0,797** | 0,950 | 0,633 | 0,760 | 0,857 | 3,4% |

- Lấy 60 tên miền, Gemini trả lời được 59 lần.
- **Tốc độ:** ML 0,033 ms/tên miền, Gemini trung bình 2.644 ms/lần → ML nhanh hơn **khoảng 80.000 lần**, và miễn phí.
- **Kết luận:** độ chính xác ngang nhau → dùng ML lọc trước mọi trang, chỉ hỏi Gemini khi trang có form và điểm còn chưa chắc chắn.

### 2.6. Mô hình học được gì (ví dụ)
- n-gram nghiêng về **lừa đảo**: `^is-`, `.cf`, `nft`, `.ga$`, `dns`... (đuôi tên miền miễn phí, từ khóa crypto, tên miền động).
- n-gram nghiêng về **hợp lệ**: `.ac.`, `.edu$`, `.mil`, `.ch$`, `.se$`... (tên miền giáo dục, quân sự, quốc gia châu Âu).

### 2.7. Biểu đồ (đã có sẵn, dùng được cho báo cáo)
- `backend/eval/results/roc.png` — đường ROC của các phương pháp.
- `cm_rules.png`, `cm_ml.png`, `cm_combined.png` — ma trận nhầm lẫn.
- Trên web: `<URL>/eval/roc.png`, `<URL>/eval/cm_combined.png`...

---

## 3. ealvaradob/phishing-dataset — mô hình email / tin nhắn

### 3.1. Dữ liệu
- File `texts.json`: email + SMS **tiếng Anh**, nhãn 1 = lừa đảo, 0 = bình thường.
- Làm sạch: bỏ dòng thiếu, cắt văn bản tối đa 20.000 ký tự, **bỏ văn bản trùng** → 20.137 văn bản (7.672 lừa đảo).

### 3.2. Kết quả (tập test 4.028 văn bản)

| Phương pháp | Accuracy | Precision | Recall | F1 | ROC-AUC | Chặn nhầm |
|---|---|---|---|---|---|---|
| Bộ luật email (chỉ nội dung) | 0,628 | 0,788 | 0,034 | 0,065 | 0,544 | 0,6% |
| **ML: Logistic Regression (từ + cặp từ)** | **0,974** | **0,974** | **0,958** | **0,966** | **0,996** | **1,6%** |

- Bộ luật email ở đây bị thiệt: dataset chỉ có nội dung, không có người gửi, Reply-To hay link riêng
  (khi chạy thật, luật xét cả những thứ đó).
- Mô hình **chỉ cho điểm khi văn bản có ≥ 12 từ/cặp từ mà nó biết**. 94% văn bản test đạt điều kiện này.
  Tin nhắn tiếng Việt thường không đạt → hệ thống dựa vào bộ luật (có từ khóa tiếng Việt) và Gemini.
- Từ nghiêng về lừa đảo: `click here`, `free`, `call`, `your`, `txt`... Từ nghiêng về bình thường: `thanks`, `attached`, `wrote`, `university`...
- Ma trận nhầm lẫn: `backend/eval/results/cm_text_ml.png`.

---

## 4. Nguồn dữ liệu khác (không dùng để huấn luyện)

| Nguồn | Dùng làm gì | Ghi chú |
|---|---|---|
| **OpenPhish** (feed miễn phí) | Tự nạp vào danh sách đen | Khoảng 425 tên miền; cập nhật lúc khởi động (nếu quá 12 giờ) và bằng nút trên dashboard; mục cũ tự xóa sau 7 ngày |
| **Google Safe Browsing** | Hỏi Google khi kiểm tra từng link | Google đánh dấu → kết luận lừa đảo ngay |
| **RDAP** | Tra ngày đăng ký tên miền | Tên miền < 14 ngày +0,3; < 90 ngày +0,15. Đuôi `.vn` chưa có RDAP |
| **Báo cáo cộng đồng** | ≥ 3 người khác nhau báo trong 30 ngày → +0,3 | Lưu mã băm IP, không lưu IP |
| Danh sách tin cậy | 48 tên miền, soạn tay | `backend/scripts/seed.py` |
| Thương hiệu | 26 thương hiệu hay bị giả mạo, soạn tay | `BRANDS` trong `backend/app/heuristics.py` |

---

## 5. Số liệu trên trang web: cái nào thật, cái nào viết sẵn

| Trang | Lấy thật (tự thay đổi) | Viết sẵn trong HTML |
|---|---|---|
| `/` | Mọi kết quả kiểm tra (điểm, kết luận, lý do) | Link / email / tin nhắn mẫu (để demo); số 175.000 và 16.000 trong thẻ "kiểm tra như thế nào" |
| `/about` | 6 ô số liệu (đếm từ MongoDB); bảng đánh giá (đọc `metrics.csv`); ảnh ROC và ma trận nhầm lẫn | Các đoạn mô tả có số (43.808, 0,797, chỉ số mô hình email...) |
| `/dashboard` | Tất cả | — |

"Nguồn: Kết quả đã lưu" = bộ nhớ đệm 24 giờ (link đã kiểm tra gần đây trả lại kết quả cũ). Muốn demo chấm mới thì dán link chưa thử bao giờ.

---

## 6. Hạn chế về dữ liệu (nên tự nói trước khi bị hỏi)

- PhiUSIIL có **ít tên miền Việt Nam**; dữ liệu hợp lệ chủ yếu là trang chủ website quốc tế.
- Mô hình email/tin nhắn **chỉ có dữ liệu tiếng Anh** → chưa có mô hình tiếng Việt.
- Chỉ đánh giá trên **tên miền**, không đánh giá được phần đường dẫn của URL (do đặc điểm dataset ở mục 2.2).
- So sánh với Gemini chỉ trên **59 mẫu** (giới hạn hạn mức API miễn phí) → kết quả mang tính tham khảo.
- Dataset email có nhiều email cũ (từ Enron, đầu những năm 2000) → mô hình học cả từ như `enron`, `2002`.

**Hướng phát triển:** thu thập dữ liệu lừa đảo tiếng Việt có nhãn (tin nhắn giả ngân hàng, link giả Shopee/Lazada...)
để huấn luyện mô hình riêng.

---

## 7. Câu hỏi hội đồng hay hỏi về dữ liệu

**Hỏi: Em dùng bộ dữ liệu nào? Sao tin được?**
Đáp: PhiUSIIL của UCI (2024), một kho dữ liệu học máy uy tín, và bộ email/SMS công khai trên Hugging Face (Apache-2.0).
Cả hai đều có nhãn sẵn, ai cũng tải về chạy lại được, và em cố định `random_state=42` để kết quả lặp lại được.

**Hỏi: Sao không dùng URL đầy đủ mà chỉ dùng tên miền?**
Đáp: Vì trong PhiUSIIL mọi URL hợp lệ đều là `https://www.tên-miền` không có đường dẫn. Dùng URL đầy đủ thì mô hình học mẹo
đó và đạt gần 100% một cách vô nghĩa. Dùng tên miền cho con số thấp hơn nhưng trung thực.

**Hỏi: Accuracy chỉ 0,858, sao không cao hơn?**
Đáp: Em ưu tiên **không chặn nhầm trang thật** (chặn nhầm 0,6%, Precision 0,986). Những trang bỏ sót còn được các lớp khác bắt:
danh sách đen OpenPhish, Google Safe Browsing, tuổi tên miền, và Gemini đọc nội dung trang có form đăng nhập.
Con số 0,858 là khi **chỉ nhìn tên miền**, còn khi chạy thật hệ thống có thêm nhiều thông tin hơn.

**Hỏi: Sao không dùng deep learning?**
Đáp: Logistic Regression đạt AUC 0,914 / 0,996, chạy 0,03 ms, lưu được thành file JSON chạy trên server miễn phí không cần GPU.
Với bài toán này, ca khó đã có Gemini (mô hình ngôn ngữ lớn) xử lý.

**Hỏi: Tin nhắn tiếng Việt thì sao?**
Đáp: Mô hình học máy chưa có dữ liệu tiếng Việt nên tự bỏ qua (khi biết dưới 12 từ). Khi đó bộ luật có từ khóa tiếng Việt
(`tạm khóa`, `mã OTP`, `chuyển khoản`, `trong 24 giờ`...) và Gemini đảm nhận. Thu thập dữ liệu tiếng Việt là hướng phát triển.

---

## 8. Chạy lại đánh giá

Từ thư mục `backend`:
```
pip install -r eval/requirements-eval.txt
python -m eval.evaluate <đường-dẫn>/PhiUSIIL_Phishing_URL_Dataset.csv --gemini 60
python -m eval.evaluate_text <đường-dẫn>/texts.json
```
- Mất khoảng 3 phút (PhiUSIIL) và 16 giây (email).
- **Ghi đè** `app/ml_model.json`, `app/text_model.json` và toàn bộ `eval/results/` → nhớ cập nhật lại file này
  và các con số viết sẵn trên trang `/` và `/about` (mục 5).
