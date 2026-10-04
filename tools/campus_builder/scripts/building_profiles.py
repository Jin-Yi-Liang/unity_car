"""Resolve per-building evidence; never promote an assumed storey height to fact."""
import copy
import hashlib
import json
import math


def load_profiles(root):
    data=json.loads((root/'config/building_profiles.json').read_text())
    sources={s['id']:s for s in data['sources']}
    for source in sources.values():
        path=root/source['path']
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Missing building evidence: {source['id']}")
        source['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    for profile in [data['default_profile'],*data['profiles'].values()]:
        if profile['roof_shape'] not in ['flat','gable','swept']:
            raise ValueError('Unsupported roof shape')
        if not profile['source_ids'] or any(s not in sources for s in profile['source_ids']):
            raise ValueError('Building profile has no auditable source')
        for photo in profile['photos']:
            path=root/'input/evidence/buildings'/photo
            if not path.is_file():raise ValueError(f'Missing facade reference {photo}')
    return data


def resolve(building,config,profiles):
    label=building['map_label']
    result=copy.deepcopy(profiles['profiles'].get(label,profiles['default_profile']))
    source_ids=building.get('source_trace_ids',[building['id']])
    for identifier in source_ids:
        override=profiles['features'].get(identifier,{})
        for key in ['floor_count','eave_height_m','roof_rise_m','measured_height_m','measurement_source','override_provenance']:
            if key in override:result[key]=override[key]
    default=config['low_building_height_m'] if building['height_class']=='low' else config['default_building_height_m']
    count=result['floor_count']
    if count is not None and (not isinstance(count,int) or count<=0):raise ValueError('Invalid floor count')
    if result.get('measured_height_m') is not None:
        if not result.get('measurement_source'):raise ValueError('Measured height requires measurement provenance')
        eave=float(result['measured_height_m'])-result['roof_rise_m']
        result['height_status']='measured height with source attribution'
    else:
        eave=result.get('eave_height_m',count*result['floor_height_m'] if count is not None else default)
    if not math.isfinite(eave) or eave<=0 or not 0<=result['roof_rise_m']<20:
        raise ValueError(f'Invalid building height: {label}')
    result.update(eave_height_m=eave,total_height_m=eave+result['roof_rise_m'],source_trace_ids=source_ids,
                  actual_height_measured=result.get('measured_height_m') is not None)
    return result


def generate_textures(root,profiles):
    """Small authored repeat tiles, plain BSDF image textures in both exports."""
    from PIL import Image,ImageDraw
    folder=root/'output/textures';folder.mkdir(parents=True,exist_ok=True)
    for key,p in [('default',profiles['default_profile']),*profiles['profiles'].items()]:
        rgb=lambda value:tuple(round(c*255) for c in value)
        wall=rgb(p['wall_rgb']);image=Image.new('RGB',(512,512),wall);draw=ImageDraw.Draw(image)
        if p['floor_count'] is not None:
            ratio=.9 if p['kind'] in ['exhibition','gym'] else p['window_width_ratio']
            height=.8 if p['kind'] in ['exhibition','gym'] else p['window_height_ratio']
            x0,x1=int((1-ratio)*256),int((1+ratio)*256)
            y0,y1=int((1-height)*256),int((1+height)*256)
            draw.rectangle((x0-6,y0-6,x1+6,y1+6),fill=(158,167,168))
            draw.rectangle((x0,y0,x1,y1),fill=rgb(p['glass_rgb']))
            draw.line((256,y0,256,y1),fill=(190,199,196),width=4)
            draw.line((x0,int(y0+(y1-y0)*.3),x1,int(y0+(y1-y0)*.3)),fill=(180,191,190),width=3)
            draw.line((0,505,511,505),fill=tuple(max(0,c-20) for c in wall),width=3)
        else:
            # Neutral cladding joints convey material without inventing floors.
            draw.line((0,0,511,0),fill=tuple(max(0,c-8) for c in wall),width=2)
            draw.line((0,0,0,511),fill=tuple(max(0,c-8) for c in wall),width=2)
        image.save(folder/f'facade_{key}.png')
        if p['kind']=='administration':
            # Full-height vertical tile: photo-informed glazed crown and white end wall.
            whole=Image.new('RGB',(512,1024),wall)
            count=p['floor_count'];tile=image.resize((512,round(1024/count)))
            for floor in range(count):whole.paste(tile,(0,round(floor*1024/count)))
            d=ImageDraw.Draw(whole);d.rectangle((0,0,511,130),fill=rgb(p['glass_rgb']))
            for y in [0,43,86,129]:d.line((0,y,511,y),fill=wall,width=6)
            for x in [0,256,511]:d.line((x,0,x,130),fill=wall,width=6)
            whole.save(folder/f'facade_{key}.png')
            end=Image.new('RGB',(512,1024),wall);d=ImageDraw.Draw(end)
            d.rectangle((55,145,100,970),fill=rgb(p['glass_rgb']))
            d.rectangle((430,145,460,970),fill=rgb(p['glass_rgb']))
            for y in range(145,970,65):d.line((50,y,465,y),fill=wall,width=5)
            end.paste(whole.crop((0,0,512,130)),(0,0));end.save(folder/f'facade_{key}_end.png')


def report_buildings(root,data,profiles):
    buildings=[dict(id=b['id'],name=b['name'],map_label=b['map_label'],height_m=b['height_m'],architecture=b['architecture']) for b in data['buildings']]
    report=dict(model_version='0.3',profile_validation_pass=True,measured_height_count=sum(b['architecture']['actual_height_measured'] for b in data['buildings']),
        photo_referenced_buildings=sum(bool(b['architecture']['photos']) for b in data['buildings']),
        floor_based_buildings=sum(b['architecture']['floor_count'] is not None for b in data['buildings']),
        floor_evidence_buildings=sum('assumption' not in b['architecture']['floor_status'] and b['architecture']['floor_count'] is not None for b in data['buildings']),
        building_count=len(buildings),sources=profiles['sources'],buildings=buildings,
        reconstruction_status='PARTIAL: unmeasured heights and unverified buildings remain explicitly marked',
        notes=['Storey heights, window spacing and roof rise are modeled estimates, not surveyed dimensions.',
               'Official 2023 new-building counts are not assigned to unidentified footprints on the older planning map.',
               'Known floor counts / minimum counts / photographic interpretations have distinct provenance.',
               'Facade textures are authored approximations; source photographs are not applied to the mesh.'])
    path=root/'data/building_reconstruction.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['# Building reconstruction evidence','',report['reconstruction_status'],'',
           f"Buildings: {len(buildings)}; photo-referenced: {report['photo_referenced_buildings']}; floor-based: {report['floor_based_buildings']}; non-typology floor evidence: {report['floor_evidence_buildings']}; measured heights: {report['measured_height_count']}",'',
           '| Mesh | Map label | Floors | Eave / total m | Roof | Floor provenance | Height provenance |',
           '|---|---|---|---|---|---|---|']
    for b in buildings:
        a=b['architecture'];lines.append(f"| {b['id']} | {b['map_label']} | {a['floor_count']} | {a['eave_height_m']:.2f} / {b['height_m']:.2f} | {a['roof_shape']} | {a['floor_status']} | {a['height_status']} |")
    lines+=['','## Sources','']+[f"- [{s['id']}]({s['url']}): {s['fact']}; retrieved {s['retrieved_date']}; SHA256 {s['sha256']}" for s in profiles['sources']]
    lines+=['','## Limits','']+['- '+n for n in report['notes']]
    (root/'output/validation/building_reconstruction_report.md').write_text('\n'.join(lines)+'\n')
    return report
