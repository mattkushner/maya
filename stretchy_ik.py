def make_ik_stretchy(ctrl):
  # uses distance dimension
    base =  '_'.join(ik_handle.split('_')[:-1])
    # get ik from ctrl
    ik_handle = base + '_ikHandle'
    if mc.nodeExists(ik_handle):
        # add toothScale attr to ctrl if it doesn't exist
        if not mc.attributeQuery('toothScale', node=ctrl, exists=True):
            mc.addAttr(ctrl, longName="toothScale", attributeType='double', defaultValue=1)
            mc.setAttr(ctrl+'.toothScale', edit=True, keyable=True)

        name_dict = {'dist': base + '_dist',
                     'mult': base + '_mult',
                     'default': base + '_default',
                     'divide': base + '_divide',
                     'cond': base + '_cond',
                     'start_loc': base + '_start_loc',
                     'end_loc': base + '_end_loc',
                     'start_jnt_dummy': base + '_start_jnt',
                     'end_jnt_dummy': base + '_end_jnt'}
        # blow away any existing nodes
        for key, value in name_dict.iteritems():
            if mc.objExists(value):
                mc.delete(value)
        # set up distance
        all_jnts =  mc.ikHandle(ik_handle, query=True, jointList=True)
        name_dict['start_jnt'] = start_jnt = mc.ikHandle(ik_handle, query=True, startJoint=True)
        eff = mc.ikHandle(ik_handle, query=True, endEffector=True)
        name_dict['end_jnt'] = list(set(mc.listConnections(eff, type='joint')))[0]
        # create dummy jnts for measturing
        for jnt in ['start', 'end']:
            mc.select(clear=True)
            mc.joint(name=name_dict[jnt+'_jnt_dummy'])
            const = mc.parentConstraint(name_dict[jnt+'_jnt'], name_dict[jnt+'_jnt_dummy'])
            mc.delete(const)
            # start_dummy under parent, start_loc under start_dummy
            if jnt == 'start':
                name_dict[jnt+'_jnt_parent'] = mc.listRelatives(name_dict[jnt+'_jnt'], parent=True)[0]
                name_dict[jnt+'_loc_parent'] = name_dict[jnt+'_jnt_dummy']
            # end_dummy under start_dummy, end_loc under ctrl
            elif jnt == 'end':
                mc.parentConstraint(ctrl, name_dict[jnt+'_jnt_dummy'], maintainOffset=True)
                name_dict[jnt+'_jnt_parent'] = name_dict['start_jnt_dummy']
                name_dict[jnt+'_loc_parent'] = ctrl   
            mc.parent(name_dict[jnt+'_jnt_dummy'], name_dict[jnt+'_jnt_parent'])
    
        start_pnt = mc.xform(name_dict['start_jnt'], query=True, worldSpace=True, translation=True)
        end_pnt = mc.xform(name_dict['end_jnt'], query=True, worldSpace=True, translation=True)
        dist_shape = mc.distanceDimension(startPoint=start_pnt, endPoint=end_pnt)
        dist_trans = mc.listRelatives(dist_shape, parent=True)[0]
        mc.rename(dist_trans, name_dict['dist'])
        # rename locs, parent to jnts
        for loc in ['start', 'end']:
            loc_attr = mc.connectionInfo(name_dict['dist']+'Shape.'+loc+'Point', sourceFromDestination=True)
            loc_trans = mc.listRelatives(loc_attr.split('.')[0], parent=True)
            mc.rename(loc_trans, name_dict[loc+'_loc'])
            mc.parent(name_dict[loc+'_loc'], name_dict[loc+'_loc_parent'])
            mc.hide(name_dict[loc+'_loc'])
        # set up mult of toothScale & distance
        mc.shadingNode('multiplyDivide', asUtility=True, name=name_dict['mult'])
        mc.setAttr(name_dict['mult']+'.operation', 1)
        mc.connectAttr(name_dict['dist']+'Shape.distance', name_dict['mult']+'.input1X', force=True)
        mc.connectAttr(ctrl+'.toothScale', name_dict['mult']+'.input2X', force=True)
        # set up default mult of toothScale & init distance
        mc.shadingNode('multiplyDivide', asUtility=True, name=name_dict['default'])
        mc.setAttr(name_dict['default']+'.operation', 1)
        mc.connectAttr(ctrl+'.toothScale', name_dict['default']+'.input1X', force=True)
        distance = mc.getAttr(name_dict['mult']+'.input1X')
        mc.setAttr(name_dict['default']+'.input2X', distance)
        # set up divide of mult/default
        mc.shadingNode('multiplyDivide', asUtility=True, name=name_dict['divide'])
        mc.setAttr(name_dict['divide']+'.operation', 2)
        mc.connectAttr(name_dict['mult']+'.outputX', name_dict['divide']+'.input1X', force=True)
        mc.connectAttr(name_dict['default']+'.outputX', name_dict['divide']+'.input2X', force=True)
        # set up condition, only scale joints when greater than default distance 
        mc.shadingNode('condition', asUtility=True, name=name_dict['cond'])
        mc.setAttr(name_dict['cond']+'.operation', 2)
        mc.connectAttr(name_dict['dist']+'Shape.distance', name_dict['cond']+'.firstTerm', force=True)
        mc.connectAttr(name_dict['default']+'.outputX', name_dict['cond']+'.secondTerm', force=True)
        mc.connectAttr(name_dict['divide']+'.outputX', name_dict['cond']+'.colorIfTrueR', force=True)
        mc.connectAttr(ctrl+'.toothScale', name_dict['cond']+'.colorIfFalseR', force=True)
        # connect to jnts
        for jnt in all_jnts:
            for axis in ['X', 'Y', 'Z']:
                mc.connectAttr(name_dict['cond']+'.outColorR', jnt+'.scale'+axis) 




