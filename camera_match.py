import maya.cmds as mc

def get_keys(node, attr):
    """Function to get first and last keys on a node attribute.
    Args:
        node (str): Name of maya node
        attr (str): Name of attribute
    """
    key_dict = {}
    keys = mc.keyframe(node, attribute=attr, q=True, kc=True)
    if keys:
        first_keys = mc.keyframe(node+'.'+attr, q=True, index=(0, 0))
        if first_keys:
            key_dict['first'] = int(first_keys[0])
            key_dict['last'] = int(key_dict['first'])+keys-1
    
    return key_dict

def set_timeline_from_selected():
    """Function to set timeline based on selected keys."""
    selected = mc.ls(sl=1)
    key_dict = get_keys(selected[0], 'translateX')
    if 'first' in key_dict.keys() and 'last' in key_dict.keys():
        mc.playbackOptions(minTime=key_dict['first'], animationStartTime=key_dict['first'], maxTime=key_dict['last'], animationEndTime=key_dict['last'])
    else:
        print (selected[0]+ ' has no keys.')

def match_camera(old_offset=0, new_offset=0):
    """Function to match syntheyes_new to syntheyes_old for updating tracks.
    Args:
        old_offset (int): Number of frames to offset animation of old camera
        new_offset (int): Number of frames to offset animation of new camera
    """
    groups_dict = {}
    groups_dict['old_cam'] = groups_dict['new_cam'] = 'Camera01'
    groups_dict['old_offset'] = old_offset
    groups_dict['new_offset'] = new_offset
    # offsets original if need be, moves group pivot to camera, transfers values from old to new, snaps new camera to old
    old_groups = [f for f in mc.ls(assemblies=1) if 'old' in f]
    new_groups = [f for f in mc.ls(assemblies=1) if 'new' in f]
    if old_groups and len(new_groups)==1:
        groups_dict['old'] = old_groups[0]
        groups_dict['new'] = new_groups[0]
        for each in ['old', 'new']:
            cam_transforms = [mc.listRelatives(f, parent=True)[0] for f in mc.listRelatives(groups_dict[each], allDescendents=True, fullPath=True) if mc.nodeType(f)=='camera']
            if cam_transforms:
                groups_dict[each+'_cam']= cam_transforms[0]
        # offset keys
        for group in ['old', 'new']:
            elems = [groups_dict[group+'_cam'], 'Object01', 'Object02']
            if groups_dict[group+'_offset']:
                for elem in elems:
                    long_name = groups_dict[group] + '|' + elem
                    if mc.objExists(long_name):
                        keyed = mc.keyframe(long_name, name=1, query=1)
                        if keyed:
                            # get keyable attrs and check for keys
                            keyable_attrs = mc.listAttr(long_name, k=1)
                            if keyable_attrs:
                                for attr in keyable_attrs:
                                    attr_keys = mc.keyframe(long_name, attribute=attr, query=True, keyframeCount=True)
                                    if attr_keys:
                                        key_dict = get_keys(long_name, attr)
                                        if 'last' in key_dict.keys() and 'first' in key_dict.keys():
                                            mc.keyframe(longname+'.'+attr, edit=True, relative=True, timeChange=groups_dict[group+'_offset'], time=(key_dict['first'], key_dict['last']))
        # set new frame range
        end_frame = 1000 + mc.keyframe(groups_dict['new']+'|'+groups_dict['new_cam'], attribute='translateX', query=True, keyframeCount=True)
        mc.playbackOptions(animationStartTime=1001, minTime=1001, animationEndTime=end_frame, maxTime=end_frame)
        # set current time to beginning of old camera
        mc.currentTime(1001+groups_dict['old_offset'])
        for key, value in groups_dict.iteritems():
            if key in ['old', 'new']:
                cam_transform = value+'|'+groups_dict[key+'_cam']
                x_pos, y_pos, z_pos = mc.xform(cam_transform, query=True, worldSpace=True, translation=True)                   
                mc.move(x_pos, y_pos, z_pos, [value+'.rotatePivot', value+'.scalePivot'], rotatePivotRelative=True)
        # snap new group to old group values
        for attr in ['.translateX', '.translateY', '.translateZ', '.rotateX', '.rotateY', '.rotateZ', '.scaleX', '.scaleY', '.scaleZ']:
            attr_value = mc.getAttr(groups_dict['old']+attr)
            mc.setAttr(groups_dict['new']+attr, attr_value)
        # snap new camera group to old camera position
        x_pos, y_pos, z_pos = mc.xform(groups_dict['old']+'|'+groups_dict['old_cam'], query=True, worldSpace=True, translation=True)
        mc.move(x_pos, y_pos, z_pos, groups_dict['new'], rotatePivotRelative=True)

        
