#!/usr/bin/env python3
"""Strong Origin v2 Body-only v0 external economy observer.

Observes only environment/public-rule quantities. Candidate policy is unchanged.
Reuses the already-validated exact Cash-flow market instrumentation from
run_sb01_exact_cash_flow_v0 and exports retained environment State.
"""
import json, os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import export_scale_baseline_v1 as basecfg
import strong_origin_v2_body_only_v0 as candidate
import run_sb01_exact_cash_flow_v0 as exact

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
TARGET_DAYS=(0,4,8,12,16,20,24,28)
OUT=Path(f"strong_origin_v2_external_economy_v0_{SEED}.json")


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    candidate.reset_telemetry()


def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)):
        return v
    if isinstance(v,dict):
        return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):
        return [plain(x) for x in v]
    if hasattr(v,"items"):
        try: return {str(k):plain(x) for k,x in v.items()}
        except Exception: pass
    if hasattr(v,"tolist"):
        try: return plain(v.tolist())
        except Exception: pass
    if hasattr(v,"item"):
        try: return plain(v.item())
        except Exception: pass
    if hasattr(v,"__dict__"):
        try: return {str(k):plain(x) for k,x in vars(v).items() if not str(k).startswith("_")}
        except Exception: pass
    return str(v)


def getv(x,key,default=None):
    if isinstance(x,dict):
        return x.get(key,default)
    try: return getattr(x,key)
    except Exception: return default


def export_states(env):
    out={"0":{},"1":{}}
    for step_index,step in enumerate(getattr(env,"steps",[]) or []):
        if not isinstance(step,(list,tuple)) or len(step)<2:
            continue
        for p in (0,1):
            obs=plain(getv(step[p],"observation"))
            if not isinstance(obs,dict):
                continue
            day=int(obs.get("day",0) or 0)
            k=str(day)
            if day in TARGET_DAYS and k not in out[str(p)]:
                out[str(p)][k]={"step_index":step_index,"observation":obs}
    return out


def measured_market_with_time(state,env):
    before=len(exact.events)
    exact.measured_process_market(state,env)
    obs0=state[0].observation
    day=int(getv(obs0,"day",0) or 0)
    hour=int(getv(obs0,"hour",0) or 0)
    for e in exact.events[before:]:
        e["day"]=day
        e["hour"]=hour


def main():
    configure()
    exact.ledger=[defaultdict(float),defaultdict(float)]
    exact.units=[defaultdict(int),defaultdict(int)]
    exact.events=[]

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    initial=[float(env.state[p].observation.farms[p].money) for p in (0,1)]

    original=kg._process_market
    kg._process_market=measured_market_with_time
    try:
        players=[basecfg.OPPONENT,basecfg.OPPONENT]
        players[SEAT]=candidate.agent
        env.run(players)
    finally:
        kg._process_market=original

    terminal=[float(x.reward) for x in env.state]
    snapshots=export_states(env)
    final_obs={str(p):plain(env.state[p].observation) for p in (0,1)}

    players_out=[]
    for p in (0,1):
        net=sum(exact.ledger[p].values())
        players_out.append({
            "player":p,
            "initial_cash":initial[p],
            "cash_flow_net":net,
            "reconstructed_terminal":initial[p]+net,
            "actual_terminal":terminal[p],
            "error":initial[p]+net-terminal[p],
            "ledger":dict(sorted(exact.ledger[p].items())),
            "executed_units":dict(sorted(exact.units[p].items())),
        })

    payload={
        "schema":"kaggriculture.strong-origin-v2.external-economy.v0",
        "seed":SEED,
        "seat":SEAT,
        "target_days":list(TARGET_DAYS),
        "terminal":{"self":terminal[SEAT],"opponent":terminal[1-SEAT],"margin":terminal[SEAT]-terminal[1-SEAT]},
        "state_export":snapshots,
        "final_observation":final_obs,
        "players":players_out,
        "events":exact.events,
        "candidate_telemetry":candidate.get_telemetry(),
        "boundary":[
            "Candidate policy is Strong Origin v2 Body-only v0 without Catalog/Flow repair.",
            "Only environment/public-rule quantities are observed.",
            "Market execution is instrumented with the already-validated logging-equivalent public-rule processor.",
            "Cash reconstruction must be exact for both players.",
            "No causal or adoption conclusion is generated in this runner."
        ]
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("STRONG_ORIGIN_V2_EXTERNAL_ECONOMY "+json.dumps({
        "seed":SEED,"seat":SEAT,"terminal":payload["terminal"],
        "self_error":players_out[SEAT]["error"],"opp_error":players_out[1-SEAT]["error"]
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
