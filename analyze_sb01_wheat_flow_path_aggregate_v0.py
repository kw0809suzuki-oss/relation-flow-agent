#!/usr/bin/env python3
"""Aggregate SB-01 WHEAT flow path over 50 paired seeds.

No cause is assigned to between-market WHEAT movement.
The key purpose is to close the Day0-7 WHEAT stock/cash path before judging
whether BUY_PRODUCT:WHEAT represents replaceable allocation.
"""
import json, math, statistics, sys
from pathlib import Path

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None
def q(xs,p):
    ys=sorted(xs)
    if not ys:return None
    pos=(len(ys)-1)*p; lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi:return ys[lo]
    return ys[lo]*(hi-pos)+ys[hi]*(pos-lo)
def summ(xs):
    return {"n":len(xs),"mean":mean(xs),"median":median(xs),"q25":q(xs,.25),"q75":q(xs,.75),
            "positive":sum(x>0 for x in xs),"negative":sum(x<0 for x in xs),"zero":sum(x==0 for x in xs),
            "min":min(xs) if xs else None,"max":max(xs) if xs else None}

def side_metrics(r):
    rows=r["market_rows"]
    buy_cash=sum(float(x["buy_wheat_cash"]) for x in rows)
    sell_cash=sum(float(x["sell_wheat_cash"]) for x in rows)
    overlap_units=sum(min(int(x["buy_wheat_units"]),int(x["sell_wheat_units"])) for x in rows)
    overlap_turns=sum(int(x["buy_wheat_units"])>0 and int(x["sell_wheat_units"])>0 for x in rows)
    return {
      "initial":float(r["initial_wheat"]),
      "buy_units":float(r["buy_units"]),
      "sell_units":float(r["sell_units"]),
      "buy_cash":buy_cash,
      "sell_cash":sell_cash,
      "wheat_market_cash_net":sell_cash-buy_cash,
      "nonmarket_net":float(r["between_market_net_change"]),
      "nonmarket_gross_decrease":float(r["between_market_gross_decrease"]),
      "nonmarket_gross_increase":float(r["between_market_gross_increase"]),
      "day8_stock":float(r["day8_start_wheat"]),
      "purchase_events":float(len(r["purchase_events"])),
      "same_turn_overlap_units":float(overlap_units),
      "same_turn_overlap_turns":float(overlap_turns),
    }

def purchase_state_summary(raws,side):
    events=[]
    for r in raws:
        for e in r[side]["purchase_events"]:
            st=e["state_before_first_buy"]
            w=float(e["units"])
            events.append({
              "weight":w,
              "pre_stock":float(st["wheat"]["total"]),
              "shed":float(st["wheat"]["shed"]),
              "carried":float(st["wheat"]["carried"]),
              "animal_total":float(st["animal_total"]),
              "unfed_total":float(st["unfed_total"]),
              "money":float(st["money"]),
            })
    def weighted(k):
        den=sum(e["weight"] for e in events)
        return sum(e[k]*e["weight"] for e in events)/den if den else None
    return {
      "event_count":len(events),
      "unit_count":sum(e["weight"] for e in events),
      "event_median_pre_stock":median([e["pre_stock"] for e in events]),
      "unit_weighted_pre_stock":weighted("pre_stock"),
      "unit_weighted_shed_stock":weighted("shed"),
      "unit_weighted_carried_stock":weighted("carried"),
      "unit_weighted_animal_total":weighted("animal_total"),
      "unit_weighted_unfed_total":weighted("unfed_total"),
      "unit_weighted_money":weighted("money"),
    }

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/sb01_wheat_flow_path_7*.json"))
    if len(files)!=50: raise SystemExit(f"Expected 50 files, got {len(files)}")
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    bad=[r["seed"] for r in raws if r["self"]["mass_balance_error"]!=0 or r["opponent"]["mass_balance_error"]!=0 or r["self"]["market_phase_max_abs_error"]!=0 or r["opponent"]["market_phase_max_abs_error"]!=0]
    if bad: raise SystemExit(f"Balance failure: {bad}")

    rows=[]
    keys=None
    for raw in raws:
        s=side_metrics(raw["self"]); o=side_metrics(raw["opponent"])
        if keys is None: keys=list(s)
        row={"seed":raw["seed"],"seat":raw["seat"],"self":s,"opponent":o,
             "self_minus_opponent":{k:s[k]-o[k] for k in s}}
        rows.append(row)

    absolute={}
    paired={}
    for k in keys:
        absolute[k]={"self":summ([r["self"][k] for r in rows]),"opponent":summ([r["opponent"][k] for r in rows])}
        paired[k]=summ([r["self_minus_opponent"][k] for r in rows])

    # Mechanical balance of the paired extra-WHEAT path:
    # Day8 gap = initial gap + buy gap - sell gap + nonmarket gap.
    balance=[]
    for r in rows:
        g=r["self_minus_opponent"]
        reconstructed=g["initial"]+g["buy_units"]-g["sell_units"]+g["nonmarket_net"]
        balance.append(reconstructed-g["day8_stock"])

    payload={
      "schema":"kaggriculture.sb01.wheat-flow-path-aggregate.v0",
      "battle_count":50,
      "absolute":absolute,
      "self_minus_opponent":paired,
      "purchase_state":{
        "self":purchase_state_summary(raws,"self"),
        "opponent":purchase_state_summary(raws,"opponent"),
      },
      "paired_path_balance_error":summ(balance),
      "rows":rows,
      "boundary":[
        "All stock/cash paths close mechanically before interpretation.",
        "Same-turn overlap is min(realized BUY units, realized SELL units) in the same market phase; it is descriptive churn only.",
        "Between-market movement remains net observed WHEAT movement with no FEED/HARVEST/necessity/waste label.",
        "BUY cash is gross outflow and SELL cash is gross inflow; wheat_market_cash_net reports their realized net through Day7."
      ]
    }
    Path("sb01_wheat_flow_path_aggregate_v0.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SB01_WHEAT_FLOW_AGG "+json.dumps({
      "battle_count":50,
      "absolute":absolute,
      "self_minus_opponent":paired,
      "purchase_state":payload["purchase_state"],
      "paired_balance_error":payload["paired_path_balance_error"],
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
