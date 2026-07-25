# Kien truc Moc 3 — Mo phong giao dich va backtest

## Pham vi

Moc 3 bien ty trong muc tieu thanh lenh DAY, khop lenh gia lap, tien mat, vi the, NAV va chi so. Day la lop nghien cuu, khong ket noi SSI, khong doc tai khoan, khong gui lenh, khong hoc may va khong phai lop chia von san xuat.

## Luong xu ly

1. Doc va xac thuc cau hinh, duong co so, ty trong muc tieu va corporate actions.
2. Dung lich phien toan cuc tu cac ngay co bar.
3. Ap dung corporate actions truoc giao dich va dinh gia trong ngay.
4. Thuc thi lenh DAY cua ngay: ban truoc, mua sau; trong moi chieu sap xep ma tang dan.
5. Dinh gia vi the bang gia dong cua cua chinh ngay, khong forward-fill.
6. Ghi so cai, NAV va loi nhuan phien.
7. Sau khi dong cua T da biet, tao lenh cho dung phien thi truong ke tiep.
8. Tinh chi so va cong bo tron bo thu muc ket qua theo cach nguyen tu.

## Tam quyet dinh da phe duyet

1. Tin hieu T khong duoc khop trong T; som nhat la gia mo cua phien ke tiep.
2. Gia mua = open * (1 + slippage_bps/10000); gia ban = open * (1 - slippage_bps/10000).
3. Lenh DAY het han neu ma khong co bar hoac thieu open tai ngay thuc thi; khong tim ngay xa hon va khong thay open bang close.
4. MVP khong partial fill va khong participation rate; lenh hop le khop toan bo hoac bi tu choi.
5. Toan bo tham so san xuat nam trong cau hinh tap trung; khong co mac dinh an cho che do ma vang mat.
6. Baseline mua-va-giu, can-bang-deu, MA250-dong-luong chi kiem tra engine.
7. Corporate actions MVP gom chia tach, co phieu thuong va co tuc tien mat.
8. Dau ra la nghien cuu/danh muc/lenh de xuat; nguoi dung tu dat lenh thu cong.

## Quy tac khoi luong va tien mat

- `gia_tri_muc_tieu = NAV_tham_chieu * ty_trong_muc_tieu`.
- `so_luong_tho = gia_tri_muc_tieu / gia_dong_cua_T`.
- Mua lam tron xuong theo `kich_thuoc_lo`.
- Ban khong vuot vi the; ban le khi dong vi the chi duoc phep neu cau hinh bat.
- Ban duoc xu ly truoc mua. Cac lenh mua canh tranh tien mat duoc xu ly theo ma tang dan, cho ket qua xac dinh; khong partial fill.
- Phi mua/ban tinh tren gia tri khop. Thue chi tinh phia ban.
- Gia von luu theo gia khop, khong gom phi; phi duoc truy vet rieng trong so cai va NAV.

## Corporate actions

- Chia tach/co phieu thuong dung `ty_le` nhu he so nhan so luong; gia von chia cho cung he so. Lenh cho khop trong ngay hieu luc cung duoc nhan he so.
- Co tuc tien mat chi tang tien vao `ngay_thanh_toan` theo so luong dang nam giu.
- Neu `co_so_gia=dieu_chinh` ma van cung cap corporate actions, lan chay bi tu choi de tranh tinh hai lan.
- Ngay su kien phai co trong lich mo phong; he thong khong tu doi ngay.

## Cong thuc chi so

- Loi nhuan phien: `r_t = NAV_t / NAV_(t-1) - 1`; phien dau so voi von ban dau.
- Tong loi nhuan: `NAV_cuoi / NAV_dau - 1`.
- CAGR: `(NAV_cuoi/NAV_dau)^(so_phien_moi_nam/so_quan_sat) - 1` khi du quan sat.
- Maximum drawdown: `min(NAV_t / peak_t - 1)`.
- Sharpe: `mean(r_t-rf_phien) / stdev_mau(r_t) * sqrt(so_phien_moi_nam)`.
- Turnover: `(tong_mua + tong_ban) / (2 * NAV_trung_binh)`.
- Sharpe tra `null` neu khong du quan sat hoac phuong sai bang 0.

## San pham

Moi lan chay cong bo mot thu muc rieng gom:

- `cau_hinh.json`
- `lenh.csv`
- `khop_lenh.csv`
- `vi_the.csv`
- `so_cai.csv`
- `nav.csv`
- `chi_so.json`
- `bao_cao.json`
- `manifest.json`

Noi dung duoc tao trong thu muc tam, fsync, sau do rename nguyen tu. Neu cong bo loi, thu muc tam bi xoa. Thu muc thanh cong khong chua `bao_cao_loi.json`; thu muc that bai chi chua bao cao loi. Manifest ghi Git commit, thoi diem, co so gia, SHA-256 dau vao va SHA-256 cua cac san pham con lai.

## Gioi han

- Khong partial fill, participation rate, quyen mua, sap nhap, hoan doi, huy niem yet cuong buc.
- Khong tu dien bar/gia bi thieu.
- Chua xac minh du lieu that FPT, HPG, MBB trong moi truong connector.
- Khong duoc suy dien hieu qua dau tu tu baseline hoac mot khoang du lieu ngan.
