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
    inset=a.get('facade_base_inset_fraction',0)
    outline=feature['polygon']
    # Homothety towards an interior center stays inside a convex footprint.
    center=(sum(x for x,y in outline)/len(outline),sum(y for x,y in outline)/len(outline))
    if inset:
        signs=[(q[0]-p[0])*(r[1]-q[1])-(q[1]-p[1])*(r[0]-q[0])
               for p,q,r in zip(outline,outline[1:]+outline[:1],outline[2:]+outline[:2])]
        if min(signs)<-1e-5 and max(signs)>1e-5:raise ValueError('Taper requires a convex traced envelope')
        for vertex in obj.data.vertices:
            if abs(vertex.co.z)<1e-5:
                vertex.co.x=center[0]+(vertex.co.x-center[0])*(1-inset)
                vertex.co.y=center[1]+(vertex.co.y-center[1])*(1-inset)
        obj.data.update()
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
    segments=[]
    for ring in [feature['polygon'],*feature.get('holes',[])]:
        distance=0
        for p,q in zip(ring,ring[1:]+ring[:1]):
            length=math.dist(p,q)
            segments.append((p,q,length,distance));distance+=length
    roof_texture=config.get('roof_texture_root')
    # Material images use the same simple Principled BSDF path as facades.
    if a.get('roof_surface')=='standing_seam' and roof_texture:
        if not any(n.type=='TEX_IMAGE' for n in roof_material.node_tree.nodes):
            node=roof_material.node_tree.nodes.new('ShaderNodeTexImage')
            node.image=bpy.data.images.load(str(roof_texture/f"roof_{feature['map_label']}.png"),check_existing=True)
            roof_material.node_tree.links.new(node.outputs['Color'],roof_material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    def original_xy(p):
        factor=1-inset*max(0,1-p.z/eave)
        return (center[0]+(p.x-center[0])/factor,center[1]+(p.y-center[1])/factor)
    def segment_distance(segment,point):
        p,q,length,offset=segment
        t=max(0,min(1,((point[0]-p[0])*(q[0]-p[0])+(point[1]-p[1])*(q[1]-p[1]))/length**2))
        return math.dist(point,(p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
    for face in obj.data.polygons:
        heights=[obj.data.vertices[i].co.z for i in face.vertices]
        is_wall=min(heights)<1e-5 and max(heights)>1e-5
        face.material_index=0 if is_wall else 1
        tangent=(-face.normal.y,face.normal.x)
        horizontal=[obj.data.vertices[i].co.x*tangent[0]+obj.data.vertices[i].co.y*tangent[1] for i in face.vertices]
        low,high=min(horizontal),max(horizontal)
        end_wall=end_material is not None and is_wall and high-low<a['end_wall_max_span_m']
        if end_wall:face.material_index=2
        midpoint=(sum(original_xy(obj.data.vertices[i].co)[0] for i in face.vertices)/len(face.vertices),
                  sum(original_xy(obj.data.vertices[i].co)[1] for i in face.vertices)/len(face.vertices))
        segment=min(segments,key=lambda s:segment_distance(s,midpoint)) if is_wall else None
        for loop in face.loop_indices:
            p=obj.data.vertices[obj.data.loops[loop].vertex_index].co
            u=p.x*tangent[0]+p.y*tangent[1]
            if is_wall:
                start,end,length,offset=segment;xy=original_xy(p)
                along=((xy[0]-start[0])*(end[0]-start[0])+(xy[1]-start[1])*(end[1]-start[1]))/length
                full_height=a['kind']=='administration' or a.get('facade_uv_mode')=='full_height'
                uv.data[loop].uv=((u-low)/max(high-low,.001) if end_wall else (offset+along)/pitch,p.z/a['total_height_m'] if full_height else p.z/story)
            else:
                ux,uy=feature['roof_axis_xy'];seam=a.get('roof_seam_pitch_m',8)
                uv.data[loop].uv=((p.x*ux+p.y*uy)/seam,(-p.x*uy+p.y*ux)/8)
    obj['height_provenance']=a['height_status']
    obj['floor_provenance']=a['floor_status'];obj['appearance_provenance']=a['appearance_status']
    obj['modeled_floor_count']=a['floor_count'] or 0;obj['roof_shape']=a['roof_shape']
    obj['measured_height']=a['actual_height_measured'];obj['source_trace_ids']=','.join(a['source_trace_ids'])
    obj['facade_base_inset_fraction']=inset
    obj['facade_geometry_provenance']=a.get('facade_geometry_provenance','Source polygon extrusion')
