"""Auditable robust metric calibration; residual PASS never substitutes evidence PASS."""
import hashlib
import json
import math
import statistics
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
from metric_mapping import MetricMapping


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def metrics(distances, records, weights):
    errors=[d-r['real_distance_m'] for d,r in zip(distances,records)]
    relative=[e/r['real_distance_m']*100 for e,r in zip(errors,records)]
    total=sum(weights)
    return dict(rmse_m=math.sqrt(sum(w*e*e for w,e in zip(weights,errors))/total),
                rmse_percent=math.sqrt(sum(w*e*e for w,e in zip(weights,relative))/total),
                max_relative_error_percent=max(map(abs,relative)),
                relative_errors_percent=relative)


def uniform_fit(records, base):
    candidates=[r['real_distance_m']/r['pixel_distance'] for r in records]
    median=statistics.median(candidates)
    mad=statistics.median(abs(v-median) for v in candidates)
    # A relative floor prevents MAD=0 from rejecting small ordinary measurement noise.
    threshold=max(3*1.4826*mad,median*0.08)
    outliers=[abs(v-median)>threshold for v in candidates]
    weights=[w*(0.05 if o else 1) for w,o in zip(base,outliers)]
    s=median
    for _ in range(12):
        predicted=[s*r['pixel_distance'] for r in records]
        relative=[abs(d-r['real_distance_m'])/r['real_distance_m'] for d,r in zip(predicted,records)]
        # Huber IRLS in relative residuals, with the specified metre-space WLS solution.
        current=[w*min(1,0.05/max(e,1e-12)) for w,e in zip(weights,relative)]
        s=sum(w*r['pixel_distance']*r['real_distance_m'] for w,r in zip(current,records))/sum(w*r['pixel_distance']**2 for w,r in zip(current,records))
    return dict(model='uniform_scale',meters_per_pixel=s,
        **metrics([s*r['pixel_distance'] for r in records],records,base)), current, outliers, median, mad


def anisotropic_fit(records, weights):
    # Nonlinear least squares on lengths, not on squared lengths.
    s=sum(w*r['pixel_distance']*r['real_distance_m'] for w,r in zip(weights,records))/sum(w*r['pixel_distance']**2 for w,r in zip(weights,records))
    sx=sy=s
    for _ in range(30):
        aa=ab=bb=ar=br=0.0
        for r,w in zip(records,weights):
            dx,dy=r['pixel_delta']; prediction=math.hypot(sx*dx,sy*dy)
            ja,jb=sx*dx*dx/prediction,sy*dy*dy/prediction
            error=r['real_distance_m']-prediction
            aa+=w*ja*ja;ab+=w*ja*jb;bb+=w*jb*jb;ar+=w*ja*error;br+=w*jb*error
        det=aa*bb-ab*ab
        if abs(det)<1e-12:return None
        da,db=(ar*bb-br*ab)/det,(br*aa-ar*ab)/det
        sx+=da;sy+=db
        if sx<=0 or sy<=0:return None
        if abs(da)+abs(db)<1e-12:break
    return dict(model='anisotropic_scale',meters_per_pixel_x=sx,meters_per_pixel_y=sy,
                **metrics([math.hypot(sx*r['pixel_delta'][0],sy*r['pixel_delta'][1]) for r in records],records,weights))


def similarity_fit(points):
    if len(points)<3:return None
    p=[(v['pixel'][0],-v['pixel'][1]) for v in points];q=[v['metric'] for v in points]
    cross=max(abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])) for a in p for b in p for c in p)
    if cross<1e-6:return None
    pc=[statistics.mean(v[i] for v in p) for i in range(2)]
    qc=[statistics.mean(v[i] for v in q) for i in range(2)]
    denominator=sum((a[0]-pc[0])**2+(a[1]-pc[1])**2 for a in p)
    dot=sum((a[0]-pc[0])*(b[0]-qc[0])+(a[1]-pc[1])*(b[1]-qc[1]) for a,b in zip(p,q))
    skew=sum((a[0]-pc[0])*(b[1]-qc[1])-(a[1]-pc[1])*(b[0]-qc[0]) for a,b in zip(p,q))
    a,b=dot/denominator,skew/denominator
    tx,ty=qc[0]-a*pc[0]+b*pc[1],qc[1]-b*pc[0]-a*pc[1]
    matrix=[[a,b,tx],[b,-a,ty],[0,0,1]]
    errors=[math.dist([a*x+b*y+tx,b*x-a*y+ty],v['metric']) for v in points for x,y in [v['pixel']]]
    return dict(model='similarity_transform',matrix=matrix,scale=math.hypot(a,b),
                control_point_rmse_m=math.sqrt(statistics.mean(e*e for e in errors)),control_point_errors_m=errors)


