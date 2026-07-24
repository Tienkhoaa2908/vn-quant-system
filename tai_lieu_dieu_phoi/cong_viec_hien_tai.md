# Cong viec hien tai

Cap nhat: 2026-07-25

## Doan phu trach

Doan `03 Mo phong giao dich va backtest` phu trach trien khai Moc 3 duoi dieu phoi cua doan `00 Dieu phoi trung tam`.

Doan `02 Tap co phieu va duong co so` da hoan thanh pham vi Moc 2. Khong con nhiem vu ma tren nhanh cu.

## Nen da duoc phe duyet

- PR so 6 da gop bang merge commit `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- `main` trung khop merge commit tren.
- CI sau gop: run so 86, Run ID `30123567224`, job `kiem_tra` ID `89581624420`, thanh cong.
- Dac ta chinh thuc: `tai_lieu/dac_ta_moc_3.md`.
- Ca 8 quyet dinh kien truc trong dac ta da duoc phe duyet.

## Nhanh chuyen mon

- Nhanh: `m3-mo_phong-giao_dich`.
- Base: `f52e06ffd4dde26e8af9d6451ec1e64f5a61b35d`.
- Nhanh duoc tao truc tiep tu base tren sau khi CI `main` dat.
- Cac commit dieu phoi dau nhanh chi cap nhat tai lieu, chua co ma engine.

## Cong viec bat buoc Moc 3

1. Doc toan bo `tai_lieu/dac_ta_moc_3.md` truoc khi viet ma.
2. Thiet ke giao dien ty trong muc tieu, lenh, khop lenh, vi the va so cai danh muc.
3. Bao dam tin hieu ngay `T` chi khop som nhat tai mo cua phien ke tiep.
4. Trien khai lenh `DAY`; thieu bar ngay thuc thi thi het han, khong tu dời sang phien xa hon.
5. Trien khai phi mua, phi ban, thue ban, truot gia va kich thuoc lo bang cau hinh.
6. Ngan tien mat am, ban vuot vi the, vi the am, short va margin.
7. Trien khai corporate actions MVP: chia tach/co phieu thuong va co tuc tien mat.
8. Trien khai baseline mua-va-giu, can bang deu va MA250/dong luong de kiem tra engine.
9. Tinh NAV, loi nhuan, drawdown, Sharpe, turnover va tong chi phi.
10. Cong bo dau ra bat bien, manifest SHA-256, commit va cau hinh lan chay.
11. Bo sung kiem thu ngoai tuyen, kich ban vang va giu toan bo hoi quy Moc 0–Moc 2.
12. Mo PR dang draft va bao cao day du ve doan `00`.

## Nguyen tac Git va CI

- Khong lam viec truc tiep tren `main`.
- Khong tao nhanh thay the.
- Khong force-push.
- Khong commit `du_lieu/`, log that hoac khoa.
- Cap nhat workflow de CI ho tro nhanh Moc 3 hoac mo PR draft som de trigger `pull_request`.
- PR Moc 3 phai giu draft.
- Khong tu chuyen Ready, khong tu gop va khong mo Moc 4.

## Ngoai pham vi

- Khong Logistic Regression.
- Khong LightGBM.
- Khong walk-forward cho mo hinh hoc may.
- Khong inverse volatility san xuat.
- Khong tran 15% moi ma hay 25% moi nganh trong lop phan bo san xuat.
- Khong toi uu danh muc.
- Khong ket noi SSI, khong doc tai khoan va khong gui lenh.

## Gioi han du lieu

- Nguon lich su thanh vien that chua duoc phe duyet; khong tuyen bo da loai bo thien lech song sot thuc te.
- Co so gia dieu chinh hoac khong dieu chinh phai duoc khai bao.
- Khong duoc tinh corporate action hai lan.
- Du lieu that FPT, HPG va MBB chi duoc dung de xac minh cuc bo va khong commit.
