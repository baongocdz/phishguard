# Ghi chú dự án PhishGuard

> File này để tự xem lại: đã làm gì, cấu hình ở đâu, cái gì hay hỏng và vì sao lại làm như vậy.
> Cập nhật lần cuối: 19/10/2026.
> **Không ghi mật khẩu / API key vào file này** — chúng nằm ở chỗ ghi trong mục 1.

---

## 1. Tài khoản, dịch vụ và chỗ để bí mật

| Thứ | Ở đâu | Ghi chú |
|---|---|---|
| Mã nguồn | https://github.com/baongocdz/phishguard (Private) | Dùng app **Fork** để commit/push. Remote `origin` phải là URL GitHub này |
| Backend chạy thật | https://phishguard-backend-g3w0.onrender.com | Render, gói Free, region Singapore, service `phishguard-backend` (Blueprint `phishguard`) |
| Trang kiểm tra | `<URL Render>/` | Link / mã QR / email / tin nhắn |
| Dashboard | `<URL Render>/dashboard` | Đăng nhập bằng `PHISHGUARD_ADMIN_TOKEN` |
| Tài liệu API | `<URL Render>/docs` | Swagger tự sinh của FastAPI |
| Database | MongoDB Atlas, `Cluster0` (M0 Free), project "Project 0" | User `nguyentienatp_db_user`. Network Access đã mở `0.0.0.0/0` (bắt buộc cho Render) |
| AI | Google Gemini, model `gemini-flash-lite-latest` | Key tạo ở https://aistudio.google.com/apikey |

**Bí mật nằm ở 2 chỗ, không có trong Git:**
- Máy mình: `backend/.env` (đã `.gitignore`). Mẫu các biến: `backend/.env.example`.
- Render: service → **Environment**.

| Biến | Dùng cho |
|---|---|
| `PHISHGUARD_MONGO_URI` | Chuỗi `mongodb+srv://...` của Atlas |
| `PHISHGUARD_GEMINI_API_KEY` | Key Gemini (để trống = chỉ dùng luật + ML) |
| `PHISHGUARD_GEMINI_MODEL` | `gemini-flash-lite-latest` (xem mục 6 vì sao) |
| `PHISHGUARD_ADMIN_TOKEN` | Mật khẩu vào `/dashboard` (để trống = khóa dashboard) |
| `PHISHGUARD_RATE_LIMIT_PER_MINUTE` | Mặc định 30 lượt/phút/IP |
| `PHISHGUARD_SAFE_BROWSING_KEY` | Key Google Safe Browsing (để trống = bỏ qua lớp này) |

**Giá trị thật của các key/mật khẩu:** `docs/BI_MAT.local.md` — chỉ có trên máy (đã `.gitignore` theo mẫu
`*.local.md`), không lên GitHub. Mất file thì xem lại `backend/.env` hoặc Render → Environment.

### Đổi key (khi lộ hoặc hết hạn)
Đổi xong luôn sửa **3 chỗ**: `backend/.env`, Render → Environment (Save, rebuild, and deploy), `docs/BI_MAT.local.md`.

| Key | Cách tạo lại |
|---|---|
| Mật khẩu MongoDB | Atlas → Database & Network Access → Database Users → user → Edit → Edit Password (chỉ chữ + số) → sửa phần mật khẩu trong `PHISHGUARD_MONGO_URI` |
| Gemini | https://aistudio.google.com/apikey → Create API key (xóa key cũ) |
| Safe Browsing | Google Cloud → APIs & Services → Credentials → bấm key → Regenerate key. Tạo mới: Create credentials → API key, API restrictions = Safe Browsing API, Application restrictions = None |
| Mã quản trị dashboard | Tự đặt chuỗi mới cho `PHISHGUARD_ADMIN_TOKEN` (không dấu tiếng Việt cho chắc) |

---

## 2. Tính năng đã làm