def calibrate():
    cfg=json.loads((ROOT/'config/scale_anchors.json').read_text())
    campus=json.loads((ROOT/'config/campus_config.json').read_text())
    geometry=json.loads((ROOT/'config/source_geometry.json').read_text())
    image=Image.open(REPO/campus['primary_map']).convert('RGB')
    records=[];base=[];groups={}
    for raw in cfg['anchors']:
        if raw.get('enabled',True) is False:continue
        r=dict(raw)
        if r.get('metric_a') is not None:
            r['real_distance_m']=math.dist(r['metric_a'],r['metric_b'])
        length=float(r['real_distance_m']);a,b=r['pixel_a'],r['pixel_b']
        if not math.isfinite(length) or length<=0 or math.dist(a,b)<=0:
            raise ValueError(f"Invalid scale anchor {r['id']}")
        for p in [a,b]:
            if not all(math.isfinite(v) for v in p) or not (0<=p[0]<image.width and 0<=p[1]<image.height):
                raise ValueError(f"Scale anchor outside image: {r['id']}")
        if not r.get('source') or not r.get('source_type') or not r.get('source_id'):
            raise ValueError('All anchors require source attribution')
        evidence=ROOT/r['evidence_file']
        if not evidence.is_file():raise ValueError(f'Missing evidence {evidence}')
        r['evidence_sha256']=hashlib.sha256(evidence.read_bytes()).hexdigest()
        r['pixel_delta']=[b[i]-a[i] for i in range(2)];r['pixel_distance']=math.dist(a,b)
        r['candidate_scale']=length/r['pixel_distance']
        factor={'high':1.0,'medium':0.5,'low':0.15}[r['confidence'].lower()]
        weight=float(r['weight'])*factor
        if not math.isfinite(weight) or weight<=0:raise ValueError('Anchor weight must be finite and positive')
        records.append(r);base.append(weight)
        group=r.get('correlation_group',r['source_id']);groups[group]=groups.get(group,0)+1
    if not records:raise ValueError('No usable length anchors; add lengths or pairwise distances from measured controls to scale_anchors.json')
    # Divide by group size, keeping confidence weights while avoiding duplicated
    # lengths from one reference receiving disproportionate influence.
    base=[w/groups[r.get('correlation_group',r['source_id'])] for w,r in zip(base,records)]
    uniform,effective,outliers,median,mad=uniform_fit(records,base)
    candidates=[uniform];selected=uniform;reason='Simpler model first: uniform residuals do not justify extra degrees of freedom.'
    policy=cfg['model_selection']
    anisotropic=None
    directional=[sum(abs(r['pixel_delta'][i])>2*abs(r['pixel_delta'][1-i]) for r in records) for i in range(2)]
    if len(records)>=policy['anisotropic_min_anchor_count'] and min(directional)>=2:
        anisotropic=anisotropic_fit(records,base)
        if anisotropic:
            candidates.append(anisotropic)
            improvement=uniform['rmse_percent']-anisotropic['rmse_percent']
            difference=abs(anisotropic['meters_per_pixel_x']/anisotropic['meters_per_pixel_y']-1)*100
            verified_directional=[{r['source_id'] for r in records if r['source_type']!='standard-dimension assumption' and abs(r['pixel_delta'][i])>2*abs(r['pixel_delta'][1-i])} for i in range(2)]
            if improvement>=policy['minimum_anisotropic_rmse_improvement_percent_points'] and difference>=policy['minimum_anisotropic_scale_difference_percent'] and min(map(len,verified_directional))>=2:
                selected=anisotropic;reason='Independent verified directional evidence and material residual improvement justify anisotropic scale.'
    controls=cfg.get('control_points',[])
    similarity=similarity_fit(controls)
    if similarity:
        candidates.append(similarity)
        if not all(v.get('source_type') in ['survey','GIS','measured'] and v.get('source') for v in controls):
            raise ValueError('Similarity control points must have actual verified coordinate provenance')
        if similarity['control_point_rmse_m']<=cfg.get('control_point_tolerance_m',2):
            selected=similarity;reason='Verified non-collinear metric controls support similarity registration.'
    x1,y1,x2,y2=geometry['ground_bounds_px'];cx,cy=(x1+x2)/2,(y1+y2)/2
    if selected['model']=='similarity_transform':
        matrix=[row[:] for row in selected['matrix']]
        metric_origin=[matrix[i][0]*cx+matrix[i][1]*cy+matrix[i][2] for i in range(2)]
        for i in range(2):matrix[i][2]-=metric_origin[i]
    else:
        sx=selected.get('meters_per_pixel_x',selected.get('meters_per_pixel'));sy=selected.get('meters_per_pixel_y',sx)
        matrix=[[sx,0,-sx*cx],[0,-sy,sy*cy],[0,0,1]];metric_origin=[0,0]
    mapping=MetricMapping({'pixel_to_metric_matrix':matrix})
    predictions=[mapping.distance(r['pixel_a'],r['pixel_b']) for r in records]
    summary=metrics(predictions,records,base)
    acceptance=cfg['acceptance'];verified={r['source_id'] for r in records if r['source_type']!='standard-dimension assumption' and not outliers[records.index(r)]}
    conflicts=[r['id'] for r,e,o in zip(records,summary['relative_errors_percent'],outliers) if r['confidence'].lower()=='high' and (abs(e)>acceptance['max_reliable_error_percent'] or o)]
    reliable_max=max([abs(e) for r,e in zip(records,summary['relative_errors_percent']) if r['confidence'].lower()!='low'] or [0])
    majority=sum(abs(e)<=acceptance['majority_error_percent'] for e in summary['relative_errors_percent'])/len(records)
    residual_pass=len(records)>=acceptance['minimum_anchor_count'] and summary['rmse_percent']<=acceptance['warning_rmse_percent'] and majority>=0.8 and reliable_max<=acceptance['max_reliable_error_percent'] and not conflicts
    evidence_pass=len(verified)>=acceptance['minimum_verified_source_count']
    spatial_groups={r.get('spatial_group',r['source_id']) for r in records if r['source_type']!='standard-dimension assumption'}
    confidence='HIGH' if residual_pass and summary['rmse_percent']<=acceptance['good_rmse_percent'] and len(verified)>=2 and len(spatial_groups)>=2 and sum(r['confidence'].lower()=='high' for r in records)>=3 else 'MEDIUM' if evidence_pass and residual_pass else 'LOW'
    for r,w,ew,o,prediction,error in zip(records,base,effective,outliers,predictions,summary['relative_errors_percent']):
        r.update(estimated_distance_m=prediction,absolute_error_m=abs(prediction-r['real_distance_m']),
                 signed_error_m=prediction-r['real_distance_m'],relative_error_percent=error,
                 normalized_weight=w,effective_fit_weight=ew,outlier=o,
                 metric_a=mapping.point(r['pixel_a']),metric_b=mapping.point(r['pixel_b']))
    result=dict(schema_version=2,model_version='0.2',calibration_version='0.2',
        status='calibrated' if residual_pass and evidence_pass else 'conditional' if residual_pass else 'conflicting',
        pass_=residual_pass and evidence_pass,residual_pass=residual_pass,evidence_pass=evidence_pass,
        reason=None if residual_pass and evidence_pass else 'INSUFFICIENT SCALE EVIDENCE' if not evidence_pass else 'SCALE ANCHOR CONFLICT',
        model=selected['model'],meters_per_pixel=selected.get('meters_per_pixel'),
        meters_per_pixel_x=math.hypot(matrix[0][0],matrix[1][0]),meters_per_pixel_y=math.hypot(matrix[0][1],matrix[1][1]),
        pixel_to_metric_matrix=matrix,origin_pixel=[cx,cy],metric_reference_origin=metric_origin,
        anchor_count=len(records),independent_source_count=len({r['source_id'] for r in records}),
        independent_spatial_group_count=len({r.get('spatial_group',r['source_id']) for r in records}),
        verified_source_count=len(verified),confidence=confidence,anchors=records,
        **summary,candidates=candidates,selection_reason=reason,
        robust_statistics=dict(candidate_scale_median=median,candidate_scale_MAD=mad,
            outlier_ids=[r['id'] for r,o in zip(records,outliers) if o],high_confidence_conflicts=conflicts),
        acceptance=acceptance,required_extra_evidence=cfg['required_extra_evidence'],
        uncertainty_note='Residuals quantify fit conditional on the reference dimensions. They do not bound actual campus-scale error when facility standard compliance is unknown.')
    write(ROOT/'data/scale_calibration.json',result)
    lines=['# Campus V0.2 scale calibration','',f"SCALE: {'PASS' if result['pass_'] else 'PARTIAL'} — {result['reason'] or 'verified evidence and residual criteria met'}",'',
        f"Model: {result['model']}; confidence: **{confidence}**; status: {result['status']}",
        f"Scale X/Y: {result['meters_per_pixel_x']:.9f} / {result['meters_per_pixel_y']:.9f} m/px",
        f"Anchors: {len(records)}; independent source documents: {result['independent_source_count']}; independent physical areas: {result['independent_spatial_group_count']}; verified actual campus sources: {len(verified)}",
        f"Weighted RMSE: {summary['rmse_m']:.4f} m / {summary['rmse_percent']:.4f}%; maximum residual: {summary['max_relative_error_percent']:.4f}%",
        f"Residual criterion: {residual_pass}; real-world evidence criterion: {evidence_pass}",reason,'',
        '| Anchor | Pixels | Reference m | Predicted m | Absolute residual m | Signed relative residual % | Weight | Confidence | Source |',
        '|---|---|---|---|---|---|---|---|---|']
    for r in records:lines.append(f"| {r['id']} | {r['pixel_distance']:.3f} | {r['real_distance_m']:.3f} | {r['estimated_distance_m']:.3f} | {r['absolute_error_m']:.3f} | {r['relative_error_percent']:.3f} | {r['normalized_weight']:.3f} | {r['confidence']} | [{r['source_id']}]({r['source']}) — {r['source_type']} |")
    lines+=['','## Candidate models','', '```json',json.dumps(candidates,indent=2),'```','',
        '## Facts and assumptions','',
        '- FACT: standard reference dimensions are documented by their publishers. Source summaries, URLs, access date and SHA256 are saved.',
        '- FACT: pixel endpoints are selected on the supplied planning map. The official school image has the same layout and no scale bar.',
        '- ASSUMPTION: this campus track is an eight-lane standard track and its pitch uses FIFA recommended dimensions. Neither has been verified.',
        '- Four lines are not four independent measurements: they share one sports complex and two normative documents; correlation-group weight is normalized.',
        '- LOW confidence remains LOW even when conditional fit RMSE is small. No claim of surveyed campus dimensions is made.',
        '- XY mapping is independent of Z building heights and all environment thicknesses.',
        '- OSM raw-data requests timed out or returned HTTP 406. No unverified OSM coordinates or tertiary web size estimates entered the fit.',
        '', '## Minimal additional information','',cfg['required_extra_evidence']['request'],
        'A surveyed length between pixel [210,552] and [210,692] can replace TRACK_OUTER_LONG. For HIGH confidence, also provide an independent long baseline outside the sports complex, with clearly identified map endpoints.',
        '',result['uncertainty_note'],'']
    path=ROOT/'output/validation/scale_calibration_report.md';path.parent.mkdir(parents=True,exist_ok=True);path.write_text('\n'.join(lines))
    scale_overlay(image,result)
    return result


