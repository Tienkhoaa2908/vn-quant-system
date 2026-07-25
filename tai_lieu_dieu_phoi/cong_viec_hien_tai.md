# Cong viec hien tai

Cap nhat: 2026-07-25

## Doan phu trach

Doan `03 Mo phong giao dich va backtest` phu trach trien khai Moc 3 duoi dieu phoi cua doan `00 Dieu phoi trung tam`.

## Nen da duoc phe duyet

- Base: `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- Nhanh: `m3-mo_phong-giao_dich`.
- Dac ta: `tai_lieu/dac_ta_moc_3.md`.
- PR dieu phoi số 6 da gop; CI sau gop run 86 thanh cong.
- Bon commit dieu phoi tren dau nhanh phai duoc giu nguyen.

## Ket qua vong trien khai hien tai

Da hoan thanh:

1. Mo CI cho nhanh Mốc 3, khong giam cac buoc kiem tra.
2. Tach domain model khoi CLI va lop cong bo.
3. Trien khai giao dien ty trong muc tieu, cau hinh tap trung va xac thuc dau vao.
4. Trien khai lenh DAY, khop open phien ke tiep, phi/thue/truot gia va lot size.
5. Trien khai so cai tien mat, vi the, NAV va cac bat bien long-only.
6. Trien khai chia tach, co phieu thuong, co tuc tien mat va chong tinh hai lan.
7. Trien khai ba baseline kiem tra engine.
8. Trien khai CAGR, maximum drawdown, Sharpe, turnover va tong chi phi.
9. Trien khai CLI va chin san pham bat bien co manifest SHA-256/rollback.
10. Bo sung kiem thu Mốc 3, kich ban vang va giu hoi quy Mốc 0–2.
11. Cap nhat kien truc, DECISIONS, README va tai lieu dieu phoi.
12. Mo PR số 7 o trang thai draft.

## Cua kiem so tiep theo

- Xac minh CI tren head cuoi va ghi Run ID/Job ID vao PR.
- Xac minh merge ref cua PR số 7.
- Chay cuc bo FPT, HPG, MBB sau khi co moi truong Vnstock/du lieu that phu hop; khong commit san pham.
- Bao cao day du cho doan 00.
- Giu PR draft, khong chuyen Ready va khong gop.

## Gioi han hien tai

- Moi truong connector khong co working tree Git va khong co du lieu thi truong that duoc mount, nen vong nay chua chay xac minh FPT/HPG/MBB cho Mốc 3.
- Nguon lich su thanh vien that chua duoc phe duyet.
- Engine khong mo phong partial fill, participation rate, quyen mua, sap nhap, hoan doi hay huy niem yet cuong buc.
- Khong SSI, khong ML, khong chia von san xuat va khong mo Mốc 4.