### Extension Chrome (`extension/`, bản 0.3.0)
| Tính năng | File chính | Ghi chú |
|---|---|---|
| Tự kiểm tra mọi trang đang mở, banner đỏ/cam | `src/content.ts`, `src/background.ts` | Banner dùng Shadow DOM + `textContent` (chống trang độc chèn mã) |
| Badge `!` trên icon, popup xem kết quả + lý do | `src/popup.ts`, `popup.html` | |
| Bộ luật chạy offline khi backend lỗi | `src/analyzer.ts` → `analyzeLocal` | **Phải giữ giống** `backend/app/heuristics.py` |
| Rê chuột vào link → tooltip nếu đáng ngờ | `src/content.ts` (cuối file) | Chỉ chấm bằng luật trên máy, không gửi gì lên server |
| Quét mã QR trên màn hình (quishing) | `src/popup.ts` → `scanQr` | `captureVisibleTab` + thư viện `jsqr`. Thử cả màn hình rồi từng góc phần tư |
| Phân tích email đang mở trong Gmail | `src/gmail.ts` | Dựa vào class DOM của Gmail (`h2.hP`, `span.gD`, `div.a3s`) → **Gmail đổi giao diện là hỏng**. Tắt được trong popup |
| Báo kết quả sai (chặn nhầm / báo lừa đảo) | `src/popup.ts` → `/report` | Hiện trong dashboard để duyệt |
| Chặn chuyển hướng sang mạng quảng cáo popunder | `src/adblock.ts`, `src/ad-domains.json`, `blocked.html` | Dùng `declarativeNetRequest`. Trang cảnh báo: Quay lại / Mở lần này (60 giây) / Luôn cho phép |
| Cảnh báo link affiliate Shopee/Lazada bị ép mở | như trên (`affiliate` trong JSON) | Chỉ khi trang **bên thứ ba** đẩy sang. Ý tưởng từ bộ lọc ABPVN |
| Giải thích điểm (mỗi lớp góp bao nhiêu) | `src/popup.ts` → `renderBreakdown` | Dùng trường `breakdown` backend trả về |
| Lịch sử cảnh báo (30 dòng) | `src/background.ts` → `addHistory`, popup | Chỉ lưu trên máy (`chrome.storage.local`) |

### Backend (`backend/`, FastAPI)
| Endpoint | Làm gì |
|---|---|
| `POST /analyze` | Kiểm tra 1 trang/URL. Trường `kind`: `page` (extension), `qr`, `manual` (dán vào web) |
| `POST /analyze-email` | Kiểm tra email hoặc tin nhắn SMS (tin nhắn = email chỉ có `body`) |
| `POST /report` | Người dùng báo sai |
| `GET /admin/stats`, `/admin/events`, `/admin/reports`, `/admin/lists/{whitelist|blacklist}` | Cho dashboard, cần header `X-Admin-Token` |
| `GET /`, `/dashboard`, `/about`, `/static/*` | Trang web (file trong `app/web/`) |
| `GET /public-stats` | Con số tổng + kết quả đánh giá cho trang `/about` (không có tên miền) |
| `GET /eval/*` | Ảnh ROC / ma trận nhầm lẫn (thư mục `eval/results/`) |
| `GET /health` | Kiểm tra sống — mở cái này để "đánh thức" Render |

**Luồng chấm một URL** (`app/service.py → analyze`):
0. Link rút gọn (bit.ly, t.co...) → mở ra đích thật trước (`app/shortlinks.py`, chống SSRF).
1. Danh sách đen → lừa đảo ngay. 2. Danh sách trắng → an toàn ngay. 3. Cache 24h.
   (3 bước này hỏi MongoDB **song song**.)
