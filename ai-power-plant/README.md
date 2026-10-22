# AI Neighborhood Power Plant

An AI that lets ordinary homes, including renters with no battery or solar panel,
use electricity when it is cheap and clean, and later share it with neighbors.

## Step 1: How much can one household save?

A household on a dynamic tariff in Germany puts four ordinary appliances on smart plugs.
Instead of starting at the usual evening time, each run starts in the cheapest slot
within a waiting window. Prices are real German day-ahead prices (DE-LU, 15-minute steps)
for 2025-10-21 to 2026-10-21.

```
python3 savings.py
```

### Assumptions (edit `DEVICES` in `savings.py`)

| Appliance  | kWh per run | Run length | Usual start | Runs per year |
|------------|-------------|------------|-------------|---------------|
| Washer     | 1.0         | 2 h        | 19:00       | 150           |
| Dishwasher | 1.0         | 3 h        | 20:00       | 200           |
| Dryer      | 2.0         | 2 h        | 19:00       | 100           |
| E-bike     | 0.5         | 4 h        | 19:00       | 150           |

Only the market part of the price changes with time; grid fees and taxes stay the same,
so savings = price difference x energy x 1.19 (VAT).

### Result

| May wait up to | Mostly moves to | Savings per year (all 4) |
|----------------|-----------------|--------------------------|
| 6 h            | 23:00           | about EUR 28             |
| 12 h           | 01:00 to 03:00  | about EUR 40             |
| 18 h           | 11:00 (solar)   | about EUR 75             |

The usual evening slot (19:00 to 21:00) is the most expensive time of the day
(about 160 EUR/MWh on average). Around 13:00 it is about 51 EUR/MWh, and 5.4% of all
15-minute slots had negative prices.

## Data

Day-ahead prices from the [Energy-Charts API](https://api.energy-charts.info/) (Fraunhofer ISE).
Data: Bundesnetzagentur | SMARD.de, CC BY 4.0.
