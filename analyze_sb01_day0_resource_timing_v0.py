#!/usr/bin/env python3
"""SB-01 Day0 Resource Timing v0.

Reuses Day0 raw State exported by Run 35831478953.
For each SEED/ANIMAL resource, derive cumulative acquired, cumulative converted,
and unconverted balance at every Day0 boundary (Day0 hour0..23 plus Day1 hour0).

No unit identity is assumed. Timing is measured on the aggregate balance:
  balance = acquired - converted.
The end-positive-streak reports how long an unconverted balance persisted into
Day1 without returning to zero.
"""
import json, statistics, sys
from pathlib import Path

CROPS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON")
ANIMALS=("GOOSE","COW","SHEEP")


def state_counts(obs):
    player=int(obs.get("player",0))
    farm=obs["farms"][player]
    private=obs.get("private",{}) or {}

    planted={c:0 for c in CROPS}
    placed={a:0 for a in ANIMALS}
    for row in farm.get("tiles",[]) or []:
        for tile in row or []:
            if not isinstance(tile,dict): continue
            c=tile.get("crop")
            if c in planted and int(tile.get("planted_day",-999))==0:
                planted[c]+=1
            a=tile.get("animal")
            if a in placed and int(tile.get("placed_day",-999))==0:
                placed[a]+=1

    seeds={c:int((private.get("seeds",{}) or {}).get(c,0) or 0) for c in CROPS}
    unplaced={a:0 for a in ANIMALS}
    shed=private.get("shed",{}) or {}
    for a in ANIMALS:
        unplaced[a]+=int(shed.get(a,0) or 0)
    for inv in private.get("inventories",[]) or []:
        if not isinstance(inv,dict): continue
        for a in ANIMALS:
            unplaced[a]+=int(inv.get(a,0) or 0)

    return {
        "seed":{c:{"acquired":seeds[c]+planted[c],"converted":planted[c],"balance":seeds[c]} for c in CROPS},
        "animal":{a:{"acquired":unplaced[a]+placed[a],"converted":placed[a],"balance":unplaced[a]} for a in ANIMALS},
    }


def timeline(raw, seat):
    key=f"seat{seat}"
    seq=[]
    for row in raw["day0_steps"]:
        seq.append({
            "boundary":int(row["hour"]),
            "label":f"D0H{int(row['hour']):02d}",
            "counts":state_counts(row[key]["observation"]),
        })
    d1=raw["day1_first"][str(seat)]["observation"]
    seq.append({"boundary":24,"label":"D1H00","counts":state_counts(d1)})
    seq=sorted(seq,key=lambda x:x["boundary"])
    return seq


def resource_timing(seq, kind, item):
    rows=[]
    prev_acq=0
    prev_conv=0
    for s in seq:
        x=s["counts"][kind][item]
        acq=x["acquired"]; conv=x["converted"]; bal=x["balance"]
        rows.append({
            "boundary":s["boundary"],"label":s["label"],
            "acquired":acq,"converted":conv,"balance":bal,
            "acquired_increment":max(0,acq-prev_acq),
            "converted_increment":max(0,conv-prev_conv),
        })
        prev_acq=max(prev_acq,acq)
        prev_conv=max(prev_conv,conv)

    # Cumulative acquisition can only increase under normal Day0 flow; use max
    # to remain robust to any later destructive action.
    end_acq=max(r["acquired"] for r in rows)
    end_conv=rows[-1]["converted"]
    end_bal=end_acq-end_conv

    first_acq=next((r["boundary"] for r in rows if r["acquired"]>0),None)
    first_conv=next((r["boundary"] for r in rows if r["converted"]>0),None)
    first_positive=next((r["boundary"] for r in rows if r["balance"]>0),None)

    # Consecutive positive balance ending at Day1 boundary.
    streak_start=None
    if rows[-1]["balance"]>0:
        i=len(rows)-1
        while i>=0 and rows[i]["balance"]>0:
            streak_start=rows[i]["boundary"]
            i-=1
    end_positive_age=(24-streak_start) if streak_start is not None else 0

    # Longest interval between boundaries during which balance remains positive.
    longest=0; current_start=None
    for r in rows:
        if r["balance"]>0 and current_start is None:
            current_start=r["boundary"]
        if r["balance"]==0 and current_start is not None:
            longest=max(longest,r["boundary"]-current_start)
            current_start=None
    if current_start is not None:
        longest=max(longest,24-current_start)

    increments=[(r["boundary"],r["acquired_increment"]) for r in rows if r["acquired_increment"]>0]
    conversions=[(r["boundary"],r["converted_increment"]) for r in rows if r["converted_increment"]>0]

    return {
        "end_acquired":end_acq,
        "end_converted":end_conv,
        "end_unconverted":end_bal,
        "first_acquired_boundary":first_acq,
        "first_converted_boundary":first_conv,
        "first_positive_unconverted_boundary":first_positive,
        "end_positive_balance_age_turns":end_positive_age,
        "longest_positive_balance_turns":longest,
        "peak_unconverted_balance":max(r["balance"] for r in rows),
        "acquisition_increments":[{"boundary":b,"units":n} for b,n in increments],
        "conversion_increments":[{"boundary":b,"units":n} for b,n in conversions],
        "timeline":rows,
    }


