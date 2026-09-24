#!/usr/bin/env python3
"""G1 Formation Timeline Audit v0.

Reconstructs Day4->8 non-WHEAT G1 productive-State entry timing from existing
hourly public State traces, then maps each (asset, origin_day) group to public
maturity timing and observed Day8->12 production/harvest.

No Candidate, Direction, readiness score, or policy mutation.
No new Battle is required.
"""
import glob,json,sys
from collections import Counter,defaultdict
from pathlib import Path

START,END=4,8
NEXT_END=12

CROPS={
    "CARROT":{"first":2,"max_day":3,"ongoing":False},
    "TOMATO":{"first":8,"max_day":8,"ongoing":True},
    "STRAWBERRY":{"first":10,"max_day":10,"ongoing":True},
    "MELON":{"first":10,"max_day":12,"ongoing":False},
}
ANIMALS={
    "GOOSE":{"first":4,"product":"EGG"},
    "COW":{"first":8,"product":"MILK"},
    "SHEEP":{"first":6,"product":"WOOL"},
}


def mean(xs): return sum(xs)/len(xs) if xs else None


def next_production_day(asset,origin):
    if asset in ANIMALS:
        return origin+ANIMALS[asset]["first"]
    r=CROPS[asset]
    if r["ongoing"]:
        return origin+r["first"]
    # Non-ongoing crops gain additional yield from WATER beginning halfway
    # through the public max-yield window.
    return origin+(r["max_day"]+1)//2


def harvest_eligible_day(asset,origin):
    if asset in ANIMALS:
        return origin+ANIMALS[asset]["first"]
    return origin+CROPS[asset]["first"]


def asset_from_event_item(item):
    return {"MILK":"COW","WOOL":"SHEEP","EGG":"GOOSE"}.get(item,item)


def observed_entries(raw,p):
    prev=Counter()
    out=[]
    for row in raw["commitment_trace"][str(p)]:
        cur=Counter(
            (a["asset_type"],str(a["asset"]),int(a["origin_day"]))
            for a in row.get("maturity_assets",[]) or []
        )
        for key,n in (cur-prev).items():
            typ,asset,origin=key
            if n>0 and START<=origin<END and asset!="WHEAT":
                for _ in range(n):
                    out.append({
                        "day":int(row["day"]),"hour":int(row["hour"]),
                        "asset_type":typ,"asset":asset,"origin_day":origin,
                    })
        prev=cur
    return out


def day8_groups(raw,p):
    obs=raw["state_export"][str(p)]["8"]["observation"]
    farm=obs["farms"][p]
    groups=defaultdict(lambda:{"asset_count":0.0,"held_yield":0.0,"future_units":0.0})

    for row in farm.get("tiles",[]) or []:
        for t in row or []:
            if not isinstance(t,dict):
                continue
            if t.get("kind")=="PLANT":
                asset=str(t.get("crop"))
                if asset=="WHEAT" or asset not in CROPS:
                    continue
                origin=int(t.get("planted_day",8))
                if not START<=origin<END:
                    continue
                held=int(t.get("yield_units",0) or 0)
                r=CROPS[asset]
                if r["ongoing"]:
                    future_events=0
                    interval=1 if asset=="TOMATO" else 2
                    max_yield=4
                    for n in range(max_yield):
                        d=origin+r["first"]+n*interval
                        if d>8 and d<=30:
                            future_events+=1
                    units=held+future_events
                else:
                    window_start=(r["max_day"]+1)//2
                    first=max(8,origin+window_start)
                    last=min(29,origin+r["max_day"])
                    opportunities=max(0,last-first+1)
                    units=min(6,held+opportunities)
                g=groups[(asset,origin)]
                g["asset_count"]+=1; g["held_yield"]+=held; g["future_units"]+=units

            elif t.get("animal") in ANIMALS:
                asset=str(t["animal"])
                origin=int(t.get("placed_day",8))
                if not START<=origin<END:
                    continue
                held=int(t.get("yield_units",0) or 0)
                first=origin+ANIMALS[asset]["first"]
                interval={"GOOSE":1,"COW":2,"SHEEP":3}[asset]
                d=first; events=0
                while d<=30:
                    if d>8: events+=1
                    d+=interval
                g=groups[(asset,origin)]
                g["asset_count"]+=1; g["held_yield"]+=held
                g["future_units"]+=held+events
    return groups


def actual_next_cycle(raw,p):
    production=defaultdict(float)
    harvest=defaultdict(float)
    for e in raw.get("production_events",[]) or []:
        if int(e.get("player",-1))!=p:
            continue
        origin=int(e.get("asset_origin_day",999))
        if not START<=origin<END:
            continue
        d=int(e.get("result_state_day",e.get("transition_day",-1)))
        # Strictly before the saved Day12 hour-0 State. DAILY refresh into
        # Day12 is already reflected there; Day12 WATER actions are not.
        if not (8<d<12 or (d==12 and e.get("source")!="WATER")):
            continue
        asset=asset_from_event_item(str(e.get("item")))
        production[(asset,origin)]+=float(e.get("units",0) or 0)

    for e in raw.get("harvest_events",[]) or []:
        if int(e.get("player",-1))!=p:
            continue
        origin=int(e.get("asset_origin_day",999))
        d=int(e.get("day",-1))
        if START<=origin<END and 8<=d<12:
            asset=asset_from_event_item(str(e.get("item")))
            harvest[(asset,origin)]+=float(e.get("units",0) or 0)
    return production,harvest


