# Pixeler development

Single-file Blender 5.0+ add-on: `pixeler.py`. The local `blender` MCP server is already registered in `~/.omp/agent/mcp.json` (`uvx mcp-for-blender`); Blender needs the "Interface: Blender MCP" add-on enabled and **Start MCP Server** clicked.

## Live edit loop

1. Edit the add-on source.
2. Reload it in Blender through `execute_blender_code`:
   `exec(open(r'C:/Users/benny/Documents/pixeler/dev/reload_addon.py').read())`
3. Create a test image with `bpy.data.images.new(...)`, assign `bpy.context.scene.pixeler_settings.image`, then call `bpy.ops.object.pixeler_create()`.
4. Inspect the evaluated object with `obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()` (call `to_mesh_clear()` afterward). `get_scene_info` and `look` inspect the live scene.
5. Remove test objects, images, orphan Pixeler node groups and material, and an empty `Pixeler` collection; leave the user's scene intact.

Blender 5 modifier socket values use `modifier.properties.inputs.<identifier>.value`, not `modifier[identifier]`. Interface identifiers are found in `group.interface.items_tree`; `pixeler.py:input_socket` handles lookup. Group sockets are created via `group.interface.new_socket`. Shader nodes should be found by `node.type` rather than localized name.
