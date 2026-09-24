#!/usr/bin/env python3
"""Allocation-to-Commitment Bridge v0.

Broad audit only:
BUY_SEED -> seed stock queue -> successful PLANT -> Day4 productive State.

No individual seed lineage is inferred. Queue area is measured directly from
observed seed stock over turns (unit-turns).
"""
import glob,json,statistics,sys
from collections import defaultdict
from pathlib import Path

SEED_COST={"WHEAT":10,"CARROT":20,"TOMATO":50,"STRAWBERRY":100,"MELON":80}
CROPS=tuple(SEED_COST)

def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None

def day4_obs(raw,p):
    return raw["state_export"][str(p)]["4"]["observation"]

def initial_seed_stock(raw,p):
    tr=raw["commitment_trace"][str(p)]
    if not tr:return {c:0 for c in CROPS}
    s=tr[0].get("seed_stock",{}) or {}
    return {c:int(s.get(c,0) or 0) for c in CROPS}

def closing_seed_stock(raw,p):
    obs=day4_obs(raw,p)
    s=(obs.get("private",{}) or {}).get("seeds",{}) or {}
    return {c:int(s.get(c,0) or 0) for c in CROPS}

def buys(raw,p):
    units=defaultdict(int); cash=defaultdict(float)
    for e in raw.get("market_events",[]):
        if int(e.get("player",-1))!=p or not (0<=int(e.get("day",-1))<4):
            continue
        if e.get("op")!="BUY_SEED": continue
        crop=str(e.get("item"))
        qty=int(e.get("qty",e.get("units",0)) or 0)
        # exact logger may not retain qty; derive from cash when necessary.
        if qty<=0 and crop in SEED_COST:
            qty=int(round(max(0.0,-float(e.get("cash_delta",0) or 0))/SEED_COST[crop]))
        units[crop]+=qty
        cash[crop]+=max(0.0,-float(e.get("cash_delta",0) or 0))
    return dict(units),dict(cash)

def buy_events_by_turn(raw,p):
    out=defaultdict(lambda: defaultdict(int))
    for e in raw.get("market_events",[]):
        if int(e.get("player",-1))!=p or not (0<=int(e.get("day",-1))<4):
            continue
        if e.get("op")!="BUY_SEED":
            continue
        crop=str(e.get("item"))
        if crop not in SEED_COST:
            continue
        qty=int(e.get("qty",e.get("units",0)) or 0)
        if qty<=0:
            qty=int(round(max(0.0,-float(e.get("cash_delta",0) or 0))/SEED_COST[crop]))
        out[(int(e.get("day",0)),int(e.get("hour",0)))][crop]+=qty
    return out


def inferred_plants(raw,p):
    trace=raw["commitment_trace"][str(p)]
    buys_by_turn=buy_events_by_turn(raw,p)
    closing=closing_seed_stock(raw,p)
    out=defaultdict(int)
    by_turn=[]
    for i,row in enumerate(trace):
        before=row.get("seed_stock",{}) or {}
        if i+1<len(trace):
            after=trace[i+1].get("seed_stock",{}) or {}
        else:
            after=closing
        key=(int(row.get("day",0)),int(row.get("hour",0)))
        turn_buys=buys_by_turn.get(key,{})
        turn_plants={}
        for crop in CROPS:
            q0=int(before.get(crop,0) or 0)
            qb=int(turn_buys.get(crop,0) or 0)
            q1=int(after.get(crop,0) or 0)
            n=q0+qb-q1
            if n<0:
                raise ValueError(f"negative inferred PLANT p={p} turn={key} crop={crop}: {n}")
            if n:
                out[crop]+=n
                turn_plants[crop]=n
        if turn_plants:
            by_turn.append({
                "day":key[0],"hour":key[1],"plants":turn_plants
            })
    return dict(out),by_turn

def queue_area(raw,p):
    area=defaultdict(float)
    positive_turns=defaultdict(int)
    positive_with_empty=defaultdict(int)
    workers_when_positive=defaultdict(list)
    empty_when_positive=defaultdict(list)
    trace=raw["commitment_trace"][str(p)]
    for row in trace:
        stock=row.get("seed_stock",{}) or {}
        empty=int(row.get("empty_tiles",0) or 0)
        workers=int(row.get("workers",0) or 0)
        for crop in CROPS:
            q=int(stock.get(crop,0) or 0)
            area[crop]+=q
            if q>0:
                positive_turns[crop]+=1
                if empty>0: positive_with_empty[crop]+=1
                workers_when_positive[crop].append(workers)
                empty_when_positive[crop].append(empty)
    return {
      c:{
        "queue_unit_turns":area[c],
        "queue_positive_turns":positive_turns[c],
        "queue_positive_with_empty_turns":positive_with_empty[c],
        "mean_workers_when_queue_positive":mean(workers_when_positive[c]),
        "mean_empty_tiles_when_queue_positive":mean(empty_when_positive[c]),
      } for c in CROPS
    }

