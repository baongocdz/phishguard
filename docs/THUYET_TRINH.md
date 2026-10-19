# Bài thuyết trình PhishGuard

> Kịch bản nói khoảng **12–14 phút**, kèm phần chuẩn bị câu hỏi.
> Phần trong ngoặc vuông **[Màn hình: ...]** là chỗ cần mở hoặc bấm khi nói.
> Trước giờ trình bày: mở `<URL Render>/health` cho máy chủ "thức dậy", chạy `scripts.smoke` để chắc mọi thứ xanh,
> mở sẵn các tab: trang Giới thiệu, trang Kiểm tra, Dashboard (đã đăng nhập), trang `fake-login.html`,
> trang `ad-redirect.html`, Gmail, và một ảnh có mã QR. Nếu mạng có vấn đề thì chiếu video demo dự phòng.

---

## 1. Mở đầu (khoảng 1 phút)

Em xin chào thầy cô. Đề tài của em là **PhishGuard – hệ thống phát hiện lừa đảo trực tuyến nhiều lớp**.

Lừa đảo trực tuyến ở Việt Nam bây giờ không chỉ là một trang web giả nữa. Kẻ gian giả trang đăng nhập ngân hàng,
gửi email giả mạo, nhắn tin SMS kiểu "tài khoản của quý khách bị khóa", dán mã QR giả ở bãi xe hay trên hóa đơn,
và cả những trang web cứ bấm vào là bị đẩy sang trang quảng cáo. Người dùng phổ thông rất khó tự phân biệt.

Vì vậy em xây dựng PhishGuard với ba mục tiêu:
- **Bảo vệ ở nhiều kênh**: trang web, mã QR, email và tin nhắn.
- **Phát hiện chính xác mà ít chặn nhầm**, nhờ kết hợp luật, học máy và trí tuệ nhân tạo.
- **Giải thích được**: không chỉ nói "trang này nguy hiểm", mà nói rõ *vì sao*.

---

## 2. Tổng quan hệ thống (khoảng 1 phút)

**[Màn hình: trang Giới thiệu `/about`, phần "Thành phần"]**

Hệ thống có ba thành phần dùng chung một máy chủ:

1. **Tiện ích Chrome (extension)**: tự kiểm tra mọi trang người dùng mở và cảnh báo ngay trên trình duyệt.
2. **Trang web kiểm tra**: ai cũng dùng được, không cần cài đặt. Dán link, tải ảnh QR, dán email hoặc tin nhắn vào là có kết quả.
3. **Trang quản trị (dashboard)**: dành cho người vận hành, để theo dõi thống kê và xử lý báo cáo từ người dùng.

Phía sau là máy chủ viết bằng **FastAPI**, cơ sở dữ liệu **MongoDB Atlas**, AI **Google Gemini**, dữ liệu mối đe dọa
**Google Safe Browsing**, và **hai mô hình học máy do em tự huấn luyện**. Toàn bộ chạy trên Render và có thể truy cập
qua Internet ngay lúc này.

---

## 3. Demo tiện ích Chrome (khoảng 3–4 phút)

### 3.1. Cảnh báo trang giả mạo
**[Màn hình: mở `fake-login.html` → banner đỏ hiện lên]**

Khi em mở một trang đăng nhập giả, extension lập tức hiện **banner đỏ** ở đầu trang và liệt kê lý do: trang không
dùng HTTPS, có ô mật khẩu trên kết nối không an toàn... Biểu tượng của extension cũng hiện dấu chấm than.

**[Màn hình: bấm vào biểu tượng PhishGuard]**

Trong cửa sổ nhỏ (popup), người dùng thấy kết luận, điểm nguy hiểm từ 0 đến 1, và các ô nhỏ cho biết **từng lớp kiểm tra
cộng bao nhiêu điểm**: bộ luật cộng bao nhiêu, học máy bao nhiêu, AI bao nhiêu. Đây là phần **giải thích được** mà em
sẽ nói kỹ hơn ở phần sau.

