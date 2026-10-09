# Pixeler - turn an image into live pixel geometry in Blender.
# Copyright (C) 2018-2026 Benjamin Kleinert
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pixeler: a live image-to-geometry modifier for Blender 5+."""

import bpy
from bpy.props import PointerProperty
from bpy.types import Operator, Panel, PropertyGroup

GROUP_NAME = "Pixeler Geometry"
MATERIAL_NAME = "Pixeler Surface"
COLOR_ATTRIBUTE = "pixeler_color"
ALPHA_ATTRIBUTE = "pixeler_alpha"
PIXEL_GROUP_NAME = 'Pixeler Pixel Geometry'


class PixelerSettings(PropertyGroup):
    image: PointerProperty(name="Image", type=bpy.types.Image)


def socket(group, name, direction, socket_type, default=None, minimum=None, description='', parent=None):
    item = group.interface.new_socket(name=name, in_out=direction, socket_type=socket_type,
                                      description=description, parent=parent)
    if default is not None:
        item.default_value = default
    if minimum is not None:
        item.min_value = minimum
    return item


def new_node(group, node_type, label):
    node = group.nodes.new(node_type)
    node.label = label
    return node


def socket_by_id(sockets, identifier):
    return next(s for s in sockets if s.identifier == identifier)


def tint_material(material):
    """Multiply the stored pixel color by the object's viewport color."""
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    shader = next(node for node in nodes if node.type == 'BSDF_PRINCIPLED')
    source = next((node for node in nodes if node.type == 'ATTRIBUTE'
                   and node.attribute_name == COLOR_ATTRIBUTE), None)
    if source is None:
        source = nodes.new('ShaderNodeAttribute')
        source.attribute_name = COLOR_ATTRIBUTE
    object_info = nodes.new('ShaderNodeObjectInfo')
    tint = nodes.new('ShaderNodeMix')
    tint.data_type = 'RGBA'
    tint.blend_type = 'MULTIPLY'
    tint.inputs['Factor'].default_value = 1.0
    links.new(source.outputs['Color'], socket_by_id(tint.inputs, 'A_Color'))
    links.new(object_info.outputs['Color'], socket_by_id(tint.inputs, 'B_Color'))
    links.new(socket_by_id(tint.outputs, 'Result_Color'), shader.inputs['Base Color'])


def create_material():
    material = bpy.data.materials.new(MATERIAL_NAME)
    material.use_nodes = True
    material.surface_render_method = 'BLENDED'
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    shader = next(node for node in nodes if node.type == 'BSDF_PRINCIPLED')
    tint_material(material)
    alpha = nodes.new('ShaderNodeAttribute')
    alpha.attribute_name = ALPHA_ATTRIBUTE
    links.new(alpha.outputs['Fac'], shader.inputs['Alpha'])
    return material


