"""Summary
"""
#modified by Zed Bennett 7/10/2008 modified by Matt Kushner 5/20/2019
#to allow more convenient scalability of objects parented constrained to follicles
#all of the hard stuff belongs to the original author of parentToSurface
#----------------------------------------------------------------------------------------
# constrainToSurface
# This mel command allows one to attach selected objects to a selected mesh or nurbs surface.
# The objects will follow any deformation or transformation of the surface.
# Usage: put this script in your local scripts directory. In Maya select object(s) to attach
#        followed by a mesh or nurbs surface to attach then enter "parentToSurface" in the
#        command line. A follicle node will be created at the point on surface closest to
#        the center of the object and the object will be parented to this follicle. Note that
#	    if the surface to attach to is a mesh it must have well defined UVs that range from 0-1
#	    with no areas sharing the same value.
#
#        For convenience drag the constrainToSurface string onto the shelf to make a shelf button.
# 
# This command uses the follicle node, which is normally used by the hair system. The follicle node
# is currently the only node in maya that can derive a rotate and translate based on a uv position
# for both meshes and nurbs surfaces.
#
# One use of this script might be to attach buttons to a cloth object, or any deforming surface. To
# attach several buttons, first position the buttons where desired then select them followed by the
# object to attach to and run this command.
# For more info or to report problems with this script go to Duncan's Corner:
# http://area.autodesk.com/blogs/blog/7/

import maya.cmds as mc

def convert_to_cm_factor():
	"""Convert current units to cm for nearestPointOnMesh plugin bug.
	
	Returns:
	    float: cm conversion from current units
	"""
	unit = mc.currentUnit(query=True, linear=True)
	if unit == "mm":
		return 0.1
	elif unit == "cm":
		return 1.0
	elif unit == "m":
		return 100.0
	elif unit == "in":
		return 2.54
	elif unit == "ft":
		return 30.48
	elif unit == "yd":
		return 91.44
	else:
		return 1.0


def attach_obj_to_surface(obj, surface, u, v):
	"""Create a follicle on surface, point constrain obj to follicle
	
	Args:
	    obj (str): Object to point constrain to surface
	    surface (str): Surface to create follicle on and constrain to
	    u (float): U value for setting follicle parameter
	    v (float): V value for setting follicle parameter
	"""
	fol_trans = '{OBJ}_fol'.format(OBJ=obj)
	fol = mc.createNode('follicle')
	transforms = mc.listRelatives(fol, parent=True, path=True)
	mc.rename(transforms[0], fol_trans)
	fol_shape = '{FOL}Shape'.format(FOL=fol_trans)
	
	mc.connectAttr(surface + ".worldMatrix[0]", fol_shape + ".inputWorldMatrix")
	node_type = mc.nodeType(surface)
	if node_type == "nurbsSurface": 
		mc.connectAttr(surface + ".local", fol_shape + ".inputSurface")
	else:
		mc.connectAttr(surface + ".outMesh", fol_shape + ".inputMesh")
	mc.connectAttr(fol_shape + ".outTranslate", fol_trans + ".translate")
	mc.connectAttr(fol_shape + ".outRotate", fol_trans + ".rotate")
	mc.setAttr(fol_trans+'.translate', lock=True)
	mc.setAttr(fol_trans+'.rotate', lock=True)
	mc.setAttr(fol_shape + ".parameterU", u)
	mc.setAttr(fol_shape + ".parameterV", v)
	
	mc.pointConstraint(fol_trans, obj, maintainOffset=True)
	mc.orientConstraint(fol_trans, obj, maintainOffset=True)


def constrain_to_surface():
	"""Constrain all in selection to last in selection using follicles and point constraints."""
	selected = mc.ls(selection=True)
	if len(selected) < 2:
		mc.warning("ParentToSurface: select object(s) to parent followed by a mesh or nurbsSurface to attach to.")
		return
	# surface is last selected, if transform, get shape instead
	surface = selected[-1]
	if mc.nodeType(surface) == "transform":
		shapes = mc.ls(surface, dagObjects=True, shapes=True, noIntermediate=True, visible=True)
		if len(shapes) > 0:
			surface = shapes[0]
	node_type = mc.nodeType(surface)
	if node_type != "mesh" and node_type != "nurbsSurface":
		warning( "ParentToSurface: Last selected item must be a mesh or nurbsSurface.")
		return

	uv_dict = {'u': {}, 'v': {}}

	# for nurbs meshes
	if node_type == "nurbsSurface":
		closest_point = mc.createNode('closestPointOnSurface')	
		mc.connectAttr(surface + ".worldSpace[0]", closest_point + ".inputSurface")
		for uv in ['u', 'v']:
			uv_dict[uv]['min'] = mc.getAttr('{SURFACE}.mn{UV}'.float(SURFACE=surface, UV=uv))
			uv_dict[uv]['max']= mc.getAttr('{SURFACE}.mx{UV}'.float(SURFACE=surface, UV=uv))
			uv_dict[uv]['size']= uv_dict[uv]['max'] - uv_dict[uv]['min']

	# for poly meshes, use nearestPointOnMesh plugin
	else:
		if not mc.pluginInfo('nearestPointOnMesh', query=True, loaded=True):
			try:
				mc.loadPlugin('nearestPointOnMesh')
			except:
				mc.warning( "ParentToSurface: Can't load nearestPointOnMesh plugin.")
				return

		#The following is to overcome a units bug in the nearestPointOnMesh plugin
		#If at some point it correctly handles units, then we need to take out the following conversion factor.	
		convert_factor = convert_to_cm_factor()

		closest_point = mc.createNode('nearestPointOnMesh')
		mc.connectAttr(surface + ".worldMesh", closest_point + ".inMesh")
	
	# iterate through all but last of selected list to attach to surface
	for i in range(len(selected)-1):
		obj = selected[i]
		if mc.nodeType(obj)!= "transform":
			if mc.listRelatives(obj, parent=True):
				obj = mc.listRelatives(obj, parent=True)[0]
				if mc.nodeType(obj) != 'transform':
					warning( "ParentToSurface: select the transform of the node(s) to constrain\n")
					continue
			else:	
				warning( "ParentToSurface: select the transform of the node(s) to constrain\n")
				continue
		# get the closest point on surface by uv
		if node_type == "nurbsSurface":
			for uv in ['u', 'v']:
				uv_dict[uv]['closest'] = (uv_dict[uv]['closest']+uv_dict[uv]['min'])/uv_dict[uv]['size']
		else:
			bbox = mc.xform(obj, query=True, worldSpace=True, boundingBox=True)
			pos = [(bbox[0] + bbox[3])*0.5, (bbox[1] + bbox[4])*0.5, (bbox[2] + bbox[5])*0.5]
			mc.setAttr(closest_point + ".inPosition", pos[0]*convert_factor, pos[1]*convert_factor, pos[2]*convert_factor, type='double3') 
			for uv in ['u', 'v']:
				uv_dict[uv]['closest'] = mc.getAttr('{POINT}.parameter{UV}'.format(POINT=closest_point, UV=uv.capitalize()))


		attach_obj_to_surface(obj, surface, uv_dict['u']['closest'], uv_dict['v']['closest'])

	# delete closest point node
	if closest_point != "":
		mc.delete(closest_point)


constrain_to_surface()
