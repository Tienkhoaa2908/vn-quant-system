# Cong viec hien tai

Cap nhat: 2026-07-25

## Doan phu trach

`02 Tap co phieu va duong co so` dang phu trach chuyen mon Moc 2 duoi dieu phoi cua doan `00 Dieu phoi trung tam`.

## Trang thai nen da xac minh

- PR so 3 da gop phan trien khai Moc 1.
- PR so 4 da gop phan tai lieu dieu phoi sau nghiem thu.
- Dau `main`: `97399e291b0d3d237f247f58ffa03049826d40bd`.
- Nhanh `m2-tap_co_phieu-duong_co_so` ton tai va tai thoi diem mo moc trung khop hoan toan voi dau `main` neu tren.
- Python muc tieu: 3.12.
- Cong cu moi truong: `uv`.

## Bang chung GitHub Actions cuoi cung cua Moc 1

- Run so 44, ID `30111176831`: `completed`, `success`.
- Job `kiem_tra`, ID `89540796877`: `completed`, `success`.
- Tat ca buoc cua job deu dat.

## Ket luan Moc 1

**DAT — MOC 1 DA DONG HOAN TOAN.**

## Viec dang hoat dong cua Moc 2

1. Cap nhat tai lieu dieu phoi trong commit dau tien, khong kem ma chuyen mon.
2. Chot quyet dinh kien truc trong `DECISIONS.md`.
3. Xay tap co phieu theo tung thoi diem bang anh chup co ngay hieu luc.
4. Them gia tri giao dich, bo loc thanh khoan, MA250 va dong luong khong nhin truoc.
5. Them CLI, CSV/JSON dau ra, kiem thu ngoai tuyen va tai lieu van hanh.
6. Mo draft PR `M2: tap co phieu va duong co so` vao `main` va giu draft cho den khi doan 00 phe duyet.

## Nguyen tac bat buoc

- Khong dung danh sach co phieu hien tai cho toan bo lich su.
- Khong lay anh chup tap co phieu co ngay hieu luc sau ngay danh gia.
- Khong gia mao du lieu thanh vien lich su va khong tu suy doan thanh vien thieu.
- Khong dung quan sat tuong lai cho thanh khoan, MA250 hoac dong luong.
- Khong hard-code nguong thanh khoan hay cua so dong luong san xuat chua duoc phe duyet.
- Khong ghi de im lang san pham da ton tai.
- CI hoan toan ngoai tuyen; khong goi Vnstock hoac mang.

## Ngoai pham vi

- Moc 3 va mo phong giao dich.
- Backtest, phi, thue, truot gia va lot size.
- Hoc may, LightGBM va nhan.
- Chia von, toi uu danh muc va gioi han ty trong.
- Tai toan bo VN100.