def side_case(raw,p):
    entries=observed_entries(raw,p)
    groups=day8_groups(raw,p)
    prod,harv=actual_next_cycle(raw,p)

    first_any=min((x["day"]*24+x["hour"] for x in entries),default=None)
    near=[x for x in entries if next_production_day(x["asset"],x["origin_day"])<NEXT_END]
    real=[x for x in entries if harvest_eligible_day(x["asset"],x["origin_day"])<NEXT_END]

    rows=[]
    for (asset,origin),v in sorted(groups.items(),key=lambda kv:(kv[0][1],kv[0][0])):
        times=[x for x in entries if x["asset"]==asset and x["origin_day"]==origin]
        rows.append({
            "asset":asset,"origin_day":origin,
            "state_entry_times":[{"day":x["day"],"hour":x["hour"]} for x in times],
            "asset_count":v["asset_count"],"held_yield_day8":v["held_yield"],
            "future_units_day8":v["future_units"],
            "next_production_day":next_production_day(asset,origin),
            "harvest_eligible_day":harvest_eligible_day(asset,origin),
            "production_inside_next_cycle":next_production_day(asset,origin)<NEXT_END,
            "harvest_inside_next_cycle":harvest_eligible_day(asset,origin)<NEXT_END,
            "actual_production_before_day12_snapshot":prod.get((asset,origin),0.0),
            "actual_harvest_day8_to_11":harv.get((asset,origin),0.0),
        })

    return {
        "first_any_entry_step":first_any,
        "first_next_cycle_production_entry_step":min((x["day"]*24+x["hour"] for x in near),default=None),
        "first_next_cycle_harvest_entry_step":min((x["day"]*24+x["hour"] for x in real),default=None),
        "groups":rows,
        "day8":{
            "asset_count":sum(v["asset_count"] for v in groups.values()),
            "future_units":sum(v["future_units"] for v in groups.values()),
            "next_cycle_production_asset_count":sum(v["asset_count"] for (a,o),v in groups.items() if next_production_day(a,o)<NEXT_END),
            "next_cycle_production_future_units":sum(v["future_units"] for (a,o),v in groups.items() if next_production_day(a,o)<NEXT_END),
            "next_cycle_harvest_asset_count":sum(v["asset_count"] for (a,o),v in groups.items() if harvest_eligible_day(a,o)<NEXT_END),
            "next_cycle_harvest_future_units":sum(v["future_units"] for (a,o),v in groups.items() if harvest_eligible_day(a,o)<NEXT_END),
            "actual_production_before_day12_snapshot":sum(prod.values()),
            "actual_harvest_day8_to_11":sum(harv.values()),
        }
    }


def agg(cases,side,key):
    vals=[c[side]["day8"][key] for c in cases]
    return mean(vals)


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("**/state_transition_growth_audit_v0_*.json"))
    if not files:
        files=[Path(x) for x in glob.glob(str(root/"**"/"state_transition_growth_audit_v0_*.json"),recursive=True)]
    raws=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    raws.sort(key=lambda x:int(x["seed"]))
    cases=[]
    for raw in raws:
        seat=int(raw["seat"])
        cases.append({
            "seed":int(raw["seed"]),"seat":seat,
            "self":side_case(raw,seat),
            "opponent":side_case(raw,1-seat),
        })

    out={
        "schema":"kaggriculture.strong-origin-v2.g1-formation-timeline-audit.v0",
        "battle_count":len(cases),
        "day8_summary":{
            "self":{k:agg(cases,"self",k) for k in (
                "asset_count","future_units","next_cycle_production_asset_count",
                "next_cycle_production_future_units","next_cycle_harvest_asset_count",
                "next_cycle_harvest_future_units","actual_production_before_day12_snapshot",
                "actual_harvest_day8_to_11")},
            "opponent":{k:agg(cases,"opponent",k) for k in (
                "asset_count","future_units","next_cycle_production_asset_count",
                "next_cycle_production_future_units","next_cycle_harvest_asset_count",
                "next_cycle_harvest_future_units","actual_production_before_day12_snapshot",
                "actual_harvest_day8_to_11")},
        },
        "first_entry_steps":{
            "self_any":sorted(set(c["self"]["first_any_entry_step"] for c in cases)),
            "opponent_any":sorted(set(c["opponent"]["first_any_entry_step"] for c in cases)),
            "self_next_cycle_production":sorted(set(c["self"]["first_next_cycle_production_entry_step"] for c in cases),key=lambda x:(x is None,x)),
            "opponent_next_cycle_production":sorted(set(c["opponent"]["first_next_cycle_production_entry_step"] for c in cases),key=lambda x:(x is None,x)),
            "self_next_cycle_harvest":sorted(set(c["self"]["first_next_cycle_harvest_entry_step"] for c in cases),key=lambda x:(x is None,x)),
            "opponent_next_cycle_harvest":sorted(set(c["opponent"]["first_next_cycle_harvest_entry_step"] for c in cases),key=lambda x:(x is None,x)),
        },
        "cases":cases,
        "boundary":[
            "No Candidate, Direction, readiness score, or policy mutation is introduced.",
            "State-entry time is the first hourly trace where the asset appears in productive State; it is not asserted to equal market purchase time.",
            "G1 means non-WHEAT productive assets with public origin day in [4,8).",
            "Next production opportunity and HARVEST eligibility are separate public-rule times.",
            "For non-ongoing crops, WATER can add yield before HARVEST becomes legal.",
            "The audit tests time placement, not asset optimality.",
        ]
    }
    Path("g1_formation_timeline_audit_v0.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("G1_FORMATION_TIMELINE_AUDIT "+json.dumps({
        "battle_count":len(cases),"day8_summary":out["day8_summary"],
        "first_entry_steps":out["first_entry_steps"]
    },ensure_ascii=False,separators=(",",":")))


if __name__=="__main__":
    main()
