"""
AI neighborhood power plant - step 2: what changes when we group homes?

A neighborhood of 100 homes. Some homes have solar panels on the roof.
Since 1 June 2026, German law (Energy Sharing, section 42c EnWG) lets
neighbors use that solar power through the public grid.

Three ways to run the same washers, dishwashers, dryers and e-bike chargers:
  none   - everyone starts at the usual evening time
  price  - each home's smart plug picks the cheapest time (step 1)
  neigh  - the AI plans for the whole neighborhood: first fill hours where
           neighbors' solar power would otherwise be sent to the grid,
           then pick cheap hours

Data: real German day-ahead prices and real German solar generation
(15-minute steps) from the Energy-Charts API (Fraunhofer ISE),
Bundesnetzagentur | SMARD.de, CC BY 4.0.

Run:  python3 neighborhood.py          (takes a few minutes)
No extra packages needed (standard library only).
"""

import json
import os
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from savings import DEVICES, load_prices

BERLIN = ZoneInfo("Europe/Berlin")
START, END = "2025-10-21", "2026-10-21"
SOLAR_API = "https://api.energy-charts.info/public_power?country=de&start={start}&end={end}"

HOMES = 100
PV_HOMES_LIST = [10, 30, 50]  # how many of the 100 homes have solar panels
KWP = 8                       # solar size per roof (kW peak)
YIELD = 950                   # kWh per kWp per year (typical for Germany)
BASE_KWH = 2000               # other electricity use per home per year (not shiftable)
WINDOW_H = 18                 # a run may wait up to 18 h (same as step 1)
VAT = 1.19

# Value of one shared kWh (ct/kWh, without VAT):
# the neighbor no longer buys it from a supplier (energy part of the price,
# BDEW August 2026: 15.17 ct), and the roof owner no longer gets the
# feed-in tariff for it (small roofs from August 2026: 7.70 ct).
# Grid fees and levies are paid in full under Energy Sharing, so they do not change.
ENERGY_PART = 15.17
FEED_IN = 7.70

# Usual daily shape of the non-shiftable use, hour 0..23 (simple assumption)
SHAPE = [0.55, 0.45, 0.4, 0.4, 0.4, 0.5, 0.8, 1.1, 1.1, 1.0, 1.0, 1.05,
         1.1, 1.0, 0.95, 0.95, 1.0, 1.2, 1.45, 1.55, 1.5, 1.35, 1.1, 0.8]


def load_solar(start, end, cache_dir="data"):
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"public_power_DE_{start}_{end}.json")
    if not os.path.exists(path):
        url = SOLAR_API.format(start=start, end=end)
        print(f"Downloading {url}")
        with urllib.request.urlopen(url, timeout=120) as r:
            data = json.load(r)
        with open(path, "w") as f:
            json.dump(data, f)
    with open(path) as f:
        data = json.load(f)
    solar = next(p["data"] for p in data["production_types"] if p["name"] == "Solar")
    return data["unix_seconds"], solar


def build_jobs(hours, minutes):
    """Which home runs which appliance on which day, and its usual start slot.
    Uses a fixed rule instead of random numbers so results are repeatable."""
    n = len(hours)
    day_starts = [i for i in range(n) if hours[i] == 0 and minutes[i] == 0]
    jobs = []
    for h in range(HOMES):
        for di, dv in enumerate(DEVICES):
            q = dv["hours"] * 4
            limit = round(dv["runs"] / 365 * 1000)
            for d, ds in enumerate(day_starts):
                if (h * 7919 + d * 104729 + di * 15485863) % 1000 >= limit:
                    continue
                offset = ((h * 31 + di * 17) % 3) * 2  # usual start 0, 30 or 60 min late
                i0 = ds + dv["habit"] * 4 + offset
                if i0 + WINDOW_H * 4 > n:
                    continue
                jobs.append((h, q, dv["kwh"] / q, i0))  # home, slots, kWh per slot, usual start
    return jobs


