import maya.cmds as mc

def key_offset(node, attr, offset):
    """Function to offset keys on a node so they start on first_frame.
    Args:
        node (str): Name of maya node
        attr (str): Name of attribute
        offset (int): Amount to offset keys
    """
    keys = mc.keyframe(node, attribute=attr, q=True, kc=True)
    if keys:
        first_keys = mc.keyframe(node+'.'+attr, q=True, index=(0, 0))
        if first_keys:
            first_key = int(first_keys[0])
            last_key = int(first_key)+keys-1
            mc.keyframe(node+'.'+attr, edit=True, relative=True, timeChange=offset, time=(first_key, last_key))


def match_camera(offset):
    groups_dict = {}
    # offsets original if need be, moves group pivot to camera, transfers values from old to new, snaps new camera to old
    old_groups = [f for f in mc.ls(assemblies=1) if 'SynthEyesGroup' == f]
    new_groups = [f for f in mc.ls(assemblies=1) if 'SynthEyesGroup' in f and f not in old_groups]
    if old_groups and len(new_groups)==1:
        groups_dict['old'] = old_groups[0]
        groups_dict['new'] = new_groups[0]
        # offset old_group keys
        elems = ['Camera01', 'Object01']
        for elem in elems:
            long_name = groups_dict['old'] + '|' + elem
            if mc.objExists(long_name):
                keyed = mc.keyframe(long_name, name=1, query=1)
                if keyed:
                    # get keyable attrs and check for keys
                    keyable_attrs = mc.listAttr(long_name, k=1)
                    if keyable_attrs:
                        for attr in keyable_attrs:
                            attr_keys = mc.keyframe(long_name, attribute=attr, query=True, keyframeCount=True)
                            if attr_keys:
                                key_offset(long_name, attr, offset)
        # set current time to beginning of old camera
        mc.currentTime(1001+offset)
        for key, value in groups_dict.iteritems():
            camera_transform = value+'Camera01'
            x_pos, y_pos, z_pos = mc.xform(camera_transform, query=True, worldSpace=True, translation=True)                   
            mc.move(x_pos, y_pos, z_pos, [value+'.rotatePivot', value+'.scalePivot'], rotatePivotRelative=True)
        # snap new group to old group values
        for attr in ['.translateX', '.translateY', '.translateZ', '.rotateX', '.rotateY', '.rotateZ', '.scaleX', '.scaleY', '.scaleZ']:
            attr_value = mc.getAttr(groups_dict['old']+attr)
            mc.setAttr(groups_dict['new']+attr, attr_value)
        # snap new camera group to old camera position
        x_pos, y_pos, z_pos = mc.xform(groups_dict['old']+'|Camera01', query=True, worldSpace=True, translation=True)
        mc.move(x_pos, y_pos, z_pos, groups_dict['new'], rotatePivotRelative=True)
