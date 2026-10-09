# Pixeler development

Blender 5.0+ extension: source in `pixeler/__init__.py`, metadata in `pixeler/blender_manifest.toml` (keep its `version` in sync with releases). The local `blender` MCP server is already registered in `~/.omp/agent/mcp.json` (`uvx mcp-for-blender`); Blender needs the "Interface: Blender MCP" add-on enabled and **Start MCP Server** clicked.

## Live edit loop

1. Edit the add-on source.
2. Reload it in Blender through `execute_blender_code`:
   `exec(open(r'C:/Users/benny/Documents/pixeler/dev/reload_addon.py').read())`
3. Create a test image with `bpy.data.images.new(...)`, assign `bpy.context.scene.pixeler_settings.image`, then call `bpy.ops.object.pixeler_create()`.
4. Inspect the evaluated object with `obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()` (call `to_mesh_clear()` afterward). `get_scene_info` and `look` inspect the live scene.
5. Remove test objects, images, orphan Pixeler node groups and material, and an empty `Pixeler` collection; leave the user's scene intact.

Blender 5 modifier socket values use `modifier.properties.inputs.<identifier>.value`, not `modifier[identifier]`. Interface identifiers are found in `group.interface.items_tree`; `pixeler/__init__.py:input_socket` handles lookup by socket name. Inputs sit in interface panels (`new_panel`, `parent=` on `new_socket`); sidebar sub-panels mirror them through `bl_parent_id`. Setting `is_panel_toggle` renames the socket to its panel's name, so the Tilesheet and Animation checkboxes are the sockets called `Tilesheet` and `Animation`. Shader nodes should be found by `node.type` rather than localized name.

## Packaging check

`blender --factory-startup -b --command extension build --source-dir pixeler --output-dir dist`, then `extension install-file -r user_default -e dist/pixeler-<version>.zip` with `BLENDER_USER_RESOURCES` set to a scratch directory, and smoke-test in a background Blender. Use `--factory-startup`; third-party add-ons in the normal profile can break headless runs. Panels only fail when drawn, so also draw them live (wrap each `PIXELER_PT_*.draw` and force `bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP')`).
