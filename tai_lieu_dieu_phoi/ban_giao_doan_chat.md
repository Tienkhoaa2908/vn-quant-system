# Ban giao doan chat dieu phoi

Cap nhat: 2026-07-24

## Vai tro

- Doan `00` la dau moi dieu phoi trung tam.
- Doan `01` da hoan thanh pham vi chuyen mon Moc 1 — du lieu.
- GitHub la nguon su that ve nhanh, commit, PR va CI.
- Moc 2 chua duoc giao cho den khi PR so 4 duoc gop va `main` duoc xac minh lan cuoi.

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

## Nghiệm thu sau gop

- Su kien CI: `push` tren nhanh `main`.
- Commit duoc kiem tra: `e94d4a340ac734bfabc14f340626c408af33645f`.
- GitHub Actions run so 39, ID `30110023878`: `completed`, `success`.
- Job `kiem_tra`, ID `89536932151`: `completed`, `success`.
- Tat ca buoc lay ma nguon, cai uv, cai Python, dong bo, kiem tra cu phap, kiem thu ngoai tuyen va don dep deu dat.
- Canh bao Node.js 20 deprecated duoc GitHub chay tren Node.js 24; khong chan nghiem thu.

## Phan quyet

**MOC 1 DA HOAN TAT NGHIEM THU SAU GOP.**

Da dat:

1. PR so 3 da gop.
2. Merge commit da duoc xac minh tren `main`.
3. Pham vi Moc 1 da xuat hien day du tren `main`.
4. Khong co du lieu that trong Git.
5. CI tren dau nhanh truoc gop dat.
6. CI tren merge commit cua `main` dat.

## PR so 4

- Muc tieu: ghi ben vung ket qua nghiem thu sau gop trong ba tep dieu phoi.
- Nhanh: `cap_nhat-sau-gop-m1` vao `main`.
- Khong sua ma Python, workflow, kiem thu hoac du lieu.
- Can CI dat tren dau nhanh moi nhat truoc khi nguoi dung gop.

## Viec nguoi dung can lam

1. Cho CI moi nhat cua PR so 4 hoan tat.
2. Neu CI dat, gop PR so 4 bang `Create a merge commit`.
3. Khong xoa nhanh `m1-du_lieu` hoac `cap_nhat-sau-gop-m1` truoc khi doan `00` xac minh `main` lan cuoi.
4. Dong bo may cuc bo ve `main` moi nhat sau khi PR so 4 duoc gop.
5. Bao lai doan `00` de xac minh va nhan prompt giao viec Moc 2.

## Khong duoc lam

- Khong mo hoac trien khai Moc 2 truoc khi PR so 4 duoc gop va xac minh.
- Khong dua du lieu that, nhat ky that hoac khoa len GitHub.
- Khong them MA250, momentum, backtest, hoc may hoac chia von trong buoc cap nhat dieu phoi nay.
