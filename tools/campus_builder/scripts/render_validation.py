"""Fit cameras analytically to all campus bounds; render with CPU Cycles."""
import math
import bpy
from mathutils import Vector
from mathutils import Quaternion


def setup(scene, config):
    scene.render.engine='CYCLES'
    scene.cycles.device='CPU'
    scene.cycles.samples=config['render_samples']
    scene.cycles.use_denoising=False
    scene.render.threads_mode='FIXED'
    scene.render.threads=8
    scene.render.resolution_x,scene.render.resolution_y=config['render_resolution']
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.film_transparent=False
    scene.view_settings.view_transform='Standard'
    scene.world=bpy.data.worlds.new('ValidationWorld')
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(0.72,0.79,0.87,1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=0.65
    light=bpy.data.lights.new('ValidationSun','SUN')
    light.energy=2.2
    light.angle=math.radians(12)
    obj=bpy.data.objects.new('ValidationSun',light)
    scene.collection.objects.link(obj)
    obj.rotation_euler=(math.radians(27),math.radians(-22),math.radians(-30))


def render(path, bounds, direction, config):
    scene=bpy.context.scene
    lo,hi=Vector(bounds['bbox_min']),Vector(bounds['bbox_max'])
    center=(lo+hi)/2
    corners=[Vector((x,y,z)) for x in [lo.x,hi.x] for y in [lo.y,hi.y] for z in [lo.z,hi.z]]
    direction=Vector(direction).normalized()
    camera=bpy.data.cameras.new('ValidationCamera')
    camera.type='ORTHO'
    cam=bpy.data.objects.new('ValidationCamera',camera)
    scene.collection.objects.link(cam)
    # Looking exactly down has no unique roll. Explicit identity keeps image
    # right = +X and image up = +Y, matching the original map rather than 180° roll.
    rotation=Quaternion((1,0,0,0)) if abs(direction.x)+abs(direction.y)<1e-8 else (-direction).to_track_quat('-Z','Y')
    cam.rotation_euler=rotation.to_euler()
    # Project each bbox corner into the camera basis, then solve the frame size.
    inv=rotation.inverted()
    projected=[inv@(p-center) for p in corners]
    horizontal=max(p.x for p in projected)-min(p.x for p in projected)
    vertical=max(p.y for p in projected)-min(p.y for p in projected)
    aspect=scene.render.resolution_x/scene.render.resolution_y
    camera.ortho_scale=max(vertical,horizontal/aspect)*1.13
    distance=(hi-lo).length*1.5
    cam.location=center+direction*distance
    camera.clip_start=0.01
    camera.clip_end=distance*4
    scene.camera=cam
    scene.render.filepath=str(path)
    bpy.ops.render.render(write_still=True)
    # Verify projected bounds have a real framing margin.
    from bpy_extras.object_utils import world_to_camera_view
    projected=[world_to_camera_view(scene,cam,p) for p in corners]
    framed=all(0.001<=p.x<=0.999 and 0.001<=p.y<=0.999 and p.z>0 for p in projected)
    map_orientation=None
    if abs(direction.x)+abs(direction.y)<1e-8:
        origin=world_to_camera_view(scene,cam,center)
        east=world_to_camera_view(scene,cam,center+Vector((1,0,0)))
        north=world_to_camera_view(scene,cam,center+Vector((0,1,0)))
        map_orientation=east.x>origin.x and north.y>origin.y
        if not map_orientation:raise ValueError('Overhead camera axes do not match source map')
    result=dict(path=str(path),camera_location=list(cam.location),ortho_scale=camera.ortho_scale,
                all_bbox_corners_in_frame=framed,map_orientation_correct=map_orientation)
    bpy.data.objects.remove(cam,do_unlink=True)
    if not framed:raise ValueError(f'Camera does not frame campus: {path}')
    return result
