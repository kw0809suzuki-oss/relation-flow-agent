#!/usr/bin/env python3
import json, os
from pathlib import Path
from collections import Counter,defaultdict
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"value_source_reentry_v0_{SEED}.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    for k in ["OUTER_MEANING_OPTION_PRESERVATION_DAY","OUTER_MEANING_REALIZABLE_CAPACITY_DAY","OUTER_MEANING_CONVERSION_PATH_DAY","OUTER_MEANING_GUIDED_CONVERSION_DAY"]:
        os.environ.pop(k,None)
    os.environ["OUTER_MEANING_OBJECTIVE_PRESSURE_DAY"]="14"
    for k in ["ORIGIN_EVALUATION_LENS","ORIGIN_MODEL_CANDIDATE_EVALUATION","ORIGIN_MODEL_CANDIDATE_COMPARISON","ORIGIN_MODEL_CANDIDATE_SELECTION","ORIGIN_MODEL_CANDIDATE_DIRECTION","ORIGIN_MODEL_SELECTION_GUIDED_GENERATION","ORIGIN_MODEL_SELECTION_TO_ACTION","ORIGIN_MODEL_DIRECTIONAL_STATE_READ"]:
        os.environ[k]="0"
    os.environ["ORIGIN_DIRECTION_CONTROL_MODE"]="none"
    os.environ["ORIGIN_ABSTRACTION_TRANSMISSION"]="1"
    os.environ["ORIGIN_GUIDANCE_MODE"]="objective_pressure_guidance"
    combat.set_probe_enabled(True); combat.set_attribution_enabled(True); combat.reset_telemetry()

def composition(farm):
    crops=Counter(); animals=Counter()
    for row in farm.get("tiles",[]) or []:
        for tile in row:
            if not isinstance(tile,dict):
                continue
            kind=tile.get("kind")
            if kind=="PLANT":
                crop = tile.get("crop") or tile.get("plant") or tile.get("product") or tile.get("name") or "UNKNOWN_PLANT"
                crops[str(crop)] += 1
            animal = tile.get("animal")
            if animal:
                if isinstance(animal,dict):
                    at = animal.get("kind") or animal.get("type") or animal.get("name") or "UNKNOWN_ANIMAL"
                else:
                    at = animal
                animals[str(at)] += 1
            elif kind=="ANIMAL":
                animals["UNKNOWN_ANIMAL"] += 1
    return {"crops":dict(crops),"animals":dict(animals),
            "crop_tiles":sum(crops.values()),"animal_tiles":sum(animals.values())}

def main():
    configure()
    snapshots=[]
    sell_events=[]

    def wrapped(obs):
        day=int(obs.get("day",0) or 0)
        me=obs["farms"][obs["player"]]
        op=obs["farms"][1-obs["player"]]
        snapshots.append({
          "day":day,
          "self_money":float(me.get("money",0) or 0),
          "opp_money":float(op.get("money",0) or 0),
          "self_comp":composition(me),
          "opp_comp":composition(op)
        })
        action=combat.agent(obs)
        if 5 <= day <= 20:
            prices=dict((obs.get("market",{}) or {}).get("prices",{}) or {})
            items=defaultdict(lambda:{"units":0.0,"face_value":0.0})
            for o in action.get("market",[]) or []:
                if not isinstance(o,(list,tuple)) or len(o)<3 or o[0]!="SELL" or not isinstance(o[2],(int,float)):
                    continue
                item=str(o[1]); qty=float(o[2]); px=float(prices.get(item,0) or 0)
                items[item]["units"] += qty
                items[item]["face_value"] += qty*px
            if items:
                sell_events.append({"day":day,"items":dict(items)})
        return action

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=wrapped
    env.run(players)
    rewards=[float(s.reward) for s in env.state]

    byday=defaultdict(list)
    for s in snapshots:
        if 5 <= s["day"] <= 20:
            byday[s["day"]].append(s)

    sell_by_day=defaultdict(lambda:defaultdict(lambda:{"units":0.0,"face_value":0.0}))
    for e in sell_events:
        for item,v in e["items"].items():
            sell_by_day[e["day"]][item]["units"] += v["units"]
            sell_by_day[e["day"]][item]["face_value"] += v["face_value"]

    days=[]
    for d in range(5,21):
        if d not in byday: continue
        s=byday[d][-1]
        sells=dict(sell_by_day[d])
        days.append({
          "day":d,
          "self_money":s["self_money"],
          "opp_money":s["opp_money"],
          "money_gap":s["opp_money"]-s["self_money"],
          "self_comp":s["self_comp"],
          "opp_comp":s["opp_comp"],
          "self_sell_items":sells,
          "self_sell_face_total":sum(v["face_value"] for v in sells.values()),
          "self_sell_units_total":sum(v["units"] for v in sells.values())
        })

    for i,d in enumerate(days):
        if i==0:
            d["money_gap_change"]=None
        else:
            d["money_gap_change"]=d["money_gap"]-days[i-1]["money_gap"]

    payload={
      "schema":"kaggriculture.value-source-reentry.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"residual":rewards[1-SEAT]-rewards[SEAT]},
      "days":days,
      "boundary":"Opponent private stock and SELL actions are unobserved; visible composition is not treated as sold-output identity."
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,"self":rewards[SEAT],"opp":rewards[1-SEAT],"days":len(days)},ensure_ascii=False))

if __name__=="__main__": main()
