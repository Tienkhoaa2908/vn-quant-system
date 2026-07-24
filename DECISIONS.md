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
