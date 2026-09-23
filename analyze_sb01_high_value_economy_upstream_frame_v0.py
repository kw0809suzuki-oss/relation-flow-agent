#!/usr/bin/env python3
"""SB-01 High-Value Economy Upstream Frame v0.

Existing artifacts only. No new Battle and no new Observer.

Frame:
- Day 0..6 from early daily derived cases
- Day 8/10/12 from economic-layer derived cases
- cumulative realized structural investment from exact daily Cash ledgers

No composite score and no causal conclusion.
"""
import json, sys
from pathlib import Path

DAYS=(0,1,2,3,4,5,6,8,10,12)
HIGH_VALUE={
  "STRAWBERRY":("crop","STRAWBERRY","STRAWBERRY"),
  "MELON":("crop","MELON","MELON"),
  "MILK":("animal","COW","MILK"),
  "WOOL":("animal","SHEEP","WOOL"),
}

def mean(xs): return sum(xs)/len(xs) if xs else None

def summarize(vals_self, vals_opp):
    gaps=[o-s for s,o in zip(vals_self,vals_opp)]
    return {
      "self_absolute_mean":mean(vals_self),
      "opponent_absolute_mean":mean(vals_opp),
      "mean_gap_opponent_minus_self":mean(gaps),
      "opponent_ahead_cases":sum(g>0 for g in gaps),
      "self_ahead_cases":sum(g<0 for g in gaps),
      "equal_cases":sum(g==0 for g in gaps),
      "min_gap":min(gaps) if gaps else None,
      "max_gap":max(gaps) if gaps else None,
    }

def load_json_one(root, name):
    hits=list(root.glob(f"**/{name}"))
    if not hits: raise SystemExit(f"Missing {name}")
    return json.loads(hits[0].read_text(encoding="utf-8"))

def index_cases(payload):
    return {int(c["seed"]):c for c in payload["cases"]}

def load_cash_cases(root):
    hits=list(root.glob("**/sb01_exact_cash_flow_daily_*.json"))
    hits=[p for p in hits if "aggregate" not in p.name]
    out={}
    for p in hits:
        r=json.loads(p.read_text(encoding="utf-8"))
        out[int(r["seed"])]=r
    if len(out)!=50:
        raise SystemExit(f"Expected 50 daily Cash files, got {len(out)}")
    bad=[s for s,r in out.items() if r["self"]["error"]!=0 or r["opponent"]["error"]!=0]
    if bad: raise SystemExit(f"Cash reconstruction error: {bad}")
    return out

def side_day(seed,day,early,later):
    src=early if day<=6 else later
    return src[seed]["days"][str(day)]

def invest_through(r, side, day):
    daily=r[side].get("daily_ledger",{})
    keys={
      "seed":lambda k:k.startswith("BUY_SEED:"),
      "animal":lambda k:k.startswith("BUY_ANIMAL:"),
      "hire":lambda k:k=="HIRE",
      "land":lambda k:k=="BUY_LAND",
      "buy_product":lambda k:k.startswith("BUY_PRODUCT:"),
    }
    out={k:0.0 for k in keys}
    for d in range(0,day+1):
        led=daily.get(str(d),{}) or {}
        for lk,v in led.items():
            for cat,pred in keys.items():
                if pred(lk): out[cat] += -float(v)  # expenditure as positive amount
    out["structural_total"]=out["seed"]+out["animal"]+out["hire"]+out["land"]
    return out