def create_pixel_group(material):
    group = bpy.data.node_groups.new(PIXEL_GROUP_NAME, 'GeometryNodeTree')
    for name, kind in (('Color', 'NodeSocketColor'), ('Alpha', 'NodeSocketFloat'),
                       ('Size', 'NodeSocketFloat'), ('Height', 'NodeSocketFloat'),
                       ('Column', 'NodeSocketInt'), ('Row', 'NodeSocketInt'),
                       ('Store Vertex Colors', 'NodeSocketBool')):
        socket(group, name, 'INPUT', kind)
    socket(group, 'Geometry', 'OUTPUT', 'NodeSocketGeometry')
    links = group.links
    inputs = new_node(group, 'NodeGroupInput', 'Pixel data')
    output = new_node(group, 'NodeGroupOutput', 'Pixel mesh')
    plane = new_node(group, 'GeometryNodeMeshGrid', 'Flat pixel')
    plane.inputs['Vertices X'].default_value = 2
    plane.inputs['Vertices Y'].default_value = 2
    links.new(inputs.outputs['Size'], plane.inputs['Size X'])
    links.new(inputs.outputs['Size'], plane.inputs['Size Y'])
    cube = new_node(group, 'GeometryNodeMeshCube', 'Extruded pixel')
    dimensions = new_node(group, 'ShaderNodeCombineXYZ', 'Cube dimensions')
    links.new(inputs.outputs['Size'], dimensions.inputs['X'])
    links.new(inputs.outputs['Size'], dimensions.inputs['Y'])
    links.new(inputs.outputs['Height'], dimensions.inputs['Z'])
    links.new(dimensions.outputs['Vector'], cube.inputs['Size'])
    lift = new_node(group, 'GeometryNodeTransform', 'Rest cube on XY plane')
    links.new(cube.outputs['Mesh'], lift.inputs['Geometry'])
    half = new_node(group, 'ShaderNodeMath', 'Half height')
    half.operation = 'MULTIPLY'
    half.inputs[1].default_value = 0.5
    links.new(inputs.outputs['Height'], half.inputs[0])
    offset = new_node(group, 'ShaderNodeCombineXYZ', 'Height offset')
    links.new(half.outputs[0], offset.inputs['Z'])
    links.new(offset.outputs['Vector'], lift.inputs['Translation'])
    shape = new_node(group, 'GeometryNodeSwitch', 'Plane or cube')
    shape.input_type = 'GEOMETRY'
    greater = new_node(group, 'ShaderNodeMath', 'Extrude')
    greater.operation = 'GREATER_THAN'
    links.new(inputs.outputs['Height'], greater.inputs[0])
    links.new(greater.outputs[0], shape.inputs['Switch'])
    links.new(plane.outputs['Mesh'], shape.inputs['False'])
    links.new(lift.outputs['Geometry'], shape.inputs['True'])
    paint = new_node(group, 'GeometryNodeSetMaterial', 'Pixel material')
    paint.inputs['Material'].default_value = material
    links.new(shape.outputs[0], paint.inputs['Geometry'])
    color = new_node(group, 'GeometryNodeStoreNamedAttribute', 'Optional vertex color')
    color.data_type = 'FLOAT_COLOR'
    color.domain = 'POINT'
    color.inputs['Name'].default_value = COLOR_ATTRIBUTE
    links.new(paint.outputs['Geometry'], color.inputs['Geometry'])
    links.new(inputs.outputs['Color'], color.inputs['Value'])
    color_mode = new_node(group, 'GeometryNodeSwitch', 'Vertex color on/off')
    color_mode.input_type = 'GEOMETRY'
    links.new(inputs.outputs['Store Vertex Colors'], color_mode.inputs['Switch'])
    links.new(paint.outputs['Geometry'], color_mode.inputs['False'])
    links.new(color.outputs['Geometry'], color_mode.inputs['True'])
    alpha = new_node(group, 'GeometryNodeStoreNamedAttribute', 'Pixel alpha')
    alpha.data_type = 'FLOAT'
    alpha.domain = 'POINT'
    alpha.inputs['Name'].default_value = ALPHA_ATTRIBUTE
    links.new(color_mode.outputs[0], alpha.inputs['Geometry'])
    links.new(inputs.outputs['Alpha'], alpha.inputs['Value'])
    links.new(alpha.outputs['Geometry'], output.inputs['Geometry'])
    return group


