import maya.cmds as mc

import collections
def reverse_leg_setup_spring(leg_name='l_b'):
    """Functiom to duplicate leg as a drv chain and set up two sets of iks for driving the leg. Self cleaning."""
    # setup iks
    leg_ctrl = '{L}_leg_foot_ctrl'.format(L=leg_name)
    bones = ['hip', 'knee', 'ankle', 'ball', 'toe']
    leg_jnts = ['{L}_{B}_jnt'.format(L=leg_name, B=b) for b in bones]
    drv_jnts = [l.replace('_jnt', '_drv_jnt') for l in leg_jnts]
    iks_dict = collections.OrderedDict()
    iks_dict['drv_sc'] = {'start': leg_jnts[3], 'end': leg_jnts[4], 'solver': 'ikSCsolver'}
    iks_dict['drv_sp'] = {'start': drv_jnts[0], 'end': drv_jnts[3], 'solver': 'ikRPsolver', 'pole': 'aim'}
    iks_dict['bnd_sc'] = {'start': leg_jnts[3], 'end': leg_jnts[4], 'solver': 'ikSCsolver'}
    iks_dict['bnd_rp'] = {'start': leg_jnts[1], 'end': leg_jnts[3], 'solver': 'ikRPsolver', 'pole': 'ankleTwist'}
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
    # locator setups (aim & twist)
    locs_dict = {'aim': {'parent': drv_jnts[1], 'move': [0, -16, -25]},
                 'ankleTwist': {'parent': leg_jnts[3], 'move': [10, 0, 0]}}
    for name, loc_dict in locs_dict.iteritems():
        # name, parent under jnt, zero out, move locally
        loc_name = '{L}_leg_{N}_loc'.format(L=leg_name, N=name)
        if mc.objExists(loc_name):
            mc.delete(loc_name)
        mc.spaceLocator(name=loc_name)
        mc.parent(loc_name, loc_dict['parent'])
        for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz']:
            mc.setAttr('{L}.{A}'.format(L=loc_name, A=attr), 0)
        # move out from ik locally, unparent and set up poleVector
        if leg_name.startswith('r_'):
            loc_dict['move'] = [-x for x in loc_dict['move']]
        mc.move(loc_dict['move'][0], loc_dict['move'][1], loc_dict['move'][2], loc_name, relative=True, objectSpace=True, worldSpaceDistance=True)
        mc.parent(loc_name, world=True)  
    for name, ik_dict in iks_dict.iteritems():
       ik_name = '{L}_{N}_ik'.format(L=leg_name, N=name)
       ik = mc.ikHandle(startJoint=ik_dict['start'], endEffector=ik_dict['end'], solver=ik_dict['solver'], sticky=0)
       if name == 'drv_sp':
           if not mc.pluginInfo('ikSpringSolver.mll', query=True, loaded=True):
               mc.loadPlugin('ikSpringSolver.mll')
           mc.connectAttr('ikSpringSolver.message', '{I}.ikSolver'.format(I=ik[0]), force=True)
       mc.rename(ik[0], ik_name)
       # set up pole vectors
       if 'pole' in ik_dict.keys():
           loc_name = '{L}_leg_{P}_loc'.format(L=leg_name, P=ik_dict['pole'])
           mc.poleVectorConstraint(loc_name, ik_name)
           # twist setup
           twist = -90
           if 'ankleTwist' in loc_name:
               if leg_name.startswith('r_'):
                   twist = -twist
               mc.setAttr('{I}.offset'.format(I=ik_name), twist)
               plus = loc_name.replace('_loc', '_plus')
               if mc.objExists(plus):
                   mc.delete(plus)
               mc.shadingNode('plusMinusAverage', asUtility=True, name=plus)
               mc.connectAttr('{L}.ankleTwist'.format(L=leg_ctrl), '{P}.input1D[0]'.format(P=plus), force=True)
               mc.connectAttr('{I}.offset'.format(I=ik_name), '{P}.input1D[1]'.format(P=plus), force=True)
               mc.connectAttr('{P}.output1D'.format(P=plus), '{I}.twist'.format(I=ik_name), force=True)
       mc.hide(ik_name)
       mc.parent(ik_name, leg_ctrl)
    mc.parent(leg_jnts[0], drv_jnts[0])
    mc.hide(drv_jnts[1])
    # set up hip ctrl
    hip_ctrl = '{L}_leg_hip_ctrl'.format(L=leg_name)
    hip_ctrl_grp = hip_ctrl+'_grp'
    mc.orientConstraint(drv_jnts[0], hip_ctrl_grp) 
    mc.orientConstraint(hip_ctrl, leg_jnts[0])
        