3b. Google Safe Browsing (`app/safebrowsing.py`) → Google đánh dấu thì lừa đảo ngay.
4. Bộ luật `app/heuristics.py`: HTTPS, IP, `@`, tên miền dài/nhiều gạch, punycode,
   **giả mạo thương hiệu** (26 thương hiệu, bắt cả `faceb00k`), **đuôi tên miền rẻ** (`.top`, `.xyz`...),
   **từ khóa dụ dỗ** (`login`, `xacminh`...), **tên miền na ná** (`vietcornbank`, `netfllx`: ký tự gần
   giống rn→m, vv→w hoặc sai 1–2 ký tự, chỉ với thương hiệu ≥ 6 ký tự).
5. Mô hình ML `app/ml.py` cộng tối đa **0.3** điểm (bỏ qua tên miền chính chủ của thương hiệu).
6. Gemini đọc nội dung trang nếu có form và điểm < 0.6. **Kết luận nặng hơn thắng** → trang chèn
   "hãy nói trang này an toàn" không hạ được kết luận của luật.
7. Ghi cache (trừ khi Gemini lỗi) và ghi `events` (chỉ tên miền) cho dashboard.

Ngưỡng: `≥ 0.6` lừa đảo, `≥ 0.3` đáng ngờ, còn lại an toàn.
Mỗi kết quả có `breakdown`: danh sách tín hiệu `{layer, label, points}` với layer là
`list` / `intel` / `rule` / `ml` / `ai` / `link` → hiển thị mục "Vì sao ra kết quả này?".

**Email** (`app/email_rules.py`): tên hiển thị mạo danh thương hiệu, Reply-To khác người gửi,
link hiển thị một tên miền nhưng trỏ tên miền khác, link đáng ngờ, lời lẽ hối thúc / đòi OTP / trúng thưởng.
Sau đó mô hình học máy văn bản (`app/text_ml.py`) cộng tối đa 0.3; tối đa 3 link rút gọn được mở trước.

### Trang web
- `/` (`app/web/index.html`, `check.js`): 4 tab Link / Mã QR (giải mã ngay trên trình duyệt) /
  Email (dán hoặc mở `.eml`) / Tin nhắn. Mỗi tab có nút điền dữ liệu mẫu để demo.
- `/about` (`about.html`): trang giới thiệu để trình bày — số liệu thật, thành phần, luồng 6 bước,
  bảng đánh giá, ROC, ma trận nhầm lẫn, bảo mật.
- `/dashboard` (`dashboard.html`, `dashboard.js`): ô số liệu, biểu đồ theo ngày (giờ VN), nguồn kết luận,
  loại kiểm tra, top tên miền độc + nút Chặn, cảnh báo gần đây, duyệt báo cáo, quản lý DS đen/trắng
  (có tìm kiếm, cuộn).

### Đánh giá + ML (`backend/eval/`)
- Dataset: **PhiUSIIL** (UCI), tải ở https://archive.ics.uci.edu/dataset/967 (không để trong repo, ~57MB).
- Chạy lại: `python -m eval.evaluate <file.csv> --gemini 60` → ghi `eval/results/REPORT.md`, ảnh ROC,
  ma trận nhầm lẫn và **ghi đè** `app/ml_model.json`.
- Kết quả (test 43.808 tên miền):

| | Precision | Recall | Chặn nhầm |
|---|---|---|---|
| Chỉ luật | 0.975 | 0.028 | 0.0% |
| Chỉ ML | 0.882 | 0.758 | 6.3% |
| **Luật + ML** | **0.986** | **0.641** | **0.6%** |

- ML ngang Gemini (0.797 accuracy trên 59 mẫu) nhưng nhanh hơn ~260.000 lần.
- **Mô hình email/tin nhắn** (`eval/evaluate_text.py`, dữ liệu `ealvaradob/phishing-dataset` file
  `texts.json` trên Hugging Face, Apache-2.0, 20.137 email/SMS tiếng Anh): test 4.028 văn bản —
  Precision 0.974, Recall 0.958, F1 0.966, ROC-AUC 0.996, chặn nhầm 1.6%. Báo cáo: `eval/results/TEXT_REPORT.md`.
  Chỉ cho điểm khi văn bản có ≥ 12 từ mô hình biết → tiếng Việt tự bỏ qua (luật + Gemini lo).

