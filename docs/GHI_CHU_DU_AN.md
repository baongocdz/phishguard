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
| Phân tích email đang mở trong Gmail | `src/gmail.ts` | Dựa vào class DOM của Gmail (`h2.hP`, `span.gD`, `div.a3s` **đang hiển thị**) → **Gmail đổi giao diện là hỏng**. Hiện thanh "đang kiểm tra" → xanh (an toàn) / đỏ, cam (nguy hiểm). Popup trên Gmail hiện kết quả **email đang mở** (lưu theo tab). Tắt được trong popup. **Đã thử thật 19/10/2026: chạy** |
| Báo kết quả sai (chặn nhầm / báo lừa đảo) | `src/popup.ts` → `/report` | Hiện trong dashboard để duyệt |
| Chặn chuyển hướng sang mạng quảng cáo popunder | `src/adblock.ts`, `src/ad-domains.json`, `blocked.html` | Dùng `declarativeNetRequest`. Trang cảnh báo: Quay lại / Mở lần này (60 giây) / Luôn cho phép |
| Cảnh báo link affiliate Shopee/Lazada bị ép mở | như trên (`affiliate` trong JSON) | Chỉ khi trang **bên thứ ba** đẩy sang. Ý tưởng từ bộ lọc ABPVN |
| **Chặn tab quảng cáo tự bật của mạng lạ** (không cần danh sách) | `src/popunder.ts`, `src/clicktrack.ts` | Trang tự mở tab sang **web khác** sau cú bấm, mà chỗ bấm không phải link tới đó (nút Play, nền, link trong suốt phủ kín) → trang cảnh báo `pop`. Cả **cửa sổ nhỏ** (popunder cổ điển) — chỉ miễn cửa sổ có đường dẫn đăng nhập/thanh toán (`/oauth`, `/login`, `/checkout`…). **Tab-under** (chính tab bị đổi sang web khác sau cú bấm) → trang cảnh báo `tu` (nút Quay lại về trang trước); xét ở `onCommitted` để biết loại điều hướng (chỉ xét "link", bỏ gõ địa chỉ/bookmark/Back), so với địa chỉ **ban đầu** (trước chuyển hướng server), bỏ qua gửi form. Bỏ qua: cùng web, thương hiệu chính chủ, danh sách "luôn cho phép". `clicktrack.js` chạy mọi khung (cả iframe trình phát), gửi cú bấm cho background |
| Popup báo "Bạn đến trang này qua quảng cáo" | `src/popup.ts` → `adLandingInfo` | `utm_medium` trả tiền (cpm, cpc, display, video, banner…) hoặc mã quảng cáo (gclid, dclid, msclkid…). **Chỉ thông báo, không chặn** — quảng cáo hợp pháp (vd Skoda `utm_medium=cpm`) không nguy hiểm |
| Chặn URL tự khai là quảng cáo bật lên (`utm_medium` chứa `popunder/popup/onclick...`) | `src/adblock.ts` (`POP_MARKER`, trang cảnh báo loại `mk`) | Bắt `yo88.town/?utm_medium=popunder`, `net88.forum/?utm_medium=banner_popup_400x400` — kể cả khi người dùng tự bấm banner (vẫn "Mở lần này" được). Cần `host_permissions` mọi trang (luật redirect) |
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
   Danh sách đen tự cập nhật từ **OpenPhish** (`app/threatfeeds.py`): lúc khởi động nếu quá 12 giờ + nút trên
   dashboard. Chỉ lưu đúng tên máy (abc.pages.dev), không chặn cả nền tảng; mục cũ tự xóa sau 7 ngày.
