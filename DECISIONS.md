# Cac quyet dinh kien truc

## QD-0001: Khoi tao theo tung lat doc

Moc 0 chi tao mot lat doc chay duoc: doc tep CSV, kiem tra chat luong, xuat bao cao JSON va tra ma thoat.

## QD-0002: Khong phu thuoc thu vien chay ben ngoai

Phan chay cua Moc 0 chi dung thu vien chuan Python de giam rui ro cai dat va giu bo khung nho.

## QD-0003: Ten du an tu dat dung tieng Viet khong dau

Ten thu muc, tep va ham do du an tu dat dung chu thuong, tieng Viet khong dau va dau gach duoi. Ten bat buoc theo cong cu duoc giu nguyen.

## QD-0004: Du lieu gia lap chi phuc vu kiem thu

Moi du lieu trong `tests/du_lieu` la du lieu gia lap, khong duoc su dung nhu du lieu thi truong that.

## QD-0005: Tach nguon du lieu bang giao dien chung

Luon thu thap chi phu thuoc giao dien `nguon_du_lieu`. Chi bo chuyen doi `nguon_vnstock` duoc phep biet chi tiet Vnstock va KBS. Nguon gia lap thuc hien cung giao dien de kiem thu ngoai tuyen.

## QD-0006: Du lieu tho bat bien va trang thai rieng tung ma

Moi tep tho la JSON dang bang va duoc ghi theo ma lan chay duy nhat. Tep da ton tai khong duoc ghi de. Neu mot ma khong co du lieu, khong tao tep tho gia; chi ghi nhat ky that bai da lam sach va tiep tuc ma khac khi an toan.

## QD-0007: Dinh dang san pham Moc 1

Du lieu tho, nhat ky va bao cao chat luong dung JSON. Du lieu chuan hoa va san sang dung CSV UTF-8 voi bay cot cua du an. Du lieu san sang chi duoc tao khi khong co loi chat luong nghiem trong.

## QD-0008: Khoang ngay bat thuong chi la canh bao

Khi hai quan sat lien tiep cach nhau hon bay ngay lich, he thong ghi canh bao. He thong khong tu dien ngay, khong tao ngay giao dich gia va khong chan tep san sang chi vi canh bao nay.

## QD-0009: Vnstock Community 4.0.4 va nguon KBS

Bo chuyen doi khoa dung Vnstock Community `4.0.4`. Giao dien da duoc xac minh tu ma nguon tag `v4.0.4`: `Market().equity/index(symbol).ohlcv(start, end, interval="1D", source="kbs")` tra cac cot `time`, `open`, `high`, `low`, `close`, `volume`.

Vnstock chuyen gia co phieu ve nghin dong, con chi so giu don vi diem. Giao dien cong khai nay khong co tham so chon gia dieu chinh hay chua dieu chinh, vi vay du an khong truyen tham so suy doan.

## QD-0010: VNINDEX la phan mo rong

FPT, HPG va MBB la ba ma bat buoc. VNINDEX duoc thu rieng. That bai, thieu khoi luong hoac y nghia khoi luong chua ro cua VNINDEX khong chan nghiem thu ba ma bat buoc.

## QD-0011: Vnstock khong la phu thuoc mac dinh cua CI

GitHub Actions chi cai moi truong du an va chay kiem thu ngoai tuyen. Nguoi dung chay Vnstock that bang `uv run --with vnstock==4.0.4`. Cach nay giu CI khong can khoa, khong goi nguon thi truong va khong tai du lieu that.
