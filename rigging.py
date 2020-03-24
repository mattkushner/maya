import maya.cmds as mc

def reverse_leg_setup(leg_name='l_b'):
    """Functiom to duplicate leg as a drv chain and set up two sets of iks for driving the leg."""
    leg_ctrl = '{L}_leg_foot_ctrl'.format(L=leg_name)
    bones = ['hip', 'knee', 'ankle', 'ball', 'toe']
    leg_jnts = ['{L}_{B}_jnt'.format(L=leg_name, B=b) for b in bones]
    drv_jnts = [l.replace('_jnt', '_drv_jnt') for l in leg_jnts] 
    mc.duplicate(leg_jnts[0], name=drv_jnts[0])
    # rename drv children
    drv_kids = sorted(mc.listRelatives(drv_jnts[0], allDescendents=True, fullPath=True), key=lambda x: len(x), reverse=True)
    for i in range(len(drv_kids)):
        mc.rename(drv_kids[i], drv_jnts[-(i+1)])
    # setup iks
    iks_dict = {'full': {'start': drv_jnts[0], 'end': drv_jnts[-2], 'parent': leg_ctrl, 'solver': 'ikRPsolver'},
                'upper': {'start': leg_jnts[0], 'end': leg_jnts[-3], 'parent': drv_jnts[-2], 'solver': 'ikRPsolver'},
                'lower': {'start': leg_jnts[-3], 'end': leg_jnts[-2], 'parent': drv_jnts[-3], 'solver': 'ikSCsolver'},
                'foot': {'start': leg_jnts[-2], 'end': leg_jnts[-1], 'parent': leg_ctrl, 'solver': 'ikSCsolver'}}
    for name, ik_dict in iks_dict.iteritems():
       ik = mc.ikHandle(startJoint=ik_dict['start'], endEffector=ik_dict['end'], solver=ik_dict['solver'])
       ik_name = '{L}_{N}_ik'.format(L=leg_name, N=name)
       mc.rename(ik[0], ik_name)
       mc.hide(ik_name)
       mc.parent(ik_name, ik_dict['parent'])
    mc.connectAttr(leg_ctrl+'.ankle_bend', drv_jnts[-2]+'.rotateZ')
    mc.hide(drv_jnts[0])

def locators_for_skinned_jnts(mesh, bind_pose=False):
    """Function to generate baked world space locators for skinned joints. TO DO: option to set locator origin to bind pose"""
    pcs = []
    locs = []
    jnts = mc.skinCluster(mesh, influence=True, query=True)
    mc.select(jnts, replace=True)
    #jnts = mc.ls(sl=1)
    transform_list = ['translateX', 'translateY', 'translateZ', 'rotateX', 'rotateY', 'rotateZ']
    start_frame = mc.playbackOptions(query=True, animationStartTime=True)
    end_frame = mc.playbackOptions(query=True, animationEndTime=True)
    for i in range(len(jnts)):
        loc_name = '{J}_loc'.format(J=jnts[i].split('|')[-1])
        loc = mc.spaceLocator()
        mc.rename(loc, loc_name)
        locs.append(loc_name)
        pc = mc.parentConstraint(jnts[i], loc_name)
        # if bind_pose, freeze transforms and re-constrain maintaining offset. still need logic to set bind pose
        if bind_pose:
            mc.delete(pc)
            pc = mc.parentConstraint(jnts[i], loc_name, maintainOffset=True)
        pcs.append(pc[0])
    mc.bakeResults(locs, simulation=True, t=(start_frame, end_frame), disableImplicitControl=1, preserveOutsideKeys=1, shape=False, at=transform_list)
    mc.delete(pcs)
        
