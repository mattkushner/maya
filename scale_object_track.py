import maya.cmds as mc
import math

def euclidian_distance(x, y):
    distance = math.sqrt(sum([(a - b) ** 2 for a, b in zip(x, y)]))

    return distance


def scale_object_track(cam_transform, object_grp):
    """Designed to scale object track at ideal length from camera for animated cameras.
       Assumptions include that you have already grouped your object and set it's pivot and scaled it to the ideal size on the first frame.
       The tool duplicates the group on each frame, sets the pivot to the camera and scales to attain a world scale for the object that matches what was set.
    """
    start = int(mc.playbackOptions(query=True, minTime=True))
    end = int(mc.playbackOptions(query=True, maxTime=True))
    # determine optimal bbox length from min to max
    object = mc.listRelatives(object_grp, children=True, fullPath=True)[0]
    bbox = mc.exactWorldBoundingBox(object)
    optimal_length = euclidian_distance(bbox[:3], bbox[3:])
    for i in range(start, end+1):
        # duplicate group with input connections, rename group with _framenum
        new = mc.duplicate(object_grp, inputConnections=True, returnRootsOnly=True)
        new_grp = '{GRP}_{FRAME}'.format(GRP=object_grp.split('|')[-1], FRAME=str(i))
        if mc.objExists(new_grp):
            mc.delete(new_grp)
        mc.rename(new, new_grp)
        new_obj = mc.listRelatives(new_grp, children=True, fullPath=True)[0]
        mc.currentTime(i)
        if mc.currentTime(query=True) == start:
            transfer = mc.duplicate(object_grp, returnRootsOnly=True)
            transfer_grp = '{GRP}_transfer'.format(GRP=object_grp.split('|')[-1])
            mc.rename(transfer, transfer_grp)
            transfer_obj = mc.listRelatives(transfer_grp, children=True, fullPath=True)[0]
        # move pivot of group to camera pivot
        group_pivot = mc.xform(cam_transform, query=True, rotatePivot=True, worldSpace=True)
        mc.move(group_pivot[0], group_pivot[1], group_pivot[2], [new_grp+'.scalePivot', new_grp+'.rotatePivot'], rotatePivotRelative=True)
        # reset scale to determine default bbox length, calculate and set scale
        mc.setAttr(new_grp+'.scale', 1, 1, 1)
        new_bbox = mc.exactWorldBoundingBox(new_obj)
        new_length = euclidian_distance(new_bbox[:3], new_bbox[3:])
        scale_val = optimal_length/new_length
        mc.setAttr(new_grp+'.scale', scale_val, scale_val, scale_val)
        #break connections to object, make it static
        conns = mc.listConnections(new_obj)
        for conn in conns:
            mc.disconnectAttr('{CONN}.output'.format(CONN=conn), '{OBJ}.{ATTR}'.format(OBJ=new_obj, ATTR=conn.split('_')[-1]))
        #parent constraint transfer object to all new ones and key weights per frame
        constraint = mc.parentConstraint(new_obj, transfer_obj)
        # key weight at 0 before and after current frame, at 1 for current frame
        time_range = range(i-1, i+2)
        constraint_attr = '{CONST}.w{ITER}'.format(CONST=constraint[0], ATTR=constraint[0].split('_')[0], ITER=str(i-start))
        for t in time_range:
            mc.currentTime(t)
            value = 0
            if t == i:
                value = 1
            mc.setAttr(constraint_attr, value)
            mc.setKeyframe(constraint_attr, value=value)
