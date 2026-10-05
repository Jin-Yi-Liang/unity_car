"""Closed low-poly robot, useful wheel pivots, explicit axes and metric checks."""
import math
import bpy
import bmesh
from mathutils import Matrix, Vector

ROOT_NAME='DeliveryRobot_ROOT'


def build(data, material_factory):
    c=data['config'];w,l,h=c['width_m'],c['length_m'],c['height_m']
    coll=bpy.data.collections.new('DeliveryRobot');bpy.context.scene.collection.children.link(coll)
    mats={key:material_factory('Robot_'+key,value) for key,value in c['colors'].items()}
    def empty(name,parent=None,position=(0,0,0)):
        obj=bpy.data.objects.new(name,None);coll.objects.link(obj);obj.parent=parent;obj.location=position
        obj.empty_display_type='PLAIN_AXES';obj.empty_display_size=.12
        obj['actor_id']='delivery_robot_001';return obj
    root=empty(ROOT_NAME)
    root['actor_type']='delivery_robot';root['mobility']='dynamic_actor';root['local_forward']='-Y';root['local_up']='+Z'
    root['length_m']=l;root['width_m']=w;root['height_m']=h
    root['root_origin']='ground contact center';root['dimension_provenance']=c['dimension_provenance']
    def mesh(name,bm,parent,position,material):
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        geo=bpy.data.meshes.new(name+'_Mesh');bm.to_mesh(geo);bm.free();geo.update()
        obj=bpy.data.objects.new(name,geo);coll.objects.link(obj);obj.parent=parent;obj.location=position
        obj.data.materials.append(mats[material]);obj['actor_id']='delivery_robot_001';obj['part_role']=name.removeprefix('ROBOT_')
        obj['physics_hint']='Visual part; configure compound colliders on robot root in engine'
        return obj
    def cube(name,size,position,material,parent=root,bevel=0):
        bm=bmesh.new();bmesh.ops.create_cube(bm,size=1)
        for v in bm.verts:
            for i in range(3):v.co[i]*=size[i]
        if bevel:
            bmesh.ops.bevel(bm,geom=list(bm.edges),offset=min(bevel,min(size)/4),segments=2,affect='EDGES')
        return mesh('ROBOT_'+name,bm,parent,position,material)
    def cylinder(name,radius,depth,position,material,parent=root,axis='Z'):
        bm=bmesh.new();bmesh.ops.create_cone(bm,cap_ends=True,cap_tris=False,segments=24,radius1=radius,radius2=radius,depth=depth)
        if axis=='X':bmesh.ops.transform(bm,matrix=Matrix.Rotation(math.pi/2,4,'Y'),verts=list(bm.verts))
        return mesh('ROBOT_'+name,bm,parent,position,material)
    cube('Chassis',(w*.85,l*.86,.17),(0,0,c['chassis_clearance_m']+.085),'chassis',bevel=.025)
    cube('CargoBody',(w*.875,l*.8833333333,h*.5727272727),(0,0,h*.5772727273),'shell',bevel=.045)
    cube('Lid',(w*.88,l*.89,.045),(0,0,.946*h/1.1),'accent',bevel=.012)
    for sign,side in [(-1,'Left'),(1,'Right')]:
        cube('Door_'+side,(.012,l*.73,h*.44),(sign*w*.444,0,h*.58),'shell',bevel=.003)
        cube('Stripe_'+side,(.018,l*.78,.065),(sign*w*.452,0,h*.43),'accent',bevel=.003)
        cube('Handle_'+side,(.025,.11,.035),(sign*w*.46,-l*.22,h*.7),'chassis',bevel=.006)
        for j,y in enumerate([-.21,0,.21]):
            cube(f'Vent_{side}_{j}',(.016,.10,.018),(sign*w*.45,y,h*.79),'chassis',bevel=.002)
    for sign,end in [(-1,'Front'),(1,'Rear')]:
        cube('Bumper_'+end,(w*.925,.08,.13),(0,sign*(l/2-.04),.31),'chassis',bevel=.018)
        for signx,side in [(-1,'Left'),(1,'Right')]:
            cube('Light_'+end+'_'+side,(.12,.02,.035),(signx*w*.30,sign*l*.451,.42),'headlight' if sign<0 else 'taillight',bevel=.006)
    cube('FrontDisplay',(.35,.016,.14),(0,-l*.449,.78),'glass',bevel=.008)
    cube('DisplayStatus',(.19,.019,.018),(0,-l*.455,.78),'headlight',bevel=.002)
    cylinder('LidarBase',.105,.03,(0,0,h-.135),'chassis')
    cylinder('Lidar',.085,.102,(0,0,h-.069),'glass')
    cylinder('LidarCap',.09,.018,(0,0,h-.009),'accent')
    track=w-c['wheel_width_m']-2*c['hub_protrusion_m'];radius=c['wheel_radius_m']
    for sx,side in [(-1,'L'),(1,'R')]:
        for sy,end in [(-1,'F'),(1,'R')]:
            key=end+side;wheel=empty('WheelPivot_'+key,root,(sx*track/2,sy*c['wheelbase_m']/2,radius))
            wheel['joint_role']='wheel';wheel['rotation_axis']='+X';wheel['radius_m']=radius
            cylinder('Tire_'+key,radius,c['wheel_width_m'],(0,0,0),'tire',wheel,'X')
            cylinder('Hub_'+key,radius*.55,.012,(sx*(c['wheel_width_m']/2+c['hub_protrusion_m']-.006),0,0),'hub',wheel,'X')
    for name,position in [('BaseLink',(0,0,0)),('ForwardAxis',(0,-l*.65,0)),('LidarMount',(0,0,h)),('CameraMount',(0,-l*.46,.82))]:
        marker=empty(name,root,position);marker['joint_role']='reference_only';marker.hide_render=True
    root.location=data['pose']['position_m'];root.rotation_euler.z=data['pose']['yaw_rad']
    bpy.context.view_layer.update()
    return root,coll