### 3.2. Cảnh báo trước khi bấm link
**[Màn hình: rê chuột lên một link giả]**

Người dùng chưa cần bấm. Chỉ cần **rê chuột lên một đường link**, nếu link đáng ngờ thì một khung cảnh báo hiện ngay
bên cạnh. Phần này chấm hoàn toàn trên máy người dùng, không gửi gì lên máy chủ, nên vừa nhanh vừa riêng tư.

### 3.3. Quét mã QR trên màn hình (quishing)
**[Màn hình: mở một ảnh có mã QR → popup → "Quét mã QR trên màn hình"]**

Lừa đảo bằng mã QR đang tăng mạnh, vì con người không đọc được mã QR bằng mắt. Khi màn hình có mã QR, ví dụ trong
một email hay một bài đăng, người dùng bấm nút này. Extension chụp màn hình, đọc mã QR, rồi kiểm tra đường link
bên trong trước khi người dùng mở nó bằng điện thoại.

### 3.4. Phân tích email trong Gmail
**[Màn hình: mở một email trong Gmail]**

Khi mở một email trong Gmail, PhishGuard đọc người gửi, tiêu đề, nội dung và các đường link. Nếu là email lừa đảo,
khung cảnh báo hiện ngay trên email. Tính năng này có công tắc tắt trong popup, vì nó gửi nội dung email lên máy chủ
để phân tích. Người dùng được quyền lựa chọn.

### 3.5. Chặn chuyển hướng sang trang quảng cáo
**[Màn hình: `ad-redirect.html` → bấm "Xem phim" → trang cảnh báo cam]**

Nhiều trang phim, truyện lậu cứ bấm vào đâu là bật tab quảng cáo, và những tab đó có thể dẫn tới trang lừa đảo
hay trúng thưởng giả. PhishGuard chặn các **mạng quảng cáo chuyển hướng cưỡng ép** này ngay từ trình duyệt: trang
quảng cáo không bao giờ được tải, thay vào đó là trang cảnh báo của PhishGuard.

**[Màn hình: bấm "Xem tập 2 (mở tab quảng cáo lạ)" → trang cảnh báo "tab quảng cáo tự bật"]**

Danh sách mạng quảng cáo thì không bao giờ đủ, vì mạng mới mọc lên liên tục. Nên PhishGuard còn **nhận ra theo hành vi**:
khi trang tự mở tab sang một trang web khác ngay sau cú bấm của người dùng, mà chỗ được bấm **không phải là link tới
trang đó** (nút Play, nền trang, hay một link trong suốt phủ kín màn hình), thì đó là quảng cáo tự bật. Cách này
chặn được cả mạng quảng cáo chưa ai biết, mà không chặn nhầm link thật hay cửa sổ đăng nhập Google, Facebook.

**[Màn hình: bấm "Đọc chương tiếp" → cảnh báo affiliate]**

Em còn phát hiện một kiểu rất phổ biến ở Việt Nam: trang lậu tự đẩy người dùng sang **link tiếp thị liên kết của
Shopee, Lazada** để ăn hoa hồng. PhishGuard nhận ra và cảnh báo riêng trường hợp này, nhưng không chặn khi người dùng
đang ở chính Shopee hay Lazada. Người dùng có thể chọn "Mở lần này" hoặc "Luôn cho phép tên miền này".

Ngoài ra, popup có **lịch sử cảnh báo** (chỉ lưu trên máy người dùng) và nút **báo kết quả sai** để người dùng góp ý.

---

## 4. Trang web kiểm tra (khoảng 1,5 phút)

**[Màn hình: trang chủ `/`]**

Không phải ai cũng cài extension, nên em làm thêm trang web kiểm tra với bốn mục:

- **Link**: dán đường link bất kỳ. **[Bấm mẫu `secure-vietcombank-xacminh.top`]** Kết quả là lừa đảo, kèm bảng
  "Vì sao ra kết quả này?": tên miền chứa chữ Vietcombank nhưng không phải tên miền thật của Vietcombank, đuôi `.top`
  hay bị lạm dụng, có từ "xacminh" để dụ dỗ, và mô hình học máy cũng đánh giá giống trang lừa đảo.
