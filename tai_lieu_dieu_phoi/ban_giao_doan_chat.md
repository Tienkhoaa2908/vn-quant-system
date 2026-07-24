# Ban giao doan chat dieu phoi

Cap nhat: 2026-07-25

## Vai tro va nen

- Doan `00` la dau moi dieu phoi trung tam.
- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh chinh: `main`.
- Dau `main` khi mo Moc 3: `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- Doan `02` da hoan thanh pham vi Moc 2.
- Doan `03 Mo phong giao dich va backtest` duoc chi dinh phu trach Moc 3.
- Nhanh chuyen mon: `m3-mo_phong-giao_dich`.

## Moc 2 da dong

- PR so 5 da gop bang merge commit `6e8d2ed49c2ef57e43c9f0f2249361b26b838b33`.
- CI sau gop PR so 5: run so 84, `push` vao `main`, thanh cong.
- FPT, HPG va MBB moi ma co 287 phien va 38 dong MA250 trong xac minh that.
- Tinh toan ven CLI, `--so_nen`, truy vet cau hinh va dau ra bat bien da dat.
- Nguon lich su thanh vien that van chua duoc phe duyet.

## Dac ta Moc 3 da duoc phe duyet

Tai lieu chinh thuc:

`tai_lieu/dac_ta_moc_3.md`

Nguoi dung va doan `00` da phe duyet toan bo 8 quyet dinh:

1. tin hieu tai `T`, gia khop MVP tai mo cua phien ke tiep co truot gia;
2. lenh `DAY`, thieu bar ngay thuc thi thi het han;
3. chua mo phong partial fill hay participation rate;
4. phi, thue, truot gia, lot size, so phien nam va lai suat phi rui ro la cau hinh;
5. baseline MA250/dong luong dung `top_k` va chia deu chi de kiem tra engine;
6. corporate actions MVP gom chia tach/co phieu thuong va co tuc tien mat;
7. co so gia phai khai bao va khong tinh su kien hai lan;
8. khong tich hop SSI, nguoi dung tu dat lenh thu cong.

## PR dieu phoi so 6

- Dau nhanh da duyet: `164f49b35f5167cfe21e3d85d32ee3656a1b95e8`.
- CI truoc gop: run so 85, Run ID `30123231682`, job ID `89580559878`, thanh cong.
- Merge commit: `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- Phuong thuc: merge commit; khong squash, khong rebase.
- PR: `closed`, `merged=true`.
- `main` trung khop merge commit.
- CI sau gop: run so 86, Run ID `30123567224`, job `kiem_tra` ID `89581624420`, `completed/success`.
- Tat ca buoc cai Python 3.12, dong bo, compile va kiem thu ngoai tuyen deu dat.
- Canh bao Node.js 20 deprecation khong chan ket qua.

## Nhanh Moc 3

- Ten nhanh: `m3-mo_phong-giao_dich`.
- Base duoc phe duyet: `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- Nhanh duoc tao truc tiep tu base sau khi CI run so 86 dat.
- Cac commit dau tien tren nhanh chi cap nhat tai lieu dieu phoi.
- Chua co module backtest, lenh, khop lenh hay so cai tai thoi diem ban giao.

## Pham vi trien khai

- giao dien ty trong muc tieu;
- lenh, khop lenh, vi the, tien mat va so cai;
- phi mua, phi ban, thue ban, truot gia va lot size;
- long-only, khong short, khong margin, khong tien mat am;
- corporate actions MVP;
- baseline mua-va-giu, can bang deu va MA250/dong_luong;
- NAV, loi nhuan, drawdown, Sharpe, turnover va chi phi;
- CLI, dau ra bat bien, manifest va SHA-256;
- kiem thu ngoai tuyen va kich ban vang.

## Cua kiem soat

- Doan `03` phai mo PR dang draft.
- Khong chuyen Ready va khong gop neu chua co phan quyet cua doan `00`.
- Khong mo Moc 4.
- Khong commit du lieu that, log that hoac khoa.
- Khong tich hop SSI hay API dat lenh.
- Moi bao cao phai ghi base, head, commit, danh sach tep, so kiem thu, Python, uv, CI, merge ref va gioi han.
