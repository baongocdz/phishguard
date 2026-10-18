/**
 * Địa chỉ backend. Sau khi deploy lên Render, thay bằng URL Render cấp
 * (vd: "https://phishguard-backend.onrender.com") rồi chạy lại `npm run build`.
 * Chạy backend ở máy thì dùng "http://localhost:8000".
 */
export const API_BASE = "http://localhost:8000";

/**
 * Render gói free "ngủ" sau ~15 phút không có request, lần gọi đầu mất 30-50s
 * để thức dậy. Quá thời gian này extension tự dùng bộ luật cục bộ.
 */
export const API_TIMEOUT_MS = 8000;
