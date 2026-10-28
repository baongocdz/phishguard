# Dữ liệu cho trợ lý chat PhishGuard (Giai đoạn 2)

Mục tiêu: ~2.700 mẫu hội thoại tiếng Việt để fine-tune trợ lý (Giai đoạn 3). Dữ liệu do model sinh chỉ là
**bản nháp**; chỉ mẫu đã được người duyệt (`"reviewed": true`) mới vào tập train.

| Nhóm | Số mẫu dự kiến | Nội dung |
|---|---|---|
| `knowledge` | 1.200 | Hỏi–đáp kiến thức (89 chủ đề lừa đảo phổ biến ở VN × 8 kiểu người hỏi) |
| `scan` | 600 | Giải thích **kết quả quét thật** của PhishGuard (`<scan_result>`) |
| `multi_turn` | 450 | Hội thoại 2–3 lượt theo tình huống |
| `out_of_scope` | 250 | Câu hỏi ngoài phạm vi / yêu cầu gây hại → từ chối lịch sự |
| `injection` | 200 | Nội dung dán vào có prompt injection → không làm theo |

## File

| File | Vai trò |
|---|---|
| `system_prompt.txt` | Vai trò + quy tắc của trợ lý. Dùng chung khi sinh dữ liệu, fine-tune và chạy thật |
| `seeds.json` | Chủ đề, tình huống, kiểu người hỏi — sửa/thêm để đa dạng dữ liệu |
| `common.py` | Định dạng 1 mẫu, kiểm tra lỗi, cờ cần chú ý (số điện thoại, link lạ, không phải tiếng Việt...) |
| `build_scan_inputs.py` | Chạy bộ chấm thật của backend → `data/scan_inputs.jsonl` |
| `generate.py` | Sinh bản nháp qua API kiểu OpenAI → `data/drafts.jsonl` (chạy lại thì tiếp tục) |
| `review.html` | Mở bằng trình duyệt để đọc, sửa, duyệt/bỏ từng mẫu → tải về `reviewed.jsonl` |
| `check.py` | Kiểm tra lỗi, trùng lặp, thống kê; chia `train/val/test.jsonl` (80/10/10 theo từng nhóm) |
| `data/` | Dữ liệu (đã `.gitignore`, không đưa lên git) |

## Quy trình

```bash
cd backend
.venv\Scripts\python ../training/chat_data/build_scan_inputs.py --phiusiil <PhiUSIIL.csv> --n 900

cd ../training/chat_data
# Model sinh nháp: LM Studio trên máy (Developer → Start Server) hoặc server kiểu OpenAI khác
..\..\backend\.venv\Scripts\python generate.py --base-url http://localhost:1234/v1 --model <id model> --limit 20
..\..\backend\.venv\Scripts\python check.py data/drafts.jsonl          # xem chất lượng 20 mẫu thử rồi mới chạy hết

# Duyệt: mở review.html bằng Chrome → chọn data/drafts.jsonl → duyệt → "Tải về reviewed.jsonl" → chép vào data/
..\..\backend\.venv\Scripts\python check.py data/reviewed.jsonl --split   # → data/train.jsonl, val.jsonl, test.jsonl
```

**Sinh trên Kaggle (khuyên dùng):** import `training/kaggle/generate_drafts.ipynb` vào Kaggle (GPU T4 x2,
Internet On) và chạy từ trên xuống. Mã nguồn + `data/scan_inputs.jsonl` đã **nhúng sẵn** trong notebook (không cần
dataset); notebook chạy Qwen3 bằng vLLM và gọi đúng `generate.py` này (`--workers 32 --no-think`).
Sửa code ở đây xong thì chạy `python training/kaggle/build_notebook.py` để nhúng lại (tiêu đề notebook ghi
"bản code" để biết Kaggle đang chạy bản nào).

**Chấm sơ bộ (LLM-as-judge) để đỡ đọc hết:** `to_review.jsonl` (bản nháp đã bỏ trùng) → notebook
`training/kaggle/judge_drafts.ipynb` (Qwen3-32B chấm 1–5 theo `common.FACTS` + tiêu chí từng nhóm, `judge.py`)
→ `data/judged.jsonl`. Mở file đó trong `review.html`:
1. ① đọc kỹ mọi mẫu điểm ≤ 3 (sửa hoặc bỏ);
2. ② kiểm tra ngẫu nhiên ≥ 10% mẫu điểm ≥ 4 — thấy model chấm bỏ sót nhiều lỗi thì đọc thêm;
3. ③ "Chấp nhận phần còn lại": mẫu được đánh dấu `auto_accepted` (báo cáo ghi rõ "duyệt thủ công có máy hỗ trợ");
   `check.py` không đưa mẫu này vào tập test.
Không dùng Claude/Gemini để chấm hay sửa dữ liệu train (điều khoản của cả hai hạn chế dùng để phát triển model khác).

Khi duyệt, chú ý các mẫu có cờ ⚑: số điện thoại / đường link phải có thật (tốt nhất là xóa, hướng dẫn dùng kênh
chính thức), thông tin phải đúng với Việt Nam hiện tại, giọng văn dễ hiểu.

## Lưu ý về nguồn sinh nháp

- **Điều khoản Gemini API** (cập nhật 28/04/2026): *"You may not use the Services to develop models that compete
  with the Services"*. Trợ lý hẹp về an toàn thông tin khó coi là cạnh tranh, nhưng là vùng xám; gói miễn phí
  còn cho Google dùng nội dung gửi lên. Vì vậy ưu tiên model mã nguồn mở có giấy phép cho dùng đầu ra (vd dòng
  Qwen3, Apache 2.0 — kiểm tra lại giấy phép của đúng bản dùng trên Hugging Face).
- Ghi lại model đã dùng để sinh (trường `source`) — cần cho phần phương pháp trong báo cáo.
- Tập `test.jsonl` giữ riêng để đánh giá (Giai đoạn 7), không dùng khi fine-tune.
