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
import hashlib
import json
import os
import re
import urllib.request
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SAVES = os.path.join(HERE, "saves")
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
7. Make items concrete and measurable. A company is tracked by its share price ("Naver share price", "%"),
   a group of people by a count, a route or law by a status. Avoid vague items like "expectations".
8. An analog must be similar in kind and size. Do not compare a routine rate decision or a company
   announcement with a financial crisis or a war. Typical patterns in the list are fine to use.
9. For the United States, "currency" means the dollar index (the dollar against other currencies).
10. A country that is not in the basic list (for example Taiwan, France, Germany) can use the same
    basic indicators: write "item": "<country id>.<basic key>" (for example "taiwan.stocks",
    "france.approval") and add "scope_label". The item is created automatically.
11. When an industry is hit, track the share prices of the two to four companies that matter most
    (for example TSMC, Samsung Electronics, SK hynix for chips). Some companies can gain
    (competitors, substitutes); say so when it is the case.
12. Say how sure you are. "confidence" is "high" when the event is close to a case in the list,
    "medium" when only partly similar, "low" when history has no real precedent.
    Always "low" for a direct military conflict between major powers, or a sudden stop of something
    the world cannot replace (for example advanced chips from Taiwan), even if one part of it looks
    like a past case. For "low", give the
    plausible range in "uncertainty" (for example "US stocks could fall 2% or 15%") and pick a value
    in the middle of that range.
13. Market expectations: the prompt lists what markets have already priced in, with a probability
    for each outcome. If the event is one of those outcomes, markets react to the SURPRISE, not to
    the event itself: an outcome priced at 90% moves markets very little (most of it happened
    before), an outcome priced at 10% moves them a lot, often more than the event alone would.
    Name the match in "expectation_match". Things that are not market prices (laws, wars, protests,
    supply) still change by the event itself.
14. After the event, update what markets now expect in "expectation_updates": change probabilities,
    add a new expectation that the event created (for example the chance of another rate cut), or
    mark one as resolved. Only add expectations that markets really trade on.
15. Write label, interpretation, why, action, reason, uncertainty, topic, outcome names and
    narrative in {lang}.