def mean(xs): return sum(xs)/len(xs) if xs else None
def median(xs): return statistics.median(xs) if xs else None


def metric(cases,kind,item,field):
    sv=[c["self"][kind][item][field] for c in cases]
    ov=[c["opponent"][kind][item][field] for c in cases]
    # Fields used here are numeric.
    return {
        "self_mean":mean(sv),"opponent_mean":mean(ov),
        "self_median":median(sv),"opponent_median":median(ov),
        "self_min":min(sv),"self_max":max(sv),
        "opponent_min":min(ov),"opponent_max":max(ov),
        "mean_gap_opponent_minus_self":mean([o-s for s,o in zip(sv,ov)]),
    }


def categorical_count(cases,kind,item,field):
    from collections import Counter
    return {
        "self":dict(sorted(Counter(c["self"][kind][item][field] for c in cases).items(),key=lambda kv:str(kv[0]))),
        "opponent":dict(sorted(Counter(c["opponent"][kind][item][field] for c in cases).items(),key=lambda kv:str(kv[0]))),
    }


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("sb01_day0_resource_flow_input_*.json"))
    if not files: files=sorted(root.glob("**/sb01_day0_resource_flow_input_*.json"))
    if not files: raise SystemExit("No input files")

    cases=[]
    for p in files:
        raw=json.loads(p.read_text(encoding="utf-8"))
        seat=int(raw["seat"]); opp=1-seat
        st=timeline(raw,seat); ot=timeline(raw,opp)
        self_out={"seed":{},"animal":{}}
        opp_out={"seed":{},"animal":{}}
        for c in CROPS:
            self_out["seed"][c]=resource_timing(st,"seed",c)
            opp_out["seed"][c]=resource_timing(ot,"seed",c)
        for a in ANIMALS:
            self_out["animal"][a]=resource_timing(st,"animal",a)
            opp_out["animal"][a]=resource_timing(ot,"animal",a)
        cases.append({"seed":int(raw["seed"]),"seat":seat,"self":self_out,"opponent":opp_out})

    agg={"seed":{},"animal":{}}
    fields=("end_acquired","end_converted","end_unconverted","end_positive_balance_age_turns","longest_positive_balance_turns","peak_unconverted_balance")
    for c in CROPS:
        agg["seed"][c]={f:metric(cases,"seed",c,f) for f in fields}
        agg["seed"][c]["first_acquired_boundary"]=categorical_count(cases,"seed",c,"first_acquired_boundary")
        agg["seed"][c]["first_converted_boundary"]=categorical_count(cases,"seed",c,"first_converted_boundary")
    for a in ANIMALS:
        agg["animal"][a]={f:metric(cases,"animal",a,f) for f in fields}
        agg["animal"][a]["first_acquired_boundary"]=categorical_count(cases,"animal",a,"first_acquired_boundary")
        agg["animal"][a]["first_converted_boundary"]=categorical_count(cases,"animal",a,"first_converted_boundary")

    payload={
        "schema":"kaggriculture.sb01.day0-resource-timing.v0",
        "source_run_id":35831478953,
        "battle_count":len(cases),
        "aggregate":agg,
        "cases":cases,
        "boundary":[
            "Timing is derived from retained State only.",
            "boundary 0..23 are Day0 hour states; boundary 24 is first Day1 State after the final Day0 transition.",
            "Unconverted balance is acquired minus converted at each State boundary.",
            "A long positive-balance age indicates time existed while the resource remained unconverted; it is not itself a causal explanation."
        ]
    }
    Path("sb01_day0_resource_timing_v0.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    focus={}
    for kind,items in (("seed",CROPS),("animal",ANIMALS)):
        focus[kind]={}
        for item in items:
            a=agg[kind][item]
            focus[kind][item]={
                "self_end_acquired":a["end_acquired"]["self_mean"],
                "opp_end_acquired":a["end_acquired"]["opponent_mean"],
                "self_end_converted":a["end_converted"]["self_mean"],
                "opp_end_converted":a["end_converted"]["opponent_mean"],
                "self_end_unconverted":a["end_unconverted"]["self_mean"],
                "opp_end_unconverted":a["end_unconverted"]["opponent_mean"],
                "self_unconverted_age":a["end_positive_balance_age_turns"]["self_mean"],
                "opp_unconverted_age":a["end_positive_balance_age_turns"]["opponent_mean"],
                "first_acquired_boundary":a["first_acquired_boundary"],
                "first_converted_boundary":a["first_converted_boundary"],
            }
    print("SB01_DAY0_RESOURCE_TIMING "+json.dumps({"battle_count":len(cases),"focus":focus},ensure_ascii=False,separators=(",",":")))

if __name__=="__main__": main()
