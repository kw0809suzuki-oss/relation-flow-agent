#!/usr/bin/env python3
"""SB-01 Day0 Hand Spatial Allocation v0.

Measures hand position diversity in aligned Day0 pre-States and localizes
same-tile hand PLANT collisions. No strategic interpretation.
"""
import json,statistics,sys
from pathlib import Path
from collections import Counter,defaultdict

def mean(xs):return sum(xs)/len(xs) if xs else None
def med(xs):return statistics.median(xs) if xs else None

def side(raw,seat):
    key=f"seat{seat}"
    rows=[]
    first_colocated=None
    first_plant_collision=None
    totals=Counter()
    by_hour={}

    for tr in raw["transitions"]:
        pre=tr[key]["pre_observation"]; act=tr[key]["action"] or {}
        player=int(pre.get("player",seat)); farm=pre["farms"][player]
        hands=[tuple(p) for p in (farm.get("hands",[]) or [])]
        unique=len(set(hands))
        excess=len(hands)-unique
        hour=int(tr["from"]["hour"])
        if excess>0 and first_colocated is None:first_colocated=hour

        hand_actions=act.get("hands",[]) if isinstance(act,dict) else []
        plant_targets=[]
        for idx,a in enumerate(hand_actions if isinstance(hand_actions,list) else []):
            if idx>=len(hands):continue
            if isinstance(a,list) and len(a)>=2 and a[0]=="PLANT":
                plant_targets.append((hands[idx],a[1]))

        groups=defaultdict(int)
        for pos,crop in plant_targets:groups[(pos,crop)]+=1
        plant_collision=sum(max(0,n-1) for n in groups.values())
        if plant_collision>0 and first_plant_collision is None:first_plant_collision=hour

        totals["hand_state_count"]+=1
        totals["hand_count_sum"]+=len(hands)
        totals["unique_position_sum"]+=unique
        totals["colocated_excess_sum"]+=excess
        totals["turns_with_any_colocation"]+=1 if excess>0 else 0
        totals["hand_plant_requests"]+=len(plant_targets)
        totals["unique_hand_plant_targets"]+=len(groups)
        totals["hand_plant_collision_excess"]+=plant_collision
        totals["turns_with_plant_collision"]+=1 if plant_collision>0 else 0
        by_hour[str(hour)]={
            "hands":len(hands),"unique_positions":unique,"colocated_excess":excess,
            "hand_plant_requests":len(plant_targets),"unique_hand_plant_targets":len(groups),
            "plant_collision_excess":plant_collision,
        }
        rows.append(by_hour[str(hour)])

    return {
        "mean_hands_per_pre_state": totals["hand_count_sum"]/totals["hand_state_count"] if totals["hand_state_count"] else 0,
        "mean_unique_hand_positions_per_pre_state": totals["unique_position_sum"]/totals["hand_state_count"] if totals["hand_state_count"] else 0,
        "total_colocated_excess_hand_states": totals["colocated_excess_sum"],
        "turns_with_any_colocation": totals["turns_with_any_colocation"],
        "hand_plant_requests":totals["hand_plant_requests"],
        "unique_hand_plant_targets":totals["unique_hand_plant_targets"],
        "hand_plant_collision_excess":totals["hand_plant_collision_excess"],
        "turns_with_plant_collision":totals["turns_with_plant_collision"],
        "first_colocated_hour": first_colocated,
        "first_plant_collision_hour": first_plant_collision,
        "by_hour":by_hour,
    }

def summarize(cases,field):
    sv=[c["self"][field] for c in cases if c["self"][field] is not None]
    ov=[c["opponent"][field] for c in cases if c["opponent"][field] is not None]
    return {
      "self_mean":mean(sv),"opponent_mean":mean(ov),
      "self_median":med(sv),"opponent_median":med(ov),
      "self_defined":len(sv),"opponent_defined":len(ov)
    }

def count_values(cases,field):
    return {
      "self":dict(sorted(Counter(c["self"][field] for c in cases).items(),key=lambda kv:str(kv[0]))),
      "opponent":dict(sorted(Counter(c["opponent"][field] for c in cases).items(),key=lambda kv:str(kv[0])))
    }

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("sb01_day0_aligned_transitions_v1_*.json"))
    if not files:files=sorted(root.glob("**/sb01_day0_aligned_transitions_v1_*.json"))
    cases=[]
    for p in files:
        raw=json.loads(p.read_text(encoding="utf-8"));seat=int(raw["seat"])
        cases.append({"seed":raw["seed"],"self":side(raw,seat),"opponent":side(raw,1-seat)})
    fields=("mean_hands_per_pre_state","mean_unique_hand_positions_per_pre_state","total_colocated_excess_hand_states","turns_with_any_colocation","hand_plant_requests","unique_hand_plant_targets","hand_plant_collision_excess","turns_with_plant_collision")
    agg={f:summarize(cases,f) for f in fields}
    agg["first_colocated_hour"]=count_values(cases,"first_colocated_hour")
    agg["first_plant_collision_hour"]=count_values(cases,"first_plant_collision_hour")

    # Hour profile means.
    hour_profile={}
    for h in range(24):
        hour_profile[str(h)]={}
        for metric in ("hands","unique_positions","colocated_excess","hand_plant_requests","unique_hand_plant_targets","plant_collision_excess"):
            sv=[c["self"]["by_hour"][str(h)][metric] for c in cases]
            ov=[c["opponent"]["by_hour"][str(h)][metric] for c in cases]
            hour_profile[str(h)][metric]={"self":mean(sv),"opponent":mean(ov)}

    payload={"schema":"kaggriculture.sb01.day0-hand-spatial-allocation.v0","source_run_id":35836285226,"battle_count":len(cases),"aggregate":agg,"hour_profile":hour_profile,"cases":cases,
      "boundary":["Colocation is a physical State fact: multiple hired hands share the same tile in the pre-State.","PLANT collision excess counts duplicate same-crop PLANT targets among hands in the same turn.","No claim is made yet about why hands became colocated."]}
    Path("sb01_day0_hand_spatial_allocation_v0.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SB01_DAY0_HAND_SPATIAL "+json.dumps({"battle_count":len(cases),"aggregate":agg,"hour_profile":hour_profile},ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
