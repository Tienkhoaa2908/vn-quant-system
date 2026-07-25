# Cac quyet dinh kien truc

## QD-0001: Khoi tao theo tung lat doc

Moc 0 chi tao mot lat doc chay duoc: doc tep CSV, kiem tra chat luong, xuat bao cao JSON va tra ma thoat.

## QD-0002: Khong phu thuoc thu vien chay ben ngoai

Phan chay cua Moc 0 chi dung thu vien chuan Python de giam rui ro cai dat va giu bo khung nho.

## QD-0003: Ten du an tu dat dung tieng Viet khong dau

Ten thu muc, tep va ham do du an tu dat dung chu thuong, tieng Viet khong dau va dau gach duoi. Ten bat buoc theo cong cu duoc giu nguyen.

## QD-0004: Du lieu gia lap chi phuc vu kiem thu

Moi du lieu trong `tests/du_lieu` la du lieu gia lap, khong duoc su dung nhu du lieu thi truong that.

## QD-0005: Tach nguon du lieu bang giao dien chung

Luon thu thap chi phu thuoc giao dien `nguon_du_lieu`. Chi bo chuyen doi `nguon_vnstock` duoc phep biet chi tiet Vnstock va KBS. Nguon gia lap thuc hien cung giao dien de kiem thu ngoai tuyen.

## QD-0006: Du lieu tho bat bien va trang thai rieng tung ma

Moi tep tho la JSON dang bang va duoc ghi theo ma lan chay duy nhat. Tep da ton tai khong duoc ghi de. Neu mot ma khong co du lieu, khong tao tep tho gia; chi ghi nhat ky that bai da lam sach va tiep tuc ma khac khi an toan.

## QD-0007: Dinh dang san pham Moc 1

Du lieu tho, nhat ky va bao cao chat luong dung JSON. Du lieu chuan hoa va san sang dung CSV UTF-8 voi bay cot cua du an. Du lieu san sang chi duoc tao khi khong co loi chat luong nghiem trong.

## QD-0008: Khoang ngay bat thuong chi la canh bao

Khi hai quan sat lien tiep cach nhau hon bay ngay lich, he thong ghi canh bao. He thong khong tu dien ngay, khong tao ngay giao dich gia va khong chan tep san sang chi vi canh bao nay.

## QD-0009: Vnstock Community 4.0.4 va nguon KBS

Bo chuyen doi khoa dung Vnstock Community `4.0.4`. Giao dien da duoc xac minh tu ma nguon tag `v4.0.4`: `Market().equity/index(symbol).ohlcv(start, end, interval="1D", source="kbs")` tra cac cot `time`, `open`, `high`, `low`, `close`, `volume`.

Vnstock chuyen gia co phieu ve nghin dong, con chi so giu don vi diem. Giao dien cong khai nay khong co tham so chon gia dieu chinh hay chua dieu chinh, vi vay du an khong truyen tham so suy doan.

## QD-0010: VNINDEX la phan mo rong

FPT, HPG va MBB la ba ma bat buoc. VNINDEX duoc thu rieng. That bai, thieu khoi luong hoac y nghia khoi luong chua ro cua VNINDEX khong chan nghiem thu ba ma bat buoc.

## QD-0011: Vnstock khong la phu thuoc mac dinh cua CI

GitHub Actions chi cai moi truong du an va chay kiem thu ngoai tuyen. Nguoi dung chay Vnstock that bang `uv run --with vnstock==4.0.4`. Cach nay giu CI khong can khoa, khong goi nguon thi truong va khong tai du lieu that.

## QD-0012: Dinh dang tap co phieu theo tung thoi diem

Anh chup thanh vien dung CSV UTF-8 voi bon cot bat buoc:

```text
ngay_hieu_luc,ma,nguon,phien_ban
```

