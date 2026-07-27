# Cac quyet dinh kien truc — Moc 4 final

Cac quyet dinh QD-0001..QD-0059 cua source ky thuat `5aec6ace8423fbf30442aa77db6ff63adb3c854e` tiep tuc co hieu luc. Tai lieu final clean-history bo sung quyet dinh sau.

## QD-0060: Durability cong bo theo capability nen tang

- 16 file san pham va `manifest.json` deu duoc ghi bang mode tao moi, `flush()` va file fsync tren Ubuntu va Windows.
- Tren POSIX/Linux, directory fsync dung `O_RDONLY`, them `O_DIRECTORY` khi he dieu han cung cap, goi `os.fsync(fd)` va luon dong descriptor trong `finally`.
- Loi `os.open` hoac `os.fsync` tren POSIX phai propagate; khong co broad fallback che loi permission, disk hoac filesystem.
- Tren Windows, directory fsync unsupported trong implementation Python MVP; `_fsync_dir` khong goi `os.open` tren directory va tra `False`.
- Staging nam cung parent filesystem voi destination; publication dung mot `os.replace`, tu choi ghi de destination va rollback staging khi co loi.
- Khong tuyen bo Windows co directory-entry crash durability tuong duong POSIX.

Final source ky thuat da duoc doan 00 phe duyet la `5aec6ace8423fbf30442aa77db6ff63adb3c854e`. CI run #334 da dat tren Ubuntu Job `89890344314` va Windows Job `89890344310`, tong 320 test discovery. Tier A/Tier B chua chay.