- **Mã QR**: tải ảnh, dán ảnh bằng Ctrl+V, hoặc **quét trực tiếp bằng camera**.
  **[Màn hình: mở trang trên điện thoại → "Quét bằng camera" → đưa vào một mã QR in trên giấy]**
  Đây là tình huống quishing thật ngoài đời: mã QR dán ở bãi xe, quán ăn, tờ rơi. Hình ảnh được đọc **ngay trên
  điện thoại**, không gửi lên máy chủ. Trang web này còn **cài được như một ứng dụng** trên điện thoại.
- **Email**: dán nội dung hoặc mở file `.eml`. **[Bấm "Điền email mẫu" → Phân tích]** Hệ thống phát hiện người gửi
  xưng là Vietcombank nhưng gửi từ tên miền lạ, địa chỉ trả lời khác người gửi, link hiển thị là trang thật nhưng
  thực ra dẫn tới trang khác, lời lẽ hối thúc và đòi mã OTP.
- **Tin nhắn**: dán tin nhắn SMS hoặc Zalo. Những tin dạng "tài khoản bị khóa, truy cập link để xác minh" bị nhận ra ngay.

Nếu link là **link rút gọn** như bit.ly, hệ thống tự mở ra để xem nó thật sự dẫn tới đâu rồi mới chấm điểm.

---

## 5. Hệ thống quyết định như thế nào (khoảng 2 phút)

**[Màn hình: trang Giới thiệu, phần "Luồng phát hiện"]**

Đây là phần cốt lõi. Mỗi đường link đi qua **sáu lớp**, từ rẻ và nhanh đến đắt và chậm:

1. **Danh sách đen, danh sách trắng**: tên miền đã biết thì kết luận ngay. Danh sách đen **tự cập nhật từ OpenPhish**,
   nguồn dữ liệu về hàng trăm trang lừa đảo đang hoạt động trên thế giới.
2. **Bộ nhớ đệm và Google Safe Browsing**: trang vừa kiểm tra trong 24 giờ thì dùng lại kết quả. Chưa có thì hỏi
   danh sách trang độc hại của Google.
3. **Bộ luật**: em xây dựng các luật nhận diện **giả mạo 26 thương hiệu** phổ biến ở Việt Nam, kể cả kiểu viết lách như
   `faceb00k` (số 0 thay chữ o), `vietcornbank` (chữ r-n thay cho chữ m), hay sai một hai ký tự như `netfllx`; nhận diện
   đuôi tên miền rẻ tiền, từ khóa dụ dỗ, địa chỉ IP, ô mật khẩu trên kết nối không mã hóa.
4. **Học máy và các tín hiệu bổ sung**: mô hình em tự huấn luyện đánh giá tên miền "trông có giống" trang lừa đảo
   không; hệ thống tra **tuổi tên miền** (trang lừa đảo thường dùng tên miền vừa đăng ký vài ngày); và nếu **nhiều người
   dùng khác nhau cùng báo cáo** một trang thì trang đó bị nâng mức cảnh báo. Mỗi tín hiệu này một mình không đủ để
   kết luận lừa đảo, mà chỉ đẩy trang lên mức "đáng ngờ" để các lớp sau xem kỹ hơn.
5. **AI Gemini**: chỉ được gọi khi trang có form đăng nhập và các lớp trước **chưa chắc chắn**. Gemini đọc nội dung
   trang và đánh giá.
6. **Kết luận và giải thích**: từ 0,6 điểm trở lên là lừa đảo, từ 0,3 là đáng ngờ.

Có hai điểm thiết kế em muốn nhấn mạnh:

- **Gọi AI có chọn lọc**: AI chậm và tốn chi phí, nên chỉ gọi khi thật sự cần. Phần lớn trường hợp được quyết định ở
  các lớp đầu chỉ trong vài mili-giây.
