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

def transfer_selected():
    shape_dict = {'source':{},'dest':{}}
    selected = mc.ls(selection=True, long=True)
    shape_keys = sorted(shape_dict.keys(), reverse=True)
    if len(selected) == 2:
        for i in range(len(shape_keys)):
            shape_dict[shape_keys[i]]['transform'] = selected[i]
            shape_dict[shape_keys[i]]['shape'] = mc.listRelatives(selected[i], children=True, path=True)[0]
        transfer_weights(shape_dict)
    else:
        print("Please select exactly two meshes for transfer.")