def main():
    times, prices = load_prices(START, END)
    stimes, solar = load_solar(START, END)
    assert stimes == times, "price and solar time steps do not match"
    n = len(times)

    local = [datetime.fromtimestamp(t, BERLIN) for t in times]
    hours = [d.hour for d in local]
    minutes = [d.minute for d in local]

    wsum = sum(SHAPE[h] for h in hours)
    base = [BASE_KWH * SHAPE[h] / wsum for h in hours]        # kWh per slot per home
    ssum = sum(solar)
    pv = [s / ssum * YIELD * KWP for s in solar]               # kWh per slot per solar home

    jobs = build_jobs(hours, minutes)
    w = WINDOW_H * 4
    print(f"{len(jobs)} appliance runs in a year for {HOMES} homes")

    # cheapest start for each run (same rule as step 1)
    price_start = []
    for _, q, _, i0 in jobs:
        best, bi = float("inf"), i0
        for i in range(i0, i0 + w - q + 1):
            m = sum(prices[i:i + q]) / q
            if m < best:
                best, bi = m, i
        price_start.append(bi)

    def neighborhood_start(pv_homes):
        free = [pv_homes * pv[i] - HOMES * base[i] for i in range(n)]  # solar not yet used
        order = sorted(range(len(jobs)), key=lambda k: (jobs[k][3], -jobs[k][1] * jobs[k][2], k))
        start = [0] * len(jobs)
        for k in order:
            _, q, e, i0 = jobs[k]
            best, bi = -1e18, i0
            for i in range(i0, i0 + w - q + 1):
                cov = pc = 0.0
                for t in range(q):
                    cov += min(e, max(0.0, free[i + t]))
                    pc += prices[i + t]
                score = cov * 1000 - pc * e / 1000
                if score > best + 1e-12:
                    best, bi = score, i
            start[k] = bi
            for t in range(q):
                free[bi + t] -= e
        return start

    def account(start, pv_homes):
        flex = [[0.0] * n for _ in range(HOMES)]
        for k, (h, q, e, _) in enumerate(jobs):
            for t in range(q):
                flex[h][start[k] + t] += e
        self_use = shared = feed = cost = 0.0
        for i in range(n):
            surplus = need = 0.0
            for h in range(HOMES):
                f = flex[h][i]
                d = base[i] + f
                cost += f * prices[i] / 1000 * VAT
                if h < pv_homes:
                    s = min(pv[i], d)
                    self_use += s
                    surplus += pv[i] - s
                else:
                    need += d
            sh = min(surplus, need)
            shared += sh
            feed += surplus - sh
        return {
            "solar_mwh": pv_homes * KWP * YIELD / 1000,
            "shared_mwh": shared / 1000,
            "fed_to_grid_mwh": feed / 1000,
            "appliance_cost_eur": cost,
            "sharing_value_eur": shared * (ENERGY_PART - FEED_IN) / 100,
        }

    results = {}
    usual = [j[3] for j in jobs]
    for pvh in PV_HOMES_LIST:
        print(f"\n=== {pvh} of {HOMES} homes have solar ({pvh * KWP} kWp) ===")
        r = {
            "none": account(usual, pvh),
            "price": account(price_start, pvh),
            "neigh": account(neighborhood_start(pvh), pvh),
        }
        results[pvh] = r
        base_cost = r["none"]["appliance_cost_eur"]
        base_share = r["none"]["sharing_value_eur"]
        print(f"{'mode':<7}{'shared MWh':>11}{'to grid MWh':>12}{'appl. cost':>11}{'sharing':>9}{'gain vs none':>13}")
        for mode, x in r.items():
            gain = (base_cost - x["appliance_cost_eur"]) + (x["sharing_value_eur"] - base_share)
            print(f"{mode:<7}{x['shared_mwh']:>11.1f}{x['fed_to_grid_mwh']:>12.1f}"
                  f"{x['appliance_cost_eur']:>11.0f}{x['sharing_value_eur']:>9.0f}{gain:>13.0f}")
    print("\n(EUR per year for all 100 homes; sharing = value of shared solar, split between roof owners and neighbors)")

    os.makedirs("results", exist_ok=True)
    out = os.path.join("results", f"neighborhood_{START}_{END}.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
