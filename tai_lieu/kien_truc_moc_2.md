# Kien truc Moc 2 — Tap co phieu va duong co so

## Pham vi

Moc 2 chi xay:

- tap co phieu theo tung thoi diem;
- bo loc thanh khoan;
- MA250;
- dong luong;
- CSV va bao cao JSON phuc vu nghien cuu sau nay.

Khong bao gom backtest, mo phong giao dich, phi, thue, truot gia, hoc may, chia von, toi uu danh muc hoac tai toan bo VN100.

## Dau vao du lieu gia

Tai su dung CSV san sang cua Moc 1:

```text
ma,ngay,gia_mo_cua,gia_cao_nhat,gia_thap_nhat,gia_dong_cua,khoi_luong
```

Moi cap `ma,ngay` phai duy nhat. Gia dong cua phai duong va huu han. Khoi luong phai la so nguyen khong am. Dau vao co the chua sap xep; he thong sap xep rieng tung ma theo ngay.

## Dau vao tap co phieu

CSV UTF-8:

```text
ngay_hieu_luc,ma,nguon,phien_ban
```

Moi cap `ngay_hieu_luc,ma` phai duy nhat. Voi ngay `T`, chi chon anh chup gan nhat co ngay hieu luc khong lon hon `T`. Neu khong co anh chup hop le, dung voi loi. Khong suy doan thanh vien va khong dung anh chup tuong lai.

## Thanh khoan

```text
gia_tri_giao_dich = gia_dong_cua * khoi_luong
```

Vi gia co phieu cua Moc 1 co don vi nghin dong moi co phieu, gia tri giao dich co don vi nghin dong. Trung binh truot gom phien hien tai va cac phien truoc do trong cua so. Chi xuat co `dat_thanh_khoan` khi da co du `so_quan_sat_toi_thieu`. Nguong dat theo phep so sanh `>=`.

CLI bat buoc nhan:

- cua so thanh khoan;
- so quan sat toi thieu;
- nguong thanh khoan.

Khong co tham so san xuat mac dinh.

## MA250

MA250 la trung binh cong don gian cua dung 250 gia dong cua gan nhat cua cung ma. Phien 249 chua co MA250; phien 250 co gia tri dau tien; phien 251 bo quan sat dau va them quan sat moi. Co `tren_ma250` dung `gia_dong_cua >= ma250`.

## Dong luong

```text
dong_luong_N = gia_dong_cua_t / gia_dong_cua_t_tru_N - 1
```

`N` la tham so bat buoc. Can `N + 1` quan sat cua cung ma. Khong xep hang, khong chon top-N va khong dat nguong dau tu.

## Dau ra

CSV co thu tu cot on dinh:

```text
ma,ngay,thuoc_tap_co_phieu,ngay_hieu_luc_tap_co_phieu,nguon_tap_co_phieu,phien_ban_tap_co_phieu,gia_tri_giao_dich,gia_tri_giao_dich_trung_binh,dat_thanh_khoan,ma250,tren_ma250,dong_luong,trang_thai_lich_su
```

Gia tri thieu de trong trong CSV. Bool ghi `true` hoac `false`. Bao cao JSON ghi cau hinh, don vi, so dong va tom tat rieng tung ma. Hai tep dau ra mac dinh la `duong_co_so.csv` va `bao_cao.json`; tep da ton tai khong bi ghi de.

## Bang chung khong nhin truoc

- anh chup duoc chon bang dieu kien `ngay_hieu_luc <= ngay_dong`;
- du lieu duoc nhom theo ma va sap xep tang dan theo ngay;
- thanh khoan chi dung hang doi ket thuc tai dong hien tai;
- MA250 chi dung 250 quan sat ket thuc tai dong hien tai;
- dong luong chi tham chieu quan sat cach truoc `N` phien;
- kiem thu thay doi quan sat tuong lai khong lam thay doi ket qua qua khu;
- kiem thu tach hai ma chung minh khong truyen lich su giua cac ma.

## Gioi han du lieu that

Chua co tep lich su thanh vien dang tin cay duoc phe duyet. Cac tep trong `tests/du_lieu` la gia lap. Viec tich hop nguon thanh vien that phai duoc bao ve doan 00 truoc; khong commit danh sach co han che ban quyen.
