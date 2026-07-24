# Đặc tả đề xuất Mốc 3 — Mô phỏng giao dịch và backtest

Cập nhật: 2026-07-25

Trạng thái: **đề xuất để phê duyệt; chưa được phép triển khai mã**.

Mốc nền:

- Mốc 2 đã gộp vào `main` bằng merge commit `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.
- CI sau gộp trên `main` đã thành công ở run số 84.
- Mốc 3 chỉ được mở sau khi đặc tả này được đoạn `00 Điều phối trung tâm` và người dùng phê duyệt.

## 1. Mục tiêu

Xây bộ máy mô phỏng giao dịch có thể tái lập, kiểm toán và kiểm thử, biến tín hiệu hoặc tỷ trọng mục tiêu thành:

- lệnh dự kiến;
- khớp lệnh giả lập;
- tiền mặt và vị thế theo thời gian;
- giá trị danh mục hằng ngày;
- chi phí giao dịch;
- lợi nhuận và chỉ số rủi ro.

Bộ máy phải trả lời được:

1. tín hiệu được biết vào thời điểm nào;
2. lệnh sớm nhất có thể khớp ở phiên nào;
3. giá khớp được tạo từ dữ liệu nào;
4. phí, thuế, trượt giá và lô giao dịch được áp dụng ra sao;
5. tiền mặt, vị thế và NAV thay đổi như thế nào;
6. kết quả có thể tái lập từ dữ liệu, cấu hình và commit nào.

## 2. Nguyên tắc bắt buộc

- Long-only.
- Không short.
- Không margin.
- Không vay tiền hoặc tạo tiền mặt âm.
- Không dùng dữ liệu sau thời điểm ra quyết định.
- Không khớp lệnh trong cùng phiên tạo tín hiệu.
- Không tự điền giá, khối lượng hoặc phiên giao dịch bị thiếu.
- Không thay thế giá mở cửa thiếu bằng giá đóng cửa hoặc giá khác.
- Không ghi đè sản phẩm đã công bố.
- Mọi tham số ảnh hưởng kết quả phải được lưu trong báo cáo lần chạy.
- Kiểm thử CI hoàn toàn ngoại tuyến.
- Không commit dữ liệu thị trường thật dưới `du_lieu/`.

## 3. Ngoài phạm vi Mốc 3

Mốc 3 không triển khai:

- Logistic Regression;
- LightGBM;
- feature store mở rộng;
- walk-forward cho mô hình học máy;
- inverse volatility hoàn chỉnh;
- trần 15% mỗi mã và 25% mỗi ngành ở lớp phân bổ sản xuất;
- tối ưu danh mục;
- margin, short hoặc phái sinh;
- gửi lệnh tới SSI hoặc công ty chứng khoán;
- đọc tài khoản chứng khoán;
- dữ liệu tick, order book hoặc streaming;
- mô hình tác động thị trường cấp vi mô;
- quyền mua và các sự kiện doanh nghiệp phức tạp ngoài phạm vi được nêu dưới đây.

Mốc 3 được phép có các baseline quyết định đơn giản chỉ để kiểm tra bộ máy backtest. Chúng không thay thế Mốc 4 và Mốc 5.

## 4. Đầu vào

### 4.1. Dữ liệu giá và đường cơ sở

Tái sử dụng sản phẩm Mốc 2. Tối thiểu cần các cột:

```text
ma
ngay
gia_mo_cua
gia_cao_nhat
gia_thap_nhat
gia_dong_cua
khoi_luong
thuoc_tap_co_phieu
dat_thanh_khoan
ma250
tren_ma250
dong_luong
```

Yêu cầu:

- cặp `ma,ngay` duy nhất;
- ngày tăng dần sau khi chuẩn hóa;
- giá hữu hạn và dương;
- khối lượng là số nguyên không âm;
- không có dữ liệu tương lai trong trạng thái tập cổ phiếu;
- đơn vị giá phải được ghi rõ;
- cơ sở giá điều chỉnh hoặc không điều chỉnh phải được khai báo rõ.

### 4.2. Tỷ trọng mục tiêu

Giao diện trung tâm của bộ máy là bảng tỷ trọng mục tiêu:

```text
ngay_tin_hieu,ma,ty_trong_muc_tieu,ten_chien_luoc
```

Quy tắc:

- `ngay_tin_hieu` là ngày sau khi giá đóng cửa của phiên đó đã được biết;
- `ty_trong_muc_tieu` nằm trong `[0,1]`;
- tổng tỷ trọng tại mỗi `ngay_tin_hieu` không vượt quá `1`;
- phần còn lại là tiền mặt mục tiêu;
- mã không xuất hiện trong ngày tín hiệu được hiểu theo chế độ cấu hình rõ ràng: giữ nguyên hoặc mục tiêu bằng 0;
- chế độ này phải được lưu trong báo cáo và không có mặc định ẩn.

### 4.3. Cấu hình backtest

Cấu hình phải được lưu bền vững, tối thiểu gồm:

```text
von_ban_dau
phi_mua_bps
phi_ban_bps
thue_ban_bps
truot_gia_bps
kich_thuoc_lo
so_phien_moi_nam
lai_suat_phi_rui_ro
che_do_ma_khong_xuat_hien
cho_phep_ban_le_khi_dong_vi_the
co_so_gia
```

Không hard-code giá trị sản xuất. Kiểm thử được phép dùng giá trị giả lập rõ ràng.

### 4.4. Sự kiện doanh nghiệp

CSV đề xuất:

```text
ma,loai_su_kien,ngay_hieu_luc,ngay_thanh_toan,ty_le,gia_tri_tien_mat,nguon,phien_ban
```

MVP hỗ trợ:

- `chia_tach_hoac_thuong_co_phieu`;
- `co_tuc_tien_mat`.

Yêu cầu:

- chia tách/cổ phiếu thưởng áp dụng trước định giá và giao dịch trong ngày hiệu lực;
- cổ tức tiền mặt chỉ ghi tăng tiền mặt vào ngày thanh toán;
- không dùng ngày công bố để ghi nhận tiền;
- nguồn và phiên bản sự kiện phải truy vết được;
- không áp dụng sự kiện lên chuỗi giá đã điều chỉnh theo cách gây tính hai lần.

Quyền mua, sáp nhập, hủy niêm yết cưỡng bức và hoán đổi cổ phiếu chưa thuộc MVP Mốc 3.

## 5. Đồng hồ mô phỏng và chống nhìn trước

### 5.1. Ngày tín hiệu

Tín hiệu ngày `T` chỉ được tạo sau khi toàn bộ dữ liệu đóng cửa của ngày `T` đã có.

### 5.2. Ngày thực thi

Lệnh từ tín hiệu ngày `T` chỉ được phép khớp sớm nhất tại giá mở cửa của phiên thị trường kế tiếp.

```text
đóng cửa T
→ tạo tín hiệu và tỷ trọng mục tiêu
→ tạo lệnh chờ
→ mở cửa phiên kế tiếp
→ khớp giả lập
```

Không được dùng giá mở cửa, cao, thấp hoặc đóng cửa của phiên thực thi để quyết định tín hiệu ngày `T`.

### 5.3. Giá thực thi

MVP dùng giá mở cửa quan sát được của phiên thực thi.

- Nếu không có bar của mã tại ngày thực thi, lệnh không được khớp.
- Không tự tìm phiên xa hơn trong tương lai cho cùng lệnh.
- Không tự thay bằng giá đóng cửa.
- Lệnh hết hiệu lực trong ngày và được ghi trạng thái từ chối hoặc hết hạn với lý do rõ ràng.

Quy tắc này tạo mô hình lệnh `DAY` đơn giản, bảo thủ và dễ kiểm toán.

## 6. Mô hình giá khớp và chi phí

### 6.1. Trượt giá

Với `truot_gia_bps >= 0`:

```text
gia_khop_mua = gia_mo_cua * (1 + truot_gia_bps / 10000)
gia_khop_ban = gia_mo_cua * (1 - truot_gia_bps / 10000)
```

### 6.2. Phí giao dịch

```text
phi_mua = gia_tri_khop_mua * phi_mua_bps / 10000
phi_ban = gia_tri_khop_ban * phi_ban_bps / 10000
```

### 6.3. Thuế bán

```text
thue_ban = gia_tri_khop_ban * thue_ban_bps / 10000
```

Thuế không áp dụng cho lệnh mua trong MVP.

### 6.4. Tổng tiền

Lệnh mua tiêu thụ:

```text
gia_tri_khop + phi_mua
```

Lệnh bán tạo tiền mặt:

```text
gia_tri_khop - phi_ban - thue_ban
```

Mọi thành phần phải xuất riêng trong sổ khớp lệnh.

## 7. Lô giao dịch và số lượng

- `kich_thuoc_lo` là số nguyên dương bắt buộc trong cấu hình.
- Khối lượng mua được làm tròn xuống theo lô.
- Khối lượng bán không vượt quá khối lượng khả dụng.
- Mặc định mô phỏng lệnh lô chẵn; không tự suy đoán quy tắc thị trường hiện hành.
- Cổ phiếu lẻ phát sinh từ sự kiện doanh nghiệp được giữ trong vị thế.
- Việc bán hết phần lẻ chỉ được phép khi `cho_phep_ban_le_khi_dong_vi_the=true`.
- Chính sách này phải có kiểm thử riêng và được ghi trong báo cáo.

## 8. Tạo lệnh tái cân bằng

Tại mỗi ngày tín hiệu:

1. định giá danh mục bằng giá đóng cửa ngày tín hiệu;
2. tính giá trị mục tiêu theo tỷ trọng;
3. tạo nhu cầu giảm vị thế và tăng vị thế;
4. thực thi lệnh bán trước;
5. tính tiền mặt khả dụng sau bán và chi phí;
6. phân bổ sức mua còn lại theo tỷ lệ nhu cầu mua;
7. làm tròn xuống theo lô;
8. dùng thứ tự mã tăng dần làm tie-break để kết quả xác định hoàn toàn.

Nếu tiền mặt không đủ sau làm tròn và chi phí:

- giảm lệnh mua;
- không cho tiền mặt âm;
- ghi số lượng yêu cầu, số lượng khớp và lý do phần không khớp.

## 9. Giới hạn thanh khoản trong MVP

Mốc 3 bắt buộc dùng cờ `dat_thanh_khoan` để xác định mã có được mở vị thế mới hay không.

- Không mở vị thế mới khi `dat_thanh_khoan=false`.
- Vẫn cho phép giảm hoặc đóng vị thế để quản trị rủi ro, với cảnh báo.
- Không mô phỏng participation rate hoặc partial fill theo khối lượng thị trường trong MVP.
- Giới hạn tỷ lệ tham gia khối lượng có thể được bổ sung sau bằng một quyết định kiến trúc riêng.

Giới hạn này phải được ghi rõ trong báo cáo để không tuyên bố mức độ hiện thực cao hơn khả năng thực tế.

## 10. Sổ cái danh mục

Mỗi ngày mô phỏng phải có:

- tiền mặt đầu ngày;
- tiền mặt cuối ngày;
- số lượng từng mã;
- giá vốn bình quân;
- giá đánh dấu cuối ngày;
- giá trị thị trường;
- lãi/lỗ đã thực hiện;
- lãi/lỗ chưa thực hiện;
- cổ tức tiền mặt nhận được;
- phí;
- thuế;
- chi phí trượt giá;
- NAV cuối ngày.

Không cho phép:

- tiền mặt âm ngoài sai số số thực được định nghĩa;
- vị thế âm;
- bán quá số lượng khả dụng;
- một lệnh được khớp nhiều lần ngoài thiết kế;
- trạng thái không cân bằng giữa sổ lệnh, sổ khớp và sổ vị thế.

## 11. Baseline để kiểm tra bộ máy

Mốc 3 cung cấp các bộ tạo tỷ trọng xác định, không học máy:

### 11.1. Mua và giữ

- mua tại phiên thực thi đầu tiên hợp lệ;
- giữ đến hết kỳ;
- dùng cùng phí, thuế, trượt giá và lô giao dịch với bộ máy chính.

### 11.2. Cân bằng đều

- chọn các mã thuộc tập cổ phiếu và đạt thanh khoản;
- chia đều tỷ trọng tại ngày tái cân bằng;
- lịch tái cân bằng là cấu hình;
- phần không đầu tư giữ bằng tiền mặt.

### 11.3. MA250 và động lượng

- mã phải thuộc tập cổ phiếu;
- phải đạt thanh khoản;
- phải có `tren_ma250=true`;
- phải có động lượng hợp lệ;
- xếp hạng động lượng giảm dần;
- `top_k` là tham số bắt buộc, không có giá trị sản xuất ẩn;
- các mã được chọn chia đều trong baseline Mốc 3.

Baseline này chỉ xác minh toàn bộ luồng từ chỉ báo đến giao dịch. Phân bổ inverse volatility và giới hạn ngành thuộc Mốc 5.

## 12. Chỉ số kết quả

Báo cáo tối thiểu gồm:

- vốn ban đầu;
- NAV cuối;
- lợi nhuận tổng;
- lợi nhuận hằng ngày;
- lợi nhuận năm hóa khi đủ dữ liệu;
- biến động năm hóa;
- Sharpe với `lai_suat_phi_rui_ro` và `so_phien_moi_nam` từ cấu hình;
- maximum drawdown;
- ngày bắt đầu và kết thúc drawdown lớn nhất;
- tổng giá trị mua;
- tổng giá trị bán;
- tổng phí mua;
- tổng phí bán;
- tổng thuế bán;
- tổng chi phí trượt giá;
- turnover;
- số lệnh tạo;
- số lệnh khớp;
- số lệnh từ chối hoặc hết hạn;
- tỷ lệ thời gian giữ tiền mặt;
- cảnh báo và giới hạn dữ liệu.

Không tính chỉ số năm hóa khi số quan sát không đủ; phải trả `null` kèm cảnh báo thay vì tạo con số gây hiểu lầm.

## 13. Đầu ra bất biến

Thư mục đầu ra đề xuất:

```text
<thu_muc_dau_ra>/
├── cau_hinh.json
├── dau_vao.json
├── ty_trong_muc_tieu.csv
├── lenh.csv
├── khop_lenh.csv
├── vi_the_hang_ngay.csv
├── gia_tri_danh_muc.csv
├── su_kien_doanh_nghiep_da_ap_dung.csv
├── bao_cao.json
└── bao_cao_loi.json
```

Một thư mục chỉ được ở một trong hai trạng thái:

- thành công: có sản phẩm thành công, không có `bao_cao_loi.json`;
- thất bại: có `bao_cao_loi.json`, không có sản phẩm thành công một phần.

Yêu cầu công bố:

- ghi tệp tạm;
- kiểm tra nội dung;
- công bố nguyên tử hoặc cơ chế tương đương;
- rollback nếu công bố một phần;
- không ghi đè tệp đã tồn tại;
- xóa tệp tạm khi thất bại.

## 14. Truy vết

`dau_vao.json` hoặc `bao_cao.json` phải ghi:

- mã lần chạy;
- thời điểm chạy UTC;
- commit Git;
- Python version;
- phiên bản gói;
- đường dẫn đầu vào;
- SHA-256 từng tệp đầu vào;
- toàn bộ cấu hình;
- đơn vị giá;
- cơ sở giá điều chỉnh/không điều chỉnh;
- nguồn sự kiện doanh nghiệp;
- ngày đầu và ngày cuối thực tế;
- danh sách mã;
- số dòng đầu vào và đầu ra;
- các giới hạn đã biết.

Không ghi bí mật, token hoặc dữ liệu tài khoản.

## 15. Giao diện dòng lệnh đề xuất

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.mo_phong \
  --duong_co_so <duong_co_so.csv> \
  --ty_trong_muc_tieu <ty_trong_muc_tieu.csv> \
  --cau_hinh <cau_hinh.json> \
  --su_kien_doanh_nghiep <su_kien.csv> \
  --thu_muc_dau_ra <thu_muc_moi>
```

