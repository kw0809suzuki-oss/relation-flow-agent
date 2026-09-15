#!/usr/bin/env python3
"""Observe public State from turn 59 through 73 on fresh seeds.
No terminal/margin labels; observer-only. The purpose is descriptive only:
find the first public-state coordinates that differ before the WHEAT path splits at turn 73.
"""
import copy
import importlib.util
import json
from collections import Counter
from pathlib import Path

from kaggle_environments import make

import strong_origin_g5_roi as baseline_agent
import full_strong_origin_v1 as candidate_agent

OPPONENT_PATH = 'opponents/seyamalam_v21.py'
CASES = ((3564,0),(3565,1),(3566,0),(3567,1),(3568,0))
WINDOW = range(59,74)


def load_opp(tag):
    spec = importlib.util.spec_from_file_location(f'opp_{tag}', OPPONENT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.agent


def plants(farm):
    out = Counter(); active = 0
    for row in farm.get('tiles', []):
        for tile in row:
            if isinstance(tile, dict) and tile.get('kind') == 'PLANT':
                active += 1
                out[tile.get('crop', 'UNKNOWN')] += 1
    return active, dict(out)


def public_farm(farm):
    active, crops = plants(farm)
    animals = farm.get('animals', {})
    if isinstance(animals, dict):
        animal_counts = {str(k): len(v) if isinstance(v, list) else v for k,v in animals.items()}
    else:
        animal_counts = {}
    return {
        'money': float(farm.get('money', 0)),
        'hands': len(farm.get('hands', [])),
        'land': len(farm.get('unlocked_quadrants', [])),
        'active_plants': active,
        'crops': crops,
        'animals': animal_counts,
    }


def world(obs):
    market = obs.get('market', {})
    town = obs.get('town', {})
    return {
        'day': obs.get('day'),
        'inventory': copy.deepcopy(market.get('inventory', {})),
        'prices': copy.deepcopy(market.get('prices', {})),
        'shops': list(town.get('unlocked_shops', [])) if isinstance(town, dict) else [],
    }


def play(seed, seat, self_module, tag):
    self_module.reset_telemetry()
    trace = []
    opp = load_opp(tag)
    env = make('kaggriculture', configuration={'seed': seed}, debug=False)

    def sw(obs):
        turn = len(trace)
        action = self_module.agent(obs)
        if turn in WINDOW:
            trace.append({
                'turn': turn,
                'self': public_farm(obs['farms'][obs['player']]),
                'opponent': public_farm(obs['farms'][1-obs['player']]),
                'world': world(obs),
                'action': copy.deepcopy(action),
            })
        else:
            trace.append({'turn': turn})
        return action

    def ow(obs):
        return opp(obs)

    players = [ow, ow]
    players[seat] = sw
    players[1-seat] = ow
    env.run(players)
    return {x['turn']: x for x in trace if x['turn'] in WINDOW}


def num_delta(a,b):
    out={}
    for k in sorted(set(a)|set(b)):
        av,bv=a.get(k),b.get(k)
        if isinstance(av,(int,float)) and isinstance(bv,(int,float)):
            d=bv-av
            if d!=0: out[k]=d
    return out


def dict_delta(a,b):
    out={}
    for k in sorted(set(a)|set(b)):
        av,bv=a.get(k,0),b.get(k,0)
        if isinstance(av,(int,float)) and isinstance(bv,(int,float)) and av!=bv:
            out[k]=bv-av
    return out


def state_delta(base,cand):
    return {
        'self_scalar': num_delta({k:v for k,v in base['self'].items() if isinstance(v,(int,float))}, {k:v for k,v in cand['self'].items() if isinstance(v,(int,float))}),
        'self_crops': dict_delta(base['self']['crops'], cand['self']['crops']),
        'self_animals': dict_delta(base['self']['animals'], cand['self']['animals']),
        'opp_scalar': num_delta({k:v for k,v in base['opponent'].items() if isinstance(v,(int,float))}, {k:v for k,v in cand['opponent'].items() if isinstance(v,(int,float))}),
        'opp_crops': dict_delta(base['opponent']['crops'], cand['opponent']['crops']),
        'opp_animals': dict_delta(base['opponent']['animals'], cand['opponent']['animals']),
        'inventory': num_delta(base['world']['inventory'], cand['world']['inventory']),
        'prices': num_delta(base['world']['prices'], cand['world']['prices']),
        'shops_equal': base['world']['shops']==cand['world']['shops'],
    }


def signature(d):
    # compact, descriptive signature used only to compare observed public deltas
    return json.dumps(d, sort_keys=True, separators=(',',':'))


def main():
    cases=[]
    for seed,seat in CASES:
        b=play(seed,seat,baseline_agent,f'b{seed}')
        c=play(seed,seat,candidate_agent,f'c{seed}')
        rows=[]
        for t in WINDOW:
            d=state_delta(b[t],c[t])
            rows.append({'turn':t,'delta':d,'signature':signature(d)})
        cases.append({'seed':seed,'seat':seat,'turns':rows})

    # Cross-seed observation: at each turn, report how many distinct public delta signatures exist.
    cross=[]
    for t in WINDOW:
        sigs={}
        for case in cases:
            row=next(x for x in case['turns'] if x['turn']==t)
            sigs.setdefault(row['signature'],[]).append(case['seed'])
        cross.append({'turn':t,'distinct_signatures':len(sigs),'groups':list(sigs.values())})

    result={
        'schema':'kaggriculture.full-v1-prebranch-state.v1',
        'observer_only':True,
        'agent_mutated':False,
        'terminal_read':False,
        'margin_read':False,
        'window':[59,73],
        'cases':cases,
        'cross_seed':cross,
    }
    Path('full_v1_prebranch_state.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('PREBRANCH_CROSS '+json.dumps(cross,separators=(',',':')))
    for case in cases:
        compact=[]
        prev=None
        for row in case['turns']:
            if row['signature']!=prev:
                compact.append({'turn':row['turn'],'delta':row['delta']})
            prev=row['signature']
        print('PREBRANCH_SEED',case['seed'],json.dumps(compact,separators=(',',':')))

if __name__=='__main__':
    main()