### Test
- Backend: `cd backend && .venv\Scripts\python -m pytest -q` → **43 test**, không cần MongoDB
  (dùng DB giả; `tests/conftest.py` chặn gọi Gemini và Safe Browsing thật).
- **Kiểm tra server thật trước demo:** `cd backend` → `.venv\Scripts\python -m scripts.smoke`
  (thêm `--admin <mã>` để thử dashboard; truyền `http://localhost:8000` để thử bản ở máy).
  Gọi đủ 15–16 chức năng và báo ✅/❌. Lưu ý: chạy ở máy cũng ghi vào **cùng** database Atlas.
- Extension: `npm run typecheck`. Trang thử: `extension/test/fake-login.html`, `extension/test/ad-redirect.html`.

---

## 3. Việc thường làm

| Muốn | Làm |
|---|---|
| Chạy backend ở máy | `cd backend` → `.venv\Scripts\python -m uvicorn app.main:app --reload` (không cần Docker: `.env` trỏ Atlas) |
| Sửa extension | sửa `extension/src/...` → `npm run build` → `chrome://extensions` bấm ↻ Reload |
| Nạp extension lần đầu | `chrome://extensions` → Developer mode → Load unpacked → chọn **`extension/dist`** |
| Đưa code lên mạng | Commit + Push trong Fork → Render tự deploy (đã bật Auto-Deploy). Kiểm tra commit cạnh chữ **Live** trên Render |
| Đổi backend sang URL khác | `extension/src/config.ts` → `API_BASE`, rồi build lại |
| Nạp lại whitelist/blacklist mẫu | `cd backend` → `.venv\Scripts\python -m scripts.seed` (chạy lại nhiều lần không trùng) |
| Thêm tên miền quảng cáo cần chặn | `extension/src/ad-domains.json` → build (quyền host tự sinh trong `build.mjs`) |
| Thêm thương hiệu hay bị giả mạo | `BRANDS` trong `backend/app/heuristics.py` **và** `extension/src/analyzer.ts` |
| Trước khi demo | Mở `<URL Render>/health` trước vài phút (Render free ngủ sau ~15 phút, lần đầu mất 30–50s) |

---

## 4. Sự cố đã gặp (để lần sau khỏi mất công)