`ngay_hieu_luc` dung `YYYY-MM-DD`; `ma` duoc chuan hoa chu hoa; `nguon` khong duoc rong; `phien_ban` co the rong khi nguon khong cung cap. Cap `ngay_hieu_luc,ma` phai duy nhat. Ket qua thanh vien duoc sap xep theo ma de tai lap.

## QD-0013: Chon anh chup va ngan thanh vien tuong lai

Voi moi ngay danh gia `T`, he thong chi xet anh chup co `ngay_hieu_luc <= T` va chon ngay hieu luc lon nhat. Anh chup sau `T` khong duoc su dung. Neu khong co anh chup hop le, quy trinh dung voi loi ro rang; khong suy doan thanh vien va khong gia mao lich su. Khi xuat mot khoang ngay, quy tac nay duoc ap dung rieng cho ngay cua tung dong dau ra.

## QD-0014: Gia tri giao dich va bo loc thanh khoan

Gia tri giao dich ngay:

```text
gia_tri_giao_dich = gia_dong_cua * khoi_luong
```

Gia co phieu dau vao co don vi nghin dong moi co phieu, vi vay `gia_tri_giao_dich` va trung binh cua no co don vi nghin dong. Trung binh truot tinh rieng tung ma, gom quan sat hien tai va cac quan sat truoc do trong `cua_so_thanh_khoan`; khong dung quan sat tuong lai. Ba tham so bat buoc la `cua_so_thanh_khoan`, `so_quan_sat_toi_thieu` va `nguong_thanh_khoan`. Dat nguong khi trung binh lon hon hoac bang nguong. Khong co nguong san xuat mac dinh.

## QD-0015: MA250

`ma250` la trung binh cong don gian cua dung 250 quan sat gia dong cua gan nhat theo tung ma, co bao gom quan sat hien tai. Truoc quan sat thu 250, `ma250` va `tren_ma250` de trong. Khong backfill, khong dung ngay lich va khong truyen du lieu giua cac ma. `tren_ma250=true` khi gia dong cua lon hon hoac bang MA250.

## QD-0016: Dong luong

Voi cua so bat buoc `N > 0`:

```text
dong_luong_N = gia_dong_cua_t / gia_dong_cua_t_tru_N - 1
```

Tinh rieng tung ma theo thu tu phien quan sat. Can toi thieu `N + 1` quan sat; neu thieu thi de trong va ghi trang thai thieu lich su. Khong dat nguong chon co phieu, khong xep hang va khong chon top-N trong Moc 2.

## QD-0017: Du lieu thieu, dau vao khong hop le va khong nhin truoc

He thong khong tu dien gia, khoi luong, ngay giao dich, thanh vien hoac chi bao. Gia dong cua phai la so huu han duong; khoi luong phai la so nguyen khong am; cap `ma,ngay` phai duy nhat. Dau vao co the chua sap xep, nhung duoc sap xep theo `ma,ngay` truoc khi tinh. Moi cua so chi gom quan sat tai hoac truoc ngay cua dong dang tinh.

## QD-0018: Dinh dang dau ra va gioi han Moc 2

Dau ra chinh la CSV UTF-8 co thu tu cot on dinh va bao cao JSON. CSV co it nhat `ma`, `ngay`, `thuoc_tap_co_phieu`, `gia_tri_giao_dich`, `gia_tri_giao_dich_trung_binh`, `dat_thanh_khoan`, `ma250`, `tren_ma250`, `dong_luong`, `trang_thai_lich_su`, dong thoi kem ngay hieu luc, nguon va phien ban anh chup de truy vet. San pham khong duoc ghi de im lang.

Moc 2 khong tao co du dieu kien dau tu tong hop, khong backtest, khong mo phong giao dich, khong hoc may va khong chia von. Cho den khi co nguon lich su dang tin cay duoc doan 00 phe duyet, viec chong thien lech song sot chi duoc kiem chung o cap giao dien va du lieu gia lap; khong tuyen bo da co lich su thanh vien that.

## QD-0019: So nen Vnstock phai duoc yeu cau ro rang

