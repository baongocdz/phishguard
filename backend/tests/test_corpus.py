"""Bộ mẫu báo nhầm / bỏ sót: email và trang HỢP LỆ dựng theo đúng cách các hãng thật gửi (tên miền gửi thư,
link rút gọn riêng, link qua hệ thống theo dõi của dịch vụ gửi thư, Outlook SafeLinks...), cùng các biến thể
LỪA ĐẢO tương ứng (Google Forms/Sites, S3, GitHub Pages, giả mạo người gửi...).

Nguồn tham khảo tên miền: tài liệu và trang hỗ trợ của từng hãng (xem docs/GHI_CHU_DU_AN.md, mục 6).
Chạy riêng: pytest -q tests/test_corpus.py -rA
"""
import pytest

from app.email_rules import is_official_and_clean, run_email_rules
from app.heuristics import run_heuristics
from app.schemas import AnalyzeRequest, EmailLink, EmailRequest


def email(sender, subject, body, links=()):
    return EmailRequest(sender=sender, subject=subject, body=body,
                        links=[EmailLink(text=t, href=h) for t, h in links])


LEGIT_EMAILS = {
    "Facebook gửi từ facebookmail.com": email(
        "Facebook <security@facebookmail.com>", "Mã đăng nhập Facebook của bạn",
        "Ai đó đã cố đăng nhập vào tài khoản của bạn. Nếu không phải bạn, hãy bảo mật tài khoản.",
        [("Bảo mật tài khoản", "https://www.facebook.com/hacked"), ("facebook.com", "https://www.facebook.com/")]),
    "Facebook dẫn link qua l.facebook.com": email(
        "Facebook <notification@facebookmail.com>", "Bạn bè đã chia sẻ một bài viết",
        "Xem bài viết trên VnExpress.",
        [("vnexpress.net", "https://l.facebook.com/l.php?u=https%3A%2F%2Fvnexpress.net%2Fbai-viet&h=AT0")]),
    "Instagram": email(
        "Instagram <security@mail.instagram.com>", "Đăng nhập mới vào Instagram",
        "Chúng tôi nhận thấy lượt đăng nhập mới.", [("instagram.com", "https://www.instagram.com/accounts/")]),
    "Microsoft cảnh báo bảo mật": email(
        "Microsoft account team <account-security-noreply@accountprotection.microsoft.com>",
        "Hoạt động đăng nhập bất thường trên tài khoản Microsoft",
        "Chúng tôi phát hiện hoạt động đăng nhập bất thường. Xem lại hoạt động gần đây.",
        [("https://account.live.com/Activity", "https://account.live.com/Activity"),
         ("aka.ms/security", "https://aka.ms/security")]),
    "Apple biên lai (link apple.co)": email(
        "Apple <no_reply@email.apple.com>", "Biên lai của bạn từ Apple",
        "Cảm ơn bạn đã mua hàng.", [("apple.com/bill", "https://apple.co/3xYz"),
                                     ("Báo cáo sự cố", "https://reportaproblem.apple.com/")]),
    "Google: chia sẻ dữ liệu với tdmu.edu.vn (c.gle)": email(
        "Google <noreply-accounts@google.com>", "Bạn đã chia sẻ một số dữ liệu trong Tài khoản Google với tdmu.edu.vn",
        "Bạn đã dùng tính năng Đăng nhập bằng Google để đăng nhập vào tdmu.edu.vn.",
        [("tdmu.edu.vn", "https://c.gle/ANiao5r"), ("Truy cập Tài khoản Google", "https://myaccount.google.com/")]),
    "Google Ads (link googleadservices)": email(
        "Google Ads <ads-account-noreply@google.com>", "Hóa đơn Google Ads",
        "Xem hóa đơn của bạn.", [("ads.google.com", "https://www.googleadservices.com/pagead/aclk?sa=L")]),
    "YouTube": email(
        "YouTube <no-reply@youtube.com>", "Video mới từ kênh bạn đăng ký",
        "Xem ngay.", [("youtube.com", "https://youtu.be/abc123")]),
    "Shopee (link shp.ee)": email(
        "Shopee <info@mail.shopee.vn>", "Đơn hàng đã được giao",
        "Đơn hàng của bạn đã giao thành công.", [("shopee.vn", "https://shp.ee/abc12")]),
    "Lazada (link lzd.co)": email(
        "Lazada Việt Nam <noreply@lazada.vn>", "Ưu đãi hôm nay",
        "Săn sale cùng Lazada.", [("lazada.vn", "https://lzd.co/xyz")]),
    "ZaloPay": email(
        "ZaloPay <noreply@zalopay.vn>", "Giao dịch thành công",
        "Bạn đã thanh toán thành công.", [("zalopay.vn", "https://zalopay.vn/")]),
    "Amazon Anh (amazon.co.uk)": email(
        "Amazon.co.uk <auto-confirm@amazon.co.uk>", "Your Amazon.co.uk order",
        "Thanks for your order.", [("amazon.co.uk", "https://www.amazon.co.uk/gp/css/order-history")]),
    "Vietcombank thông báo (nhắc không đưa OTP)": email(
        "Vietcombank <vcbdigibank@vietcombank.com.vn>", "Thông báo giao dịch",
        "Vietcombank không bao giờ yêu cầu quý khách cung cấp mã OTP.",
        [("vietcombank.com.vn", "https://portal.vietcombank.com.vn/")]),
    "Bản tin qua SendGrid": email(
        "Tiki <hello@tiki.vn>", "Ưu đãi cuối tuần", "Mua sắm ngay trên Tiki.",
        [("tiki.vn", "https://u1234567.ct.sendgrid.net/ls/click?upn=abcDEF")]),
    "Bản tin qua Mailchimp": email(
        "Công ty ABC <news@abc.vn>", "Bản tin tháng 10", "Tin tức mới nhất.",
        [("www.abc.vn", "https://abc.us1.list-manage.com/track/click?u=1&id=2&e=3")]),
    "Bản tin qua Amazon SES (awstrack)": email(
        "Grab <no-reply@grab.com>", "Khuyến mãi GrabFood", "Đặt món ngay.",
        [("grab.com", "https://abc.r.us-east-1.awstrack.me/L0/https:%2F%2Fwww.grab.com%2Fvn%2F/1/0100abc")]),
    "Thầy cô gửi qua Outlook (SafeLinks)": email(
        "Nguyễn Văn Nam <nam@tdmu.edu.vn>", "Lịch thi học kỳ", "Các em xem lịch thi.",
        [("tdmu.edu.vn", "https://apc01.safelinks.protection.outlook.com/?url=https%3A%2F%2Ftdmu.edu.vn%2Flich-thi&data=05")]),
    "Cô giáo gửi Google Forms khảo sát": email(
        "Trần Thị Lan <lan@tdmu.edu.vn>", "Khảo sát sinh viên", "Các em điền khảo sát giúp cô nhé.",
        [("Link khảo sát", "https://forms.gle/AbCdEf123")]),
    "GitHub": email(
        "GitHub <noreply@github.com>", "[GitHub] A new SSH key was added", "A new public key was added.",
        [("github.com/settings/keys", "https://github.com/settings/keys")]),
    "Netflix (thanh toán)": email(
        "Netflix <info@mailer.netflix.com>", "Cập nhật phương thức thanh toán",
        "Thanh toán gần nhất của bạn không thành công.", [("netflix.com/youraccount", "https://www.netflix.com/YourAccount")]),
    "Google Drive báo có người chia sẻ tài liệu": email(
        "Nguyễn Văn A (qua Google Tài liệu) <drive-shares-dm-noreply@google.com>", "Tài liệu đã được chia sẻ với bạn",
        "Nguyễn Văn A đã chia sẻ tài liệu sau: Báo cáo đồ án.", [("Mở", "https://docs.google.com/document/d/1abc/edit")]),
    "TPBank": email(
        "TPBank <ebank@tpb.vn>", "Thông báo biến động số dư", "Tài khoản của quý khách vừa thay đổi.",
        [("tpb.vn", "https://tpb.vn/")]),
}

