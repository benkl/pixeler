
# Pixeler
Pixels to planes Blender Plugin. Install or copy into the addons folder.

# Usage
Open/Add an image data block to your .blend and select the name (e.g. image.png) in the Image dropdown. Running the operator will then create a continuous plane with respective PBR materials for each face according to the source image pixel colour.

# History
2_1
New functionality.
  - Images can now be selected in a dropdown
  - Images can now be added from the addon UI
  - Extrude toggle
  - Merge/Remove Doubles toggle
  - Simplify colours toggle
  - Skip alpha = 0 pixels toggle
  - Node Group for centralized materials control (only supports metalness and roughness for now)

1_1
Port to Blender 2.8 without added functionality. The 2.79 Version can be found in the 'Blender_2.79' branch.

0_1
Blender 2.79 version 
  - Simple ui implementation
  - Image name input field
  - Modify x and y offset

# Further information
can be found in the system console while running the function. Reasonable file sizes and restricted colour palettes are recommended. 1000*1000 pixels is the tested working limit. Alpha channel transparency is supported.

https://blender.stackexchange.com/questions/88196/map-pixels-to-a-grid-of-faces/99090#99090