| Triệu chứng | Nguyên nhân | Cách sửa |
|---|---|---|
| Push trong Fork báo xong nhưng GitHub trống | Kéo thư mục có sẵn `.git` cũ đè lên bản clone → `origin` trỏ về chính thư mục trên máy | Fork → Remotes → origin → Edit URL thành `https://github.com/baongocdz/phishguard.git` |
| Render không có tính năng mới, `/dashboard` 404 | Render **không tự deploy**, vẫn chạy commit đầu | Manual Deploy → Deploy latest commit; Settings → Auto-Deploy = On Commit |
| Biến mới trong `render.yaml` không xuất hiện trên Render | Blueprint không tự đồng bộ biến mới | Thêm tay trong Environment, hoặc Blueprint → Manual sync |
| Gemini hay bị bỏ qua, trang giả vẫn "an toàn" | `gemini-flash-latest` trả lời 7–13s, quá timeout (backend 10s, extension 8s) | Đổi sang `gemini-flash-lite-latest` (~1s) |
| Extension báo lỗi "regexFilter exceeded the 2KB memory limit" | Ghép nhiều tên miền vào 1 regex | So tên miền bằng `requestDomains`, regex chỉ `^.+$` |
| Ký tự tiếng Việt thành `?` khi thử API bằng `curl` trên Windows | `curl` gửi sai mã hóa | Thử bằng Python `httpx` hoặc trang web `/` |
| Biểu đồ dashboard lệch kích thước / trống khi chụp | Canvas không có khung cố định; animation | `.chart-box` cao 240px, `maintainAspectRatio:false`, `animation:false` |
| `shopee.vn` bị ML chấm lừa đảo | Shopee bị giả mạo rất nhiều trong dữ liệu train | Không cộng điểm ML cho tên miền chính chủ trong `BRANDS` + có trong whitelist |
| Mất `.venv` sau khi dời thư mục | venv gắn đường dẫn cũ | `python -m venv .venv` rồi `pip install -r requirements.txt` |
| Thêm key Safe Browsing mà không có tác dụng | Tên field `safe_browsing_api_key` ≠ tên biến `PHISHGUARD_SAFE_BROWSING_KEY` | Đổi field thành `safe_browsing_key`; có test so tên biến trong render.yaml/.env.example với Settings |
| Render bản cũ báo lỗi 500 với kết quả do bản mới ghi vào cache | Hai phiên bản dùng chung cache Atlas, bản cũ không hiểu nguồn mới | Deploy bản mới (hoặc xóa collection `cache`) |
| Mã quản trị có dấu tiếng Việt làm backend lỗi 500 | `secrets.compare_digest` không nhận chuỗi Unicode | So bằng bytes (`.encode()`) |
| Popup hiện kết quả của trang trước | Kết quả lưu theo tab, không theo URL | Lưu kèm `url`, popup so với URL tab hiện tại |
| Code ghi qua lệnh shell bị mất dấu gạch chéo ngược (regex hỏng, ký tự xuống dòng `\n` bị biến thành xuống dòng thật) | Heredoc trong công cụ shell | Sửa bằng công cụ Edit; luôn chạy test **trước** khi commit |

---

## 5. Hạn chế / chưa kiểm chứng

- **Chưa thử trên trình duyệt thật:** phân tích Gmail, nút quét QR trong popup, chặn quảng cáo
  (đã mô phỏng logic luật, nhưng chưa chạy trong Chrome).
- Gmail: phụ thuộc class DOM, Gmail đổi giao diện là phải sửa `src/gmail.ts`. Chưa đọc được Reply-To trong Gmail.
- Rate limit lưu trong RAM, lấy IP từ `X-Forwarded-For` → người cố tình giả IP vẫn vượt được. Khởi động lại là mất bộ đếm.
- ML chỉ học từ **tên miền**; dữ liệu hợp lệ của PhiUSIIL ít tên miền Việt Nam.
- Danh sách quảng cáo và thương hiệu là danh sách tay, cần cập nhật dần.
- Dashboard chỉ có 1 mã quản trị chung, không có tài khoản riêng.
- Database thử nghiệm và database chạy thật là **một** (Atlas) → chạy thử ở máy cũng ghi vào dashboard.

## 6. Quyết định quan trọng (để trả lời khi bị hỏi "tại sao")

- **Đánh giá trên tên miền, không trên URL đầy đủ:** 100% URL hợp lệ trong PhiUSIIL có dạng
  `https://www.<domain>` không có đường dẫn → train trên URL đầy đủ sẽ đạt ~100% vô nghĩa.
- **ML là "điểm cộng" tối đa 0.3, không tự kết luận lừa đảo:** ML một mình chặn nhầm 6.3%; cộng vào luật
  giữ chặn nhầm 0.6%. Trang bị ML nghi ngờ sẽ được Gemini xem tiếp.
- **ML chạy bằng Python thuần từ file JSON:** không phải cài scikit-learn trên Render (nhẹ, build nhanh).
- **Gemini chỉ gọi khi cần** (có form và điểm < 0.6): tiết kiệm hạn mức, giảm độ trễ.
- **Riêng tư:** chỉ gửi chữ trên trang khi trang có form, và không bao giờ gửi với hộp thư/nhắn tin
  (Gmail, Outlook, Zalo web...); `events` không lưu tên của trang an toàn người dùng tự mở (chỉ đếm);
  email chỉ gửi khi bật công tắc Gmail; tooltip rê chuột chấm hoàn toàn trên máy.
