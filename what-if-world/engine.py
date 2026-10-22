"""
What-If World - the game master.

The world is a set of numbers (how far each indicator has moved away from today).
Each step is one week. The author may add an event in plain words. The game
master (a language model) decides which parts of the world the event touches,
looks for similar events in history to size the reaction, lets governments,
central banks and markets react, and writes what happened.

The language model only proposes changes. This code checks every change
(valid country, valid indicator, weekly limit) before it touches the world.
"""

import copy
import json
import os
import urllib.request
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SAVE = os.path.join(HERE, "saves", "current.json")
MODEL = os.environ.get("WHATIF_MODEL", "gpt-4o-mini")
LANG = os.environ.get("WHATIF_LANG", "Korean")
HISTORY_WEEKS = 8  # how many past weeks the game master reads


def load_json(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


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
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    return json.loads(data["choices"][0]["message"]["content"])


SYSTEM = """You are the game master of "What-If World", a simulation of the real world.
The author adds events. You decide how the world reacts, one week at a time.

Rules:
1. First decide which parts of the world the event (and everything that happened before) actually touches. Leave everything else unchanged.
2. Size every change by comparing with real events in history. Prefer cases from the given list. If you use a case that is not on the list, say so (from_list = false). If there is no similar case, say that and keep the changes small.
3. Governments, central banks, companies and markets react the way they really tend to react. Effects can continue in later weeks; a shock usually fades unless something keeps it going.
4. Changes are for THIS week only, relative to last week. Respect the weekly limits.
5. Never invent precise facts about the present. Use the context the author gives.
6. Write "interpretation", "why", "action", "reason" and "narrative" in {lang}.

Reply with JSON only:
{{
  "interpretation": "what the event means and which parts of the world it touches",
  "analogs": [{{"case": "name", "from_list": true, "why": "why it is similar, and how big the effect was"}}],
  "actions": [{{"actor": "who", "action": "what they do this week"}}],
  "changes": [{{"scope": "global or a country name", "indicator": "key", "change": 0.0, "reason": "short"}}],
  "narrative": "3 to 6 sentences: what happened in the world this week"
}}"""


class World:
    def __init__(self):
        self.cfg = load_json("world.json")
        self.cases = load_json("cases.json")
        if os.path.exists(SAVE):
            with open(SAVE, encoding="utf-8") as f:
                saved = json.load(f)
            self.state, self.history = saved["state"], saved["history"]
        else:
            self.reset()

    # ---------- state ----------
    def fresh_state(self):
        return {
            "week": 0,
            "date": self.cfg["start_date"],
            "countries": {c: {k: 0.0 for k in self.cfg["country_indicators"]}
                          for c in self.cfg["countries"]},
            "global": {k: 0.0 for k in self.cfg["global_indicators"]},
        }

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
            json.dump({"state": self.state, "history": self.history}, f, ensure_ascii=False, indent=1)

    # ---------- one week ----------
    def build_prompt(self, event):
        lines = [f"Today in the simulation: {self.state['date']} (week {self.state['week']}).", ""]
        lines.append("What the world looks like (context from the author):")
        lines += [f"- {c}" for c in self.cfg["context"]]
        lines += ["", "Indicators (value = change since the simulation started; pp = percentage points):"]
        for k, v in self.cfg["global_indicators"].items():
            lines.append(f"- global.{k}: {v['label']} ({v['unit']}, weekly limit {v['max_week']})")
        for k, v in self.cfg["country_indicators"].items():
            lines.append(f"- <country>.{k}: {v['label']} ({v['unit']}, weekly limit {v['max_week']})")
        lines += ["", "Countries: " + ", ".join(self.cfg["countries"]), "", "Current values:"]
        lines.append("global: " + ", ".join(f"{k} {v:+.1f}" for k, v in self.state["global"].items()))
        for c, vals in self.state["countries"].items():
            lines.append(f"{c}: " + ", ".join(f"{k} {v:+.1f}" for k, v in vals.items()))
        lines += ["", "Past weeks:"]
        past = self.history[-HISTORY_WEEKS:]
        if not past:
            lines.append("(nothing yet)")
        for h in past:
            ev = f" Event: {h['event']}." if h["event"] else ""
            lines.append(f"Week {h['week']}.{ev} {h['narrative']}")
        lines += ["", "Historical cases:"]
        lines += [f"- {c['name']}: {c['event']} -> {c['effects']}" for c in self.cases]
        lines += ["", f"New event this week: {event}" if event else
                  "No new event this week. Continue from what already happened."]
        return "\n".join(lines)

    def check(self, raw):
        """Keep only valid changes and cut them to the weekly limit."""
        ok, dropped = [], []
        for ch in raw.get("changes", []):
            scope, ind = ch.get("scope"), ch.get("indicator")
            try:
                val = float(ch.get("change", 0))
            except (TypeError, ValueError):
                dropped.append({**ch, "why_dropped": "not a number"})
                continue
            if scope == "global":
                spec = self.cfg["global_indicators"].get(ind)
            elif scope in self.cfg["countries"]:
                spec = self.cfg["country_indicators"].get(ind)
            else:
                dropped.append({**ch, "why_dropped": "unknown country"})
                continue
            if spec is None:
                dropped.append({**ch, "why_dropped": "unknown indicator"})
                continue
            limit = spec["max_week"]
            capped = max(-limit, min(limit, val))
            ok.append({"scope": scope, "indicator": ind, "change": round(capped, 2),
                       "unit": spec["unit"], "reason": ch.get("reason", ""),
                       "capped": capped != val})
        return ok, dropped

    def apply(self, changes):
        for ch in changes:
            box = self.state["global"] if ch["scope"] == "global" else self.state["countries"][ch["scope"]]
            old = box[ch["indicator"]]
            if ch["unit"] == "%":  # percentage changes compound
                new = ((1 + old / 100) * (1 + ch["change"] / 100) - 1) * 100
            else:                  # percentage points add up
                new = old + ch["change"]
            box[ch["indicator"]] = round(new, 2)

    def step(self, event=None, ask=ask_openai):
        event = (event or "").strip() or None
        raw = ask(SYSTEM.format(lang=LANG), self.build_prompt(event))
        changes, dropped = self.check(raw)
        self.apply(changes)
        self.state["week"] += 1
        self.state["date"] = (date.fromisoformat(self.state["date"]) + timedelta(days=7)).isoformat()
        entry = {
            "week": self.state["week"],
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
