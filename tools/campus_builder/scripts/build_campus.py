"""Blender CLI: build, validate, export, render, reset, import, validate, render."""
import json
import sys
from pathlib import Path

import bpy
import bmesh

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_scene import snapshot, public_snapshot, compare
from render_validation import setup, render
from validate_metric import validate_metric


def write(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def collection(name,parent):
    coll=bpy.data.collections.new(name); parent.children.link(coll); return coll


def material(name,color):
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1)
    mat.use_nodes=True
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=(*color,1)
    bsdf.inputs['Roughness'].default_value=0.85
    return mat


def solid(feature,coll,mat,bottom,top):
    points=feature['vertices_xy_m']; n=len(points)
    vertices=[(x,y,z) for z in [bottom,top] for x,y in points]
    faces=[]
    for triangle in feature['triangles']:
        a,b,c=[points[i] for i in triangle]
        signed=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        t=triangle if signed>0 else triangle[::-1]
        faces.append(tuple(i+n for i in t))
        faces.append(tuple(t[::-1]))
    for ri,ring in enumerate(feature['boundary_rings']):
        area=sum(points[a][0]*points[b][1]-points[b][0]*points[a][1] for a,b in zip(ring,ring[1:]+ring[:1]))
        if (ri==0 and area<0) or (ri>0 and area>0):ring=ring[::-1]
        for a,b in zip(ring,ring[1:]+ring[:1]):faces.append((a,b,b+n,a+n))
    mesh=bpy.data.meshes.new(feature['id']+'_Mesh'); mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=0.00001)
    bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=0.00001)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    obj=bpy.data.objects.new(feature['id'],mesh); coll.objects.link(obj)
    obj.data.materials.append(mat)
    obj['campus_feature_id']=feature['id'];obj['source_name']=feature.get('name',feature['id'])
    obj['physics_hint']='static obstacle' if feature['id'].startswith('BLDG') else 'environment surface'
    if 'map_label' in feature:obj['map_label']=feature['map_label']
    obj['surface_type']=feature.get('surface_type','road' if feature['id'].startswith('ROAD') else 'building' if feature['id'].startswith('BLDG') else 'environment')
    obj['driveable']=feature.get('driveable','unknown')
    obj['collidable']=feature.get('collidable',True)
    return obj


def main():
    cfg=json.loads((ROOT/'config/campus_config.json').read_text())
    data=json.loads((ROOT/'data/campus_map.json').read_text())
    calibration=json.loads((ROOT/'data/scale_calibration.json').read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1.0
    campus=collection('Campus',scene.collection)
    collections={n:collection(n,campus) for n in ['Ground','Roads','Bridges','Buildings','Vegetation','Water','Walls','Landmarks','Plazas']}
    mats={key:material(key,color) for key,color in {
        'Building':(0.72,0.58,0.39),'Road':(0.16,0.18,0.20),
        'Grass':(0.25,0.44,0.19),'Ground':(0.68,0.66,0.58),
        'Water':(0.055,0.34,0.57),'Wall':(0.46,0.45,0.41),
        'Plaza':(0.63,0.32,0.20),'Track':(0.63,0.29,0.15),'Court':(0.31,0.52,0.35)}.items()}
    solid(data['ground'],collections['Ground'],mats['Ground'],data['ground']['bottom_m'],0)
    for b in data['buildings']:solid(b,collections['Buildings'],mats['Building'],0,b['height_m'])
    for category,coll,mat in [('roads','Roads','Road'),('bridges','Bridges','Road'),('grass','Vegetation','Grass'),('water','Water','Water'),('plazas','Plazas','Plaza'),('walls','Walls','Wall')]:
        for feature in data[category]:solid(feature,collections[coll],mats[mat],feature['bottom_m'],feature['top_m'])
    for feature in data['landmarks']:
        mat={'track':'Track','field':'Grass','court':'Court','water':'Water'}[feature['kind']]
        solid(feature,collections['Landmarks'],mats[mat],feature['bottom_m'],feature['top_m'])
    original=snapshot()
    write(ROOT/'output/validation/source_scene.json',public_snapshot(original))
    if not original['pass_']:raise ValueError(f"Source scene failed: {original['errors'][:12]}")
    source_metric=validate_metric(data,calibration,cfg)
    if not source_metric['pass_']:raise ValueError('Source absolute metric validation failed')
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'output/campus.blend'))
    # Inspect the live operator schema before using required Unity axis settings.
    operator=bpy.ops.export_scene.fbx.get_rna_type().properties
    for key in ['axis_forward','axis_up','apply_unit_scale','apply_scale_options','bake_space_transform']:
        if key not in operator:raise RuntimeError(f'FBX API lacks {key}')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in scene.objects:
        if obj.type=='MESH' and not obj.get('validation_only'):obj.select_set(True)
    bpy.ops.export_scene.fbx(filepath=str(ROOT/'output/campus.fbx'),use_selection=True,
        object_types={'MESH'},axis_forward='-Z',axis_up='Y',global_scale=1.0,
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
        bake_space_transform=True,use_mesh_modifiers=True,mesh_smooth_type='FACE',
        add_leaf_bones=False,bake_anim=False,use_custom_props=True,path_mode='AUTO')
    bpy.ops.export_scene.gltf(filepath=str(ROOT/'output/campus.glb'),export_format='GLB',
                              use_selection=True,export_yup=True)
    export=dict(pass_=True,axis_forward='-Z',axis_up='Y',apply_unit_scale=True,
                apply_scale_options='FBX_SCALE_UNITS',bake_space_transform=True,
                exported_meshes=original['object_count'],cameras_lights_exported=False)
    export['scale_references_exported']=False
    setup(scene,cfg)
    cameras=[]
    for name,direction in [('top',(0,0,1)),('perspective_01',(0.8,-1.0,1.4)),('perspective_02',(-0.9,1.0,1.2))]:
        cameras.append(render(ROOT/f'output/previews/{name}.png',original,direction,cfg))
    # Fresh factory scene guarantees that the imported FBX stands alone.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1.0
    bpy.ops.import_scene.fbx(filepath=str(ROOT/'output/campus.fbx'),use_custom_props=True)
    imported=snapshot(require_applied=False)
    if any(o.name.startswith('ScaleReference_') for o in scene.objects):raise ValueError('Debug scale objects leaked into FBX')
    comparison=compare(original,imported,cfg['bbox_tolerance_m'])
    write(ROOT/'output/validation/reimport_scene.json',public_snapshot(imported))
    if not imported['pass_'] or not comparison['pass_']:
        raise ValueError(f"FBX validation failed: {imported['errors'][:12]} {comparison['errors']}")
    imported_metric=validate_metric(data,calibration,cfg)
    if not imported_metric['pass_']:raise ValueError('FBX absolute metric validation failed')
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'output/validation/reimported_fbx.blend'))
    setup(scene,cfg)
    cameras.append(render(ROOT/'output/previews/reimported_fbx.png',imported,(0.8,-1.0,1.4),cfg))
    write(ROOT/'output/validation/blender_validation.json',dict(blender_version=bpy.app.version_string,
          original_scene=public_snapshot(original),fbx_export=export,
          fbx_reimport=public_snapshot(imported),comparison=comparison,camera_validation=cameras,
          absolute_metric_validation=dict(source=source_metric,reimport=imported_metric),
          pass_=original['pass_'] and imported['pass_'] and comparison['pass_'] and imported_metric['pass_'] and source_metric['pass_']))
    print('CAMPUS_BLENDER_VALIDATION_PASS', flush=True)


if __name__=='__main__':main()
