# What-If World

The world as a book, and you are the author. Set up today's world, write an event
("Iran closes the Strait of Hormuz", "the Bank of Korea raises rates by 2 points",
"wheat harvests fall 30%"), and watch how the world reacts week by week.

## Ask a question

Type a question ("What will the Fed decide in October?", "What if China blockades Taiwan?").
The app suggests the main possible outcomes with rough probabilities (marked as AI estimates;
replace them with real numbers if you have them), runs one world per outcome at the same time,
and shows them side by side with the things that differ most between them. Underneath, each
outcome is its own branch with its own market expectation, so everything below still applies.

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

## How sure is it?

Every week comes with a confidence level: high when the event is close to a case in history,
low when there is no real precedent (a blockade of Taiwan, for example). Low-confidence weeks
show the plausible range and are highlighted on screen, so a single number is not mistaken
for a forecast.

## Market expectations: markets react to surprises

Markets move on what they did not expect. Add what markets have priced in ("Fed decision:
cut 70%, hold 30%"). When an event is one of those outcomes, the code works out the surprise
(an outcome priced at 30% is a 70% surprise) and the game master sizes the market reaction by
it: a cut that everyone expected barely moves stocks, a surprise hold moves them a lot. After
the event the game master updates what markets expect next (for example the chance of another
cut). Expectations come from the author; the simulator never invents today's odds.

## Branches: compare two worlds

A what-if needs something to compare with. Make a branch from any past week, give each
branch a different event ("the Fed cuts rates" vs "the Fed holds rates"), and the
"compare branches" tab shows the two stories side by side and every item that ended up
different, sorted by the size of the gap. Each branch is saved in its own file in `saves/`.

## Run

1. Put your OpenAI key in a file `what-if-world/.env`:
   ```
   OPENAI_API_KEY=sk-...
   ```
2. On a Mac, double-click `start.command` (or `시작.command`). Or in a terminal:
   ```
   cd what-if-world
   python3 app.py
   ```
3. The browser opens at http://localhost:8000.

No extra packages needed. Model: `gpt-5.4` by default (`WHATIF_MODEL` to change).
The story language is Korean by default (`WHATIF_LANG=English` to change).
Edit the `context` list in `world.json` to tell the game master what the world looks like
today, because the model may not know recent events.

## Status

Working prototype. Next: check the simulator against an event whose result is known
(the 2026 Strait of Hormuz closure), and keep the world context up to date.