Bo chuyen doi Vnstock nhan `so_nen` tu ben ngoai, xac thuc la so nguyen duong va truyen nguyen gia tri do thanh tham so `count` cua `ohlcv`. Bo chuyen doi khong hard-code `400`. Cac CLI Vnstock dung mac dinh duoc cong bo la `400`, ghi gia tri yeu cau trong bao cao va khong con am tham phu thuoc gioi han mac dinh 100 dong cua nguon.

Bao cao Moc 2 canh bao rieng khi mot ma co duoi 250 phien, vi chua du de tinh MA250, va khi co duoi 260 phien, vi chua dat nguong xac minh du lieu that. Hai canh bao nay khong tu dong bien du lieu hop le thanh loi.

## QD-0020: Cau hinh lan chay duoc cong bo cung ket qua quy trinh

Cau hinh anh huong den viec lay du lieu, nhu `so_nen_yeu_cau`, phai duoc truyen vao `chay_quy_trinh` truoc khi tao san pham. `ket_qua_lan_chay` la nguon duy nhat tao noi dung `tong_hop.json`; stdout dung cung noi dung va chi bo sung duong dan tep tong hop. Khong duoc chen cau hinh bang cach doc va ghi de tep bat bien sau khi cong bo. Cac khoa cau hinh khong duoc trung voi khoa he thong cua tong hop.

## QD-0021: Dong ho giao dich va lenh DAY Moc 3

Tin hieu ngay T chi duoc tao sau khi close T da biet. Lenh chi duoc khop tai open cua dung phien thi truong ke tiep. Neu ma thieu bar hoac thieu open tai ngay do, lenh DAY het han; khong tim phien xa hon va khong thay open bang gia khac.

## QD-0022: Gia khop, phi, thue va partial fill

Mua dung `open * (1 + truot_gia_bps/10000)`; ban dung `open * (1 - truot_gia_bps/10000)`. Phi tinh theo tung chieu; thue chi ap dung phia ban. MVP khong partial fill va khong participation rate: lenh khop toan bo khoi luong hop le hoac bi tu choi.

## QD-0023: Thu tu xu ly tien mat xac dinh

Trong mot ngay, lenh ban duoc xu ly truoc lenh mua; trong moi chieu sap xep ma tang dan. Lenh mua canh tranh tien mat duoc xu ly theo thu tu nay. Khong duoc lam tien mat am, ban vuot vi the hoac tao vi the am.

## QD-0024: Corporate actions MVP va co so gia

Chia tach/co phieu thuong ap dung truoc giao dich va dinh gia trong ngay hieu luc; so luong va lenh cho nhan he so, gia von chia cho cung he so. Co tuc tien mat chi tang tien vao ngay thanh toan. Neu gia da dieu chinh ma van cung cap corporate actions, lan chay bi tu choi de tranh tinh hai lan.

## QD-0025: Chi so Moc 3

Loi nhuan phien la `NAV_t/NAV_(t-1)-1`; maximum drawdown la `min(NAV_t/peak_t-1)`; Sharpe dung do lech chuan mau va lai phi rui ro quy doi theo phien; turnover la `(tong_mua+tong_ban)/(2*NAV_trung_binh)`. Sharpe tra null khi khong du quan sat hoac phuong sai bang 0.

## QD-0026: Cong bo thu muc ket qua nguyen tu

Chin san pham Moc 3 duoc tao trong thu muc tam, fsync va rename nguyen tu sang thu muc lan chay moi. Khong ghi de. Neu cong bo loi, thu muc tam bi xoa. Thu muc thanh cong va that bai khong duoc tron; manifest ghi Git commit, co so gia, dau vao va SHA-256 san pham.

## QD-0027: Baseline khong phai chien luoc san xuat

Mua-va-giu, can-bang-deu va MA250-dong-luong chi la baseline kiem tra engine. Moc 3 khong ket noi SSI, khong hoc may va khong chia von san xuat.