3b. Google Safe Browsing (`app/safebrowsing.py`) → Google đánh dấu thì lừa đảo ngay.
4. Bộ luật `app/heuristics.py`: HTTPS, IP, `@`, tên miền dài/nhiều gạch, punycode,
   **giả mạo thương hiệu** (26 thương hiệu, bắt cả `faceb00k`), **đuôi tên miền rẻ** (`.top`, `.xyz`...),
   **từ khóa dụ dỗ** (`login`, `xacminh`...), **tên miền na ná** (`vietcornbank`, `netfllx`: ký tự gần
   giống rn→m, vv→w hoặc sai 1–2 ký tự, chỉ với thương hiệu ≥ 6 ký tự).
4b. **Trang cờ bạc / cá cược** (`GAMBLING_WORDS` trong `heuristics.py`): ≥ 2 từ khóa nhà cái trong **tiêu đề**
   (hoặc ≥ 3 trong tiêu đề + chữ trên trang) → +0.35 (đáng ngờ). Đích của quảng cáo trên web phim lậu
   (NET88: "Nhà cái uy tín, Thể thao, Casino, Nổ hũ, Tài xỉu"). Không dùng "đánh bạc" để bài báo không bị bắt nhầm.
   Chỉ có ở backend (extension offline không có tiêu đề/nội dung).
5. Mô hình ML `app/ml.py` cộng tối đa **0.3** điểm (bỏ qua tên miền chính chủ của thương hiệu).
5b. **Cộng đồng báo cáo**: ≥ 3 người KHÁC NHAU báo lừa đảo trong 30 ngày → +0.3 (`apply_community`).
    Người báo lưu bằng mã băm IP (không lưu IP); tên miền tin cậy/chính chủ không bị ảnh hưởng.
5c. **Tuổi tên miền** (`app/domain_age.py`, RDAP): < 14 ngày +0.3, < 90 ngày +0.15. Chỉ tra khi dán link/QR,
    trang có form hoặc đã nghi ngờ. Đuôi `.vn` chưa có RDAP → bỏ qua.
6. Gemini đọc nội dung trang nếu có form và điểm < 0.6. **Kết luận nặng hơn thắng** → trang chèn
   "hãy nói trang này an toàn" không hạ được kết luận của luật.
7. Ghi cache (trừ khi Gemini lỗi) và ghi `events` (chỉ tên miền) cho dashboard.

Ngưỡng: `≥ 0.6` lừa đảo, `≥ 0.3` đáng ngờ, còn lại an toàn.
Mỗi kết quả có `breakdown`: danh sách tín hiệu `{layer, label, points}` với layer là
`list` / `intel` / `rule` / `ml` / `ai` / `link` → hiển thị mục "Vì sao ra kết quả này?".

**Email** (`app/email_rules.py`): tên hiển thị mạo danh thương hiệu, Reply-To khác người gửi,
link hiển thị một tên miền nhưng trỏ tên miền khác, link đáng ngờ, lời lẽ hối thúc / đòi OTP / trúng thưởng.
Sau đó mô hình học máy văn bản (`app/text_ml.py`) cộng tối đa 0.3; tối đa 3 link rút gọn được mở trước.
**Người gửi là tên miền chính chủ + link sạch** (`is_official_and_clean`) → an toàn ngay, không hỏi học máy/Gemini
(Gemini hay đoán thông báo bảo mật thật là đáng ngờ; giả mạo đúng tên miền thì Gmail chặn bằng DMARC).
Khóa cache email gồm cả danh sách link.

### Trang web
- `/` (`app/web/index.html`, `check.js`): 4 tab Link / Mã QR (tải ảnh, Ctrl+V hoặc **quét bằng camera**; giải mã ngay trên trình duyệt) /
  Email (dán hoặc mở `.eml`) / Tin nhắn. Mỗi tab có nút điền dữ liệu mẫu để demo.
- **Giao diện (19/10/2026)**: font Be Vietnam Pro (Google Fonts), icon SVG vẽ sẵn trong `index.html` (`<symbol id="i-...">`,
  `check.js` gọi qua hàm `icon()`), kết quả có vòng điểm + lời khuyên theo mức. `style.css` dùng chung cho cả 3 trang, có chế độ tối.
  Khi đổi giao diện **giữ nguyên id/class** mà `extension/test/web.mjs` dùng (`#result`, `.tab[data-tab]`, `#result .row .ghost`...)
  và chạy lại `npm run web-test`.
