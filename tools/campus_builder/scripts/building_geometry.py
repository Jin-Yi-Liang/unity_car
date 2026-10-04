"""Closed photo-informed building solids and exportable facade UVs."""
import math
import bpy
import bmesh


def facade_material(feature,root,material_factory,suffix=''):
    a=feature['architecture'];key=feature['map_label'] if (root/f"output/textures/facade_{feature['map_label']}.png").is_file() else 'default'
    key+=suffix
    name='Facade_'+key
    mat=bpy.data.materials.get(name)
    if mat:return mat
    mat=material_factory(name,a['wall_rgb'])
    texture=mat.node_tree.nodes.new('ShaderNodeTexImage')
    texture.image=bpy.data.images.load(str(root/f'output/textures/facade_{key}.png'),check_existing=True)
    texture.extension='REPEAT';texture.interpolation='Linear'
    mat.node_tree.links.new(texture.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    return mat


def finish_building(obj,feature,config,roof_material,end_material=None):
    a=feature['architecture'];eave=a['eave_height_m'];rise=a['roof_rise_m']
    if rise>0:
        bm=bmesh.new();bm.from_mesh(obj.data)
        edges=[e for e in bm.edges if all(abs(v.co.z-eave)<1e-5 for v in e.verts)]
        bmesh.ops.subdivide_edges(bm,edges=edges,cuts=config['building_roof_subdivisions'],use_grid_fill=True)
        top=[v for v in bm.verts if abs(v.co.z-eave)<1e-5]
        # Roof curvature spans the short axis of the footprint's oriented box.
        ux,uy=feature['roof_axis_xy'];values=[v.co.x*ux+v.co.y*uy for v in top]
        low,high=min(values),max(values)
        values=[(x-low)/(high-low) for x in values]
        shape=[1-abs(2*t-1) if a['roof_shape']=='gable' else (2*t-1)**2 for t in values]
        maximum=max(shape)
        for vertex,factor in zip(top,shape):vertex.co.z=eave+rise*factor/maximum
        # Curved roof patches must be triangles; no non-planar export n-gons.
        bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if all(v in top for v in f.verts)])
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free()
        obj.data.update()
    obj.data.materials.append(roof_material)
    if end_material:obj.data.materials.append(end_material)
    uv=obj.data.uv_layers.new(name='FacadeUV')
    pitch=a['window_pitch_m'];story=a['floor_height_m'] or 3.0
    for face in obj.data.polygons:
        is_wall=abs(face.normal.z)<.01
        face.material_index=0 if is_wall else 1
        tangent=(-face.normal.y,face.normal.x)
        horizontal=[obj.data.vertices[i].co.x*tangent[0]+obj.data.vertices[i].co.y*tangent[1] for i in face.vertices]
        low,high=min(horizontal),max(horizontal)
        end_wall=end_material is not None and is_wall and high-low<a['end_wall_max_span_m']
        if end_wall:face.material_index=2
        for loop in face.loop_indices:
            p=obj.data.vertices[obj.data.loops[loop].vertex_index].co
            u=p.x*tangent[0]+p.y*tangent[1]
            uv.data[loop].uv=(((u-low)/max(high-low,.001) if end_wall else u/pitch),p.z/a['total_height_m'] if a['kind']=='administration' else p.z/story) if is_wall else (p.x/8,p.y/8)
    obj['height_provenance']=a['height_status']
    obj['floor_provenance']=a['floor_status'];obj['appearance_provenance']=a['appearance_status']
    obj['modeled_floor_count']=a['floor_count'] or 0;obj['roof_shape']=a['roof_shape']
    obj['measured_height']=a['actual_height_measured'];obj['source_trace_ids']=','.join(a['source_trace_ids'])