`--su_kien_doanh_nghiep` có thể không bắt buộc trong kiểm thử không có sự kiện, nhưng báo cáo phải ghi rõ không có dữ liệu sự kiện được cung cấp.

Mã thoát:

- `0`: thành công;
- khác `0`: thất bại;
- lỗi phải có báo cáo máy đọc được khi thư mục đầu ra an toàn để ghi.

## 16. Cấu trúc mã đề xuất

```text
src/he_thong_dinh_luong/mo_phong/
├── __init__.py
├── __main__.py
├── dong_lenh.py
├── mo_hinh.py
├── so_cai.py
├── khop_lenh.py
├── chi_phi.py
├── su_kien_doanh_nghiep.py
├── chi_so.py
├── baseline.py
└── bao_cao.py
```

Tên tệp có thể điều chỉnh sau rà soát, nhưng phải tách rõ:

- mô hình dữ liệu;
- mô hình thực thi;
- kế toán danh mục;
- sự kiện doanh nghiệp;
- chỉ số;
- CLI và công bố sản phẩm.

## 17. Kiểm thử bắt buộc

Tất cả kiểm thử ngoại tuyến. Tối thiểu phải có:

1. tín hiệu ngày `T` không thể khớp tại `T`;
2. khớp đúng giá mở cửa `T+1` với trượt giá theo hướng;
3. thiếu giá mở cửa tại ngày thực thi làm lệnh hết hạn, không tự thay giá;
4. phí mua tính đúng;
5. phí và thuế bán tính đúng;
6. lệnh mua không làm tiền mặt âm;
7. lệnh bán không vượt vị thế;
8. làm tròn lô đúng;
9. bán lẻ khi đóng vị thế tuân theo cấu hình;
10. bán trước mua khi tái cân bằng;
11. phân bổ lệnh mua thiếu tiền theo tỷ lệ và tie-break xác định;
12. không mở vị thế mới khi không đạt thanh khoản;
13. chia tách/cổ phiếu thưởng cập nhật số lượng và giá vốn đúng;
14. cổ tức tiền mặt chỉ ghi nhận ngày thanh toán;
15. không tính hai lần corporate action với cơ sở giá đã khai báo;
16. NAV và tiền mặt cân bằng sau từng giao dịch;
17. maximum drawdown đúng trên chuỗi biết trước;
18. turnover và tổng chi phí đúng;
19. chỉ số năm hóa trả `null` khi thiếu dữ liệu;
20. kết quả không phụ thuộc thứ tự dòng đầu vào;
21. chạy lại cùng dữ liệu/cấu hình tạo nội dung nghiệp vụ giống nhau;
22. thư mục thành công không có báo cáo lỗi;
23. thư mục thất bại không có sản phẩm thành công một phần;
24. chạy lại thư mục đã tồn tại không sửa bất kỳ tệp nào;
25. SHA-256 và cấu hình được lưu đúng;
26. toàn bộ kiểm thử Mốc 0–2 tiếp tục đạt.

