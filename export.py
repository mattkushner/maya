import os
import maya.cmds as mc
parent_folder = '/Users/lkushner/Documents/SciBull-SciViz/OpenSpace/maya/exports/apollo/'
def obj_export(parent_folder):
  all_top_nodes = mc.ls(assemblies=True)
  # removes default cameras
  top_nodes = mc.ls(assemblies=True, tail=len(all_top_nodes)-4)
  for top_node in top_nodes:
      top_node_folder = os.path.join(parent_folder, top_node)
      geometry = mc.listRelatives(top_node, children=1)
      if not os.path.exists(top_node_folder):
          os.makedirs(top_node_folder)
      for geo in geometry:
          export_path = os.path.join(top_node_folder, geo+'.obj')
          mc.select(geo, replace=True)
          mc.file(export_path, force=True, options="groups=0;ptgroups=0;materials=1;smoothing=1;normals=1",typ="OBJexport",pr=1,es=1)
