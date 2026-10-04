#!/usr/bin/env python3
"""One entry point. --verify-idempotency runs two complete clean builds."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
from analyze_map import analyze, write_json


def image_check(path,resolution):
    im=Image.open(path).convert('RGB')
    stat=ImageStat.Stat(im)
    small=im.resize((128,128))
    background=ImageStat.Stat(im.crop((0,0,16,16))).mean
    nonbackground=sum(sum((v-background[i])**2 for i,v in enumerate(p))>25**2
                      for p in (small.get_flattened_data() if hasattr(small,'get_flattened_data') else small.getdata()))/(128*128)
    result=dict(path=str(path),bytes=path.stat().st_size,resolution=list(im.size),
        mean_rgb=stat.mean,variance_rgb=stat.var,non_background_ratio=nonbackground)
    result['pass']=result['bytes']>1000 and list(im.size)==resolution and min(stat.var)>30 and 0.03<nonbackground<0.98
    return result


def clean_generated():
    """Delete only owned outputs; input and hand-maintained config stay intact."""
    for folder in ['data','output']:
        path=ROOT/folder
        if path.is_symlink():raise ValueError(f'Refusing to clear symlink: {path}')
    # Logs and idempotency evidence are preserved across the two passes.
    for path in list((ROOT/'output').iterdir()):
        if path.name in ['logs','idempotency_runs.json']:continue
        if path.is_dir() and not path.is_symlink():shutil.rmtree(path)
        else:path.unlink()
    for path in (ROOT/'data').glob('*.json'):path.unlink()
    for directory in ['output/previews','output/validation','output/logs']:
        (ROOT/directory).mkdir(parents=True,exist_ok=True)


def build_once(blender,index):
    clean_generated()
    metadata=analyze()
    log=ROOT/f'output/logs/run_{index:02}.log'
    with log.open('w') as stream:
        process=subprocess.run([blender,'--background','--factory-startup','--python-exit-code','1',
                 '--python',str(ROOT/'scripts/build_campus.py')],stdout=stream,stderr=subprocess.STDOUT)
    if process.returncode:
        print(log.read_text()[-7000:],file=sys.stderr)
        raise RuntimeError(f'Blender failed; see {log}')
    validation=json.loads((ROOT/'output/validation/blender_validation.json').read_text())
    cfg=json.loads((ROOT/'config/campus_config.json').read_text())
    renders=[image_check(ROOT/f'output/previews/{name}.png',cfg['render_resolution'])
             for name in ['top','perspective_01','perspective_02','reimported_fbx']]
    # Independent FBX render should also retain material/layout appearance.
    a=Image.open(ROOT/'output/previews/perspective_01.png').convert('RGB')
    b=Image.open(ROOT/'output/previews/reimported_fbx.png').convert('RGB')
    diff=ImageStat.Stat(ImageChops.difference(a,b))
    appearance=dict(mean_absolute_rgb_error=diff.mean,pass_=max(diff.mean)<12)
    files={name:dict(bytes=(ROOT/f'output/{name}').stat().st_size,
                     sha256=hashlib.sha256((ROOT/f'output/{name}').read_bytes()).hexdigest())
           for name in ['campus.blend','campus.fbx','campus.glb']}
    inputs_unchanged=hashlib.sha256(Path(metadata['input_path']).read_bytes()).hexdigest()==metadata['input_sha256'] and hashlib.sha256(Path(metadata['reference_path']).read_bytes()).hexdigest()==metadata['reference_sha256']
    passed=validation['pass_'] and all(r['pass'] for r in renders) and appearance['pass_'] and all(f['bytes']>1000 for f in files.values()) and inputs_unchanged
    run=dict(index=index,pass_=passed,map_sha256=hashlib.sha256((ROOT/'data/campus_map.json').read_bytes()).hexdigest(),
             source_scene=validation['original_scene'], comparison=validation['comparison'],
             render_validation=renders,fbx_render_appearance=appearance,artifacts=files,
             inputs_unchanged=inputs_unchanged,log=str(log))
    if not passed:raise ValueError(f'Artifact/render validation failed: {run}')
    return run,metadata,validation


def report(runs,metadata,validation,idem):
    final=runs[-1]
    report=dict(result='PASS' if idem['pass'] else 'PARTIAL',
        generated_at=datetime.now().astimezone().isoformat(),map_metadata=metadata,
        blender_validation=validation,render_validation=final['render_validation'],
        fbx_render_appearance=final['fbx_render_appearance'],artifacts=final['artifacts'],
        inputs_unchanged=final['inputs_unchanged'],idempotency=idem,
        findings_and_repairs=metadata['automatic_repairs'],
        remaining_limitations=metadata['assumptions']+[
            'No Unity/Tuanjie runtime was available; Blender FBX round-trip is verified, actual engine import remains a next-stage check.',
            'Collider components, layers, water exclusion and walkable masks must be configured in the engine.',
            'No collision components, vehicle logic, navigation bake, interiors or fine facade details are generated.',
            'Road slab tops are 0.045 m above ground at the current scale; engine collision design should account for these small transitions.'])
    write_json(ROOT/'output/validation/validation_report.json',report)
    scene=validation['original_scene']; counts=scene['category_counts']
    lines=['# Campus build validation report','',f"RESULT: {report['result']}",'',
        f"Blender: {validation['blender_version']}",f"Input: `{metadata['input_path']}`",
        f"Reference: `{metadata['reference_path']}`",f"Input size: {metadata['image_size_px']} px",
        f"Method: {metadata['method']}",'',
        f"Scale: **{metadata['meters_per_pixel']} m/px, {metadata['scale_status']}**. {metadata['scale_reason']}",
        '1 Blender unit = 1 modeled metre. X = image right, Y = image up, Z = height. Image Y is flipped; north = +Y.',
        f"Origin pixel: {metadata['origin_pixel']}. All dimensions, including default heights, scale through campus_config.json.",'',
        f"Campus Ground bbox (m): {scene['bbox_min']} to {scene['bbox_max']}",
        f"Campus dimensions (m): {scene['dimensions_m']}",
        f"Buildings: {counts['BLDG']}; road surface Mesh components: {counts['ROAD']}; annotated road routes: {metadata['planar_validation']['road_routes']}",
        f"Other object counts: {json.dumps({k:v for k,v in counts.items() if k not in ['BLDG','ROAD']})}",
        f"Meshes: {scene['object_count']}; vertices: {scene['total_vertices']}; faces: {scene['total_faces']}",
        f"Road widths (provisional metres): {metadata['planar_validation']['road_width_range_m']}",'',
        '## Automated acceptance','',
        '| Check | Result / evidence |','|---|---|',
        '| Original scene | PASS: required categories; finite coordinates; applied transforms; manifold solids; positive heights; normals and face areas |',
        '| Planar road/building overlap | '+str(metadata['planar_validation']['building_road_overlap_m2'])+' m² |',
        '| Unbridged road/water overlap | '+str(metadata['planar_validation']['unbridged_road_water_overlap_m2'])+' m² |',
        '| FBX export | PASS: -Z forward / Y up; meshes only; unit handling recorded in JSON |',
        f"| Fresh FBX import | PASS: {validation['fbx_reimport']['object_count']} Mesh objects; same object names/material slots |",
        f"| Bbox deviation | {validation['comparison']['max_bbox_delta_m']} m |",
        f"| Bidirectional vertex deviation | {validation['comparison']['max_vertex_delta_m']} m |",
        f"| Dimension ratios XYZ | {validation['comparison']['dimension_ratios']} |",
        '| Direction | PASS: world-space geometry matches, Z remains height; no axis swap or inversion |',
        '| Render camera framing | PASS: all eight bbox corners lie inside every automatic camera frame |',
        f"| Reimport render RGB mean error | {final['fbx_render_appearance']['mean_absolute_rgb_error']} |",
        f"| Original images preserved | {final['inputs_unchanged']} (SHA256 verified) |",
        f"| Clean repeated build | {'PASS' if idem['pass'] else 'NOT VERIFIED'}: {idem['runs']} full run(s) |",'',
        '## Render checks','', '| Image | Resolution | Mean RGB | Variance RGB | Non-background ratio | Result |',
        '|---|---|---|---|---|---|']
    for r in final['render_validation']:
        lines.append(f"| {Path(r['path']).name} | {r['resolution']} | {[round(x,2) for x in r['mean_rgb']]} | {[round(x,2) for x in r['variance_rgb']]} | {r['non_background_ratio']:.3f} | {'PASS' if r['pass'] else 'FAIL'} |")
    lines+=['','## Map facts versus modeling assumptions','',
        '### Read from the supplied maps','']+['- '+s for s in metadata['map_facts']]
    lines+=['','### Modeling assumptions','']+['- '+s for s in metadata['assumptions']]
    lines+=['','## Problems found and automatic repairs','']+['- '+s for s in report['findings_and_repairs']]
    lines+=['',f"Maximum local road-centreline correction: {metadata['planar_validation']['road_max_centerline_adjustment_px']:.3f} pixels. Corrected paths are visible in map_debug_overlay.png.",
            f"Road component areas: {metadata['planar_validation']['road_surface_component_areas_m2']} m².",'',
            '## Remaining limitations','']+['- '+s for s in report['remaining_limitations']]
    lines+=['','## Reproduce','', '```bash','python3 tools/campus_builder/run_pipeline.py --verify-idempotency','```','',
            'Only tool-owned data/output artifacts are cleared; source images and configuration are preserved.',
            'Detailed object checks, camera positions, hashes and repeated-run evidence are in validation_report.json and output/idempotency_runs.json.','']
    (ROOT/'output/validation/validation_report.md').write_text('\n'.join(lines))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-idempotency',action='store_true')
    parser.add_argument('--blender',default=shutil.which('blender'))
    args=parser.parse_args()
    if not args.blender:raise RuntimeError('Blender executable not found')
    (ROOT/'data').mkdir(exist_ok=True);(ROOT/'output').mkdir(exist_ok=True)
    runs=[]
    for index in range(1,3 if args.verify_idempotency else 2):
        print(f'Clean build {index}: map -> Blender -> FBX -> clean import -> render -> image checks',flush=True)
        run,metadata,validation=build_once(args.blender,index)
        runs.append(run)
        write_json(ROOT/'output/idempotency_runs.json',runs)
        print(f"Build {index} PASS: {run['source_scene']['object_count']} meshes",flush=True)
    idem=dict(runs=len(runs))
    idem['pass']=len(runs)>=2 and len({r['map_sha256'] for r in runs})==1 and all(r['source_scene']==runs[0]['source_scene'] for r in runs)
    idem['criteria']='Each run clears generated data/assets/previews; metric map SHA256 and all source mesh summaries must match; each FBX round-trip and render must pass independently.'
    report(runs,metadata,validation,idem)
    print('RESULT: '+('PASS' if idem['pass'] else 'PARTIAL (run --verify-idempotency for repeated clean-build acceptance)'),flush=True)
    if args.verify_idempotency and not idem['pass']:raise RuntimeError('Idempotency verification failed')


if __name__=='__main__':main()
