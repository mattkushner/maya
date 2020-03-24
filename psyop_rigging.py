import maya.cmds as mc
import maya.mel as mel

def update_ctrl_set():
    #takes all ctrls in scene and regenerates ctrl set from them
    ctrls=mc.ls("*_Ctrl")
    ctrlSet="ctrlSet"
    if mc.objExists(ctrlSet):
        mc.delete(ctrlSet)
    mc.sets(ctrls, n=ctrlSet) 

def add_ctrl_vis():
    # psyop: connect control vis
    master= 'head_Ctrl'
    ctrls = ['brow', 'nose', 'cheek', 'teeth', 'mouth', 'tongue']
    for ctrl in ctrls:
        attr = ctrl+'CtrlVis'
        grp = ctrl+'_CTRL_Grp'
        if ctrl == 'mouth':
            grp = ctrl+'Move_Prnt_Grp'
        mc.addAttr(master, ln=attr, at='bool')
        mc.setAttr(master+'.'+attr, edit=True, channelBox=True)
        mc.connectAttr(master+'.'+attr, grp+'.visibility')

def unlock_normals_soften():
    # psyop: unlock normals, soften, delete non-deformer history
    selected = mc.ls(sl=1)
    for each in selected:
        mc.polyNormalPerVertex(each, ufn=True)
        mc.polySoftEdge(each, angle=180, constructionHistory=True)
    mel.eval('doBakeNonDefHistory( 1, {"prePost" });')

def jaw_corrective_loc():
    # psyop: facial jaw setup
    constraint = mc.parentConstraint('jaw_Jnt', 'jaw_Jnt_Loc_Grp')
    mc.delete(constraint)
    mc.parentConstraint('neck_end_Jnt', 'jaw_Jnt_Loc_Grp', mo=True)
    mc.orientConstraint('jaw_Jnt', 'jaw_Jnt_Loc')

    mc.parentConstraint('jaw_Jnt', 'teethBot_Ctrl_Grp', mo=True)
    mc.parentConstraint('jaw_Jnt', 'tongue_CTRL_Grp', mo=True)     
   
def transfer_weights(shape_dict):
    #for new models, pass new, old and skin to same joints and transfer weights
    joints = mc.skinCluster(shape_dict['source']['shape'], influence=True, query=True)
    shape_dict['source']['cluster'] =mel.eval("findRelatedSkinCluster "+shape_dict['source']['shape']+";")
    shape_dict['dest']['cluster'] = mc.skinCluster(joints+[shape_dict['dest']['transform']], toSelectedBones=True, bindMethod=0, normalizeWeights=1, weightDistribution=0, maximumInfluences=5, obeyMaxInfluences=True, dropoffRate=4, removeUnusedInfluence=False)[0]
    mc.copySkinWeights(sourceSkin=shape_dict['source']['cluster'], destinationSkin=shape_dict['dest']['cluster'], noMirror=True, surfaceAssociation="closestPoint", influenceAssociation=("label", "oneToOne", "closestJoint"))

        
def transfer_shader(shape_dict):
    SGs = [f for f  in mc.listConnections(shape_dict['source']['shape']) if mc.nodeType(f) == 'shadingEngine']
    if SGs:
        mc.sets(shape_dict['dest']['shape'], edit=True, forceElement=SGs[0])
        
def transfer_selected(shader=False):
    # transfers skinning and shader from selected[0] to selected[1]
    shape_dict = {'source':{},'dest':{}}
    selected = mc.ls(selection=True, long=True)
    shape_keys = sorted(shape_dict.keys(), reverse=True)
    if len(selected) == 2:
        for i in range(len(shape_keys)):
            shape_dict[shape_keys[i]]['transform'] = selected[i]
            shape_dict[shape_keys[i]]['shape'] = mc.listRelatives(selected[i], children=True, path=True)[0]
        transfer_weights(shape_dict)
        if shader:
            transfer_shader(shape_dict)
    else:
        print("Please select exactly two meshes for transfer.")