Phải có ít nhất một kịch bản vàng nhiều ngày, nhiều mã, gồm mua, bán, phí, thuế, trượt giá, lô và corporate action với kết quả tính tay biết trước.

## 18. Tiêu chí nghiệm thu

Mốc 3 chỉ được đề nghị chuyển khỏi draft khi:

- đặc tả đã được phê duyệt trước khi triển khai;
- mã nằm trên nhánh chuyên môn tách từ đúng `main` sau PR điều phối;
- không thay đổi công thức Mốc 2 ngoài sửa lỗi được phê duyệt;
- toàn bộ kiểm thử cũ và mới đạt;
- CI Python 3.12 đạt trên đầu nhánh và merge ref;
- kịch bản vàng đạt;
- chạy thử dữ liệu thật FPT, HPG, MBB thành công;
- báo cáo chứng minh tín hiệu `T` chỉ khớp từ `T+1`;
- chi phí, thuế, trượt giá và lô được thể hiện riêng;
- không có dữ liệu thật dưới `du_lieu/` trong PR;
- tài liệu và ba tệp điều phối được cập nhật;
- giới hạn về lịch sử thành viên thật tiếp tục được công bố.

## 19. Các quyết định cần phê duyệt

Trước khi mở mã Mốc 3, cần phê duyệt toàn bộ các điểm sau:

