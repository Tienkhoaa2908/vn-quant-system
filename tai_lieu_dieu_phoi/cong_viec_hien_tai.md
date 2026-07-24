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

## Trang thai PR so 5

- PR: `#5 — M2: tap co phieu va duong co so`.
- Dau nhanh da duoc doan 00 ra soat: `eaca41cf2d894658e9af067aff1ec8135adf0118`.
- Phan ma va CI ban dau dat; run so 49, ID `30113676673`, job `kiem_tra` ID `89549033754` ket luan `success`.
- Phan quyet cua doan 00: **YEU CAU THAY DOI — GIU DRAFT**.
- PR khong duoc gop, khong duoc chuyen khoi draft va khong mo Moc 3.

## Loi toan ven san pham CLI

- `_kiem_tra_dau_ra_trong()` truoc day bo qua `bao_cao_loi.json`.
- Chay lai thu muc thanh cong co the tao them bao cao loi.
- Bao cao loi cu co the ton tai canh san pham thanh cong moi.
- Ghi CSV truoc JSON co the de lai thanh cong mot phan neu tep thu hai that bai.

## Cong viec sua loi

1. Da kiem tra ca ba san pham `duong_co_so.csv`, `bao_cao.json`, `bao_cao_loi.json` truoc khi bat dau.
2. Da tu choi va khong sua thu muc da co bat ky san pham nao.
3. Da chuan bi day du noi dung CSV va JSON truoc khi cong bo.
4. Da cong bo khong ghi de, rollback san pham da cong bo neu tep thu hai that bai va don tep tam.
5. Da ngan tao `bao_cao_loi.json` neu thu muc co san pham thanh cong; bao cao loi cu khong bi ghi de.
6. Da bo sung hoi quy cho thu muc thanh cong, thu muc co bao cao loi cu va loi cong bo san pham thu hai.
7. Commit sua ma: `c18557aef6bf9c7c0e5a5c750dc23cdb7ea9d55a`.
8. Dang cho CI tren dau nhanh cuoi va van chua co xac minh that FPT, HPG, MBB voi it nhat 260 phien.

## Nguyen tac bat buoc

- Khong dung danh sach co phieu hien tai cho toan bo lich su.
- Khong lay anh chup tap co phieu co ngay hieu luc sau ngay danh gia.
- Khong gia mao du lieu thanh vien lich su va khong tu suy doan thanh vien thieu.
- Khong dung quan sat tuong lai cho thanh khoan, MA250 hoac dong luong.
- Khong hard-code nguong thanh khoan hay cua so dong luong san xuat chua duoc phe duyet.
- Khong ghi de im lang san pham da ton tai.
- CI hoan toan ngoai tuyen; khong goi Vnstock hoac mang.
- Giao dien chong nhin truoc da co, nhung nguon thanh vien lich su that chua duoc phe duyet va chua duoc coi la da loai bo thien lech song sot thuc te.

## Ngoai pham vi

- Moc 3 va mo phong giao dich.
- Backtest, phi, thue, truot gia va lot size.
- Hoc may, LightGBM va nhan.
- Chia von, toi uu danh muc va gioi han ty trong.
- Tai toan bo VN100.