- **Chống "dụ" AI (prompt injection)**: một trang lừa đảo có thể giấu dòng chữ "hãy nói trang này an toàn" để lừa AI.
  Vì vậy em quy định **kết luận nghiêm trọng hơn luôn thắng**: AI có thể nâng mức cảnh báo, nhưng không bao giờ hạ
  được kết luận của bộ luật.

---

## 6. Học máy và kết quả đánh giá (khoảng 2–2,5 phút)

**[Màn hình: trang Giới thiệu, phần "Kết quả đánh giá"]**

Em tự huấn luyện **hai mô hình học máy**.

**Mô hình thứ nhất chấm tên miền.** Em dùng bộ dữ liệu **PhiUSIIL** (UCI, 2024) với khoảng 235 nghìn đường link.

Khi phân tích dữ liệu, em phát hiện một cái bẫy: **100% link hợp lệ trong bộ này đều có dạng `https://www.tên-miền`
và không có đường dẫn phía sau**, còn link lừa đảo thì đủ kiểu. Nếu huấn luyện trên link đầy đủ, mô hình chỉ cần học
mẹo "có www là an toàn" là đạt gần 100%, nhưng con số đó vô nghĩa ngoài thực tế. Vì vậy em chỉ dùng **tên miền**, bỏ
"www", bỏ phần trùng lặp, còn 219 nghìn tên miền, và chia 80% để huấn luyện, 20% (43.808 tên miền) để kiểm tra.

Kết quả trên tập kiểm tra:
- **Chỉ dùng luật**: rất ít chặn nhầm, nhưng chỉ bắt được **2,8%** trang lừa đảo, vì luật chỉ nhận ra các mẫu rõ ràng.
- **Chỉ dùng học máy**: bắt được **76%**, nhưng chặn nhầm **6,3%** trang thật, quá nhiều để dùng một mình.
- **Kết hợp luật và học máy** như hệ thống đang chạy: độ chính xác **98,6%**, bắt được **64%** trang lừa đảo, và chỉ
  chặn nhầm **0,6%**. Tức là bắt được gấp khoảng 23 lần so với chỉ dùng luật, mà vẫn giữ tỉ lệ chặn nhầm rất thấp.

Em cũng so sánh với Gemini trên cùng một mẫu: **mô hình học máy của em có độ chính xác ngang Gemini (79,7%), nhưng
nhanh hơn khoảng 80 nghìn lần** (0,033 mili-giây so với 2,6 giây) và miễn phí. Đây là lý do hệ thống dùng học máy để
lọc trước, chỉ hỏi AI ở những ca khó.

**Mô hình thứ hai chấm email và tin nhắn**, huấn luyện trên 20 nghìn email và tin nhắn tiếng Anh. Trên tập kiểm tra
4.028 văn bản, mô hình đạt **F1 0,966, ROC-AUC 0,996**, chỉ chặn nhầm 1,6%. Với tin nhắn tiếng Việt, mô hình tự nhận
biết là không đủ dữ liệu để đánh giá, khi đó bộ luật có từ khóa tiếng Việt và AI Gemini sẽ đảm nhận.

Cả hai mô hình chạy bằng Python thuần trên máy chủ, mất vài mili-giây, không cần GPU.

---

## 7. Trang quản trị (khoảng 1 phút)

**[Màn hình: Dashboard]**

Người vận hành đăng nhập bằng mã quản trị để xem:
- Số lượt kiểm tra, số trang lừa đảo phát hiện, số mã QR và email đã phân tích.
- Biểu đồ theo ngày, tỉ lệ các nguồn kết luận (luật, học máy, AI, danh sách...).
- Những tên miền bị cảnh báo nhiều nhất, có nút **Chặn** để đưa ngay vào danh sách đen.
- **Báo cáo từ người dùng**: duyệt và đưa vào danh sách đen hoặc danh sách tin cậy chỉ với một cú bấm.

**[Màn hình: bấm "Chặn" một tên miền → kiểm tra lại trên trang chủ → nguồn "Danh sách đen"]**