PHISH_EMAILS = {
    "Facebook giả, tên miền lạ": email(
        "Facebook <security@facebook-support-team.com>", "Tài khoản của bạn sẽ bị khóa",
        "Xác minh trong 24 giờ.", [("Xác minh", "https://facebook-verify.top/login")]),
    "Giả đúng facebookmail.com nhưng link lạ": email(
        "Facebook <security@facebookmail.com>", "Tài khoản bị khóa",
        "Xác minh ngay.", [("facebook.com/security", "https://fb-security-check.xyz/login")]),
    "Ngân hàng giả dẫn tới Google Forms": email(
        "Vietcombank <thongbao@vcb-notify.com>", "[KHẨN] Xác minh tài khoản",
        "Tài khoản sẽ bị tạm khóa, nhập mật khẩu và mã OTP tại đây.",
        [("vietcombank.com.vn/xac-minh", "https://forms.gle/xyz789")]),
    "Chữ hiển thị trang thật, link tới Google Sites": email(
        "Phòng CNTT <it@tdmu-edu.com>", "Hộp thư sắp đầy",
        "Tài khoản email sẽ bị khóa trong 24 giờ, đăng nhập để xác minh mật khẩu.",
        [("mail.tdmu.edu.vn", "https://sites.google.com/view/tdmu-verify")]),
    "Microsoft giả": email(
        "Microsoft <noreply@microsoft-account-alert.com>", "Mật khẩu sắp hết hạn",
        "Đổi mật khẩu ngay.", [("Đổi mật khẩu", "https://login.microsoftonline.com.verify-session.top/")]),
    "Mượn trang chuyển hướng của Google": email(
        "Google <no-reply@accounts.google.com>", "Cảnh báo bảo mật", "Kiểm tra hoạt động.",
        [("myaccount.google.com", "https://www.google.com/url?q=https://g00gle-verify-account.top/login")]),
    "PayPal giả qua SendGrid": email(
        "PayPal <service@paypal-billing-center.com>", "Your account is limited",
        "Confirm your identity within 24 hours.",
        [("paypal.com", "https://u999.ct.sendgrid.net/ls/click?upn=zzz")]),
    "Zalo giả": email(
        "Zalo <support@zalo-security.net>", "Tài khoản Zalo bị khóa",
        "Đăng nhập để mở khóa.", [("zalo.me", "https://zalo-unlock.xyz/")]),
    "Shopee nhái tên (shoppe)": email(
        "Shopee <khuyenmai@shoppe-vn.com>", "Chúc mừng bạn trúng thưởng",
        "Nhận quà tặng tri ân khách hàng.", [("Nhận quà", "https://shoppe-vn.com/nhanqua")]),
    "Microsoft giả từ tenant onmicrosoft.com": email(
        "Microsoft 365 <admin@contoso-secure.onmicrosoft.com>", "Mật khẩu của bạn sẽ hết hạn hôm nay",
        "Giữ mật khẩu hiện tại tại đây.", [("Giữ mật khẩu", "https://contoso-secure.sharepoint.com/sites/x")]),
    "Tài liệu SharePoint giả, chữ hiển thị microsoft.com": email(
        "Phòng Kế toán <ketoan@cong-ty-abc.vn>", "Hóa đơn tháng 10", "Xem hóa đơn đính kèm.",
        [("microsoft.com/hoa-don", "https://evil-tenant.sharepoint.com/:b:/g/hoadon")]),
    "Giả đúng google.com, link Google Sites ghi accounts.google.com": email(
        "Google <no-reply@google.com>", "Cảnh báo bảo mật", "Đăng nhập để xác minh tài khoản.",
        [("accounts.google.com", "https://sites.google.com/view/google-verify-login")]),
    "Apple giả": email(
        "Apple <no-reply@apple-id-locked.com>", "Your Apple ID has been locked",
        "Verify your account immediately.", [("Verify", "https://appleid-verify.top/")]),
}

