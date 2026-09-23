#!/usr/bin/env python3
"""SB-01 Day0 Resource Acquisition -> Conversion accounting v0.

Mechanical accounting only.

SEED:
  acquired = Day1 remaining seed + Day0 plants still present with planted_day=0
  converted = Day0 plants present at Day1
  unconverted = Day1 remaining seed

ANIMAL:
  acquired = Day1 placed animals with placed_day=0 + Day1 unplaced animal inventory
  converted = placed
  unconverted = unplaced

HIRE:
  acquired = maximum Day0 hand count observed
  converted = hands that performed >=1 economic state-changing unit action after appearing
  unconverted = acquired - converted

HIRE economic-action classification is explicit and does not claim terminal value.
"""
import json, statistics, sys
from pathlib import Path

CROPS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON")
ANIMALS=("GOOSE","COW","SHEEP")
MOVE={"NORTH","SOUTH","EAST","WEST","PASS"}
ECONOMIC_OPS={
    "PICKUP","DROP","PLACE","PLANT","WATER","HARVEST","FERTILIZE","DIG",
    "BUILD_COOP","BUILD_PASTURE","FEED","COLLECT_FERTILIZER","CARE"
}


def farm_and_private(obs, seat):
    player=int(obs.get("player",seat))
    # For each seat observation, player should equal that seat.
    farm=obs["farms"][player]
    private=obs.get("private",{}) or {}
    return farm,private


def count_day1(side_obs):
    seat=int(side_obs.get("player",0))
    farm,private=farm_and_private(side_obs,seat)

    planted={c:0 for c in CROPS}
    placed={a:0 for a in ANIMALS}
    for row in farm.get("tiles",[]) or []:
        for tile in row or []:
            if not isinstance(tile,dict): continue
            crop=tile.get("crop")
            if crop in planted and int(tile.get("planted_day",-999))==0:
                planted[crop]+=1
            animal=tile.get("animal")
            if animal in placed and int(tile.get("placed_day",-999))==0:
                placed[animal]+=1

    seeds={c:int((private.get("seeds",{}) or {}).get(c,0) or 0) for c in CROPS}
    unplaced={a:0 for a in ANIMALS}
    shed=private.get("shed",{}) or {}
    for a in ANIMALS:
        unplaced[a]+=int(shed.get(a,0) or 0)
    for inv in private.get("inventories",[]) or []:
        if not isinstance(inv,dict): continue
        for a in ANIMALS:
            unplaced[a]+=int(inv.get(a,0) or 0)

    seed_flow={}
    for c in CROPS:
        acquired=planted[c]+seeds[c]
        seed_flow[c]={
            "acquired":acquired,
            "converted_planted":planted[c],
            "unconverted_remaining":seeds[c],
            "conversion_rate":(planted[c]/acquired if acquired else None),
        }

    animal_flow={}
    for a in ANIMALS:
        acquired=placed[a]+unplaced[a]
        animal_flow[a]={
            "acquired":acquired,
            "converted_placed":placed[a],
            "unconverted_remaining":unplaced[a],
            "conversion_rate":(placed[a]/acquired if acquired else None),
        }
    return seed_flow,animal_flow


def hand_flow(day0_steps, seat):
    max_hands=0
    economic_by_idx=set()
    active_by_idx=set()
    economic_actions_by_idx={}
    nonpass_actions_by_idx={}

    key=f"seat{seat}"
    for row in day0_steps:
        obs=(row[key] or {}).get("observation") or {}
        act=(row[key] or {}).get("action") or {}
        player=int(obs.get("player",seat))
        farm=(obs.get("farms") or [])[player]
        hands=farm.get("hands",[]) or []
        max_hands=max(max_hands,len(hands))

        hand_actions=act.get("hands",[]) if isinstance(act,dict) else []
        if not isinstance(hand_actions,list): continue
        for idx,a in enumerate(hand_actions):
            if idx>=len(hands): continue
            if not isinstance(a,list) or not a: continue
            op=a[0]
            if op!="PASS":
                active_by_idx.add(idx)
                nonpass_actions_by_idx[idx]=nonpass_actions_by_idx.get(idx,0)+1
            if op in ECONOMIC_OPS:
                economic_by_idx.add(idx)
                economic_actions_by_idx[idx]=economic_actions_by_idx.get(idx,0)+1

    acquired=max_hands
    converted=len([i for i in range(acquired) if i in economic_by_idx])
    active=len([i for i in range(acquired) if i in active_by_idx])
    return {
        "acquired_successful_hires":acquired,
        "hands_with_any_nonpass_action":active,
        "hands_with_economic_action":converted,
        "unconverted_no_economic_action":acquired-converted,
        "economic_hand_conversion_rate":(converted/acquired if acquired else None),
        "economic_action_count":sum(economic_actions_by_idx.values()),
        "nonpass_action_count":sum(nonpass_actions_by_idx.values()),
        "economic_actions_by_hand_index":{str(k):v for k,v in sorted(economic_actions_by_idx.items())},
    }


