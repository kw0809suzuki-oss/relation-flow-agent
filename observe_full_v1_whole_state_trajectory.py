#!/usr/bin/env python3
"""Observe whole-state trajectories for Full v1 vs baseline on fresh seeds.
Observer-only. No terminal or margin reads.
"""
import importlib.util, json
from pathlib import Path
from collections import Counter
from kaggle_environments import make
import strong_origin_g5_roi as baseline_agent
import full_strong_origin_v1 as candidate_agent

OPPONENT_PATH='opponents/seyamalam_v21.py'
CASES=((3564,0),(3565,1),(3566,0),(3567,1),(3568,0))
WINDOW=range(59,74)

def load_opp(tag):
    spec=importlib.util.spec_from_file_location(f'opp_{tag}',OPPONENT_PATH)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod.agent

def crops(farm):
    c=Counter(); active=0
    for row in farm.get('tiles',[]):
        for tile in row:
            if isinstance(tile,dict) and tile.get('kind')=='PLANT':
                active+=1; c[str(tile.get('crop','UNKNOWN'))]+=1
    return active,dict(sorted(c.items()))

def public_farm(farm):
    active,c=crops(farm)
    animals=farm.get('animals',{})
    if isinstance(animals,dict):
        animals={str(k):(len(v) if isinstance(v,list) else v) for k,v in animals.items()}
    else: animals={}
    return {
        'money':farm.get('money',0),
        'hands':len(farm.get('hands',[])),
        'land':len(farm.get('unlocked_quadrants',[])),
        'active_plants':active,
        'crops':c,
        'animals':dict(sorted(animals.items())),
    }

def world(obs):
    m=obs.get('market',{}); town=obs.get('town',{})
    return {
        'self':public_farm(obs['farms'][obs['player']]),
        'opponent':public_farm(obs['farms'][1-obs['player']]),
        'market_inventory':dict(sorted((m.get('inventory',{}) or {}).items())),
        'market_prices':dict(sorted((m.get('prices',{}) or {}).items())),
        'shops':list(town.get('unlocked_shops',[]) or []),
    }

def play(seed,seat,module,tag):
    module.reset_telemetry(); trace={}; opp=load_opp(tag)
    env=make('kaggriculture',configuration={'seed':seed},debug=False)
    def sw(obs):
        t=len(sw.calls); sw.calls.append(t)
        if t in WINDOW: trace[t]=world(obs)
        return module.agent(obs)
    sw.calls=[]
    def ow(obs): return opp(obs)
    players=[ow,ow]; players[seat]=sw; env.run(players)
    return trace

def numeric_delta(a,b):
    keys=set(a)|set(b); out={}
    for k in keys:
        av=a.get(k,0); bv=b.get(k,0)
        if isinstance(av,(int,float)) and isinstance(bv,(int,float)) and av!=bv:
            out[k]=bv-av
    return dict(sorted(out.items()))

def state_delta(base,cand):
    out={
        'self_scalar':numeric_delta({k:v for k,v in base['self'].items() if k not in ('crops','animals')},{k:v for k,v in cand['self'].items() if k not in ('crops','animals')}),
        'self_crops':numeric_delta(base['self']['crops'],cand['self']['crops']),
        'self_animals':numeric_delta(base['self']['animals'],cand['self']['animals']),
        'opp_scalar':numeric_delta({k:v for k,v in base['opponent'].items() if k not in ('crops','animals')},{k:v for k,v in cand['opponent'].items() if k not in ('crops','animals')}),
        'opp_crops':numeric_delta(base['opponent']['crops'],cand['opponent']['crops']),
        'opp_animals':numeric_delta(base['opponent']['animals'],cand['opponent']['animals']),
        'inventory':numeric_delta(base['market_inventory'],cand['market_inventory']),
        'prices':numeric_delta(base['market_prices'],cand['market_prices']),
        'shops_equal':base['shops']==cand['shops'],
    }
    return out

def signature(d): return json.dumps(d,sort_keys=True,separators=(',',':'))

def main():
    rows=[]
    for seed,seat in CASES:
        b=play(seed,seat,baseline_agent,f'b{seed}'); c=play(seed,seat,candidate_agent,f'c{seed}')
        traj=[]
        for t in WINDOW:
            d=state_delta(b[t],c[t])
            traj.append({'turn':t,'delta':d,'signature':signature(d)})
        rows.append({'seed':seed,'seat':seat,'trajectory':traj})
    cross=[]
    for t in WINDOW:
        groups={}
        for r in rows:
            sig=next(x['signature'] for x in r['trajectory'] if x['turn']==t)
            groups.setdefault(sig,[]).append(r['seed'])
        cross.append({'turn':t,'group_count':len(groups),'groups':list(groups.values())})
    result={'schema':'kaggriculture.full-v1-whole-state-trajectory.v1','observer_only':True,'agent_mutated':False,'terminal_read':False,'margin_read':False,'window':[59,73],'cases':rows,'cross_seed':cross}
    Path('full_v1_whole_state_trajectory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('WHOLE_STATE_GROUPS '+json.dumps(cross,separators=(',',':')))
    for r in rows:
        changes=[]; prev=None
        for x in r['trajectory']:
            if x['signature']!=prev:
                changes.append({'turn':x['turn'],'delta':x['delta']}); prev=x['signature']
        print('WHOLE_STATE_SEED',r['seed'],json.dumps(changes,separators=(',',':')))

if __name__=='__main__': main()