- **PWA**: `manifest.webmanifest`, `/sw.js`, icon `icon-*.png` → trên điện thoại "Thêm vào màn hình chính".
  Camera chỉ chạy trên https (Render) hoặc localhost.
- `/about` (`about.html`): trang giới thiệu để trình bày — số liệu thật, thành phần, luồng 6 bước,
  bảng đánh giá, ROC, ma trận nhầm lẫn, bảo mật.
- `/dashboard` (`dashboard.html`, `dashboard.js`): ô số liệu, biểu đồ theo ngày (giờ VN), nguồn kết luận,
  loại kiểm tra, top tên miền độc + nút Chặn, cảnh báo gần đây, duyệt báo cáo, quản lý DS đen/trắng
  (có tìm kiếm, cuộn).

### Đánh giá + ML (`backend/eval/`)
> Bản đầy đủ để viết báo cáo (dataset, làm sạch, bảng kết quả, hạn chế, câu hỏi hội đồng): `docs/DU_LIEU_VA_DANH_GIA.md`.
- Dataset: **PhiUSIIL** (UCI), tải ở https://archive.ics.uci.edu/dataset/967 (không để trong repo, ~57MB).
- Chạy lại: `python -m eval.evaluate <file.csv> --gemini 60` → ghi `eval/results/REPORT.md`, ảnh ROC,
  ma trận nhầm lẫn và **ghi đè** `app/ml_model.json`.
- Kết quả (test 43.808 tên miền):

| | Precision | Recall | Chặn nhầm |
|---|---|---|---|
| Chỉ luật | 0.975 | 0.028 | 0.0% |
| Chỉ ML | 0.882 | 0.758 | 6.3% |
| **Luật + ML** | **0.986** | **0.641** | **0.6%** |

- ML ngang Gemini (0.797 accuracy trên 59 mẫu) nhưng nhanh hơn ~80.000 lần (0,033 ms so với 2.644 ms, theo REPORT.md).
- **Mô hình email/tin nhắn** (`eval/evaluate_text.py`, dữ liệu `ealvaradob/phishing-dataset` file
  `texts.json` trên Hugging Face, Apache-2.0, 20.137 email/SMS tiếng Anh): test 4.028 văn bản —
  Precision 0.974, Recall 0.958, F1 0.966, ROC-AUC 0.996, chặn nhầm 1.6%. Báo cáo: `eval/results/TEXT_REPORT.md`.
  Chỉ cho điểm khi văn bản có ≥ 12 từ mô hình biết **và không phải tiếng Việt có dấu** (≥ 10% số từ mang dấu
  → bỏ qua; xem sự cố mục 4) → tiếng Việt do luật + Gemini lo.

### Test (4 lớp)
| Lớp | Lệnh | Kiểm tra gì | Số kịch bản |
|---|---|---|---|
| Đơn vị backend | `cd backend` → `.venv\Scripts\python -m pytest -q` | Luật, ML, email, cache, admin, rate limit, link rút gọn, Safe Browsing, tuổi tên miền, OpenPhish, cộng đồng, trang cờ bạc, link chính chủ Google, **bộ mẫu báo nhầm 68 ca** (`tests/test_corpus.py`) | 139 |
| Extension trong Chrome thật | `cd extension` → `npm run build` → `npm run e2e` | Banner, tooltip, chặn quảng cáo (danh sách + **tab tự bật của mạng lạ** + URL `utm_medium=…popup…`), affiliate, "Mở lần này", công tắc, popup, **Gmail giả lập** (cả mở thư khác không F5), **tab-under, cửa sổ nhỏ**, không chặn nhầm Back/form, **nút quét QR trong popup** (chạy trên bản sao `dist-e2e/` có quyền `<all_urls>` vì Puppeteer không bấm được icon) | 30 |
| Trang web + dashboard | bật backend ở máy → `npm run web-test -- http://localhost:8000 <mã quản trị>` | 4 tab (tải ảnh QR thật), **camera giả phát video QR**, PWA, báo sai, /about, dashboard, OpenPhish, giao diện 390px | 16 |
| Server thật | `cd backend` → `.venv\Scripts\python -m scripts.smoke [--admin <mã>]` | Gọi đủ chức năng trên Render | 15–16 |

