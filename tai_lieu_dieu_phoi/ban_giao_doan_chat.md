# Ban giao doan chat dieu phoi

Cap nhat: 2026-07-27

## Nguon su that

- Base: `24bf02a7cf0f18d5a0fe342356b8ea0e045b1ed6`.
- Final source ky thuat: `5aec6ace8423fbf30442aa77db6ff63adb3c854e`.
- CI run #334: success.
- Ubuntu Job `89890344314`: success.
- Windows Job `89890344310`: success.
- 320 test discovery.

## Durability

File fsync ap dung cho 16 san pham va manifest tren Ubuntu/Windows. POSIX directory fsync dung O_DIRECTORY khi co va propagate loi. Windows khong mo directory bang os.open va tra capability unsupported. Atomic replace, same-parent staging, chong ghi de va rollback van giu tren ca hai nen tang. Khong tuyen bo crash durability directory entry Windows tuong duong POSIX.

## Buoc hien tai

Tao PR clean-history cuoi voi nam commit sach. Sau CI xanh, bao doan 00; khong tu dong dong PR #13, khong Ready/merge va khong chay Tier A.
