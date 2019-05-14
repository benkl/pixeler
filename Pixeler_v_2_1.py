import bpy
from bpy.props import ( FloatVectorProperty, FloatProperty, BoolProperty, PointerProperty, StringProperty, EnumProperty )
from bpy.types import ( Panel, Operator, AddonPreferences, PropertyGroup )

bl_info = { \
    'name': 'Pixeler - Pixels to planes',
    'author': '_benkl',
    'version': (0, 2, 1),
    'blender': (2, 80, 0),
    'location': 'View3D > Tools > Pixeler - Pixels to Planes',
    'description': 'Converts the pixels of an image to an array of planes with corresponding colours.',
    'tracker_url': 'https://github.com/benkl/pixeler',
    'wiki_url': 'https://github.com/benkl/pixeler/wiki',
    'support': 'COMMUNITY',
    'category': 'Object'}

class PXL_UI_variables(PropertyGroup):

    def pixeler_img_list(self, context):
        return [(img.name,)*3 for img in bpy.data.images]

    pixeler_images: EnumProperty(
        name="Image",
        description="Selected image",
        items=pixeler_img_list
        )

    pixeler_mergebool: BoolProperty(
        name="Merge vertices",
        description="Remove doubles while joining meshes",
        default = False
        )

    pixeler_cubebool: BoolProperty(
        name="Use cubes",
        description="Extrudes all faces by 2 units",
        default = False
        )

    pixeler_alpha: BoolProperty(
        name="Skip transparent pixels",
        description="Skip pixels with alpha=0",
        default = False
        )

    pixeler_simplify: BoolProperty(
        name="Reduce color palette",
        description="Rounds the color values to reduce material count",
        default = False
        )

    pixeler_xoffset: FloatProperty(
        name="X offset",
        default=0,
        description="Values over 0 create an X offset"
        )

    pixeler_yoffset: FloatProperty(
        name="Y offset",
        default=0,
        description="Values over 0 create an Y offset"
        )

#class PXL_OT_open_image(bpy.types.Operator):

