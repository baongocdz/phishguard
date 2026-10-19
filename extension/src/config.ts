/**
 * Địa chỉ backend. Sau khi deploy lên Render, thay bằng URL Render cấp
 * (vd: "https://phishguard-backend.onrender.com") rồi chạy lại `npm run build`.
 * Chạy backend ở máy thì dùng "http://localhost:8000".
 */
export const API_BASE = "https://phishguard-backend-g3w0.onrender.com";

/**
 * Render gói free "ngủ" sau ~15 phút không có request, lần gọi đầu mất 30-50s
 * để thức dậy. Quá thời gian này extension tự dùng bộ luật cục bộ.
 */
export const API_TIMEOUT_MS = 8000;

/**
 * Email (Gmail) không chặn việc đọc thư nên chờ lâu hơn: server có thể hỏi Gemini (tối đa ~10 s) hoặc
 * vừa thức dậy. Chờ 8 s như trang web thì Gemini chậm là extension bỏ cuộc trước khi server trả lời.
 */
export const EMAIL_TIMEOUT_MS = 25000;
