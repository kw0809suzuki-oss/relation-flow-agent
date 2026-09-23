#!/usr/bin/env python3
"""SB-01 Cash -> Productive State Conversion Frame v0.

Existing 50-battle artifacts only. No new Battle / Observer.

Alignment:
- State snapshot at Day D is the first retained observation of that day.
- Therefore realized Cash flow is accumulated only through Day D-1.
- Day 0 uses zero prior spend.

No composite productive-state score is created.
Each output dimension is reported separately.
"""
import json, sys
from pathlib import Path

DAYS=(0,4,8,10,12)

def mean(xs): return sum(xs)/len(xs) if xs else None

def summarize(sv,ov):
    gaps=[o-s for s,o in zip(sv,ov)]
    return {
      "self_absolute_mean":mean(sv),
      "opponent_absolute_mean":mean(ov),
      "mean_gap_opponent_minus_self":mean(gaps),
      "opponent_ahead_cases":sum(g>0 for g in gaps),
      "self_ahead_cases":sum(g<0 for g in gaps),
      "equal_cases":sum(g==0 for g in gaps),
      "min_gap":min(gaps) if gaps else None,
      "max_gap":max(gaps) if gaps else None,
    }

def load_one(root,name):
    hits=list(root.glob(f"**/{name}"))
    if not hits: raise SystemExit(f"Missing {name}")
    return json.loads(hits[0].read_text(encoding="utf-8"))

def idx(payload): return {int(c["seed"]):c for c in payload["cases"]}

def load_cash(root):
    hits=[p for p in root.glob("**/sb01_exact_cash_flow_daily_*.json") if "aggregate" not in p.name]
    out={}
    for p in hits:
        r=json.loads(p.read_text(encoding="utf-8"))
        out[int(r["seed"])]=r
    if len(out)!=50: raise SystemExit(f"Expected 50 cash cases, got {len(out)}")
    bad=[s for s,r in out.items() if r["self"]["error"]!=0 or r["opponent"]["error"]!=0]
    if bad: raise SystemExit(f"Cash reconstruction error: {bad}")
    return out

def get_day(seed,day,early,later):
    src=early if day<=6 else later
    return src[seed]["days"][str(day)]

def prior_spend(r,side,day):
    # Snapshot at start of Day D: include realized spending only through D-1.
    ledger=r[side].get("daily_ledger",{})
    out={
      "buy_product":0.0,
      "seed":0.0,
      "animal":0.0,
      "hire":0.0,
      "land":0.0,
      "total_outflow":0.0,
      "structural":0.0,
    }
    for d in range(day):
        dl=ledger.get(str(d),{}) or {}
        for k,v0 in dl.items():
            v=float(v0)
            if v>=0: continue
            cost=-v
            out["total_outflow"] += cost
            if k.startswith("BUY_PRODUCT:"): out["buy_product"] += cost
            elif k.startswith("BUY_SEED:"): out["seed"] += cost
            elif k.startswith("BUY_ANIMAL:"): out["animal"] += cost
            elif k=="HIRE": out["hire"] += cost
            elif k=="BUY_LAND": out["land"] += cost
    out["structural"]=out["seed"]+out["animal"]+out["hire"]+out["land"]
    return out

def crop_total(side):
    return float(sum(side["committed_production"]["crop_count"].values()))

def high_value_crop_total(side):
    c=side["committed_production"]["crop_count"]
    return float(c.get("STRAWBERRY",0)+c.get("MELON",0))

def animal_total(side):
    return float(sum(side["committed_production"]["animal_count"].values()))

def high_value_animal_total(side):
    a=side["committed_production"]["animal_count"]
    return float(a.get("COW",0)+a.get("SHEEP",0))

def ratio(delta, spend):
    if spend<=0: return None
    return 1000.0*delta/spend