def side(raw,p):
    opening=initial_seed_stock(raw,p)
    closing=closing_seed_stock(raw,p)
    bu,bc=buys(raw,p)
    pl,plant_turns=inferred_plants(raw,p)
    qa=queue_area(raw,p)
    per={}
    for c in CROPS:
        available=opening[c]+int(bu.get(c,0) or 0)
        committed=int(pl.get(c,0) or 0)
        close=closing[c]
        per[c]={
          "opening_seed_units":opening[c],
          "buy_seed_units":int(bu.get(c,0) or 0),
          "buy_seed_cash":float(bc.get(c,0) or 0),
          "successful_plant_units":committed,
          "day4_seed_units":close,
          "commitment_rate":(committed/available if available else None),
          "day4_idle_capital":close*SEED_COST[c],
          "stock_identity_error":available-committed-close,
          **qa[c],
        }
    total_available=sum(opening[c]+int(bu.get(c,0) or 0) for c in CROPS)
    total_plants=sum(int(pl.get(c,0) or 0) for c in CROPS)
    total_close=sum(closing.values())
    return {
      "plant_turns":plant_turns,
      "per_crop":per,
      "total":{
        "available_seed_units":total_available,
        "successful_plant_units":total_plants,
        "day4_seed_units":total_close,
        "commitment_rate":(total_plants/total_available if total_available else None),
        "day4_idle_capital":sum(closing[c]*SEED_COST[c] for c in CROPS),
        "queue_unit_turns":sum(qa[c]["queue_unit_turns"] for c in CROPS),
        "stock_identity_error":sum(per[c]["stock_identity_error"] for c in CROPS),
      }
    }

def pair_summary(cases,path):
    def pick(side):
        x=side
        for k in path:x=x[k]
        return None if x is None else float(x)
    sv=[pick(c["self"]) for c in cases]
    ov=[pick(c["opponent"]) for c in cases]
    pairs=[(s,o) for s,o in zip(sv,ov) if s is not None and o is not None]
    s=[x[0] for x in pairs];o=[x[1] for x in pairs]
    gaps=[b-a for a,b in pairs]
    return {
      "self_absolute_mean":mean(s),
      "opponent_absolute_mean":mean(o),
      "mean_gap_opponent_minus_self":mean(gaps),
      "opponent_ahead_cases":sum(g>0 for g in gaps),
      "self_ahead_cases":sum(g<0 for g in gaps),
      "equal_cases":sum(g==0 for g in gaps),
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
        s=side(raw,seat);o=side(raw,1-seat)
        if abs(s["total"]["stock_identity_error"])>1e-9 or abs(o["total"]["stock_identity_error"])>1e-9:
            raise SystemExit(f"seed stock identity failed seed {raw['seed']}")
        cases.append({"seed":int(raw["seed"]),"seat":seat,"self":s,"opponent":o})

    totals={k:pair_summary(cases,["total",k]) for k in (
      "available_seed_units","successful_plant_units","day4_seed_units",
      "commitment_rate","day4_idle_capital","queue_unit_turns"
    )}
    crops={}
    for crop in CROPS:
        crops[crop]={k:pair_summary(cases,["per_crop",crop,k]) for k in (
          "buy_seed_units","successful_plant_units","day4_seed_units",
          "commitment_rate","day4_idle_capital","queue_unit_turns",
          "queue_positive_turns","queue_positive_with_empty_turns",
          "mean_workers_when_queue_positive","mean_empty_tiles_when_queue_positive"
        )}

    out={
      "schema":"kaggriculture.strong-origin-v2.allocation-to-commitment-bridge.v0",
      "battle_count":len(cases),
      "totals":totals,
      "crops":crops,
      "cases":cases,
      "boundary":[
        "No Candidate or policy mutation is introduced.",
        "Seeds are treated as fungible stock; no purchased seed is individually matched to a PLANT.",
        "Queue unit-turns is the observed area under seed-stock-over-time, not literal per-seed waiting time.",
        "Successful PLANT is derived by public stock conservation each turn: seed_before + executed BUY_SEED - seed_after.",
        "Commitment Rate uses opening seed stock plus executed BUY_SEED as available units and derived successful PLANT as commitment."
        "Idle Capital is Day4 seed stock marked at public seed purchase cost.",
        "Worker and empty-tile values are context while queue is positive, not causal attribution.",
        "Action-level diagnosis is deferred unless a stable queue separator appears."
      ]
    }
    Path("allocation_to_commitment_bridge_v0.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    compact={"battle_count":len(cases),"totals":totals,"WHEAT":crops["WHEAT"],"MELON":crops["MELON"],"STRAWBERRY":crops["STRAWBERRY"]}
    print("ALLOCATION_TO_COMMITMENT_BRIDGE "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
