# What-If World

The world as a book, and you are the author. Set up today's world, write an event
("Iran closes the Strait of Hormuz", "the Bank of Korea raises rates by 2 points",
"wheat harvests fall 30%"), and watch how the world reacts week by week.

## How it works

1. **World state** (`world.json`): 13 countries with 9 indicators each (growth, inflation,
   unemployment, central bank rate, stocks, currency, government approval, food prices,
   fuel prices) and 6 global markets (oil, gas, wheat, gold, shipping cost, market fear).
   Every number starts at 0 = "no change from today", so no starting levels are guessed.
2. **Game master** (`engine.py`): a language model reads the event, decides which parts of
   the world it touches, and lets governments, central banks and markets react.
3. **History as a ruler** (`cases.json`): the game master sizes each reaction by comparing
   with real past events (1973 oil embargo, 2008 crisis, 2022 invasion of Ukraine, 2026
   Hormuz closure, ...) and shows which case it used. Cases from outside the list are marked.
4. **Code checks the AI**: every proposed change is checked (real country, real indicator,
   weekly limit) before it touches the world. Wrong ones are dropped and shown.
5. **Story**: each week is written as a short story with the numbers that changed and why.

## Run

1. Put your OpenAI key in a file `what-if-world/.env`:
   ```
   OPENAI_API_KEY=sk-...
   ```
2. Start:
   ```
   cd what-if-world
   python3 app.py
   ```
3. The browser opens at http://localhost:8000.

No extra packages needed. Model: `gpt-4o-mini` by default (`WHATIF_MODEL` to change).
The story language is Korean by default (`WHATIF_LANG=English` to change).
Edit the `context` list in `world.json` to tell the game master what the world looks like
today, because the model may not know recent events.

## Status

First version. Next: check the world against an event whose result is known
(the 2026 Hormuz closure), and add more indicators and historical cases.
