"""Blender CLI: build, validate, export, render, reset, import, validate, render."""
import json
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from validate_scene import snapshot, public_snapshot, compare
from render_validation import setup, render
from validate_metric import validate_metric
from building_geometry import facade_material,finish_building
from metric_mapping import MetricMapping
import build_robot
import build_delivery_sites


def write(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def render_robot(path,bounds,direction,cfg):
    scene=bpy.context.scene
    samples,denoise=scene.cycles.samples,scene.cycles.use_denoising
    scene.cycles.samples=64;scene.cycles.use_denoising=True
    try:return render(path,bounds,direction,cfg)
    finally:scene.cycles.samples=samples;scene.cycles.use_denoising=denoise


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
    cfg['roof_texture_root']=ROOT/'output/textures'
    data=json.loads((ROOT/'data/campus_map.json').read_text())
    calibration=json.loads((ROOT/'data/scale_calibration.json').read_text())
    robot_data=json.loads((ROOT/'data/delivery_robot.json').read_text())
    delivery_data=json.loads((ROOT/'data/delivery_sites.json').read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1.0
    campus=collection('Campus',scene.collection)
    collections={n:collection(n,campus) for n in ['Ground','Roads','Bridges','Buildings','Vegetation','Water','Walls','Landmarks','Plazas','AccessPaths','DeliverySites']}
    mats={key:material(key,color) for key,color in {
        'Building':(0.72,0.58,0.39),'Road':(0.16,0.18,0.20),
        'Grass':(0.25,0.44,0.19),'Ground':(0.68,0.66,0.58),
        'Water':(0.055,0.34,0.57),'Wall':(0.46,0.45,0.41),
        'Plaza':(0.63,0.32,0.20),'Track':(0.63,0.29,0.15),'Court':(0.31,0.52,0.35)}.items()}
    solid(data['ground'],collections['Ground'],mats['Ground'],data['ground']['bottom_m'],0)
    for b in data['buildings']:
        a=b['architecture']
        obj=solid(b,collections['Buildings'],facade_material(b,ROOT,material),0,a['eave_height_m'])
        roof=bpy.data.materials.get('Roof_'+b['map_label']) or material('Roof_'+b['map_label'],a['roof_rgb'])
        end=facade_material(b,ROOT,material,'_end') if a['kind']=='administration' else None
        finish_building(obj,b,cfg,roof,end)
    for category,coll,mat in [('roads','Roads','Road'),('bridges','Bridges','Road'),('grass','Vegetation','Grass'),('water','Water','Water'),('plazas','Plazas','Plaza'),('walls','Walls','Wall')]:
        for feature in data[category]:solid(feature,collections[coll],mats[mat],feature['bottom_m'],feature['top_m'])
    for feature in data['landmarks']:
        mat={'track':'Track','field':'Grass','court':'Court','water':'Water'}[feature['kind']]
        solid(feature,collections['Landmarks'],mats[mat],feature['bottom_m'],feature['top_m'])
    build_delivery_sites.build(delivery_data,collections,solid,material)
    delivery_source=build_delivery_sites.validate(delivery_data)
    if not delivery_source['pass_']:raise ValueError(f'Candidate delivery source geometry failed: {delivery_source}')
    robot_root,robot_collection=build_robot.build(robot_data,material)
    robot_source=build_robot.validate(robot_data)
    if not robot_source['pass_']:raise ValueError(f'Robot validation failed: {robot_source}')
    original=snapshot()
    write(ROOT/'output/validation/source_scene.json',public_snapshot(original))
    if not original['pass_']:raise ValueError(f"Source scene failed: {original['errors'][:12]}")
    source_metric=validate_metric(data,calibration,cfg)
    write(ROOT/'output/validation/source_metric.json',source_metric)
    if not source_metric['pass_']:raise ValueError('Source absolute metric validation failed')
    center=(Vector(original['bbox_min'])+Vector(original['bbox_max']))/2
    size=(Vector(original['bbox_max'])-Vector(original['bbox_min'])).length
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active
                space.region_3d.view_location=center
                space.region_3d.view_distance=size*.75
                space.region_3d.view_rotation=Vector((-.8,1,-1.4)).to_track_quat('-Z','Y')
                space.region_3d.view_perspective='ORTHO'
                space.shading.type='MATERIAL'
                space.clip_end=size*10
    bpy.ops.file.pack_all()
    bpy.ops.object.select_all(action='DESELECT')
    robot_root.select_set(True);bpy.context.view_layer.objects.active=robot_root
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'output/campus.blend'))
    # Inspect the live operator schema before using required Unity axis settings.
    operator=bpy.ops.export_scene.fbx.get_rna_type().properties
    for key in ['axis_forward','axis_up','apply_unit_scale','apply_scale_options','bake_space_transform']:
        if key not in operator:raise RuntimeError(f'FBX API lacks {key}')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in scene.objects:
        if obj.type in {'MESH','EMPTY'} and not obj.get('validation_only'):obj.select_set(True)
    bpy.ops.export_scene.fbx(filepath=str(ROOT/'output/campus.fbx'),use_selection=True,
        object_types={'MESH','EMPTY'},axis_forward='-Z',axis_up='Y',global_scale=1.0,
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
        bake_space_transform=False,use_mesh_modifiers=True,mesh_smooth_type='FACE',
        add_leaf_bones=False,bake_anim=False,use_custom_props=True,path_mode='COPY',embed_textures=True)
    bpy.ops.export_scene.gltf(filepath=str(ROOT/'output/campus.glb'),export_format='GLB',
                              use_selection=True,export_yup=True)
    export=dict(pass_=True,axis_forward='-Z',axis_up='Y',apply_unit_scale=True,
                apply_scale_options='FBX_SCALE_UNITS',bake_space_transform=False,
                exported_meshes=original['object_count'],cameras_lights_exported=False)
    export['scale_references_exported']=False
    # Reusable asset is exported at its contact origin; restore the placed instance.
    placement=robot_root.matrix_world.copy()
    robot_root.location=(0,0,0);robot_root.rotation_euler=(0,0,0)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    for obj in build_robot.robot_objects():obj.select_set(True)
    bpy.ops.export_scene.fbx(filepath=str(ROOT/'output/delivery_robot.fbx'),use_selection=True,
        object_types={'MESH','EMPTY'},axis_forward='-Z',axis_up='Y',global_scale=1,
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',bake_space_transform=False,
        use_custom_props=True,bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE')
    bpy.ops.export_scene.gltf(filepath=str(ROOT/'output/delivery_robot.glb'),export_format='GLB',use_selection=True,export_yup=True)
    robot_asset_source=snapshot(required_categories=['ROBOT'],campus_bounds=False,
                                object_filter=lambda o:o.get('actor_id')=='delivery_robot_001')
    if not robot_asset_source['pass_']:raise ValueError('Standalone robot source Mesh failed')
    robot_root.matrix_world=placement;bpy.context.view_layer.update()
    setup(scene,cfg)
    cameras=[]
    for name,direction in [('top',(0,0,1)),('perspective_01',(0.8,-1.0,1.4)),('perspective_02',(-0.9,1.0,1.2))]:
        cameras.append(render(ROOT/f'output/previews/{name}.png',original,direction,cfg))
    cameras.append(render_robot(ROOT/'output/previews/delivery_robot_closeup.png',build_robot.bounds(.45),(.9,-1,.7),cfg))
    neighborhood=build_robot.bounds()
    for i in [0,1]:neighborhood['bbox_min'][i]-=13;neighborhood['bbox_max'][i]+=13
    neighborhood['bbox_max'][2]+=9
    cameras.append(render(ROOT/'output/previews/delivery_robot_on_campus.png',neighborhood,(.2,-1,1.5),cfg))
    # Isolated close-ups expose roof and facade errors hidden by campus-wide views.
    for name,labels in [('building_administration',{'1'}),('building_teaching',{'3','4','5','6','7','8'}),('building_gym',{'10'}),('building_library',{'18'}),('building_exhibition',{'2'})]:
        selected=[o for o in scene.objects if o.type=='MESH' and o.get('map_label') in labels]
        points=[o.matrix_world@v.co for o in selected for v in o.data.vertices]
        bounds=dict(bbox_min=[min(p[i] for p in points) for i in range(3)],bbox_max=[max(p[i] for p in points) for i in range(3)])
        visibility={o:o.hide_render for o in scene.objects if o.type=='MESH'}
        for o in visibility:o.hide_render=o not in selected
        cameras.append(render(ROOT/f'output/previews/{name}.png',bounds,(.8,-1,.65),cfg))
        for o,hidden in visibility.items():o.hide_render=hidden
    mapping=MetricMapping(calibration)
    for name,rect in [('roads_south',(125,645,620,940)),('roads_northeast',(525,375,790,615))]:
        xmin,ymin,xmax,ymax=rect
        points=[mapping.point(p) for p in [(xmin,ymin),(xmax,ymin),(xmin,ymax),(xmax,ymax)]]
        bounds=dict(bbox_min=[min(p[0] for p in points),min(p[1] for p in points),0],
                    bbox_max=[max(p[0] for p in points),max(p[1] for p in points),32])
        cameras.append(render(ROOT/f'output/previews/{name}.png',bounds,(.1,-.35,1.5),cfg))
    for site in delivery_data['sites']:
        points=[site['entry_world_m'],site['approach_world_m'],site['dock_world_m']]
        building=next(b for b in data['buildings']if b['id']==site['building_id'])
        bounds=dict(bbox_min=[min(p[i]for p in points)-3 for i in [0,1]]+[0],
                    bbox_max=[max(p[i]for p in points)+3 for i in [0,1]]+[min(building['height_m'],20)])
        normal=site['outward_world_xy']
        cameras.append(render(ROOT/f"output/previews/delivery_site_{site['id']}.png",bounds,(normal[0],normal[1],1.2),cfg))
    # Fresh factory scene guarantees that the imported FBX stands alone.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1.0
    bpy.ops.import_scene.fbx(filepath=str(ROOT/'output/campus.fbx'),use_custom_props=True)
    imported=snapshot(require_applied=False)
    robot_reimport=build_robot.validate(robot_data)
    delivery_reimport=build_delivery_sites.validate(delivery_data)
    if not delivery_reimport['pass_']:raise ValueError(f'Candidate delivery FBX failed: {delivery_reimport}')
    if not robot_reimport['pass_']:raise ValueError(f'Placed robot FBX failed: {robot_reimport}')
    texture_images=[n.image for m in bpy.data.materials if m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
    if not texture_images or any(len(image.pixels)==0 or not image.has_data for image in texture_images):raise ValueError('FBX facade textures failed to load')
    export['embedded_facade_textures_reimported']=len(texture_images)
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
    cameras.append(render_robot(ROOT/'output/previews/delivery_robot_reimported.png',build_robot.bounds(.45),(.9,-1,.7),cfg))
    # Independently import the origin-centered vehicle asset and inspect hierarchy.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(ROOT/'output/delivery_robot.fbx'),use_custom_props=True)
    asset_imported=snapshot(require_applied=False,required_categories=['ROBOT'],campus_bounds=False)
    asset_metric=build_robot.validate(robot_data,placed=False)
    asset_compare=compare(robot_asset_source,asset_imported,.001)
    if not asset_imported['pass_'] or not asset_metric['pass_'] or not asset_compare['pass_']:
        raise ValueError(f'Standalone robot FBX failed: {asset_metric} {asset_compare}')
    bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=1
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active;space.region_3d.view_location=(0,0,.55)
                space.region_3d.view_distance=2.4;space.region_3d.view_perspective='ORTHO'
                space.region_3d.view_rotation=Vector((-.9,1,-.7)).to_track_quat('-Z','Y')
                space.shading.type='MATERIAL'
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'output/delivery_robot.blend'))
    setup(bpy.context.scene,cfg)
    cameras.append(render_robot(ROOT/'output/previews/delivery_robot_asset.png',build_robot.bounds(.08),(.9,-1,.7),cfg))
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'output/delivery_robot.blend'))
    asset_blend=build_robot.validate(robot_data,placed=False)
    if not asset_blend['pass_'] or any(o.name.startswith('BLDG_') for o in bpy.context.scene.objects):raise ValueError('Standalone blend is not a valid isolated robot')
    robot_validation=dict(pass_=True,placed_source=robot_source,placed_fbx=robot_reimport,standalone_fbx=asset_metric,
        standalone_blend=asset_blend,standalone_comparison=asset_compare,standalone_mesh=public_snapshot(asset_imported),
        design_provenance=robot_data['config']['dimension_provenance'],physics_runtime_tested=False)
    write(ROOT/'output/validation/delivery_robot_validation.json',robot_validation)
    delivery_validation=dict(pass_=delivery_source['pass_'] and delivery_reimport['pass_'],source=delivery_source,reimport=delivery_reimport)
    write(ROOT/'output/validation/delivery_scene_validation.json',delivery_validation)
    write(ROOT/'output/validation/blender_validation.json',dict(blender_version=bpy.app.version_string,
          original_scene=public_snapshot(original),fbx_export=export,
          fbx_reimport=public_snapshot(imported),comparison=comparison,camera_validation=cameras,
          absolute_metric_validation=dict(source=source_metric,reimport=imported_metric),delivery_robot=robot_validation,delivery_sites=delivery_validation,
          pass_=original['pass_'] and imported['pass_'] and comparison['pass_'] and imported_metric['pass_'] and source_metric['pass_']))
    print('CAMPUS_BLENDER_VALIDATION_PASS', flush=True)


if __name__=='__main__':main()
