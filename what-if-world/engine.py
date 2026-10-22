"""
What-If World - the game master.

The world is a growing list of things that can change ("items"). A set of basic
indicators exists from the start, but the game master can add any new item it
needs: a new country, a company, a group of people, a price nobody tracked before.

Every number is a change since the simulation started (today = 0), so the model
never has to invent today's levels. Things that are not numbers are kept as a
short status text (for example "closed to tankers").

Every change says what caused it: the author's event, or an earlier change.
This builds a chain of effects that can run over many weeks.

The language model only proposes changes. This code checks each one before it
touches the world.
"""

import copy
import json
import os
import re
import urllib.request
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SAVE = os.path.join(HERE, "saves", "current.json")
MODEL = os.environ.get("WHATIF_MODEL", "gpt-4o-mini")
LANG = os.environ.get("WHATIF_LANG", "Korean")
HISTORY_WEEKS = 8        # past weeks of story the game master reads
LINK_WEEKS = 3           # past weeks of changes it can point to as causes
MAX_NEW_PER_WEEK = 15    # new items per week
LIMITS = {"%": 300.0, "pp": 10.0}  # largest change in one week, when the item has no own limit
UNITS = {"%", "pp", "count", "status"}


def load_json(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")[:40] or "item"


def api_key():
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key.strip()
    env = os.path.join(HERE, ".env")
    if os.path.exists(env):
        with open(env) as f:
            for line in f:
                if line.startswith("OPENAI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"')
    raise RuntimeError("No OpenAI key. Put OPENAI_API_KEY=... in what-if-world/.env")


def ask_openai(system, user):
    body = json.dumps({
        "model": MODEL,
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        data = json.load(r)
    return json.loads(data["choices"][0]["message"]["content"])


SYSTEM = """You are the game master of "What-If World", a simulation of the real world.
The author adds events. You decide how the world reacts, one week at a time.

How to think:
1. Decide which parts of the world the event (and everything that already happened) touches.
   Think in chains: a first effect causes second effects, which cause third effects.
   Do not stop at the basic indicators. If something important changes that is not tracked yet
   (a country, a company, a group of people, a price, a law, a route), create a new item for it.
2. Size every change by comparing with real events in history. Prefer cases from the given list.
   If you use a case that is not on the list, set from_list to false. If there is no similar case,
   say so and keep changes small.
3. Governments, central banks, companies, markets and people react the way they really tend to react.
   Effects can continue in later weeks; a shock usually fades unless something keeps it going.
4. Changes are for THIS week only, relative to last week.
5. Never invent today's levels. Numbers are always changes:
   unit "%"  = percent change, "pp" = percentage points, "count" = number of people or things
   added since the start (for example refugees, job losses), "status" = a short text describing
   the new state (for example "closed to tankers").
6. Every change must say what caused it in "caused_by": "event" (the author's event this week),
   the "ref" of another change in this reply, or the id of a change from an earlier week
   (ids look like "w3.c2"). Use earlier ids to continue chains over weeks.
7. Write label, interpretation, why, action, reason and narrative in {lang}.

Reply with JSON only:
{{
  "interpretation": "what the event means and which parts of the world it touches",
  "analogs": [{{"case": "name", "from_list": true, "why": "why it is similar and how big the effect was"}}],
  "actions": [{{"actor": "who", "action": "what they do this week"}}],
  "changes": [
    {{"ref": "c1", "item": "existing item id", "change": 12.0, "reason": "short", "caused_by": ["event"]}},
    {{"ref": "c2", "new_item": {{"scope": "Egypt", "scope_label": "Egypt in {lang}", "name": "Bread subsidy cost", "label": "label in {lang}", "unit": "%"}},
      "change": 20.0, "reason": "short", "caused_by": ["c1"]}},
    {{"ref": "c3", "new_item": {{"scope": "Strait of Hormuz", "scope_label": "in {lang}", "name": "Tanker traffic", "label": "label in {lang}", "unit": "status"}},
      "status": "short new state", "reason": "short", "caused_by": ["event"]}}
  ],
  "narrative": "3 to 6 sentences: what happened in the world this week"
}}"""


class World:
    def __init__(self):
        self.cfg = load_json("world.json")
        self.cases = load_json("cases.json")
        if os.path.exists(SAVE):
            with open(SAVE, encoding="utf-8") as f:
                saved = json.load(f)
            if "items" in saved.get("state", {}):
                self.state, self.history = saved["state"], saved["history"]
                return
        self.reset()

    # ---------- state ----------
    def fresh_state(self):
        items = {}
        for k, spec in self.cfg["global_indicators"].items():
            items[f"global.{k}"] = self.make_item("global", k, spec["label"], spec["unit"], True, spec.get("max_week"))
        for c in self.cfg["countries"]:
            for k, spec in self.cfg["country_indicators"].items():
                items[f"{slug(c)}.{k}"] = self.make_item(c, k, spec["label"], spec["unit"], True, spec.get("max_week"))
        return {"week": 0, "date": self.cfg["start_date"], "items": items}

    @staticmethod
    def make_item(scope, name, label, unit, basic=False, max_week=None, week=0):
        return {"scope": scope, "name": name, "label": label, "unit": unit, "basic": basic,
                "max_week": max_week, "value": 0.0, "status": "", "created_week": week}

    def reset(self):
        self.state = self.fresh_state()
        self.history = []
        self.save()

    def undo(self):
        if not self.history:
            return
        self.history.pop()
        self.state = copy.deepcopy(self.history[-1]["state"]) if self.history else self.fresh_state()
        self.save()

    def save(self):
        os.makedirs(os.path.dirname(SAVE), exist_ok=True)
        with open(SAVE, "w", encoding="utf-8") as f:
            json.dump({"state": self.state, "history": self.history}, f, ensure_ascii=False)

    # ---------- prompt ----------
    def build_prompt(self, event):
        items = self.state["items"]
        L = [f"Today in the simulation: {self.state['date']} (week {self.state['week']}).", "",
             "What the world looks like (context from the author):"]
        L += [f"- {c}" for c in self.cfg["context"]]

        L += ["", "Basic indicators exist for these countries: " + ", ".join(self.cfg["countries"]),
              "Basic country indicator ids: <country>.<key> with keys: " +
              ", ".join(f"{k} ({v['unit']})" for k, v in self.cfg["country_indicators"].items()),
              "Country part of the id: " + ", ".join(f"{c} = {slug(c)}" for c in self.cfg["countries"]),
              "Global ids: " + ", ".join(f"global.{k} ({v['unit']})" for k, v in self.cfg["global_indicators"].items()),
              "", "Items that have changed or were added (id | scope | name | unit | value or status):"]
        moved = [(i, it) for i, it in items.items() if it["value"] or it["status"] or not it["basic"]]
        moved.sort(key=lambda x: -abs(x[1]["value"]))
        if not moved:
            L.append("(nothing has changed yet)")
        for i, it in moved[:120]:
            val = it["status"] if it["unit"] == "status" else f"{it['value']:+.1f}"
            L.append(f"{i} | {it['scope']} | {it['name']} | {it['unit']} | {val}")

        L += ["", "Story so far:"]
        past = self.history[-HISTORY_WEEKS:]
        if not past:
            L.append("(nothing yet)")
        for h in past:
            ev = f" Event: {h['event']}." if h["event"] else ""
            L.append(f"Week {h['week']}.{ev} {h['narrative']}")

        L += ["", "Changes from recent weeks you can point to as causes:"]
        recent = [c for h in self.history[-LINK_WEEKS:] for c in h["changes"]]
        if not recent:
            L.append("(none)")
        for c in recent:
            what = c["status"] if c["unit"] == "status" else f"{c['change']:+.1f} {c['unit']}"
            L.append(f"{c['id']}: {c['scope']} {c['name']} {what} ({c['reason']})")

        L += ["", "Historical cases:"]
        L += [f"- {c['name']}: {c['event']} -> {c['effects']}" for c in self.cases]
        L += ["", f"New event this week: {event}" if event else
              "No new event this week. Continue from what already happened."]
        return "\n".join(L)

    # ---------- checking ----------
    def find_item(self, scope, name):
        for i, it in self.state["items"].items():
            if slug(it["scope"]) == slug(scope) and slug(it["name"]) == slug(name):
                return i
        return None

    def check(self, raw, week):
        """Turn the model's proposals into safe changes. Returns (changes, dropped)."""
        items = self.state["items"]
        ok, dropped, refmap, new_count = [], [], {}, 0
        known_ids = {c["id"] for h in self.history for c in h["changes"]}
        for n, ch in enumerate(raw.get("changes", []), start=1):
            cid = f"w{week}.c{n}"
            ref = str(ch.get("ref") or f"c{n}")
            # which item?
            item_id = ch.get("item")
            new_spec = ch.get("new_item")
            if item_id not in items:
                item_id = None
            if item_id is None and isinstance(new_spec, dict):
                scope = str(new_spec.get("scope") or "").strip()[:40]
                name = str(new_spec.get("name") or "").strip()[:60]
                unit = new_spec.get("unit")
                if not scope or not name or unit not in UNITS:
                    dropped.append({**ch, "why_dropped": "new item needs scope, name and a valid unit"})
                    continue
                item_id = self.find_item(scope, name)  # already exists under another id?
                if item_id is None:
                    if new_count >= MAX_NEW_PER_WEEK:
                        dropped.append({**ch, "why_dropped": "too many new items this week"})
                        continue
                    item_id = f"{slug(scope)}.{slug(name)}"
                    while item_id in items:
                        item_id += "_"
                    items[item_id] = self.make_item(scope, name, str(new_spec.get("label") or name)[:60],
                                                    unit, week=week)
                    items[item_id]["scope_label"] = str(new_spec.get("scope_label") or scope)[:40]
                    new_count += 1
            if item_id is None:
                dropped.append({**ch, "why_dropped": "unknown item"})
                continue
            it = items[item_id]
            change, status, capped = 0.0, "", False
            if it["unit"] == "status":
                status = str(ch.get("status") or "").strip()[:120]
                if not status:
                    dropped.append({**ch, "why_dropped": "status item without status text"})
                    continue
            else:
                try:
                    val = float(ch.get("change", 0))
                except (TypeError, ValueError):
                    dropped.append({**ch, "why_dropped": "not a number"})
                    continue
                limit = it.get("max_week") or LIMITS.get(it["unit"])
                change = max(-limit, min(limit, val)) if limit else val
                if it["unit"] == "%":
                    change = max(change, -100.0)
                capped = change != val
            refmap[ref] = cid
            ok.append({"id": cid, "item": item_id, "scope": it["scope"], "name": it["name"],
                       "scope_label": it.get("scope_label", ""),
                       "label": it["label"], "unit": it["unit"], "change": round(change, 2),
                       "status": status, "capped": capped, "new": it["created_week"] == week,
                       "reason": str(ch.get("reason") or "")[:200],
                       "caused_by_raw": ch.get("caused_by") or []})
        # resolve causes now that every ref in this reply is known
        for c in ok:
            causes = []
            raw_causes = c.pop("caused_by_raw")
            if isinstance(raw_causes, str):
                raw_causes = [raw_causes]
            for x in raw_causes:
                x = str(x)
                if x == "event":
                    causes.append("event")
                elif x in refmap and refmap[x] != c["id"]:
                    causes.append(refmap[x])
                elif x in known_ids:
                    causes.append(x)
            c["caused_by"] = causes
        return ok, dropped

    def apply(self, changes):
        items = self.state["items"]
        for c in changes:
            it = items[c["item"]]
            if it["unit"] == "status":
                it["status"] = c["status"]
            elif it["unit"] == "%":  # percentage changes compound
                it["value"] = round(((1 + it["value"] / 100) * (1 + c["change"] / 100) - 1) * 100, 2)
            else:                    # pp and counts add up
                it["value"] = round(it["value"] + c["change"], 2)

    # ---------- one week ----------
    def step(self, event=None, ask=None):
        ask = ask or ask_openai
        event = (event or "").strip() or None
        week = self.state["week"] + 1
        raw = ask(SYSTEM.format(lang=LANG), self.build_prompt(event))
        before = copy.deepcopy(self.state)
        try:
            changes, dropped = self.check(raw, week)
            self.apply(changes)
        except Exception:
            self.state = before
            raise
        self.state["week"] = week
        self.state["date"] = (date.fromisoformat(self.state["date"]) + timedelta(days=7)).isoformat()
        entry = {
            "week": week,
            "date": self.state["date"],
            "event": event,
            "interpretation": raw.get("interpretation", ""),
            "analogs": raw.get("analogs", []),
            "actions": raw.get("actions", []),
            "changes": changes,
            "dropped": dropped,
            "narrative": raw.get("narrative", ""),
            "state": copy.deepcopy(self.state),
        }
        self.history.append(entry)
        self.save()
        return entry
