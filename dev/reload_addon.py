"""Hot-reload pixeler.py from the repo into the running Blender.

Run through the Blender MCP (execute_blender_code) or from Blender's Text Editor.
Unregisters the previous copy (if any), re-executes the source file, registers it.
"""
import sys
import importlib.util
import bpy

REPO = r"C:/Users/benny/Documents/pixeler"
SRC = REPO + "/pixeler.py"
MOD = "pixeler_dev"

old = sys.modules.pop(MOD, None)
if old is not None:
    try:
        old.unregister()
    except Exception as e:  # half-registered state from a previous failure
        print("unregister failed:", e)

spec = importlib.util.spec_from_file_location(MOD, SRC)
mod = importlib.util.module_from_spec(spec)
sys.modules[MOD] = mod
spec.loader.exec_module(mod)
mod.register()
print("Pixeler loaded from", SRC, "| scene.pixeler_settings:", hasattr(bpy.types.Scene, "pixeler_settings"))
