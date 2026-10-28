"""Định dạng dữ liệu chat và các phép kiểm tra dùng chung cho generate.py / check.py.

Mỗi dòng JSONL là một mẫu:
{
  "id": "knowledge-012-3",            # duy nhất
  "category": "knowledge",            # knowledge | scan | multi_turn | out_of_scope | injection
  "seed": "...", "persona": "...",    # hạt giống đã dùng để sinh (seeds.json)
  "messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...],
  "reviewed": false,                  # chỉ mẫu đã được người duyệt (true) mới vào tập train cuối
  "source": "draft:<model>",          # nguồn sinh; sửa tay xong vẫn giữ để biết gốc
  "flags": []                         # cảnh báo tự động để người duyệt chú ý (số điện thoại, link...)
}
System prompt KHÔNG lưu trong mẫu: lúc fine-tune và lúc chạy cùng thêm system_prompt.txt vào đầu.
"""
import json
import os
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
SYSTEM_PROMPT = (HERE / "system_prompt.txt").read_text(encoding="utf-8").strip()
CATEGORIES = ("knowledge", "scan", "multi_turn", "out_of_scope", "injection")

# Kiến thức bắt buộc đúng: dùng chung khi SINH dữ liệu (generate.py) và khi CHẤM (judge.py).
FACTS = """Kiến thức BẮT BUỘC đúng (lỗi hay gặp, tuyệt đối không viết ngược lại):
- HTTPS / biểu tượng ổ khóa chỉ cho biết kết nối được mã hóa, KHÔNG chứng minh trang thật hay an toàn: hầu hết
  trang lừa đảo đều có HTTPS. Không khuyên người dùng phổ thông "xem chứng chỉ SSL" để đánh giá trang.
- Kiểm tra tên miền: tên miền thật phải KẾT THÚC đúng bằng tên chính thức (vd ...vietcombank.com.vn). "Có chứa"
  tên thương hiệu là KHÔNG đủ: vietcombank.com.vn.xac-minh.top hay shopee-hoantien.vn đều là giả.
- Ngân hàng, cơ quan nhà nước, sàn thương mại điện tử không bao giờ đòi mật khẩu, mã OTP qua điện thoại, tin nhắn
  hay đường link; không yêu cầu chuyển tiền để "xác minh" hay "điều tra".
- Cách an toàn nhất là tự mở ứng dụng chính thức hoặc tự gõ địa chỉ trang, không bấm link được gửi tới.
- Lỡ nhập mật khẩu vào trang lạ: đổi ngay mật khẩu của chính tài khoản đó (từ app/trang chính thức) và ở mọi nơi
  dùng chung mật khẩu, bật xác thực hai lớp, xem lại thiết bị/lần đăng nhập lạ. Chỉ khi là tài khoản ngân hàng/thẻ
  hoặc đã mất tiền mới cần gọi ngân hàng khóa tài khoản và báo công an — đừng khuyên mọi trường hợp như nhau.
- Lỡ đưa OTP hoặc đã chuyển tiền: liên hệ ngay ngân hàng qua kênh chính thức để khóa tài khoản/thẻ, báo cơ quan
  công an nơi gần nhất; cảnh giác với người "hỗ trợ lấy lại tiền" (lừa đảo lần hai).
- Mã QR: phần lớn mã QR thanh toán ở cửa hàng là thật; rủi ro là mã bị DÁN ĐÈ hoặc mã lạ dẫn tới trang đăng nhập.
  Khi quét để chuyển khoản, kiểm tra tên người nhận hiện trong app ngân hàng trước khi xác nhận; không nhập mật
  khẩu/thông tin vào trang mở ra từ mã QR. Không nói chung chung "mã QR nơi công cộng là lừa đảo".
- Đầu tư/việc làm online lừa đảo: KHÔNG khuyên "rút tiền ngay" — app lừa đảo thường không cho rút, hoặc đòi nộp
  thêm "phí/thuế" để rút. Khuyên dừng nạp tiền, không nộp thêm bất kỳ khoản phí nào, lưu bằng chứng, báo công an.
- Không hứa lấy lại được tiền; không khẳng định trang/tin nhắn "an toàn tuyệt đối"."""

MAX_USER_CHARS = 6000       # tin nhắn có thể chứa <scan_result> / <page_data>
MIN_ASSISTANT_CHARS = 40
MAX_ASSISTANT_CHARS = 1800  # ~ 400 từ: trợ lý phải trả lời ngắn gọn