def scale_overlay(image,calibration):
    mapping=MetricMapping(calibration);matrix=mapping.matrix
    a,b,tx=matrix[0];c,d,ty=matrix[1];det=a*d-b*c
    def inverse(x,y):return ((d*(x-tx)-b*(y-ty))/det,(-c*(x-tx)+a*(y-ty))/det)
    points=[mapping.point(p) for p in [(0,0),(image.width,0),(0,image.height),(image.width,image.height)]]
    xs=[p[0] for p in points];ys=[p[1] for p in points];spacing=50
    out=image.copy();draw=ImageDraw.Draw(out)
    for i in range(math.floor(min(xs)/spacing),math.ceil(max(xs)/spacing)+1):
        x=i*spacing;p1,p2=inverse(x,min(ys)),inverse(x,max(ys));draw.line([p1,p2],fill=(0,160,190),width=1)
        for y in [image.height-20,68]:
            px,_=inverse(x,0);draw.text((px,y),f'{x:g}m',fill=(0,60,90),stroke_width=1,stroke_fill='white')
    for i in range(math.floor(min(ys)/spacing),math.ceil(max(ys)/spacing)+1):
        y=i*spacing;p1,p2=inverse(min(xs),y),inverse(max(xs),y);draw.line([p1,p2],fill=(0,160,190),width=1)
        _,py=inverse(0,y);draw.text((5,py),f'{y:g}m',fill=(0,60,90),stroke_width=1,stroke_fill='white')
    draw.rectangle((2,2,image.width-2,62),fill='white')
    draw.text((10,8),f"V0.2 {calibration['model']} | 50m grid | {calibration['confidence']} confidence | {calibration['status']}",fill='black')
    draw.text((10,30),'Standard facility assumptions are NOT measured campus dimensions.',fill='red')
    for i,r in enumerate(calibration['anchors'],1):
        pa,pb=tuple(r['pixel_a']),tuple(r['pixel_b']);draw.line([pa,pb],fill=(255,0,70),width=3)
        for x,y in [pa,pb]:draw.ellipse((x-3,y-3,x+3,y+3),fill='yellow',outline='red')
        y=80+(i-1)*47
        draw.rectangle((450,y,895,y+43),fill='white')
        draw.text((455,y+2),f"A{i} {r['id']}: reference {r['real_distance_m']:.2f}m",fill='black')
        draw.text((455,y+20),f"mapped {r['estimated_distance_m']:.2f}m | error {r['relative_error_percent']:+.2f}%",fill='red')
        draw.text(pa,f'A{i}',fill='black',stroke_width=2,stroke_fill='yellow')
    path=ROOT/'output/previews/scale_debug_overlay.png';path.parent.mkdir(parents=True,exist_ok=True);out.save(path)


if __name__=='__main__':
    result=calibrate();print(json.dumps({k:result[k] for k in ['model','meters_per_pixel','rmse_percent','confidence','pass_','reason']},indent=2))
