# Ban giao doan chat dieu phoi

Cap nhat: 2026-07-25

## Vai tro

- Doan `00` la dau moi dieu phoi trung tam.
- Doan `01` da hoan thanh pham vi chuyen mon Moc 1 — du lieu.
- Doan `02` dang phu trach Moc 2 — tap co phieu va duong co so.
- GitHub la nguon su that ve nhanh, commit, PR va CI.

## Nen da xac minh khi mo Moc 2

- PR so 3 da gop phan trien khai Moc 1.
- PR so 4 da gop phan tai lieu dieu phoi sau nghiem thu.
- Dau `main`: `97399e291b0d3d237f247f58ffa03049826d40bd`.
- Nhanh lam viec: `m2-tap_co_phieu-duong_co_so`.
- Nhanh lam viec duoc tach tu dung commit `97399e291b0d3d237f247f58ffa03049826d40bd`; tai thoi diem mo moc, nhanh va commit nen la `identical`.
- Python muc tieu: 3.12; cong cu moi truong: `uv`.

## Bang chung CI dong Moc 1

- GitHub Actions run so 44, ID `30111176831`: `completed`, `success`.
- Job `kiem_tra`, ID `89540796877`: `completed`, `success`.
- Tat ca cac buoc deu dat.

## Phan quyet

**MOC 1 DA DONG HOAN TOAN. MOC 2 DA MO.**

## Ra soat PR so 5 cua doan 00

- PR: `#5 — M2: tap co phieu va duong co so`.
- Dau nhanh duoc ra soat: `eaca41cf2d894658e9af067aff1ec8135adf0118`.
- Phan ma va CI ban dau dat; run so 49, ID `30113676673`, job `kiem_tra` ID `89549033754` ket luan `success`.
- Phan quyet: **YEU CAU THAY DOI — GIU DRAFT**.
- Loi can sua la tinh toan ven san pham CLI: bo qua `bao_cao_loi.json` khi khoa dau ra, co the de bao cao loi canh san pham thanh cong, va co the de lai CSV thanh cong mot phan neu ghi JSON that bai.
- Commit sua ma: `c18557aef6bf9c7c0e5a5c750dc23cdb7ea9d55a` (`sua tinh toan ven san pham CLI Moc 2`).
- Hoi quy moi bao ve thu muc thanh cong, bao cao loi cu, rollback khi cong bo tep thu hai that bai va quy tac khong dong thoi co `bao_cao.json` voi `bao_cao_loi.json`.
- PR van giu draft, khong gop va khong mo Moc 3. Dang cho CI tren dau nhanh cuoi va xac minh that FPT, HPG, MBB voi it nhat 260 phien.

## Pham vi doan 02

- tap co phieu theo tung thoi diem;
- bo loc thanh khoan;
- MA250;
- dong luong;
- CSV va bao cao JSON duong co so phuc vu nghien cuu sau nay.

## Gioi han du lieu thanh vien

Neu chua co nguon lich su dang tin cay, doan 02 chi xay giao dien, dinh dang tep va kiem thu bang du lieu gia lap. Giao dien chong nhin truoc da co, nhung khong duoc tuyen bo da giai quyet thien lech song sot bang du lieu that. Moi phuong an nguon moi phai bao ve doan 00 truoc khi tich hop.

## Quy tac ban giao

Bao cao ve doan 00 phai co dau main, dau nhanh, danh sach commit va tep, quyet dinh kien truc, cong thuc, bang chung khong nhin truoc, so kiem thu, log Python 3.12, CI, ket qua thu that neu co, du lieu con thieu, rui ro va ket luan ve trang thai draft.

## Khong duoc lam

- Khong mo Moc 3.
- Khong tu gop PR.
- Khong chuyen PR khoi draft khi chua co phe duyet cua doan 00.
- Khong dua du lieu that, nhat ky that, danh sach thanh vien bi han che hoac khoa len GitHub.
- Khong trien khai backtest, hoc may, chia von hoac tai toan bo VN100 trong Moc 2.