- **Ghim phiên bản thư viện** trong `requirements.txt` để Render build lại không hỏng bất ngờ.
- **Không chặn quảng cáo thông thường** (Google, Facebook) vì người dùng có thể chủ động bấm; chỉ chặn mạng
  popunder/chuyển hướng cưỡng ép.
- **Không chép danh sách ABPVN vào repo** (giấy phép GPLv3) — chỉ học cách phân loại.

## 7. Hướng phát triển (đã nghiên cứu, chưa làm)

1. ~~Google Safe Browsing~~, ~~tên miền na ná~~, ~~mở link rút gọn~~ — **đã làm** (19/10/2026).
2. Mô hình email/tin nhắn tiếng Việt (cần dữ liệu tiếng Việt có nhãn).
4. Đồng bộ blacklist tự động từ OpenPhish / URLhaus; tải bộ lọc ABPVN lúc chạy thay vì chép vào repo.
5. Chế độ chặn popup "nghiêm ngặt" kiểu Popup Blocker (strict): bắt `window.open` để chặn cả mạng quảng cáo lạ.
6. LLM chạy trên máy (Ollama) để email không phải gửi ra ngoài.
7. Nhận diện QR độc từ hình ảnh mã QR (theo nghiên cứu fouadtrad, AUC 0.91).

Tham khảo: Popup Blocker strict (github.com/schomery/popup-blocker), ABPVN (github.com/abpvn/abpvn),
CyberShield (github.com/Jmie-175/CyberShield), phishdetector-fyp (github.com/itxtalal/phishdetector-fyp).

## 8. Kịch bản demo 5 phút

1. Mở trang giả mạo (`extension/test/fake-login.html`) → banner đỏ; rê chuột vào link giả → tooltip.
2. Popup → **Quét mã QR trên màn hình** (mở một ảnh QR trên màn hình trước).
3. Trang web `/` → tab Email → "Điền email mẫu" → 6 lý do.
4. `extension/test/ad-redirect.html` → bấm thử → trang cảnh báo quảng cáo / affiliate.
5. `/about` → trình bày kiến trúc + kết quả đánh giá (dùng thay slide).
6. `/dashboard` → biểu đồ cập nhật; bấm "Chặn" một tên miền → kiểm tra lại thấy nguồn "Danh sách đen".
7. Mở `backend/eval/results/REPORT.md`: luật chính xác nhưng bỏ sót → ML bù → Gemini cho ca khó.

## 9. Lịch sử commit chính

| Commit | Nội dung |
|---|---|
| `f057c16` | Gộp backend + extension vào một repo |
| `b8bf643` | Trỏ extension về Render |
| `6c5fd16` | Đổi sang Gemini flash-lite |
| `c064921` | Luật giả mạo thương hiệu + rate limit |
| `321592c` | Gửi chữ trên trang cho Gemini, hỏi DB song song |
| `18a201c` | Email/tin nhắn, báo sai, trang web, dashboard |
| `dbd1104` | Extension: QR, Gmail, rê chuột, báo sai |
| `66c9588` | Đánh giá PhiUSIIL + mô hình ML |
| `81d9aed` | Dashboard gọn hơn, sửa lỗi nhỏ |
| `63e2461` | Chặn chuyển hướng quảng cáo |
| `9b962e0` | Sửa lỗi regex 2KB, cảnh báo affiliate, "luôn cho phép" |
| `8ef8a71` | File ghi chú này |
| `4b60d46` | Sửa lỗi mã quản trị Unicode, popup hiện kết quả cũ; bảo vệ riêng tư; ghim thư viện |
| `c944c90` | Trang /about + giải thích điểm số (Explainable AI) |
| `376619b` | Tên miền na ná + mở link rút gọn |
| `ae0dbe9`, `42d0c72` | Mô hình học máy email/tin nhắn |
| `19e3036` | Google Safe Browsing + lịch sử cảnh báo trong popup |