def pole_vector():
    """Create a pole vector aim locator for the selected ik(s)"""
    selected = mc.ls(sl=1)
    for i in range(len(selected)):
        loc = mc.spaceLocator()
        loc_name = selected[i].replace('ik', 'aim')
        mc.rename(loc, loc_name)
        # get root jnt for ik chain from ik connections
        jnts = [j for j in mc.listConnections(selected[i]) if mc.nodeType(j) == 'joint']
        start_jnt = jnts[0]
        # move loc to root joint
        point = mc.pointConstraint(start_jnt, loc_name)
        mc.delete(point)
        # translate loc to root joint + poleVector values
        for axis in ['x', 'y', 'z']:
            pv = mc.getAttr(selected[i]+'.poleVector{AXIS}'.format(AXIS=axis.capitalize()))
            t = mc.getAttr(loc_name+'.translate{AXIS}'.format(AXIS=axis.capitalize()))
            mc.setAttr(loc_name+'.translate{AXIS}'.format(AXIS=axis.capitalize()), pv+t)
        # freeze transforms on loc, set up pole vector constraint
        mc.makeIdentity(loc_name, apply=True, translate=True, rotate=True, scale=True, normal=False, preserveNormals=True)
        mc.poleVectorConstraint(loc_name, selected[i])    
    
def toe_group_setup(toe_name='l_b_index'):
    """Function to create single plane iks, parent into hierarchy and set pivots so they can be controlled"""
    jnts_dict = {'toe': {'name': '', 'translates': [0,0,0], 'child': 'claw', 'grp': ''},
                'ball': {'name': '', 'translates': [0,0,0], 'child': 'toe', 'grp': ''},
                'ankle': {'name': '', 'translates': [0,0,0], 'child': 'ball', 'grp': ''}}
    for name, jnt_dict in  jnts_dict.iteritems():
        jnt = '{T}_{N}_jnt'.format(T=toe_name, N=name)
        child = '{T}_{C}_jnt'.format(T=toe_name, C=jnt_dict['child'])
        jnts_dict[name]['name'] = jnt
        jnts_dict[name]['translates'] = mc.xform(jnt, query=True, worldSpace=True, translation=True)
        # create ik between jnt & child
        ik = mc.ikHandle(startJoint=jnt, endEffector=child, solver='ikSCsolver')
        ik_name = '{T}_{N}_ik'.format(T=toe_name, N=name)
        grp_name = '{I}_grp'.format(I=ik_name).replace('_ik', 'Rotate')
        mc.rename(ik[0], ik_name)
        mc.group(ik_name, name=grp_name)
        jnts_dict[name]['grp'] = grp_name
        mc.move(jnts_dict[name]['translates'][0],jnts_dict[name]['translates'][1],jnts_dict[name]['translates'][2],'{G}.rotatePivot'.format(G=grp_name),'{G}.scalePivot'.format(G=grp_name), rpr=True)
    # nest groups and add parents
    mc.parent(jnts_dict['toe']['grp'], jnts_dict['ball']['grp'])
    mc.parent(jnts_dict['ball']['grp'], jnts_dict['ankle']['grp'])
    grp = mc.group(jnts_dict['ankle']['grp'], name='{T}_heelRotate_grp'.format(T=toe_name))
    mc.move(jnts_dict['ankle']['translates'][0],0,jnts_dict['ankle']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{T}_heelPivot_grp'.format(T=toe_name))
    mc.move(jnts_dict['ankle']['translates'][0],0,jnts_dict['ankle']['translates'][2]+.01,'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{T}_ballPivot_grp'.format(T=toe_name))
    mc.move(jnts_dict['ball']['translates'][0],jnts_dict['ball']['translates'][1],jnts_dict['ball']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{T}_toePivot_grp'.format(T=toe_name))
    mc.move(jnts_dict['toe']['translates'][0],jnts_dict['toe']['translates'][1],jnts_dict['toe']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{T}_toeStand_grp'.format(T=toe_name))
    mc.move(jnts_dict['toe']['translates'][0],jnts_dict['toe']['translates'][1],jnts_dict['toe']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
