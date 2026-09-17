#!/usr/bin/env python3
"""Outside-in observer: where does liquidation throughput differ?

No policy mutation. Reuses capital_cycle_v1.json and compares high/low terminal
cases by money carried through each liquidation event, keeping the coordinate at
the whole-system flow rather than local action causes.
"""
import json
from pathlib import Path

SRC = Path("capital_cycle_v1.json")
OUT = Path("liquidation_throughput_v1.json")


def summarize(cases):
    events = []
    per_case = []
    for c in cases:
        gains = [x["money_gain"] for x in c["cycles"]]
        total = sum(gains)
        per_case.append({
            "seed": c["seed"],
            "seat": c["seat"],
            "terminal_self": c["terminal"]["self"],
            "liquidation_count": len(gains),
            "total_liquidation_gain": total,
            "mean_gain_per_liquidation": total / len(gains) if gains else 0,
            "max_gain": max(gains, default=0),
            "gains_by_order": gains,
        })
        events.extend(gains)
    return {
        "case_count": len(cases),
        "event_count": len(events),
        "mean_gain_per_event": sum(events) / len(events) if events else 0,
        "max_event_gain": max(events, default=0),
        "mean_case_total_gain": sum(x["total_liquidation_gain"] for x in per_case) / len(per_case) if per_case else 0,
        "mean_case_gain_per_liquidation": sum(x["mean_gain_per_liquidation"] for x in per_case) / len(per_case) if per_case else 0,
        "cases": per_case,
    }


def main():
    data = json.loads(SRC.read_text())
    ranked = data["cases_ranked_by_terminal"]
    n = len(ranked) // 3
    high = ranked[:n]
    low = ranked[-n:]
    out = {
        "coordinate": "asset stock -> liquidation event throughput -> repeated capital flow -> terminal",
        "policy_mutated": False,
        "boundary": "descriptive only; throughput association does not establish causal direction",
        "high": summarize(high),
        "low": summarize(low),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print("LIQUIDATION_THROUGHPUT_V1 " + json.dumps({
        "high": {k:v for k,v in out["high"].items() if k != "cases"},
        "low": {k:v for k,v in out["low"].items() if k != "cases"},
    }, separators=(",", ":")))

if __name__ == "__main__":
    main()
