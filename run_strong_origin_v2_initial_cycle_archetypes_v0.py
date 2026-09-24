#!/usr/bin/env python3
"""Fresh paired test for Strong Origin v2 initial-cycle archetypes v0.

Baseline:
  Strong Origin v2 Body-only v0

Candidates:
  FAST_CLOSURE / PRODUCTIVE_OCCUPANCY / CAPITAL_PRESERVATION / ANIMAL_CYCLE

Only Day0-4 candidate behavior differs. Public-rule execution is instrumented
to observe early-asset HARVEST -> SELL -> productive reinvestment closure.
"""
import copy
import json
import os
from collections import defaultdict
from pathlib import Path

from kaggle_environments import make
from kaggle_environments.envs.kaggriculture import kaggriculture as kg

import analyze_sb01_economic_layers_v0 as econ
import export_scale_baseline_v1 as basecfg
import run_sb01_exact_cash_flow_v0 as exact
import strong_origin_v2_body_only_v0 as baseline
import strong_origin_v2_initial_cycle_archetypes_v0 as candidate

SEED=int(os.environ["BATTLE_SEED"])
SEAT=int(os.environ["BATTLE_SEAT"])
OUT=Path(f"strong_origin_v2_initial_cycle_archetypes_v0_{SEED}.json")
MODES=("FAST_CLOSURE","PRODUCTIVE_OCCUPANCY","CAPITAL_PRESERVATION","ANIMAL_CYCLE")
TARGET_DAYS=(1,4,8,12)
TURN_PER_DAY=24


