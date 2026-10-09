# Pixeler

Pixeler turns an image into live pixel geometry in Blender 5.0+. Download `pixeler.py` from the [latest release](https://github.com/benkl/pixeler/releases/latest), then install it in Blender with **Edit → Preferences → Add-ons → Install from Disk** and enable the add-on.

## Use

1. Open an image in Blender. In the 3D View sidebar (**N**), open **Pixeler** and choose the image. The folder button can open another image.
2. Click **Create Pixel Geometry**. Pixeler makes one object in the `Pixeler` collection with a Geometry Nodes modifier; no per-pixel objects or materials are created.
3. Select that object to edit its live controls in the Pixeler sidebar or Geometry Nodes modifier:
   - **Image**: switch the source image; edits to image pixels update the object.
   - **Pixel Size**: width and depth of each plane or cube, in Blender units.
   - **Gap X / Gap Y**: additional spacing between pixels.
   - **Height**: `0` for planes; positive values make cubes resting on the XY plane.
   - **Skip Transparent**: remove pixels with zero alpha. Turn it off to keep their geometry; partially transparent pixels retain their alpha.
   - **Palette Steps**: `0` keeps original colors; positive values quantize straight RGB to that many steps between 0 and 1.

Pixels are centered around the object's origin; the bottom row of the image maps to negative Y. Pixeler stores `pixeler_color` and `pixeler_alpha` as geometry attributes and reads them in one shared `Pixeler Surface` material. Adjust that material's Principled BSDF for metalness, roughness, etc. Editing the shared node group or material affects all Pixeler objects in the file. To edit geometry directly, apply the modifier first. This is a clean cutover: existing objects made by the Blender 2.8 add-on are not converted automatically.

Large images produce many faces: roughly one face per visible pixel in plane mode or six in cube mode. Start with small images, especially when extruding. Saved `.blend` files keep the source image data block; pack external images if the file must be portable.

## Development

The `pre-ai` branch preserves the original Blender 2.8 implementation. This release uses Blender 5's typed Geometry Nodes modifier inputs. For local development, `dev/reload_addon.py` reloads the source in Blender through the Blender MCP `execute_blender_code` tool; its hard-coded path points to this checkout and must be changed on another machine. See `AGENTS.md` for the local test loop.
