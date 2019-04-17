import maya.cmds as mc

def update_ctrl_set():
    #takes all ctrls in scene and regenerates ctrl set from them
    ctrls=mc.ls("*_Ctrl")
    ctrlSet="ctrlSet"
    if mc.objExists(ctrlSet):
        mc.delete(ctrlSet)
    mc.sets(ctrls, n=ctrlSet) 

def transfer_weights(shape_dict):
    #for new models, pass both and skin to same joints and transfer weights
    joints = mc.skinCluster(shape_dict['source']['shape'], influence=True, query=True)
    shape_dict['source']['cluster'] =mel.eval("findRelatedSkinCluster "+shape_dict['source']['shape']+";")
    shape_dict['dest']['cluster'] = mc.skinCluster(joints+[shape_dict['dest']['transform']], toSelectedBones=True, bindMethod=0, normalizeWeights=1, weightDistribution=0, maximumInfluences=5, obeyMaxInfluences=True, dropoffRate=4, removeUnusedInfluence=False)[0]
    mc.copySkinWeights(sourceSkin=shape_dict['source']['cluster'], destinationSkin=shape_dict['dest']['cluster'], noMirror=True, surfaceAssociation="closestPoint", influenceAssociation=("label", "oneToOne", "closestJoint"))
    print('Weights transferred from '+shape_dict['source']['transform']+' to '+shape_dict['dest']['transform']+'.')

def transfer_shader(shape_dict):
    SGs = [f for f  in mc.listConnections(shape_dict['source']['shape']) if mc.nodeType(f) == 'shadingEngine']
    if SGs:
        mc.sets(shape_dict['dest']['shape'], edit=True, forceElement=SGs[0])

def transfer_selected():
    # transfers skinning and shader from selected[0] to selected[1]
    shape_dict = {'source':{},'dest':{}}
    selected = mc.ls(selection=True, long=True)
    shape_keys = sorted(shape_dict.keys(), reverse=True)
    if len(selected) == 2:
        for i in range(len(shape_keys)):
            shape_dict[shape_keys[i]]['transform'] = selected[i]
            shape_dict[shape_keys[i]]['shape'] = mc.listRelatives(selected[i], children=True, path=True)[0]
        transfer_weights(shape_dict)
        transfer_shader(shape_dict)
    else:
        print("Please select exactly two meshes for transfer.")

def combine_selected(out_mesh='body_collider_Geo'):
    # duplicates and skins all selected meshes and then combines to make one skinned passive collider mesh for cloth
    shape_dict = {}
    selected = mc.ls(selection=True, long=True)
    for i in range(len(selected)):
        shape_dict[str(i).zfill(2)] = {'source': {'transform': '', 'shape': ''}, 'dest': {'transform': '', 'shape': ''}}
        shape_dict[str(i).zfill(2)]['source']['transform'] = selected[i]
        shape_dict[str(i).zfill(2)]['source']['shape'] = mc.listRelatives(selected[i], children=True, path=True)[0]
        new_geo = selected[i].split('|')[-1]+'_new'
        mc.duplicate(selected[i], name=new_geo)
        mc.parent(new_geo, world=True)
        shape_dict[str(i).zfill(2)]['dest']['transform'] = new_geo
        shape_dict[str(i).zfill(2)]['dest']['shape'] = mc.listRelatives(new_geo, children=True, path=True)[0]
    transfer_weights(shape_dict)
    dest_transforms = [v['dest']['transform'] for k, v in shape_dict.iteritems()]
    united = mc.polyUniteSkinned(dest_transforms, constructionHistory=False)
    mc.rename(united[0], out_mesh)
    mc.parent(out_mesh, 'collider_Geo_Grp')
    shader='sim_Gold_Mtl'
    if not mc.objExists(shader):
        mc.shadingNode('lambert', asShader=True, name=shader)
        mc.sets(name=shader+'SG', renderable=True, noSurfaceShader=True, empty=True)
        mc.connectAttr(shader+'.outColor',shader+'SG.surfaceShader', force=True)
    mc.sets(out_mesh, edit=True, forceElement=shader+'SG')
    mc.delete(dest_transforms)
    mc.setAttr(shader+'.color', 1, .7, 0, type='double3')

