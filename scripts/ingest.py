"""Download IESO's monthly Generator Output and Capability report and clean it into Parquet.

Each month becomes data/clean/gen_YYYYMM.parquet with one row per generator per hour:
timestamp, generator_name, plant, fuel_type, output_mw, capability_mw.
Safe to rerun: downloaded months are cached and each Parquet file is overwritten, never appended.
"""
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
URL = "https://reports-public.ieso.ca/public/GenOutputCapabilityMonth/PUB_GenOutputCapabilityMonth_{}.csv"
START = pd.Period("2019-05", "M")  # first month IESO publishes in this format
END = pd.Period.now("M") - 1  # latest complete month
REFRESH = 2  # IESO keeps revising recent months, so always re-download the last few
HOURS = [f"Hour {h}" for h in range(1, 25)]
PLANTS = {"BRUCE": "Bruce", "DARLINGTON": "Darlington", "PICKERING": "Pickering"}


def download(month, force):
    path = RAW / f"{month:%Y%m}.csv"
    if force or not path.exists():
        r = requests.get(URL.format(f"{month:%Y%m}"), timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
        print(f"downloaded {month}")
    return path


def clean(path):
    # 3 metadata lines precede the header; usecols drops the empty column left by each row's trailing comma
    # missing hours appear as a single space
    df = pd.read_csv(path, skiprows=3, usecols=["Delivery Date", "Generator", "Fuel Type", "Measurement", *HOURS],
                     na_values=[" "])
    df = df[df["Measurement"].isin(["Output", "Capability"])]
    long = df.melt(id_vars=["Delivery Date", "Generator", "Fuel Type", "Measurement"], value_vars=HOURS,
                   var_name="hour", value_name="mw")
    # "Hour 1" is 00:00-01:00; IESO uses Eastern Standard Time all year (no daylight saving), so timestamps stay naive
    long["timestamp"] = pd.to_datetime(long["Delivery Date"]) + pd.to_timedelta(long["hour"].str[5:].astype(int) - 1, unit="h")
    out = long.pivot(index=["timestamp", "Generator", "Fuel Type"], columns="Measurement", values="mw").reset_index()
    out.columns.name = None
    out = out.rename(columns={"Generator": "generator_name", "Fuel Type": "fuel_type",
                              "Output": "output_mw", "Capability": "capability_mw"})
    nuclear = out["fuel_type"] == "NUCLEAR"
    out["plant"] = out["generator_name"].str.extract(f"^({'|'.join(PLANTS)})", expand=False).map(PLANTS).where(nuclear)
    return out[["timestamp", "generator_name", "plant", "fuel_type", "output_mw", "capability_mw"]]


def check(df):
    assert not df.duplicated(["timestamp", "generator_name"]).any(), "duplicate (timestamp, generator) rows"
    nuclear = df[df["fuel_type"] == "NUCLEAR"]
    assert nuclear["plant"].notna().all(), f"unmapped nuclear units: {nuclear.loc[nuclear['plant'].isna(), 'generator_name'].unique()}"
    assert (nuclear["output_mw"].dropna() >= 0).all(), "negative nuclear output"
    units = sorted(nuclear["generator_name"].unique())
    print(f"{len(df):,} rows, {df['timestamp'].min()} to {df['timestamp'].max()}, {len(units)} nuclear units: {', '.join(units)}")


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    CLEAN.mkdir(parents=True, exist_ok=True)
    for month in pd.period_range(START, END, freq="M"):
        raw = download(month, force=month > END - REFRESH)
        clean(raw).to_parquet(CLEAN / f"gen_{month:%Y%m}.parquet", index=False)
    check(pd.read_parquet(CLEAN))


if __name__ == "__main__":
    main()