def create_group(material, pixel_group):
    group = bpy.data.node_groups.new(GROUP_NAME, 'GeometryNodeTree')
    group.is_modifier = True
    socket(group, 'Geometry', 'INPUT', 'NodeSocketGeometry')
    socket(group, 'Geometry', 'OUTPUT', 'NodeSocketGeometry')
    socket(group, 'Image', 'INPUT', 'NodeSocketImage',
           description='Image or tilesheet to turn into geometry')

    sheet = group.interface.new_panel('Tilesheet', default_closed=True,
                                      description='Pick one sprite from a regular grid of tiles')
    sheet_toggle = socket(group, 'Tilesheet', 'INPUT', 'NodeSocketBool', False, parent=sheet,
                          description='Use one sprite of a tilesheet instead of the whole image')
    sheet_toggle.is_panel_toggle = True  # Blender names a panel toggle after its panel
    socket(group, 'Tile Width', 'INPUT', 'NodeSocketInt', 0, 0, parent=sheet,
           description='Width of one sprite in pixels. 0 uses everything inside the margin')
    socket(group, 'Tile Height', 'INPUT', 'NodeSocketInt', 0, 0, parent=sheet,
           description='Height of one sprite in pixels. 0 uses everything inside the margin')
    socket(group, 'Margin', 'INPUT', 'NodeSocketInt', 0, 0, parent=sheet,
           description='Pixels of border around the whole sheet')
    socket(group, 'Spacing', 'INPUT', 'NodeSocketInt', 0, 0, parent=sheet,
           description='Pixels between neighboring tiles')
    socket(group, 'Tile Column', 'INPUT', 'NodeSocketInt', 0, 0, parent=sheet,
           description='Sprite column to show, counted from 0. Ignored while Animation is on')
    socket(group, 'Tile Row', 'INPUT', 'NodeSocketInt', 0, 0, parent=sheet,
           description='Sprite row to show, counted from 0. Ignored while Animation is on')

    animation = group.interface.new_panel('Animation', default_closed=True,
                                          description='Flip through tiles by scene frame')
    toggle = socket(group, 'Animation', 'INPUT', 'NodeSocketBool', False, parent=animation,
                    description='Step through tiles in reading order using the current frame')
    toggle.is_panel_toggle = True  # Blender names a panel toggle after its panel
    socket(group, 'Frames Per Tile', 'INPUT', 'NodeSocketInt', 4, 1, parent=animation,
           description='Frames each tile is held')
    socket(group, 'Start Frame', 'INPUT', 'NodeSocketInt', 0, parent=animation,
           description='Frame at which the first tile appears. Earlier frames wrap backwards')
    socket(group, 'First Tile', 'INPUT', 'NodeSocketInt', 0, 0, parent=animation,
           description='Index of the first tile in the loop, 0 is the upper left')
    socket(group, 'Tile Count', 'INPUT', 'NodeSocketInt', 0, 0, parent=animation,
           description='Tiles in the loop. 0 runs through the last tile')

    pixels = group.interface.new_panel('Pixels', description='Size and shape of each pixel')
    socket(group, 'Pixel Size', 'INPUT', 'NodeSocketFloat', 1.0, 0.001, parent=pixels,
           description='Width and depth of each plane or cube')
    socket(group, 'Gap X', 'INPUT', 'NodeSocketFloat', 0.0, 0.0, parent=pixels,
           description='Extra space between pixels along X')
    socket(group, 'Gap Y', 'INPUT', 'NodeSocketFloat', 0.0, 0.0, parent=pixels,
           description='Extra space between pixels along Y')
    socket(group, 'Height', 'INPUT', 'NodeSocketFloat', 0.0, 0.0, parent=pixels,
           description='0 makes flat planes, above 0 makes cubes resting on the XY plane')
    socket(group, 'Custom Pixel', 'INPUT', 'NodeSocketBool', False, parent=pixels,
           description='Run the editable Pixel Geometry group once for each visible pixel')

    color = group.interface.new_panel('Color', default_closed=True, description='Transparency and palette')
    socket(group, 'Skip Transparent', 'INPUT', 'NodeSocketBool', True, parent=color,
           description='Remove fully transparent pixels. Partly transparent ones keep their alpha')
    socket(group, 'Palette Steps', 'INPUT', 'NodeSocketInt', 0, 0, parent=color,
           description='0 keeps original colors, above 0 quantizes RGB to that many steps')
    socket(group, 'Store Vertex Colors', 'INPUT', 'NodeSocketBool', True, parent=color,
           description='Write pixeler_color to the generated mesh; turn off for uncolored custom geometry')
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

    def math_c(operation, a, value, label=None):
        out = math(operation, a, None, label)
        out.node.inputs[1].default_value = value
        return out

    def switch(kind, label, condition, false, true):
        node = new_node(group, 'GeometryNodeSwitch', label)
        node.input_type = kind
        links.new(condition, node.inputs['Switch'])
        links.new(false, node.inputs['False'])
        links.new(true, node.inputs['True'])
        return node.outputs[0]

    pitch_x = math('ADD', inputs.outputs['Pixel Size'], inputs.outputs['Gap X'], 'X pitch')
    pitch_y = math('ADD', inputs.outputs['Pixel Size'], inputs.outputs['Gap Y'], 'Y pitch')
    # Margin is an equal border on all four sides. A zero tile dimension means
    # the whole area inside the margin on that axis; larger tiles are clipped to it.
    # With Tilesheet off, tile size, margin and spacing count as 0: the whole image is used.
    sheet_on = inputs.outputs[sheet_toggle.identifier]
    margin = math('MULTIPLY', inputs.outputs['Margin'], sheet_on, 'Margin if tilesheet')
    spacing = math('MULTIPLY', inputs.outputs['Spacing'], sheet_on, 'Spacing if tilesheet')
    sheet_width = math('MULTIPLY', inputs.outputs['Tile Width'], sheet_on, 'Tile width if tilesheet')
    sheet_height = math('MULTIPLY', inputs.outputs['Tile Height'], sheet_on, 'Tile height if tilesheet')
    tile_width = math('MAXIMUM', sheet_width)
    tile_height = math('MAXIMUM', sheet_height)
    group.nodes[tile_width.node.name].inputs[1].default_value = 1
    group.nodes[tile_height.node.name].inputs[1].default_value = 1
    border = math_c('MULTIPLY', margin, 2, 'Both margins')
    usable_width = math_c('MAXIMUM', math('SUBTRACT', info.outputs['Width'], border), 1, 'Usable width')
    usable_height = math_c('MAXIMUM', math('SUBTRACT', info.outputs['Height'], border), 1, 'Usable height')
    width = math('MINIMUM', usable_width, tile_width, 'Selected width')
    height = math('MINIMUM', usable_height, tile_height, 'Selected height')
    use_width = math('GREATER_THAN', sheet_width)
    use_height = math('GREATER_THAN', sheet_height)
    width_switch = new_node(group, 'GeometryNodeSwitch', 'Tile or full width')
    height_switch = new_node(group, 'GeometryNodeSwitch', 'Tile or full height')
    width_switch.input_type = 'INT'
    height_switch.input_type = 'INT'
    links.new(use_width, width_switch.inputs['Switch'])
    links.new(use_height, height_switch.inputs['Switch'])
    links.new(usable_width, width_switch.inputs['False'])
    links.new(usable_height, height_switch.inputs['False'])
    links.new(width, width_switch.inputs['True'])
    links.new(height, height_switch.inputs['True'])
    selected_width = width_switch.outputs[0]
    selected_height = height_switch.outputs[0]
    width_minus_one = math('SUBTRACT', selected_width, label='Width - 1')
    height_minus_one = math('SUBTRACT', selected_height, label='Height - 1')
    group.nodes[width_minus_one.node.name].inputs[1].default_value = 1
    group.nodes[height_minus_one.node.name].inputs[1].default_value = 1
    points = new_node(group, 'GeometryNodePoints', 'One point per pixel')
    links.new(math('MULTIPLY', selected_width, selected_height), points.inputs['Count'])
    index = new_node(group, 'GeometryNodeInputIndex', 'Pixel index')
    column = math('FLOOR', math('DIVIDE', index.outputs['Index'], selected_height))
    row = math('MODULO', index.outputs['Index'], selected_height)
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

    # Tiles form a regular grid counted from the upper-left inside the margin,
    # separated by Spacing pixels. Partial tiles at the far edge are ignored.
    # Geometry rows grow upward, matching Blender image coordinates.
    pitch_w = math('ADD', selected_width, spacing, 'Tile pitch X')
    pitch_h = math('ADD', selected_height, spacing, 'Tile pitch Y')
    columns = math_c('MAXIMUM', math('FLOOR', math('DIVIDE', math('ADD', usable_width, spacing), pitch_w)), 1, 'Tile columns')
    rows = math_c('MAXIMUM', math('FLOOR', math('DIVIDE', math('ADD', usable_height, spacing), pitch_h)), 1, 'Tile rows')
    total = math('MULTIPLY', columns, rows, 'Tile total')

    # Animation walks tiles in reading order from First Tile, loops over Tile Count
    # (0 = through the last tile), and holds each for Frames Per Tile frames.
    first = math('MINIMUM', math_c('MAXIMUM', inputs.outputs['First Tile'], 0), math_c('SUBTRACT', total, 1), 'First tile')
    remaining = math('SUBTRACT', total, first, 'Tiles after first')
    count = switch('INT', 'Loop length', math_c('GREATER_THAN', inputs.outputs['Tile Count'], 0),
                   remaining, math('MINIMUM', inputs.outputs['Tile Count'], remaining))
    scene_time = new_node(group, 'GeometryNodeInputSceneTime', 'Scene frame')
    hold = math_c('MAXIMUM', inputs.outputs['Frames Per Tile'], 1, 'Frames per tile')
    step = math('FLOOR', math('DIVIDE', math('SUBTRACT', scene_time.outputs['Frame'], inputs.outputs['Start Frame']), hold), label='Animation step')
    animated_index = math('ADD', first, math('FLOORED_MODULO', step, count), 'Animated tile')
    animated_column = math('FLOORED_MODULO', animated_index, columns, 'Animated column')
    animated_row = math('FLOOR', math('DIVIDE', animated_index, columns), label='Animated row')
    animate = inputs.outputs[toggle.identifier]
    tile_column = switch('INT', 'Tile column', animate,
                         math('MINIMUM', inputs.outputs['Tile Column'], math_c('SUBTRACT', columns, 1)), animated_column)
    tile_row = switch('INT', 'Tile row', animate,
                      math('MINIMUM', inputs.outputs['Tile Row'], math_c('SUBTRACT', rows, 1)), animated_row)
    tile_left = math('ADD', margin, math('MULTIPLY', tile_column, pitch_w), 'Tile left')
    tile_top = math('ADD', margin, math('MULTIPLY', tile_row, pitch_h), 'Tile top')
    tile_bottom = math('SUBTRACT', math('SUBTRACT', info.outputs['Height'], tile_top), selected_height, 'Tile bottom')
    x_sample = math('ADD', column, tile_left, 'Source X')
    y_sample = math('ADD', row, tile_bottom, 'Source Y')
    u = math('ADD', x_sample, label='Pixel U center')
    group.nodes[u.node.name].inputs[1].default_value = 0.5
    v = math('ADD', y_sample, label='Pixel V center')
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
    color_mode = new_node(group, 'GeometryNodeSwitch', 'Vertex color on/off')
    color_mode.input_type = 'GEOMETRY'
    links.new(inputs.outputs['Store Vertex Colors'], color_mode.inputs['Switch'])
    links.new(points.outputs['Points'], color_mode.inputs['False'])
    links.new(color.outputs['Geometry'], color_mode.inputs['True'])
    links.new(quantize.outputs[0], color.inputs['Value'])
    alpha = new_node(group, 'GeometryNodeStoreNamedAttribute', 'Pixel alpha')
    alpha.data_type = 'FLOAT'
    alpha.domain = 'POINT'
    alpha.inputs['Name'].default_value = ALPHA_ATTRIBUTE
    links.new(color_mode.outputs[0], alpha.inputs['Geometry'])
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
    custom_points = new_node(group, 'GeometryNodeDeleteGeometry', 'Visible pixel points')
    custom_points.domain = 'POINT'
    links.new(points.outputs['Points'], custom_points.inputs['Geometry'])
    links.new(skip, custom_points.inputs['Selection'])
    each = new_node(group, 'GeometryNodeForeachGeometryElementInput', 'For each visible pixel')
    collect = new_node(group, 'GeometryNodeForeachGeometryElementOutput', 'Collect pixel meshes')
    each.pair_with_output(collect)
    for kind, name in (('RGBA', 'Color'), ('FLOAT', 'Alpha'), ('VECTOR', 'Position'),
                       ('INT', 'Column'), ('INT', 'Row')):
        collect.input_items.new(kind, name)
    links.new(custom_points.outputs['Geometry'], each.inputs['Geometry'])
    links.new(quantize.outputs[0], each.inputs['Color'])
    links.new(texture.outputs['Alpha'], each.inputs['Alpha'])
    links.new(position.outputs['Vector'], each.inputs['Position'])
    links.new(column, each.inputs['Column'])
    links.new(row, each.inputs['Row'])
    pixel = new_node(group, 'GeometryNodeGroup', 'Edit this group to shape each pixel')
    pixel.node_tree = pixel_group
    for name in ('Color', 'Alpha', 'Column', 'Row'):
        links.new(each.outputs[name], pixel.inputs[name])
    links.new(inputs.outputs['Pixel Size'], pixel.inputs['Size'])
    links.new(inputs.outputs['Height'], pixel.inputs['Height'])
    links.new(inputs.outputs['Store Vertex Colors'], pixel.inputs['Store Vertex Colors'])
    place = new_node(group, 'GeometryNodeTransform', 'Position custom pixel')
    links.new(pixel.outputs['Geometry'], place.inputs['Geometry'])
    links.new(each.outputs['Position'], place.inputs['Translation'])
    links.new(place.outputs['Geometry'], collect.inputs['Geometry'])
    final = switch('GEOMETRY', 'Built-in or custom pixel', inputs.outputs['Custom Pixel'],
                   realize.outputs['Geometry'], collect.outputs['Generation_0'])
    links.new(final, output.inputs['Geometry'])
    return group

