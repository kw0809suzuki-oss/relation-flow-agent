#!/usr/bin/env python3
"""Battle Value Map v0 — one fixed Battle from start to terminal.

Purpose:
Place self and Seyamalam on one world-time axis using public-rule-derived
absolute economic quantities. No cause, action diagnosis, representation,
evaluation, direction, or candidate is introduced.

Anchor case: seed/seat come from environment variables.

Observable Economic Mark (visualization only):
    Cash
  + liquidatable harvested inventory at current displayed prices
  + committed production current-price potential mark

This is not profit, wealth, objective, adoption score, or guaranteed future
cash. Its components remain separately exported.
"""
import json,os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import analyze_sb01_economic_layers_v0 as econ
import export_scale_baseline_v1 as basecfg
import run_sb01_exact_cash_flow_v0 as exact
import strong_origin_v2_body_only_v0 as body_only

SEED=int(os.environ.get("BATTLE_SEED","7351"))
SEAT=int(os.environ.get("BATTLE_SEAT","0"))
OUT=Path(f"battle_value_map_v0_{SEED}_seat{SEAT}.json")


def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)):return v
    if isinstance(v,dict):return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception:pass
    return str(v)


def getv(x,key,default=None):
    if isinstance(x,dict):return x.get(key,default)
    try:return getattr(x,key)
    except Exception:return default


def configure():
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    body_only.reset_telemetry()


def side_row(obs):
    s=econ.derive_side(obs)
    cash=float(s["cash"])
    inventory=float(s["liquidatable_inventory"]["display_price_mark"])
    committed=float(s["committed_production"]["same_basis_subtotal"])
    return {
        "cash":cash,
        "liquidatable_inventory_mark":inventory,
        "committed_production_mark":committed,
        "observable_economic_mark":cash+inventory+committed,
        "crop_production_mark":float(s["committed_production"]["crop_current_price_potential_mark"]),
        "animal_production_mark":float(s["committed_production"]["animal_base_current_price_potential_mark"]),
        "productive_assets":int(
            sum(s["committed_production"]["crop_count"].values())
            + sum(s["committed_production"]["animal_count"].values())
        ),
        "empty_unlocked_tiles":int(s["uncommitted_capacity"]["empty_unlocked_tiles"]),
    }