- **CI (GitHub Actions)**: `.github/workflows/ci.yml` tự chạy pytest + typecheck/build mỗi lần push. Xem tab **Actions** trên GitHub.
  Test trình duyệt (e2e, web-test) chỉ chạy ở máy (dùng Chrome for Testing do Puppeteer tải về `~/.cache/puppeteer`).
- Thêm `HEADFUL=1` trước lệnh e2e/web-test để xem trình duyệt chạy.

- Backend: `cd backend && .venv\Scripts\python -m pytest -q` → **139 test**, không cần MongoDB
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
| Thêm thương hiệu / tên miền chính chủ | `BRANDS` (và `USER_CONTENT` nếu là nơi người dùng tự đăng nội dung) trong `backend/app/heuristics.py` → `cd backend` → `.venv\Scripts\python -m scripts.export_brands` (sinh `extension/src/brands.json`) → build extension. Thêm 1 ca vào `tests/test_corpus.py` |
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
| Trang quản trị modem 192.168.1.1 bị báo lừa đảo 0.6 (phát hiện nhờ e2e) | Luật chấm "địa chỉ IP" + "HTTP có mật khẩu" | Địa chỉ mạng nội bộ (10.x, 172.16–31.x, 192.168.x, .local...) coi là an toàn, không gửi lên server. Không dùng `ip.is_private` (gồm cả dải 203.0.113.x). 127.0.0.1 vẫn chấm để demo |
| Kết quả cũ trong cache không có phần giải thích | Cache lưu từ trước khi có `breakdown` | Khóa cache có phiên bản `CACHE_VERSION` trong `service.py` — **tăng lên khi đổi cách chấm** |
| Mã quản trị có dấu tiếng Việt làm backend lỗi 500 | `secrets.compare_digest` không nhận chuỗi Unicode | So bằng bytes (`.encode()`) |
| Popup hiện kết quả của trang trước | Kết quả lưu theo tab, không theo URL | Lưu kèm `url`, popup so với URL tab hiện tại |
| Đổi giao diện xong, trên Render thấy icon thành khối đen to, trang vỡ | Trình duyệt giữ `style.css` cũ (server không gửi `Cache-Control` → trình duyệt tự giữ hàng giờ), ghép với HTML mới | Middleware gửi `Cache-Control: no-cache` cho trang + `/static/*`; link CSS/JS có `?v=N` — **tăng N mỗi khi sửa CSS/JS** (cả trong `sw.js`). Người đã bị thì bấm Ctrl+F5 |
| Thư bảo mật **thật** của Google (tiếng Việt) bị chấm lừa đảo 0.6 | (1) Mô hình email tiếng Anh cắt vụn tiếng Việt có dấu ("chúng" → "ch","ng") thành mảnh trùng từ tiếng Anh, vượt ngưỡng 12 từ → 98%; (2) link `accounts.google.com/...?Email=a@b` bị luật trang web coi là lạ (có `@`, "account"); (3) chữ "Cảnh báo" | `text_ml.is_vietnamese` bỏ qua văn bản ≥10% từ có dấu; link về tên miền chính chủ không xét; người gửi chính chủ + link sạch → bỏ qua từ khóa nội dung. `CACHE_VERSION` → v3. Thư giả (người gửi đúng nhưng link lạ, hoặc tên miền nhái) vẫn bị bắt — có test |
| Web phim lậu vẫn bật tab quảng cáo (yo88.town) | Chỉ chặn theo danh sách 42 mạng quảng cáo; mạng lạ lọt. Trang thử cũng chỉ dùng mạng có trong danh sách nên test không thấy | Thêm phát hiện theo hành vi (`popunder.ts`) + luật `utm_medium=popunder`; test e2e dùng mạng **không** có trong danh sách |
| Trang `/about` không hiện số liệu (online) | `service.py` thiếu import `BRANDS` sau lần sửa danh sách thương hiệu → `/public-stats` lỗi 500; chưa có test cho API này | Sửa import + test `/public-stats`; **CI chạy pyflakes** để bắt tên chưa định nghĩa |
| Tab-under có thể lọt nếu xem trang lâu rồi mới bấm Play | Service worker (MV3) bị Chrome tắt sau ~30 s rảnh → mất địa chỉ trang trước lưu trong bộ nhớ | Hỏi địa chỉ trang hiện tại từ Chrome (`webNavigation.getFrame`) ngay khi điều hướng bắt đầu. **Chưa có test tự động**: `ServiceWorker.stopAllWorkers` qua DevTools làm service worker đang bị Puppeteer gắn vào hỏng luôn, không mô phỏng đúng |
| **Rà soát báo nhầm** (sau ca c.gle): bộ mẫu `tests/test_corpus.py` dựng theo cách các hãng thật gửi thư → **12/21 email hợp lệ và 14/23 tên miền hợp lệ bị báo nhầm** (Facebook gửi từ facebookmail.com, apple.co, shp.ee, lzd.co, ZaloPay, Amazon UK, bản tin qua SendGrid/Mailchimp/SES; zalora.com.vn bị coi là giả Zalo, applebees.com giả Apple...) | (1) Thiếu tên miền chính chủ; (2) tên thương hiệu ngắn khớp mọi cụm bắt đầu bằng nó; (3) link theo dõi của dịch vụ gửi thư; (4) ngược lại, bản sửa c.gle tin cả Google Sites/Docs, GitHub Pages, S3 | Bổ sung tên miền theo nguồn (mục 6); tên ngắn < 6 ký tự chỉ khớp khi đứng một mình / ghép đuôi kẻ gian hay dùng (`BRAND_SUFFIXES`); mở link theo dõi (không vào trang đích), đọc địa chỉ đích nằm trong link (`?q=`, `?u=`, SafeLinks `?url=`, awstrack `/L0/https:...`); `USER_CONTENT` không được tin; học máy bỏ qua `.gov.vn/.edu.vn`. Sau sửa: **68/68 ca đúng**, bắt đủ 13/13 email và 10/10 tên miền lừa đảo; extension (luật trên máy) 32/32 |
| Thư thật của Google "Bạn đã chia sẻ dữ liệu với tdmu.edu.vn" bị báo đáng ngờ 55 | Chữ `tdmu.edu.vn` trỏ tới `c.gle` (link rút gọn của Google) → luật "link hiển thị khác link thật" | Thêm `c.gle`, `g.co`, `goo.gle` vào tên miền chính chủ Google (backend + extension); link về tên miền chính chủ không xét "hiển thị khác thật". Chống lách: link chính chủ mang địa chỉ đích lạ (`google.com/url?q=https://lua-dao…`) thì xét địa chỉ đích (`_real_target`). `CACHE_VERSION` → v5 |
| Gmail đôi khi kẹt ở "đang kiểm tra" | Extension chờ 8 s, server hỏi Gemini có thể tới 10 s | Email chờ 25 s (`EMAIL_TIMEOUT_MS`); thư chính chủ không hỏi Gemini |
| Gmail: mở thư khác (không F5) thì không có thanh kết quả | (1) Chờ DOM "đứng yên" 0,8 s mới kiểm tra, nhưng Gmail đổi DOM gần như liên tục → không bao giờ tới; (2) Gmail giữ DOM thư cũ (ẩn) → `querySelector("h2.hP")` lấy nhầm tiêu đề thư cũ | Kiểm tra tối đa mỗi 0,6 s + khi `hashchange`; chỉ dùng tiêu đề/thanh **đang hiển thị**; kết quả về muộn mà người dùng đã sang thư khác thì không gắn nhầm. Test e2e "mở thư 1, quay ra, mở thư 2" (bản cũ hỏng, bản mới đạt) |
| Bộ nhớ đệm email trả nhầm kết quả | Khóa cache email = người gửi + tiêu đề + nội dung, **thiếu link** → cùng nội dung thay link lừa đảo vẫn nhận "an toàn" đã lưu | Đưa danh sách link vào khóa. (Phát hiện nhờ test "thư chính chủ không hỏi Gemini") |
| Gmail: server đã chấm email (có trong `events`) nhưng không thấy thanh kết quả, popup báo "Mở một email…" | Thanh chèn trên nội dung thư cuối của thread dài → bị cuộn khuất; popup so URL đầy đủ với `sender.url` | Thanh đặt **ngay dưới tiêu đề** (`h2.hP`); gmail.ts gửi kèm `location.href`, popup so theo **mã thư** cuối `#…/<id>`; kiểm tra ngay khi script chạy; bỏ link > 2048 ký tự (server từ chối cả email). Có test e2e Gmail giả lập |
| `chrome://extensions` báo lỗi "Cannot read properties of undefined (reading 'local')" ở `gmail.js` | Bấm Reload extension khi tab Gmail đang mở: script cũ trên tab mất kết nối (`chrome.storage` = undefined) nhưng vẫn chạy theo MutationObserver | `gmail.ts` kiểm tra `chrome.runtime?.id`, mất kết nối thì tự dừng. **Sau khi Reload extension, F5 các tab đang mở** |
| Tự bấm banner quảng cáo trên web phim lậu → vào net88.forum, không cảnh báo | Bấm vào link thật nên phần "tab tự bật" (cố ý) bỏ qua; luật `utm_medium` chỉ khớp đúng `popup` | `POP_MARKER` khớp `…_popup_…`; backend thêm luật trang cờ bạc (banner cam). `CACHE_VERSION` → v4 |
| Quét QR tạo từ me-qr.com ra `q.me-qr.com/...` chứ không phải link đã nhập, chấm "An toàn" | Mã QR **động**: trong mã chỉ có link trung gian, mở ra mới chuyển hướng (302) tới link thật. Không phải lỗi quét; nhưng server không mở link trung gian này | Thêm các dịch vụ QR động (`q.me-qr.com`, `qrco.de`, `qr.codes`, `l.ead.me`, `qr1.be`, `qrfy.io`, `qr.page`) vào `SHORTENERS` → lý do hiện "thực ra dẫn tới <đích thật>" và chấm theo đích thật |
| Code ghi qua lệnh shell bị mất dấu gạch chéo ngược (regex hỏng, ký tự xuống dòng `\n` bị biến thành xuống dòng thật) | Heredoc trong công cụ shell | Sửa bằng công cụ Edit; luôn chạy test **trước** khi commit |

