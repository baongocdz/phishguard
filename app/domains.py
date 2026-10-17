import hashlib
import ipaddress
from urllib.parse import urlsplit, urlunsplit


def is_ip(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        return False


def candidate_domains(hostname: str) -> list[str]:
    """mail.google.com -> [mail.google.com, google.com].

    Lưu ý: cách cắt đơn giản này chưa xử lý public suffix như co.uk.
    Muốn chính xác hơn, dùng thư viện `tldextract` hoặc Public Suffix List.
    """
    host = hostname.lower().rstrip(".")
    if is_ip(host):
        return [host]
    labels = host.split(".")
    if len(labels) < 2:
        return [host]
    return [".".join(labels[i:]) for i in range(len(labels) - 1)]


def cache_key(url: str) -> str:
    """Băm URL đã chuẩn hóa (bỏ fragment). Chỉ lưu hash, không lưu URL gốc
    vì query string có thể chứa token hoặc thông tin cá nhân."""
    parts = urlsplit(url.strip())
    normalized = urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, "")
    )
    return hashlib.sha256(normalized.encode()).hexdigest()
