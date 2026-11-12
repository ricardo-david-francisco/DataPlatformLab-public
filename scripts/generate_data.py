"""Generate the lab's dataset: a fictional European asset manager, Boreal Asset Management, January to November 2026.

Reference data is real and public: the securities are well-known listed companies with their real ISINs, and the euro
FX rates come live from the ECB (ingestion/pipelines.py). Everything else is synthetic and seeded, so every run gives
the same files:

    data/reference/  funds.csv, share_classes.csv, securities.csv, fund_attributes_v1.csv, fund_attributes_v2.csv
    data/market/     prices.csv                  (a seeded random walk per security, business days)
    data/custody/    trades/trades_YYYY-MM.json  (custodian messages, nested JSON; amendments as new versions)
                     settlements.csv             (T+2, a few fails), custodian_positions.csv (with planted breaks)
                     opening_positions.csv
    data/transfer_agent/ flows.csv               (subscriptions and redemptions per share class)

The legacy SQL Server warehouse isn't data here: it's code (migration/legacy/*.sql, T-SQL). The migration translates
that code and runs it, and the parity check compares its output with the new dbt marts.

    python scripts/generate_data.py [--out data] [--seed 7]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import random
from collections import defaultdict
from pathlib import Path

START, END = dt.date(2026, 1, 2), dt.date(2026, 11, 12)

# Real, public identifiers of well-known listed companies (ISIN, name, country, currency, start price, sector).
SECURITIES = [
    ("DK0062498333", "Novo Nordisk B", "DK", "DKK", 420.0, "Health care"),
    ("DK0061539921", "Vestas Wind Systems", "DK", "DKK", 110.0, "Industrials"),
    ("DK0060094928", "Orsted", "DK", "DKK", 140.0, "Utilities"),
    ("DK0060079531", "DSV", "DK", "DKK", 1500.0, "Industrials"),
    ("DK0010274414", "Danske Bank", "DK", "DKK", 210.0, "Financials"),
    ("NO0010096985", "Equinor", "NO", "NOK", 260.0, "Energy"),
    ("NO0010161896", "DNB Bank", "NO", "NOK", 230.0, "Financials"),
    ("NO0010063308", "Telenor", "NO", "NOK", 150.0, "Communication"),
    ("NO0005052605", "Norsk Hydro", "NO", "NOK", 70.0, "Materials"),
    ("SE0000115446", "Volvo B", "SE", "SEK", 270.0, "Industrials"),
    ("SE0000108656", "Ericsson B", "SE", "SEK", 85.0, "Technology"),
    ("SE0015811963", "Investor B", "SE", "SEK", 300.0, "Financials"),
    ("SE0007100581", "Assa Abloy B", "SE", "SEK", 330.0, "Industrials"),
    ("SE0000667891", "Sandvik", "SE", "SEK", 210.0, "Industrials"),
    ("FI0009000681", "Nokia", "FI", "EUR", 5.0, "Technology"),
    ("FI0009013403", "Kone B", "FI", "EUR", 52.0, "Industrials"),
    ("FI0009013296", "Neste", "FI", "EUR", 14.0, "Energy"),
    ("FI0009005987", "UPM-Kymmene", "FI", "EUR", 25.0, "Materials"),
    ("NL0010273215", "ASML Holding", "NL", "EUR", 680.0, "Technology"),
    ("DE0007164600", "SAP", "DE", "EUR", 240.0, "Technology"),
    ("DE0007236101", "Siemens", "DE", "EUR", 190.0, "Industrials"),
    ("DE0008404005", "Allianz", "DE", "EUR", 320.0, "Financials"),
    ("FR0000121972", "Schneider Electric", "FR", "EUR", 240.0, "Industrials"),
    ("FR0000121014", "LVMH", "FR", "EUR", 620.0, "Consumer"),
    ("ES0144580Y14", "Iberdrola", "ES", "EUR", 14.0, "Utilities"),
    ("CH0038863350", "Nestle", "CH", "CHF", 80.0, "Consumer staples"),
    ("CH0012005267", "Novartis", "CH", "CHF", 90.0, "Health care"),
    ("CH0012032048", "Roche Holding", "CH", "CHF", 260.0, "Health care"),
    ("GB0009895292", "AstraZeneca", "GB", "GBP", 105.0, "Health care"),
    ("GB00B10RZP78", "Unilever", "GB", "GBP", 46.0, "Consumer staples"),
    ("US0378331005", "Apple", "US", "USD", 230.0, "Technology"),
    ("US5949181045", "Microsoft", "US", "USD", 420.0, "Technology"),
    ("US67066G1040", "NVIDIA", "US", "USD", 135.0, "Technology"),
    ("US4781601046", "Johnson & Johnson", "US", "USD", 150.0, "Health care"),
]
# Synthetic covered bonds (not real ISINs: the SYN prefix says so). Quoted per 100 nominal, in EUR or DKK.
BONDS = [(f"SYNCB{n:06d}", f"Covered bond {n}", c, cur, 100.0, "Covered bonds")
         for n, (c, cur) in enumerate([("DK", "DKK"), ("DK", "DKK"), ("SE", "SEK"), ("NO", "NOK"),
                                        ("FI", "EUR"), ("DE", "EUR"), ("FR", "EUR"), ("NL", "EUR")], 1)]

FUNDS = [  # fund_id, name, asset class, base ccy, universe filter
    ("BOR-NEU", "Boreal Northern Europe Equity", "Equity", lambda s: s[2] in ("DK", "NO", "SE", "FI")),
    ("BOR-CLT", "Boreal Climate Transition Equity", "Equity",
     lambda s: s[0] in ("DK0061539921", "DK0060094928", "FR0000121972", "DE0007236101", "ES0144580Y14",
                        "FI0009013296", "NL0010273215", "FI0009005987", "NO0005052605", "SE0007100581")),
    ("BOR-GQE", "Boreal Global Quality Equity", "Equity",
     lambda s: s[5] in ("Health care", "Consumer staples", "Technology") and s[2] in ("CH", "GB", "US", "DK", "DE")),
    ("BOR-ECV", "Boreal Euro Covered Bonds", "Fixed income", lambda s: s[0].startswith("SYN")),
    ("BOR-BAL", "Boreal Balanced Multi-Asset", "Multi-asset",
     lambda s: s[0].startswith("SYN") or s[0] in ("US5949181045", "NL0010273215", "DE0008404005", "CH0038863350",
                                                   "SE0015811963", "DK0062498333")),
]
SHARE_CLASSES = [  # suffix, investor type, yearly management fee rate for equity / bonds, share of the fund's AUM
    ("A-EUR", "Retail, accumulating", 0.0150, 0.0080, 0.45),
    ("I-EUR", "Institutional", 0.0080, 0.0040, 0.40),
    ("D-EUR", "Retail, with distributor fee", 0.0225, 0.0120, 0.15),
]
CUSTODIAN = "Custodian Bank Luxembourg (fictional)"


def business_days(a: dt.date, b: dt.date) -> list[dt.date]:
    days, d = [], a
    while d <= b:
        if d.weekday() < 5:
            days.append(d)
        d += dt.timedelta(days=1)
    return days


def write_csv(path: Path, header: list[str], rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)
            n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="data")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rnd = random.Random(args.seed)
    out = Path(args.out)
    days = business_days(START, END)
    universe = SECURITIES + BONDS

    # --- reference ---------------------------------------------------------------------------------------------
    write_csv(out / "reference/securities.csv", ["isin", "name", "country", "currency", "sector", "asset_class"],
              [(s[0], s[1], s[2], s[3], s[5], "Bond" if s[0].startswith("SYN") else "Equity") for s in universe])
    write_csv(out / "reference/funds.csv", ["fund_id", "fund_name", "asset_class", "base_currency", "domicile",
                                            "legal_form", "custodian"],
              [(f[0], f[1], f[2], "EUR", "LU", "SICAV sub-fund", CUSTODIAN) for f in FUNDS])
    write_csv(out / "reference/share_classes.csv", ["share_class_id", "fund_id", "share_class", "investor_type",
                                                    "mgmt_fee_rate", "aum_weight"],
              [(f"{f[0]}-{c[0]}", f[0], c[0], c[1], c[2] if f[2] == "Equity" else c[3], c[4])
               for f in FUNDS for c in SHARE_CLASSES])
    # Fund attributes change once (11 Nov): the SCD2 snapshot keeps both versions.
    attrs = [(f[0], f"PM team {i % 3 + 1}", 4 if f[2] == "Equity" else 2, "Article 9" if "Climate" in f[1] else "Article 8")
             for i, f in enumerate(FUNDS)]
    write_csv(out / "reference/fund_attributes_v1.csv", ["fund_id", "portfolio_manager", "risk_class", "sfdr_article"],
              attrs)
    changed = [(a[0], "PM team 4", 5, a[3]) if a[0] == "BOR-NEU" else a for a in attrs]
    write_csv(out / "reference/fund_attributes_v2.csv", ["fund_id", "portfolio_manager", "risk_class", "sfdr_article"],
              changed)

    # --- prices: a seeded random walk ----------------------------------------------------------------------------
    price = {s[0]: s[4] for s in universe}
    prices = []
    for d in days:
        for s in universe:
            vol = 0.002 if s[0].startswith("SYN") else 0.015
            price[s[0]] = round(price[s[0]] * math.exp(rnd.gauss(0.0002, vol)), 4)
            prices.append((s[0], d.isoformat(), price[s[0]], s[3]))
    write_csv(out / "market/prices.csv", ["isin", "price_date", "close_price", "currency"], prices)
    px = {(r[0], r[1]): r[2] for r in prices}

    # --- opening positions, trades with amendments --------------------------------------------------------------
    holdings: dict[tuple[str, str], float] = {}
    opening = []
    for f in FUNDS:
        names = [s for s in universe if f[3](s)]
        for s in names:
            qty = float(rnd.randrange(20, 200) * (100 if s[0].startswith("SYN") else 10) * (10 if s[4] < 50 else 1))
            holdings[(f[0], s[0])] = qty
            opening.append((f[0], s[0], START.isoformat(), qty))
    write_csv(out / "custody/opening_positions.csv", ["fund_id", "isin", "as_of_date", "quantity"], opening)

    trades, trade_id = [], 100000
    for d in days[1:]:
        for _ in range(rnd.randint(6, 14)):
            f = rnd.choice(FUNDS)
            names = [s for s in universe if f[3](s)]
            s = rnd.choice(names)
            key = (f[0], s[0])
            side = "BUY" if rnd.random() < 0.55 or holdings[key] < 50 else "SELL"
            qty = float(rnd.randrange(1, 20) * (100 if s[0].startswith("SYN") else 10))
            if side == "SELL":
                qty = min(qty, holdings[key] // 2)
                if qty <= 0:
                    side, qty = "BUY", 10.0
            trade_id += 1
            p = px[(s[0], d.isoformat())]
            t = {"trade_id": trade_id, "version": 1, "fund_id": f[0], "isin": s[0], "side": side, "quantity": qty,
                 "price": p, "currency": s[3], "trade_date": d.isoformat(), "broker": rnd.choice(["BRK-A", "BRK-B", "BRK-C"]),
                 "updated_at": f"{d.isoformat()}T{rnd.randint(9, 16):02d}:{rnd.randint(0, 59):02d}:00Z"}
            trades.append(t)
            final_qty = qty
            if rnd.random() < 0.05:                                      # an amendment later the same day
                final_qty = qty + (10.0 if side == "BUY" else -min(10.0, qty - 1)) if qty > 1 else qty
                trades.append({**t, "version": 2, "quantity": final_qty,
                               "updated_at": f"{d.isoformat()}T17:{rnd.randint(10, 59):02d}:00Z"})
            holdings[key] += final_qty if side == "BUY" else -final_qty

    # Custodian messages: nested JSON (dlt unnests them), one file per month.
    by_month = defaultdict(list)
    for t in trades:
        by_month[t["trade_date"][:7]].append({
            "message_id": f"MSG-{t['trade_id']}-{t['version']}", "trade_id": t["trade_id"], "version": t["version"],
            "fund_id": t["fund_id"], "updated_at": t["updated_at"], "trade_date": t["trade_date"],
            "instrument": {"isin": t["isin"], "currency": t["currency"]},
            "execution": {"side": t["side"], "quantity": t["quantity"], "price": t["price"], "broker": t["broker"]}})
    for month, msgs in by_month.items():
        p = out / "custody/trades" / f"trades_{month}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(msgs, indent=0), encoding="utf-8")

    # Settlements: T+2 business days; about 2% fail and settle 2 days late.
    latest = {}
    for t in trades:
        latest[t["trade_id"]] = t
    idx = {d: i for i, d in enumerate(days)}
    sett = []
    for t in latest.values():
        i = idx[dt.date.fromisoformat(t["trade_date"])]
        due = days[min(i + 2, len(days) - 1)]
        failed = rnd.random() < 0.02
        if failed and i + 4 < len(days):
            status, actual = "SETTLED_LATE", days[i + 4]
        elif failed:
            status, actual = "FAILED", None
        elif i + 2 >= len(days):
            status, actual = "PENDING", None
        else:
            status, actual = "SETTLED", due
        sett.append((t["trade_id"], due.isoformat(), actual.isoformat() if actual else "", status))
    write_csv(out / "custody/settlements.csv", ["trade_id", "intended_settlement_date", "actual_settlement_date",
                                                "status"], sett)

    # Custodian end-of-day positions for the last 5 business days: equal to ours, except 3 planted breaks.
    def position(fund: str, isin: str, upto: dt.date, versions: dict) -> float:
        q = next((o[3] for o in opening if o[0] == fund and o[1] == isin), 0.0)
        for t in versions.values():
            if t["fund_id"] == fund and t["isin"] == isin and t["trade_date"] <= upto.isoformat():
                q += t["quantity"] if t["side"] == "BUY" else -t["quantity"]
        return q

    custodian = []
    for d in days[-5:]:
        for (fund, isin) in sorted(holdings):
            q = position(fund, isin, d, latest)
            custodian.append([fund, isin, d.isoformat(), q])
    breaks = [("BOR-NEU", "SE0000115446", -100.0), ("BOR-GQE", "US5949181045", 25.0), ("BOR-ECV", "SYNCB000003", -500.0)]
    for fund, isin, delta in breaks:
        for row in custodian:
            if row[0] == fund and row[1] == isin and row[2] == days[-1].isoformat():
                row[3] += delta
    write_csv(out / "custody/custodian_positions.csv", ["fund_id", "isin", "position_date", "quantity"], custodian)

    # --- transfer agent: subscriptions and redemptions per share class ----------------------------------------------
    flows, fid = [], 0
    for d in days:
        for f in FUNDS:
            for c in SHARE_CLASSES:
                if rnd.random() < 0.35:
                    fid += 1
                    kind = "SUBSCRIPTION" if rnd.random() < 0.55 else "REDEMPTION"
                    flows.append((f"TA{fid:07d}", f"{f[0]}-{c[0]}", d.isoformat(), kind,
                                  round(rnd.uniform(5_000, 900_000), 2), "EUR"))
    write_csv(out / "transfer_agent/flows.csv", ["flow_id", "share_class_id", "trade_date", "flow_type", "amount",
                                                 "currency"], flows)

    print(f"wrote {len(universe)} securities, {len(FUNDS)} funds, {len(prices)} prices, {len(trades)} trade messages, "
          f"{len(sett)} settlements, {len(custodian)} custodian positions, {len(flows)} flows into {out}/")


if __name__ == "__main__":
    main()
