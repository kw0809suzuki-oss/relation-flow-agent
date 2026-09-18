#!/usr/bin/env python3
"""Transition Sequence Observer v1.

Question:
When the first action divergence is the same in improved and worsened fresh30
cases, from which later value-transformation divergence do their trajectories
begin to differ?

This observer is descriptive only. It reuses the same 30 paired runs from
observe_bundle_flow_gate_boundary_v1 and compresses the baseline/control trace
into divergence-change events after the first action difference.
"""
import json
from collections import Counter, defaultdict
import observe_bundle_flow_gate_boundary_v1 as src

PRODUCTS = src.PRODUCTS

def num_delta(a, b):
    try:
        d = float(b) - float(a)
        return 0.0 if abs(d) < 1e-9 else d
    except Exception:
        return None if a == b else [a, b]

def dict_delta(a, b):
    out = {}
    for k in sorted(set(a or {}) | set(b or {})):
        d = num_delta((a or {}).get(k), (b or {}).get(k))
        if d not in (0, 0.0, None):
            out[k] = d
    return out

def divergence_signature(b, c):
    sig = {}
    for key in ("self_money", "opp_money", "self_hands", "self_land", "self_cows",
                "opp_hands", "opp_land", "opp_cows"):
        d = num_delta(b.get(key), c.get(key))
        if d not in (0, 0.0, None):
            sig[key] = d

    stock = dict_delta(b.get("stock", {}), c.get("stock", {}))
    prices = dict_delta(b.get("market_prices", {}), c.get("market_prices", {}))
    inv = dict_delta(b.get("market_inventory", {}), c.get("market_inventory", {}))
    if stock: sig["stock"] = stock
    if prices: sig["market_prices"] = prices
    if inv: sig["market_inventory"] = inv
    if b.get("action") != c.get("action"):
        sig["action"] = {"baseline": b.get("action"), "control": c.get("action")}
    return sig

def domains(sig):
    out = []
    if "action" in sig: out.append("action")
    if "self_money" in sig: out.append("self_money")
    if "stock" in sig: out.append("stock")
    if any(k in sig for k in ("self_hands", "self_land", "self_cows")): out.append("self_capacity")
    if any(k in sig for k in ("market_prices", "market_inventory")): out.append("market")
    if any(k in sig for k in ("opp_money", "opp_hands", "opp_land", "opp_cows")): out.append("opponent")
    return out

def action_type(event):
    a = event.get("signature", {}).get("action")
    if not a:
        return "no-action-diff"
    return json.dumps(a, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

def compact_events(bt, ct, start):
    events = []
    prev = None
    n = min(len(bt), len(ct))
    for i in range(start, n):
        sig = divergence_signature(bt[i], ct[i])
        canon = json.dumps(sig, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        if canon != prev:
            events.append({
                "turn": i,
                "day": ct[i].get("day"),
                "domains": domains(sig),
                "signature": sig,
            })
            prev = canon
    return events

def first_action_index(bt, ct):
    n = min(len(bt), len(ct))
    for i in range(n):
        if bt[i].get("action") != ct[i].get("action"):
            return i
    return None

def analyze(seed, seat):
    b = src.play(seed, seat, False)
    c = src.play(seed, seat, True)
    bt, ct = b["trace"], c["trace"]
    ai = first_action_index(bt, ct)
    sd = c["terminal_self"] - b["terminal_self"]
    cls = "improved" if sd > 0 else "worsened" if sd < 0 else "equal"
    events = compact_events(bt, ct, ai if ai is not None else 0)
    first_type = action_type(events[0]) if events else "none"
    return {
        "seed": seed,
        "seat": seat,
        "class": cls,
        "terminal_self_diff": sd,
        "terminal_opp_diff": c["terminal_opp"] - b["terminal_opp"],
        "terminal_margin_diff": c["terminal_margin"] - b["terminal_margin"],
        "first_action_turn": ai,
        "first_action_type": first_type,
        "event_count": len(events),
        "events": events,
    }

def summarize(rows):
    by_first = defaultdict(Counter)
    event_count = defaultdict(list)
    for r in rows:
        by_first[r["first_action_type"]][r["class"]] += 1
        event_count[r["class"]].append(r["event_count"])
    return {
        "count_by_class": dict(Counter(r["class"] for r in rows)),
        "first_action_type_by_class": {
            k: dict(v) for k, v in by_first.items()
        },
        "mean_event_count": {
            k: (sum(v) / len(v) if v else None) for k, v in event_count.items()
        },
    }

def main():
    rows = [analyze(seed, seat) for seed, seat in src.CASES]
    out = {
        "schema": "transition-sequence-observer.v1",
        "policy_mutated": False,
        "question": "When the first action divergence is the same, from which later transformation divergence do improved and worsened trajectories separate?",
        "event_definition": "A new event is emitted whenever the baseline/control divergence signature changes after first action divergence.",
        "cases": rows,
        "summary": summarize(rows),
        "boundary": "Event sequence is descriptive. Divergence order is not causal attribution.",
    }
    with open("transition_sequence_observer_v1.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("TRANSITION_SEQUENCE_OBSERVER_V1 " + json.dumps(out["summary"], ensure_ascii=False, separators=(",", ":")))

if __name__ == "__main__":
    main()
