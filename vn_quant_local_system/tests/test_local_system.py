from __future__ import annotations

from datetime import date
import unittest

from vn_quant_local.c3_model import CurrentFeature, HistoricalRow, _signal_days, average_percentile, component_weights, rank_features
from vn_quant_local.weekly_plan import capped_inverse_vol_weights


class LocalSystemTests(unittest.TestCase):
    def test_average_percentile_preserves_ties(self) -> None:
        self.assertEqual(average_percentile([1.0,1.0,3.0]),[0.25,0.25,1.0])

    def test_signal_day_uses_previous_completed_month(self) -> None:
        canonical,preview=_signal_days([date(2026,6,30),date(2026,7,31),date(2026,8,3)])
        self.assertEqual(canonical,date(2026,7,31)); self.assertEqual(preview,date(2026,8,3))

    def test_component_weights_ignore_unfinished_labels(self) -> None:
        rows=[]
        for month in range(1,5):
            signal=date(2025,month,28)
            for index in range(5):
                rows.append(HistoricalRow(signal,date(2025,month+1,20),f"S{index}",float(index),float(index),float(4-index),float(index)))
        weights=component_weights(rows,before_day=date(2025,3,1))
        self.assertAlmostEqual(sum(weights.values()),1.0)
        self.assertTrue(all(0.0<=value<=0.5+1e-12 for value in weights.values()))

    def test_rank_features(self) -> None:
        features=[CurrentFeature(date(2026,7,31),f"S{i}",10000+i,0.01+i*0.001,i/10,0.8+i/100,True,10e9,0,True,True) for i in range(10)]
        rows=rank_features(features,{"low_volatility":1/3,"relative_strength_120":1/3,"high_52_week":1/3})
        self.assertEqual(len(rows),10); self.assertEqual([row["rank"] for row in rows],list(range(1,11)))

    def test_inverse_vol_weights_respect_cap(self) -> None:
        rows=[{"symbol":f"S{i}","volatility_60":0.01+i*0.001} for i in range(10)]
        weights=capped_inverse_vol_weights(rows,cap=0.15)
        self.assertAlmostEqual(sum(weights.values()),1.0,places=9); self.assertLessEqual(max(weights.values()),0.15+1e-9)


if __name__=="__main__": unittest.main()