def main():
    configure()
    exact.ledger=[defaultdict(float),defaultdict(float)]
    exact.units=[defaultdict(int),defaultdict(int)]
    exact.events=[]

    event_clock=[]

    def measured_market(state,env):
        obs0=state[0].observation
        d=int(getv(obs0,"day",0) or 0)
        h=int(getv(obs0,"hour",0) or 0)
        before=len(exact.events)
        exact.measured_process_market(state,env)
        for e in exact.events[before:]:
            e["day"]=d;e["hour"]=h
            event_clock.append(e)

    env=make("kaggriculture",configuration={"seed":SEED},debug=False)
    original_market=kg._process_market
    kg._process_market=measured_market
    try:
        players=[basecfg.OPPONENT,basecfg.OPPONENT]
        players[SEAT]=body_only.agent
        env.run(players)
    finally:
        kg._process_market=original_market

    # cumulative market-flow facts keyed by state step reached after action.
    flow=[{
        "realized_sell":0.0,
        "operating_buy_product":0.0,
        "productive_spend":0.0,
    } for _ in (0,1)]
    events_by_next_step=defaultdict(list)
    for e in event_clock:
        d=int(e.get("day",0));h=int(e.get("hour",0))
        action_step=d*24+h
        events_by_next_step[action_step+1].append(e)

    timeline=[]
    for step_index,step in enumerate(getattr(env,"steps",[]) or []):
        if not isinstance(step,(list,tuple)) or len(step)<2:continue

        for e in events_by_next_step.get(step_index,[]):
            p=int(e.get("player",-1))
            if p not in (0,1):continue
            op=e.get("op")
            delta=float(e.get("cash_delta",0) or 0)
            if op=="SELL":
                flow[p]["realized_sell"]+=max(0.0,delta)
            elif op=="BUY_PRODUCT":
                flow[p]["operating_buy_product"]+=max(0.0,-delta)
            elif op in ("HIRE","BUY_LAND","BUY_SEED","BUY_ANIMAL"):
                flow[p]["productive_spend"]+=max(0.0,-delta)

        obs_self=plain(getv(step[SEAT],"observation"))
        obs_opp=plain(getv(step[1-SEAT],"observation"))
        if not isinstance(obs_self,dict) or not isinstance(obs_opp,dict):continue
        sr=side_row(obs_self);orow=side_row(obs_opp)
        sr.update(flow[SEAT]);orow.update(flow[1-SEAT])

        residual={k:orow[k]-sr[k] for k in (
            "cash","liquidatable_inventory_mark","committed_production_mark",
            "observable_economic_mark","crop_production_mark","animal_production_mark",
            "productive_assets","empty_unlocked_tiles",
            "realized_sell","operating_buy_product","productive_spend"
        )}

        timeline.append({
            "step":step_index,
            "day":int(obs_self.get("day",0) or 0),
            "hour":int(obs_self.get("hour",0) or 0),
            "self":sr,
            "opponent":orow,
            "residual_opponent_minus_self":residual,
        })

    rewards=[float(x.reward) for x in env.state]
    payload={
        "schema":"kaggriculture.strong-origin-v2.battle-value-map.v0",
        "seed":SEED,"seat":SEAT,
        "terminal":{
            "self":rewards[SEAT],
            "opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
        },
        "timeline":timeline,
        "map_definition":{
            "observable_economic_mark":"cash + liquidatable_inventory_mark + committed_production_mark",
            "cash":"World fact.",
            "liquidatable_inventory_mark":"Harvested SELL-able inventory quantity x current displayed price.",
            "committed_production_mark":"Existing productive assets' current-price potential mark under the existing WB-0001 assumptions.",
            "realized_sell":"Cumulative exact SELL cash from validated public market execution.",
            "operating_buy_product":"Cumulative exact BUY_PRODUCT cash outflow.",
            "productive_spend":"Cumulative exact HIRE + BUY_LAND + BUY_SEED + BUY_ANIMAL cash outflow."
        },
        "boundary":[
            "One fixed Battle only; no cross-seed averaging.",
            "Observable Economic Mark is a visualization mark, not realized profit, wealth, objective, or adoption score.",
            "Uncommitted capacity, seeds, unplaced animals, future price change, future operating cost, and action cost are not monetized into the mark.",
            "Committed Production remains a valuation with explicit assumptions; Cash remains Fact.",
            "No cause, Action diagnosis, Representation, Evaluation, Direction, Candidate, or policy mutation is introduced."
        ],
        "rule_provenance":econ.RULE_PROVENANCE,
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    # compact landmarks every day at hour0 plus terminal
    landmarks=[]
    seen=set()
    for r in timeline:
        if r["hour"]==0 and r["day"] not in seen:
            seen.add(r["day"]);landmarks.append(r)
    if timeline and landmarks[-1]["step"]!=timeline[-1]["step"]:
        landmarks.append(timeline[-1])

    print("BATTLE_VALUE_MAP "+json.dumps({
        "seed":SEED,"seat":SEAT,"terminal":payload["terminal"],
        "landmarks":[{
            "day":r["day"],"hour":r["hour"],
            "self_mark":r["self"]["observable_economic_mark"],
            "opponent_mark":r["opponent"]["observable_economic_mark"],
            "residual":r["residual_opponent_minus_self"]["observable_economic_mark"],
            "self_cash":r["self"]["cash"],
            "opponent_cash":r["opponent"]["cash"],
            "self_committed":r["self"]["committed_production_mark"],
            "opponent_committed":r["opponent"]["committed_production_mark"],
        } for r in landmarks]
    },ensure_ascii=False,separators=(",",":")))


if __name__=="__main__":
    main()
