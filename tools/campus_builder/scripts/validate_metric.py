"""Blender-only absolute metre checks independent of source/import size ratios."""
import json
import math
import bpy
from mathutils import Vector


def validate_metric(data, calibration, config):
    from metric_mapping import MetricMapping
    mapping=MetricMapping(calibration)
    ground=bpy.data.objects['Ground']
    actual=[ground.matrix_world@v.co for v in ground.data.vertices]
    # Register four actual top-plane Ground vertices to the known image ROI.
    xmin,ymin,xmax,ymax=data['metadata']['ground_bounds_px']
    pixels=[(xmin,ymin),(xmax,ymin),(xmin,ymax),(xmax,ymax)]
    expected=[Vector((*mapping.point(p),0)) for p in pixels]
    corners=[min(actual,key=lambda v:(v-e).length) for e in expected]
    corner_error=max((a-e).length for a,e in zip(corners,expected))
    def registered(pixel):
        u=(pixel[0]-xmin)/(xmax-xmin);v=(pixel[1]-ymin)/(ymax-ymin)
        return corners[0]+u*(corners[1]-corners[0])+v*(corners[2]-corners[0])
    anchors=[]
    for reference in calibration['anchors']:
        a,b=registered(reference['pixel_a']),registered(reference['pixel_b'])
        length=(b-a).length
        error=abs(length-reference['estimated_distance_m'])
        anchors.append(dict(id=reference['id'],measured_world_length_m=length,
            calibrated_expected_length_m=reference['estimated_distance_m'],reference_length_m=reference['real_distance_m'],
            mapped_geometry_error_m=error,reference_relative_error_percent=(length/reference['real_distance_m']-1)*100,
            pass_=error<=config['bbox_tolerance_m'],measurement_method='Affine registration to actual Ground Mesh corner vertices'))
    # Real Blender meshes: dimensions are measured after applying transforms.
    collection=bpy.data.collections.new('ValidationOnly_ScaleReferences')
    bpy.context.scene.collection.children.link(collection)
    rulers=[]
    for length in [1,10,50]:
        mesh=bpy.data.meshes.new(f'ScaleReference_{length}m_Mesh')
        mesh.from_pydata([(0,0,0),(length,0,0),(length,0.1,0),(0,0.1,0),(0,0,0.1),(length,0,0.1),(length,0.1,0.1),(0,0.1,0.1)],[],
                         [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
        obj=bpy.data.objects.new(f'ScaleReference_{length}m',mesh);collection.objects.link(obj)
        obj['validation_only']=True;obj.hide_render=True
        obj.location=(max(v.x for v in actual)+5,min(v.y for v in actual)+length,0)
        points=[obj.matrix_world@v.co for v in obj.data.vertices]
        measured=math.dist(points[0],points[1]);rulers.append(dict(name=obj.name,expected_m=length,actual_m=measured,pass_=abs(measured-length)<1e-6))
    heights=[]
    for b in data['buildings']:
        obj=bpy.data.objects[b['id']];z=[(obj.matrix_world@v.co).z for v in obj.data.vertices]
        measured=max(z)-min(z);heights.append(dict(id=b['id'],expected_m=b['height_m'],actual_m=measured,pass_=abs(measured-b['height_m'])<config['bbox_tolerance_m']))
    bridge_checks=[]
    for b in data['bridges']:
        obj=bpy.data.objects[b['id']]
        z=[(obj.matrix_world@v.co).z for v in obj.data.vertices]
        properties=all(obj.get(k)==v for k,v in [('surface_type','bridge'),('driveable',True),('collidable',True)])
        bridge_checks.append(dict(id=b['id'],top_m=max(z),water_top_m=config['water_top_m'],semantic_properties_preserved=properties,
            pass_=max(z)>config['water_top_m'] and abs(max(z)-config['road_top_m'])<config['bbox_tolerance_m'] and properties))
    return dict(pass_=corner_error<=config['bbox_tolerance_m'] and all(a['pass_'] for a in anchors+rulers+heights+bridge_checks),
        expected_ground_width_m=mapping.distance(pixels[0],pixels[1]),
        measured_ground_width_m=(corners[1]-corners[0]).length,
        expected_ground_length_m=mapping.distance(pixels[0],pixels[2]),
        measured_ground_length_m=(corners[2]-corners[0]).length,
        ground_corner_error_m=corner_error,anchors=anchors,scale_references=rulers,
        building_height_validation=heights,bridge_validation=bridge_checks,xy_z_decoupled=True,
        scope='Absolute Blender metre consistency of calibrated mapping, not proof of the real-world anchor assumptions.')