Thay đổi có hiệu lực ngay lập tức. Ngoài ra còn nút **"Cập nhật từ OpenPhish"** để tải danh sách trang lừa đảo mới nhất.

Hệ thống còn **tự học từ cộng đồng**: khi từ ba người dùng khác nhau trở lên cùng báo một trang là lừa đảo, trang đó tự
động bị nâng mức cảnh báo. Để chống phá hoại, em chỉ đếm số người khác nhau (lưu dạng mã băm, không lưu địa chỉ IP), và
trang của các thương hiệu chính chủ hay trong danh sách tin cậy thì không bị ảnh hưởng.

---

## 8. Bảo mật và quyền riêng tư (khoảng 1 phút)

Vì là công cụ bảo mật, bản thân PhishGuard cũng phải an toàn:
- **Không lộ khóa**: các khóa API nằm trong biến môi trường, không có trong mã nguồn.
- **Tối thiểu dữ liệu**: chỉ gửi chữ trên trang khi trang có form đăng nhập; không bao giờ gửi nội dung hộp thư hay
  ứng dụng nhắn tin; thống kê chỉ lưu tên miền của trang đáng ngờ, **không lưu lịch sử duyệt web** của người dùng;
  thiết bị trong mạng nhà (như modem) không bị gửi đi.
- **Chống tấn công**: chống "dụ" AI, giới hạn 30 lượt mỗi phút cho mỗi địa chỉ IP, khi mở link rút gọn thì chặn truy
  cập vào địa chỉ nội bộ của máy chủ, khung cảnh báo được cách ly để trang độc không chèn mã vào được.

---

## 9. Kiểm thử (khoảng 30 giây)

Hệ thống được kiểm thử ở **bốn lớp**:
- **139 bài test** cho máy chủ, trong đó **68 ca mẫu** email/trang hợp lệ và lừa đảo để đo báo nhầm.
- **29 kịch bản** chạy extension trong Chrome thật một cách tự động.
- **16 kịch bản** cho trang web và trang quản trị, gồm cả tải ảnh QR thật, **giả lập camera phát video có mã QR**,
  và kiểm tra giao diện trên điện thoại.
- Một script kiểm tra nhanh toàn bộ máy chủ thật.

Mỗi lần cập nhật mã nguồn, **GitHub tự chạy test** (CI). Nhờ kiểm thử tự động, em đã phát hiện và sửa những lỗi như
trang quản trị modem `192.168.1.1` bị báo nhầm là lừa đảo.

---

## 10. Hạn chế và hướng phát triển (khoảng 30 giây)

Hạn chế:
- Mô hình học máy chủ yếu học từ dữ liệu quốc tế; dữ liệu tên miền và tin nhắn tiếng Việt còn ít.
- Tính năng Gmail phụ thuộc vào giao diện Gmail, khi Gmail thay đổi giao diện thì cần cập nhật.

Hướng phát triển:
- Thu thập dữ liệu lừa đảo tiếng Việt để huấn luyện mô hình riêng.
- Chạy mô hình AI ngay trên máy người dùng để email không phải gửi ra ngoài.
- Nhận diện mã QR độc trực tiếp từ hình ảnh, và mở rộng sang ứng dụng điện thoại.

---

## 11. Kết luận (khoảng 20 giây)

Tóm lại, PhishGuard bảo vệ người dùng ở **bốn kênh** (trang web, mã QR, email, tin nhắn), kết hợp **sáu lớp kiểm tra**
từ luật, học máy đến AI, **giải thích rõ ràng** từng kết luận, và đã được **đánh giá bằng số liệu** trên bộ dữ liệu thật.

Em xin cảm ơn thầy cô đã lắng nghe. Em xin sẵn sàng trả lời câu hỏi.

---

# Chuẩn bị câu hỏi