def combine_selected(out_mesh='body_collider_Geo', shader=False):
    # duplicates and skins all selected meshes and then combines to make one skinned passive collider mesh for cloth
    shape_dict = {}
    selected = mc.ls(selection=True, long=True)
    dest_transforms = []
    for i in range(len(selected)):
        shape_dict = {'source': {'transform': '', 'shape': ''}, 'dest': {'transform': '', 'shape': ''}}
        shape_dict['source']['transform'] = selected[i]
        shape_dict['source']['shape'] = mc.listRelatives(selected[i], children=True, path=True)[0]
        new_geo = selected[i].split('|')[-1]+'_new'
        mc.duplicate(selected[i], name=new_geo)
        # unlock transforms before parenting to avoid world space issues
        for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz', 'v']:
            mc.setAttr('{GEO}.{ATTR}'.format(GEO=new_geo, ATTR=attr), lock=False)
        mc.parent(new_geo, world=True)
        shape_dict['dest']['transform'] = new_geo
        shape_dict['dest']['shape'] = mc.listRelatives(new_geo, children=True, path=True)[0]
        transfer_weights(shape_dict)
        dest_transforms.append(new_geo)
    united = mc.polyUniteSkinned(dest_transforms, constructionHistory=False)
    mc.rename(united[0], out_mesh)
    mc.delete(dest_transforms)
    mc.parent(out_mesh, 'collider_Geo_Grp')
    if shader:
    shader_name='sim_Gold_Mtl'
        if not mc.objExists(shader_name):
            mc.shadingNode('lambert', asShader=True, name=shader_name)
            mc.sets(name=shader_name+'SG', renderable=True, noSurfaceShader=True, empty=True)
            mc.connectAttr(shader_name+'.outColor',shader_name+'SG.surfaceShader', force=True)
            mc.setAttr(shader_name+'.color', 1, .7, 0, type='double3')
        mc.sets(out_mesh, edit=True, forceElement=shader_name+'SG')

def dynamic_attributes():
    # psyop:
    # sets up dynamic attributes
    # dynamic to connect to nucleus
    # blendshape toggles for each geo
    # meshDisplay toggle between GEO & CLOTH groups
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
    # psyop: connect the ctrl attrs to the blendshape target attrs for mouth corners
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

def fix_RNs():
    mc.namespace(setNamespace=':')
    root_namespaces = mc.namespaceInfo(listOnlyNamespaces=True, recurse=False)
    for ns in root_namespaces:
        try:
            ns_nodes = [f for f in mc.namespaceInfo(ns, listNamespace=True) if mc.objectType(f) == 'transform']
            if ns_nodes:
                new_rn = ns+'RN'
                rn = mc.referenceQuery(ns_nodes[0], referenceNode=True)
                # if somehow there is already a reference node of the needed name, fix it's name first
                if mc.objExists(new_rn):
                    mc.lockNode(new_rn, lock=False)
                    fix_rn = mc.referenceQuery('crt0045_fxCloth_v006RN', namespace=True)
                    mc.rename(new_rn, fix_rn+'NS')
                    mc.lockNode(fix_rn, lock=True)
                else:
                    if not ns+'RN' == rn:
                        mc.lockNode(rn, lock=False)
                        mc.rename(rn, new_rn)
                        mc.lockNode(new_rn, lock=True)
        except:
            pass

def all_CHAR_ctrls(parent_grp='CHAR', root='cRoot'):
    # select all character ctrls from sets, where the rig root is root and the parent of the rigs is parent_grp
    rig_namespaces = [f for f in mc.namespaceInfo(listOnlyNamespaces=True, recurse=False) if mc.namespaceInfo(f, listNamespace=True) and f+':'+root in  mc.namespaceInfo(f, listNamespace=True)]
    char_namespaces = [f for f in rig_namespaces if mc.listRelatives(f+':'+root, parent=True) and mc.listRelatives(f+':'+root, parent=True)[0] == parent_grp]
    all_set_members = []
    for char_ns in char_namespaces:
        set_members = mc.sets(char_ns+':ctrlSet', query=True)
        all_set_members += set_members
    mc.select(all_set_members, replace=True)

def generate_modeling_data(top_node='GEO', yaml_path=r'C:\Users\mkushner\cortevaWorker.yaml'):
    geometry = [str(mc.listRelatives(f, parent=True, fullPath=True)[0]) for f in mc.listRelatives(top_node, allDescendents=True, fullPath=True) if mc.objectType(f) == 'mesh']
    data_dict = {}
    base_dict = {'vertex': 3, 'uv': 2}
    for geo in geometry:
        data_dict[geo] = {}
        for key, value in base_dict.iteritems():
            arg_dict = {key: True}
            num = mc.polyEvaluate(geo, **arg_dict)
            if key == 'vertex':
                data =  mc.xform('{GEO}.vtx[*]'.format(GEO=geo), query=True, worldSpace=True, translation=True)
            elif key == 'uv':
                data = mc.polyEditUV('{GEO}.map[*]'.format(GEO=geo), query=True, u=True, v=True)
            data_dict[geo][key] = {k: v for k, v in zip(range(num), [list(t) for t in zip(*[iter(data)]*value)])}
    createYaml(data_dict, yaml_path)