1. Giá khớp MVP là giá mở cửa phiên kế tiếp cộng/trừ trượt giá.
2. Lệnh là lệnh `DAY`; thiếu bar ngày thực thi thì hết hạn, không tìm phiên xa hơn.
3. Mốc 3 không mô phỏng partial fill hoặc participation rate.
4. Phí, thuế, trượt giá, lot size, số phiên năm và lãi suất phi rủi ro đều là cấu hình, không có giá trị sản xuất ẩn.
5. Baseline MA250/động lượng được phép xếp hạng `top_k` và chia đều chỉ để kiểm tra engine.
6. Mốc 3 hỗ trợ chia tách/cổ phiếu thưởng và cổ tức tiền mặt; quyền mua chưa thuộc MVP.
7. Cơ sở giá điều chỉnh/không điều chỉnh phải khai báo và không được tính corporate action hai lần.
8. Người dùng tiếp tục đặt lệnh thủ công trên SSI; không có API giao dịch.

## 20. Trình tự triển khai sau phê duyệt

Sau khi đặc tả được duyệt:

1. gộp PR điều phối này;
2. xác minh CI trên `main`;
3. tạo nhánh `m3-mo_phong-giao_dich` từ đúng đầu `main`;
4. mở đoạn chuyên môn `03 Mô phỏng giao dịch`;
5. chốt mô hình dữ liệu và kịch bản vàng trước;
6. triển khai sổ cái và mô hình khớp;
7. thêm corporate actions;
8. thêm chỉ số và baseline;
9. thêm CLI và công bố sản phẩm bất biến;
10. chạy kiểm thử và dữ liệu thật;
11. mở PR Mốc 3 ở trạng thái draft;
12. đoạn 00 rà soát trước khi chuyển ready hoặc gộp.
