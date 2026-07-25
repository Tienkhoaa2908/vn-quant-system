# Kiem thu runner dau-cuoi Moc 4

Tai lieu nay ghi pham vi kiem chung ngoai tuyen cua `chay_nghien_cuu_moc_4`.

## Luong duoc kiem chung

Runner doc va xac thuc cac tep cuc bo, ap dung universe/metadata point-in-time, tong hop coverage, tinh feature cuoi thang theo lich benchmark chinh thuc, tao nhan T+H, lap walk-forward fold, chay momentum baseline va Logistic Regression, xep hang, tao target weight OOS, goi engine Moc 3 mot lan cho moi chien luoc, tinh metric va cong bo nguyen tu 17 tep san pham.

## Kich ban vang

Fixture vang xac minh:

- du dung 17 tep san pham;
- fold test khong chong lan;
- prediction test duy nhat theo `(ngay,ma)`;
- ranking va target weight xac dinh;
- ma roi top-K co target 0;
- ngay khong co ma hop le van tai can bang ve tien mat;
- lenh khop tai open dung T+1 qua engine Moc 3;
- NAV la mot chuoi OOS lien tuc, von chi khoi tao mot lan;
- manifest co SHA-256 dau vao/san pham va metadata bat buoc;
- hai lan chay cung fixture va thoi diem UTC cho cung noi dung san pham.

## Gioi han

Chi fixture ngoai tuyen duoc su dung. Tier A va Tier B chua chay. Nguon VN100, VNINDEX, lich benchmark, co so gia va corporate actions that chua duoc phe duyet. Ket qua khong duoc dien giai nhu bang chung hieu qua chien luoc. Khong co LightGBM, chia von san xuat, SSI hoac Moc 5.
