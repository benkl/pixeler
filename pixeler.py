"""Pixeler: a live image-to-geometry modifier for Blender 5+."""

import bpy
from bpy.props import PointerProperty
from bpy.types import Operator, Panel, PropertyGroup

bl_info = {
    "name": "Pixeler - Pixels to Geometry",
    "author": "_benkl",
    "version": (0, 3, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Pixeler",
    "description": "Turn an image into live, editable pixel geometry",
    "category": "Object",
}

GROUP_NAME = "Pixeler Geometry"
MATERIAL_NAME = "Pixeler Surface"
COLOR_ATTRIBUTE = "pixeler_color"
ALPHA_ATTRIBUTE = "pixeler_alpha"


class PixelerSettings(PropertyGroup):
    image: PointerProperty(name="Image", type=bpy.types.Image)


def socket(group, name, direction, socket_type, default=None, minimum=None):
    item = group.interface.new_socket(name=name, in_out=direction, socket_type=socket_type)
    if default is not None:
        item.default_value = default
    if minimum is not None:
        item.min_value = minimum
    return item


def new_node(group, node_type, label):
    node = group.nodes.new(node_type)
    node.label = label
    return node


def create_material():
    material = bpy.data.materials.new(MATERIAL_NAME)
    material.use_nodes = True
    material.surface_render_method = 'BLENDED'
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    shader = next(node for node in nodes if node.type == 'BSDF_PRINCIPLED')

    color = nodes.new('ShaderNodeAttribute')
    color.attribute_name = COLOR_ATTRIBUTE
    links.new(color.outputs['Color'], shader.inputs['Base Color'])
    alpha = nodes.new('ShaderNodeAttribute')
    alpha.attribute_name = ALPHA_ATTRIBUTE
    links.new(alpha.outputs['Fac'], shader.inputs['Alpha'])
    return material


def create_group(material):
    group = bpy.data.node_groups.new(GROUP_NAME, 'GeometryNodeTree')
    group.is_modifier = True
    socket(group, 'Geometry', 'INPUT', 'NodeSocketGeometry')
    socket(group, 'Geometry', 'OUTPUT', 'NodeSocketGeometry')
    socket(group, 'Image', 'INPUT', 'NodeSocketImage')
    socket(group, 'Pixel Size', 'INPUT', 'NodeSocketFloat', 1.0, 0.001)
    socket(group, 'Gap X', 'INPUT', 'NodeSocketFloat', 0.0, 0.0)
    socket(group, 'Gap Y', 'INPUT', 'NodeSocketFloat', 0.0, 0.0)
    socket(group, 'Height', 'INPUT', 'NodeSocketFloat', 0.0, 0.0)
    socket(group, 'Skip Transparent', 'INPUT', 'NodeSocketBool', True)
    socket(group, 'Palette Steps', 'INPUT', 'NodeSocketInt', 0, 0)
    links = group.links
    inputs = new_node(group, 'NodeGroupInput', 'Controls')
    output = new_node(group, 'NodeGroupOutput', 'Geometry')
    info = new_node(group, 'GeometryNodeImageInfo', 'Image dimensions')
    links.new(inputs.outputs['Image'], info.inputs['Image'])

    def math(operation, a=None, b=None, label=None):
        node = new_node(group, 'ShaderNodeMath', label or operation.title())
        node.operation = operation
        if a is not None:
            links.new(a, node.inputs[0])
        if b is not None:
            links.new(b, node.inputs[1])
        return node.outputs[0]

    pitch_x = math('ADD', inputs.outputs['Pixel Size'], inputs.outputs['Gap X'], 'X pitch')
    pitch_y = math('ADD', inputs.outputs['Pixel Size'], inputs.outputs['Gap Y'], 'Y pitch')
    width_minus_one = math('SUBTRACT', info.outputs['Width'], label='Width - 1')
    height_minus_one = math('SUBTRACT', info.outputs['Height'], label='Height - 1')
    group.nodes[width_minus_one.node.name].inputs[1].default_value = 1
    group.nodes[height_minus_one.node.name].inputs[1].default_value = 1
    points = new_node(group, 'GeometryNodePoints', 'One point per pixel')
    links.new(math('MULTIPLY', info.outputs['Width'], info.outputs['Height']), points.inputs['Count'])
    index = new_node(group, 'GeometryNodeInputIndex', 'Pixel index')
    column = math('FLOOR', math('DIVIDE', index.outputs['Index'], info.outputs['Height']))
    row = math('MODULO', index.outputs['Index'], info.outputs['Height'])
    half = new_node(group, 'ShaderNodeValue', 'Half')
    half.outputs[0].default_value = 0.5
    center_x = math('MULTIPLY', width_minus_one, pitch_x)
    center_y = math('MULTIPLY', height_minus_one, pitch_y)
    center_x = math('MULTIPLY', center_x, half.outputs[0])
    center_y = math('MULTIPLY', center_y, half.outputs[0])
    position = new_node(group, 'ShaderNodeCombineXYZ', 'Pixel position')
    links.new(math('SUBTRACT', math('MULTIPLY', column, pitch_x), center_x), position.inputs['X'])
    links.new(math('SUBTRACT', math('MULTIPLY', row, pitch_y), center_y), position.inputs['Y'])
    links.new(position.outputs['Vector'], points.inputs['Position'])

    # Sample the center of each pixel, independent of geometry spacing.
    u = math('ADD', column, label='Pixel U center')
    group.nodes[u.node.name].inputs[1].default_value = 0.5
    v = math('ADD', row, label='Pixel V center')
    group.nodes[v.node.name].inputs[1].default_value = 0.5
    uv = new_node(group, 'ShaderNodeCombineXYZ', 'Normalized pixel center')
    links.new(math('DIVIDE', u, info.outputs['Width']), uv.inputs['X'])
    links.new(math('DIVIDE', v, info.outputs['Height']), uv.inputs['Y'])
    texture = new_node(group, 'GeometryNodeImageTexture', 'Nearest image pixel')
    texture.interpolation = 'Closest'
    links.new(inputs.outputs['Image'], texture.inputs['Image'])
    links.new(uv.outputs['Vector'], texture.inputs['Vector'])

    # Image Texture returns premultiplied RGB. Recover straight color before
    # shader alpha is applied; quantize the visible color, not the darkened one.
    split = new_node(group, 'FunctionNodeSeparateColor', 'Color channels')
    links.new(texture.outputs['Color'], split.inputs['Color'])
    safe_alpha = math('MAXIMUM', texture.outputs['Alpha'])
    group.nodes[safe_alpha.node.name].inputs[1].default_value = 0.00001
    straight = new_node(group, 'FunctionNodeCombineColor', 'Straight pixel color')
    reduced = new_node(group, 'FunctionNodeCombineColor', 'Quantized color')
    for channel in ('Red', 'Green', 'Blue'):
        channel_value = math('DIVIDE', split.outputs[channel], safe_alpha)
        links.new(channel_value, straight.inputs[channel])
        scaled = math('MULTIPLY', channel_value, inputs.outputs['Palette Steps'])
        rounded = math('ROUND', scaled)
        links.new(math('DIVIDE', rounded, inputs.outputs['Palette Steps']), reduced.inputs[channel])
    quantize = new_node(group, 'GeometryNodeSwitch', 'Palette on/off')
    quantize.input_type = 'RGBA'
    links.new(math('GREATER_THAN', inputs.outputs['Palette Steps']), quantize.inputs['Switch'])
    links.new(straight.outputs['Color'], quantize.inputs['False'])
    links.new(reduced.outputs['Color'], quantize.inputs['True'])

    color = new_node(group, 'GeometryNodeStoreNamedAttribute', 'Pixel color')
    color.data_type = 'FLOAT_COLOR'
    color.domain = 'POINT'
    color.inputs['Name'].default_value = COLOR_ATTRIBUTE
    links.new(points.outputs['Points'], color.inputs['Geometry'])
    links.new(quantize.outputs[0], color.inputs['Value'])
    alpha = new_node(group, 'GeometryNodeStoreNamedAttribute', 'Pixel alpha')
    alpha.data_type = 'FLOAT'
    alpha.domain = 'POINT'
    alpha.inputs['Name'].default_value = ALPHA_ATTRIBUTE
    links.new(color.outputs['Geometry'], alpha.inputs['Geometry'])
    links.new(texture.outputs['Alpha'], alpha.inputs['Value'])

    transparent = math('LESS_THAN', texture.outputs['Alpha'], label='Fully transparent')
    group.nodes[transparent.node.name].inputs[1].default_value = 0.00001
    skip = math('MULTIPLY', transparent, inputs.outputs['Skip Transparent'])
    delete = new_node(group, 'GeometryNodeDeleteGeometry', 'Discard transparent pixels')
    delete.domain = 'POINT'
    links.new(alpha.outputs['Geometry'], delete.inputs['Geometry'])
    links.new(skip, delete.inputs['Selection'])

    plane = new_node(group, 'GeometryNodeMeshGrid', 'Flat pixel')
    plane.inputs['Vertices X'].default_value = 2
    plane.inputs['Vertices Y'].default_value = 2
    links.new(inputs.outputs['Pixel Size'], plane.inputs['Size X'])
    links.new(inputs.outputs['Pixel Size'], plane.inputs['Size Y'])
    cube = new_node(group, 'GeometryNodeMeshCube', 'Extruded pixel')
    dimensions = new_node(group, 'ShaderNodeCombineXYZ', 'Cube size')
    links.new(inputs.outputs['Pixel Size'], dimensions.inputs['X'])
    links.new(inputs.outputs['Pixel Size'], dimensions.inputs['Y'])
    links.new(inputs.outputs['Height'], dimensions.inputs['Z'])
    links.new(dimensions.outputs['Vector'], cube.inputs['Size'])
    lift = new_node(group, 'GeometryNodeTransform', 'Rest cube on XY plane')
    links.new(cube.outputs['Mesh'], lift.inputs['Geometry'])
    half_height = math('MULTIPLY', inputs.outputs['Height'], label='Half height')
    group.nodes[half_height.node.name].inputs[1].default_value = 0.5
    translation = new_node(group, 'ShaderNodeCombineXYZ', 'Height offset')
    links.new(half_height, translation.inputs['Z'])
    links.new(translation.outputs['Vector'], lift.inputs['Translation'])
    shape = new_node(group, 'GeometryNodeSwitch', 'Plane or cube')
    shape.input_type = 'GEOMETRY'
    links.new(math('GREATER_THAN', inputs.outputs['Height']), shape.inputs['Switch'])
    links.new(plane.outputs['Mesh'], shape.inputs['False'])
    links.new(lift.outputs['Geometry'], shape.inputs['True'])
    paint = new_node(group, 'GeometryNodeSetMaterial', 'One material for every pixel')
    paint.inputs['Material'].default_value = material
    links.new(shape.outputs[0], paint.inputs['Geometry'])
    instance = new_node(group, 'GeometryNodeInstanceOnPoints', 'Pixel instances')
    links.new(delete.outputs['Geometry'], instance.inputs['Points'])
    links.new(paint.outputs['Geometry'], instance.inputs['Instance'])
    realize = new_node(group, 'GeometryNodeRealizeInstances', 'Expose pixel colors to shader')
    links.new(instance.outputs['Instances'], realize.inputs['Geometry'])
    links.new(realize.outputs['Geometry'], output.inputs['Geometry'])
    return group

def input_socket(modifier, group, name):
    identifier = next(item.identifier for item in group.interface.items_tree
                      if item.item_type == 'SOCKET' and item.in_out == 'INPUT' and item.name == name)
    return getattr(modifier.properties.inputs, identifier)


class PIXELER_OT_create(Operator):
    bl_idname = 'object.pixeler_create'
    bl_label = 'Create Pixel Geometry'
    bl_description = 'Create a live Geometry Nodes object from the selected image'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        settings = getattr(context.scene, 'pixeler_settings', None)
        return settings is not None and settings.image is not None

    def execute(self, context):
        image = context.scene.pixeler_settings.image
        if not all(image.size) or image.size[0] < 1 or image.size[1] < 1:
            self.report({'ERROR'}, 'Image has no pixels')
            return {'CANCELLED'}
        material = bpy.data.materials.get(MATERIAL_NAME) or create_material()
        group = bpy.data.node_groups.get(GROUP_NAME) or create_group(material)
        collection = bpy.data.collections.get('Pixeler')
        if collection is None:
            collection = bpy.data.collections.new('Pixeler')
            context.scene.collection.children.link(collection)
        mesh = bpy.data.meshes.new(image.name + ' pixel source')
        obj = bpy.data.objects.new(image.name + ' Pixels', mesh)
        collection.objects.link(obj)
        modifier = obj.modifiers.new('Pixeler', 'NODES')
        modifier.node_group = group
        input_socket(modifier, group, 'Image').value = image
        for selected in context.selected_objects:
            selected.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return {'FINISHED'}


class PIXELER_PT_main(Panel):
    bl_idname = 'PIXELER_PT_main'
    bl_label = 'Pixeler'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Pixeler'

    def draw(self, context):
        layout = self.layout
        layout.template_ID(context.scene.pixeler_settings, 'image', open='image.open')
        layout.operator('object.pixeler_create', icon='MOD_NODES')
        obj = context.object
        if obj:
            modifier = next((mod for mod in obj.modifiers
                             if mod.type == 'NODES' and mod.node_group
                             and mod.node_group.name == GROUP_NAME), None)
            if modifier:
                layout.separator()
                for name in ('Image', 'Pixel Size', 'Gap X', 'Gap Y', 'Height',
                             'Skip Transparent', 'Palette Steps'):
                    layout.prop(input_socket(modifier, modifier.node_group, name), 'value', text=name)


CLASSES = (PixelerSettings, PIXELER_OT_create, PIXELER_PT_main)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.pixeler_settings = PointerProperty(type=PixelerSettings)


def unregister():
    del bpy.types.Scene.pixeler_settings
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == '__main__':
    register()
