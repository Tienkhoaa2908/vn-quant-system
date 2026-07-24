# Cong viec hien tai

Cap nhat: 2026-07-24

## Doan phu trach

`00 Dieu phoi trung tam` dang hoan tat cap nhat tai lieu sau khi Moc 1 da duoc nghiem thu sau gop.

## Trang thai da xac minh

- PR so 3 da duoc gop vao `main` bang merge commit.
- Thoi diem gop: `2026-07-24T16:40:46Z`.
- Dau nhanh Moc 1 da gop: `639afabb406bd839540be9acfbfcf1d6c44f5aa8`.
- Dau `main` sau gop: `e94d4a340ac734bfabc14f340626c408af33645f`.
- PR co 24 tep thay doi va khong chua tep duoi `du_lieu/`.

## Moc 1 tren main

Da xac minh `main` co:

- workflow `kiem_tra_tu_dong` dung Python 3.12;
- giao dien va cac nguon du lieu;
- nguon Vnstock Community 4.0.4;
- luu tru, chuan hoa, kiem tra chat luong va quy trinh xu ly;
- CLI tham do va tai that nho;
- kiem thu du lieu thi truong va nguon Vnstock;
- quy tac `.gitignore` bo qua `/du_lieu/` va tep nhay cam;
- tai lieu kien truc va huong dan van hanh.

## Bang chung ky thuat

### Truoc gop

- Tham do that FPT, HPG, MBB: dat.
- Tai that nho FPT, HPG, MBB: dat.
- Python 3.12: 30/30 kiem thu dat.
- GitHub Actions run so 38, ID `30108780878`: success tren commit `639afabb406bd839540be9acfbfcf1d6c44f5aa8`.

### Sau gop tren main

- Su kien: `push`.
- Nhanh: `main`.
- Commit: `e94d4a340ac734bfabc14f340626c408af33645f`.
- Run so 39, ID `30110023878`: `completed`, `success`.
- Job `kiem_tra`, ID `89536932151`: `completed`, `success`.
- Tat ca buoc cua job deu dat.
- Canh bao Node.js 20 deprecated la canh bao bao tri khong chan.

## Ket luan Moc 1

**DAT — MOC 1 DA HOAN TAT NGHIEM THU SAU GOP.**

Tat ca dieu kien bat buoc da dat:

1. PR so 3 da merged.
2. Merge commit tren `main` da xac minh.
3. Pham vi Moc 1 ton tai day du tren `main`.
4. Khong co du lieu that trong Git.
5. CI truoc gop dat.
6. CI sau gop tren `main` dat.

## Viec dang hoat dong

1. Hoan tat PR so 4 chi cap nhat ba tep dieu phoi.
2. Cho CI chay tren dau nhanh moi nhat cua PR so 4.
3. Neu CI dat, nguoi dung gop PR so 4 bang merge commit.
4. Sau khi gop, doan `00` xac minh dau `main` va CI lan cuoi.
5. Chi sau buoc 4 moi duoc giao ke hoach Moc 2.

## Pham vi bi khoa

- Khong mo hoac trien khai Moc 2 truoc khi PR so 4 duoc gop va xac minh.
- Khong them MA250, momentum, backtest, hoc may hoac chia von.
- Khong tai toan bo VN100.
- Chua xoa nhanh `m1-du_lieu` truoc khi cap nhat dieu phoi sau gop hoan tat.