**Hỏi: Sao không huấn luyện trên đường link đầy đủ cho chính xác hơn?**
Đáp: Vì trong bộ PhiUSIIL, mọi link hợp lệ đều có dạng `https://www.tên-miền` không có đường dẫn. Huấn luyện trên link
đầy đủ thì mô hình học mẹo này và đạt gần 100%, nhưng ra thực tế sẽ sai. Dùng tên miền cho kết quả thấp hơn nhưng trung thực.

**Hỏi: Recall chỉ 64%, vậy 36% trang lừa đảo bị bỏ sót?**
Đáp: 64% là khi **chỉ nhìn tên miền**. Thực tế còn có danh sách đen, Google Safe Browsing, và AI Gemini đọc nội dung các
trang có form đăng nhập, nên tỉ lệ phát hiện khi chạy thật cao hơn. Em chọn ưu tiên **ít chặn nhầm** (0,6%), vì nếu chặn
nhầm nhiều thì người dùng sẽ tắt extension đi.

**Hỏi: Nếu trang lừa đảo dụ được AI nói là an toàn thì sao?**
Đáp: Nội dung trang được bọc trong vùng "dữ liệu không tin cậy" và AI được dặn không làm theo chỉ dẫn bên trong. Quan trọng
hơn, kết luận nghiêm trọng hơn luôn thắng: AI không hạ được mức cảnh báo của bộ luật. Phần này có bài test riêng.

**Hỏi: Tại sao không dùng AI cho tất cả?**
Đáp: AI mất khoảng 1–3 giây mỗi lần và có giới hạn lượt gọi. Mô hình học máy của em đạt độ chính xác ngang Gemini nhưng
nhanh hơn khoảng 80 nghìn lần, nên dùng để lọc trước; AI chỉ dành cho ca khó.

**Hỏi: Hệ thống có thu thập dữ liệu người dùng không?**
Đáp: Chỉ lưu tên miền của trang **đáng ngờ** để thống kê, tự xóa sau 90 ngày. Trang an toàn chỉ được đếm, không lưu là
trang nào. Không lưu đường link đầy đủ, không lưu nội dung email. Lịch sử cảnh báo trong popup chỉ nằm trên máy người dùng.

**Hỏi: Chặn quảng cáo có làm hỏng trang web không?**
Đáp: Em chỉ chặn khoảng 40 mạng quảng cáo chuyên chuyển hướng cưỡng ép, không chặn quảng cáo thông thường như Google
hay Facebook. Người dùng luôn có nút "Mở lần này" hoặc "Luôn cho phép", và có thể tắt hẳn tính năng.

**Hỏi: Dự án khác gì các extension chống lừa đảo đã có?**
Đáp: Các dự án em tham khảo thường chỉ làm một kênh (web hoặc email) và hầu như không công bố số liệu đánh giá. PhishGuard
làm cả bốn kênh, có hai mô hình tự huấn luyện kèm đánh giá trên bộ dữ liệu thật, có phần giải thích, và có các tính năng
riêng cho Việt Nam như nhận diện ngân hàng Việt Nam và link tiếp thị Shopee, Lazada.

**Hỏi: Nếu kẻ xấu rủ nhau báo cáo sai để làm hại một trang thật thì sao?**
Đáp: Hệ thống chỉ đếm số người khác nhau, một người bấm nhiều lần vẫn tính là một. Điểm cộng đồng chỉ đưa trang lên mức
"đáng ngờ", không tự kết luận lừa đảo. Trang trong danh sách tin cậy hay tên miền chính chủ của thương hiệu thì không bị
ảnh hưởng. Mọi báo cáo đều hiện trên dashboard để quản trị viên duyệt.

**Hỏi: Công nghệ sử dụng?**
Đáp: Extension viết bằng TypeScript theo chuẩn Manifest V3. Máy chủ dùng Python FastAPI, cơ sở dữ liệu MongoDB Atlas,
triển khai trên Render. AI là Google Gemini, dữ liệu mối đe dọa là Google Safe Browsing. Học máy dùng scikit-learn để
huấn luyện, Logistic Regression trên n-gram ký tự và n-gram từ. Kiểm thử bằng pytest, Puppeteer và GitHub Actions.
