#!/usr/bin/env python3
"""Aggregate LAND Transition Action Bridge v0.

Reports issued Action composition and directly observed State deltas around the
first realized LAND expansion. No causal attribution.
"""
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

RELS=(-1,0,1,2)
DELTA_FIELDS=(
    "cash","unlocked_tiles","empty_tiles","occupied_tiles","crop_count","animal_count",
    "hands","seed_inventory_total","sellable_stock_total","committed_mark",
)

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None

def summ(xs):
    xs=[float(x) for x in xs if x is not None]
    return {
      "n":len(xs),"mean":mean(xs),"median":median(xs),
      "min":min(xs) if xs else None,"max":max(xs) if xs else None,
    }

def opkey(a):
    if isinstance(a,list) and a: return str(a[0])
    if isinstance(a,str): return a
    if a is None:return "NONE"
    return str(a)

def market_full(a):
    if isinstance(a,list): return ":".join(str(x) for x in a[:3])
    return str(a)

def transition_action_counts(tr):
    c={"market_op":Counter(),"market_full":Counter(),"farmer_op":Counter(),"hand_op":Counter()}
    if not tr: return c
    a=tr.get("action")
    if not isinstance(a,dict): return c
    for x in a.get("market",[]) or []:
        c["market_op"][opkey(x)]+=1
        c["market_full"][market_full(x)]+=1
    c["farmer_op"][opkey(a.get("farmer"))]+=1
    for x in a.get("hands",[]) or []:
        c["hand_op"][opkey(x)]+=1
    return c

def merge(cs):
    out={k:Counter() for k in ("market_op","market_full","farmer_op","hand_op")}
    for c in cs:
        for k in out: out[k].update(c[k])
    return {k:dict(v.most_common()) for k,v in out.items()}

def per_case_signature(tr):
    c=transition_action_counts(tr)
    return {
      "market_full":tuple(sorted(c["market_full"].elements())),
      "farmer_op":tuple(sorted(c["farmer_op"].elements())),
      "hand_op":tuple(sorted(c["hand_op"].elements())),
    }

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/land_transition_action_bridge_v0_*.json"))
    if len(files)!=50:
        raise SystemExit(f"Expected 50 bridge files, got {len(files)}")
    rows=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    rows.sort(key=lambda x:int(x["seed"]))

    agg={}
    for rel in RELS:
        rk=str(rel)
        agg[rk]={}
        for side in ("self","opponent"):
            trs=[r[side]["transitions"].get(rk) for r in rows]
            valid=[t for t in trs if t is not None]
            agg[rk][side]={
              "n":len(valid),
              "actions":merge([transition_action_counts(t) for t in valid]),
              "state_delta":{
                f:summ([t["state_delta"].get(f) for t in valid])
                for f in DELTA_FIELDS
              },
            }

        pair_patterns=Counter()
        for r in rows:
            s=r["self"]["transitions"].get(rk)
            o=r["opponent"]["transitions"].get(rk)
            if not s or not o: continue
            ss=per_case_signature(s); oo=per_case_signature(o)
            pair_patterns[
                json.dumps({"self":ss,"opponent":oo},sort_keys=True)
            ]+=1
        agg[rk]["paired_action_patterns"]=[
            {"count":n,"pattern":json.loads(k)}
            for k,n in pair_patterns.most_common(10)
        ]

    terminal={
      "mean_self":mean([float(r["terminal"]["self"]) for r in rows]),
      "mean_opponent":mean([float(r["terminal"]["opponent"]) for r in rows]),
      "mean_margin":mean([float(r["terminal"]["margin"]) for r in rows]),
      "wins":sum(float(r["terminal"]["margin"])>0 for r in rows),
    }

    payload={
      "schema":"kaggriculture.land-transition-action-bridge.aggregate.v0",
      "battle_count":len(rows),
      "terminal_absolute":terminal,
      "relative_transitions":agg,
      "cases":[{
        "seed":r["seed"],"seat":r["seat"],"terminal":r["terminal"],
        "self_land":r["self"]["land_event"],"opponent_land":r["opponent"]["land_event"],
        "self_actions":{k:(r["self"]["transitions"].get(k) or {}).get("action_summary") for k in map(str,RELS)},
        "opponent_actions":{k:(r["opponent"]["transitions"].get(k) or {}).get("action_summary") for k in map(str,RELS)},
        "self_deltas":{k:(r["self"]["transitions"].get(k) or {}).get("state_delta") for k in map(str,RELS)},
        "opponent_deltas":{k:(r["opponent"]["transitions"].get(k) or {}).get("state_delta") for k in map(str,RELS)},
      } for r in rows],
      "boundary":[
        "Issued Actions and observed one-transition State deltas are reported side by side.",
        "Action presence is not treated as execution success unless the State change itself demonstrates an effect.",
        "No cause, bottleneck, strategy target, or Candidate is inferred.",
        "Relative transition 0 is the LAND-causing transition; +1 is the first transition after realized LAND."
      ]
    }
    Path("land_transition_action_bridge_v0_aggregate.json").write_text(
        json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )

    compact={
      "battle_count":len(rows),"terminal":terminal,
      "relative":{
        rk:{
          side:{
            "market_op":agg[rk][side]["actions"]["market_op"],
            "market_full_top10":dict(list(agg[rk][side]["actions"]["market_full"].items())[:10]),
            "farmer_op":agg[rk][side]["actions"]["farmer_op"],
            "hand_op":agg[rk][side]["actions"]["hand_op"],
            "seed_delta_mean":agg[rk][side]["state_delta"]["seed_inventory_total"]["mean"],
            "stock_delta_mean":agg[rk][side]["state_delta"]["sellable_stock_total"]["mean"],
            "crop_delta_mean":agg[rk][side]["state_delta"]["crop_count"]["mean"],
            "occupied_delta_mean":agg[rk][side]["state_delta"]["occupied_tiles"]["mean"],
          } for side in ("self","opponent")
        } for rk in map(str,RELS)
      }
    }
    print("LAND_TRANSITION_ACTION_BRIDGE_AGG "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
