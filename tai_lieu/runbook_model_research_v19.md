# Model research v19: deep point-in-time history first

Web and DNSE portfolio synchronization are not prerequisites for this workflow.
The research pipeline must remain runnable with no DNSE account credentials.

## Locked evaluation contract

- Monthly model horizon only; T+1 is execution-only.
- Minimum train: 60 labeled months.
- Inner validation: 3 months.
- Nested policy validation: 6 months.
- Minimum outer test: 48 months.
- Model family remains fixed inside each outer evaluation.
- Current-universe membership must not be applied backwards for a research gate.
- Price data must be adjusted, or accompanied by point-in-time corporate actions.

## Step 1: derive the dated history requirement

```bash
PYTHONPATH=src uv run --python 3.12 \
  python -m he_thong_dinh_luong.historical_data_requirements_v19 \
  --input-zip "C:\path\to\daily_prediction_input.zip" \
  --output-json "C:\path\to\historical_data_requirements_v19.json" \
  --evaluation-months 72 \
  --minimum-train-months 60 \
  --minimum-outer-test-periods 48
```

A non-zero exit is expected while deeper history is missing. The JSON is the
source of truth. Do not lower the protocol merely to obtain exit code zero.

## Step 2: probe market-data coverage before a full download

KBS and VCI do not use DNSE account credentials:

```bash
PYTHONPATH=src uv run --python 3.12 --with vnstock==4.0.4 \
  python -m he_thong_dinh_luong.historical_source_probe_v19 \
  --providers kbs,vci \
  --symbols VNINDEX,VCB,MBB,FPT \
  --start 2015-07-31 \
  --end 2026-07-31 \
  --output-json "C:\path\to\historical_source_probe_v19.json"
```

DNSE OpenAPI may be added explicitly only to compare market-data coverage:

```bash
--providers kbs,vci,dnse
```

This optional DNSE probe reads only `DNSE_API_KEY` and `DNSE_API_SECRET` from
the local environment. It does not use account, balance, position, or order
endpoints and never writes credential values.

## Interpretation

`SOURCE_FOUND` means at least one provider returned the requested start and end
for all probe symbols. It does not by itself make a research dataset valid.
The full acquisition still needs:

- all historical candidate symbols, including delisted/removed names;
- a point-in-time universe or a dynamic liquidity universe computed only from
  information available at each signal date;
- VNINDEX calendar and returns;
- adjusted price basis, or unadjusted prices plus point-in-time corporate
  actions;
- immutable raw files and source hashes.

Only after those contracts pass should `extended_history_reference_v18` or a
later locked runner start Model Lab.
