"""Source CU3 camera tracks and shot markers for the observed older PC layouts."""
import math
import bpy
from mathutils import Matrix
from .cu3 import FormatError
from .cinematic import read_cameras
from .blender_import import C, row_matrix, rotations, action_bag, curve


def import_cameras(cut, scene):
    data = read_cameras(cut)
    # Validate every track and optical sample before creating Blender data.
    samples = []
    basis = Matrix.Rotation(math.pi, 4, 'Y')
    for record in data['cameras']:
        anim = record['animation']
        if anim and (anim.nodes != 1 or anim.curves not in (6, 7)):
            raise FormatError('Unsupported camera animation channel layout')
        matrices, lenses = [], []
        for frame in range(cut.frames if anim else 1):
            if anim:
                values = anim.sample(frame)[0]
                matrix = rotations(anim, frame)[0].to_matrix().to_4x4()
                matrix.translation = (values[0], values[1], -values[2])
                lens = values[6] if anim.curves == 7 else record['lens_mm']
            else:
                matrix = row_matrix(cut.matrices[record['matrix_index']])
                lens = record['lens_mm']
            if not math.isfinite(lens) or not 0 < lens < 10000 or not all(math.isfinite(v) for row in matrix for v in row):
                raise FormatError('Invalid camera pose or focal length')
            matrices.append(C @ matrix @ basis)
            lenses.append(lens)
        samples.append((record, matrices, lenses))
    collection = bpy.data.collections.new(cut.name + ' / source cameras')
    scene.collection.children.link(collection)
    cameras = []
    for record, matrices, lenses in samples:
        camera = bpy.data.cameras.new(f'CU3 camera {record["index"]}')
        camera.sensor_fit = 'HORIZONTAL'
        camera.sensor_width = record['film_width_inches'] * 25.4
        camera.sensor_height = record['film_height_inches'] * 25.4
        camera.lens = lenses[0]
        camera.clip_start, camera.clip_end = .001, 10000
        obj = bpy.data.objects.new(camera.name, camera)
        collection.objects.link(obj)
        obj.matrix_world = matrices[0]
        obj.rotation_mode = 'QUATERNION'
        if len(matrices) > 1:
            rows, previous = [], None
            for matrix in matrices:
                location, quaternion, scale = matrix.decompose()
                if previous is not None and previous.dot(quaternion) < 0:
                    quaternion.negate()
                previous = quaternion.copy()
                rows.append((location, quaternion, scale))
            action = bpy.data.actions.new(obj.name + ' / source motion')
            slot, bag = action_bag(action, obj)
            for field, count, value in [('location',3,0),('rotation_quaternion',4,1),('scale',3,2)]:
                for axis in range(count):
                    curve(bag, field, axis, [row[value][axis] for row in rows])
            obj.animation_data_create()
            obj.animation_data.action, obj.animation_data.action_slot = action, slot
            action = bpy.data.actions.new(obj.name + ' / source lens')
            slot, bag = action_bag(action, camera)
            curve(bag, 'lens', 0, lenses)
            camera.animation_data_create()
            camera.animation_data.action, camera.animation_data.action_slot = action, slot
        obj['cu3_camera_index'] = record['index']
        obj['cu3_camera_flags'] = record['flags']
        cameras.append(obj)
    for time, index in zip(data['shots']['times'], data['shots']['values']):
        scene.timeline_markers.new(f'Source shot {index}', frame=max(1, round(time))).camera = cameras[index]
    if cameras:
        scene.camera = cameras[data['shots']['values'][0]]
    scene.render.resolution_x = 1280
    scene.render.resolution_y = round(1280 / data['aspect'])
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    return {'cameras':len(cameras), 'shots':len(data['shots']['values']), 'aspect':data['aspect'],
            'limitations':'Source camera convention; focus/exposure effects and frame-for-frame game comparison remain incomplete.'}
