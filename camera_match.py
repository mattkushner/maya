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
    old_group = 'SynthEyesGroup'
    elems = ['Camera01', 'Object01']
    for elem in elems:
        long_name = old_group + '|' + elem
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
