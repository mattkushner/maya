import maya.cmds as mc

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
        grp_name = '{I}_grp'.format(I=ik_name)
        mc.rename(ik[0], ik_name)
        mc.group(ik_name, name=grp_name)
        jnts_dict[name]['grp'] = grp_name
        mc.move(jnts_dict[name]['translates'][0],jnts_dict[name]['translates'][1],jnts_dict[name]['translates'][2],'{G}.rotatePivot'.format(G=grp_name),'{G}.scalePivot'.format(G=grp_name), rpr=True)
    # grouping and pivot logic
    grp = mc.group(jnts_dict['ankle']['grp'], jnts_dict['ball']['grp'], name='{T}_ballRotate_grp'.format(T=toe_name))
    mc.move(jnts_dict['ball']['translates'][0],jnts_dict['ball']['translates'][1],jnts_dict['ball']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(jnts_dict['toe']['grp'], grp, name='{T}_ankleRotate_grp'.format(T=toe_name))
    mc.move(jnts_dict['ankle']['translates'][0],jnts_dict['ankle']['translates'][1],jnts_dict['ankle']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{T}_heelRotate_grp'.format(T=toe_name))
    mc.move(jnts_dict['ankle']['translates'][0],0,jnts_dict['ankle']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{T}_heelPivot_grp'.format(T=toe_name))
    mc.move(jnts_dict['ankle']['translates'][0],0,jnts_dict['ankle']['translates'][2]+.01,'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{T}_ballPivot_grp'.format(T=toe_name))
    mc.move(jnts_dict['ball']['translates'][0],jnts_dict['ball']['translates'][1],jnts_dict['ball']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{T}_toePivot_grp'.format(T=toe_name))
    mc.move(jnts_dict['toe']['translates'][0],jnts_dict['toe']['translates'][1],jnts_dict['toe']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)
    grp = mc.group(grp, name='{T}_toeStand_grp'.format(T=toe_name))
    mc.move(jnts_dict['toe']['translates'][0],jnts_dict['toe']['translates'][1],jnts_dict['toe']['translates'][2],'{G}.rotatePivot'.format(G=grp),'{G}.scalePivot'.format(G=grp), rpr=True)