def input_socket(modifier, group, name):
    identifier = next(item.identifier for item in group.interface.items_tree
                      if item.item_type == 'SOCKET' and item.in_out == 'INPUT' and item.name == name)
    return getattr(modifier.properties.inputs, identifier)


def is_current_group(group):
    return any(item.item_type == 'SOCKET' and item.name == 'Custom Pixel'
               for item in group.interface.items_tree)


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
        if not any(node.type == 'OBJECT_INFO' for node in material.node_tree.nodes):
            tint_material(material)
        # Each object gets its own editable pixel template and modifier graph.
        # Existing objects keep their graph when a new one is created.
        pixel_group = create_pixel_group(material)
        group = create_group(material, pixel_group)
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
        obj.color = (1.0, 1.0, 1.0, 1.0)
        for selected in context.selected_objects:
            selected.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return {'FINISHED'}


def pixeler_modifier(context):
    obj = context.object
    if obj is None:
        return None
    return next((mod for mod in obj.modifiers
                 if mod.type == 'NODES' and mod.node_group
                 and mod.node_group.name.startswith(GROUP_NAME)
                 and is_current_group(mod.node_group)), None)


def draw_inputs(layout, modifier, names):
    layout.use_property_split = True
    layout.use_property_decorate = False
    for name in names:
        layout.prop(input_socket(modifier, modifier.node_group, name), 'value', text=name)


