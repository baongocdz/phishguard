import hashlib
import ipaddress
from urllib.parse import urlsplit, urlunsplit


def is_ip(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        return False


LAN_SUFFIXES = (".local", ".lan", ".home", ".home.arpa", ".internal")
# Chỉ các dải mạng nội bộ thật (không dùng ip.is_private vì nó gồm cả dải dành cho
# tài liệu như 203.0.113.0/24). Giữ giống isLanHost trong extension/src/analyzer.ts.
LAN_NETWORKS = [ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "fc00::/7", "fe80::/10",
)]


def is_lan_host(hostname: str) -> bool:
    """Thiết bị trong mạng nội bộ (modem 192.168.1.1, NAS, máy in...): không xét lừa đảo.
    127.0.0.1 KHÔNG tính để trang demo chạy ở máy vẫn được chấm như thường."""
    host = hostname.lower().rstrip(".")
    if host.endswith(LAN_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(ip in net for net in LAN_NETWORKS if ip.version == net.version)


def registrable_domain(hostname: str) -> str:
    """Tên miền gốc đã đăng ký: mail.paypal.com -> paypal.com, a.x.com.vn -> x.com.vn.
    Cách cắt đơn giản (không dùng Public Suffix List), đủ cho các đuôi phổ biến."""
    parts = hostname.lower().rstrip(".").split(".")
    if len(parts) >= 3 and parts[-2] in {"com", "net", "org", "edu", "gov", "co", "ac"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


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
