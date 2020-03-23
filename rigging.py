import maya.cmds as mc

def reverse_leg_setup(leg_name='l_b'):
    """Functiom to duplicate leg as a drv chain and set up two sets of iks for driving the leg."""
    bones = ['hip', 'knee', 'ankle', 'ball', 'toe']
    leg_jnts = ['{L}_{B}_jnt'.format(L=leg_name, B=b) for b in bones]
    drv_jnts = [l.replace('_jnt', '_drv_jnt') for l in leg_jnts] 
    mc.duplicate(leg_jnts[0], name=drv_jnts[0])
    # rename drv children
    drv_kids = sorted(mc.listRelatives(drv_jnts[0], allDescendents=True, fullPath=True), key=lambda x: len(x), reverse=True)
    for i in range(len(drv_kids)):
        mc.rename(drv_kids[i], drv_jnts[-(i+1)])
    # setup iks
    iks_dict = {'full': {'start': drv_jnts[0], 'end': drv_jnts[-2], 'solver': 'ikRPsolver'},
                'upper': {'start': leg_jnts[0], 'end': leg_jnts[-3], 'solver': 'ikRPsolver'},
                'lower': {'start': leg_jnts[-3], 'end': leg_jnts[-2], 'solver': 'ikSCsolver'}}
    for name, ik_dict in iks_dict.iteritems():
       ik = mc.ikHandle(startJoint=ik_dict['start'], endEffector=ik_dict['end'], solver=ik_dict['solver'])
        ik_name = '{L}_{N}_ik'.format(L=leg_name, N=name)
        mc.rename(ik[0], ik_name)

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
