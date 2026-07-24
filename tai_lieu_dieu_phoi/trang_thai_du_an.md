# Trang thai du an

Cap nhat gan nhat: 2026-07-25

## Kho ma nguon

- Kho: `Tienkhoaa2908/vn-quant-system`.
- Nhanh chinh: `main`.
- Dau `main` da xac minh khi mo Moc 2: `97399e291b0d3d237f247f58ffa03049826d40bd`.
- Commit nay la merge commit cua PR so `4` tu `cap_nhat-sau-gop-m1` vao `main`.
- Nhanh Moc 2: `m2-tap_co_phieu-duong_co_so`.
- Nhanh Moc 2 duoc tach chinh xac tu dau `main` neu tren; tai thoi diem mo moc, so commit truoc/sau la `0/0`.
- Python muc tieu: 3.12.
- Cong cu moi truong: `uv`.
- GitHub la nguon su that ve nhanh, commit, PR va CI.

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

Trang thai dieu phoi: **da dong hoan toan**.

### PR va commit

- PR so 3: da gop luc `2026-07-24T16:40:46Z`.
- Dau nhanh duoc phe duyet: `639afabb406bd839540be9acfbfcf1d6c44f5aa8`.
- Merge commit cua PR so 3: `e94d4a340ac734bfabc14f340626c408af33645f`.
- PR so 4: da gop vao `main`.
- Merge commit cua PR so 4 va dau `main` khi mo Moc 2: `97399e291b0d3d237f247f58ffa03049826d40bd`.

### Bang chung CI cuoi cung tren main

- GitHub Actions run so 44, ID `30111176831`: `completed`, `success`.
- Job `kiem_tra`, ID `89540796877`: `completed`, `success`.
- Tat ca buoc lay ma nguon, cai uv, cai Python, dong bo moi truong, kiem tra cu phap, kiem thu ngoai tuyen va don dep deu dat.

### Ket luan

**DAT — MOC 1 DA DONG HOAN TOAN.**

## Moc 2 — Tap co phieu va duong co so

Trang thai: **da mo; PR so 5 dang draft va dang xu ly yeu cau thay doi cua doan 00**.

- Doan chuyen mon dang phu trach: `02 Tap co phieu va duong co so`.
- Nhanh lam viec bat buoc: `m2-tap_co_phieu-duong_co_so`.
- Pham vi: tap co phieu theo tung thoi diem, bo loc thanh khoan, MA250, dong luong va du lieu dau ra duong co so.
- Tap co phieu lich su that chua duoc coi la da co; truoc mat chi xay giao dien, dinh dang va kiem thu bang du lieu gia lap.
- Khong mo Moc 3.

### Ra soat PR so 5 cua doan 00

- Dau nhanh duoc ra soat ban dau: `eaca41cf2d894658e9af067aff1ec8135adf0118`.
- Phan ma va CI ban dau da dat; GitHub Actions run so 49, ID `30113676673`, job `kiem_tra` ID `89549033754` ket luan `success`.
- Phan quyet: **YEU CAU THAY DOI — GIU DRAFT**.
- Loi phat hien: CLI chua coi `bao_cao_loi.json` la san pham can khoa, co the de bao cao loi cu canh san pham thanh cong, co the tao bao cao loi moi canh san pham thanh cong cu, va co the de lai san pham thanh cong mot phan khi ghi tep thu hai that bai.
- Commit sua ma: `c18557aef6bf9c7c0e5a5c750dc23cdb7ea9d55a` (`sua tinh toan ven san pham CLI Moc 2`).
- Ban sua kiem tra ca ba ten san pham, khong sua thu muc da co san pham, chuan bi hai noi dung truoc khi cong bo, rollback khi cong bo tep thu hai that bai va don tep tam.
- PR tiep tuc giu draft. Dang cho CI tren dau nhanh cuoi va xac minh that FPT, HPG, MBB voi it nhat 260 phien.
- Giao dien chong nhin truoc da co; nguon thanh vien lich su that chua duoc phe duyet; chua tuyen bo loai bo thien lech song sot trong thuc te.

## Pham vi bi khoa

- Khong mo phong giao dich, khop lenh, phi, thue, truot gia hoac backtest.
- Khong hoc may, LightGBM, nhan, chia von, toi uu danh muc hoac gioi han ty trong.
- Khong tai toan bo VN100.
- Khong commit du lieu thi truong that, danh sach thanh vien bi han che, nhat ky that hoac khoa.
