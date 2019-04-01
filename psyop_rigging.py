import maya.cmds as mc

def update_ctrl_set():
  #takes all ctrls in scene and regenerates ctrl set from them
  ctrls=mc.ls("*_Ctrl")
  ctrlSet="ctrlSet"
  if mc.objExists(ctrlSet):
      mc.delete(ctrlSet)
  mc.sets(ctrls, n=ctrlSet) 



def transfer_weights(source_shape, dest_shape):
    #for new models, pass both and skin to same joints and transfer weights
    joints = mc.skinCluster(source_shape, influence=True, query=True)
    mc.skinCluster(dest_shape, toSelectedBones=True, bindMethod=0, normalizeWeights=1, weightDistribution=0, maximumInfluences=5, obeyMaxInfluences=True, dropoffRate=4, removeUnusedInfluence=False)
    mc.copySkinWeights(sourceSkin=source_shape, destinationSkin=dest_shape, noMirror=True, surfaceAssociation="closestPoint", influenceAssociation="label", influenceAssociation="oneToOne". influenceAssociation="closestJoint")