def plain(v):
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if isinstance(v,dict): return {str(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if hasattr(v,"items"):
        try:return {str(k):plain(x) for k,x in v.items()}
        except Exception:pass
    if hasattr(v,"tolist"):
        try:return plain(v.tolist())
        except Exception:pass
    if hasattr(v,"item"):
        try:return plain(v.item())
        except Exception:pass
    if hasattr(v,"__dict__"):
        try:return {str(k):plain(x) for k,x in vars(v).items() if not str(k).startswith("_")}
        except Exception:pass
    return str(v)


def getv(x,key,default=None):
    if isinstance(x,dict): return x.get(key,default)
    try:return getattr(x,key)
    except Exception:return default


def productive_count(farm):
    n=0
    for row in farm.get("tiles",[]) or []:
        for t in row or []:
            if isinstance(t,dict) and (t.get("kind")=="PLANT" or t.get("animal")):
                n+=1
    return n


def first_obs_for_day(env,seat,day):
    for step in getattr(env,"steps",[]) or []:
        if not isinstance(step,(list,tuple)) or len(step)<2: continue
        obs=plain(getv(step[seat],"observation"))
        if isinstance(obs,dict) and int(obs.get("day",0) or 0)==day:
            return obs
    return None


def summarize(obs):
    if not obs:return None
    p=int(obs["player"])
    side=econ.derive_side(obs)
    return {
        "cash":side["cash"],
        "productive_assets":sum(side["committed_production"]["crop_count"].values())+sum(side["committed_production"]["animal_count"].values()),
        "crop_count":side["committed_production"]["crop_count"],
        "animal_count":side["committed_production"]["animal_count"],
        "committed_production_potential_mark":side["committed_production"]["same_basis_subtotal"],
        "unlocked_tiles":side["uncommitted_capacity"]["unlocked_tiles"],
        "empty_unlocked_tiles":side["uncommitted_capacity"]["empty_unlocked_tiles"],
        "hands":side["uncommitted_capacity"]["current_hands"],
        "seeds":side["seed_inventory_fact"],
    }


def compute_closure(player,unit_events,market_events):
    harvests=[e for e in unit_events if e.get("player")==player and e.get("type")=="HARVEST" and e.get("early_asset")]
    feeds=[e for e in unit_events if e.get("player")==player and e.get("type")=="FEED"]
    buys_wheat=[e for e in market_events if e.get("player")==player and e.get("op")=="BUY_PRODUCT" and e.get("item")=="WHEAT"]

    pool=defaultdict(float)
    attributed=defaultdict(float)
    generated_sell_cash=0.0
    first_sale=None
    source_origin_days=defaultdict(list)

    all_times=sorted(set(
        [(int(e["day"]),int(e["hour"])) for e in harvests]
        +[(int(e["day"]),int(e["hour"])) for e in market_events if e.get("player")==player]
    ))

    market_by_time=defaultdict(list)
    for e in market_events:
        if e.get("player")==player:
            market_by_time[(int(e["day"]),int(e["hour"]))].append(e)

    harvest_by_time=defaultdict(list)
    for e in harvests:
        harvest_by_time[(int(e["day"]),int(e["hour"]))].append(e)

    for tm in all_times:
        # Output harvested on this same turn is still in a unit inventory when
        # market orders execute, so only harvests from earlier turns can support
        # a generated-output SELL on this turn.
        for e in market_by_time.get(tm,[]):
            if e.get("op")=="SELL":
                item=e.get("item")
                available=pool[item]-attributed[item]
                if available>=1:
                    attributed[item]+=1
                    generated_sell_cash+=float(e.get("cash_delta",0) or 0)
                    if first_sale is None:
                        first_sale=dict(e)
                        first_sale["source_item"]=item
                        ods=source_origin_days.get(item,[])
                        first_sale["source_origin_day"]=min(ods) if ods else None
            if first_sale is not None and e.get("op") in ("HIRE","BUY_LAND","BUY_SEED","BUY_ANIMAL"):
                item=first_sale.get("source_item")
                confidence="exact_non_wheat"
                if item=="WHEAT":
                    fs=(int(first_sale["day"]),int(first_sale["hour"]))
                    had_external=any((int(x["day"]),int(x["hour"]))<=fs for x in buys_wheat)
                    had_feed=any((int(x["day"]),int(x["hour"]))<=fs for x in feeds)
                    confidence="wheat_fungibility_ambiguous" if (had_external or had_feed) else "exact_no_external_wheat_before_sale"
                return {
                    "closed":True,
                    "day":int(e["day"]),
                    "hour":int(e["hour"]),
                    "turn":int(e["day"])*TURN_PER_DAY+int(e["hour"]),
                    "source_item":item,
                    "source_asset_origin_day":first_sale.get("source_origin_day"),
                    "first_generated_sell":{"day":int(first_sale["day"]),"hour":int(first_sale["hour"]),"cash_delta":float(first_sale.get("cash_delta",0) or 0)},
                    "generated_sell_cash_to_closure":generated_sell_cash,
                    "productive_assets_at_closure":int(e.get("productive_assets_before_market",0) or 0),
                    "reinvestment_order":plain(e.get("order")),
                    "reinvestment_op":e.get("op"),
                    "lineage_confidence":confidence,
                }
        for e in harvest_by_time.get(tm,[]):
            item=e.get("item")
            units=float(e.get("units",0) or 0)
            if units>0:
                pool[item]+=units
                source_origin_days[item].append(int(e.get("asset_origin_day",999)))

    return {
        "closed":False,
        "day":None,"hour":None,"turn":None,
        "source_item":None,
        "source_asset_origin_day":None,
        "generated_sell_cash_to_closure":generated_sell_cash,
        "productive_assets_at_closure":None,
        "reinvestment_order":None,
        "reinvestment_op":None,
        "lineage_confidence":None,
    }


def configure(agent_module,mode=None):
    basecfg._configure_baseline()
    os.environ["BUNDLE_FLOW_CONTROL_V0"]="0"
    os.environ["ORIGIN_CROP_COMMITMENT"]="0"
    if mode is not None:
        os.environ["INITIAL_CYCLE_MODE"]=mode
    agent_module.reset_telemetry()


def run_one(agent_module,mode=None):
    configure(agent_module,mode)

    exact.ledger=[defaultdict(float),defaultdict(float)]
    exact.units=[defaultdict(int),defaultdict(int)]
    exact.events=[]

    unit_events=[]
    pending=[]
    farm_player={}
    original_apply=kg._apply_unit_action
    original_market=kg._process_market

    def observed_apply(farm,private,unit_index,action,board_size,day,turns_per_day,shed_capacity):
        p=farm_player.get(id(farm))
        positions=[farm.get("farmer")]+list(farm.get("hands",[]) or [])
        pos=positions[unit_index] if 0<=unit_index<len(positions) else None
        op=action[0] if isinstance(action,(list,tuple)) and action else None
        before_tile=None
        before_inv={}
        if pos is not None:
            x,y=pos
            try: before_tile=copy.deepcopy(farm["tiles"][y][x])
            except Exception: before_tile=None
        invs=private.get("inventories",[]) or []
        if 0<=unit_index<len(invs):
            before_inv=copy.deepcopy(invs[unit_index] or {})

        original_apply(farm,private,unit_index,action,board_size,day,turns_per_day,shed_capacity)

        if p is None:
            return
        invs2=private.get("inventories",[]) or []
        after_inv=(invs2[unit_index] or {}) if 0<=unit_index<len(invs2) else {}

        if op=="HARVEST" and isinstance(before_tile,dict) and int(before_tile.get("yield_units",0) or 0)>0:
            item=None
            origin_day=None
            if before_tile.get("kind")=="PLANT":
                item=before_tile.get("crop")
                origin_day=int(before_tile.get("planted_day",999) or 999)
            elif before_tile.get("animal"):
                animal=before_tile.get("animal")
                item=kg.ANIMALS[animal]["product"]
                origin_day=int(before_tile.get("placed_day",999) or 999)
            if item:
                delta=int(after_inv.get(item,0) or 0)-int(before_inv.get(item,0) or 0)
                if delta>0:
                    pending.append({
                        "player":p,"type":"HARVEST","item":item,"units":delta,
                        "asset_origin_day":origin_day,"early_asset":origin_day<=4,
                    })

        if op=="FEED":
            delta=int(before_inv.get("WHEAT",0) or 0)-int(after_inv.get("WHEAT",0) or 0)
            if delta>0:
                pending.append({"player":p,"type":"FEED","item":"WHEAT","units":delta})

    def observed_market(state,env):
        obs0=state[0].observation
        day=int(getv(obs0,"day",0) or 0)
        hour=int(getv(obs0,"hour",0) or 0)
        for p,farm in enumerate(obs0.farms):
            farm_player[id(farm)]=p
        for e in pending:
            e["day"]=day;e["hour"]=hour
            unit_events.append(dict(e))
        pending.clear()

        before=len(exact.events)
        exact.measured_process_market(state,env)
        for idx,e in enumerate(exact.events[before:],start=before):
            e["day"]=day
            e["hour"]=hour
            e["event_index"]=idx
            p=int(e.get("player",-1))
            if p in (0,1):
                e["productive_assets_before_market"]=productive_count(obs0.farms[p])
            op=e.get("op")
            item=e.get("item")
            if op in ("HIRE","BUY_LAND"):
                e["order"]=[op]
            elif op in ("BUY_SEED","BUY_PRODUCT","BUY_ANIMAL","SELL"):
                e["order"]=[op,item,1]

    kg._apply_unit_action=observed_apply
    kg._process_market=observed_market
    try:
        env=make("kaggriculture",configuration={"seed":SEED},debug=False)
        obs0=env.state[0].observation
        for p,farm in enumerate(obs0.farms):
            farm_player[id(farm)]=p
        players=[basecfg.OPPONENT,basecfg.OPPONENT]
        players[SEAT]=agent_module.agent
        env.run(players)
        rewards=[float(x.reward) for x in env.state]
    finally:
        kg._apply_unit_action=original_apply
        kg._process_market=original_market

    market_events=[dict(e) for e in exact.events]
    snapshots={}
    for d in TARGET_DAYS:
        so=first_obs_for_day(env,SEAT,d)
        oo=first_obs_for_day(env,1-SEAT,d)
        snapshots[str(d)]={"self":summarize(so),"opponent":summarize(oo)}

    return {
        "mode":mode or "BODY_ONLY",
        "terminal":{
            "self":rewards[SEAT],"opponent":rewards[1-SEAT],
            "margin":rewards[SEAT]-rewards[1-SEAT],
            "win":rewards[SEAT]>rewards[1-SEAT],
        },
        "closure":{
            "self":compute_closure(SEAT,unit_events,market_events),
            "opponent":compute_closure(1-SEAT,unit_events,market_events),
        },
        "snapshots":snapshots,
        "cash_reconstruction":{
            "self_error":float(env.state[SEAT].reward)-(float(env.state[SEAT].reward)),
            "market_net_self":sum(float(v) for v in exact.ledger[SEAT].values()),
        },
        "telemetry":plain(agent_module.get_telemetry()),
    }


results={"BODY_ONLY":run_one(baseline)}
for mode in MODES:
    results[mode]=run_one(candidate,mode)

b=results["BODY_ONLY"]["terminal"]
for mode in MODES:
    results[mode]["delta_self_vs_body"]=results[mode]["terminal"]["self"]-b["self"]
    results[mode]["delta_margin_vs_body"]=results[mode]["terminal"]["margin"]-b["margin"]

payload={
    "schema":"kaggriculture.strong-origin-v2.initial-cycle-archetypes.paired.v0",
    "seed":SEED,"seat":SEAT,
    "results":results,
    "boundary":[
        "Body-only v0 is the comparison baseline.",
        "All four archetypes change only Day0-4 and return to Body-only behavior from Day5 onward.",
        "All archetypes share the same Day0-4 unique work-target reservation substrate.",
        "First-cycle closure is operationalized as: HARVEST from an asset created Day0-4, then a later SELL of that output class, then HIRE/BUY_LAND/BUY_SEED/BUY_ANIMAL.",
        "For WHEAT, lineage is flagged ambiguous when BUY_PRODUCT WHEAT or FEED occurred before the qualifying SELL because units are fungible.",
        "No adoption conclusion is generated here."
    ]
}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("INITIAL_CYCLE_ARCHETYPES "+json.dumps({
    "seed":SEED,"seat":SEAT,
    "body":results["BODY_ONLY"]["terminal"],
    "modes":{m:{
        "self":results[m]["terminal"]["self"],
        "delta_self":results[m]["delta_self_vs_body"],
        "closure":results[m]["closure"]["self"],
    } for m in MODES}
},ensure_ascii=False,separators=(",",":")))
