#!/usr/bin/env python3
"""SB-01 Day0 occupied-PLANT decomposition v0.

Decomposes invalid PLANT-on-occupied outcomes into:
- pre-existing occupied target
- same-turn collision after an earlier PLANT filled an initially empty target
and records the pre-existing occupant kind.

Uses aligned transitions from Run 35836285226.
"""
import copy,json,statistics,sys
from pathlib import Path
from collections import Counter

CROPS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON")


def occupant_kind(tile):
    if tile is None:return "EMPTY"
    if tile=="LOCKED":return "LOCKED"
    if isinstance(tile,dict):
        if tile.get("crop") in CROPS:return "PLANT_"+tile["crop"]
        if "animal" in tile:return "ANIMAL_"+str(tile.get("animal"))
        if tile.get("kind"):return str(tile.get("kind"))
    return "OTHER"


def side(raw,seat):
    key=f"seat{seat}"
    out=Counter()
    by_crop={c:Counter() for c in CROPS}
    by_actor=Counter()
    details=[]

    for tr in raw["transitions"]:
        pre=tr[key]["pre_observation"]; act=tr[key]["action"] or {}
        player=int(pre.get("player",seat)); farm=pre["farms"][player]; private=pre.get("private",{}) or {}
        positions=[tuple(farm.get("farmer",[0,0]))]+[tuple(p) for p in (farm.get("hands",[]) or [])]
        actions=[act.get("farmer",["PASS"])]
        ha=act.get("hands",[])
        if isinstance(ha,list):actions.extend(ha)

        demand=Counter()
        for a in actions:
            if isinstance(a,list) and len(a)>=2 and a[0]=="PLANT" and a[1] in CROPS:demand[a[1]]+=1
        seeds={c:int((private.get("seeds",{}) or {}).get(c,0) or 0) for c in CROPS}
        blocked={c for c,n in demand.items() if n>seeds[c]}
        tiles=copy.deepcopy(farm["tiles"])

        for idx,a in enumerate(actions):
            if not (isinstance(a,list) and len(a)>=2 and a[0]=="PLANT" and a[1] in CROPS):continue
            crop=a[1]
            actor="MAIN" if idx==0 else "HAND"
            out["issued"]+=1; by_crop[crop]["issued"]+=1; by_actor[f"{actor}_issued"]+=1

            if crop in blocked:
                out["seed_blocked"]+=1; by_crop[crop]["seed_blocked"]+=1
                continue
            x,y=positions[idx]
            pre_tile=farm["tiles"][y][x]
            cur_tile=tiles[y][x]

            if pre_tile is not None:
                kind=occupant_kind(pre_tile)
                out["pre_existing_occupied"]+=1
                by_crop[crop]["pre_existing_occupied"]+=1
                out["pre_occupant_"+kind]+=1
                by_crop[crop]["pre_occupant_"+kind]+=1
                by_actor[f"{actor}_pre_existing_occupied"]+=1
                details.append({"seed":raw["seed"],"from":tr["from"],"crop":crop,"actor":actor,"position":[x,y],"outcome":"pre_existing_occupied","occupant":kind})
                continue
            if cur_tile is not None:
                kind=occupant_kind(cur_tile)
                out["same_turn_collision"]+=1
                by_crop[crop]["same_turn_collision"]+=1
                by_actor[f"{actor}_same_turn_collision"]+=1
                details.append({"seed":raw["seed"],"from":tr["from"],"crop":crop,"actor":actor,"position":[x,y],"outcome":"same_turn_collision","occupant":kind})
                continue
            if seeds[crop]<=0:
                out["seed_depleted"]+=1; by_crop[crop]["seed_depleted"]+=1
                continue

            tiles[y][x]={"kind":"PLANT","crop":crop,"planted_day":0}
            seeds[crop]-=1
            out["valid"]+=1; by_crop[crop]["valid"]+=1; by_actor[f"{actor}_valid"]+=1

    return {"total":dict(out),"by_crop":{c:dict(by_crop[c]) for c in CROPS},"by_actor":dict(by_actor),"details":details}


def mean(xs):return sum(xs)/len(xs) if xs else None
def med(xs):return statistics.median(xs) if xs else None


def get(d,*path):
    for p in path:d=d.get(p,{}) if isinstance(d,dict) else {}
    return d if isinstance(d,(int,float)) else 0


def summary(cases,path):
    sv=[get(c["self"],*path) for c in cases]; ov=[get(c["opponent"],*path) for c in cases]
    return {"self_mean":mean(sv),"opponent_mean":mean(ov),"gap":mean([o-s for s,o in zip(sv,ov)]),"self_median":med(sv),"opponent_median":med(ov)}


def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else ".")
    files=sorted(root.glob("sb01_day0_aligned_transitions_v1_*.json"))
    if not files:files=sorted(root.glob("**/sb01_day0_aligned_transitions_v1_*.json"))
    cases=[]
    for p in files:
        raw=json.loads(p.read_text(encoding="utf-8")); seat=int(raw["seat"])
        cases.append({"seed":raw["seed"],"self":side(raw,seat),"opponent":side(raw,1-seat)})

    keys=["issued","valid","pre_existing_occupied","same_turn_collision","seed_blocked","seed_depleted"]
    agg={"total":{k:summary(cases,("total",k)) for k in keys},"wheat":{},"actor":{}}
    wheat_keys=set()
    actor_keys=set()
    for c in cases:
        wheat_keys.update(c["self"]["by_crop"]["WHEAT"]);wheat_keys.update(c["opponent"]["by_crop"]["WHEAT"])
        actor_keys.update(c["self"]["by_actor"]);actor_keys.update(c["opponent"]["by_actor"])
    agg["wheat"]={k:summary(cases,("by_crop","WHEAT",k)) for k in sorted(wheat_keys)}
    agg["actor"]={k:summary(cases,("by_actor",k)) for k in sorted(actor_keys)}

    payload={"schema":"kaggriculture.sb01.day0-occupied-plant-decomposition.v0","source_run_id":35836285226,"battle_count":len(cases),"aggregate":agg,"cases":cases,
      "boundary":["pre_existing_occupied means target was already non-empty in the pre-State.","same_turn_collision means target was empty in pre-State but an earlier PLANT in the same unit-action order filled it.","No strategic explanation is inferred."]}
    Path("sb01_day0_occupied_plant_decomposition_v0.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    print("SB01_DAY0_OCCUPIED_PLANT "+json.dumps({"battle_count":len(cases),"total":agg["total"],"wheat":agg["wheat"],"actor":agg["actor"]},ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":main()
