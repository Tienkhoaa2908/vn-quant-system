# Ban giao doan chat dieu phoi

Cap nhat: 2026-07-24

## Vai tro

- Doan `00` la dau moi dieu phoi trung tam.
- Doan `01` da hoan thanh pham vi chuyen mon Moc 1 — du lieu.
- GitHub la nguon su that ve nhanh, commit, PR va CI.
- Chua giao Moc 2 khi nghiem thu sau gop Moc 1 chua hoan tat.

## Trang thai ben vung

### PR so 3

- Trang thai: `closed`, `merged=true`.
- Thoi diem gop: `2026-07-24T16:40:46Z`.
- Nhanh nguon: `m1-du_lieu`.
- Nhanh dich: `main`.
- Dau nhanh da gop: `639afabb406bd839540be9acfbfcf1d6c44f5aa8`.
- Merge commit: `e94d4a340ac734bfabc14f340626c408af33645f`.
- PR co 17 commit, 24 tep thay doi, khong co tep nao duoi `du_lieu/`.

### Moc 1 da co tren main

- giao dien nguon du lieu;
- nguon gia lap ngoai tuyen;
- nguon Vnstock Community 4.0.4 va KBS;
- JSON tho bat bien;
- CSV chuan hoa va san sang;
- bao cao chat luong va nhat ky JSON;
- trang thai doc lap tung ma va retry loi tam thoi;
- CLI tham do va tai that nho;
- kiem thu ngoai tuyen;
- workflow Python 3.12;
- `.gitignore` cho `du_lieu/` va tep nhay cam.

## Bang chung ky thuat

- Tham do that: `20260724T152739494769Z_521d23ce`.
- Tai that nho: `20260724T153953222157Z_5383eaab`.
- FPT, HPG, MBB: deu thanh cong, moi ma 8 dong.
- Python 3.12: `Ran 30 tests in 0.696s`, ket qua `OK`.
- GitHub Actions truoc gop: run so 38, ID `30108780878`, success tren commit `639afabb406bd839540be9acfbfcf1d6c44f5aa8`.

## Trang thai nghiem thu sau gop

Da dat:

1. PR so 3 da gop.
2. Merge commit da dung dau `main` tai thoi diem xac minh.
3. Pham vi tep Moc 1 da xuat hien tren `main`.
4. Khong co du lieu that trong PR.

Chua dong:

1. Chua co ma GitHub Actions run cua su kien `push` tren merge commit `e94d4a340ac734bfabc14f340626c408af33645f` duoc doan `00` xac minh.
2. Ba tep dieu phoi dang duoc cap nhat tren nhanh `cap_nhat-sau-gop-m1` va can duoc gop sau khi CI dat.
3. Chua duoc giao Moc 2.

## Viec nguoi dung can lam

1. Tren GitHub, mo `Actions` va chon run cua workflow `kiem_tra_tu_dong` tren nhanh `main`, commit `e94d4a340ac734bfabc14f340626c408af33645f`.
2. Gui lai run number, run ID, job ID, trang thai va conclusion.
3. Sau khi doan `00` xac minh, gop PR cap nhat tai lieu dieu phoi neu CI cua PR do dat.
4. Dong bo may cuc bo ve `main` moi nhat.
5. Khong xoa nhanh `m1-du_lieu` va khong bat dau Moc 2 truoc thong bao dong nghiem thu.

## Khong duoc lam

- Khong mo hoac trien khai Moc 2.
- Khong dua du lieu that, nhat ky that hoac khoa len GitHub.
- Khong them MA250, momentum, backtest, hoc may hoac chia von trong buoc nghiem thu nay.