---

## 5. Hạn chế / chưa kiểm chứng

- **Nút quét QR trong popup:** test tự động đã chạy được phần chụp → đọc mã → chấm (bản sao có quyền `<all_urls>`). Phần quyền thật (`activeTab` khi bấm icon) vẫn nên thử tay một lần trước khi demo.
- Chặn tab quảng cáo tự bật: trang **hợp lệ** mở web khác bằng nút (không phải link), vd nút "Thanh toán" sang cổng lạ,
  sẽ bị hiện trang cảnh báo → bấm "Mở lần này" / "Luôn cho phép". Chưa chặn kiểu "tab-under" (tab cũ bị đổi sang quảng cáo).
- Gmail: phụ thuộc class DOM, Gmail đổi giao diện là phải sửa `src/gmail.ts`. Chưa đọc được Reply-To trong Gmail.
- Rate limit lưu trong RAM, lấy IP từ `X-Forwarded-For` → người cố tình giả IP vẫn vượt được. Khởi động lại là mất bộ đếm.
- ML chỉ học từ **tên miền**; dữ liệu hợp lệ của PhiUSIIL ít tên miền Việt Nam.
- Danh sách quảng cáo và thương hiệu là danh sách tay, cần cập nhật dần. Thương hiệu: một nguồn duy nhất
  (`heuristics.py` → `brands.json`), mỗi lần thêm nên thêm 1 ca vào `tests/test_corpus.py`.