LEGIT_HOSTS = [
    "zalora.com.vn", "applebees.com", "appleton.org", "shopeefood.vn", "zalopay.vn", "googleadservices.com",
    "facebookmail.com", "amazon.co.uk", "tdmu.edu.vn", "dichvucong.gov.vn", "forms.gle", "c.gle", "momo.vn",
    "sacombank.com", "mbbank.com.vn", "microsoft365.com", "apple.co", "youtu.be", "shp.ee", "lzd.co",
    "facebookcorewwwi.onion", "amazonses.com", "googleapis.com", "cloud.mongodb.com", "cloud.oracle.com",
    # Báo nhầm tìm được khi rà 134.792 tên miền hợp lệ của PhiUSIIL và các trang hay dùng.
    "finance.gov.au", "vpbank.com.vn", "otpbank.com.ua", "isacombank.com.vn", "blog.google", "ai.google",
    "blog.youtube", "google.org", "googleplay.com", "youtube-nocookie.com", "apple.com.cn", "icloud-content.com",
    "microsoftstore.com",
]
PHISH_HOSTS = [
    "vietcombank-xacminh.top", "faceb00k-login.com", "appleid-verify.com", "zalopay-nhanqua.xyz",
    "momopay-hoantien.com", "shoppe-sale.vn", "paypal.github.io", "paypal-login.s3.amazonaws.com",
    "googlesupport-verify.com", "facebookmail-security.com", "lcloud-verify.com", "blnance.com", "tpbamk.vn",
    "google.verify-account.top",
]


@pytest.mark.parametrize("name", LEGIT_EMAILS)
def test_legit_email_is_not_flagged(name):
    r = run_email_rules(LEGIT_EMAILS[name])
    assert r.verdict == "safe", r.reasons


# Ca chỉ có thể "chưa tin luôn" (luật cho 0 điểm nhưng KHÔNG đi nhánh chính chủ → học máy / Gemini xem tiếp).
NOT_TRUSTED_OUTRIGHT = {"Giả đúng google.com, link Google Sites ghi accounts.google.com"}


@pytest.mark.parametrize("name", PHISH_EMAILS)
def test_phishing_email_is_flagged(name):
    r = run_email_rules(PHISH_EMAILS[name])
    if name in NOT_TRUSTED_OUTRIGHT:
        assert not is_official_and_clean(r), r.reasons
    else:
        assert r.verdict != "safe", r.reasons


def page(host):
    return run_heuristics(AnalyzeRequest(url=f"https://{host}/", hostname=host, protocol="https:"))


@pytest.mark.parametrize("host", LEGIT_HOSTS)
def test_legit_host_is_not_flagged(host):
    r = page(host)
    assert r.verdict == "safe", r.reasons


@pytest.mark.parametrize("host", PHISH_HOSTS)
def test_phishing_host_is_flagged(host):
    r = page(host)
    assert r.verdict != "safe", r.reasons
