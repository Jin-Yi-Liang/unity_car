"""Shared checks run on the source scene and a fresh FBX import."""
import math
import bpy
import bmesh
from mathutils import Vector


def snapshot(require_applied=True):
    objects={}
    errors=[]
    all_points=[]
    category_counts={}
    for obj in sorted(bpy.context.scene.objects, key=lambda o:o.name):
        if obj.get('validation_only'):continue
        if obj.type!='MESH':
            continue
        coords=[tuple(obj.matrix_world@v.co) for v in obj.data.vertices]
        if not coords or not obj.data.polygons:
            errors.append(f'{obj.name}: empty mesh')
            continue
        if any(not math.isfinite(c) or abs(c)>10000 for p in coords for c in p):
            errors.append(f'{obj.name}: invalid/huge coordinate')
        if any(v<=0 for v in obj.scale):
            errors.append(f'{obj.name}: nonpositive scale')
        lo=[min(p[i] for p in coords) for i in range(3)]
        hi=[max(p[i] for p in coords) for i in range(3)]
        if require_applied and any(abs(v-1)>1e-5 for v in obj.scale):
            errors.append(f'{obj.name}: unapplied scale')
        if require_applied and any(abs(v)>1e-4 for v in obj.rotation_euler):
            errors.append(f'{obj.name}: unexpected rotation')
        if obj.modifiers:
            errors.append(f'{obj.name}: unapplied modifiers')
        bm=bmesh.new(); bm.from_mesh(obj.data)
        nonmanifold=sum(not e.is_manifold for e in bm.edges)
        degenerate=sum(f.calc_area()<1e-12 for f in bm.faces)
        normals=sum(not all(math.isfinite(v) for v in f.normal) or f.normal.length<0.9 for f in bm.faces)
        signed_volume=bm.calc_volume(signed=True)
        bm.free()
        # FBX can split vertices at material/smoothing boundaries. Weld only in
        # the temporary validation mesh; do not mutate the imported artifact.
        if nonmanifold:
            bm=bmesh.new(); bm.from_mesh(obj.data)
            bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-6)
            nonmanifold=sum(not e.is_manifold for e in bm.edges)
            bm.free()
        if nonmanifold or degenerate or normals:
            errors.append(f'{obj.name}: nonmanifold={nonmanifold}, degenerate={degenerate}, invalid_normals={normals}')
        if signed_volume<=0:
            errors.append(f'{obj.name}: inward normals or zero signed volume')
        category='Ground' if obj.name=='Ground' else obj.name.split('_')[0]
        category_counts[category]=category_counts.get(category,0)+1
        if category=='BLDG' and hi[2]-lo[2]<=0:
            errors.append(f'{obj.name}: nonpositive building height')
        if category=='ROAD' and (lo[2]<-0.01 or hi[2]>0.2):
            errors.append(f'{obj.name}: road not near ground')
        objects[obj.name]=dict(vertices=len(coords), faces=len(obj.data.polygons),
            bbox_min=lo,bbox_max=hi, nonmanifold_edges=nonmanifold,
            degenerate_faces=degenerate, invalid_normals=normals,
            signed_volume_m3=signed_volume,
            material_count=len(obj.data.materials), points=coords)
        all_points+=coords
    for required in ['Ground','BLDG','ROAD']:
        if not category_counts.get(required):
            errors.append(f'Missing {required}')
    if not all_points:
        raise ValueError('No campus mesh geometry')
    lo=[min(p[i] for p in all_points) for i in range(3)]
    hi=[max(p[i] for p in all_points) for i in range(3)]
    dimensions=[hi[i]-lo[i] for i in range(3)]
    center=[(hi[i]+lo[i])/2 for i in range(3)]
    if max(abs(center[0]),abs(center[1]))>1:
        errors.append('Campus horizontal origin is not centered')
    if not (1<dimensions[0]<3000 and 1<dimensions[1]<3000 and 0<dimensions[2]<300):
        errors.append('Unexpected campus dimensions')
    return dict(pass_=not errors, errors=errors, object_count=len(objects),
        category_counts=category_counts, total_vertices=sum(o['vertices'] for o in objects.values()),
        total_faces=sum(o['faces'] for o in objects.values()), bbox_min=lo,bbox_max=hi,
        dimensions_m=dimensions, center_m=center, objects=objects)


def public_snapshot(data):
    result=dict(data)
    result['pass']=result.pop('pass_')
    result['objects']={name:{k:v for k,v in obj.items() if k!='points'} for name,obj in data['objects'].items()}
    return result


def compare(original, imported, tolerance):
    from mathutils.kdtree import KDTree
    errors=[]
    if set(original['objects'])!=set(imported['objects']):
        errors.append('Object identities differ after FBX import')
    max_bbox_delta=max(abs(original[key][i]-imported[key][i])
                       for key in ['bbox_min','bbox_max'] for i in range(3))
    max_vertex_delta=0
    for name in set(original['objects'])&set(imported['objects']):
        a,b=original['objects'][name],imported['objects'][name]
        delta=max(abs(a[key][i]-b[key][i]) for key in ['bbox_min','bbox_max'] for i in range(3))
        max_bbox_delta=max(max_bbox_delta,delta)
        for first,second in [(a,b),(b,a)]:
            tree=KDTree(len(first['points']))
            for i,p in enumerate(first['points']):tree.insert(p,i)
            tree.balance()
            max_vertex_delta=max(max_vertex_delta,max(tree.find(p)[2] for p in second['points']))
        if a['material_count']!=b['material_count']:
            errors.append(f'{name}: material slot count changed')
    if max_bbox_delta>tolerance or max_vertex_delta>tolerance:
        errors.append('FBX geometry changed beyond tolerance')
    ratios=[imported['dimensions_m'][i]/original['dimensions_m'][i] for i in range(3)]
    if any(abs(r-1)>0.001 for r in ratios):errors.append('FBX scale/orientation changed')
    return dict(pass_=not errors,errors=errors,max_bbox_delta_m=max_bbox_delta,
                max_vertex_delta_m=max_vertex_delta, dimension_ratios=ratios,
                direction_check='Named object world-space bounds and bidirectional vertices match; Z remains height')
