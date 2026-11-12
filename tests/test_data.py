"""The generated data: deterministic, and the real ISINs are valid."""
import csv
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check import isin_valid  # noqa: E402


def test_isin_check_digit():
    assert isin_valid("DK0062498333")          # Novo Nordisk B
    assert isin_valid("US0378331005")          # Apple
    assert not isin_valid("US0378331006")


def test_generator_is_deterministic(tmp_path):
    digests = []
    for run in ("a", "b"):
        out = tmp_path / run
        subprocess.run([sys.executable, str(ROOT / "scripts/generate_data.py"), "--out", str(out)], check=True)
        digests.append(hashlib.sha256((out / "market/prices.csv").read_bytes()).hexdigest())
    assert digests[0] == digests[1]


def test_real_isins_are_valid(tmp_path):
    subprocess.run([sys.executable, str(ROOT / "scripts/generate_data.py"), "--out", str(tmp_path)], check=True)
    rows = list(csv.DictReader((tmp_path / "reference/securities.csv").open(encoding="utf-8")))
    real = [r["isin"] for r in rows if not r["isin"].startswith("SYN")]
    assert real and all(isin_valid(i) for i in real)