class PIXELER_PT_main(Panel):
    bl_idname = 'PIXELER_PT_main'
    bl_label = 'Pixeler'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Pixeler'

    def draw(self, context):
        layout = self.layout
        layout.template_ID(context.scene.pixeler_settings, 'image', open='image.open')
        layout.operator('object.pixeler_create', icon='GEOMETRY_NODES')
        modifier = pixeler_modifier(context)
        if modifier:
            layout.separator()
            draw_inputs(layout, modifier, ('Image',))


class PixelerSubPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Pixeler'
    bl_parent_id = 'PIXELER_PT_main'

    @classmethod
    def poll(cls, context):
        return pixeler_modifier(context) is not None


class PIXELER_PT_tilesheet(PixelerSubPanel, Panel):
    bl_label = 'Tilesheet'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        modifier = pixeler_modifier(context)
        self.layout.prop(input_socket(modifier, modifier.node_group, 'Tilesheet'), 'value', text='')

    def draw(self, context):
        modifier = pixeler_modifier(context)
        body = self.layout.column()
        body.active = input_socket(modifier, modifier.node_group, 'Tilesheet').value
        draw_inputs(body, modifier, ('Tile Width', 'Tile Height', 'Margin', 'Spacing'))
        body.separator()
        picker = body.column()
        picker.active = body.active and not input_socket(modifier, modifier.node_group, 'Animation').value
        draw_inputs(picker, modifier, ('Tile Column', 'Tile Row'))


