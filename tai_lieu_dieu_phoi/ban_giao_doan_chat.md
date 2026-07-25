# Ban giao doan chat dieu phoi

Cap nhat: 2026-07-25

## Vai tro va nen

- Doan `00` la dau moi dieu phoi trung tam.
- Doan `03 Mo phong giao dich va backtest` phu trach Moc 3.
- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh chinh: `main`.
- Nhanh chuyen mon: `m3-mo_phong-giao_dich`.
- Base da phe duyet: `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- Bon commit dieu phoi dau nhanh duoc giu nguyen, khong reset/squash/sua lich su.

## Nen da xac minh

- PR Mốc 2 số 5 gop bang merge commit `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.
- FPT, HPG, MBB Mốc 2 moi ma 287 phien va 38 dong MA250.
- PR dieu phoi số 6 gop bang merge commit `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- CI sau gop PR số 6: run 86, Run ID `30123567224`, Job ID `89581624420`, thanh cong.
- Dac ta Mốc 3 va tam quyet dinh kien truc da duoc phe duyet.

## PR trien khai Mốc 3

- PR: số 7.
- Tieu de: `M3: mo phong giao dich va backtest`.
- Trang thai bat buoc: draft.
- Base: `main`.
- Head: `m3-mo_phong-giao_dich`.
- Khong chuyen Ready, khong bat auto-merge va khong gop.

## Kien truc da trien khai

- `mo_hinh.py`: cau hinh, thanh gia, ty trong, corporate actions, lenh, khop lenh, vi the, so cai va ket qua.
- `engine.py`: dong ho phien, tao/thuc thi lenh, bat bien tien mat/vi the, corporate actions va NAV.
- `baseline.py`: mua-va-giu, can-bang-deu, MA250/dong-luong.
- `chi_so.py`: loi nhuan, CAGR, drawdown, Sharpe, turnover va chi phi.
- `bao_cao.py`: CSV/JSON, SHA-256, manifest, cong bo nguyen tu, rollback va bao cao loi rieng.
- `dong_lenh.py`: CLI va truy vet dau vao/cau hinh/Git/Python/uv.

## Quy tac nghiep vu chinh

1. Tin hieu sau close T; khop som nhat tai open phien ke tiep.
2. Lenh DAY; thieu bar/open thi het han, khong tim phien xa hon.
3. Mua/bán cong/tru truot gia; phi theo chieu; thue chi phia ban.
4. Khong partial fill; lenh hop le khop toan bo hoac bi tu choi.
5. Ban truoc mua; trong moi chieu sap xep ma tang dan.
6. Long-only, khong margin, khong tien mat am, khong ban vuot vi the.
7. Chia tach/co phieu thuong truoc giao dich/dinh gia; co tuc tien mat tai ngay thanh toan.
8. Gia dieu chinh kem corporate actions bi tu choi de tranh tinh hai lan.

## San pham

Mot lan chay thanh cong tao dung:

- `cau_hinh.json`;
- `lenh.csv`;
- `khop_lenh.csv`;
- `vi_the.csv`;
- `so_cai.csv`;
- `nav.csv`;
- `chi_so.json`;
- `bao_cao.json`;
- `manifest.json`.

Thu muc thanh cong va that bai khong tron. Khong ghi de; cong bo qua thu muc tam va rename nguyen tu; rollback neu loi.

## Kiem thu

- Tep `tests/test_mo_phong.py` gom 17 phuong thuc nhom, bao phu 33 kich ban bat buoc cua dac ta.
- Co kich ban vang tinh tay voi von, open, truot gia, khoi luong, phi, thue, tien, vi the, NAV va loi nhuan.
- Workflow van chay toan bo test Mốc 0–2, compileall va Python 3.12 ngoai tuyen.
- CI head cuoi phai duoc lay sau commit ban giao nay va ghi vao PR/bao cao.

## Ket qua du lieu that

Chua chay Mốc 3 tren FPT, HPG, MBB trong vong connector nay vi khong co working tree/du lieu that/Vnstock runtime duoc mount. Day la cua nghiem thu con mo; khong duoc tuyen bo hieu qua dau tu.

## Gioi han va cua kiem soat

- Nguon lich su thanh vien that chua duoc phe duyet.
- Khong partial fill/participation rate; chua co quyen mua, sap nhap, hoan doi va huy niem yet cuong buc.
- Khong tich hop SSI, khong doc tai khoan va khong gui lenh.
- Khong Logistic Regression, LightGBM hay chia von san xuat.
- Khong mo Mốc 4.
- Chi doan 00 duoc phep yeu cau sua, chuyen Ready, cho phep gop va mo mốc tiep theo.
