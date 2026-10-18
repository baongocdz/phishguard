# PhishGuard Extension (Chrome, Manifest V3)

## Cài đặt
1. `npm install`
2. `npm run build` (hoặc `npm run watch` khi đang sửa code)
3. `chrome://extensions` → bật **Developer mode** → **Load unpacked** → chọn thư mục **`dist/`**
4. Sửa code → `npm run build` → bấm **↻ Reload** của extension → tải lại trang.

Địa chỉ backend nằm ở `src/config.ts` (`API_BASE`).

## Thử nghiệm
Chạy `python -m http.server 5500` trong thư mục `extension`, rồi mở:
- `http://127.0.0.1:5500/test/fake-login.html` → phải hiện banner đỏ.
- `http://127.0.0.1:5500/test/ad-redirect.html` → các nút quảng cáo phải dẫn tới trang cảnh báo,
  link vnexpress mở bình thường.

## Cấu trúc
| File | Vai trò |
|---|---|
| `src/content.ts` | Thu thập thông tin trang, banner cảnh báo (Shadow DOM), tooltip khi rê chuột vào link |
| `src/background.ts` | Service worker: gọi backend, lưu kết quả theo tab, đặt badge, nhận tin nhắn |
| `src/analyzer.ts` | Gọi API; bộ luật cục bộ khi mất mạng (giữ đồng bộ với `backend/app/heuristics.py`) |
| `src/popup.ts` | Popup: kết quả, báo sai, quét mã QR trên màn hình, các công tắc |
| `src/gmail.ts` | Phân tích email đang mở trong Gmail |
| `src/adblock.ts`, `src/ad-domains.json` | Chặn chuyển hướng quảng cáo / cảnh báo link affiliate (declarativeNetRequest) |
| `blocked.html`, `src/blocked.ts` | Trang cảnh báo khi chặn chuyển hướng |
| `build.mjs` | Đóng gói bằng esbuild, sinh quyền host cho danh sách quảng cáo vào `dist/manifest.json` |
