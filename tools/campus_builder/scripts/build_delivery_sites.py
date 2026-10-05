"""Blender formal candidate-access geometry and independently measured semantics."""
import math
import bpy
from mathutils import Vector


def build(data,collections,solid,material):
    access_material=material('CandidateAccess',(0.58,0.43,0.25))
    bay_material=material('DeliveryBay',(0.015,0.48,0.55))
    portal_material=material('CandidateEntrance',(0.06,0.20,0.27))
    for category,coll,mat in [('access_paths','AccessPaths',access_material),('delivery_bays','DeliverySites',bay_material)]:
        for feature in data[category]:
            obj=solid(feature,collections[coll],mat,feature['bottom_m'],feature['top_m'])
            obj['site_id']=feature['site_id'];obj['real_world_confirmed']=False
    config=data['config']
    for site in data['sites']:
        for prefix,position in [('ENTRY',site['entry_world_m']),('HANDOFF',site['approach_world_m']),('STOP',site['dock_world_m'])]:
            obj=bpy.data.objects.new(prefix+'_'+site['id'],None);collections['DeliverySites'].objects.link(obj)
            obj.location=position;obj.empty_display_size=.5;obj.empty_display_type='PLAIN_AXES'
            obj['site_id']=site['id'];obj['source_trace_id']=site['source_trace_id'];obj['real_world_confirmed']=False
            obj['semantic_role']=prefix.lower();obj['provenance']=site['provenance']
        normal=site['outward_world_xy'];side=(-normal[1],normal[0]);entry=site['entry_world_m']
        center=[entry[i]+normal[i]*config['portal_offset_m']for i in [0,1]]
        width=config['portal_width_m'];height=config['portal_height_m'];depth=config['portal_depth_m']
        vertices=[];faces=[]
        # Three separated closed boxes make a visual candidate portal. It is not
        # a wall opening, survey claim or new collision obstacle.
        for x0,x1,z0,z1 in [(-width/2,-width/2+.12,0,height-.18),(width/2-.12,width/2,0,height-.18),(-width/2,width/2,height-.16,height)]:
            offset=len(vertices)
            for z in [z0,z1]:
                for x,y in [(x0,-depth/2),(x1,-depth/2),(x1,depth/2),(x0,depth/2)]:
                    vertices.append((center[0]+side[0]*x+normal[0]*y,center[1]+side[1]*x+normal[1]*y,z))
            faces.extend(tuple(offset+i for i in face)for face in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
        # The basis (side,normal) can be mirrored; recalculate normals explicitly.
        import bmesh
        mesh=bpy.data.meshes.new('CandidatePortal_'+site['id']);mesh.from_pydata(vertices,[],faces);mesh.update()
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
        obj=bpy.data.objects.new('ENTRANCE_'+site['id'],mesh);collections['DeliverySites'].objects.link(obj);mesh.materials.append(portal_material)
        obj['site_id']=site['id'];obj['collidable']=False;obj['surface_type']='candidate_entrance_marker'
        obj['real_world_confirmed']=False;obj['provenance']=site['provenance']


def validate(data,tolerance=.01):
    bpy.context.view_layer.update()
    checks=[]
    for site in data['sites']:
        errors=[]
        for prefix,position in [('ENTRY',site['entry_world_m']),('HANDOFF',site['approach_world_m']),('STOP',site['dock_world_m'])]:
            obj=bpy.data.objects.get(prefix+'_'+site['id'])
            if obj is None:errors.append('Missing '+prefix);continue
            if (obj.matrix_world.translation-Vector(position)).length>tolerance:errors.append(prefix+' position changed')
            if obj.get('site_id')!=site['id'] or obj.get('real_world_confirmed')!=False:errors.append(prefix+' semantics changed')
        for identifier,feature in [('ACCESS_',next(v for v in data['access_paths']if v['site_id']==site['id'])),('DOCK_',next(v for v in data['delivery_bays']if v['site_id']==site['id']))]:
            obj=bpy.data.objects.get(identifier+site['id'])
            if obj is None:errors.append('Missing '+identifier);continue
            points=[obj.matrix_world@v.co for v in obj.data.vertices]
            if abs(max(v.z for v in points)-feature['top_m'])>tolerance:errors.append(identifier+' top changed')
            if obj.get('collidable')!=feature['collidable'] or obj.get('driveable')!=False:errors.append(identifier+' surface semantics changed')
        bay=bpy.data.objects.get('DOCK_'+site['id'])
        if bay:
            points=[bay.matrix_world@v.co for v in bay.data.vertices];center=Vector(site['dock_world_m']);yaw=site['dock_yaw_rad']
            local=[(math.cos(yaw)*(v.x-center.x)+math.sin(yaw)*(v.y-center.y),-math.sin(yaw)*(v.x-center.x)+math.cos(yaw)*(v.y-center.y))for v in points]
            measured=[max(p[i]for p in local)-min(p[i]for p in local)for i in [0,1]]
            if abs(measured[0]-site['bay_width_m'])>tolerance or abs(measured[1]-site['bay_length_m'])>tolerance:errors.append('Bay absolute dimensions changed')
        portal=bpy.data.objects.get('ENTRANCE_'+site['id'])
        if portal is None or portal.get('collidable')!=False or portal.get('real_world_confirmed')!=False:errors.append('Candidate portal semantics changed')
        checks.append(dict(site_id=site['id'],pass_=not errors,errors=errors))
    return dict(pass_=all(v['pass_']for v in checks),sites=checks,scope='Absolute marker positions, bay dimensions and assumptions survive export; real door locations and traffic access are not certified.')