def follicle_constraint():
    #parse selection for ctrl (assumes ctrl has a parent grp for constraint), then geo
    selected = mc.ls(sl=True)
    if len(selected) == 2:
        ctrl, geo = selected
        ctrl_grp = mc.listRelatives(ctrl, parent=True)[0]
        # create closestPointOnMesh to calculate where the follicle should go in u & v
        closest = mc.createNode('closestPointOnMesh')
        mc.connectAttr(geo+'.outMesh', closest+'.inMesh')
        trans = mc.xform(ctrl, translation=True, query=True)
        mc.setAttr(closest+'.inPositionX', trans[0])
        mc.setAttr(closest+'.inPositionY', trans[1])
        mc.setAttr(closest+'.inPositionZ', trans[2])
        # create follicle and rename based on ctrl
        follicle_transform = ctrl+'_follicle'
        follicle_shape = follicle_transform+'Shape'
        follicle = mc.createNode('follicle')
        mc.rename(follicle, follicle_shape)
        follicle = mc.listRelatives(follicle_shape, type='transform', parent=True)[0]
        mc.rename(follicle, follicle_transform)
        # connect follicle_shape & transform
        mc.connectAttr(follicle_shape+'.outRotate', follicle_transform+'.rotate')
        mc.connectAttr(follicle_shape+'.outTranslate', follicle_transform+'.translate')
        # connect geo to follicle
        mc.connectAttr(geo+'.worldMatrix', follicle_shape+'.inputWorldMatrix')
        mc.connectAttr(geo+'.outMesh', follicle_shape+'.inputMesh')
        mc.setAttr(follicle_shape+'.simulationMethod', 0)
        # determine u & v, parent constrain grp to follicle
        u = mc.getAttr(closest+'.result.parameterU')
        v = mc.getAttr(closest+'.result.parameterV')
        mc.setAttr(follicle_shape+'.parameterU', u)
        mc.setAttr(follicle_shape+'.parameterV', v)
        mc.parentConstraint(follicle_transform, ctrl_grp, mo=True)
        # delete closestPointOnMesh node
        mc.delete(closest)
        
import maya.OpenMaya as om
import maya.cmds as mc
import math

def pole_vector_math()

    sel = mc.ls(sl = 1)
    # get transforms
    start = mc.xform(sel[0] ,q= 1 ,ws = 1,t =1 )
    mid = mc.xform(sel[1] ,q= 1 ,ws = 1,t =1 )
    end = mc.xform(sel[2] ,q= 1 ,ws = 1,t =1 )
    # get vectors
    startV = om.MVector(start[0] ,start[1],start[2])
    midV = om.MVector(mid[0] ,mid[1],mid[2])
    endV = om.MVector(end[0] ,end[1],end[2])

    startEnd = endV - startV
    startMid = midV - startV

    dotP = startMid * startEnd
    proj = float(dotP) / float(startEnd.length())
    startEndN = startEnd.normal()
    projV = startEndN * proj

    arrowV = startMid - projV
    arrowV*= 0.5
    finalV = arrowV + midV

    cross1 = startEnd ^ startMid
    cross1.normalize()

    cross2 = cross1 ^ arrowV
    cross2.normalize()
    arrowV.normalize()

    matrixV = [arrowV.x , arrowV.y , arrowV.z , 0 ,
               cross1.x ,cross1.y , cross1.z , 0 ,
               cross2.x , cross2.y , cross2.z , 0,
               0,0,0,1]

    matrixM = om.Matrix()

    om.MScriptUtil.createMatrixFromList(matrixV , matrixM)

    matrixFn = om.MTransformationMatrix(matrixM)

    rot = matrixFn.eulerRotation()

    loc = mc.spaceLocator()[0]
    mc.xform(loc , ws =1 , t= (finalV.x , finalV.y ,finalV.z))

    mc.xform ( loc , ws = 1 , rotation = ((rot.x/math.pi*180.0),
             (rot.y/math.pi*180.0),
             (rot.z/math.pi*180.0)))
