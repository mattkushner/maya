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
    # takes selected skinned geo, duplicates as a new skinned combined mesh with a gold lambert shader for passive collisions
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
    mc.shadingNode('lambert', asShader=True, name=shader)
    mc.sets(name=shader+'SG', renderable=True, noSurfaceShader=True, empty=True)
    mc.connectAttr(shader+'.outColor',shader+'SG.surfaceShader', force=True)
    mc.sets(out_mesh, edit=True, forceElement=shader+'SG')
    mc.delete(dest_transforms)
    mc.setAttr(shader+'.color', 1, .7, 0, type='double3')