PHONE = re.compile(r"(?<!\d)(?:\+?84|0)(?:[\s.-]?\d){8,10}(?!\d)|(?<!\d)1[89]00[\s.-]?\d{3,4}(?!\d)")
URL = re.compile(r"https?://[^\s)>\]]+|(?<![@\w])(?:[a-z0-9-]+\.)+(?:vn|com|net|org|top|xyz|click|info)\b", re.I)
# Tên miền được phép nhắc trong câu trả lời mà không cần người duyệt kiểm tra lại.
KNOWN_DOMAINS = re.compile(r"(?:^|\.)(?:gov\.vn|vietcombank\.com\.vn|google\.com|facebook\.com|zalo\.me|"
                           r"chongluadao\.vn|tinnhiemmang\.vn|khonggianmang\.vn|haveibeenpwned\.com)$", re.I)
# "https" đứng một mình (không phải phần đầu của đường link https://...) gần chữ "an toàn"...
HTTPS_MYTH = re.compile(r"(\bhttps\b(?!://)|ổ khóa|ổ khoá|chứng chỉ ssl|\bssl\b).{0,60}(an toàn|đáng tin|uy tín|chính thức)",
                        re.I)
AI_SELF = re.compile(r"(mô hình ngôn ngữ|language model|as an ai|tôi là (gemini|chatgpt|claude|qwen)|"
                     r"do google (phát triển|huấn luyện)|openai)", re.I)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def save_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    os.replace(tmp, path)  # ghi đè một lần: tắt máy giữa chừng không làm hỏng file cũ


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def vietnamese_ratio(text: str) -> float:
    """Tỉ lệ chữ cái có dấu tiếng Việt trong các chữ cái (văn bản tiếng Việt có dấu thường > 0.15)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    marked = sum(1 for c in letters if unicodedata.decomposition(c) or c in "đĐ")
    return marked / len(letters)


def problems(rec: dict) -> list[str]:
    """Lỗi định dạng khiến mẫu KHÔNG dùng được (khác với flags chỉ để người duyệt chú ý)."""
    errs = []
    if rec.get("category") not in CATEGORIES:
        errs.append(f"category lạ: {rec.get('category')!r}")
    msgs = rec.get("messages")
    if not isinstance(msgs, list) or len(msgs) < 2:
        return errs + ["messages phải có ít nhất 1 lượt hỏi và 1 lượt trả lời"]
    for i, m in enumerate(msgs):
        want = "user" if i % 2 == 0 else "assistant"
        if not isinstance(m, dict) or m.get("role") != want or not isinstance(m.get("content"), str):
            errs.append(f"tin nhắn {i}: phải là role={want} có content")
            continue
        text = m["content"].strip()
        if not text:
            errs.append(f"tin nhắn {i}: rỗng")
        elif want == "user" and len(text) > MAX_USER_CHARS:
            errs.append(f"tin nhắn {i}: người dùng quá dài ({len(text)} ký tự)")
        elif want == "assistant" and not MIN_ASSISTANT_CHARS <= len(text) <= MAX_ASSISTANT_CHARS:
            errs.append(f"tin nhắn {i}: trả lời dài {len(text)} ký tự (cho phép {MIN_ASSISTANT_CHARS}–{MAX_ASSISTANT_CHARS})")
    if msgs and msgs[-1].get("role") != "assistant":
        errs.append("lượt cuối phải là assistant")
    if rec.get("category") == "multi_turn" and len(msgs) < 4:
        errs.append("multi_turn cần ít nhất 2 lượt hỏi-đáp")
    return errs


def auto_flags(rec: dict) -> list[str]:
    """Điểm cần người duyệt kiểm tra kỹ: số điện thoại, link lạ, câu trả lời không phải tiếng Việt..."""
    flags = []
    for m in rec.get("messages", []):
        if m.get("role") != "assistant":
            continue
        text = m.get("content", "")
        if PHONE.search(text):
            flags.append("có số điện thoại — kiểm tra có bịa không")
        for u in URL.findall(text):
            host = re.sub(r"^https?://", "", u).split("/")[0].lower()
            if not KNOWN_DOMAINS.search(host):
                flags.append(f"có link/tên miền '{host}' — kiểm tra có thật và phù hợp không")
        if vietnamese_ratio(text) < 0.12:
            flags.append("câu trả lời có vẻ không phải tiếng Việt có dấu")
        if HTTPS_MYTH.search(text):
            flags.append("nhắc HTTPS/ổ khóa/SSL cạnh 'an toàn' — kiểm tra không khuyên sai (HTTPS không chứng minh trang thật)")
        if AI_SELF.search(text):
            flags.append("tự nhận là mô hình AI khác — sửa thành PhishGuard")
    return sorted(set(flags))
