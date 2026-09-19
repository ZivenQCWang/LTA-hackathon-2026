from __future__ import annotations
import csv
import io
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / 'data' / 'official'
FILES = ['01_LINES.csv','02_STATIONS.csv','03_SECTORS.csv','04_LOCATION_SUPPLY.csv',
         '05_BUFFER_LOCATION.csv','06_PARAMETERS.csv','07_PROJECT_DETAILS.csv','08_ACTIVITY_DETAILS.csv']

def csv_rows(text: str):
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError('CSV headers are missing or duplicated.')
    rows=[]
    for row in reader:
        if None in row: raise ValueError('CSV row has more fields than its header.')
        if any(value is None for value in row.values()): raise ValueError('CSV row has missing fields.')
        if any(row.values()): rows.append({k:(v or '').strip() for k,v in row.items() if k})
    return rows

def load_official():
    return {name: (OFFICIAL / '01_data' / name).read_text(encoding='utf-8-sig') for name in FILES}

def prepare(texts: dict):
    missing = set(FILES) - set(texts)
    if missing: raise ValueError('Missing files: ' + ', '.join(sorted(missing)))
    tables = {name: csv_rows(texts[name]) for name in FILES}
    params = {r['key']: r['value'] for r in tables[FILES[5]]}
    start = date.fromisoformat(params['horizon_start'])
    horizon = int(params['horizon_weeks'])
    if not 1 <= horizon <= 104: raise ValueError('Planning horizon must be 1–104 weeks.')
    projects = {r['contract_number']: dict(r) for r in tables[FILES[6]]}
    if len(projects) != len(tables[FILES[6]]): raise ValueError('Duplicate contract IDs.')
    for p in projects.values():
        for col in ['contract_priority','number_of_workfronts','number_of_maximum_access_per_week']:
            p[col] = int(p[col])
        if p['contract_priority'] not in [1,2,3] or not 1 <= p['number_of_workfronts'] <= 20 or not 1 <= p['number_of_maximum_access_per_week'] <= 7:
            raise ValueError('Invalid contract priority, workfront count, or weekly access cap.')
        if p['access_type'] not in ['PM','PC','C']: raise ValueError('Unknown possession type.')
        if p['nature_of_activity'] not in ['Live','Non-live (Consist)','Non-live (Others)']: raise ValueError('Unknown work nature.')
        p['deadline_week'] = (date.fromisoformat(p['planned_completion_date']) - start).days // 7 + 1
    stations = tables[FILES[1]]
    lines = {}
    for r in stations: lines.setdefault(r['line_code'], []).append(r)
    for line in lines: lines[line].sort(key=lambda r: int(r['seq']))
    positions = {}
    for line, stops in lines.items():
        for i, stop in enumerate(stops):
            for bound in ['EB','WB']: positions[f'PLAT:{line}:{stop["station_id"]}:{bound}'] = (line, bound, 2*i)
    for sector in tables[FILES[2]]:
        seq = next((i for i,s in enumerate(lines[sector['line_code']]) if s['station_id'] == sector['from_station_id']), None)
        if seq is None: raise ValueError('Sector references an unknown station.')
        for bound in ['EB','WB']: positions[f'{sector["sector_id"]}:{bound}'] = (sector['line_code'],bound,2*seq+1)
    supply = {r['location_id']: int(r['supply_capacity']) for r in tables[FILES[3]]}
    if len(supply)!=len(tables[FILES[3]]): raise ValueError('Duplicate supply location IDs.')
    if any(v < 0 or v > 7 for v in supply.values()): raise ValueError('Supply must be 0–7 nights per week.')
    if set(supply) != set(positions): raise ValueError('Location supply must include every platform and sector, on both bounds.')
    buffers = {r['nature_of_works']: int(r['up_to_buffer_sectors']) for r in tables[FILES[4]]}
    mirror = {r['nature_of_works']: r['opposite_bound_required'] == '1' for r in tables[FILES[4]]}
    activities=[]
    for row in tables[FILES[7]]:
        a=dict(row)
        if a['contract_number'] not in projects: raise ValueError(f'{a["activity_id"]}: unknown contract.')
        p=projects[a['contract_number']]
        for col in ['total_accesses','activity_priority']: a[col]=int(a[col])
        if not 1 <= a['total_accesses'] <= 200 or a['activity_priority'] not in [1,2,3]: raise ValueError('Invalid workload or activity priority.')
        if a['start_location_id'] not in positions or a['end_location_id'] not in positions: raise ValueError('Activity references an unknown location.')
        line,bound,lo=positions[a['start_location_id']]; line2,bound2,hi=positions[a['end_location_id']]
        if (line,bound)!=(line2,bound2): raise ValueError('Activity endpoints must be on the same line and bound.')
        lo,hi=sorted([lo,hi]); lo-=lo%2; hi+=hi%2
        own={loc for loc,(ln,b,pos) in positions.items() if (ln,b)==(line,bound) and lo<=pos<=hi}
        # A consist buffer extends through the adjoining tunnel, stopping before
        # its far platform. Live isolation also includes that far platform.
        buffer_sectors=buffers[p['nature_of_activity']]
        buffer=2*buffer_sectors if p['nature_of_activity']=='Live' else max(0,2*buffer_sectors-1)
        footprint={loc for loc,(ln,b,pos) in positions.items() if (ln,b)==(line,bound) and lo-buffer<=pos<=hi+buffer}
        affected_lines={line}
        if mirror[p['nature_of_activity']]:
            footprint|={loc[:-2]+('WB' if loc.endswith('EB') else 'EB') for loc in list(footprint)}
        if p['nature_of_activity']=='Live' and any(':H01_H02:' in loc or ':H01:' in loc or ':H02:' in loc for loc in footprint):
            # Power isolation at the interchange carries the Live buffer onto
            # the other line too, on both bounds, not only the three hub sites.
            for ln in lines:
                hubs=[pos for loc,(line_code,b,pos) in positions.items()
                      if line_code==ln and b=='EB' and (':H01:' in loc or ':H02:' in loc)]
                if hubs:
                    footprint|={loc for loc,(line_code,_,pos) in positions.items()
                                if line_code==ln and min(hubs)-buffer<=pos<=max(hubs)+buffer}
                    affected_lines.add(ln)
        a.update(line=line,bound=bound,locations=sorted(own),footprint=sorted(footprint),
                 affected_lines=sorted(affected_lines),access_type=p['access_type'],nature=p['nature_of_activity'],
                 contract_priority=p['contract_priority'],start_week=max(1,(date.fromisoformat(a['planned_start_date'])-start).days//7+1))
        activities.append(a)
    ids={a['activity_id'] for a in activities}
    if len(ids)!=len(activities) or not activities: raise ValueError('Activities must have unique IDs and cannot be empty.')
    if len(activities)>200: raise ValueError('This hackathon build supports up to 200 activities per instance.')
    visited=set(); visiting=set(); byid={a['activity_id']:a for a in activities}
    def visit(aid):
        if aid in visiting: raise ValueError('Predecessor cycle detected.')
        if aid in visited: return
        visiting.add(aid); pred=byid[aid].get('predecessor_activity_id')
        if pred:
            if pred not in ids: raise ValueError('Unknown predecessor: '+pred)
            visit(pred)
        visiting.remove(aid); visited.add(aid)
    for aid in ids: visit(aid)
    return {'start':str(start),'horizon':horizon,'projects':projects,'activities':activities,
            'supply':supply,'lines':lines,'positions':positions,'texts':texts}

def conflict(a,b):
    """Conservative same-night collision test; shared possessions waive internal buffers."""
    own_a,own_b=set(a['locations']),set(b['locations'])
    overlap=own_a & own_b
    types={a['access_type'],b['access_type']}
    share=bool(overlap) and 'PM' not in types and not(a['access_type']==b['access_type']=='PC') and 'Live' not in (a['nature'],b['nature'])
    if share: return False
    return bool(set(a['footprint']) & set(b['footprint']))

def week_end(instance,week): return str(date.fromisoformat(instance['start'])+timedelta(days=week*7-1))

def csv_text(rows,columns):
    stream=io.StringIO(); writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore',lineterminator='\n')
    writer.writeheader(); writer.writerows(rows); return stream.getvalue()

def public_instance(instance):
    return {k:instance[k] for k in ['start','horizon','projects','activities','supply','lines']}

def provenance(): return json.loads((OFFICIAL/'provenance.json').read_text(encoding='utf-8'))
