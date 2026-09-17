#!/usr/bin/env python3
"""Observe exact Strong Origin BUY_LAND gate state without mutating policy.

Focus: Land 2 -> 3. Record which existing gate is false at each daily state.
This is descriptive observation only.
"""
import json, os
from pathlib import Path
from kaggle_environments import make
import whole_flow_control_agent as v6
from x_engine import XField, choose_x_origin
import strong_origin

OPPONENT="opponents/seyamalam_v21.py"
CASES=((3202,0),(3206,0),(3215,1),(3218,0),(3222,0),(3227,1),(3231,1),(3240,0),(3243,1),(3246,0),(3250,0),(3251,1))
BASE_PRICE=strong_origin.BASE_PRICE
STRATEGIES=strong_origin.STRATEGIES

def configure():
    os.environ.update({"ORIGIN_GATE_POLARITY":"inverted","ORIGIN_GATE_MAGNITUDE":"0.04","G15_CONNECT_OPPONENT_FIELD_DESCRIPTION":"1","G15_ADAPTIVE_W_AMPLITUDE":"1","G15_REMOVE_R_RELATION":"0","G15_REMOVE_E_RELATION":"0","G15_REMOVE_W_RELATION":"0","G15_DISABLE_RESONANCE_CONTROL":"0","ORIGIN_CROP_COMMITMENT":"1"})
    v6.set_control_enabled(False); v6.set_probe_enabled(True); v6.set_attribution_enabled(True); v6.reset_telemetry()

def snap(obs):
    p=obs['player']; me=obs['farms'][p]; opp=obs['farms'][1-p]; day=int(obs['day']); remaining=30-day
    my_plants={c:0 for c in BASE_PRICE}; opp_plants={c:0 for c in BASE_PRICE}; unlocked=empty=occupied=0
    for row in me.get('tiles',[]):
        for t in row:
            if t=='LOCKED': continue
            unlocked+=1
            if t is None: empty+=1
            elif isinstance(t,dict) and t.get('kind')=='PLANT' and t.get('crop') in my_plants: my_plants[t['crop']]+=1
    occupied=unlocked-empty; occupancy=occupied/unlocked if unlocked else 1.0
    for row in opp.get('tiles',[]):
        for t in row:
            if isinstance(t,dict) and t.get('kind')=='PLANT' and t.get('crop') in opp_plants: opp_plants[t['crop']]+=1
    prices=obs.get('market',{}).get('prices',{}) or {}
    f=XField(day=day,remaining_days=remaining,my_money=me.get('money',0),opp_money=opp.get('money',0),my_land=len(me.get('unlocked_quadrants',[])),opp_land=len(opp.get('unlocked_quadrants',[])),my_hands=len(me.get('hands',[])),opp_hands=len(opp.get('hands',[])),prices=prices,my_supply=my_plants,opp_supply=opp_plants)
    origin=choose_x_origin(f,BASE_PRICE).origin; strategy=STRATEGIES[origin]
    land=len(me.get('unlocked_quadrants',[])); cost={1:1000,2:2000,3:4000}.get(land)
    reserve=strategy['reserve_base']+20*occupied
    gates={
      'land_cost_exists': cost is not None,
      'strategy_allows': origin not in ('LIQUID','ENDGAME'),
      'remaining_allows': remaining>=9,
      'occupancy_allows': occupancy>=strategy['occupancy_target'],
      'cash_allows': bool(cost is not None and me.get('money',0)-cost>=reserve),
    }
    return {'day':day,'money':float(me.get('money',0)),'land':land,'remaining':remaining,'origin':origin,'occupancy':occupancy,'occupancy_target':strategy['occupancy_target'],'occupied':occupied,'capacity':unlocked,'land_cost':cost,'reserve':reserve,'gates':gates}

def play(seed,seat):
    configure(); env=make('kaggriculture',configuration={'seed':seed},debug=False); rows=[]; last=None
    def observed(obs):
        nonlocal last
        s=snap(obs)
        if s['day']!=last: rows.append(s); last=s['day']
        else: rows[-1]=s
        return v6.agent(obs)
    ps=[OPPONENT,OPPONENT]; ps[seat]=observed; env.run(ps)
    rewards=[x.reward for x in env.state]
    return {'seed':seed,'seat':seat,'terminal_self':float(rewards[seat]),'rows':rows}

def main():
    cases=[play(*c) for c in CASES]
    land2=[r for c in cases for r in c['rows'] if r['land']==2]
    blocked=[r for r in land2 if not all(r['gates'].values())]
    counts={k:sum(not r['gates'][k] for r in blocked) for k in ('strategy_allows','remaining_allows','occupancy_allows','cash_allows')}
    early=[r for r in blocked if r['remaining']>=9]
    early_counts={k:sum(not r['gates'][k] for r in early) for k in ('strategy_allows','occupancy_allows','cash_allows')}
    out={'policy_mutated':False,'focus':'Land 2 -> 3 existing BUY_LAND gate','cases':cases,'summary':{'land2_daily_states':len(land2),'blocked_states':len(blocked),'blocked_gate_false_counts':counts,'remaining_ge_9_blocked_states':len(early),'remaining_ge_9_gate_false_counts':early_counts}}
    Path('land_gate_observer_v1.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print('LAND_GATE_OBSERVER_V1 '+json.dumps(out['summary'],separators=(',',':')))
if __name__=='__main__': main()
