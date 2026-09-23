#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT
OUT=Path(f"crop_loss_overlay_rewrite_v0_{SEED}.json")

CROP_CLASSES={"WATER","HARVEST","PLANT","DIG"}
LIVESTOCK_CLASSES={"FEED","CARE","PLACE","BUILD_PASTURE","COLLECT_FERTILIZER","DROP","PICKUP"}

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

def snaps():
    return ((((combat.get_trace() or {}).get("observe",{}) or {}).get("body",{}) or {}).get("snapshots",[]) or [])

def farm_state(obs):
    me=obs["farms"][obs["player"]]
    crops=animals=prod=0
    for row in me.get("tiles",[]) or []:
        for tile in row:
            if not isinstance(tile,dict): continue
            if tile.get("kind")=="PLANT":
                crops+=1; prod+=1
            if tile.get("animal") is not None or tile.get("kind")=="ANIMAL":
                animals+=1; prod+=1
    return {
      "day":int(obs.get("day",0) or 0),
      "money":float(me.get("money",0) or 0),
      "hands":len(me.get("hands",[]) or []),
      "crops":crops,"animals":animals,"production":prod
    }

def flat(action):
    if not isinstance(action,dict): return []
    out=[("farmer",action.get("farmer"))]
    for i,a in enumerate(action.get("hands",[]) or []): out.append((f"hand{i}",a))
    return out

def verb(a):
    return str(a[0]) if isinstance(a,(list,tuple)) and a else None

def main():
    configure()
    state_by_turn={}
    def wrapped(obs):
        state_by_turn[len(state_by_turn)]=farm_state(obs)
        return combat.agent(obs)

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=wrapped
    env.run(players)
    rewards=[float(s.reward) for s in env.state]

    ss=snaps()
    day_last={}
    for t,s in state_by_turn.items():
        if 4 <= s["day"] <= 13: day_last[s["day"]]=(t,s)

    crop_loss_days=[]
    for d in range(5,13):
        if d in day_last and d+1 in day_last:
            cur=day_last[d][1]["crops"]; nxt=day_last[d+1][1]["crops"]
            if nxt < cur: crop_loss_days.append({"day":d,"next_day":d+1,"crop_delta":nxt-cur})

    windows=[]
    for loss in crop_loss_days:
        d=loss["day"]
        candidates=[s for s in ss if int(s.get("day",0) or 0)==d]
        tail=candidates[-6:]
        rows=[]
        for s in tail:
            b=dict(s.get("base_action",{}) or {})
            a=dict(s.get("action",{}) or {})
            bf=dict(flat(b)); af=dict(flat(a))
            changes=[]
            for slot in sorted(set(bf)|set(af)):
                bv=bf.get(slot); av=af.get(slot)
                if bv!=av:
                    changes.append({
                      "slot":slot,"base":bv,"actual":av,
                      "base_verb":verb(bv),"actual_verb":verb(av),
                      "base_crop_direct":verb(bv) in CROP_CLASSES,
                      "actual_livestock_direct":verb(av) in LIVESTOCK_CLASSES
                    })
            rows.append({
              "turn":s.get("turn"),"day":s.get("day"),
              "changes":changes,
              "market_base":b.get("market",[]),"market_actual":a.get("market",[])
            })
        windows.append({**loss,"turns":rows})

    crop_to_livestock=sum(
      1 for w in windows for r in w["turns"] for c in r["changes"]
      if c["base_crop_direct"] and c["actual_livestock_direct"]
    )
    all_overrides=sum(len(r["changes"]) for w in windows for r in w["turns"])
    payload={
      "schema":"kaggriculture.crop-loss-overlay-rewrite.v0",
      "seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"residual":rewards[1-SEAT]-rewards[SEAT]},
      "crop_loss_days":crop_loss_days,
      "windows":windows,
      "summary":{"all_overrides":all_overrides,"crop_direct_to_livestock_direct":crop_to_livestock},
      "boundary":"Observed rewrite adjacency before crop loss; not causal proof."
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,"loss_days":crop_loss_days,"overrides":all_overrides,"crop_to_livestock":crop_to_livestock},ensure_ascii=False))

if __name__=="__main__": main()
