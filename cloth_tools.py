"""cloth_tools.py"""
import maya.cmds as mc

def disconnect_cache():
    """Delete clothSetup blendshape nodes if they exist."""

    clothSetup = [f for f in mc.ls(type='blendShape') if mc.attributeQuery('clothSetup', exists=True, node=f)]
    if clothSetup:
        mc.delete(clothSetup)  


def connect_cache(task='fxCloth'):
    """Connect loaded caches by task to rig's geometry using blendshapes.
    
    Args:
        task (str, optional): Name of task for filtering alembic nodes by path
    """

    # connect alembic cache cloth meshes to rig meshes via blendshapes
    geo_dict = {}
    cloth_geos = []
    # start by deleting existing clothSetup blendshape nodes if they exist
    disconnect_cache()
    # generate dictionary of source and destination meshes
    alembics = [f for f in mc.ls(type='ExocortexAlembicFile') if task in mc.getAttr(f+'.fileName')]
    for alembic in alembics:
        geo_dict[alembic] = {}
        deform_connections = [f for f in mc.listConnections(alembic) if 'PolyMeshDeform' in mc.nodeType(f)]
        for deform_connection in deform_connections:
            geos = list(set([g for g in mc.listConnections(deform_connection) if g.endswith('Geo')]))
            if len(geos) == 1:
                geo_name = geos[0].split('|')[-1]
                geo_dict[alembic][geo_name] = {'cloth': '', 'mesh': ''}
                geo_matches = mc.ls('*'+geo_name, long=True)
                for geo_match in geo_matches:
                    if 'GEO' in geo_match:
                        geo_dict[alembic][geo_name]['mesh'] = geo_match
                    else:
                        geo_dict[alembic][geo_name]['cloth'] = geo_match
                        cloth_geos.append(geo_match)
            else:
                print('Not a single mesh:' + str(geos))
    # create blendshapes between cloth and mesh, group cloth, connect group blendShapes attr to each blendShape for global control
    for abc, abc_dict in geo_dict.iteritems():
        # setup group if needed, add blendshape attr, connect 
        abc_group = abc.replace(':','_')
        if not mc.objExists(abc_group):
            mc.group(world=True, empty=True, name=abc_group)
            mc.addAttr(abc_group, longName="blendShapes", attributeType="double", min=0, max=1, defaultValue=1)
            mc.setAttr(abc_group+'.blendShapes', edit=True, channelBox=True)
            mc.hide(abc_group)
        for geo_name, node_dict in abc_dict.iteritems():
            bs = geo_name+'_BS'
            mc.blendShape([node_dict['cloth'], node_dict['mesh']], name=bs, origin='world')
            mc.addAttr(bs, longName="clothSetup", attributeType="bool")
            mc.setAttr(bs+'.clothSetup', edit=True, channelBox=True)
            mc.connectAttr(abc_group+'.blendShapes', bs+'.'+geo_name.split(':')[-1], force=True)
            print("Creating {BS} with source {SRC} and destination {DST}".format(BS=bs, SRC=node_dict['cloth'], DST=node_dict['mesh']))
