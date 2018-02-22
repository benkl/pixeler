import bpy
from bpy.props import FloatVectorProperty, FloatProperty

bl_info = { \
    'name': 'Pixeler - Pixels to planes',
    'author': '_benkl',
    'version': (0, 0, 1),
    'blender': (2, 7, 9),
    'location': 'View3D > Tools > Pixeler - Pixels to Planes',
    'description': 'Converts the pixels of an image to an array of planes with corresponding colours.',
    'tracker_url': 'https://github.com/benkl/pixeler',
    'wiki_url': 'https://github.com/benkl/pixeler/wiki',
    'support': 'COMMUNITY',
    'category': 'Object'}

bpy.types.Scene.pixeler_xoffset = bpy.props.FloatProperty(name="X offset", default=2)
bpy.types.Scene.pixeler_yoffset = bpy.props.FloatProperty(name="Y offset", default=2)
bpy.types.Scene.pixeler_image_name = bpy.props.StringProperty(name="Image Name")

class Pixeler_Run(bpy.types.Operator):
    bl_idname = 'object.pixeler_run'
    bl_label = "Pixeler"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):

        # Set File Name
        pixeler_file = bpy.context.scene.pixeler_image_name

        # Set img
        img = bpy.data.images[pixeler_file]

        # Get and set image width and height
        w = img.size[0]
        h = img.size[1]
        tfac = img.pixels[:]

        # Set basemesh
        bpy.ops.mesh.primitive_plane_add(location=(-1.0, -1.0, 0.0))
        basemesh = bpy.context.object
        dmat = bpy.data.materials.new(name="origin")
        basemesh.data.materials.append(dmat)

        # Create Grid from Image
        z = 0
        y = 0
        for index in range(0, h):
            x = 0
            for index in range(0, w):
                x = x + 1

                # Get pixel position in flat array
                colar = (x + (y * w)) * 4

                # Set color values at current Pixel
                r = tfac[colar - 4]
                g = tfac[colar - 3]
                b = tfac[colar - 2]

                # Alpha Check
                if tfac[colar - 1] > 0:

                    # Add object at Pixel Location
                    basemeshi = basemesh.copy()
                    basemeshi.data = basemesh.data.copy()
                    basemeshi.location.x = x * bpy.context.scene.pixeler_xoffset + 1
                    basemeshi.location.y = y * bpy.context.scene.pixeler_yoffset + 1
                    bpy.context.scene.objects.link(basemeshi)

                    # Get material
                    matname = "Mat" + str(r) + str(g) + str(b)
                    mat = bpy.data.materials.get(matname)
                    if mat is None:
                        # create material
                        mat = bpy.data.materials.new(name=matname)
                        mat.use_nodes = True
                        prinode = mat.node_tree.nodes.new(type="ShaderNodeBsdfPrincipled")
                        dif = mat.node_tree.nodes["Diffuse BSDF"]
                        outshad = mat.node_tree.nodes["Material Output"]
                        mat.node_tree.nodes.remove(dif)
                        mat.node_tree.links.new(prinode.outputs[0], outshad.inputs[0])
                        # rgb = mat.node_tree.nodes.new(type = "ShaderNodeRGB")

                        # PBR Color
                        prin = mat.node_tree.nodes["Principled BSDF"]
                        prin.inputs[0].default_value = [r, g, b, 1]
                        prin.inputs[7].default_value = 0.6

                        # Set editor color from pixel value
                        bpy.data.materials[matname].diffuse_color = (r, g, b)

                    # assign to 1st material slot
                    basemeshi.data.materials[0] = mat

                    # Join newly creatd meshes
                    basemeshi.select = True
                    bpy.context.scene.objects.active = basemeshi
                    basemesh.select = False

                    # Print Pixel placement confirmation
                    print("Placed object @ x " + str(x) + " y " + str(y))

            # Join line
            bpy.ops.object.join()

            # Incerement y last
            y = y + 1
            # bpy.ops.object.select_all(action='DESELECT')

        bpy.context.scene.update()
        print("pixels to planes is done")
        return {'FINISHED'}

class Pixeler_Panel(bpy.types.Panel):
    bl_idname = "view3d.pixeler_panel"
    bl_label = "Pixeler - Pixels to Planes"
    bl_space_type ="VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Tools"

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "pixeler_image_name")
        layout.prop(context.scene, "pixeler_xoffset")
        layout.prop(context.scene, "pixeler_yoffset")
        layout.operator("object.pixeler_run", text="Pixeler", icon="PLAY")

def register():
    bpy.utils.register_module(__name__)

def unregister():
    bpy.utils.unregister_module(__name__)

if __name__ == "__main__":
    register()
