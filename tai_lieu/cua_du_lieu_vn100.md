# Cua du lieu VN100 toan phan

## Trang thai

- Base bat buoc ban dau: `e59dca55fa37d88bd0e0f6e8e78bc6d282e4996b`.
- Nhanh: `du_lieu-vn100-toan-phan`.
- Pham vi: chi thu thap, truy vet, kiem tra chat luong va bao cao du lieu.
- Khong chay lai Moc 4, khong huan luyen mo hinh, khong backtest va khong trien khai Moc 5.
- Du lieu that, checkpoint va bao cao van hanh nam ngoai kho ma; thu muc `/du_lieu/` da duoc `.gitignore` loai tru.

## Quan sat van hanh can kiem toan

Lan chay duoc bao ve cho vong kiem toan nay:

```text
ma_lan_chay: vn100_full_windows_20260724_eeca1708
tong_ma: 121
kiem_tra_dat: 45
kiem_tra_that_bai: 76
so_dong_dat_kiem_tra_nghiem_ngat: 81.695
so_dong_nhat_ky_loi: 77
ghi_chu: BCM co hai lan thu
```

Bao cao van hanh cho biet cac blocker hien tai deu la quan he `high/low` voi
`open/close`. Cac con so nay la dau vao cho kiem toan raw; khong duoc tu dong
coi la ket luan da duoc ma nguon xac minh neu chua chay che do kiem toan tren
thu muc raw Windows.

## Ba tang trang thai

Checkpoint schema `2.0` tach ba trang thai:

```text
TAI_NGUON_THAT_BAI
TAI_NGUON_THANH_CONG_KIEM_TRA_DAT
TAI_NGUON_THANH_CONG_KIEM_TRA_THAT_BAI
```

Quy tac:

- Khong co raw duoc bao toan: `TAI_NGUON_THAT_BAI`, `RAW_NOT_PRESERVED`.
- Co raw va SHA-256 tinh lai khop, kiem tra dat:
  `TAI_NGUON_THANH_CONG_KIEM_TRA_DAT`.
- Co raw nhung kiem tra chat luong that bai:
  `TAI_NGUON_THANH_CONG_KIEM_TRA_THAT_BAI`.
- Raw ton tai nhung SHA-256 pipeline/checkpoint khong khop byte hien co van
  duoc giu duong dan va hash thuc te, nhung phai bi ha thanh trang thai kiem tra
  that bai; khong duoc xem la tai nguon that bai va khong duoc sua raw.

Voi moi ma co raw, checkpoint ghi:

- `duong_dan_tho`;
- `ma_sha256` va `ma_sha256_da_kiem_tra_lai`;
- `so_dong_nguon`;
- `ngay_dau_nguon`, `ngay_cuoi_nguon`;
- `ten_cot_nguon`, `kieu_du_lieu_nguon`;
- `nguon`, `phien_ban_nguon`;
- `trang_thai_tai_nguon`, `trang_thai_kiem_tra`, `trang_thai_raw`.

## Bo dieu phoi tai hang loat

Lenh tai:

```bash
PYTHONPATH=src python -m he_thong_dinh_luong.tai_du_lieu_vn100 \
  --danh-sach-ma /duong/dan/danh_sach_hop_ma_vn100.csv \
  --ngay-bat-dau 2016-01-01 \
  --ngay-ket-thuc 2026-07-24 \
  --ngay-kiem-tra 2026-07-24 \
  --thu-muc-du-lieu /duong/dan/ngoai-kho/du_lieu \
  --ma-lan-chay vn100_20260724 \
  --so-nen 5000 \
  --yeu-cau-moi-phut 18
```

Bo dieu phoi tai tung ma qua `nguon_vnstock` va `chay_quy_trinh` cua Moc 1.
Moi lan goi nguon, ke ca retry, deu qua gioi han toc do. Loi mot ma khong chan
ma tiep theo.

Raw do pipeline Moc 1 ghi truoc buoc kiem tra phai duoc bao toan ngay ca khi
kiem tra that bai. Bo dieu phoi khong con nem trang thai validation-fail vao cung
nhom voi loi mang/nguon.

## Tiep tuc sau loi

Checkpoint nam tai:

```text
<thu_muc_du_lieu>/dieu_phoi_vn100/<ma_lan_chay>/checkpoint.json
```

Mot ma chi duoc bo qua khi:

1. checkpoint ghi `TAI_NGUON_THANH_CONG_KIEM_TRA_DAT` hoac trang thai legacy
   `thanh_cong`;
2. tep raw van ton tai;
3. SHA-256 tinh lai khop SHA-256 trong checkpoint.

Ma validation-fail khong duoc bo qua theo cua strict-pass. Neu can tai lai trong
mot vong khac, phai tao run con moi; raw cu khong bi ghi de hoac sua.

## Kiem toan raw ngoai tuyen

Lenh Windows Git Bash cho lan chay hien tai:

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.tai_du_lieu_vn100 \
  --kiem-toan-raw \
  --danh-sach-ma "$UNION_LIST" \
  --thu-muc-tho \
    /c/Users/welcome/Documents/vn-quant-data/vn100_ohlcv/tho \
  --tien-to-lan-chay vn100_full_windows_20260724_eeca1708 \
  --thu-muc-bao-cao \
    /c/Users/welcome/Documents/vn-quant-data/vn100_ohlcv/kiem_toan_eeca1708 \
  --checkpoint \
    /c/Users/welcome/Documents/vn-quant-data/vn100_ohlcv/dieu_phoi_vn100/vn100_full_windows_20260724_eeca1708/checkpoint.json
