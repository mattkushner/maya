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
    for key, value_dict in shape_dict.iteritems():
        joints = mc.skinCluster(value_dict['source']['shape'], influence=True, query=True)
        value_dict['source']['cluster'] =mel.eval("findRelatedSkinCluster "+value_dict['source']['shape']+";")
        value_dict['dest']['cluster'] = mc.skinCluster(joints+[value_dict['dest']['transform']], toSelectedBones=True, bindMethod=0, normalizeWeights=1, weightDistribution=0, maximumInfluences=5, obeyMaxInfluences=True, dropoffRate=4, removeUnusedInfluence=False)[0]
        mc.copySkinWeights(sourceSkin=value_dict['source']['cluster'], destinationSkin=value_dict['dest']['cluster'], noMirror=True, surfaceAssociation="closestPoint", influenceAssociation=("label", "oneToOne", "closestJoint"))

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
    
