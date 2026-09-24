#!/usr/bin/env python3
"""Commitment Sequence Audit v0.

No candidate, no policy mutation, no Direction model.

Reads public State/market/event facts and reconstructs a coarse economic sequence:
commitment -> realized output/SELL -> productive spend -> next State.

Seeds are fungible; successful PLANT counts are derived from public seed-stock
conservation, never individual seed lineage.
"""
import glob,json,statistics,sys
from collections import defaultdict
from pathlib import Path

SEED_COST={"WHEAT":10,"CARROT":20,"TOMATO":50,"STRAWBERRY":100,"MELON":80}
CROPS=tuple(SEED_COST)
PRODUCTIVE_OPS=("HIRE","BUY_LAND","BUY_SEED","BUY_ANIMAL")

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None

def closing_seed_stock(raw,p):
    # Day8 snapshot is the conservation boundary for the extended trace.
    obs=raw["state_export"][str(p)]["8"]["observation"]
    s=(obs.get("private",{}) or {}).get("seeds",{}) or {}
    return {c:int(s.get(c,0) or 0) for c in CROPS}

def buy_events(raw,p):
    out=defaultdict(lambda:defaultdict(int))
    for e in raw.get("market_events",[]):
        if int(e.get("player",-1))!=p or e.get("op")!="BUY_SEED": continue
        d=int(e.get("day",-1)); h=int(e.get("hour",-1))
        if not (0<=d<8): continue
        crop=str(e.get("item"))
        if crop not in SEED_COST: continue
        qty=int(e.get("qty",e.get("units",0)) or 0)
        if qty<=0:
            qty=int(round(max(0.0,-float(e.get("cash_delta",0) or 0))/SEED_COST[crop]))
        out[(d,h)][crop]+=qty
    return out

def infer_plants(raw,p):
    tr=raw["commitment_trace"][str(p)]
    buys=buy_events(raw,p)
    close=closing_seed_stock(raw,p)
    events=[]
    for i,row in enumerate(tr):
        before=row.get("seed_stock",{}) or {}
        after=(tr[i+1].get("seed_stock",{}) if i+1<len(tr) else close)
        key=(int(row.get("day",0)),int(row.get("hour",0)))
        b=buys.get(key,{})
        for crop in CROPS:
            q0=int(before.get(crop,0) or 0)
            qb=int(b.get(crop,0) or 0)
            q1=int(after.get(crop,0) or 0)
            n=q0+qb-q1
            if n<0:
                raise ValueError(f"negative inferred plant p={p} {key} {crop} {n}")
            if n>0:
                events.append({"day":key[0],"hour":key[1],"crop":crop,"units":n})
    return events

def first_event(events, pred):
    xs=[e for e in events if pred(e)]
    if not xs:return None
    e=min(xs,key=lambda x:(int(x.get("day",999)),int(x.get("hour",999))))
    return {"day":int(e.get("day",0)),"hour":int(e.get("hour",0)),"item":e.get("item") or e.get("crop"),"op":e.get("op")}

def summarize_side(raw,p):
    plants=infer_plants(raw,p)
    market=[e for e in raw.get("market_events",[]) if int(e.get("player",-1))==p and 0<=int(e.get("day",-1))<8]
    harvest=[e for e in raw.get("harvest_events",[]) if int(e.get("player",-1))==p and 0<=int(e.get("day",-1))<8]
    production=[e for e in raw.get("production_events",[]) if int(e.get("player",-1))==p and 0<=int(e.get("result_state_day",e.get("transition_day",-1)))<=8]

    commit_by_day=defaultdict(lambda:defaultdict(float))
    for e in plants:
        commit_by_day[str(e["day"])][e["crop"]]+=float(e["units"])

    sell_by_day=defaultdict(lambda:defaultdict(float))
    for e in market:
        if e.get("op")=="SELL":
            sell_by_day[str(int(e["day"]))][str(e.get("item"))]+=float(e.get("cash_delta",0) or 0)

    productive_by_day=defaultdict(lambda:defaultdict(float))
    for e in market:
        if e.get("op") in PRODUCTIVE_OPS:
            productive_by_day[str(int(e["day"]))][str(e.get("op"))]+=max(0.0,-float(e.get("cash_delta",0) or 0))

    first_commit={}
    for crop in CROPS:
        xs=[e for e in plants if e["crop"]==crop]
        if xs:
            e=min(xs,key=lambda x:(x["day"],x["hour"]))
            first_commit[crop]={"day":e["day"],"hour":e["hour"]}

    sell_items=sorted({str(e.get("item")) for e in market if e.get("op")=="SELL"})
    first_sell={}
    for item in sell_items:
        ev=first_event(market,lambda e:e.get("op")=="SELL" and str(e.get("item"))==item)
        if ev:first_sell[item]=ev

    first_productive={}
    for op in PRODUCTIVE_OPS:
        ev=first_event(market,lambda e:e.get("op")==op)
        if ev:first_productive[op]=ev

    first_harvest={}
    for item in sorted({str(e.get("item")) for e in harvest}):
        ev=first_event(harvest,lambda e:str(e.get("item"))==item)
        if ev:first_harvest[item]=ev

    def state(day):
        obs=raw["state_export"][str(p)][str(day)]["observation"]
        farm=obs["farms"][p]
        tiles=farm.get("tiles",[]) or []
        crops=defaultdict(int);animals=defaultdict(int);empty=0
        for row in tiles:
            for t in row or []:
                if t is None: empty+=1
                elif isinstance(t,dict) and t.get("kind")=="PLANT": crops[str(t.get("crop"))]+=1
                elif isinstance(t,dict) and t.get("animal"): animals[str(t.get("animal"))]+=1
        return {
            "cash":float(farm.get("money",0) or 0),
            "land_quadrants":len(farm.get("unlocked_quadrants",[]) or []),
            "empty_tiles":empty,
            "crop_count":dict(sorted(crops.items())),
            "animal_count":dict(sorted(animals.items())),
        }

    return {
        "commit_by_day":{d:dict(sorted(v.items())) for d,v in sorted(commit_by_day.items(),key=lambda kv:int(kv[0]))},
        "sell_cash_by_day":{d:dict(sorted(v.items())) for d,v in sorted(sell_by_day.items(),key=lambda kv:int(kv[0]))},
        "productive_spend_by_day":{d:dict(sorted(v.items())) for d,v in sorted(productive_by_day.items(),key=lambda kv:int(kv[0]))},
        "first_commit":first_commit,
        "first_harvest":first_harvest,
        "first_sell":first_sell,
        "first_productive_spend":first_productive,
        "day4_state":state(4),
        "day8_state":state(8),
    }