```

Che do nay:

- chi quet cac thu muc `vn100_full_windows_20260724_eeca1708_*` trong `tho`;
- khong khoi tao `nguon_vnstock`;
- khong goi KBS hoac bat ky mang nao;
- neu mot ma co nhieu lan thu, chon lan co so thu tu lon nhat va van liet ke
  tat ca ung vien trong bao cao;
- tinh lai SHA-256 tren byte raw, khong sua byte;
- ghi `RAW_NOT_PRESERVED` neu khong tim thay raw;
- cap nhat checkpoint bang cach gop provenance, khong xoa `lan_tai` va metadata
  van hanh cu.

## Bao cao bat thuong OHLC

Che do kiem toan tao:

```text
bao_cao_bat_thuong_ohlc.csv
bao_cao_phan_loai_121_ma.json
```

CSV co cac cot toi thieu:

```text
ma,ngay,open,high,low,close,volume,
loai_vi_pham,truong_vi_pham,nguon,phien_ban,raw_sha256
```

Moi vi pham la mot dong rieng. Mot dong raw co nhieu blocker se tao nhieu dong
bao cao, do do van giu duoc ca tap loai loi va tap `(ma, ngay)` duy nhat.

Cac loai loi khoa:

```text
HIGH_LT_OPEN
HIGH_LT_CLOSE
LOW_GT_OPEN
LOW_GT_CLOSE
NON_FINITE
NON_POSITIVE_PRICE
NEGATIVE_VOLUME
DUPLICATE_DATE
```

JSON tong hop ghi:

- tong ma;
- so ma co raw va so raw file thuc te;
- so ma tai nguon thanh cong/khong the xac nhan;
- so ma kiem tra dat/that bai;
- tong so dong raw;
- tong so cap `(ma, ngay)` vi pham duy nhat;
- dem theo loai va theo ma;
- ngay vi pham som nhat/muon nhat;
- so ma chi co blocker high/low trong khi open/close/volume hop le;
- so ma co blocker open/close/volume hoac duplicate date doc lap;
- so ma khong the dung hop dong rut gon;
- doi chieu SHA-256 voi checkpoint van hanh hoac baseline hash tao tu raw.

Hai lan kiem toan cung input phai tao cung byte CSV/JSON. Bao cao khong ghi
thoi gian hien tai de tranh drift khong lien quan.

## De xuat hop dong nghien cuu, chua phe duyet

### Phuong an 1: OHLCV nghiem ngat

Giu hop dong hien tai:

```text
low <= min(open, close)
high >= max(open, close)
open, high, low, close > 0
volume >= 0
khong NaN/Inf
khong trung ngay
```

Uu diem: mot hop dong duy nhat cho feature, kiem soat chat luong va cac use case
OHLC trong tuong lai. Nhuoc diem: chan toan bo ma khi provider co high/low sai
quan he du open/close/volume van co the dung cho pipeline hien tai.

### Phuong an 2: open + close + volume cho nghien cuu Moc 4

Day chi la **de xuat co dieu kien**, khong phai quyet dinh da phe duyet.

Co the xem xet hop dong rieng cho research Moc 4 neu bao cao raw chung minh dong
thoi:

1. open huu han va duong cho toan bo dong can dung;
2. close huu han va duong;
3. volume huu han va khong am;
4. khong trung ngay;
5. moi blocker strict hien tai chi nam o high/low;
6. SHA-256 raw khop, khong correction overlay;
7. high/low chi duoc giu trong raw, khong tao, khong noi suy, khong sua;
8. tai lieu Moc 4 cong bo ro feature/label/regime chi dung close va execution
   adapter chi dung open cua phien tiep theo; engine dinh gia dung close;
9. doi chieu HOSE EOD, corporate actions va price basis van dat cac cua rieng.

Dieu kien may co the kiem tra:

```text
so_ma_co_loi_open_close_volume_doc_lap == 0
so_ma_khong_the_dung_hop_dong_rut_gon == 0
so_ma_raw_ma_bam_khong_khop == 0
```

Neu mot dieu kien khong dat, phuong an 2 khong du dieu kien de de nghi. Ngay ca
khi tat ca dat, van can mot quyet dinh kien truc rieng; vong kiem toan nay khong
tu phe duyet va khong chay Moc 4.

## Kiem thu

`tests/test_tai_du_lieu_vn100.py` chi dung source/runner/raw gia lap, khong goi
mang. Cac truong hop khoa:

- chuan hoa va bo trung danh sach ma;
- gioi han toc do;
- checkpoint phan loai dung ba tang;
- raw va provenance duoc giu khi validation fail;
- resume chi bo qua strict-pass co hash khop;
- bao cao giu dung ngay va gia tri vi pham;
- mot dong co nhieu loai loi;
- duplicate date, non-finite, gia khong duong va volume am;
- tach high/low-only khoi blocker open/close/volume doc lap;
- chon lan thu moi nhat khi mot ma co nhieu raw;
- kiem toan khong khoi tao nguon, khong goi mang;
- hai lan kiem toan cho byte bao cao giong nhau va raw khong doi.

## Cua chap nhan du lieu that

Chua duoc chay Moc 4 cho toi khi dong thoi dat:

1. danh sach VN100 hien tai dung 100 ma, khong trung, co nguon HOSE;
2. lich su thanh phan point-in-time lien tuc tu 2021-01-01;
3. hop raw cua lich su duoc bao toan va hash kiem tra lai khop;
4. hop dong gia duoc phe duyet ro rang, khong tu dong ha tieu chuan;
5. doi chieu mau EOD HOSE dat;
6. kiem ke hanh dong doanh nghiep co bang chung VSDC/HOSE/doanh nghiep;
7. co so gia raw/adjusted duoc xac nhan;
8. manifest va `sha256.txt` khop toan bo san pham.

Neu mot cua khong dat, trang thai phai la `FAIL` va dung truoc Moc 4, huan
luyen va backtest.
