#!/usr/bin/env python3
"""Observe turn72 Whole State -> Action72 -> transition -> turn73 Whole State.
No terminal/margin labels; observer-only. No derived distance metric.
"""
import importlib.util, json, copy
from pathlib import Path
from collections import Counter
from kaggle_environments import make
import strong_origin_g5_roi as baseline_agent
import full_strong_origin_v1 as candidate_agent

OPPONENT_PATH='opponents/seyamalam_v21.py'
CASES=((3564,0),(3565,1),(3566,0),(3567,1),(3568,0))
WINDOW={72,73}

def load_opp(tag):
    spec=importlib.util.spec_from_file_location(f'opp_{tag}',OPPONENT_PATH)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod.agent

def plants(farm):
    out=Counter(); active=0
    for row in farm.get('tiles',[]):
        for tile in row:
            if isinstance(tile,dict) and tile.get('kind')=='PLANT':
                active+=1; out[tile.get('crop','UNKNOWN')]+=1
    return active,dict(out)

def public_farm(farm):
    active,crops=plants(farm)
    animals=farm.get('animals',{})
    if isinstance(animals,dict):
        animals={str(k):len(v) if isinstance(v,list) else v for k,v in animals.items()}
    else: animals={}
    return {'money':float(farm.get('money',0)),'hands':len(farm.get('hands',[])),'land':len(farm.get('unlocked_quadrants',[])),'active_plants':active,'crops':crops,'animals':animals}

def world(obs):
    m=obs.get('market',{}) if isinstance(obs.get('market',{}),dict) else {}
    t=obs.get('town',{}) if isinstance(obs.get('town',{}),dict) else {}
    return {
        'inventory':copy.deepcopy(m.get('inventory',{})),
        'prices':copy.deepcopy(m.get('prices',{})),
        'shops':copy.deepcopy(t.get('unlocked_shops',[])),
        'day':obs.get('day')
    }

def snap(obs):
    p=obs['player']
    return {'self':public_farm(obs['farms'][p]),'opponent':public_farm(obs['farms'][1-p]),'world':world(obs)}

def play(seed,seat,module,tag):
    module.reset_telemetry(); opp=load_opp(tag); trace={}; opp_trace={}
    env=make('kaggriculture',configuration={'seed':seed},debug=False)
    self_turn=0; opp_turn=0
    def sw(obs):
        nonlocal self_turn
        a=module.agent(obs)
        if self_turn in WINDOW:
            trace[self_turn]={'state':snap(obs),'action':copy.deepcopy(a)}
        self_turn+=1; return a
    def ow(obs):
        nonlocal opp_turn
        a=opp(obs)
        if opp_turn in WINDOW:
            opp_trace[opp_turn]={'action':copy.deepcopy(a)}
        opp_turn+=1; return a
    players=[ow,ow]; players[seat]=sw; players[1-seat]=ow
    env.run(players)
    return trace,opp_trace

def num_delta(a,b):
    out={}
    for k in sorted(set(a)|set(b)):
        av,bv=a.get(k),b.get(k)
        if isinstance(av,(int,float)) and isinstance(bv,(int,float)):
            d=bv-av
            if d: out[k]=d
    return out

def dict_delta(a,b):
    out={}
    for k in sorted(set(a)|set(b)):
        av,bv=a.get(k,0),b.get(k,0)
        if isinstance(av,(int,float)) and isinstance(bv,(int,float)):
            d=bv-av
            if d: out[k]=d
    return out

def state_delta(base,cand):
    return {
        'self_scalar':num_delta({k:v for k,v in base['self'].items() if k not in ('crops','animals')},{k:v for k,v in cand['self'].items() if k not in ('crops','animals')}),
        'self_crops':dict_delta(base['self']['crops'],cand['self']['crops']),
        'self_animals':dict_delta(base['self']['animals'],cand['self']['animals']),
        'opp_scalar':num_delta({k:v for k,v in base['opponent'].items() if k not in ('crops','animals')},{k:v for k,v in cand['opponent'].items() if k not in ('crops','animals')}),
        'opp_crops':dict_delta(base['opponent']['crops'],cand['opponent']['crops']),
        'opp_animals':dict_delta(base['opponent']['animals'],cand['opponent']['animals']),
        'inventory':dict_delta(base['world']['inventory'],cand['world']['inventory']),
        'prices':dict_delta(base['world']['prices'],cand['world']['prices']),
        'shops_equal':base['world']['shops']==cand['world']['shops']
    }

def transition_delta(s72,s73):
    return {
        'self_scalar':num_delta({k:v for k,v in s72['self'].items() if k not in ('crops','animals')},{k:v for k,v in s73['self'].items() if k not in ('crops','animals')}),
        'self_crops':dict_delta(s72['self']['crops'],s73['self']['crops']),
        'self_animals':dict_delta(s72['self']['animals'],s73['self']['animals']),
        'opp_scalar':num_delta({k:v for k,v in s72['opponent'].items() if k not in ('crops','animals')},{k:v for k,v in s73['opponent'].items() if k not in ('crops','animals')}),
        'opp_crops':dict_delta(s72['opponent']['crops'],s73['opponent']['crops']),
        'opp_animals':dict_delta(s72['opponent']['animals'],s73['opponent']['animals']),
        'inventory':dict_delta(s72['world']['inventory'],s73['world']['inventory']),
        'prices':dict_delta(s72['world']['prices'],s73['world']['prices']),
        'shops_changed':s72['world']['shops']!=s73['world']['shops']
    }

def main():
    rows=[]
    for seed,seat in CASES:
        bt,bo=play(seed,seat,baseline_agent,f'b{seed}')
        ct,co=play(seed,seat,candidate_agent,f'c{seed}')
        row={
            'seed':seed,'seat':seat,
            'turn72':{'candidate_minus_baseline':state_delta(bt[72]['state'],ct[72]['state'])},
            'action72':{
                'baseline_self':bt[72]['action'],'candidate_self':ct[72]['action'],'self_equal':bt[72]['action']==ct[72]['action'],
                'baseline_opponent':bo[72]['action'],'candidate_opponent':co[72]['action'],'opponent_equal':bo[72]['action']==co[72]['action']
            },
            'transition_72_73':{
                'baseline':transition_delta(bt[72]['state'],bt[73]['state']),
                'candidate':transition_delta(ct[72]['state'],ct[73]['state'])
            },
            'turn73':{'candidate_minus_baseline':state_delta(bt[73]['state'],ct[73]['state'])}
        }
        rows.append(row)
    result={'schema':'kaggriculture.full-v1-scatter-boundary.v1','observer_only':True,'agent_mutated':False,'terminal_read':False,'margin_read':False,'distance_metric_used':False,'cases':rows}
    Path('full_v1_scatter_boundary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('SCATTER_BOUNDARY '+json.dumps(rows,separators=(',',':')))

if __name__=='__main__': main()
