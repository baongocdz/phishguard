# PhishGuard Extension (Tuần 4)

## Chạy thử
1. `npm install`
2. `npm run build`  (hoặc `npm run watch` khi đang sửa code)
3. Mở `chrome://extensions` → bật **Developer mode** → **Load unpacked** → chọn thư mục `dist/`
4. Test: chạy `python -m http.server 5500` ở thư mục dự án, mở
   `http://127.0.0.1:5500/test/fake-login.html` → phải hiện banner đỏ.
   Mở một trang HTTPS bình thường (vd https://wikipedia.org) → không có cảnh báo.
5. Sửa code → `npm run build` → bấm nút Reload của extension → tải lại trang test.

## Cấu trúc
- `src/content.ts`   : thu thập thông tin trang + hiển thị banner cảnh báo (Shadow DOM)
- `src/background.ts`: service worker, nhận dữ liệu, phân tích, lưu kết quả, đặt badge
- `src/analyzer.ts`  : heuristic tạm thời (sắp tới thay bằng gọi Backend FastAPI)
- `src/popup.ts`     : popup hiển thị kết quả của tab hiện tại
