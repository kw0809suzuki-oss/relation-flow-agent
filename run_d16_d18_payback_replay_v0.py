#!/usr/bin/env python3
"""D16/D18 payback replay observer v0.

Observation-only replay over the already-used fresh5.
Question:
Does the recovery state of D18-only additional expansion separate the sign of
terminal D18-vs-D16 self money?

No new strategy. No new model selection. No future value beyond terminal.
"""
import copy
import json
import os
from pathlib import Path

from kaggle_environments import make
import export_scale_baseline_v1 as base
import closure_switch_sweep_v0 as switcher

OPPONENT = base.OPPONENT
CASES = [(5201+i, i%2) for i in range(5)]
OUT = Path("d16_d18_payback_replay_v0.json")

OUTPUT_ITEMS = ("MILK","WOOL","EGG","FERTILIZER")
INV_ITEMS = ("WHEAT","MELON","POTATO","MILK","WOOL","EGG","FERTILIZER","COW")

def configure(day):
    os.environ["ORIGIN_GATE_POLARITY"] = "inverted"
    os.environ["ORIGIN_GATE_MAGNITUDE"] = "0.04"
    os.environ["G15_CONNECT_OPPONENT_FIELD_DESCRIPTION"] = "1"
    os.environ["G15_ADAPTIVE_W_AMPLITUDE"] = "1"
    os.environ["G15_REMOVE_R_RELATION"] = "0"
    os.environ["G15_REMOVE_E_RELATION"] = "0"
    os.environ["G15_REMOVE_W_RELATION"] = "0"
    os.environ["G15_DISABLE_RESONANCE_CONTROL"] = "0"
    os.environ["ORIGIN_CROP_COMMITMENT"] = "1"
    os.environ["BUNDLE_FLOW_CONTROL_V0"] = "1"
    switcher.set_probe_enabled(True)
    switcher.set_attribution_enabled(True)
    switcher.reset_experiment()
    switcher.set_switch_day(day)

def total_private(obs, item):
    p = obs.get("private", {}) or {}
    shed = p.get("shed", {}) or {}
    invs = p.get("inventories", []) or []
    return float(shed.get(item,0) or 0) + sum(float((x or {}).get(item,0) or 0) for x in invs)

def snap(obs):
    me = obs["farms"][obs["player"]]
    tiles = 0
    cows_on_tiles = 0
    for row in me.get("tiles", []) or []:
        for tile in row:
            if tile in (None, "LOCKED"):
                continue
            tiles += 1
            if isinstance(tile, dict) and tile.get("animal") == "COW":
                cows_on_tiles += 1
    inv = {k: total_private(obs,k) for k in INV_ITEMS}
    return {
        "day": int(obs.get("day",0) or 0),
        "money": float(me.get("money",0) or 0),
        "hands": len(me.get("hands",[]) or []),
        "active_tiles": tiles,
        "cows": inv.get("COW",0.0) + cows_on_tiles,
        "outputs": sum(inv.get(k,0.0) for k in OUTPUT_ITEMS),
        "inventory": inv,
    }

def play(seed, seat, switch_day):
    configure(switch_day)
    trace=[]
    actions=[]
    env=make("kaggriculture", configuration={"seed":seed}, debug=False)
    def observed(obs):
        before=snap(obs)
        action=switcher.agent(obs)
        trace.append(before)
        actions.append(copy.deepcopy(action))
        return action
    players=[OPPONENT,OPPONENT]
    players[seat]=observed
    env.run(players)
    rewards=[float(s.reward) for s in env.state]
    return {
        "switch_day":switch_day,
        "score":{"self":rewards[seat],"opp":rewards[1-seat],"margin":rewards[seat]-rewards[1-seat]},
        "trace":trace,
        "actions":actions,
        "activations":switcher.get_activations(),
    }

def first_action_difference(a,b):
    for i,(x,y) in enumerate(zip(a,b)):
        if x!=y:
            return i
    return None

def daily_last(trace):
    out={}
    for s in trace:
        out[s["day"]]=s
    return out

def positive_delta(a,b):
    return max(0.0, float(a)-float(b))