def dynamic_attributes():
    ctrl='Dynamic_Ctrl'
    reverse = 'dynMeshVisRev'
    mc.addAttr(ctrl, longName="dynamic", attributeType="bool")
    mc.setAttr(ctrl+'.dynamic', edit=True, channelBox=True)
    mc.connectAttr('Dynamic_Ctrl.dynamic', 'cloth_Nucleus.enable', force=True)
    bs_geo = mc.ls(sl=True, long=True)
    for geo in bs_geo:
        geo_pfx = geo.split('|')[-1].split('_')[0]
        source_geos = [g for g in mc.ls('*'+geo_pfx+'*', long=True) if 'GEO' in g and mc.nodeType(g) != 'mesh']
        if source_geos and len(source_geos)==1:
            source_geo = source_geos[0]
            bs_type = 'wrap'
            if '_sim_' in geo:
                bs_type = 'sim'
            mc.addAttr(ctrl, longName=geo_pfx+"Cloth",attributeType="double", min=0, max=1,defaultValue=1)
            mc.setAttr(ctrl+'.'+geo_pfx+'Cloth', edit=True, keyable=True)
            mc.blendShape([geo, source_geo], n=geo_pfx+'_BS')
            mc.reorderDeformers(geo_pfx+"_SkinClst", geo_pfx+"_BS", source_geo)
            mc.connectAttr(ctrl+'.'+geo_pfx+'Cloth', geo_pfx+'_BS.'+geo_pfx+'_'+bs_type+'_Geo')
    mc.addAttr(ctrl, longName="meshDisplay", attributeType="enum", en="mesh:sim:")
    mc.setAttr(ctrl+'.meshDisplay', edit=True, channelBox=True)
    mc.connectAttr('Dynamic_Ctrl.meshDisplay', 'CLOTH.visibility', force=True)
    mc.shadingNode('reverse', asUtility=True, name=reverse)
    mc.connectAttr('Dynamic_Ctrl.meshDisplay', reverse+'.inputX', force=True)
    mc.connectAttr(reverse+'.outputX', 'GEO.visibility', force=True)

def mouth_corners():
    corners_dict = {'posTX': 'wide',
                    'posTY': 'smile',
                    'posTZ': 'forward',
                    'revTX': 'narrow',
                    'revTY': 'frown',
                    'revTZ': 'back'}

    for attr, BS in corners_dict.iteritems():
        for side in ['Lf', 'Rt']:
            ctrl_attr = '_'.join([side, 'mouthCorner', 'Ctrl.'+attr])
            bs_target = '_'.join(['mouthCorners', 'BS.', side, BS, 'BS'])
            print('Connected '+ctrl_attr+ ' to '+bs_target)
            mc.connectAttr(ctrl_attr, bs_target, force=True)

def connect_cache(task='fxCloth'):
    # connect alembic cache cloth meshes to rig meshes via blendshapes
    geo_dict = {}
    cloth_geos = []
    # start by deleting existing clothSetup blendshape nodes if they exist
    clothSetup = [f for f in mc.ls(type='blendShape') if mc.attributeQuery('clothSetup', exists=True, node=f)]
    mc.delete(clothSetup)
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
            mc.blendShape([node_dict['cloth'], node_dict['mesh']], name=bs)
            mc.addAttr(bs, longName="clothSetup", attributeType="bool")
            mc.setAttr(bs+'.clothSetup', edit=True, channelBox=True)
            mc.connectAttr(abc_group+'.blendShapes', bs+'.'+geo_name.split(':')[-1], force=True)
            print("Creating {BS} with source {SRC} and destination {DST}".format(BS=bs, SRC=node_dict['cloth'], DST=node_dict['mesh']))