def mean(xs): return sum(xs)/len(xs) if xs else None
def med(xs): return statistics.median(xs) if xs else None


def summarize(cases, getter):
    sv=[getter(c["self"]) for c in cases]
    ov=[getter(c["opponent"]) for c in cases]
    gaps=[o-s for s,o in zip(sv,ov)]
    return {
        "self_absolute_mean":mean(sv),
        "opponent_absolute_mean":mean(ov),
        "mean_gap_opponent_minus_self":mean(gaps),
        "median_gap_opponent_minus_self":med(gaps),
        "opponent_ahead_cases":sum(g>0 for g in gaps),
        "self_ahead_cases":sum(g<0 for g in gaps),
        "equal_cases":sum(g==0 for g in gaps),
    }


def rate_summary(cases, path):
    def pull(side):
        x=side
        for p in path: x=x[p]
        return x
    sr=[pull(c["self"]) for c in cases if pull(c["self"]) is not None]
    orr=[pull(c["opponent"]) for c in cases if pull(c["opponent"]) is not None]
    return {
        "self_mean_rate":mean(sr),
        "opponent_mean_rate":mean(orr),
        "self_defined_cases":len(sr),
        "opponent_defined_cases":len(orr),
    }


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("sb01_day0_resource_flow_input_*.json"))
    if not files: files=sorted(root.glob("**/sb01_day0_resource_flow_input_*.json"))
    if not files: raise SystemExit("No Day0 resource flow input")

    cases=[]
    for p in files:
        raw=json.loads(p.read_text(encoding="utf-8"))
        seat=int(raw["seat"]); opp=1-seat
        if not raw["day1_first"].get(str(seat)) or not raw["day1_first"].get(str(opp)):
            raise SystemExit(f"Missing Day1 for {raw['seed']}")
        ss,sa=count_day1(raw["day1_first"][str(seat)]["observation"])
        os,oa=count_day1(raw["day1_first"][str(opp)]["observation"])
        sh=hand_flow(raw["day0_steps"],seat)
        oh=hand_flow(raw["day0_steps"],opp)
        cases.append({
            "seed":int(raw["seed"]),"seat":seat,"terminal":raw["terminal"],
            "self":{"seed":ss,"animal":sa,"hire":sh},
            "opponent":{"seed":os,"animal":oa,"hire":oh},
        })

    agg={"seed":{},"animal":{}}
    for c in CROPS:
        agg["seed"][c]={
            "acquired":summarize(cases,lambda s,k=c:s["seed"][k]["acquired"]),
            "converted":summarize(cases,lambda s,k=c:s["seed"][k]["converted_planted"]),
            "unconverted":summarize(cases,lambda s,k=c:s["seed"][k]["unconverted_remaining"]),
            "conversion_rate":rate_summary(cases,["seed",c,"conversion_rate"]),
        }
    for a in ANIMALS:
        agg["animal"][a]={
            "acquired":summarize(cases,lambda s,k=a:s["animal"][k]["acquired"]),
            "converted":summarize(cases,lambda s,k=a:s["animal"][k]["converted_placed"]),
            "unconverted":summarize(cases,lambda s,k=a:s["animal"][k]["unconverted_remaining"]),
            "conversion_rate":rate_summary(cases,["animal",a,"conversion_rate"]),
        }

    agg["hire"]={
        "acquired_successful_hires":summarize(cases,lambda s:s["hire"]["acquired_successful_hires"]),
        "hands_with_economic_action":summarize(cases,lambda s:s["hire"]["hands_with_economic_action"]),
        "unconverted_no_economic_action":summarize(cases,lambda s:s["hire"]["unconverted_no_economic_action"]),
        "economic_action_count":summarize(cases,lambda s:s["hire"]["economic_action_count"]),
        "conversion_rate":rate_summary(cases,["hire","economic_hand_conversion_rate"]),
    }

    payload={
        "schema":"kaggriculture.sb01.day0-resource-flow.v0",
        "battle_count":len(cases),
        "aggregate":agg,
        "cases":cases,
        "boundary":[
            "Acquired/converted/unconverted are mechanical accounting categories.",
            "SEED conversion means present as a Day0-planted crop at first Day1 State.",
            "ANIMAL conversion means present as a Day0-placed animal at first Day1 State.",
            "HIRE conversion means the hired hand executed >=1 explicitly listed state-changing economic unit action on Day0.",
            "No claim is made that every converted resource was strategically good or that every unconverted resource caused terminal loss.",
        ]
    }
    Path("sb01_day0_resource_flow_v0.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    compact={
        "battle_count":len(cases),
        "seed":{
            c:{
                "self_acquired":agg["seed"][c]["acquired"]["self_absolute_mean"],
                "opp_acquired":agg["seed"][c]["acquired"]["opponent_absolute_mean"],
                "self_converted":agg["seed"][c]["converted"]["self_absolute_mean"],
                "opp_converted":agg["seed"][c]["converted"]["opponent_absolute_mean"],
                "self_unconverted":agg["seed"][c]["unconverted"]["self_absolute_mean"],
                "opp_unconverted":agg["seed"][c]["unconverted"]["opponent_absolute_mean"],
                "self_rate":agg["seed"][c]["conversion_rate"]["self_mean_rate"],
                "opp_rate":agg["seed"][c]["conversion_rate"]["opponent_mean_rate"],
            } for c in CROPS
        },
        "animal":{
            a:{
                "self_acquired":agg["animal"][a]["acquired"]["self_absolute_mean"],
                "opp_acquired":agg["animal"][a]["acquired"]["opponent_absolute_mean"],
                "self_converted":agg["animal"][a]["converted"]["self_absolute_mean"],
                "opp_converted":agg["animal"][a]["converted"]["opponent_absolute_mean"],
                "self_unconverted":agg["animal"][a]["unconverted"]["self_absolute_mean"],
                "opp_unconverted":agg["animal"][a]["unconverted"]["opponent_absolute_mean"],
                "self_rate":agg["animal"][a]["conversion_rate"]["self_mean_rate"],
                "opp_rate":agg["animal"][a]["conversion_rate"]["opponent_mean_rate"],
            } for a in ANIMALS
        },
        "hire":{
            "self_acquired":agg["hire"]["acquired_successful_hires"]["self_absolute_mean"],
            "opp_acquired":agg["hire"]["acquired_successful_hires"]["opponent_absolute_mean"],
            "self_converted_hands":agg["hire"]["hands_with_economic_action"]["self_absolute_mean"],
            "opp_converted_hands":agg["hire"]["hands_with_economic_action"]["opponent_absolute_mean"],
            "self_unconverted_hands":agg["hire"]["unconverted_no_economic_action"]["self_absolute_mean"],
            "opp_unconverted_hands":agg["hire"]["unconverted_no_economic_action"]["opponent_absolute_mean"],
            "self_rate":agg["hire"]["conversion_rate"]["self_mean_rate"],
            "opp_rate":agg["hire"]["conversion_rate"]["opponent_mean_rate"],
            "self_economic_actions":agg["hire"]["economic_action_count"]["self_absolute_mean"],
            "opp_economic_actions":agg["hire"]["economic_action_count"]["opponent_absolute_mean"],
        }
    }
    print("SB01_DAY0_RESOURCE_FLOW "+json.dumps(compact,ensure_ascii=False,separators=(",",":")))

if __name__=="__main__": main()