def get_stock(side,item):
    return float(side["liquidatable_inventory"]["by_item"].get(item,{}).get("quantity",0))

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    early=index_cases(load_json_one(root,"sb01_early_daily_economic_localization_v0.json"))
    later=index_cases(load_json_one(root,"sb01_economic_layers_v0.json"))
    cash=load_cash_cases(root)
    seeds=sorted(set(early)&set(later)&set(cash))
    if len(seeds)!=50: raise SystemExit(f"Expected 50 common seeds, got {len(seeds)}")

    days={}
    for day in DAYS:
        rows=[(s,side_day(s,day,early,later)) for s in seeds]

        def sm(getter):
            return summarize(
              [getter(r["self"]) for _,r in rows],
              [getter(r["opponent"]) for _,r in rows]
            )

        entry={
          "cash":sm(lambda x:float(x["cash"])),
          "land_unlocked_tiles":sm(lambda x:float(x["uncommitted_capacity"]["unlocked_tiles"])),
          "empty_unlocked_tiles":sm(lambda x:float(x["uncommitted_capacity"]["empty_unlocked_tiles"])),
          "hands":sm(lambda x:float(x["uncommitted_capacity"]["current_hands"])),
          "high_value":{},
          "investment_through_day":{},
        }

        for product,(kind,source,stock_item) in HIGH_VALUE.items():
            if kind=="crop":
                counts=sm(lambda x,k=source:float(x["committed_production"]["crop_count"].get(k,0)))
            else:
                counts=sm(lambda x,k=source:float(x["committed_production"]["animal_count"].get(k,0)))
            stock=sm(lambda x,k=stock_item:get_stock(x,k))
            entry["high_value"][product]={
              "source_type":kind,
              "source":source,
              "physical_count":counts,
              "sellable_stock_quantity":stock,
            }

        for cat in ("seed","animal","hire","land","structural_total","buy_product"):
            sv=[invest_through(cash[s],"self",day)[cat] for s in seeds]
            ov=[invest_through(cash[s],"opponent",day)[cat] for s in seeds]
            entry["investment_through_day"][cat]=summarize(sv,ov)

        days[str(day)]=entry

    # Mechanical first-day localization for opponent mean ahead.
    metrics={}
    def record(name, getter):
        first=None
        series=[]
        for d in DAYS:
            s=getter(days[str(d)])
            gap=s["mean_gap_opponent_minus_self"]
            series.append({"day":d,"gap":gap,"opponent_ahead_cases":s["opponent_ahead_cases"]})
            if first is None and gap>0: first=d
        metrics[name]={"first_day_opponent_mean_ahead":first,"series":series}

    record("land_unlocked_tiles",lambda d:d["land_unlocked_tiles"])
    record("hands",lambda d:d["hands"])
    for product in HIGH_VALUE:
        record(f"{product}_physical_count",lambda d,p=product:d["high_value"][p]["physical_count"])
        record(f"{product}_sellable_stock",lambda d,p=product:d["high_value"][p]["sellable_stock_quantity"])
    for cat in ("seed","animal","hire","land","structural_total"):
        record(f"cumulative_{cat}_investment",lambda d,c=cat:d["investment_through_day"][c])

    payload={
      "schema":"kaggriculture.sb01.high-value-economy-upstream-frame.v0",
      "battle_count":50,
      "days":days,
      "mechanical_localization":metrics,
      "boundary":[
        "Existing artifacts only; no new Battle or Observer.",
        "Counts, stock quantities, Cash, land, hands and realized investment are kept as separate axes.",
        "Structural investment = realized BUY_SEED + BUY_ANIMAL + HIRE + BUY_LAND expenditure only.",
        "BUY_PRODUCT is reported separately and is not included in structural investment.",
        "First-day localization means first sampled day with opponent mean greater than self mean; it is not causal evidence.",
        "No commodity, resource, or investment axis is promoted to a strategy target by this analysis."
      ]
    }
    Path("sb01_high_value_economy_upstream_frame_v0.json").write_text(
      json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )

    compact={
      "battle_count":50,
      "first_days":{k:v["first_day_opponent_mean_ahead"] for k,v in metrics.items()},
      "days":{
        str(d):{
          "cash_gap":days[str(d)]["cash"]["mean_gap_opponent_minus_self"],
          "land_gap":days[str(d)]["land_unlocked_tiles"]["mean_gap_opponent_minus_self"],
          "hands_gap":days[str(d)]["hands"]["mean_gap_opponent_minus_self"],
          "strawberry_count_gap":days[str(d)]["high_value"]["STRAWBERRY"]["physical_count"]["mean_gap_opponent_minus_self"],
          "melon_count_gap":days[str(d)]["high_value"]["MELON"]["physical_count"]["mean_gap_opponent_minus_self"],
          "cow_count_gap":days[str(d)]["high_value"]["MILK"]["physical_count"]["mean_gap_opponent_minus_self"],
          "sheep_count_gap":days[str(d)]["high_value"]["WOOL"]["physical_count"]["mean_gap_opponent_minus_self"],
          "strawberry_stock_gap":days[str(d)]["high_value"]["STRAWBERRY"]["sellable_stock_quantity"]["mean_gap_opponent_minus_self"],
          "melon_stock_gap":days[str(d)]["high_value"]["MELON"]["sellable_stock_quantity"]["mean_gap_opponent_minus_self"],
          "milk_stock_gap":days[str(d)]["high_value"]["MILK"]["sellable_stock_quantity"]["mean_gap_opponent_minus_self"],
          "wool_stock_gap":days[str(d)]["high_value"]["WOOL"]["sellable_stock_quantity"]["mean_gap_opponent_minus_self"],
          "structural_investment_gap":days[str(d)]["investment_through_day"]["structural_total"]["mean_gap_opponent_minus_self"],
          "seed_investment_gap":days[str(d)]["investment_through_day"]["seed"]["mean_gap_opponent_minus_self"],
          "animal_investment_gap":days[str(d)]["investment_through_day"]["animal"]["mean_gap_opponent_minus_self"],
          "hire_investment_gap":days[str(d)]["investment_through_day"]["hire"]["mean_gap_opponent_minus_self"],
          "land_investment_gap":days[str(d)]["investment_through_day"]["land"]["mean_gap_opponent_minus_self"],
        } for d in DAYS
      }
    }
    print("SB01_HIGH_VALUE_UPSTREAM "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__": main()
