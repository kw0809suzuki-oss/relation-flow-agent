#!/usr/bin/env python3
import json, os
from pathlib import Path
from kaggle_environments import make

import export_scale_baseline_v1 as base
import whole_flow_control_agent as baseline
import cow_first_purchase_suppress_v0 as candidate

OPPONENT = base.OPPONENT
FRESH10 = [(4402 + i, i % 2) for i in range(10)]
FOCUS_TURNS = {197, 198}

def configure():
    base._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    baseline.set_control_enabled(False)
    baseline.set_probe_enabled(True)
    baseline.set_attribution_enabled(True)
    baseline.reset_telemetry()

def safe(x):
    if isinstance(x, dict):
        return {str(k): safe(v) for k,v in x.items()}
    if isinstance(x, (list,tuple)):
        return [safe(v) for v in x]
    if isinstance(x, (str,int,float,bool)) or x is None:
        return x
    return repr(x)

def marketish(d):
    if not isinstance(d, dict):
        return safe(d)
    keep = {}
    for k,v in d.items():
        lk = str(k).lower()
        if any(tok in lk for tok in ("market","price","sell","buy","product","animal","seed")):
            keep[k] = safe(v)
    return keep

def play(agent_fn, seed, seat, reset=None):
    configure()
    if reset:
        reset()
    snaps=[]
    turn=[0]
    env = make("kaggriculture", configuration={"seed":seed}, debug=False)

    def observed(obs):
        t=turn[0]
        if t in FOCUS_TURNS:
            snaps.append({
                "turn":t,
                "obs_keys": list(obs.keys()) if isinstance(obs,dict) else [],
                "public_keys": list((obs.get("public",{}) or {}).keys()) if isinstance(obs,dict) else [],
                "private_keys": list((obs.get("private",{}) or {}).keys()) if isinstance(obs,dict) else [],
                "public_marketish": marketish((obs.get("public",{}) or {}) if isinstance(obs,dict) else {}),
                "private_marketish": marketish((obs.get("private",{}) or {}) if isinstance(obs,dict) else {}),
                "public_full": safe((obs.get("public",{}) or {}) if isinstance(obs,dict) else {}),
            })
        action=agent_fn(obs)
        turn[0]+=1
        return action

    players=[OPPONENT,OPPONENT]
    players[seat]=observed
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return {"score":{"self":rewards[seat],"opp":rewards[1-seat],"margin":rewards[seat]-rewards[1-seat]},"snapshots":snaps}

def main():
    cases=[]
    for seed,seat in FRESH10:
        b=play(baseline.agent,seed,seat)
        c=play(candidate.agent,seed,seat,candidate.reset_experiment)
        self_diff=c["score"]["self"]-b["score"]["self"]
        cls="improved" if self_diff>0 else ("worsened" if self_diff<0 else "equal")
        cases.append({
            "seed":seed,"seat":seat,"class":cls,"accident3":seed in (4404,4407,4409),
            "self_diff":self_diff,
            "baseline":b["snapshots"],
            "candidate":c["snapshots"],
        })
    out={
        "schema":"kaggriculture.milk6-market-state-discovery.v0",
        "source":{"historical_commit":"27cac110515eca257c157904984add017d5ea8bb","historical_run":35422159593},
        "focus_turns":[197,198],
        "principle":{"observer_only":True,"field_discovery_only":True,"causal_claim":False},
        "cases":cases,
        "promote":False,
    }
    Path("cow_milk6_market_state_discovery_v0.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"cases":len(cases),"focus_turns":[197,198]},ensure_ascii=False))

if __name__=="__main__":
    main()
