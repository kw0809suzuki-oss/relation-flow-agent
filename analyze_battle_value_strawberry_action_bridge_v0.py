#!/usr/bin/env python3
"""Aggregate STRAWBERRY carried-action bridge v0."""
import glob, json
from collections import Counter
from pathlib import Path

def mean(xs):
    return sum(xs)/len(xs) if xs else None

def action_key(a):
    return json.dumps(a, ensure_ascii=False, separators=(",", ":"))

def main():
    paths = sorted(Path(p) for p in glob.glob(
        "strawberry-action-artifacts/**/battle_value_strawberry_action_bridge_v0_*.json",
        recursive=True,
    ))
    if len(paths) != 5:
        raise SystemExit(f"Expected 5 artifacts, found {len(paths)}")
    raws = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    cases=[]
    opp_positive_actions=Counter()
    self_positive_actions=Counter()
    timestamps_by_seed={}
    provenances=[]
    for r in raws:
        provenances.append(r["environment_provenance"])
        timestamps=[]
        compact_events=[]
        for e in r["events"]:
            timestamps.append((e["to"]["day"], e["to"]["hour"]))
            for ch in e["opponent"]["inventory_changes"]:
                if ch["delta"] > 0:
                    opp_positive_actions[action_key(ch["current_turn_action"])] += ch["delta"]
            for ch in e["self"]["inventory_changes"]:
                if ch["delta"] > 0:
                    self_positive_actions[action_key(ch["current_turn_action"])] += ch["delta"]
            compact_events.append(e)
        timestamps_by_seed[str(r["seed"])] = timestamps
        cases.append({
            "seed": r["seed"],
            "seat": r["seat"],
            "terminal": r["terminal"],
            "event_count": len(r["events"]),
            "events": compact_events,
        })

    common_ts = sorted(set.intersection(*[
        set(tuple(x) for x in timestamps_by_seed[str(r["seed"])]) for r in raws
    ]))
    uniq_prov = []
    for p in provenances:
        if p not in uniq_prov:
            uniq_prov.append(p)

    payload={
        "schema":"kaggriculture.strong-origin-v2.strawberry-carried-action-bridge.result.v0",
        "battle_count":5,
        "terminal_absolute":{
            "mean_self":mean([float(c["terminal"]["self"]) for c in cases]),
            "mean_opponent":mean([float(c["terminal"]["opponent"]) for c in cases]),
            "mean_margin":mean([float(c["terminal"]["margin"]) for c in cases]),
        },
        "environment_provenance_unique":uniq_prov,
        "event_counts_by_seed":{str(c["seed"]):c["event_count"] for c in cases},
        "common_trigger_timestamps_5_of_5":[{"day":d,"hour":h} for d,h in common_ts],
        "opponent_positive_inventory_units_by_exact_action":[
            {"action":json.loads(k),"units":v} for k,v in opp_positive_actions.most_common()
        ],
        "self_positive_inventory_units_by_exact_action":[
            {"action":json.loads(k),"units":v} for k,v in self_positive_actions.most_common()
        ],
        "cases":cases,
        "boundary":[
            "Action counts are exact current-turn actions attached to inventory indexes whose STRAWBERRY quantity increased.",
            "Counts are observed units added to those inventories, not profitability or causal importance scores.",
            "No motive, policy, Direction, Candidate, or adoption conclusion is inferred.",
        ],
    }
    Path("battle_value_strawberry_action_bridge_v0_result.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    print("STRAWBERRY_ACTION_BRIDGE_RESULT "+json.dumps({
        "terminal_absolute":payload["terminal_absolute"],
        "event_counts_by_seed":payload["event_counts_by_seed"],
        "common_trigger_count":len(common_ts),
        "opponent_positive_inventory_units_by_exact_action":payload["opponent_positive_inventory_units_by_exact_action"],
        "environment_provenance_unique":uniq_prov,
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
