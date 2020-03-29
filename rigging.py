import maya.cmds as mc

def reverse_leg_setup_bend(leg_name='l_b'):
    """Functiom to duplicate leg as a drv chain and set up two sets of iks for driving the leg. Self cleaning."""
    # setup iks
    leg_ctrl = '{L}_leg_foot_ctrl'.format(L=leg_name)
    bones = ['hip', 'knee', 'ankle', 'ball', 'toe']
    leg_jnts = ['{L}_{B}_jnt'.format(L=leg_name, B=b) for b in bones]
    drv_jnts = [l.replace('_jnt', '_drv_jnt') for l in leg_jnts]
    iks_dict = {'full': {'start': drv_jnts[0], 'end': drv_jnts[-2], 'parent': leg_ctrl, 'solver': 'ikRPsolver'},
                'upper': {'start': leg_jnts[0], 'end': leg_jnts[-3], 'parent': drv_jnts[-2], 'solver': 'ikRPsolver'},
                'lower': {'start': leg_jnts[-3], 'end': leg_jnts[-2], 'parent': drv_jnts[-3], 'solver': 'ikSCsolver'},
                'foot': {'start': leg_jnts[-2], 'end': leg_jnts[-1], 'parent': leg_ctrl, 'solver': 'ikSCsolver'}}
    for name, ik_dict in iks_dict.iteritems():
        ik_name = '{L}_{N}_ik'.format(L=leg_name, N=name)
        if mc.objExists(ik_name):
            mc.delete(ik_name) 
    if mc.objExists(drv_jnts[0]):
        mc.delete(drv_jnts[0])
    mc.duplicate(leg_jnts[0], name=drv_jnts[0])
    # rename drv children
    drv_kids = sorted(mc.listRelatives(drv_jnts[0], allDescendents=True, fullPath=True), key=lambda x: len(x), reverse=True)
    for i in range(len(drv_kids)):
        mc.rename(drv_kids[i], drv_jnts[-(i+1)])
    for name, ik_dict in iks_dict.iteritems():
       ik_name = '{L}_{N}_ik'.format(L=leg_name, N=name)
       ik = mc.ikHandle(startJoint=ik_dict['start'], endEffector=ik_dict['end'], solver=ik_dict['solver'])
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
        
def pole_vector(y=45, leg='l_b'):
    """Create a pole vector aim locator for the selected ik(s)"""
    aim_ctrl = '{L}_knee_aim_ctrl'.format(L=leg)
    selected = mc.ls(sl=1)
    for i in range(len(selected)):
        loc = mc.spaceLocator()
        loc_name = selected[i].replace('ik', 'aim')
        mc.rename(loc, loc_name)
        # get root jnt for ik chain from ik connections
        start_jnts = [j for j in mc.listConnections(selected[i]) if mc.nodeType(j) == 'joint']
        start_jnt = start_jnts[0]
        end_effetors = [j for j in mc.listConnections(selected[i]) if mc.nodeType(j) == 'ikEffector']
        end_jnts = [j for j in mc.listConnections(end_effetors[0]) if mc.nodeType(j) == 'joint']
        end_jnt = end_jnts[0]
        # move loc to root joint
        point = mc.pointConstraint(start_jnt, loc_name)
        mc.delete(point)
        # translate loc to root joint + poleVector values
        for axis in ['x', 'y', 'z']:
            pv = mc.getAttr(selected[i]+'.poleVector{AXIS}'.format(AXIS=axis.capitalize()))
            t = mc.getAttr(loc_name+'.translate{AXIS}'.format(AXIS=axis.capitalize()))
            mc.setAttr(loc_name+'.translate{AXIS}'.format(AXIS=axis.capitalize()), pv+t)
        # to orient on the pole vector plane, constrain to start and end jnts with ik as up vector
        constraint = mc.aimConstraint(start_jnt, end_jnt, loc_name, aimVector=[-1,0,0], upVector=[0,1,0], worldUpType='object', worldUpObject=selected[i])
        mc.delete(constraint)
        mc.move(0, y, 0, loc_name, relative=True, objectSpace=True, worldSpaceDistance=True) 
        #set up pole vector constraint
        mc.poleVectorConstraint(loc_name, selected[i])
        mc.parent(loc_name, aim_ctrl)
    
