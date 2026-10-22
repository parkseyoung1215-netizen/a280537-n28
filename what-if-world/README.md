# What-If World

The world as a book, and you are the author. Set up today's world, write an event
("Iran closes the Strait of Hormuz", "the Bank of Korea raises rates by 2 points",
"wheat harvests fall 30%"), and watch how the world reacts week by week.

## How it works

1. **The world is a growing list of things that can change.** It starts with basic
   indicators (`world.json`): 13 countries with 9 indicators each and 6 global markets.
   The game master can add anything else it needs: a new country, a company, a group
   of people, a price nobody tracked before (for example "tanker insurance premium" or
   "truck drivers on strike").
2. **Numbers are always changes since today** (today = 0): `%`, percentage points, or a count
   of people or things added. Things that are not numbers are kept as a short status
   ("tanker traffic: stopped"). So the model never has to invent today's levels.
3. **Game master** (`engine.py`): a language model reads the event, decides which parts of
   the world it touches, and lets governments, central banks, companies and people react.
4. **History as a ruler** (`cases.json`): each reaction is sized by comparing with real past
   events, and the case used is shown. Cases from outside the list are marked.
5. **Chains of effects**: every change says what caused it (the event, or an earlier change,
   also from earlier weeks). The screen shows the chain as a tree:
   event → tanker traffic stopped → oil +30% → fuel prices in Korea +12% → government approval −4pp.
6. **Code checks the AI**: unknown items, missing units and too-large weekly jumps are
   dropped or cut, and shown on screen.

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