def reverse_leg_setup_bend(leg_name='l_b'):
    """Functiom to duplicate leg as a drv chain and set up two sets of iks for driving the leg, with ankle bend. Self cleaning."""
    # setup iks
    leg_ctrl = '{L}_leg_foot_ctrl'.format(L=leg_name)
    bones = ['hip', 'knee', 'ankle', 'ball', 'toe']
    leg_jnts = ['{L}_{B}_jnt'.format(L=leg_name, B=b) for b in bones]
    drv_jnts = [l.replace('_jnt', '_drv_jnt') for l in leg_jnts]
    iks_dict = {'full': {'start': drv_jnts[0], 'end': drv_jnts[3], 'parent': leg_ctrl, 'solver': 'ikRPsolver'},
                'upper': {'start': leg_jnts[0], 'end': leg_jnts[2], 'parent': drv_jnts[-2], 'solver': 'ikRPsolver'},
                'lower': {'start': leg_jnts[2], 'end': leg_jnts[3], 'parent': drv_jnts[-3], 'solver': 'ikSCsolver'},
                'foot': {'start': leg_jnts[3], 'end': leg_jnts[4], 'parent': leg_ctrl, 'solver': 'ikSCsolver'}}
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

def finger_group_setup(toe_name='l_f_index'):
    """Function to create single plane iks, parent into hierarchy and set pivots so they can be controlled"""
    jnts_dict = {'end': {'name': '', 'translates': [0,0,0], 'child': '', 'grp': ''},
                 'claw': {'name': '', 'translates': [0,0,0], 'child': 'end', 'grp': ''},
                 'finger': {'name': '', 'translates': [0,0,0], 'child': 'claw', 'grp': ''},
                 'palm': {'name': '', 'translates': [0,0,0], 'child': 'finger', 'grp': ''},
                 'wrist': {'name': '', 'translates': [0,0,0], 'child': 'palm', 'grp': ''}}
    if 'thumb' in toe_name:
        jnts_dict.pop('wrist')
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
            ctrl = jnt.replace('jnt_bnd', 'ctrl')
            for attr in ['x', 'y', 'z']:
                mc.connectAttr('{C}.rotate{A}'.format(C=ctrl, A=attr.capitalize()), '{G}.rotate{A}'.format(G=grp_name, A=attr.capitalize()))
    # nest groups and add parents
    mc.parent(jnts_dict['claw']['grp'], jnts_dict['finger']['grp'])
    mc.parent(jnts_dict['finger']['grp'], jnts_dict['palm']['grp'])
    if 'thumb' not in toe_name:
        mc.parent(jnts_dict['palm']['grp'], jnts_dict['wrist']['grp'])
        grp = mc.group(jnts_dict['wrist']['grp'], name='{T}_wristHeelRotate_grp'.format(T=toe_name))
        mc.move(jnts_dict['wrist']['translates'][0],0,jnts_dict['wrist']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
        grp = mc.group(grp, name='{T}_wristHeelPivot_grp'.format(T=toe_name))
        mc.move(jnts_dict['wrist']['translates'][0],0,jnts_dict['wrist']['translates'][2]+.01,'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
        grp = mc.group(grp, name='{T}_palmPivot_grp'.format(T=toe_name))
    if 'thumb' in toe_name:
        grp = mc.group(jnts_dict['palm']['grp'], name='{T}_palmPivot_grp'.format(T=toe_name))
    mc.move(jnts_dict['finger']['translates'][0],jnts_dict['finger']['translates'][1],jnts_dict['finger']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{T}_fingerPivot_grp'.format(T=toe_name))
    mc.move(jnts_dict['claw']['translates'][0],jnts_dict['claw']['translates'][1],jnts_dict['claw']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)    
    grp = mc.group(grp, name='{T}_fingerStand_grp'.format(T=toe_name))
    mc.move(jnts_dict['claw']['translates'][0],jnts_dict['claw']['translates'][1],jnts_dict['claw']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{T}_clawPivot_grp'.format(T=toe_name))
    mc.move(jnts_dict['end']['translates'][0],jnts_dict['end']['translates'][1],jnts_dict['end']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)    
    grp = mc.group(grp, name='{T}_clawStand_grp'.format(T=toe_name))
    mc.move(jnts_dict['end']['translates'][0],jnts_dict['end']['translates'][1],jnts_dict['end']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    foot_ctrl = '{F}_leg_foot_ctrl'.format(F='_'.join(toe_name.split('_')[:2]))
    mc.parent(grp, foot_ctrl)
    attrs = ['wristHeelRotate', 'wristHeelPivot', 'palmPivot', 'fingerPivot', 'fingerStand', 'clawPivot', 'clawStand']
    if 'thumb' in toe_name:
        attrs = ['palmPivot', 'fingerPivot', 'fingerStand', 'clawPivot', 'clawStand']
    for attr in attrs:
        axis = 'X'
        if attr.endswith('Pivot'):
            axis = 'Y'
        mc.connectAttr('{C}.{A}'.format(C=foot_ctrl, A=attr), '{T}_{A}_grp.rotate{X}'.format(T=toe_name, A=attr, X=axis), force=True)

        
def transfer_skin_weights(a='l_b_ankle_jnt_bnd', b='l_b_ankle_ik_jnt'):
    # function to transfer skin weight from jnt a to jnt b for selected verts
    selected = mc.ls(sl=1)
    mesh = mc.listRelatives(selected[0].split('.')[0], c=True)[0]
    skin = [c for c in mc.listConnections(mesh) if mc.nodeType(c) == 'skinCluster'][0]
    verts = mc.filterExpand(selected, selectionMask=31)
    vert_dict = {}
    for i in range(len(verts)):
        keys = mc.skinPercent(skin, verts[i], query=True, transform=None)
        values = mc.skinPercent(skin, verts[i], query=True, value= True)
        inf_dict = {keys[i]: values[i] for i in range(len(keys))}
        vert_dict[verts[i]] = inf_dict
    for vert, inf_dict in vert_dict.iteritems():
        most = ''
        if a in inf_dict.keys():
            mc.select(verts[i], replace=True)
            try:
                lock_dict = {a: mc.getAttr(a+'.liw'), b: mc.getAttr(b+'.liw')}
                for j, lock in lock_dict.iteritems():
                    mc.setAttr(j+'.liw', False)
                mc.skinPercent(skin, transformMoveWeights=[a, b])
                for j, lock in lock_dict.iteritems():
                    mc.setAttr(j+'.liw', lock)
            except:
                print vert, a, b
    mc.select(verts, replace=True)
        
def transfer_to_most(skin='body_lo_skinCluster', bad='c_head_jnt_bnd'):
    # function to transfer bad weights to most for that vert 
    selected = mc.ls(sl=1)
    verts = mc.filterExpand(selected, selectionMask=31)
    vert_dict = {}
    for i in range(len(verts)):
        keys = mc.skinPercent(skin, verts[i], query=True, transform=None)
        values = mc.skinPercent(skin, verts[i], query=True, value= True)
        inf_dict = {keys[i]: values[i] for i in range(len(keys))}
        vert_dict[verts[i]] = inf_dict
    for vert, inf_dict in vert_dict.iteritems():
        most = ''
        if bad in inf_dict.keys():
            most = max(inf_dict, key=lambda k: inf_dict[k])
            mc.select(verts[i], replace=True)
            try:
                lock_dict = {bad: mc.getAttr(bad+'.liw'), most: mc.getAttr(most+'.liw')}
                for j, lock in lock_dict.iteritems():
                    mc.setAttr(j+'.liw', False)
                mc.skinPercent(skin, transformMoveWeights=[bad, most])
                for j, lock in lock_dict.iteritems():
                    mc.setAttr(j+'.liw', lock)
            except:
                print vert, bad, most
    mc.select(verts, replace=True)
        
def fix_side_weights(side='l_', skin='skinCluster394'):
    # function to take selected verts and remap side weights to other side jnt
    side_dict = {'l_': 'r_', 'r_':'l_'}
    other_side = side_dict[side]
    selected = mc.ls(sl=1)
    verts = mc.filterExpand(selected, selectionMask=31)
    for i in range(len(verts)):
        keys = mc.skinPercent(skin, verts[i], query=True, transform=None)
        values = mc.skinPercent(skin, verts[i], query=True, value= True)
        inf_dict = {keys[i]: values[i] for i in range(len(keys))} 
        mc.select(verts[i], replace=True)
        for k, v in inf_dict.iteritems():
            if k.startswith(side) and v != 0:
                new_k = k.replace(side, other_side, 1)
                #unlock if needed
                lock_dict = {k: mc.getAttr(k+'.liw'), new_k: mc.getAttr(new_k+'.liw')}
                for jnt, lock in lock_dict.iteritems():
                    mc.setAttr(jnt+'.liw', False)
                mc.skinPercent(skin, transformMoveWeights=[k, new_k])
                for jnt, lock in lock_dict.iteritems():
                    mc.setAttr(jnt+'.liw', lock)
    mc.select(verts, replace=True)

def unlocked_weights(skin='skinCluster393'):
    # function to determine how many joints are currently unlocked for painting weights
    unlock_dict = {}
    jnts = mc.skinCluster(skin,query=True, inf=True)
    for jnt in jnts:
        unlock_dict[jnt] = not mc.getAttr(jnt+'.liw')
    unlocked = sum(unlock_dict.values())
    print unlocked