def toe_group_setup(toe_name='l_b_index'):
    """Function to create single plane iks, parent into hierarchy and set pivots so they can be controlled"""
    jnts_dict = {'end': {'name': '', 'translates': [0,0,0], 'child': '', 'grp': ''},
                 'claw': {'name': '', 'translates': [0,0,0], 'child': 'end', 'grp': ''},
                 'toe': {'name': '', 'translates': [0,0,0], 'child': 'claw', 'grp': ''},
                 'ball': {'name': '', 'translates': [0,0,0], 'child': 'toe', 'grp': ''},
                 'ankle': {'name': '', 'translates': [0,0,0], 'child': 'ball', 'grp': ''}}
    for name, jnt_dict in  jnts_dict.iteritems():
        ext = 'jnt_bnd'
        if name == 'end':
            ext = 'jnt'
        jnt = '{T}_{N}_{E}'.format(T=toe_name, N=name, E=ext)
        if jnt_dict['child'] == 'end':
            ext = 'jnt'
        child = '{T}_{C}_{E}'.format(T=toe_name, C=jnt_dict['child'], E=ext)
        jnts_dict[name]['name'] = jnt
        jnts_dict[name]['translates'] = mc.xform(jnt, query=True, worldSpace=True, translation=True)
        # create ik between jnt & child
        if name != 'end':
            ik = mc.ikHandle(startJoint=jnt, endEffector=child, solver='ikSCsolver')
            ik_name = '{T}_{N}_ik'.format(T=toe_name, N=name)
            grp_name = '{I}_grp'.format(I=ik_name).replace('_ik', 'Rotate')
            mc.rename(ik[0], ik_name)
            mc.group(ik_name, name=grp_name)
            jnts_dict[name]['grp'] = grp_name
            mc.move(jnts_dict[name]['translates'][0],jnts_dict[name]['translates'][1],jnts_dict[name]['translates'][2],'{G}.rotatePivot'.format(G=grp_name),'{G}.scalePivot'.format(G=grp_name), rpr=True)
            #connect ctrls to rotate grps
            ctrl = jnt.replace('_bnd', '').replace('jnt', 'ctrl')
            for attr in ['x', 'y', 'z']:
                mc.connectAttr('{C}.rotate{A}'.format(C=ctrl, A=attr.capitalize()), '{G}.rotate{A}'.format(G=grp_name, A=attr.capitalize()))
    # nest groups and add parents
    mc.parent(jnts_dict['claw']['grp'], jnts_dict['toe']['grp'])
    mc.parent(jnts_dict['toe']['grp'], jnts_dict['ball']['grp'])
    mc.parent(jnts_dict['ball']['grp'], jnts_dict['ankle']['grp'])
    grp = mc.group(jnts_dict['ankle']['grp'], name='{T}_heelRotate_grp'.format(T=toe_name))
    mc.move(jnts_dict['ankle']['translates'][0],0,jnts_dict['ankle']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{T}_heelPivot_grp'.format(T=toe_name))
    mc.move(jnts_dict['ankle']['translates'][0],0,jnts_dict['ankle']['translates'][2]+.01,'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{T}_ballPivot_grp'.format(T=toe_name))
    mc.move(jnts_dict['toe']['translates'][0],jnts_dict['toe']['translates'][1],jnts_dict['toe']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{T}_toePivot_grp'.format(T=toe_name))
    mc.move(jnts_dict['claw']['translates'][0],jnts_dict['claw']['translates'][1],jnts_dict['claw']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)    
    grp = mc.group(grp, name='{T}_toeStand_grp'.format(T=toe_name))
    mc.move(jnts_dict['claw']['translates'][0],jnts_dict['claw']['translates'][1],jnts_dict['claw']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{T}_clawPivot_grp'.format(T=toe_name))
    mc.move(jnts_dict['end']['translates'][0],jnts_dict['end']['translates'][1],jnts_dict['end']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)    
    grp = mc.group(grp, name='{T}_clawStand_grp'.format(T=toe_name))
    mc.move(jnts_dict['end']['translates'][0],jnts_dict['end']['translates'][1],jnts_dict['end']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    foot_ctrl = '{F}_leg_foot_ctrl'.format(F='_'.join(toe_name.split('_')[:2]))
    mc.parent(grp, foot_ctrl)
    for attr in ['heelRotate', 'heelPivot', 'ballPivot', 'toePivot', 'toeStand', 'clawPivot', 'clawStand']:
        axis = 'X'
        if attr.endswith('Pivot'):
            axis = 'Y'
        mc.connectAttr('{C}.{A}'.format(C=foot_ctrl, A=attr), '{T}_{A}_grp.rotate{X}'.format(T=toe_name, A=attr, X=axis), force=True)

def finger_group_setup(finger_name='l_f_index'):
    """Function to create single plane iks, parent into hierarchy and set pivots so they can be controlled"""
    jnts_dict = {'end': {'name': '', 'translates': [0,0,0], 'child': '', 'grp': ''},
                 'claw': {'name': '', 'translates': [0,0,0], 'child': 'end', 'grp': ''},
                 'finger': {'name': '', 'translates': [0,0,0], 'child': 'claw', 'grp': ''},
                 'palm': {'name': '', 'translates': [0,0,0], 'child': 'finger', 'grp': ''},
                 'wrist': {'name': '', 'translates': [0,0,0], 'child': 'palm', 'grp': ''}}
    if 'thumb' in finger_name:
        jnts_dict.pop('palm')
        jnts_dict['wrist']['child'] = 'finger'
    for name, jnt_dict in  jnts_dict.iteritems():
        ext = 'jnt_bnd'
        if name == 'end':
            ext = 'jnt'
        jnt = '{F}_{N}_{E}'.format(F=finger_name, N=name, E=ext)
        if jnt_dict['child'] == 'end':
            ext = 'jnt'
        child = '{F}_{C}_{E}'.format(F=finger_name, C=jnt_dict['child'], E=ext)
        jnts_dict[name]['name'] = jnt
        jnts_dict[name]['translates'] = mc.xform(jnt, query=True, worldSpace=True, translation=True)
        # create ik between jnt & child
        if name != 'end':
            ik = mc.ikHandle(startJoint=jnt, endEffector=child, solver='ikSCsolver')
            ik_name = '{F}_{N}_ik'.format(F=finger_name, N=name)
            grp_name = '{I}_grp'.format(I=ik_name).replace('_ik', 'Rotate')
            mc.rename(ik[0], ik_name)
            mc.group(ik_name, name=grp_name)
            jnts_dict[name]['grp'] = grp_name
            mc.move(jnts_dict[name]['translates'][0],jnts_dict[name]['translates'][1],jnts_dict[name]['translates'][2],'{G}.rotatePivot'.format(G=grp_name),'{G}.scalePivot'.format(G=grp_name), rpr=True)
            #connect ctrls to rotate grps
            ctrl = jnt.replace('jnt', 'ctrl')
            for attr in ['x', 'y', 'z']:
                mc.connectAttr('{C}.rotate{A}'.format(C=ctrl, A=attr.capitalize()), '{G}.rotate{A}'.format(G=grp_name, A=attr.capitalize()))
    # nest groups and add parents
    mc.parent(jnts_dict['claw']['grp'], jnts_dict['finger']['grp'])
    mc.parent(jnts_dict['finger']['grp'], jnts_dict['palm']['grp'])
    mc.parent(jnts_dict['palm']['grp'], jnts_dict['wrist']['grp'])
    grp = mc.group(jnts_dict['wrist']['grp'], name='{F}_wristRotate_grp'.format(F=finger_name))
    mc.move(jnts_dict['wrist']['translates'][0],0,jnts_dict['wrist']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{F}_wristPivot_grp'.format(F=finger_name))
    mc.move(jnts_dict['wrist']['translates'][0],0,jnts_dict['wrist']['translates'][2]+.01,'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{F}_palmPivot_grp'.format(F=finger_name))
    mc.move(jnts_dict['finger']['translates'][0],jnts_dict['finger']['translates'][1],jnts_dict['finger']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{F}_fingerPivot_grp'.format(F=finger_name))
    mc.move(jnts_dict['claw']['translates'][0],jnts_dict['claw']['translates'][1],jnts_dict['claw']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)    
    grp = mc.group(grp, name='{F}_fingerStand_grp'.format(F=finger_name))
    mc.move(jnts_dict['claw']['translates'][0],jnts_dict['claw']['translates'][1],jnts_dict['claw']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{F}_clawPivot_grp'.format(F=finger_name))
    mc.move(jnts_dict['end']['translates'][0],jnts_dict['end']['translates'][1],jnts_dict['end']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)    
    grp = mc.group(grp, name='{F}_clawStand_grp'.format(F=finger_name))
    mc.move(jnts_dict['end']['translates'][0],jnts_dict['end']['translates'][1],jnts_dict['end']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    foot_ctrl = '{F}_leg_foot_ctrl'.format(F='_'.join(finger_name.split('_')[:2]))
    mc.parent(grp, foot_ctrl)
    for attr in ['wristRotate', 'wristPivot', 'palmPivot', 'fingerPivot', 'fingerStand', 'clawPivot', 'clawStand']:
        axis = 'X'
        if attr.endswith('Pivot'):
            axis = 'Y'
        mc.connectAttr('{C}.{A}'.format(C=foot_ctrl, A=attr), '{F}_{A}_grp.rotate{X}'.format(F=finger_name, A=attr, X=axis), force=True)
