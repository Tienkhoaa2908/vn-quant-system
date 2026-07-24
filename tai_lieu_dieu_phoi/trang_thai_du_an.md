# Trang thai du an

Cap nhat gan nhat: 2026-07-24

## Kho ma nguon

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh chinh: `main`.
- Dau `main` da xac minh sau khi gop Moc 1: `e94d4a340ac734bfabc14f340626c408af33645f`.
- Commit nay la merge commit cua PR so `3` tu `m1-du_lieu` vao `main`.
- Python muc tieu: 3.12.
- Cong cu moi truong: `uv`.

## Moc 0

Trang thai: **da hoan thanh, da kiem tra va da gop vao main**.

- PR so 1: da gop.
- Commit trien khai chinh: `3385e401532e51457b9e9360e17df7af0e021881`.
- Commit hop nhat: `b132578b763ead96ad172a1ace68acdff6e36007`.

## Bo tai lieu dieu phoi

Trang thai: **da gop vao main**.

- PR so 2: da gop.
- Commit hop nhat: `4eba2a77d5864027c84d4350769d95fd4abd5fee`.

## Moc 1 — Du lieu

Trang thai dieu phoi: **da nghiem thu ky thuat, da gop vao main va da nghiem thu sau gop**.

### PR va commit

- PR so 3: da gop luc `2026-07-24T16:40:46Z`.
- Nhanh nguon: `m1-du_lieu`.
- Dau nhanh duoc phe duyet: `639afabb406bd839540be9acfbfcf1d6c44f5aa8`.
- Merge commit tren `main`: `e94d4a340ac734bfabc14f340626c408af33645f`.
- PR co 17 commit, 24 tep thay doi va khong chua tep nao duoi `du_lieu/`.

### Pham vi da co tren main

- giao dien chung cho nguon du lieu;
- nguon gia lap de kiem thu ngoai tuyen;
- bo chuyen doi Vnstock Community `4.0.4`, nguon KBS;
- luu JSON tho bat bien;
- chuan hoa CSV UTF-8;
- bao cao chat luong va nhat ky JSON;
- du lieu san sang CSV;
- trang thai doc lap tung ma va thu lai loi tam thoi;
- CLI tham do va tai that nho;
- kiem thu ngoai tuyen va workflow Python 3.12.

### Tham do va tai that

- Tham do that: `20260724T152739494769Z_521d23ce`.
- Tai that nho: `20260724T153953222157Z_5383eaab`.
- FPT, HPG, MBB: deu thanh cong, moi ma 8 dong trong khoang `2026-07-01` den `2026-07-10`.
- Du lieu that va nhat ky that chi nam cuc bo duoi `du_lieu/` va khong duoc commit.

### Kiem thu truoc gop

- Python: `CPython 3.12.13`, Windows x86-64.
- Unittest: `30/30` dat, `Ran 30 tests in 0.696s`, ket qua `OK`.
- GitHub Actions run so 38, ID `30108780878`, dat tren dau nhanh `639afabb406bd839540be9acfbfcf1d6c44f5aa8`.
- Job `kiem_tra`, ID `89532709434`: thanh cong; tat ca buoc deu dat.

### Kiem thu sau gop tren main

- Su kien: `push` tren nhanh `main`.
- Commit: `e94d4a340ac734bfabc14f340626c408af33645f`.
- GitHub Actions run so 39, ID `30110023878`: `completed`, `success`.
- Job `kiem_tra`, ID `89536932151`: `completed`, `success`.
- Tat ca buoc lay ma nguon, cai uv, cai Python, dong bo, kiem tra cu phap, kiem thu ngoai tuyen va don dep deu dat.
- Canh bao Node.js 20 deprecated duoc GitHub chay tren Node.js 24; day la canh bao bao tri, khong chan nghiem thu.

### Ket luan nghiem thu sau gop

**DAT — MOC 1 DA HOAN TAT NGHIEM THU SAU GOP.**

PR so 4 chi cap nhat ba tep dieu phoi de ghi ben vung ket qua nay. PR so 4 phai duoc gop va `main` phai duoc xac minh lan cuoi truoc khi giao viec Moc 2.

## Pham vi bi khoa

- Chua mo hoac trien khai Moc 2 truoc khi PR so 4 duoc gop va `main` duoc xac minh lan cuoi.
- Chua them MA250 hoac momentum.
- Chua backtest.
- Chua hoc may.
- Chua chia von.
- Chua tai toan bo VN100.