def classify(seed, d16, d18):
    first=first_action_difference(d16["actions"],d18["actions"])
    t16=daily_last(d16["trace"])
    t18=daily_last(d18["trace"])
    common_days=sorted(set(t16)&set(t18))

    # D18-only additional commitment is observed broadly:
    # extra productive state / inventory / lower cash after the first branch split.
    branch=[]
    max_commit_cash=0.0
    max_prod_gap=0.0
    max_output_gap=0.0
    for day in common_days:
        if day < 16:
            continue
        a=t16[day]; b=t18[day]
        cash_committed=positive_delta(a["money"], b["money"])
        prod_gap=(
            positive_delta(b["active_tiles"],a["active_tiles"]) +
            positive_delta(b["hands"],a["hands"]) +
            positive_delta(b["cows"],a["cows"])
        )
        output_gap=positive_delta(b["outputs"],a["outputs"])
        inv_gap=sum(positive_delta(b["inventory"].get(k,0),a["inventory"].get(k,0)) for k in INV_ITEMS)
        max_commit_cash=max(max_commit_cash,cash_committed)
        max_prod_gap=max(max_prod_gap,prod_gap)
        max_output_gap=max(max_output_gap,output_gap)
        branch.append({
            "day":day,
            "d18_minus_d16_money":b["money"]-a["money"],
            "d18_minus_d16_active_tiles":b["active_tiles"]-a["active_tiles"],
            "d18_minus_d16_hands":b["hands"]-a["hands"],
            "d18_minus_d16_cows":b["cows"]-a["cows"],
            "d18_minus_d16_outputs":b["outputs"]-a["outputs"],
            "positive_inventory_gap":inv_gap,
        })

    terminal_delta=d18["score"]["self"]-d16["score"]["self"]
    terminal_day=max(common_days) if common_days else None
    tail=(branch[-1] if branch else None)

    meaningful = (
        first is not None and
        (max_commit_cash > 0 or max_prod_gap > 0 or max_output_gap > 0)
    )

    # Operational classification is deliberately coarse.
    # "Recovered" requires positive terminal cash delta and no positive residual
    # output/inventory gap at the final observed daily snapshot.
    if not meaningful:
        cls="No meaningful extra expansion"
    else:
        residual=(tail["positive_inventory_gap"] + max(0.0, tail["d18_minus_d16_outputs"])) if tail else 0.0
        if terminal_delta > 0 and residual <= 0:
            cls="Recovered"
        elif terminal_delta > 0:
            cls="Partially recovered"
        else:
            cls="Unrecovered"

    return {
        "seed":seed,
        "first_action_difference":first,
        "terminal_d16":d16["score"]["self"],
        "terminal_d18":d18["score"]["self"],
        "terminal_d18_minus_d16":terminal_delta,
        "observed_sign":"D18>D16" if terminal_delta>0 else "D16>D18" if terminal_delta<0 else "equal",
        "max_observed_cash_commitment_gap":max_commit_cash,
        "max_productive_state_gap":max_prod_gap,
        "max_output_gap":max_output_gap,
        "terminal_observed_day":terminal_day,
        "classification":cls,
        "branch_daily_deltas":branch,
    }

def main():
    rows=[]
    for seed,seat in CASES:
        d16=play(seed,seat,16)
        d18=play(seed,seat,18)
        rows.append(classify(seed,d16,d18))

    separation={
        "d18_better":{r["seed"]:r["classification"] for r in rows if r["terminal_d18_minus_d16"]>0},
        "d16_better":{r["seed"]:r["classification"] for r in rows if r["terminal_d18_minus_d16"]<0},
    }
    result={
        "schema":"kaggriculture.d16-d18-payback-replay.v0",
        "question":"does D18-only additional-expansion recovery state separate the sign of D18 vs D16 terminal self money?",
        "observation_unit":"common path -> first expansion difference -> D18-only commitment branch -> productive-state delta -> output delta -> cash delta -> terminal",
        "classification_rules":{
            "Recovered":"meaningful D18-only expansion; positive terminal cash delta; no positive residual output/inventory gap at final observed daily snapshot",
            "Partially recovered":"meaningful D18-only expansion; positive terminal cash delta; residual output/inventory gap remains",
            "Unrecovered":"meaningful D18-only expansion; terminal cash delta is non-positive",
            "No meaningful extra expansion":"no meaningful additional commitment/productive/output branch observed after first action divergence",
        },
        "boundary":[
            "This is an operational external replay classification, not causal attribution of every cash unit.",
            "Future value beyond terminal is excluded.",
            "No model or strategy is adopted from this replay.",
            "If classes do not separate sign, Payback is not treated as a sufficient separator."
        ],
        "cases":rows,
        "separation":separation,
    }
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("D16_D18_PAYBACK_REPLAY "+json.dumps({
        "cases":[{"seed":r["seed"],"sign":r["observed_sign"],"class":r["classification"],"terminal_delta":r["terminal_d18_minus_d16"]} for r in rows],
        "separation":separation
    },ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    main()
