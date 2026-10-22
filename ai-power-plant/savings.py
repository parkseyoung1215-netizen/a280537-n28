"""
AI neighborhood power plant - step 1: how much can one household save?

Question: if a household on a dynamic electricity tariff in Germany puts
ordinary appliances (washer, dishwasher, dryer, e-bike charger) on smart
plugs, and the plug starts each run in the cheapest time instead of at the
usual evening time, how much money does it save in a year?

Data: real German day-ahead prices (bidding zone DE-LU, 15-minute steps)
from the Energy-Charts API (Fraunhofer ISE), data by Bundesnetzagentur |
SMARD.de, licence CC BY 4.0.

Run:  python3 savings.py
      python3 savings.py --start 2025-10-21 --end 2026-10-21
No extra packages needed (standard library only).
"""

import argparse
import json
import os
import urllib.request
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")
VAT = 1.19  # German VAT on the electricity price
API = "https://api.energy-charts.info/price?bzn=DE-LU&start={start}&end={end}"

# Appliances a renter can control with a smart plug.
# kwh: energy per run, hours: run length, habit: usual start hour (local time),
# runs: runs per year. Change these to match your own home.
DEVICES = [
    {"name": "washer",     "kwh": 1.0, "hours": 2, "habit": 19, "runs": 150},
    {"name": "dishwasher", "kwh": 1.0, "hours": 3, "habit": 20, "runs": 200},
    {"name": "dryer",      "kwh": 2.0, "hours": 2, "habit": 19, "runs": 100},
    {"name": "ebike",      "kwh": 0.5, "hours": 4, "habit": 19, "runs": 150},
]

# How long after the usual start time the run may wait (hours).
# 18 h from 19:00 means "finished by about 13:00 the next day".
# Day-ahead prices for tomorrow are published around 13:00 today,
# so at 19:00 all prices in this window are already known.
WINDOWS = [6, 12, 18]


def load_prices(start, end, cache_dir="data"):
    """Download prices once and keep a local copy."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"prices_DE-LU_{start}_{end}.json")
    if not os.path.exists(path):
        url = API.format(start=start, end=end)
        print(f"Downloading {url}")
        with urllib.request.urlopen(url, timeout=60) as r:
            data = json.load(r)
        with open(path, "w") as f:
            json.dump(data, f)
    with open(path) as f:
        data = json.load(f)
    return data["unix_seconds"], data["price"]  # price in EUR/MWh


def block_mean(prices, i, n):
    return sum(prices[i:i + n]) / n


def simulate(times, prices, device, window_h):
    step_s = times[1] - times[0]           # 900 s = 15 minutes
    per_hour = 3600 // step_s
    n = device["hours"] * per_hour         # run length in steps
    w = window_h * per_hour                # window length in steps

    local = [datetime.fromtimestamp(t, BERLIN) for t in times]
    starts = [i for i, d in enumerate(local)
              if d.hour == device["habit"] and d.minute == 0]

    base_sum = smart_sum = 0.0
    days = 0
    chosen_hours = Counter()
    for i0 in starts:
        last = i0 + w - n
        if last + n > len(prices):
            continue
        base = block_mean(prices, i0, n)
        best_i = min(range(i0, last + 1), key=lambda i: block_mean(prices, i, n))
        base_sum += base
        smart_sum += block_mean(prices, best_i, n)
        chosen_hours[local[best_i].hour] += 1
        days += 1

    base_avg = base_sum / days
    smart_avg = smart_sum / days
    # EUR/MWh -> EUR/kWh, times energy per run, plus VAT
    per_run_eur = (base_avg - smart_avg) / 1000 * device["kwh"] * VAT
    return {
        "days": days,
        "usual_price": base_avg,
        "smart_price": smart_avg,
        "per_run_eur": per_run_eur,
        "per_year_eur": per_run_eur * device["runs"],
        "top_start_hours": chosen_hours.most_common(3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-10-21")
    ap.add_argument("--end", default="2026-10-21")
    args = ap.parse_args()

    times, prices = load_prices(args.start, args.end)
    print(f"{len(prices)} price points, {args.start} to {args.end}")
    print(f"average day-ahead price: {sum(prices) / len(prices):.1f} EUR/MWh")
    print(f"share of negative prices: {100 * sum(p < 0 for p in prices) / len(prices):.1f}%")

    results = {}
    for w in WINDOWS:
        print(f"\n=== may wait up to {w} h ===")
        print(f"{'device':<11}{'usual':>8}{'smart':>8}{'ct/run':>8}{'EUR/yr':>8}  usual start -> chosen start")
        total = 0.0
        results[w] = {}
        for d in DEVICES:
            r = simulate(times, prices, d, w)
            results[w][d["name"]] = r
            total += r["per_year_eur"]
            tops = ", ".join(f"{h}:00 ({c}d)" for h, c in r["top_start_hours"])
            print(f"{d['name']:<11}{r['usual_price']:>8.1f}{r['smart_price']:>8.1f}"
                  f"{100 * r['per_run_eur']:>8.2f}{r['per_year_eur']:>8.2f}  {d['habit']}:00 -> {tops}")
        print(f"{'total':<11}{'':>24}{total:>8.2f} EUR per year")
        results[w]["total_eur_per_year"] = total

    os.makedirs("results", exist_ok=True)
    out = os.path.join("results", f"savings_{args.start}_{args.end}.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nsaved {out}")
    print("(usual/smart = average day-ahead price during the run, EUR/MWh)")


if __name__ == "__main__":
    main()