def make_ik_stretchy(ctrl):
    # uses distanceBetween, but never figured out all the missing attributes between it and the distanceDimension setup
    # get ik from ctrl
    const = [f for f in list(set(mc.listConnections(ctrl))) if mc.nodeType(f) == 'parentConstraint'][0]
    ik_handle_grp = [f for f in list(set(mc.listConnections(const))) if f.endswith('Grp')][0]
    ik_handle = [f for f in mc.listRelatives(ik_handle_grp) if mc.nodeType(f) == 'ikHandle'][0]
    # add toothScale attr to ctrl if it doesn't exist
    if not mc.attributeQuery('toothScale', node=ctrl, exists=True):
        mc.addAttr(ctrl, longName="toothScale", attributeType='double', defaultValue=1)
        mc.setAttr(ctrl+'.toothScale', edit=True, keyable=True)

    base =  '_'.join(ik_handle.split('_')[:-1])
    name_dict = {'dist': base + '_dist',
                 'mult': base + '_mult',
                 'default': base + '_default',
                 'divide': base + '_divide',
                 'cond': base + '_cond',
                 'start_loc': base + '_start_loc',
                 'end_loc': base + '_end_loc',
                 'start_jnt_dummy': base + '_start_jnt',
                 'end_jnt_dummy': base + '_end_jnt'}
    # blow away any existing nodes
    for key, value in name_dict.iteritems():
        if mc.objExists(value):
            mc.delete(value)
    # set up distance
    all_jnts =  mc.ikHandle(ik_handle, query=True, jointList=True)
    name_dict['start_jnt'] = start_jnt = mc.ikHandle(ik_handle, query=True, startJoint=True)
    eff = mc.ikHandle(ik_handle, query=True, endEffector=True)
    name_dict['end_jnt'] = list(set(mc.listConnections(eff, type='joint')))[0]
    # create dummy jnts for measturing
    for jnt in ['start', 'end']:
        mc.select(clear=True)
        mc.joint(name=name_dict[jnt+'_jnt_dummy'])
        const = mc.parentConstraint(name_dict[jnt+'_jnt'], name_dict[jnt+'_jnt_dummy'])
        mc.delete(const)
        # start_dummy under parent, start_loc under start_dummy
        if jnt == 'start':
            name_dict[jnt+'_jnt_parent'] = mc.listRelatives(name_dict[jnt+'_jnt'], parent=True)[0]
            name_dict[jnt+'_loc_parent'] = name_dict[jnt+'_jnt_dummy']
        # end_dummy under start_dummy, end_loc under ctrl
        elif jnt == 'end':
            mc.parentConstraint(ctrl, name_dict[jnt+'_jnt_dummy'], maintainOffset=True)
            name_dict[jnt+'_jnt_parent'] = name_dict['start_jnt_dummy']
            name_dict[jnt+'_loc_parent'] = ctrl   
        mc.parent(name_dict[jnt+'_jnt_dummy'], name_dict[jnt+'_jnt_parent'])

    start_pnt = mc.xform(name_dict['start_jnt'], query=True, worldSpace=True, translation=True)
    end_pnt = mc.xform(name_dict['end_jnt'], query=True, worldSpace=True, translation=True)
    mc.select(clear=True)
    dist_shape = mc.shadingNode('distanceBetween', asUtility=True)
    dist_trans = mc.listRelatives(dist_shape, parent=True)[0]
    mc.rename(dist_trans, name_dict['dist'])
    # rename locs, parent to jnts
    for loc in ['start', 'end']:
        mc.spaceLocator(name=name_dict[loc+'_loc'])
        const = mc.parentConstraint(mane_dict[loc+'_loc'], name_dict[loc+'_jnt'])
        mc.connectAttr(name_dict[loc+'_loc']+'.worldPosition[0]', name_dict['dist']+'.'+loc+'Position', force=True)
        mc.parent(name_dict[loc+'_loc'], name_dict[loc+'_loc_parent'])
        mc.hide(name_dict[loc+'_loc'])
    # set up mult of toothScale & distance
    mc.shadingNode('multiplyDivide', asUtility=True, name=name_dict['mult'])
    mc.setAttr(name_dict['mult']+'.operation', 1)
    mc.connectAttr(name_dict['dist']+'Shape.distance', name_dict['mult']+'.input1X', force=True)
    mc.connectAttr(ctrl+'.toothScale', name_dict['mult']+'.input2X', force=True)
    # set up default mult of toothScale & init distance
    mc.shadingNode('multiplyDivide', asUtility=True, name=name_dict['default'])
    mc.setAttr(name_dict['default']+'.operation', 1)
    mc.connectAttr(ctrl+'.toothScale', name_dict['default']+'.input1X', force=True)
    distance = mc.getAttr(name_dict['mult']+'.input1X')
    mc.setAttr(name_dict['default']+'.input2X', distance)
    # set up divide of mult/default
    mc.shadingNode('multiplyDivide', asUtility=True, name=name_dict['divide'])
    mc.setAttr(name_dict['divide']+'.operation', 2)
    mc.connectAttr(name_dict['mult']+'outputX', name_dict['divide']+'.input1X', force=True)
    mc.connectAttr(name_dict['default']+'outputX', name_dict['divide']+'.input2X', force=True)
    # set up condition, only scale joints when greater than default distance 
    mc.shadingNode('condition', asUtility=True, name=name_dict['cond'])
    mc.setAttr(name_dict['cond']+'.operation', 2)
    mc.connectAttr(name_dict['dist']+'Shape.distance', name_dict['cond']+'.firstTerm', force=True)
    mc.connectAttr(name_dict['default']+'.outputXX', name_dict['cond']+'.secondTerm', force=True)
    mc.connectAttr(name_dict['divide']+'.outputX', name_dict['cond']+'.colorIfTrueR', force=True)
    mc.connectAttr(ctrl+'.toothScale', name_dict['cond']+'.colorIfFalseR', force=True)
    # connect to jnts
    for jnt in all_jnts:
        for axis in ['X', 'Y', 'Z']:
            mc.connectAttr(name_dict['cond']+'.outColorR', jnt+'.scale'+axis) 