def robot_objects():
    return [o for o in bpy.context.scene.objects if o.get('actor_id')=='delivery_robot_001']


def validate(data,placed=True):
    root=bpy.data.objects.get(ROOT_NAME);errors=[]
    if root is None:return dict(pass_=False,errors=['Missing robot root'])
    bpy.context.view_layer.update();inverse=root.matrix_world.inverted()
    meshes=[o for o in robot_objects() if o.type=='MESH']
    points=[inverse@(o.matrix_world@v.co) for o in meshes for v in o.data.vertices]
    lo=[min(p[i] for p in points) for i in range(3)];hi=[max(p[i] for p in points) for i in range(3)]
    dims=[hi[i]-lo[i] for i in range(3)];c=data['config'];expected=[c['width_m'],c['length_m'],c['height_m']]
    if any(abs(a-b)>.001 for a,b in zip(dims,expected)):errors.append('Robot dimensions differ from configured metres')
    if any(abs(lo[i]+expected[i]/2)>.001 or abs(hi[i]-expected[i]/2)>.001 for i in [0,1]):errors.append('Root is not centered on the footprint')
    if abs(lo[2])>.001:errors.append('Root is not on the wheel contact plane')
    wheel_checks=[]
    for key in ['FL','FR','RL','RR']:
        wheel=bpy.data.objects.get('WheelPivot_'+key);tire=bpy.data.objects.get('ROBOT_Tire_'+key)
        ok=wheel is not None and tire is not None and tire.parent==wheel and wheel.parent==root
        if ok:
            center=inverse@wheel.matrix_world.translation
            target=Vector(((-1 if key[1]=='L' else 1)*(c['width_m']-c['wheel_width_m']-2*c['hub_protrusion_m'])/2,(-1 if key[0]=='F' else 1)*c['wheelbase_m']/2,c['wheel_radius_m']))
            axis=(inverse.to_3x3()@wheel.matrix_world.to_3x3()@Vector((1,0,0))).normalized()
            ok=(center-target).length<.001 and (axis-Vector((1,0,0))).length<.001
            ok=ok and wheel.get('rotation_axis')=='+X'
        wheel_checks.append(dict(wheel=key,pass_=ok))
        if not ok:errors.append('Wheel pivot/axis mismatch: '+key)
    front=bpy.data.objects.get('ForwardAxis')
    if front is None or (inverse@front.matrix_world.translation-Vector((0,-c['length_m']*.65,0))).length>.001:
        errors.append('Forward axis marker mismatch')
    target=Vector(data['pose']['position_m'] if placed else (0,0,0))
    if (root.matrix_world.translation-target).length>.001:errors.append('Robot root pose mismatch')
    world_front=root.matrix_world.to_3x3()@Vector((0,-1,0));expected_front=Vector(data['pose']['forward_world'] if placed else (0,-1,0))
    if (world_front.normalized()-expected_front).length>.001:errors.append('Robot forward direction changed')
    contacts=[min((o.matrix_world@v.co).z for v in o.data.vertices) for o in meshes if o.name.startswith('ROBOT_Tire_')]
    ground=data['pose']['position_m'][2] if placed else 0
    if any(abs(z-ground)>.001 for z in contacts):errors.append('Wheel does not meet road/ground surface')
    if root.get('actor_type')!='delivery_robot':errors.append('Actor metadata lost')
    return dict(pass_=not errors,errors=errors,mesh_count=len(meshes),measured_dimensions_xyz_m=dims,expected_dimensions_xyz_m=expected,
        root_position_m=list(root.matrix_world.translation),forward_world=list(world_front),wheel_contacts_z_m=contacts,
        expected_road_top_m=ground,wheel_pivots=wheel_checks,local_bbox_min=lo,local_bbox_max=hi,placement=data['navigation'] if placed else None)


def bounds(padding=0):
    points=[o.matrix_world@v.co for o in robot_objects() if o.type=='MESH' for v in o.data.vertices]
    return dict(bbox_min=[min(p[i] for p in points)-padding for i in range(3)],bbox_max=[max(p[i] for p in points)+padding for i in range(3)])
