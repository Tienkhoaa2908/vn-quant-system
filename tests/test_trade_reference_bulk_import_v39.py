from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from he_thong_dinh_luong import trade_reference_bulk_import_v39 as bulk


def write_csv(path: Path, rows: list[dict[str, object]], fields: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


class TradeReferenceBulkImportV39Tests(unittest.TestCase):
    def seed(self, root: Path) -> None:
        write_csv(root / bulk.SECTOR_WORK_FILE, [
            {"signal_date":"2022-01-01","execution_day":"2022-01-03","symbol":"AAA","sector":"","effective_from":"","effective_to":"","source_document_id":"","source_filename":"","source_url":"","source_sha256":"","verified":False},
            {"signal_date":"2022-02-01","execution_day":"2022-02-03","symbol":"AAA","sector":"","effective_from":"","effective_to":"","source_document_id":"","source_filename":"","source_url":"","source_sha256":"","verified":False},
        ], ("signal_date","execution_day","symbol","sector","effective_from","effective_to","source_document_id","source_filename","source_url","source_sha256","verified"))
        write_csv(root / bulk.WINDOW_WORK_FILE, [
            {"signal_date":"2022-01-01","holding_start":"2022-01-03","holding_end":"2022-02-03","symbol":"AAA","event_count":"","source_document_id":"","source_filename":"","source_url":"","source_sha256":"","source_checked":False,"verified_complete":False},
        ], ("signal_date","holding_start","holding_end","symbol","event_count","source_document_id","source_filename","source_url","source_sha256","source_checked","verified_complete"))
        write_csv(root / bulk.EVENT_WORK_FILE, [
            {"source_event_id":"E1","symbol":"AAA","event_date":"2022-01-20","event_type":"CASH_DIVIDEND","adjustment_factor":"","cash_amount_vnd":"100","source_document_id":"D","source_filename":"source.bin","source_url":"u","source_sha256":"a"*64,"verified":True},
        ], ("source_event_id","symbol","event_date","event_type","adjustment_factor","cash_amount_vnd","source_document_id","source_filename","source_url","source_sha256","verified"))
        write_csv(root / bulk.PRICE_WORK_FILE, [
            {"execution_day":"2022-01-03","crosscheck_symbol_count":"","source_document_id":"","source_filename":"","official_source_url":"","source_sha256":"","verified":False},
            {"execution_day":"2022-02-03","crosscheck_symbol_count":"","source_document_id":"","source_filename":"","official_source_url":"","source_sha256":"","verified":False},
        ], ("execution_day","crosscheck_symbol_count","source_document_id","source_filename","official_source_url","source_sha256","verified"))

    def test_compact_intervals_expand_exact_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.seed(root)
            write_csv(root / bulk.SECTOR_IMPORT_FILE, [{"symbol":"AAA","sector":"BANK","effective_from":"2020-01-01","effective_to":"2025-12-31","source_document_id":"S","source_filename":"source.bin","source_url":"u","source_sha256":"a"*64,"verified":True}], ("symbol","sector","effective_from","effective_to","source_document_id","source_filename","source_url","source_sha256","verified"))
            write_csv(root / bulk.ACTION_COVERAGE_IMPORT_FILE, [{"symbol":"*","coverage_from":"2020-01-01","coverage_to":"2025-12-31","source_document_id":"A","source_filename":"source.bin","source_url":"u","source_sha256":"a"*64,"source_checked":True,"verified_complete":True}], ("symbol","coverage_from","coverage_to","source_document_id","source_filename","source_url","source_sha256","source_checked","verified_complete"))
            write_csv(root / bulk.PRICE_COVERAGE_IMPORT_FILE, [{"coverage_from":"2020-01-01","coverage_to":"2025-12-31","crosscheck_symbol_count":78,"source_document_id":"P","source_filename":"source.bin","official_source_url":"u","source_sha256":"a"*64,"verified":True}], ("coverage_from","coverage_to","crosscheck_symbol_count","source_document_id","source_filename","official_source_url","source_sha256","verified"))
            audit=bulk.apply_bulk_import(root)
            self.assertEqual(audit["expanded_rows"], {"sector_keys":2,"corporate_action_windows":1,"price_basis_dates":2})
            self.assertEqual({r["sector"] for r in read_csv(root / bulk.SECTOR_WORK_FILE)}, {"BANK"})
            self.assertEqual(read_csv(root / bulk.WINDOW_WORK_FILE)[0]["event_count"], "1")
            self.assertEqual({r["crosscheck_symbol_count"] for r in read_csv(root / bulk.PRICE_WORK_FILE)}, {"78"})

    def test_conflicting_sector_intervals_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.seed(root)
            rows=[
                {"symbol":"AAA","sector":"BANK","effective_from":"2020-01-01","effective_to":"2025-12-31","source_document_id":"S1","source_filename":"a.bin","source_url":"u","source_sha256":"a"*64,"verified":True},
                {"symbol":"AAA","sector":"TECH","effective_from":"2020-01-01","effective_to":"2025-12-31","source_document_id":"S2","source_filename":"b.bin","source_url":"u","source_sha256":"b"*64,"verified":True},
            ]
            write_csv(root / bulk.SECTOR_IMPORT_FILE, rows, ("symbol","sector","effective_from","effective_to","source_document_id","source_filename","source_url","source_sha256","verified"))
            with self.assertRaisesRegex(ValueError, "V39_BULK_SECTOR_CONFLICT"):
                bulk.apply_bulk_import(root)


if __name__ == "__main__":
    unittest.main()