Reply with JSON only:
{{
  "interpretation": "what the event means and which parts of the world it touches",
  "analogs": [{{"case": "name", "from_list": true, "why": "why it is similar and how big the effect was"}}],
  "actions": [{{"actor": "who", "action": "what they do this week"}}],
  "changes": [
    {{"ref": "c1", "item": "existing item id", "change": 12.0, "reason": "short", "caused_by": ["event"]}},
    {{"ref": "c4", "item": "taiwan.stocks", "scope_label": "Taiwan in {lang}", "change": -8.0, "reason": "short", "caused_by": ["event"]}},
    {{"ref": "c2", "new_item": {{"scope": "Egypt", "scope_label": "Egypt in {lang}", "name": "Bread subsidy cost", "label": "label in {lang}", "unit": "%"}},
      "change": 20.0, "reason": "short", "caused_by": ["c1"]}},
    {{"ref": "c3", "new_item": {{"scope": "Strait of Hormuz", "scope_label": "in {lang}", "name": "Tanker traffic", "label": "label in {lang}", "unit": "status"}},
      "status": "short new state", "reason": "short", "caused_by": ["event"]}}
  ],
  "narrative": "3 to 6 sentences: what happened in the world this week",
  "confidence": "high | medium | low",
  "uncertainty": "why, and the plausible range when confidence is low",
  "expectation_match": {{"id": "expectation id", "outcome": "outcome name exactly as listed"}},
  "expectation_updates": [
    {{"id": "existing or new short id", "topic": "what markets are betting on", "outcomes": {{"outcome A": 60, "outcome B": 40}}}},
    {{"id": "existing id", "resolved": true}}
  ]
}}
Use "expectation_match": null when the event is not one of the listed outcomes."""


def uid(text):
    """Short id that keeps letters of any language (Korean too)."""
    return re.sub(r"[^\w]+", "_", str(text or "").lower()).strip("_")[:40]


def branch_path(name):
    # keep letters of any language (Korean too) and add a short hash so names never collide
    safe = re.sub(r"[^\w-]+", "_", str(name)).strip("_")[:30] or "branch"
    tag = hashlib.md5(str(name).encode("utf-8")).hexdigest()[:6]
    return os.path.join(SAVES, f"branch_{safe}_{tag}.json")


def list_branches():
    """Names of saved branches (one file per branch). Moves an old single save into 'main'."""
    os.makedirs(SAVES, exist_ok=True)
    old = os.path.join(SAVES, "current.json")
    if os.path.exists(old) and not os.path.exists(branch_path("main")):
        with open(old, encoding="utf-8") as f:
            saved = json.load(f)
        if "items" in saved.get("state", {}):
            saved["name"] = "main"
            with open(branch_path("main"), "w", encoding="utf-8") as f:
                json.dump(saved, f, ensure_ascii=False)
        os.rename(old, os.path.join(SAVES, "current_old.json"))
    names = []
    for fn in sorted(os.listdir(SAVES)):
        if fn.startswith("branch_") and fn.endswith(".json"):
            with open(os.path.join(SAVES, fn), encoding="utf-8") as f:
                names.append(json.load(f).get("name", fn[7:-5]))
    return names


class World:
    """One branch of the world: its own state and its own history."""

    def __init__(self, name="main"):
        self.name = name
        self.cfg = load_json("world.json")
        self.cases = load_json("cases.json")
        path = branch_path(name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                saved = json.load(f)
            self.state, self.history = saved["state"], saved["history"]
            self.state.setdefault("expectations", {})
            self.parent = saved.get("parent")
        else:
            self.parent = None
            self.reset()

    def fork(self, new_name, from_week):
        """A new branch that shares this branch's history up to from_week."""
        from_week = max(0, min(int(from_week), self.state["week"]))
        child = World.__new__(World)
        child.name, child.cfg, child.cases = new_name, self.cfg, self.cases
        child.history = copy.deepcopy(self.history[:from_week])
        if from_week == self.state["week"]:
            child.state = copy.deepcopy(self.state)  # includes expectations set since the last week
        else:
            child.state = copy.deepcopy(child.history[-1]["state"]) if child.history else child.fresh_state()
            # expectations the author added after that week, before the next one ran
            nxt = self.history[from_week] if from_week < len(self.history) else None
            if nxt and "expectations_before" in nxt:
                child.state["expectations"] = copy.deepcopy(nxt["expectations_before"])
        child.state.setdefault("expectations", {})
        child.parent = {"branch": self.name, "week": from_week}
        child.save()
        return child

    def delete(self):
        path = branch_path(self.name)
        if os.path.exists(path):
            os.remove(path)

    # ---------- state ----------
    def fresh_state(self):
        items = {}
        for k, spec in self.cfg["global_indicators"].items():
            items[f"global.{k}"] = self.make_item("global", k, spec["label"], spec["unit"], True, spec.get("max_week"))
        for c in self.cfg["countries"]:
            for k, spec in self.cfg["country_indicators"].items():
                items[f"{slug(c)}.{k}"] = self.make_item(c, k, spec["label"], spec["unit"], True, spec.get("max_week"))
        return {"week": 0, "date": self.cfg["start_date"], "items": items, "expectations": {}}

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
        undone = self.history.pop()
        self.state = copy.deepcopy(self.history[-1]["state"]) if self.history else self.fresh_state()
        self.state["expectations"] = copy.deepcopy(undone.get("expectations_before", self.state.get("expectations", {})))
        self.save()

    def save(self):
        os.makedirs(SAVES, exist_ok=True)
        with open(branch_path(self.name), "w", encoding="utf-8") as f:
            json.dump({"name": self.name, "parent": self.parent,
                       "state": self.state, "history": self.history}, f, ensure_ascii=False)

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

        L += ["", "Market expectations (what markets have priced in):"]
        exps = self.state.get("expectations", {})
        if not exps:
            L.append("(none given)")
        for eid, e in exps.items():
            outs = ", ".join(f"{o} {p:.0f}%" for o, p in e["outcomes"].items())
            L.append(f"{eid}: {e['topic']} -> {outs}")

        L += ["", "Historical cases:"]
        L += [f"- [{c.get('kind', 'event')}] {c['name']}: {c['event']} -> {c['effects']}" for c in self.cases]
        L += ["", f"New event this week: {event}" if event else
              "No new event this week. Continue from what already happened."]
        return "\n".join(L)

    # ---------- checking ----------
    def find_item(self, scope, name):
        for i, it in self.state["items"].items():
            if slug(it["scope"]) == slug(scope) and slug(it["name"]) == slug(name):
                return i
        return None

    def check(self, raw, week, has_event=True):
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
            if isinstance(new_spec, dict) and slug(new_spec.get("name")) in self.cfg["country_indicators"]:
                # new_item that is really a basic indicator for a new country
                item_id = f"{slug(new_spec.get('scope'))}.{slug(new_spec.get('name'))}"
                ch = {**ch, "scope_label": ch.get("scope_label") or new_spec.get("scope_label"),
                      "_scope": new_spec.get("scope")}
            if item_id not in items:
                item_id = self.basic_for_new_country(item_id, ch, week) if item_id else None
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
                    if has_event:
                        causes.append("event")
                elif x in refmap and refmap[x] != c["id"]:
                    causes.append(refmap[x])
                elif x in known_ids:
                    causes.append(x)
            c["caused_by"] = causes
        return ok, dropped

    def basic_for_new_country(self, item_id, ch, week):
        """'taiwan.stocks' for a country without basic indicators: create that indicator."""
        if not isinstance(item_id, str) or item_id.count(".") != 1:
            return None
        country, key = item_id.split(".")
        spec = self.cfg["country_indicators"].get(key)
        if not spec or not country or country == "global" or len(country) > 40:
            return None
        label = str(ch.get("scope_label") or "").strip()[:40]
        scope = next((it["scope"] for it in self.state["items"].values() if slug(it["scope"]) == country),
                     str(ch.get("_scope") or "").strip()[:40] or country.replace("_", " ").title())
        items = self.state["items"]
        items[item_id] = self.make_item(scope, key, spec["label"], spec["unit"], True, spec.get("max_week"), week)
        items[item_id]["scope_label"] = label or next(
            (it.get("scope_label") for it in items.values() if it["scope"] == scope and it.get("scope_label")), scope)
        return item_id

    # ---------- market expectations ----------
    @staticmethod
    def clean_outcomes(outcomes):
        """Probabilities as numbers that add up to 100."""
        if not isinstance(outcomes, dict):
            return None
        out = {}
        for k, v in list(outcomes.items())[:6]:
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            if v >= 0 and str(k).strip():
                out[str(k).strip()[:60]] = v
        total = sum(out.values())
        if len(out) < 2 or total <= 0:
            return None
        return {k: round(v * 100 / total, 1) for k, v in out.items()}

    def set_expectation(self, eid, topic, outcomes, source="author", week=None):
        clean = self.clean_outcomes(outcomes)
        topic = str(topic or "").strip()[:120]
        if not clean or not topic:
            raise ValueError("예상에는 주제와 결과가 두 개 이상 필요해요 (예: 인하 70, 동결 30)")
        eid = uid(eid or topic) or f"exp{len(self.state['expectations']) + 1}"
        self.state["expectations"][eid] = {"topic": topic, "outcomes": clean, "source": source,
                                           "week": self.state["week"] if week is None else week}
        self.save()
        return eid

    def delete_expectation(self, eid):
        self.state["expectations"].pop(eid, None)
        self.save()

    def resolve_expectations(self, raw, week, has_event=True):
        """Work out the surprise in code, then apply the model's updates."""
        exps = self.state["expectations"]
        surprise = None
        m = raw.get("expectation_match") if has_event else None
        if isinstance(m, dict) and m.get("id") in exps:
            e = exps[m["id"]]
            outcome = str(m.get("outcome") or "")
            prob = e["outcomes"].get(outcome)
            if prob is None:  # loose match on the outcome name
                prob = next((p for o, p in e["outcomes"].items() if uid(o) == uid(outcome)), None)
            if prob is not None:
                surprise = {"id": m["id"], "topic": e["topic"], "outcome": outcome,
                            "expected": prob, "surprise": round(100 - prob, 1)}
                exps.pop(m["id"], None)  # the bet is settled
        notes = []
        for u in raw.get("expectation_updates") or []:
            if not isinstance(u, dict) or not u.get("id"):
                continue
            key = u["id"] if u["id"] in exps else uid(u["id"])
            if u.get("resolved"):
                if exps.pop(key, None):
                    notes.append(f"resolved {key}")
                continue
            clean = self.clean_outcomes(u.get("outcomes"))
            topic = str(u.get("topic") or exps.get(key, {}).get("topic") or "").strip()[:120]
            if clean and topic and key:
                exps[key] = {"topic": topic, "outcomes": clean, "source": "AI", "week": week}
                notes.append(f"set {key}")
        return surprise, notes

    CONF_RANK = {"low": 0, "medium": 1, "high": 2}
    CONF_CARRY_WEEKS = 4

    def carried_confidence(self, own):
        """A week cannot be more certain than the uncertain weeks it builds on.
        Confidence is the lowest of this week's and the last few weeks'."""
        levels = [own] + [h.get("confidence") for h in self.history[-self.CONF_CARRY_WEEKS:]]
        levels = [c for c in levels if c in self.CONF_RANK]
        return min(levels, key=self.CONF_RANK.get) if levels else ""

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
        expectations_before = copy.deepcopy(self.state["expectations"])
        try:
            changes, dropped = self.check(raw, week, has_event=bool(event))
            self.apply(changes)
            surprise, exp_notes = self.resolve_expectations(raw, week, has_event=bool(event))
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
            "confidence": self.carried_confidence(raw.get("confidence")),
            "confidence_model": raw.get("confidence") if raw.get("confidence") in ("high", "medium", "low") else "",
            "uncertainty": str(raw.get("uncertainty") or "")[:400],
            "surprise": surprise,
            "expectations_before": expectations_before,
            "expectation_notes": exp_notes,
            "state": copy.deepcopy(self.state),
        }
        self.history.append(entry)
        self.save()
        return entry