class PIXELER_PT_animation(PixelerSubPanel, Panel):
    bl_label = 'Animation'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        modifier = pixeler_modifier(context)
        self.layout.prop(input_socket(modifier, modifier.node_group, 'Animation'), 'value', text='')

    def draw(self, context):
        modifier = pixeler_modifier(context)
        body = self.layout.column()
        body.active = (input_socket(modifier, modifier.node_group, 'Animation').value
                       and input_socket(modifier, modifier.node_group, 'Tilesheet').value)
        draw_inputs(body, modifier, ('Frames Per Tile', 'Start Frame', 'First Tile', 'Tile Count'))


class PIXELER_PT_pixels(PixelerSubPanel, Panel):
    bl_label = 'Pixels'

    def draw(self, context):
        draw_inputs(self.layout, pixeler_modifier(context),
                    ('Pixel Size', 'Gap X', 'Gap Y', 'Height', 'Custom Pixel'))


class PIXELER_PT_color(PixelerSubPanel, Panel):
    bl_label = 'Color'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        modifier = pixeler_modifier(context)
        draw_inputs(self.layout, modifier, ('Skip Transparent', 'Palette Steps', 'Store Vertex Colors'))
        self.layout.use_property_split = True
        self.layout.prop(context.object, 'color', text='Object Color')


CLASSES = (PixelerSettings, PIXELER_OT_create, PIXELER_PT_main, PIXELER_PT_tilesheet,
           PIXELER_PT_animation, PIXELER_PT_pixels, PIXELER_PT_color)


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
