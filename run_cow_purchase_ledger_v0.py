#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make
import export_scale_baseline_v1 as base
import g17_agent as combat

SEED=int(os.environ["BATTLE_SEED"]); SEAT=int(os.environ["BATTLE_SEAT"])
OPPONENT=base.OPPONENT; OUT=Path(f"cow_purchase_ledger_v0_{SEED}.json")

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="1"; os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    for k in ["OUTER_MEANING_OPTION_PRESERVATION_DAY","OUTER_MEANING_REALIZABLE_CAPACITY_DAY","OUTER_MEANING_CONVERSION_PATH_DAY","OUTER_MEANING_GUIDED_CONVERSION_DAY"]: os.environ.pop(k,None)
    os.environ["OUTER_MEANING_OBJECTIVE_PRESSURE_DAY"]="14"
    for k in ["ORIGIN_EVALUATION_LENS","ORIGIN_MODEL_CANDIDATE_EVALUATION","ORIGIN_MODEL_CANDIDATE_COMPARISON","ORIGIN_MODEL_CANDIDATE_SELECTION","ORIGIN_MODEL_CANDIDATE_DIRECTION","ORIGIN_MODEL_SELECTION_GUIDED_GENERATION","ORIGIN_MODEL_SELECTION_TO_ACTION","ORIGIN_MODEL_DIRECTIONAL_STATE_READ"]: os.environ[k]="0"
    os.environ["ORIGIN_DIRECTION_CONTROL_MODE"]="none"; os.environ["ORIGIN_ABSTRACTION_TRANSMISSION"]="1"; os.environ["ORIGIN_GUIDANCE_MODE"]="objective_pressure_guidance"
    combat.set_probe_enabled(True); combat.set_attribution_enabled(True); combat.reset_telemetry()

def parse(action,prices):
    cows=0; sell=0.0; buy_other=0.0
    for o in (action.get("market",[]) if isinstance(action,dict) else []) or []:
        if not isinstance(o,(list,tuple)) or not o: continue
        cmd=str(o[0])
        if cmd=="BUY_ANIMAL" and len(o)>=3 and str(o[1])=="COW":
            cows += float(o[2])
        elif len(o)>=3 and isinstance(o[2],(int,float)):
            item=str(o[1]); qty=float(o[2]); px=float(prices.get(item,0) or 0)
            if cmd=="SELL": sell += px*qty
            elif cmd in ("BUY_PRODUCT","BUY_SEED","BUY_ANIMAL"): buy_other += px*qty
    return cows,sell,buy_other

def main():
    configure(); rows=[]; pending=None
    def wrapped(obs):
        nonlocal pending
        me=obs["farms"][obs["player"]]; day=int(obs.get("day",0) or 0); money=float(me.get("money",0) or 0)
        if pending is not None:
            pending["money_after"]=money
            pending["money_delta"]=money-pending["money_before"]
            pending["priced_market_net_excluding_cow"]=pending["sell_face"]-pending["priced_buy_other_face"]
            pending["residual_excluding_cow"]=pending["money_delta"]-pending["priced_market_net_excluding_cow"]
            pending["residual_plus_400_per_cow"]=pending["residual_excluding_cow"]+400*pending["cow_buy_units"]
            rows.append(pending); pending=None
        action=combat.agent(obs)
        if 5 <= day <= 20:
            prices=dict((obs.get("market",{}) or {}).get("prices",{}) or {})
            cows,sell,buy_other=parse(action,prices)
            if cows>0:
                pending={"day":day,"money_before":money,"cow_buy_units":cows,"sell_face":sell,"priced_buy_other_face":buy_other}
        return action
    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    players=[OPPONENT,OPPONENT]; players[SEAT]=wrapped; env.run(players)
    rewards=[float(s.reward) for s in env.state]
    payload={"schema":"kaggriculture.cow-purchase-ledger.v0","seed":SEED,"seat":SEAT,
      "terminal":{"self":rewards[SEAT],"opponent":rewards[1-SEAT],"residual":rewards[1-SEAT]-rewards[SEAT]},
      "cow_purchase_turns":rows,
      "boundary":"Checks whether unexplained residual closes after adding 400 per requested COW; request is not treated as settlement proof."}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"seed":SEED,"cow_turns":len(rows)},ensure_ascii=False))
if __name__=="__main__": main()