class PXL_OT_create_pixels(bpy.types.Operator):
    bl_idname = 'mesh.pxl_ot_create_pixels'
    bl_label = "Add planes from pixels"
    bl_description = "Run the Pixeler script"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        # Settings from interface to local
        pixeler_file = bpy.context.scene.pixeler_vars.pixeler_images

        # Set img
        img = bpy.data.images[pixeler_file]

        # Get and set image width and height
        w = img.size[0]
        h = img.size[1]
        tfac = img.pixels[:]
        
        #Create Collection
        if (bpy.data.collections.find('Pixeler') == True):
            pixeler_collection = bpy.data.collections['Pixeler']
        else:
            pixeler_collection = bpy.data.collections.new('Pixeler')
            bpy.context.scene.collection.children.link(pixeler_collection)
        
        # Set basemesh
        bpy.ops.mesh.primitive_plane_add(location=(-1.0, -1.0, 0.0))
        basemesh = bpy.context.object
        dmat = bpy.data.materials.new(name="origin")
        basemesh.data.materials.append(dmat)
        
        #Link to collection
        pixeler_collection.objects.link(basemesh)

        #Create material group
        
        if (bpy.data.node_groups.find('MaterialSettingsGroup')>=1):
            print('Using existing group')
        else:
            # create a group
            materialsettingsgroup = bpy.data.node_groups.new('MaterialSettingsGroup', 'ShaderNodeTree')

            # create group outputs
            group_outputs = materialsettingsgroup.nodes.new('NodeGroupOutput')
            group_outputs.location = (300,0)
            materialsettingsgroup.outputs.new('NodeSocketFloat','Metal')
            materialsettingsgroup.outputs.new('NodeSocketFloat','Roughness')
            

            roughness = materialsettingsgroup.nodes.new(type="ShaderNodeValue")
            roughness.location = (-300,0)
            roughness.name = "Roughness"
            metal = materialsettingsgroup.nodes.new(type="ShaderNodeValue")
            metal.location = (-300,50)
            metal.name = "Metal"
            # link inputs
            materialsettingsgroup.links.new(metal.outputs[0], group_outputs.inputs['Metal'])
            materialsettingsgroup.links.new(roughness.outputs[0], group_outputs.inputs['Roughness'])

        # Create Grid from Image
        z = 0
        y = 0

        if (bpy.context.scene.pixeler_vars.pixeler_simplify==True):
            simpler = 1
        else:
            simpler = 3

        for index in range(0, h):
            
            x = 0
            for index in range(0, w):
                x = x + 1

                # Get pixel position in flat array
                colar = (x + (y * w)) * 4

                # Set color values at current Pixel
                a = round(tfac[colar - 1], 3)
                r = round(tfac[colar - 4]*a, simpler)
                g = round(tfac[colar - 3]*a, simpler)
                b = round(tfac[colar - 2]*a, simpler)               
                
                # Alpha Check
                if (bpy.context.scene.pixeler_vars.pixeler_alpha==True):
                    alpha_switch = 0
                else:
                    alpha_switch = -1

                if a > alpha_switch:

                    # Add object at Pixel Location
                    basemeshi = basemesh.copy()
                    basemeshi.data = basemesh.data.copy()
                    basemeshi.location.x = x * (bpy.context.scene.pixeler_vars.pixeler_xoffset + 2)
                    basemeshi.location.y = y * (bpy.context.scene.pixeler_vars.pixeler_yoffset + 2)
                    basemeshi.location.z = z
                    pixeler_collection.objects.link(basemeshi)      

                    # Fix coloured but transparent pixels
                    if a == 0:
                        r = 0
                        g = 0
                        b = 0
                    
                    # Get material    
                    matname = "Mat" + " r" + str(r) + " g" + str(g) + " b" + str(b) + " a" + str(a)
                    mat = bpy.data.materials.get(matname)
                    
                    if mat is None:
                        # create material
                        mat = bpy.data.materials.new(name=matname)
                        mat.use_nodes = True
                        prinode = mat.node_tree.nodes["Principled BSDF"]
                        outshad = mat.node_tree.nodes["Material Output"]
                        group = mat.node_tree.nodes.new("ShaderNodeGroup")
                        group.location = (-300,0)
                        group.node_tree = bpy.data.node_groups['MaterialSettingsGroup']
                        mat.node_tree.links.new(group.outputs[0], prinode.inputs[4])
                        mat.node_tree.links.new(group.outputs[1], prinode.inputs[7])                        
                        mat.node_tree.links.new(prinode.outputs[0], outshad.inputs[0])

                        # PBR Color
                        prinode.inputs[0].default_value = [r, g, b, a]
                        prinode.inputs[7].default_value = 0.1

                        # Set editor color from pixel value
                        bpy.data.materials[matname].diffuse_color = (r, g, b, a)

                    # assign to 1st material slot
                    basemeshi.data.materials[0] = mat

                    # Join newly creatd meshes
                    basemeshi.select_set(state=True)
                    bpy.context.view_layer.objects.active = basemeshi                                                                  
                    basemesh.select_set(state=False)                

                    # Print Pixel placement confirmation
                    print("Placed object @ x " + str(x) + " y " + str(y))
                     
            # Join line
            bpy.ops.object.join()

            # Remove doubles
            if (bpy.context.scene.pixeler_vars.pixeler_mergebool == True):
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.remove_doubles(threshold=0.0001)
                bpy.ops.object.mode_set(mode='OBJECT')
        
           # Incerement y last
            y = y + 1
            # bpy.ops.object.select_all(action='DESELECT')
        
        if (bpy.context.scene.pixeler_vars.pixeler_cubebool == True):
            bpy.ops.object.mode_set( mode   = 'EDIT'   )
            bpy.ops.mesh.select_mode( type  = 'FACE'   )
            bpy.ops.mesh.select_all( action = 'SELECT' )

            bpy.ops.mesh.extrude_region_move(
                TRANSFORM_OT_translate={"value":(0, 0, 2)}
            )

            bpy.ops.object.mode_set( mode = 'OBJECT' )
        
        basemeshi.select_set(state=False)
        basemeshi.name = pixeler_file + " Mesh"
        basemesh.select_set(state=True)
        bpy.ops.object.delete() 
        bpy.context.scene.update()
        
        print("pixels to planes is done")
        return {'FINISHED'}

class PXL_PT_pixeler_panel(bpy.types.Panel):
    bl_idname = "view3d.pxl_pt_pixeler_panel"
    bl_label = "Pixeler - Pixels to Planes"
    bl_space_type ="VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Pixeler"

    def draw(self, context):
        layout = self.layout
        layout.operator("image.open", text="Open image", icon="PLUS")
        layout.prop(context.scene.pixeler_vars, "pixeler_images")
        layout.prop(context.scene.pixeler_vars, "pixeler_xoffset")
        layout.prop(context.scene.pixeler_vars, "pixeler_yoffset")
        layout.prop(context.scene.pixeler_vars, "pixeler_alpha")
        layout.prop(context.scene.pixeler_vars, "pixeler_simplify")
        layout.prop(context.scene.pixeler_vars, "pixeler_mergebool")
        layout.prop(context.scene.pixeler_vars, "pixeler_cubebool")
        layout.operator("mesh.pxl_ot_create_pixels", text="Pixeler", icon="PLAY")

classes = ( PXL_UI_variables, PXL_OT_create_pixels, PXL_PT_pixeler_panel )

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.pixeler_vars = PointerProperty(type = PXL_UI_variables)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.pixeler_vars 


if __name__ == "__main__":
    register()
