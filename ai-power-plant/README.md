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

## Step 2: What changes when we group 100 homes?

Since 1 June 2026, German law (Energy Sharing, section 42c EnWG) lets neighbors use
solar power from roofs in the same area through the public grid. Grid fees and levies
are still paid in full, so one shared kWh is worth the energy part of the price
(15.17 ct, BDEW August 2026) minus the feed-in tariff the roof owner gives up
(7.70 ct for small roofs from August 2026): about 7.5 ct, split between both sides.

```
python3 neighborhood.py
```

A neighborhood of 100 homes, each with the same four appliances as in step 1, plus
2,000 kWh a year of other use with a simple daily shape. Some homes have 8 kWp of
solar, shaped like real German solar generation over the same year.

- **none**: everyone starts at the usual evening time
- **price**: each smart plug picks the cheapest time on its own (step 1)
- **neigh**: the AI plans for the whole neighborhood: fill hours where solar would
  otherwise go to the grid first, then cheap hours

### Result (EUR per year for all 100 homes, gain compared with "none")

| Homes with solar | price | neigh | Value of shared solar with no AI |
|------------------|-------|-------|----------------------------------|
| 10               | 7,908 | 7,890 | 3,803 |
| 30               | 9,469 | 9,418 | 4,163 |
| 50               | 9,066 | 8,992 | 3,248 |

- Grouping does not raise the value per home much: about EUR 80 to 95 per home per year.
  Most of it is still the step 1 price saving.
- Planning for the whole neighborhood (neigh) is no better than each plug following the
  price on its own. Cheap hours and solar hours are mostly the same hours.
- The evening peak (19:00 to 21:00) of the 100 homes drops from about 81 kW to 37 kW
  (10 solar homes). This helps the grid, but today no one pays households for it
  with appliances this small.

## Data

Day-ahead prices from the [Energy-Charts API](https://api.energy-charts.info/) (Fraunhofer ISE).
Data: Bundesnetzagentur | SMARD.de, CC BY 4.0. Solar generation from the same API
(`public_power`, Germany). Price breakdown: BDEW Strompreisanalyse August 2026.