- Email có người gửi **giả đúng** tên miền chính chủ + link sạch được tin luôn (dựa vào DMARC của hộp thư).
  Nếu có link tới Google Sites/Docs, GitHub Pages... thì vẫn cho học máy / Gemini xem.
- Link theo dõi của dịch vụ gửi thư chỉ mở khi chữ hiển thị là tên miền (tối đa 3), dừng trước trang đích;
  mở không được thì bỏ qua luật "hiển thị khác thật" cho link đó.
- Dashboard chỉ có 1 mã quản trị chung, không có tài khoản riêng.
- Tuổi tên miền không tra được đuôi `.vn` (VNNIC chưa có RDAP).
- OpenPhish chỉ chặn theo tên máy: trang lừa đảo đặt trên dịch vụ lớn (vd docs.google.com/forms) không chặn được.
- Extension mới thử trên Chrome; Edge/Cốc Cốc cùng nhân Chromium nên về nguyên tắc chạy được — **thử trước khi nói khi bảo vệ**.
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

**Nguồn cho danh sách tên miền chính chủ** (19/10/2026; nhiều nguồn là bài tổng hợp, không phải tài liệu chính
thức của hãng — hãng không công bố danh sách đầy đủ):
- Facebook gửi thông báo từ `facebookmail.com` (cả `em.facebookmail.com`), `fb.com`, `meta.com`: stubgroup.com/blog/how-to-spot-fake-facebook-emails, guard.io/blog/is-support-facebook-com-legit-email.
- Microsoft gửi cảnh báo bảo mật từ `account-security-noreply@accountprotection.microsoft.com`: learn.microsoft.com/en-us/answers/questions/5744207, getmailbird.com/microsoft-security-alert-email-real-or-fake.
- Apple gửi từ `email.apple.com`, `id.apple.com`, `appleid.apple.com` (đều thuộc apple.com): techradar.com (bài "Your Apple ID is not suspended"), nerdschalk.com/is-appleid-apple-com-legit.
- `.gle` là đuôi riêng của Google (c.gle, forms.gle, goo.gle), `g.co` là link rút gọn chính thức: urlert.com/domains/c.gle, whoapi.com/blog/gle-domain, urlert.com/domains/g.co.
- Dịch vụ gửi thư và link theo dõi (SendGrid `ct.sendgrid.net`, Mailchimp `list-manage.com`, Amazon SES `awstrack.me`...): biết từ cấu trúc link trong thư thật.

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
| `4dcfc76` | Sửa lệch tên biến Safe Browsing |
| `ea05148` | Script smoke test + hướng dẫn đổi key |
| `5bee77b` | Test e2e extension; không xét lừa đảo thiết bị mạng nội bộ |
| `47239ca` | Test trang web/dashboard; cache có phiên bản |
| `7acbc9c` | CI GitHub Actions |
| `6d90906` | Tuổi tên miền (RDAP) |
| `d86e616` | Danh sách đen tự cập nhật từ OpenPhish |
| `dcf7417` | Tự học từ báo cáo cộng đồng |
| `89c91fb` | Quét QR bằng camera + PWA |
