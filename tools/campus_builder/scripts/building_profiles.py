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
        inset=profile.get('facade_base_inset_fraction',0)
        if not 0<=inset<=.15 or (inset and profile['kind']!='exhibition'):
            raise ValueError('Facade taper is restricted to the convex exhibition footprint')
        if profile.get('facade_uv_mode','storey_repeat') not in ['storey_repeat','full_height']:
            raise ValueError('Unsupported facade UV mode')
        if profile.get('roof_seam_pitch_m',1)<=0:
            raise ValueError('Roof seam pitch must be positive')
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
        if p['kind'] in ['exhibition','gym','library']:
            # Full-height references preserve the distinction between glazing,
            # opaque bands and structural piers without extra collision meshes.
            whole=Image.new('RGB',(512,1024),wall);d=ImageDraw.Draw(whole)
            glass=rgb(p['glass_rgb']);frame=(179,185,182)
            if p['kind']=='exhibition':
                d.rectangle((0,0,511,1023),fill=glass)
                for y in [65,315,565,815]:
                    d.rectangle((0,y,511,y+82),fill=(102,110,111))
                    for rib in range(y+3,y+82,6):d.line((0,rib,511,rib),fill=(146,151,149),width=2)
                for x in [0,128,256,384,511]:d.line((x,0,x,1023),fill=frame,width=5)
                for y in range(0,1024,125):d.line((0,y,511,y),fill=frame,width=4)
            elif p['kind']=='gym':
                for y0,y1 in [(58,235),(400,570),(682,978)]:
                    d.rectangle((58,y0,454,y1),fill=glass)
                    for x in range(58,455,66):d.line((x,y0,x,y1),fill=frame,width=6)
                    d.line((58,(y0+y1)//2,454,(y0+y1)//2),fill=frame,width=5)
                d.rectangle((0,268,511,302),fill=(134,141,138))
                d.rectangle((0,609,511,637),fill=(160,161,152))
                d.rectangle((0,0,40,1023),fill=tuple(min(255,c+12) for c in wall))
                d.rectangle((470,0,511,1023),fill=tuple(max(0,c-12) for c in wall))
            else:
                d.rectangle((40,38,472,99),fill=glass)
                for y0,y1 in [(220,370),(475,625),(730,900)]:
                    for x0,x1 in [(55,235),(276,456)]:
                        d.rectangle((x0,y0,x1,y1),fill=glass)
                        for x in [x0,(x0+x1)//2,x1]:d.line((x,y0,x,y1),fill=frame,width=5)
                        d.line((x0,y0+45,x1,y0+45),fill=frame,width=5)
                for y in [128,405,660,950]:d.line((0,y,511,y),fill=tuple(max(0,c-15) for c in wall),width=4)
            whole.save(folder/f'facade_{key}.png')
        if p.get('roof_surface')=='standing_seam':
            roof=Image.new('RGB',(512,512),rgb(p['roof_rgb']));d=ImageDraw.Draw(roof)
            d.line((3,0,3,511),fill=(97,107,109),width=7)
            d.line((10,0,10,511),fill=(190,195,193),width=5)
            d.line((0,509,511,509),fill=(120,130,130),width=2)
            roof.save(folder/f'roof_{key}.png')
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
    report=dict(model_version=data.get('model_version','0.3'),appearance_revision=profiles.get('appearance_revision'),profile_validation_pass=True,measured_height_count=sum(b['architecture']['actual_height_measured'] for b in data['buildings']),
        photo_referenced_buildings=sum(bool(b['architecture']['photos']) for b in data['buildings']),
        floor_based_buildings=sum(b['architecture']['floor_count'] is not None for b in data['buildings']),
        floor_evidence_buildings=sum('assumption' not in b['architecture']['floor_status'] and b['architecture']['floor_count'] is not None for b in data['buildings']),
        building_count=len(buildings),sources=profiles['sources'],buildings=buildings,
        reconstruction_status='PARTIAL: unmeasured heights and unverified buildings remain explicitly marked',
        notes=['Storey heights, window spacing and roof rise are modeled estimates, not surveyed dimensions.',
               'Official 2023 new-building counts are not assigned to unidentified footprints on the older planning map.',
               'Known floor counts / minimum counts / photographic interpretations have distinct provenance.',
               'Facade textures are authored approximations; source photographs are not applied to the mesh.',
               'Exhibition taper stays inside the original XY envelope; the source polygon remains a conservative navigation obstacle.',
               'Curved facades use continuous perimeter UVs. Metal roof seams are image details, not added mesh strips.'])
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
