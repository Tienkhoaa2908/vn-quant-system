# Ban giao doan chat dieu phoi

Cap nhat: 2026-07-25

## Vai tro va nen

- Doan `00` la dau moi dieu phoi trung tam.
- Kho: `Tienkhoaa2908/vn-quant-system`.
- `main`: `79a044d75f3a66e5c636f0a83613fc9af0cac3fc`.
- Nhanh dieu phoi sau gop: `cap_nhat-sau-gop-m3`.
- Nhanh nay chi cap nhat tai lieu; khong trien khai Moc 4.
- Khong force-push, khong commit `du_lieu/`, khong tu gop PR.

## Moc 3 da dong hoan toan

PR trien khai:

- PR so 7: `M3: mo phong giao dich va backtest`.
- Head phe duyet: `305da62ac54b735a129ab4dc2c66b0826b8953c3`.
- Merge commit: `79a044d75f3a66e5c636f0a83613fc9af0cac3fc`.
- Gop bang merge commit, khong squash va khong rebase.
- PR da dong, `merged=true`.
- `main` trung khop voi merge commit.

CI sau gop:

- workflow `kiem_tra_tu_dong`;
- run number `183`;
- Run ID `30150924124`;
- job `kiem_tra`, Job ID `89661073156`;
- trigger `push`, branch `main`;
- checkout `79a044d75f3a66e5c636f0a83613fc9af0cac3fc`;
- `completed/success`;
- tat ca buoc dong bo, compile va unittest ngoai tuyen deu dat.

## Nang luc da ban giao

- Tin hieu sau close T, khop som nhat tai open phien ke tiep.
- Lenh DAY, khong tu doi phien khi thieu bar/open.
- Long-only, khong short, khong margin, khong tien mat am.
- Phi mua/ban, thue ban, slippage, lot size va pre-trade sizing.
- Tien mat, vi the, so cai, NAV, realized/unrealized P&L va doi soat.
- Chia tach, co phieu thuong va co tuc tien mat MVP.
- Eligibility fail closed cho mo/tang vi the.
- Truy vet don vi va lam sach credential.
- 121 test: 60 Moc 3 va 61 hoi quy Moc 0–2.
- 9 san pham bat bien, SHA-256, cong bo nguyen tu va rollback.

## Xac minh ky thuat tren du lieu that

- Ma lan chay: `xac_minh_fpt_hpg_mbb_20260725T074736Z`.
- Nguon Moc 1: `20260724T190515274806Z_6cd15c6d`.
- FPT, HPG va MBB; 287 phien moi ma; 861 dong sau khi ghep voi trang thai Moc 2.
- Python `3.12.10`, uv `0.11.32`.
- Kich ban: moi ma 30%, giu 10% tien mat; mua 2025-06-30; dong het 2026-07-23.
- 287 dong NAV, 287 dong so cai, 6/6 lenh khop, 0 het han, 0 tu choi.
- Tien mat khong am, dong het vi the, doi soat `0.0000000`.
- 9 san pham va SHA-256 manifest dat; khong co canh bao.

Chi tiet: `tai_lieu/ket_qua_xac_minh_that_moc_3.md`.

## Gioi han bat buoc

- Lan chay ba ma chi xac minh ky thuat engine.
- Khong dung ket qua de danh gia chien luoc hoac kha nang sinh loi.
- Chua co lich su thanh vien VN100 point-in-time that.
- Chua co universe nhieu nam duoc kiem toan.
- Co so gia va corporate actions that chua duoc phe duyet day du.
- Chua co feature set san xuat, nhan, walk-forward, ML hoac chia von.
- Khong tich hop SSI, khong doc tai khoan va khong gui lenh.

## Cua kiem soat tiep theo

1. PR dieu phoi sau gop chi duoc chua tai lieu.
2. Khong tao nhanh ma Moc 4 truoc khi dac ta Moc 4 duoc phe duyet.
3. Dac ta tiep theo phai xu ly ro universe VN100 point-in-time/Universe thanh khoan cao point-in-time va lich su nhieu nam.
4. Phai kiem soat survivorship bias, look-ahead va warm-up MA250.
5. Chi sau khi dac ta duoc phe duyet moi tao nhanh chuyen mon tiep theo.

Moc 4 hien **chua mo**.