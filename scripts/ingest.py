"""Download IESO public reports and clean them into Parquet.

- Generator Output and Capability (monthly): data/clean/gen_YYYYMM.parquet, one row per generator per hour:
  timestamp, generator_name, plant, fuel_type, output_mw, capability_mw.
- Intertie Schedule and Flow (yearly): data/clean/interties_YYYY.parquet, one row per hour of Ontario totals:
  timestamp, import_mw, export_mw, net_flow_mw.
- Prices: data/clean/prices_hoep_YYYY.parquet (HOEP, yearly CSVs, until Apr 2025) and
  data/clean/prices_ozp.parquet (day-ahead Ontario Zonal Price, daily XMLs, new market):
  timestamp, price_cad_mwh, price_type.
Safe to rerun: downloaded files are cached and each Parquet file is overwritten, never appended.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
URL = "https://reports-public.ieso.ca/public/GenOutputCapabilityMonth/PUB_GenOutputCapabilityMonth_{}.csv"
INTERTIE_URL = "https://reports-public.ieso.ca/public/IntertieScheduleFlowYear/PUB_IntertieScheduleFlowYear_{}.csv"
HOEP_URL = "https://reports-public.ieso.ca/public/PriceHOEPPredispOR/PUB_PriceHOEPPredispOR_{}.csv"
HOEP_LAST_YEAR = 2025  # HOEP ended when the renewed market started on May 1, 2025
OZP_DIR = "https://reports-public.ieso.ca/public/DAHourlyOntarioZonalPrice/"
OZP_NS = {"i": "http://www.ieso.ca/schema"}
START = pd.Period("2019-05", "M")  # first month IESO publishes in this format
END = pd.Period.now("M") - 1  # latest complete month
REFRESH = 2  # IESO keeps revising recent months, so always re-download the last few
HOURS = [f"Hour {h}" for h in range(1, 25)]
PLANTS = {"BRUCE": "Bruce", "DARLINGTON": "Darlington", "PICKERING": "Pickering"}


def download(url, path, force):
    if force or not path.exists():
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
        print(f"downloaded {path.name}")
    return path


def hour_to_ts(dates, hours):
    # IESO "Hour 1" is 00:00-01:00 Eastern Standard Time all year (no daylight saving), so timestamps stay naive
    return pd.to_datetime(dates) + pd.to_timedelta(hours.astype(int) - 1, unit="h")


def clean(path):
    # 3 metadata lines precede the header; usecols drops the empty column left by each row's trailing comma
    # missing hours appear as a single space
    df = pd.read_csv(path, skiprows=3, usecols=["Delivery Date", "Generator", "Fuel Type", "Measurement", *HOURS],
                     na_values=[" "])
    df = df[df["Measurement"].isin(["Output", "Capability"])]
    long = df.melt(id_vars=["Delivery Date", "Generator", "Fuel Type", "Measurement"], value_vars=HOURS,
                   var_name="hour", value_name="mw")
    long["timestamp"] = hour_to_ts(long["Delivery Date"], long["hour"].str[5:])
    out = long.pivot(index=["timestamp", "Generator", "Fuel Type"], columns="Measurement", values="mw").reset_index()
    out.columns.name = None
    out = out.rename(columns={"Generator": "generator_name", "Fuel Type": "fuel_type",
                              "Output": "output_mw", "Capability": "capability_mw"})
    nuclear = out["fuel_type"] == "NUCLEAR"
    out["plant"] = out["generator_name"].str.extract(f"^({'|'.join(PLANTS)})", expand=False).map(PLANTS).where(nuclear)
    return out[["timestamp", "generator_name", "plant", "fuel_type", "output_mw", "capability_mw"]]


def clean_interties(path):
    # 3 metadata lines, then a row of intertie names (each repeated over its Imp/Exp/Flow columns), then the header
    names = path.read_text(encoding="utf-8").splitlines()[3].rstrip(",").split(",")
    assert names[-3:] == ["Total"] * 3, f"{path.name}: last column group is not Total, layout changed"
    df = pd.read_csv(path, skiprows=5, header=None, na_values=[" "]).iloc[:, :len(names)]
    return pd.DataFrame({"timestamp": hour_to_ts(df[0], df[1]),
                         "import_mw": df.iloc[:, -3], "export_mw": df.iloc[:, -2], "net_flow_mw": df.iloc[:, -1]})


def clean_hoep(path):
    # 3 metadata lines, then Date,Hour,HOEP,... (predispatch and reserve columns are not needed)
    df = pd.read_csv(path, skiprows=3, usecols=["Date", "Hour", "HOEP"], na_values=[" "])
    return pd.DataFrame({"timestamp": hour_to_ts(df["Date"], df["Hour"]),
                         "price_cad_mwh": df["HOEP"], "price_type": "HOEP"})


def clean_ozp(path):
    doc = ET.parse(path).getroot()
    day = doc.find(".//i:DeliveryDate", OZP_NS).text
    hours = doc.findall(".//i:HourlyPriceComponents", OZP_NS)
    return pd.DataFrame({"timestamp": hour_to_ts(pd.Series([day] * len(hours)),
                                                 pd.Series([h.find("i:PricingHour", OZP_NS).text for h in hours])),
                         "price_cad_mwh": [float(h.find("i:ZonalPrice", OZP_NS).text) for h in hours],
                         "price_type": "DA_OZP"})


def download_ozp():
    # IESO keeps only ~90 days online, so every day ever downloaded stays cached in data/raw/ozp/
    folder = RAW / "ozp"
    folder.mkdir(exist_ok=True)
    days = sorted(set(re.findall(r"PUB_DAHourlyOntarioZonalPrice_(\d{8})\.xml", requests.get(OZP_DIR, timeout=60).text)))
    for day in days:
        # the newest few days can still be revised; the unversioned file is always the latest version
        download(f"{OZP_DIR}PUB_DAHourlyOntarioZonalPrice_{day}.xml", folder / f"{day}.xml", force=day >= days[-3])
    return sorted(folder.glob("*.xml"))


def check_prices(df):
    assert not df["timestamp"].duplicated().any(), "duplicate price hours"
    for kind, g in df.groupby("price_type"):
        print(f"prices {kind}: {len(g):,} hours, {g['timestamp'].min()} to {g['timestamp'].max()}, "
              f"median ${g['price_cad_mwh'].median():.2f}/MWh")


def check_interties(df):
    assert not df["timestamp"].duplicated().any(), "duplicate intertie hours"
    print(f"interties: {len(df):,} hours, {df['timestamp'].min()} to {df['timestamp'].max()}")


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
        raw = download(URL.format(f"{month:%Y%m}"), RAW / f"{month:%Y%m}.csv", force=month > END - REFRESH)
        clean(raw).to_parquet(CLEAN / f"gen_{month:%Y%m}.parquet", index=False)
    check(pd.concat(map(pd.read_parquet, sorted(CLEAN.glob("gen_*.parquet")))))

    for year in range(START.year, END.year + 1):
        # the current year's file grows daily; last year's may still be revised early in the year
        raw = download(INTERTIE_URL.format(year), RAW / f"interties_{year}.csv", force=year >= END.year - 1)
        clean_interties(raw).to_parquet(CLEAN / f"interties_{year}.parquet", index=False)
    check_interties(pd.concat(map(pd.read_parquet, sorted(CLEAN.glob("interties_*.parquet")))))

    for year in range(START.year, HOEP_LAST_YEAR + 1):
        raw = download(HOEP_URL.format(year), RAW / f"hoep_{year}.csv", force=False)  # all final, HOEP has ended
        clean_hoep(raw).to_parquet(CLEAN / f"prices_hoep_{year}.parquet", index=False)
    pd.concat(map(clean_ozp, download_ozp())).to_parquet(CLEAN / "prices_ozp.parquet", index=False)
    check_prices(pd.concat(map(pd.read_parquet, sorted(CLEAN.glob("prices_*.parquet")))))


if __name__ == "__main__":
    main()
