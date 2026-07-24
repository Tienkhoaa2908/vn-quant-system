# vn-quant-system

Bo khung Moc 0 cho he thong dinh luong co phieu Viet Nam.

## Pham vi hien tai

Moc 0 chi gom:

- bo khung goi Python toi thieu;
- trinh kiem tra du lieu gia mo cua, cao nhat, thap nhat, dong cua va khoi luong;
- du lieu gia lap phuc vu kiem thu;
- kiem thu tu dong tren may va tren GitHub.

Chua trien khai MA250, mo phong giao dich, hoc may, chia von hoac tai du lieu thi truong that.

## Dinh dang du lieu

Tep CSV phai co cac cot:

```text
ma,ngay,gia_mo_cua,gia_cao_nhat,gia_thap_nhat,gia_dong_cua,khoi_luong
```

Ngay dung dinh dang `YYYY-MM-DD`.

## Cai dat

Yeu cau Python 3.12 tro len va `uv`.

```bash
uv sync --frozen
```

## Chay kiem tra du lieu

Tep hop le:

```bash
PYTHONPATH=src uv run python -m he_thong_dinh_luong tests/du_lieu/gia_lap_hop_le.csv --ngay_kiem_tra 2026-07-24
```

Tep co loi:

```bash
PYTHONPATH=src uv run python -m he_thong_dinh_luong tests/du_lieu/gia_lap_co_loi.csv --ngay_kiem_tra 2026-07-24
```

Ma thoat:

- `0`: du lieu hop le;
- `1`: loi doc tep hoac tham so;
- `2`: du lieu khong dat quy tac chat luong.

## Chay kiem thu

```bash
PYTHONPATH=src uv run python -m unittest discover -s tests -p 'test_*.py' -v
```

## Nguyen tac du an

- GitHub la nguon su that.
- Khong dua khoa truy cap hoac mat khau vao kho ma nguon.
- Khong dung du lieu tuong lai trong nghien cuu.
- Du lieu gia lap chi dung cho kiem thu, khong dai dien cho thi truong that.
- Moi thay doi kien truc phai duoc ghi vao `DECISIONS.md`.