def summarize_optional(sv,ov):
    pairs=[(s,o) for s,o in zip(sv,ov) if s is not None and o is not None]
    if not pairs:
        return {"n":0}
    s2=[s for s,_ in pairs];o2=[o for _,o in pairs]
    z=summarize(s2,o2);z["n"]=len(pairs);return z

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    early=idx(load_one(root,"sb01_early_daily_economic_localization_v0.json"))
    later=idx(load_one(root,"sb01_economic_layers_v0.json"))
    cash=load_cash(root)
    seeds=sorted(set(early)&set(later)&set(cash))
    if len(seeds)!=50: raise SystemExit(f"Expected 50 common seeds, got {len(seeds)}")

    base={}
    for s in seeds:
        r=get_day(s,0,early,later)
        base[s]={
          "self":{
            "land":float(r["self"]["uncommitted_capacity"]["unlocked_tiles"]),
            "crop":crop_total(r["self"]),
            "high_crop":high_value_crop_total(r["self"]),
            "animal":animal_total(r["self"]),
            "high_animal":high_value_animal_total(r["self"]),
            "committed":float(r["self"]["committed_production"]["same_basis_subtotal"]),
          },
          "opponent":{
            "land":float(r["opponent"]["uncommitted_capacity"]["unlocked_tiles"]),
            "crop":crop_total(r["opponent"]),
            "high_crop":high_value_crop_total(r["opponent"]),
            "animal":animal_total(r["opponent"]),
            "high_animal":high_value_animal_total(r["opponent"]),
            "committed":float(r["opponent"]["committed_production"]["same_basis_subtotal"]),
          }
        }

    days={}
    for day in DAYS:
        rows=[]
        for s in seeds:
            st=get_day(s,day,early,later)
            row={"seed":s}
            for side in ("self","opponent"):
                x=st[side]
                spend=prior_spend(cash[s],side,day)
                state={
                  "cash":float(x["cash"]),
                  "land":float(x["uncommitted_capacity"]["unlocked_tiles"]),
                  "empty":float(x["uncommitted_capacity"]["empty_unlocked_tiles"]),
                  "crop":crop_total(x),
                  "high_crop":high_value_crop_total(x),
                  "animal":animal_total(x),
                  "high_animal":high_value_animal_total(x),
                  "committed":float(x["committed_production"]["same_basis_subtotal"]),
                }
                delta={
                  "land":state["land"]-base[s][side]["land"],
                  "crop":state["crop"]-base[s][side]["crop"],
                  "high_crop":state["high_crop"]-base[s][side]["high_crop"],
                  "animal":state["animal"]-base[s][side]["animal"],
                  "high_animal":state["high_animal"]-base[s][side]["high_animal"],
                  "committed":state["committed"]-base[s][side]["committed"],
                }
                conversion={}
                for denom in ("total_outflow","structural"):
                    conversion[denom]={k:ratio(v,spend[denom]) for k,v in delta.items()}
                row[side]={"spend":spend,"state":state,"delta":delta,"conversion":conversion}
            rows.append(row)

        entry={"spend":{},"state":{},"delta_from_day0":{},"per_1000_spend":{}}
        for k in ("buy_product","seed","animal","hire","land","structural","total_outflow"):
            entry["spend"][k]=summarize(
              [r["self"]["spend"][k] for r in rows],
              [r["opponent"]["spend"][k] for r in rows]
            )
        for k in ("cash","land","empty","crop","high_crop","animal","high_animal","committed"):
            entry["state"][k]=summarize(
              [r["self"]["state"][k] for r in rows],
              [r["opponent"]["state"][k] for r in rows]
            )
        for k in ("land","crop","high_crop","animal","high_animal","committed"):
            entry["delta_from_day0"][k]=summarize(
              [r["self"]["delta"][k] for r in rows],
              [r["opponent"]["delta"][k] for r in rows]
            )
            entry["per_1000_spend"][k]={
              denom:summarize_optional(
                [r["self"]["conversion"][denom][k] for r in rows],
                [r["opponent"]["conversion"][denom][k] for r in rows]
              ) for denom in ("total_outflow","structural")
            }
        days[str(day)]=entry

    payload={
      "schema":"kaggriculture.sb01.cash-to-productive-state-conversion.v0",
      "battle_count":50,
      "days":days,
      "alignment":"Day D state is compared with realized Cash outflow through Day D-1 only.",
      "boundary":[
        "Existing 50-battle artifacts only; no new Battle or Observer.",
        "No composite productive-state score is created.",
        "Per-1000 figures are descriptive ratios, not causal efficiency estimates.",
        "Crop/animal counts are current physical counts at the sampled state and can decrease after harvest/removal.",
        "Committed Production remains a valuation axis with prior explicit assumptions; it is not treated as terminal value.",
        "HIRE is included as realized structural spending, but day-start current_hands is not used as a persistent state output because hired hands are day-scoped."
      ]
    }
    Path("sb01_cash_to_productive_state_conversion_v0.json").write_text(
      json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )

    compact={"battle_count":50,"days":{}}
    for d in DAYS:
        x=days[str(d)]
        compact["days"][str(d)]={
          "prior_total_outflow_gap":x["spend"]["total_outflow"]["mean_gap_opponent_minus_self"],
          "prior_structural_spend_gap":x["spend"]["structural"]["mean_gap_opponent_minus_self"],
          "prior_buy_product_gap":x["spend"]["buy_product"]["mean_gap_opponent_minus_self"],
          "cash_gap":x["state"]["cash"]["mean_gap_opponent_minus_self"],
          "land_delta_gap":x["delta_from_day0"]["land"]["mean_gap_opponent_minus_self"],
          "crop_delta_gap":x["delta_from_day0"]["crop"]["mean_gap_opponent_minus_self"],
          "high_crop_delta_gap":x["delta_from_day0"]["high_crop"]["mean_gap_opponent_minus_self"],
          "animal_delta_gap":x["delta_from_day0"]["animal"]["mean_gap_opponent_minus_self"],
          "high_animal_delta_gap":x["delta_from_day0"]["high_animal"]["mean_gap_opponent_minus_self"],
          "committed_delta_gap":x["delta_from_day0"]["committed"]["mean_gap_opponent_minus_self"],
          "land_per_1k_total":{"self":x["per_1000_spend"]["land"]["total_outflow"].get("self_absolute_mean"),"opponent":x["per_1000_spend"]["land"]["total_outflow"].get("opponent_absolute_mean")},
          "high_crop_per_1k_total":{"self":x["per_1000_spend"]["high_crop"]["total_outflow"].get("self_absolute_mean"),"opponent":x["per_1000_spend"]["high_crop"]["total_outflow"].get("opponent_absolute_mean")},
          "high_animal_per_1k_total":{"self":x["per_1000_spend"]["high_animal"]["total_outflow"].get("self_absolute_mean"),"opponent":x["per_1000_spend"]["high_animal"]["total_outflow"].get("opponent_absolute_mean")},
          "committed_per_1k_total":{"self":x["per_1000_spend"]["committed"]["total_outflow"].get("self_absolute_mean"),"opponent":x["per_1000_spend"]["committed"]["total_outflow"].get("opponent_absolute_mean")},
        }
    print("SB01_CASH_TO_PRODUCTIVE_STATE "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__": main()
