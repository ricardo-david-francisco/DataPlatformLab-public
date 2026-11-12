"""Load every source into the warehouse's raw layer with dlt (dlthub), into DuckDB locally or Snowflake.

    python ingestion/pipelines.py                       # all sources -> DuckDB (DPL_WAREHOUSE, default warehouse/lab.duckdb)
    python ingestion/pipelines.py --offline             # ECB rates from data/sample instead of the live API
    python ingestion/pipelines.py --fund-attributes v2  # the 11 Nov change of a fund's attributes (for the SCD2 snapshot)
    python ingestion/pipelines.py --destination snowflake   # credentials from DESTINATION__SNOWFLAKE__CREDENTIALS__*

What each resource shows:
  ecb_fx_rates     a REST API, incremental (only dates after the last one loaded), merge on (currency, rate_date)
  trades           nested JSON custodian messages (dlt flattens them), incremental on updated_at, every version kept
                   (merge on trade_id + version), a frozen schema contract: a new field in the feed fails the load
  settlements,     merge on their business keys: re-running a load never duplicates rows
  positions, flows
  reference data   replace (small, full reloads), fund attributes merged on fund_id (the snapshot keeps the history)
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path

import dlt
from dlt.sources.helpers import requests

ROOT = Path(__file__).resolve().parents[1]
ECB_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.{ccys}.EUR.SP00.A"
CURRENCIES = ["DKK", "NOK", "SEK", "CHF", "GBP", "USD"]


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def ecb_rows(text: str):
    for r in csv.DictReader(io.StringIO(text)):
        yield {"currency": r["CURRENCY"], "rate_date": r["TIME_PERIOD"], "units_per_eur": float(r["OBS_VALUE"]),
               "source": "ECB euro foreign exchange reference rates"}


@dlt.resource(name="fx_rates", primary_key=["currency", "rate_date"], write_disposition="merge")
def ecb_fx_rates(offline: bool, sample: Path,
                 rate_date=dlt.sources.incremental("rate_date", initial_value="2025-12-15")):
    """Euro reference rates (units of currency per 1 EUR). Live from the ECB Data Portal, or the committed sample."""
    # Read the cursor once, before yielding: dlt moves last_value forward as rows stream through this run.
    since = rate_date.last_value
    if offline:
        yield from (r for r in ecb_rows(sample.read_text(encoding="utf-8")) if r["rate_date"] >= since)
        return
    url = ECB_URL.format(ccys="+".join(CURRENCIES))
    resp = requests.get(url, params={"startPeriod": since, "format": "csvdata"}, timeout=60)
    resp.raise_for_status()
    yield from ecb_rows(resp.text)


@dlt.resource(name="trades", primary_key=["trade_id", "version"], write_disposition="merge",
              schema_contract={"tables": "evolve", "columns": "freeze", "data_type": "freeze"})
def custodian_trades(folder: Path, updated_at=dlt.sources.incremental("updated_at", initial_value="2026-01-01T00:00:00Z")):
    """Custodian trade messages (nested JSON); amendments arrive as a new version of the same trade_id."""
    for path in sorted(folder.glob("trades_*.json")):
        yield json.loads(path.read_text(encoding="utf-8"))


@dlt.source(name="custody")
def custody(data: Path):
    yield custodian_trades(data / "custody/trades")
    yield dlt.resource(read_csv(data / "custody/settlements.csv"), name="settlements",
                       primary_key="trade_id", write_disposition="merge")
    yield dlt.resource(read_csv(data / "custody/custodian_positions.csv"), name="custodian_positions",
                       primary_key=["fund_id", "isin", "position_date"], write_disposition="merge")
    yield dlt.resource(read_csv(data / "custody/opening_positions.csv"), name="opening_positions",
                       write_disposition="replace")


@dlt.source(name="reference")
def reference(data: Path, attributes: str):
    for name in ("funds", "share_classes", "securities"):
        yield dlt.resource(read_csv(data / f"reference/{name}.csv"), name=name, write_disposition="replace")
    yield dlt.resource(read_csv(data / f"reference/fund_attributes_{attributes}.csv"), name="fund_attributes",
                       primary_key="fund_id", write_disposition="merge")


@dlt.source(name="market")
def market(data: Path):
    yield dlt.resource(read_csv(data / "market/prices.csv"), name="prices",
                       primary_key=["isin", "price_date"], write_disposition="merge")


@dlt.source(name="transfer_agent")
def transfer_agent(data: Path):
    yield dlt.resource(read_csv(data / "transfer_agent/flows.csv"), name="flows",
                       primary_key="flow_id", write_disposition="merge")


def destination(name: str):
    if name == "duckdb":
        path = Path(os.environ.get("DPL_WAREHOUSE", ROOT / "warehouse/lab.duckdb"))
        path.parent.mkdir(parents=True, exist_ok=True)
        return dlt.destinations.duckdb(str(path))
    return name                                  # "snowflake": credentials from env / .dlt/secrets.toml


def main() -> None:
    ap = argparse.ArgumentParser(description="Load the raw layer with dlt.")
    ap.add_argument("--data", default=str(ROOT / "data"))
    ap.add_argument("--destination", default="duckdb", choices=["duckdb", "snowflake"])
    ap.add_argument("--offline", action="store_true", help="ECB rates from data/sample/ecb_fx_rates.csv")
    ap.add_argument("--fund-attributes", default="v1", choices=["v1", "v2"])
    ap.add_argument("--only", nargs="*", help="sources to load: ecb reference market custody transfer_agent")
    args = ap.parse_args()
    data, dest = Path(args.data), destination(args.destination)
    wanted = set(args.only or ["ecb", "reference", "market", "custody", "transfer_agent"])
    jobs = {
        "ecb": ("raw_ecb", lambda: ecb_fx_rates(args.offline, ROOT / "data/sample/ecb_fx_rates.csv")),
        "reference": ("raw_reference", lambda: reference(data, args.fund_attributes)),
        "market": ("raw_market", lambda: market(data)),
        "custody": ("raw_custody", lambda: custody(data)),
        "transfer_agent": ("raw_transfer_agent", lambda: transfer_agent(data)),
    }
    for key, (dataset, make) in jobs.items():
        if key not in wanted:
            continue
        pipeline = dlt.pipeline(pipeline_name=f"dpl_{key}", destination=dest, dataset_name=dataset,
                                pipelines_dir=os.environ.get("DPL_DLT_DIR"))
        info = pipeline.run(make())
        rows = {t: n for t, n in (pipeline.last_trace.last_normalize_info.row_counts or {}).items()
                if not t.startswith("_dlt")}
        print(f"{dataset:<20} {rows}  ({'ok' if not info.has_failed_jobs else 'FAILED'})")


if __name__ == "__main__":
    main()