def mean_nested(cases,side,key):
    # key maps day -> item -> amount
    days=set()
    for c in cases: days.update(c[side][key].keys())
    out={}
    for d in sorted(days,key=int):
        items=set()
        for c in cases: items.update(c[side][key].get(d,{}).keys())
        out[d]={}
        for item in sorted(items):
            out[d][item]=mean([float(c[side][key].get(d,{}).get(item,0) or 0) for c in cases])
    return out

def mode_first(cases,side,key,item):
    vals=[]
    for c in cases:
        e=c[side][key].get(item)
        if e: vals.append((e["day"],e["hour"]))
    if not vals:return None
    # report mean timing and coverage, no claim of identical order.
    return {
        "coverage":len(vals),
        "mean_day":mean([x[0] for x in vals]),
        "mean_hour":mean([x[1] for x in vals]),
        "min":min(vals),
        "max":max(vals),
    }

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/state_transition_growth_audit_v0_*.json"))
    if not files:
        files=[Path(p) for p in glob.glob(str(root/"**"/"state_transition_growth_audit_v0_*.json"),recursive=True)]
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    if not raws: raise SystemExit("No raw audit files")
    raws.sort(key=lambda x:int(x["seed"]))

    cases=[]
    for raw in raws:
        seat=int(raw["seat"])
        cases.append({
            "seed":int(raw["seed"]),
            "seat":seat,
            "self":summarize_side(raw,seat),
            "opponent":summarize_side(raw,1-seat),
        })

    items=set()
    for c in cases:
        items.update(c["self"]["first_sell"].keys());items.update(c["opponent"]["first_sell"].keys())
    crops=set()
    for c in cases:
        crops.update(c["self"]["first_commit"].keys());crops.update(c["opponent"]["first_commit"].keys())

    out={
        "schema":"kaggriculture.strong-origin-v2.commitment-sequence-audit.v0",
        "battle_count":len(cases),
        "self":{
            "commit_by_day_mean":mean_nested(cases,"self","commit_by_day"),
            "sell_cash_by_day_mean":mean_nested(cases,"self","sell_cash_by_day"),
            "productive_spend_by_day_mean":mean_nested(cases,"self","productive_spend_by_day"),
            "first_commit_timing":{c:mode_first(cases,"self","first_commit",c) for c in sorted(crops)},
            "first_sell_timing":{i:mode_first(cases,"self","first_sell",i) for i in sorted(items)},
        },
        "opponent":{
            "commit_by_day_mean":mean_nested(cases,"opponent","commit_by_day"),
            "sell_cash_by_day_mean":mean_nested(cases,"opponent","sell_cash_by_day"),
            "productive_spend_by_day_mean":mean_nested(cases,"opponent","productive_spend_by_day"),
            "first_commit_timing":{c:mode_first(cases,"opponent","first_commit",c) for c in sorted(crops)},
            "first_sell_timing":{i:mode_first(cases,"opponent","first_sell",i) for i in sorted(items)},
        },
        "cases":cases,
        "boundary":[
            "No Candidate and no Direction model are introduced.",
            "Sequence is descriptive public-world timing, not copied opponent policy.",
            "Seed commitment is inferred from public seed-stock conservation; no individual seed lineage is claimed.",
            "SELL and productive spend are temporally ordered but Cash fungibility prevents source-to-use attribution.",
            "No composite score is created. Repeated sequence relations, if any, are observations only."
        ]
    }
    Path("commitment_sequence_audit_v0.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    compact={
      "battle_count":len(cases),
      "self_commit":out["self"]["commit_by_day_mean"],
      "opp_commit":out["opponent"]["commit_by_day_mean"],
      "self_sell":out["self"]["sell_cash_by_day_mean"],
      "opp_sell":out["opponent"]["sell_cash_by_day_mean"],
      "self_prod_spend":out["self"]["productive_spend_by_day_mean"],
      "opp_prod_spend":out["opponent"]["productive_spend_by_day_mean"],
      "self_first_commit":out["self"]["first_commit_timing"],
      "opp_first_commit":out["opponent"]["first_commit_timing"],
      "self_first_sell":out["self"]["first_sell_timing"],
      "opp_first_sell":out["opponent"]["first_sell_timing"],
    }
    print("COMMITMENT_SEQUENCE_AUDIT "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
