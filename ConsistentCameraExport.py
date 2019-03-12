import os
import sys
import re
import maya.cmds as mc
import maya.mel as mel
import exportFBX as exportFBX
import exportNukeCombo as exportNuke

DEBUG = True


def workDirFromMaya(project_path):
    """ Our project structure is roughly /project/shot/_#D/program.
        workDirFromMaya(), given the current project_path, returns the work/
        directory or else raises an exception. """

    root = project_path.split('_3D')[0]
    work_path = os.path.normpath(root)

    if not os.path.exists(work_path):
        raise Exception(work_error)
    else:
        return work_path


def nukeDirFromMaya(project_path):
    """ Given maya's project path, returns the /nuke directory or raises an exception. """
    work_path = workDirFromMaya(project_path)
    nuke_path = os.path.join(work_path, '_2D/nuke')

    if not os.path.exists(nuke_path):
        raise Exception(
            'Could not find the /nuke folder in the shot /work directory.')
    else:
        return nuke_path


def houdiniDirFromMaya(project_path):
    """ Given houdini's project path, returns the /nuke directory or raises an exception. """
    work_path = workDirFromMaya(project_path)
    houdini_path = os.path.join(work_path, '_3D/houdini')

    if not os.path.exists(houdini_path):
        raise Exception(
            'Could not find the /houdini folder in the shot /work directory.')
    else:
        return houdini_path


def getVisibleModelPanels():
    """ Returns the visible model panels so they can have their view flags toggled
        to aid in baking speed. """
    visible = mc.getPanel(vis=True)
    models = set(mc.getPanel(type='modelPanel'))

    visibleAndModel = []
    for v in visible:
        if v in models:
            visibleAndModel.append(v)

    return visibleAndModel


def disableCamerasAndImagePlanes():
    # hide camera/imagePlane view if requested to accelerate baking
    restoreCamPanes = []
    restoreImgPanes = []

    for v in getVisibleModelPanels():
        # this modelPane is both visible and has cameras on
        # so we need to hide it here and restore it after bake
        if mc.modelEditor(v, q=True, cameras=True):
            mc.modelEditor(v, e=True, cameras=False)
            restoreCamPanes.append(v)

        if mc.modelEditor(v, q=True, imagePlane=True):
            mc.modelEditor(v, e=True, imagePlane=False)
            restoreImgPanes.append(v)

    # turn off display mode on imagePlanes and force texture type
    # this works around a bug on some graphics card where the ip is
    # still visible after turning it off in the modelPanel
    ipOrigState = []
    imagePlanes = mc.ls(type='imagePlane')
    if imagePlanes:
        for ip in imagePlanes:
            # store the imagePlane's original settings in a list dict
            dmode = mc.getAttr('%s.displayMode' % ip)
            dtype = mc.getAttr('%s.type' % ip)
            ipOrigState.append(
                {'name': ip, 'displayMode': dmode, 'type': dtype})

            mc.setAttr('%s.displayMode' % ip, 0)  # none
            mc.setAttr('%s.type' % ip, 1)        # texture

    return [restoreCamPanes, restoreImgPanes, ipOrigState]


def enableCamerasAndImagePlanes(states):
    restoreCamPanes = states[0]
    restoreImgPanes = states[1]
    ipOrigState = states[2]

    # restore camera visibility in any panes where we hid camera vis
    for v in restoreCamPanes:
        mc.modelEditor(v, e=True, cameras=True)
    for v in restoreImgPanes:
        mc.modelEditor(v, e=True, imagePlane=True)

    # restore image planes
    for ip in ipOrigState:
        mc.setAttr('%s.displayMode' % ip['name'], ip['displayMode'])
        mc.setAttr('%s.type' % ip['name'], ip['type'])


def duplicateImagePlane(srcCam, destCam):
    """ Creates an imagePlane under destCam that matches the attributes
        and connections of srcCam. This is nessesary because the imagePlane
        -camera command is only available in the extension. Returns the new
        imagePlane xform and shape as a tuple. """
    srcXform, srcShape = getCameraXformAndShape(srcCam)
    destXform, destShape = getCameraXformAndShape(destCam)

    if srcShape == '' or destShape == '':
        raise Exception(
            'duplicateImagePlane was fed a none camera shape/xform argument.')

    # find the srcCam imagePlane
    srcIPShape = ''
    srcIPXform = ''
    children = mc.listRelatives(srcShape, c=True, pa=True)

    if not children:
        return  # don't error, just return

    for c in children:
        c2 = mc.listRelatives(c, c=True, pa=True)
        if not c2:
            continue
        if mc.nodeType(c2[0]) == 'imagePlane':
            srcIPShape = c2[0]
            srcIPXform = c
            break  # take only the first image plane we find

    if srcIPShape == '':
        return  # don't error, just return

    # imagePlane transform is under camShape
    destIPXform = mc.createNode('transform', n='imagePlane#', p=destShape)
    # destIPShape = mc.shadingNode('imagePlane', asUtility=True, p=destIPXform)
    is_color_managed = mc.getAttr('%s.colorManagementEnabled' % srcIPShape)
    colorspace_attr = mc.getAttr('%s.colorSpace' % srcIPShape)
    destIPShape = mc.shadingNode('imagePlane', asUtility=True, p=destIPXform, asShader=True, isColorManaged=is_color_managed)
    if is_color_managed:
        mc.setAttr('%s.colorSpace' % destIPShape, colorspace_attr, type="string")


    # dup expression or keyframe connection
    exp = mc.listConnections('%s.frameExtension' % srcIPShape, plugs=True)
    if (exp != None):
        frameExtInput = exp[0]
        mc.connectAttr(frameExtInput, '%s.frameExtension' %
                       destIPShape, f=True)

    # copy attribute values
    attribs = ('displayMode', 'alphaGain', 'type', 'useFrameExtension', 'frameOffset', 'frameCache',
               'fit', 'sizeX', 'sizeY', 'offsetX', 'offsetY', 'squeezeCorrection', 'depth', 'rotate',
               'coverageX', 'coverageY', 'coverageOriginX', 'coverageOriginY', 'visibleInReflections',
               'visibleInRefractions', 'visibility', 'displayOnlyIfCurrent')

    for attr in attribs:
        # get src attr values
        v = mc.getAttr('%s.%s' % (srcIPShape, attr))
        # copy values to destination imagePlane
        mc.setAttr('%s.%s' % (destIPShape, attr), v)

    # string attr imageName special case
    iname = mc.getAttr('%s.imageName' % srcIPShape)
    mc.setAttr('%s.imageName' % destIPShape, iname, type='string')

    # connect imagePlane shape to camera shape
    mc.connectAttr('%s.message' % destIPShape, '%s.imagePlane[0]' % destShape)

    return (destIPXform, destIPShape)


def findChildMatch(node, pattern):
    """ Given a node and a regular expression string, returns the matching
        child node or None. """
    matching_node = None
    for c in mc.listRelatives(node, c=True, pa=True):
        if re.match(pattern, c) != None:
            matching_node = c
            break
    return matching_node


def getCameraXformAndShape(possibleCam):
    """ Given a possibleCam, returns the camera transform and shape nodes
        or else throws an exception."""
    camXform = ''
    camShape = ''

    if mc.nodeType(possibleCam) == 'transform':
        tempShape = mc.listRelatives(possibleCam, s=True, pa=True)[0]

        if mc.nodeType(tempShape) == 'camera':
            camShape = tempShape
            camXform = possibleCam

    elif mc.nodeType(possibleCam) == 'camera':
        camShape = possibleCam
        camXform = mc.listRelatives(possibleCam, p=True, pa=True)[0]

    if camShape == '' or camXform == '':
        raise Exception('Not a camera shape or transform: %s' % possibleCam)

    return (camXform, camShape)


def getLocatorXformAndShape(possibleLoc):
    """ Given a possibleLoc, returns the locator transform and shape nodes
        or else throws an exception."""
    locXform = ''
    locShape = ''

    if mc.nodeType(possibleLoc) == 'transform':
        tempShape = mc.listRelatives(possibleLoc, s=True, pa=True)[0]

        if mc.nodeType(tempShape) == 'locator':
            locShape = tempShape
            locXform = possibleLoc

    elif mc.nodeType(possibleLoc) == 'locator':
        locShape = possibleLoc
        locXform = mc.listRelatives(possibleLoc, p=True, pa=True)[0]

    if locShape == '' or locXform == '':
        raise Exception('Not a locator shape or transform: %s' % possibleLoc)

    return (locXform, locShape)


def getLayoutXformAndShape(possibleLoc):
    """ Given a possibleLoc, returns the locator transform and shape nodes
        or else throws an exception."""
    objXform = ''
    objShape = ''

    if mc.nodeType(possibleLoc) == 'transform':
        objShape = mc.listRelatives(possibleLoc, s=True, pa=True)[0]
        objXform = possibleLoc

    elif mc.nodeType(possibleLoc) != 'transform':
        objShape = possibleLoc
        objXform = mc.listRelatives(possibleLoc, p=True, pa=True)[0]

    if objShape == '' or objXform == '':
        raise Exception('Not a locator shape or transform: %s' % possibleLoc)

    return (objXform, objShape)


def duplicateLocatorsToWorldspace(locatorsGroupStr, locatorPrefix, locatorNewGrp='TrackingLocators'):
    """ Takes a list of locators and duplicates them in world space. The list
        should be a space separated string of the locator xforms from the Maya UI. """
    # attributes that must be unlocked to unparent
    locXformAttrs = ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz', 'v')

    locators = locatorsGroupStr.split(' ')

    # error if no selection
    if len(locators) == 1:
        if locators[0] == '':
            raise Exception('No locators to copy.')

    # new group to parent duplicated locators under
    parentGrp = ''
    tempGrp = mc.group(em=True)
    if not mc.objExists(locatorNewGrp):
        parentGrp = mc.rename(tempGrp, locatorNewGrp)
    else:
        parentGrp = mc.rename(tempGrp, '%s#' % locatorNewGrp)

    for l in sorted(locators):
        # skip none locator input from the user
        try:
            locXform, locShape = getLocatorXformAndShape(l)
        except:
            continue

        # //////////////////////////////////////////////////////////////
        # duplicate and unlock
        # //////////////////////////////////////////////////////////////

        tempDup = mc.duplicate(l, rr=True)[0]
        dupXform, dupShape = getLocatorXformAndShape(tempDup)

        # unlock transform attributes on both locators
        for a in locXformAttrs:
            mc.setAttr('%s.%s' % (locXform, a), lock=False)
            mc.setAttr('%s.%s' % (dupXform, a), lock=False)

        # //////////////////////////////////////////////////////////////
        # parent and rename
        # //////////////////////////////////////////////////////////////

        # ungroup
        if mc.listRelatives(locXform, p=True, pa=True) != None:
            mc.parent(locXform, w=True)

        # parent
        mc.parent(l, parentGrp)

        # rename with prefix
        mc.rename(l, '%s#' % locatorPrefix)

    # Put TrackedPoints group inside a new group called LayoutGRP
    # new group to parent duplicated locators under
    parentLayoutGrp = ''
    tempLayoutGrp = mc.group(em=True)
    parentLayoutGrp = mc.rename(tempLayoutGrp, 'Layout_GRP')
    mc.parent(parentGrp, parentLayoutGrp)

def pivot_parent_constrain(targetCameraTrans, dupCameraTrans, skipTranslate='none', skipRotate='none'):
    """Account for offset pivots of A Cam to make sure B Cam is in the correct position before constraint.
    Args:
       aCamDict (dict): Dict of A Camera Shape and Transform
       bCamDict (dict): Dict of B Camera Shape and Transform
    """

    world_scale = mc.xform(targetCameraTrans, query=True, scale=True, worldSpace=True)
    local_rotate_pivot = mc.xform(targetCameraTrans, query=True, rotatePivot=True)
    local_rotate_pivot_scaled = [a*b for a,b in zip(world_scale,local_rotate_pivot)]
    local_scale_pivot = mc.xform(targetCameraTrans, query=True, scalePivot=True)
    local_scale_pivot_scaled = [a*b for a,b in zip(world_scale,local_scale_pivot)]
    mc.xform(dupCameraTrans, rotatePivot=local_rotate_pivot_scaled)
    mc.xform(dupCameraTrans, scalePivot=local_scale_pivot_scaled)
    constraint = mc.parentConstraint(targetCameraTrans, dupCameraTrans, skipTranslate=skipTranslate, skipRotate=skipRotate, maintainOffset=False)
    mc.delete(constraint)
    mc.xform(dupCameraTrans, rotatePivot=[0, 0, 0])
    mc.xform(dupCameraTrans, scalePivot=[0, 0, 0])
    constraint = mc.parentConstraint(targetCameraTrans, dupCameraTrans, skipTranslate=skipTranslate, skipRotate=skipRotate, maintainOffset=True, weight=1)

    return constraint

def duplicateCameraAndBake(startFrame, endFrame, stepSize, targetCamera,
                           bakeCameraName, targetCameraNewName, renameTargetCam, connectIPs):
    """ This beastly function makes a copy of targetCamera, moves it to world space,
        constrains it to the original, bakes the keyframes, relocks everything and
        renames the cameras to conform to the naming convention for trackig and
        render cameras. """
    # attributes that must be unlocked and relocked for every camera
    camXformAttrs = ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz', 'v')
    camShapeAttrs = ('hfa', 'vfa', 'fl', 'lsr', 'fs', 'fd', 'sa', 'coi')

    # error if no selection
    if not mc.objExists(targetCamera):
        raise Exception('Camera does not exist: %s' % targetCamera)

    targetCameraTrans, targetCameraShape = getCameraXformAndShape(targetCamera)

    # //////////////////////////////////////////////////////////////
    # duplicate and unlock
    # //////////////////////////////////////////////////////////////
    tempDup = mc.duplicate(targetCameraTrans, rr=True)[0]
    dupCameraTrans, dupCameraShape = getCameraXformAndShape(tempDup)

    # unlock transform attributes on both cameras
    for a in camXformAttrs:
        mc.setAttr('%s.%s' % (dupCameraTrans, a), lock=False)
        mc.setAttr('%s.%s' % (targetCameraTrans, a), lock=False)

    # unlock shape attributes on both cameras
    for a in camShapeAttrs:
        mc.setAttr('%s.%s' % (dupCameraShape, a), lock=False)
        mc.setAttr('%s.%s' % (targetCameraShape, a), lock=False)

    # ungroup
    if mc.listRelatives(dupCameraTrans, p=True, pa=True) != None:
        mc.parent(dupCameraTrans, w=True)

    # //////////////////////////////////////////////////////////////
    # constrain/connect attributes
    # //////////////////////////////////////////////////////////////
    # parentConstraint = mc.parentConstraint(
    #     targetCameraTrans, dupCameraTrans, mo=True, weight=1)
    parentConstraint = pivot_parent_constrain(targetCameraTrans, dupCameraTrans,
                                            skipTranslate='none', skipRotate='none')

    # set scale to 1.0
    mc.setAttr('%s.scale' % dupCameraTrans, 1, 1, 1, type='double3')

    # connect focal length keys if there are any
    fl = mc.listConnections('%s.focalLength' % targetCameraShape)
    if fl != None:
        mc.connectAttr('%s.output' %
                       fl[0], '%s.focalLength' % dupCameraShape, f=True)

    # make locator scale visible in the channel box so that cameras
    # can be scaled in the viewer without render effects
    mc.setAttr('%s.locatorScale' % dupCameraShape, channelBox=1)

    # set a reasonable clipping plane
    # boujou defaults to a near/far setting of 0.001/10000000
    # maya's default of 0.1/10000 is more reasonable
    mc.setAttr('%s.nearClipPlane' % dupCameraShape, 0.1)
    mc.setAttr('%s.farClipPlane' % dupCameraShape, 10000)

    # make the new camera the renderable one
    mc.setAttr('%s.renderable' % dupCameraShape, True)
    mc.setAttr('%s.renderable' % targetCameraShape, False)

    # sane shutter angle
    mc.setAttr('%s.shutterAngle' % dupCameraShape, 180)
    mc.setAttr('%s.shutterAngle' % targetCameraShape, 180)

    # hide tracking cam and make sure visibilty is unlocked on both cameras
    mc.setAttr('%s.v' % targetCameraShape, lock=False)
    mc.setAttr('%s.v' % dupCameraShape, lock=False)
    mc.setAttr('%s.v' % targetCameraTrans, False)

    # //////////////////////////////////////////////////////////////
    # bake keyframes on new cam
    # //////////////////////////////////////////////////////////////

    # hide camera/imagePlane view if requested to accelerate baking
    # restoreCamPanes = []
    # restoreImgPanes = []
    # visModelPanes = getVisibleModelPanels()
    # for v in visModelPanes:
    #     # this modelPane is both visible and has cameras on
    #     # so we need to hide it here and restore it after bake
    #     if mc.modelEditor(v, q=True, cameras=True):
    #         mc.modelEditor(v, e=True, cameras=False)
    #         restoreCamPanes.append(v)

    #     if mc.modelEditor(v, q=True, imagePlane=True):
    #         mc.modelEditor(v, e=True, imagePlane=False)
    #         restoreImgPanes.append(v)

    # # turn off display mode on imagePlanes and force texture type
    # # this works around a bug on some graphics card where the ip is
    # # still visible after turning it off in the modelPanel
    # ipOrigState = []
    # imagePlanes = mc.ls(type='imagePlane')
    # if imagePlanes:
    #     for ip in imagePlanes:
    #         # store the imagePlane's original settings in a list dict
    #         dmode = mc.getAttr('%s.displayMode' % ip)
    #         dtype = mc.getAttr('%s.type' % ip)
    #         ipOrigState.append( {'name':ip, 'displayMode':dmode, 'type':dtype} )

    #         mc.setAttr('%s.displayMode' % ip, 0) # none
    #         mc.setAttr('%s.type' % ip, 1)        # texture

    try:
        targetImagePlaneShape = getAttr("%s.imagePlane" % targetCamera)[0].getShape().name()
        mc.setAttr('%s.displayOnlyIfCurrent' % targetImagePlaneShape, True)
        mel.eval('AEchangeLookThroughCamera %s;' % targetImagePlaneShape)

        dupImagePlaneShape = getAttr("%s.imagePlane" % tempDup)[0].getShape().name()
        mc.setAttr('%s.displayOnlyIfCurrent' % dupImagePlaneShape, True)
        mel.eval('AEchangeLookThroughCamera %s;' % dupImagePlaneShape)
    except Exception, e:
        print "WARNING: Unable to set displayOnlyIfCurrent on camera image planes"
        import traceback
        print traceback.format_exc(e)

    states = disableCamerasAndImagePlanes()

    mc.bakeResults(dupCameraTrans, simulation=True,
                   t=(startFrame, endFrame), sampleBy=stepSize,
                   disableImplicitControl=True, preserveOutsideKeys=False,
                   sparseAnimCurveBake=False, removeBakedAttributeFromLayer=False,
                   bakeOnOverrideLayer=False, controlPoints=False,
                   at=('tx', 'ty', 'tz', 'rx', 'ry', 'rz'), shape=True)

    enableCamerasAndImagePlanes(states)

    # # restore camera visibility in any panes where we hid camera vis
    # for v in restoreCamPanes:
    #     mc.modelEditor(v, e=True, cameras=True)
    # for v in restoreImgPanes:
    #     mc.modelEditor(v, e=True, imagePlane=True)

    # # restore image planes
    # for ip in ipOrigState:
    #     mc.setAttr('%s.displayMode' % ip['name'], ip['displayMode'])
    #     mc.setAttr('%s.type'        % ip['name'], ip['type'])

    # delete parent constraint as it isn't needed any more
    mc.delete(parentConstraint[0])

    if connectIPs:
        duplicateImagePlane(targetCameraTrans, dupCameraTrans)

    # //////////////////////////////////////////////////////////////
    # relock attributes
    # //////////////////////////////////////////////////////////////

    # lock transform attributes on both cameras
    for a in camXformAttrs:
        mc.setAttr('%s.%s' % (dupCameraTrans, a), lock=True)
        mc.setAttr('%s.%s' % (targetCameraTrans, a), lock=True)

    # lock shape attributes on both cameras
    for a in camShapeAttrs:
        mc.setAttr('%s.%s' % (dupCameraShape, a), lock=True)
        mc.setAttr('%s.%s' % (targetCameraShape, a), lock=True)

    # //////////////////////////////////////////////////////////////
    # rename and/or delete original camera
    # //////////////////////////////////////////////////////////////

    # rename target tracking camera
    if renameTargetCam:
        # rename dup camera
        if not mc.objExists(targetCameraNewName):
            mc.rename(targetCamera, targetCameraNewName)
        else:
            mc.rename(targetCamera, '%s#' % targetCameraNewName)

    # rename dup camera
    if not mc.objExists(bakeCameraName):
        mc.rename(dupCameraTrans, bakeCameraName)
    else:
        # another camera has this name so rename it first
        mc.rename(bakeCameraName, '%s_old#' % bakeCameraName)
        # safe to rename dup cam now
        mc.rename(dupCameraTrans, bakeCameraName)


class ConsistentCameraExportUI:
    export_ext_dict = {'Maya ASCII': 'ma',
                       'Maya Binary': 'mb',
                       'Alembic': 'abc',
                       'FBX': 'fbx',
                       'Nuke Script': 'nk',
                       'OBJ': 'obj'}

    def __init__(self):
        """ Builds the UI window. """
        winx = 500
        pad = 2
        std_y = 24
        btn_x = 140
        menu_x = 140

        self.name = "ConsistentCameraExport"
        self.title = "Consistent Camera Export"

        # recreate the window if needed
        if mc.window(self.name, q=1, exists=1):
            mc.deleteUI(self.name)

        self.window = mc.window(
            self.name, title=self.title, resizeToFitChildren=True, sizeable=False)

        self.column = mc.columnLayout(
            adjustableColumn=True, cal='center', cat=['both', 0])

        #######################################################################

        self.camOps = mc.frameLayout(label='Bake Camera To World Space',
                                     borderStyle='etchedIn', cll=True)

        self.formCamOps = mc.formLayout(numberOfDivisions=100)

        minFrame = mc.playbackOptions(q=True, minTime=True)
        maxFrame = mc.playbackOptions(q=True, maxTime=True)
        self.frameRange = mc.intFieldGrp(numberOfFields=2, label='Frame Range:  ', value1=minFrame,
                                         value2=maxFrame, columnWidth3=[
                                             winx / 3, winx / 8, winx / 8],
                                         height=std_y)

        self.stepSize = mc.floatFieldGrp(numberOfFields=1, label='Step Size:  ', value1=1.0,
                                         columnWidth2=[winx / 3, winx / 8], height=std_y)

        self.targetCam = mc.textFieldButtonGrp(label='Target Camera:  ', text=self.firstSceneCamera(),
                                               buttonLabel='  Load Selected  ',
                                               columnWidth3=[
                                                   winx / 3, winx / 3, winx / 3],
                                               columnAlign3=[
                                                   'right', 'center', 'left'],
                                               buttonCommand=self.loadCam,
                                               height=std_y)
        mc.textFieldButtonGrp(self.targetCam, e=True,
                              columnAttach=[3, 'left', pad * 2])
        mc.textFieldButtonGrp(self.targetCam, e=True, ad3=2)

        self.bakeName = mc.textFieldGrp(label='Baked Camera Name:  ', text='RenderCam',
                                        columnWidth2=[winx / 3, winx / 3, ],
                                        columnAlign2=['right', 'center'],
                                        editable=False,
                                        height=std_y)
        mc.textFieldGrp(self.bakeName, e=True, columnAttach=[2, 'left', 0])
        mc.textFieldGrp(self.bakeName, e=True, ad2=2)

        self.targetNewName = mc.textFieldGrp(label='Target Camera Rename:  ', text='TrackingCam',
                                             columnWidth2=[
                                                 winx / 3, winx / 3, ],
                                             columnAlign2=['right', 'center'],
                                             editable=False,
                                             height=std_y)
        mc.textFieldGrp(self.targetNewName, e=True,
                        columnAttach=[2, 'left', 0])
        mc.textFieldGrp(self.targetNewName, e=True, ad2=2)

        self.renameTargetCam = mc.checkBoxGrp(numberOfCheckBoxes=1, label='Rename Target Camera:  ',
                                              columnWidth2=[winx / 3, winx / 8], v1=False, height=std_y)

        self.connectIPs = mc.checkBoxGrp(numberOfCheckBoxes=1, label='Duplicate Image Planes:  ',
                                         columnWidth2=[winx / 3, winx / 8], v1=True, height=std_y)

        self.bake = mc.button(label='Bake Camera To World', command=self.bakeCamera, width=btn_x,
                                    bgc=[0.40, 0.40, 0.75],
                                    height=std_y)

        self.endBake = mc.separator(style='none', height=pad)

        #######################################################################

        mc.setParent(self.column)

        self.locOps = mc.frameLayout(label='Copy Locators To World Space',
                                     borderStyle='etchedIn', cll=True)

        self.formLocOps = mc.formLayout(numberOfDivisions=100)

        self.selectLoc = mc.textFieldButtonGrp(label='Locators To Copy:  ',
                                               text=self.loadAllLocators(),
                                               buttonLabel='  Load Selected  ',
                                               columnWidth3=[
                                                   winx / 3, winx / 3, winx / 3],
                                               columnAlign3=[
                                                   'right', 'center', 'left'],
                                               buttonCommand=self.loadLocators,
                                               height=std_y)
        mc.textFieldButtonGrp(self.selectLoc, e=True,
                              columnAttach=[3, 'left', pad * 2])
        mc.textFieldButtonGrp(self.selectLoc, e=True, ad3=2)

        self.locName = mc.textFieldGrp(label='Locators Prefix:  ', text='Tracker_',
                                       columnWidth2=[winx / 3, winx / 3, ],
                                       columnAlign2=['right', 'center'],
                                       editable=False,
                                       height=std_y)
        mc.textFieldGrp(self.locName, e=True, columnAttach=[2, 'left', 0])
        mc.textFieldGrp(self.locName, e=True, ad2=2)

        self.locGrpName = mc.textFieldGrp(label='Worldspace Group Name:  ', text='TrackedPoints',
                                          columnWidth2=[winx / 3, winx / 3, ],
                                          columnAlign2=['right', 'center'],
                                          editable=False,
                                          height=std_y)
        mc.textFieldGrp(self.locGrpName, e=True, columnAttach=[2, 'left', 0])
        mc.textFieldGrp(self.locGrpName, e=True, ad2=2)

        self.extractLoc = mc.button(label='Copy Locators To World', command=self.extractLocators,
                                    bgc=[0.35, 0.7, 0.35], width=btn_x, height=std_y)

        self.endLocOps = mc.separator(style='none', height=pad)

        #######################################################################

        mc.setParent(self.column)

        self.targetOps = mc.frameLayout(label='Export Targets',
                                        borderStyle='etchedIn', cll=True)

        self.formTargetOps = mc.formLayout(numberOfDivisions=100)

        self.selectCam = mc.textFieldButtonGrp(label='Export Camera:  ',
                                               text='RenderCam',
                                               buttonLabel='  Load Selected  ',
                                               columnWidth3=[
                                                   winx / 3, winx / 3, winx / 3],
                                               columnAlign3=[
                                                   'right', 'center', 'left'],
                                               buttonCommand=self.loadSelectedCam,
                                               height=std_y)
        mc.textFieldButtonGrp(self.selectCam, e=True,
                              columnAttach=[3, 'left', pad * 2])
        mc.textFieldButtonGrp(self.selectCam, e=True, ad3=2)

        self.selectLayoutGrp = mc.textFieldButtonGrp(label='Export Layout Group:  ',
                                                     text=self.loadLayoutGrp(),
                                                     buttonLabel='  Load Selected  ',
                                                     columnWidth3=[
                                                         winx / 3, winx / 3, winx / 3],
                                                     columnAlign3=[
                                                         'right', 'center', 'left'],
                                                     buttonCommand=self.loadSelectedLayoutGrp,
                                                     height=std_y)
        mc.textFieldButtonGrp(self.selectLayoutGrp, e=True,
                              columnAttach=[3, 'left', pad * 2])
        mc.textFieldButtonGrp(self.selectLayoutGrp, e=True, ad3=2)

        self.endLoc = mc.separator(style='none', height=pad)

        #######################################################################

        mc.setParent(self.column)

        self.layout = mc.frameLayout(
            label='Export Formats Camera', borderStyle='etchedIn', cll=True)

        self.formCamExpOps = mc.formLayout(numberOfDivisions=100)

        self.exportCamMaya = mc.optionMenuGrp(label='Export Maya:  ', columnWidth2=[winx / 3, winx / 8],
                                              height=std_y)
        mc.menuItem(label='None')
        mc.menuItem(label='Alembic')
        mc.menuItem(label='FBX')
        mc.menuItem(label='Maya ASCII')
        mc.menuItem(label='Maya Binary')
        mc.optionMenuGrp(self.exportCamMaya, e=True, select=5)

        self.exportCamNuke = mc.optionMenuGrp(label='Export Nuke:  ', columnWidth2=[winx / 3, winx / 8],
                                              height=std_y)
        mc.menuItem(label='None')
        mc.menuItem(label='Alembic')
        mc.menuItem(label='FBX')
        mc.menuItem(label='Nuke Script')
        mc.optionMenuGrp(self.exportCamNuke, e=True, select=4)

        self.exportCamHou = mc.optionMenuGrp(label='Export Houdini:  ', columnWidth2=[winx / 3, winx / 8],
                                             height=std_y)
        mc.menuItem(label='None')
        mc.menuItem(label='Alembic')
        mc.menuItem(label='FBX')
        mc.optionMenuGrp(self.exportCamHou, e=True, select=2)

        self.exportCamDir = mc.optionMenuGrp(label='Export Directories:  ', columnWidth2=[winx / 3, winx / 8],
                                             height=std_y)
        mc.menuItem(label='Default Locations')
        mc.menuItem(label='Choose Directories')
        mc.optionMenuGrp(self.exportCamDir, e=True, select=1)

        self.exportCam = mc.button(label='Export RenderCam', command=self.exportUICamera, width=btn_x,
                                   bgc=[0.40, 0.40, 0.75], height=std_y)

        self.endCamExport = mc.separator(style='none', height=pad)

        #######################################################################

        mc.setParent(self.column)

        self.layout = mc.frameLayout(
            label='Export Formats Layout', borderStyle='etchedIn', cll=True)

        self.formLayoutExpOps = mc.formLayout(numberOfDivisions=100)

        self.exportLayoutMaya = mc.optionMenuGrp(label='Export Maya:  ', columnWidth2=[winx / 3, winx / 8],
                                                 height=std_y)
        mc.menuItem(label='None')
        mc.menuItem(label='Alembic')
        mc.menuItem(label='FBX')
        mc.menuItem(label='Maya ASCII')
        mc.menuItem(label='Maya Binary')
        mc.optionMenuGrp(self.exportLayoutMaya, e=True, select=5)

        self.exportLayoutNuke = mc.optionMenuGrp(label='Export Nuke:  ', columnWidth2=[winx / 3, winx / 8],
                                                 height=std_y)
        mc.menuItem(label='None')
        mc.menuItem(label='Alembic')
        mc.menuItem(label='FBX')
        mc.menuItem(label='Nuke Script')
        mc.menuItem(label='OBJ Geo / FBX Loc')
        mc.optionMenuGrp(self.exportLayoutNuke, e=True, select=5)

        self.exportLayoutHou = mc.optionMenuGrp(label='Export Houdini:  ', columnWidth2=[winx / 3, winx / 8],
                                                height=std_y)
        mc.menuItem(label='None')
        mc.menuItem(label='Alembic')
        mc.menuItem(label='FBX')
        mc.optionMenuGrp(self.exportLayoutHou, e=True, select=2)

        self.exportLayoutDir = mc.optionMenuGrp(label='Export Directories:  ', columnWidth2=[winx / 3, winx / 8],
                                                height=std_y)
        mc.menuItem(label='Default Locations')
        mc.menuItem(label='Choose Directories')
        mc.optionMenuGrp(self.exportLayoutDir, e=True, select=1)

        self.exportLayout = mc.button(label='Export Layout', command=self.exportUILayout, width=btn_x,
                                      bgc=[0.35, 0.7, 0.35], height=std_y)

        self.endLayoutExport = mc.separator(style='none', height=pad)

        #######################################################################

        mc.formLayout(self.formCamOps, edit=True,
                      attachForm=[
                          (self.frameRange,      'top',   pad),
                          (self.frameRange,      'left',  pad),
                          (self.frameRange,      'right', pad),
                          (self.stepSize,        'left',  pad),
                          (self.stepSize,        'right', pad),
                          (self.targetCam,       'left',  pad),
                          (self.targetCam,       'right', pad),
                          (self.bakeName,        'left',  pad),
                          (self.bakeName,        'right', pad),
                          (self.targetNewName,   'left',  pad),
                          (self.targetNewName,   'right', pad),
                          (self.renameTargetCam, 'left',  pad),
                          (self.renameTargetCam, 'right', pad),
                          (self.connectIPs,      'left',  pad),
                          (self.connectIPs,      'right', pad),
                          (self.bake,            'left',  pad + winx / 3),
                          (self.endBake,         'left',  pad),
                          (self.endBake,         'right', pad),
                      ],
                      attachControl=[
                          (self.stepSize,        'top', pad, self.frameRange),
                          (self.targetCam,       'top', pad, self.stepSize),
                          (self.bakeName,        'top', pad, self.targetCam),
                          (self.targetNewName,   'top', pad, self.bakeName),
                          (self.renameTargetCam, 'top', pad, self.targetNewName),
                          (self.connectIPs,      'top', pad, self.renameTargetCam),
                          (self.bake,            'top', pad, self.connectIPs),
                          (self.endBake,         'top', pad, self.bake),
                      ]
                      )

        mc.formLayout(self.formLocOps, edit=True,
                      attachForm=[
                          (self.selectLoc,  'top',   pad),
                          (self.selectLoc,  'left',  pad),
                          (self.selectLoc,  'right', pad),
                          (self.locName,    'left',  pad),
                          (self.locName,    'right', pad),
                          (self.locGrpName, 'left',  pad),
                          (self.locGrpName, 'right', pad),
                          (self.extractLoc, 'left',  pad + winx / 3),
                          (self.endLocOps,  'left',  pad),
                          (self.endLocOps,  'right', pad),
                      ],
                      attachControl=[
                          (self.locName,    'top', pad, self.selectLoc),
                          (self.locGrpName, 'top', pad, self.locName),
                          (self.extractLoc, 'top', pad, self.locGrpName),
                          (self.endLocOps,  'top', pad, self.extractLoc),
                      ]
                      )

        mc.formLayout(self.formTargetOps, edit=True,
                      attachForm=[
                          (self.selectCam,        'top',   pad),
                          (self.selectCam,        'left',  pad),
                          (self.selectCam,        'right', pad),
                          (self.selectLayoutGrp,  'top',   pad),
                          (self.selectLayoutGrp,  'left',  pad),
                          (self.selectLayoutGrp,  'right', pad),
                          (self.endLoc,           'left',  pad),
                          (self.endLoc,           'right', pad),
                      ],
                      attachControl=[
                          (self.selectLayoutGrp,  'top', pad, self.selectCam),
                          (self.endLoc,           'top',
                           pad, self.selectLayoutGrp),
                      ]
                      )

        mc.formLayout(self.formCamExpOps, edit=True,
                      attachForm=[
                          (self.exportCamMaya, 'top',   pad),
                          (self.exportCamMaya, 'left',  pad),
                          (self.exportCamMaya, 'right', pad),
                          (self.exportCamNuke, 'left',  pad),
                          (self.exportCamNuke, 'right', pad),
                          (self.exportCamHou,  'left',  pad),
                          (self.exportCamHou,  'right', pad),
                          (self.exportCamDir,  'left',  pad),
                          (self.exportCamDir,  'right', pad),
                          (self.exportCam,     'left',  pad + winx / 3),
                          (self.endCamExport,  'left',  pad),
                          (self.endCamExport,  'right', pad),
                      ],
                      attachControl=[
                          (self.exportCamNuke, 'top',  pad, self.exportCamMaya),
                          (self.exportCamHou,  'top',  pad, self.exportCamNuke),
                          (self.exportCamDir,  'top',  pad, self.exportCamHou),
                          (self.exportCam,     'top',  pad, self.exportCamDir),
                          (self.endCamExport,  'top',  pad, self.exportCam),
                      ]
                      )

        mc.formLayout(self.formLayoutExpOps, edit=True,
                      attachForm=[
                          (self.exportLayoutMaya, 'top',   pad),
                          (self.exportLayoutMaya, 'left',  pad),
                          (self.exportLayoutMaya, 'right', pad),
                          (self.exportLayoutNuke, 'left',  pad),
                          (self.exportLayoutNuke, 'right', pad),
                          (self.exportLayoutHou,  'left',  pad),
                          (self.exportLayoutHou,  'right', pad),
                          (self.exportLayoutDir,  'left',  pad),
                          (self.exportLayoutDir,  'right', pad),
                          (self.exportLayout,     'left',  pad + winx / 3),
                          (self.endLayoutExport,  'left',  pad),
                          (self.endLayoutExport,  'right', pad),
                      ],
                      attachControl=[
                          (self.exportLayoutNuke, 'top',
                           pad, self.exportLayoutMaya),
                          (self.exportLayoutHou,  'top',
                           pad, self.exportLayoutNuke),
                          (self.exportLayoutDir,  'top',
                           pad, self.exportLayoutHou),
                          (self.exportLayout,     'top',
                           pad, self.exportLayoutDir),
                          (self.endLayoutExport,  'top',  pad, self.exportLayout),
                      ]
                      )

        mc.showWindow(self.window)

    def firstSceneCamera(self):
        """ Called by init() so that on creation the UI grabs a logical
            camera to bake. We never bake the cameras in ignoreSet. """
        ignoreSet = set(['top', 'side', 'front', 'persp'])

        for cam in sorted(mc.ls(exactType='camera')):
            camXform, camShape = getCameraXformAndShape(cam)

            # takes the first valid camera
            if camXform not in ignoreSet:
                return camXform

        return 'TrackingCam'  # default if no cameras found

    def loadLayoutGrp(self):
        if mc.objExists('Layout_GRP'):
            return 'Layout_GRP'
        else:
            return ''

    def loadAllLocators(self):
        """ Called by init() so that on creation the UI grabs a locators.
            These locators are returned as a space separated list to display
            in the UI. """
        locShapes = mc.ls(exactType='locator')

        if locShapes:
            locators = []

            for l in locShapes:
                locXform, locShape = getLocatorXformAndShape(l)
                locators.append(locXform)

            return ' '.join(locators)

        else:
            return ''

    ### button cmd ###
    def loadCam(self):
        """ This is called by the Load Camera UI button. The first
            valid camera found in the selection list is set in the
            textFieldGrp. """
        sel = mc.ls(sl=True)
        print sel
        if sel:
            for s in sel:
                try:
                    camXform, camShape = getCameraXformAndShape(s)
                    # setting the first camera we found
                    trackingCamera = mc.textFieldButtonGrp(
                        self.targetCam, e=True, text=camXform)
                    return
                except:
                    # couldn't get camera, handle the exception by moving
                    # to the next item in the selection
                    continue

    ### button cmd ###
    def loadSelectedCam(self):
        cameras = []
        possibleGroup = []

        sel = mc.ls(sl=True)
        for s in sel:
            try:
                camXform, camShape = getCameraXformAndShape(s)
                cameras.append(camXform)
            except:
                possibleGroup.append(s)

        for p in possibleGroup:
            rels = mc.listRelatives(
                p, ad=True, ni=True, type='transform', pa=True)
            if rels:
                for r in rels:
                    try:
                        camXform, camShape = getCameraXformAndShape(r)
                        cameras.append(camXform)
                    except:
                        continue
        if len(cameras) > 0:
            mc.textFieldButtonGrp(self.selectCam, e=True, text=cameras[0])

    ### button cmd ###
    def loadSelectedLayoutGrp(self):
        layouts = []
        possibleGroup = []

        sel = mc.ls(sl=True)
        for s in sel:
            layouts.append(s)

        if len(layouts) > 0:
            mc.textFieldButtonGrp(self.selectLayoutGrp,
                                  e=True, text=layouts[0])

    ### button cmd ###
    def loadLocators(self, *args):
        """ Find all the selected locators and any locators in selected groups
            and set the text field of self.selectLoc to be a space seprated string
            representing that list: ' '.join(locators) """
        locators = []
        possibleGroup = []

        sel = mc.ls(sl=True)
        for s in sel:
            try:
                locXform, locShape = getLocatorXformAndShape(s)
                locators.append(locXform)
            except:
                possibleGroup.append(s)

        for p in possibleGroup:
            rels = mc.listRelatives(
                p, ad=True, ni=True, type='transform', pa=True)
            if rels:
                for r in rels:
                    try:
                        locXform, locShape = getLocatorXformAndShape(r)
                        locators.append(locXform)
                    except:
                        continue

        mc.textFieldButtonGrp(self.selectLoc, e=True, text=' '.join(locators))

    ### button cmd ###
    def bakeCamera(self, *args):
        """ Called by the Bake Camera button, this UI helper function reads
            the relevent UI values and passes them to duplicateCameraAndBake()."""
        startFrame = mc.intFieldGrp(self.frameRange, q=True, value1=True)
        endFrame = mc.intFieldGrp(self.frameRange, q=True, value2=True)
        stepSize = mc.floatFieldGrp(self.stepSize, q=True, value1=True)
        targetCamera = mc.textFieldButtonGrp(self.targetCam, q=True, text=True)
        bakeCameraName = mc.textFieldGrp(self.bakeName, q=True, text=True)
        targetCameraNewName = mc.textFieldGrp(
            self.targetNewName, q=True, text=True)
        renameTargetCam = mc.checkBoxGrp(
            self.renameTargetCam, q=True, value1=True)
        connectIPs = mc.checkBoxGrp(self.connectIPs, q=True, value1=True)

        duplicateCameraAndBake(startFrame, endFrame, stepSize, targetCamera,
                               bakeCameraName, targetCameraNewName, renameTargetCam, connectIPs)

    ### button cmd ###
    def extractLocators(self, *args):
        """ Called by the Copy Locators to World button, this UI helper function reads
            the relevent UI values and passes them to duplicateLocatorsToWorldspace()."""
        locatorsGroupStr = mc.textFieldButtonGrp(
            self.selectLoc, q=True, text=True)
        locatorPrefix = mc.textFieldGrp(self.locName, q=True, text=True)
        locatorNewGrp = mc.textFieldGrp(self.locGrpName, q=True, text=True)

        duplicateLocatorsToWorldspace(
            locatorsGroupStr, locatorPrefix, locatorNewGrp)

    def exportCamera(self, camXform):
        """ This UI helper function reads the relevent UI values and passes them
            to correct exporter function, but only if the optionMenuGrp for that
            export type (Maya,Nuke,Houdini) is not set to None. The camera that
            gets exported is camXform which was passed in by exportUICamera. """
        startFrame = mc.intFieldGrp(self.frameRange,   q=True, value1=True)
        endFrame = mc.intFieldGrp(self.frameRange,   q=True, value2=True)
        stepSize = mc.floatFieldGrp(self.stepSize,   q=True, value1=True)
        exportMayaType = mc.optionMenuGrp(
            self.exportCamMaya, q=True, value=True)
        exportNukeType = mc.optionMenuGrp(
            self.exportCamNuke, q=True, value=True)
        exportHouType = mc.optionMenuGrp(
            self.exportCamHou,  q=True, value=True)
        exportDirType = mc.optionMenuGrp(
            self.exportCamDir,  q=True, value=True)

        # export requested formats
        if exportMayaType != 'None':
            if DEBUG:
                print 'Exporting Maya camera.'
            self.exportCameraForMaya(
                startFrame, endFrame, stepSize, camXform, exportMayaType, exportDirType)

        if exportNukeType != 'None':
            if DEBUG:
                print 'Exporting Nuke camera.'
            self.exportCameraForNuke(
                startFrame, endFrame, stepSize, camXform, exportNukeType, exportDirType)

        if exportHouType != 'None':
            if DEBUG:
                print 'Exporting Houdini camera.'
            self.exportCameraForHoudini(
                startFrame, endFrame, stepSize, camXform, exportHouType, exportDirType)

    ### button cmd ###
    def exportUICamera(self, *args):
        """ Called by the Export RenderCam button, calls exportCamera() with the value of the
            textFieldGrp containing the baked camera name. This is so that users can first hit
            bake and then immediately hit export without making an export selection. """
        bakeCameraName = mc.textFieldGrp(self.bakeName, q=True, text=True)

        # verify export camera
        try:
            camXform, camShape = getCameraXformAndShape(bakeCameraName)
        except:
            raise Exception(
                'RenderCam does not exist. Try baking a RenderCam or select a camera to export.')

        self.exportCamera(camXform)

    def exportCameraForMaya(self, startFrame, endFrame, stepSize, camXform, exportType, exportDirType):
        """ Contains the different paths for different maya export types (alembic,fbx,etc). """
        # maya
        #     scenes
        #         Camera_Layout
        #             Publish (error check existance, create if needed)
        if DEBUG:
            print 'Exporting cam %s for Maya.' % camXform

        ####################################
        # Resolve path if needed
        ####################################
        try:
            ext = self.export_ext_dict[exportType]
        except KeyError:
            raise Exception(
                'Unknown export type specified for exportCameraForMaya().')

        export_dir = ''
        export_path = ''
        if exportDirType == 'Default Locations':

            project_path = mc.workspace(q=True, rd=True)
            scene_path = mc.file(q=True, sn=True)

            if project_path != '' and scene_path != '':
                export_dir = '%sscenes/Camera_Layout' % (project_path)

                # pull out the filename from the scene_path
                head, file_name_ext = os.path.split(scene_path)
                file_name, file_ext = os.path.splitext(file_name_ext)

                # set file_name to RenderCam
                file_name += '_RenderCam'
                # export_path = os.path.join( export_dir, '%s.%s' % (file_name,ext) )

                export_path = '%s/%s.%s' % (export_dir, file_name, ext)

                # create export directory if it doesn't exist
                if not os.path.exists(export_dir):
                    os.makedirs(export_dir)

        # have the user pick a file location because the default location couldn't be
        # found or because exportDirType == 'Choose Directories'
        if export_path == '':
            if exportDirType != 'Choose Directories':
                # we got here because the project wasn't set
                print 'Project was not set or the scene was not saved. Using export dialog.'
            export_path = mc.fileDialog2(
                fileFilter='%s (*.%s)' % (exportType, ext), dialogStyle=2, cap='Maya Camera Export')
            if export_path == None:
                return
            else:
                export_path = export_path[0]
            export_dir = os.path.split(export_path)[0]

        if DEBUG:
            print 'Export dir:  %s' % export_dir
            print 'Export path: %s' % export_path

        ####################################
        # Maya export
        ####################################
        if exportType == 'Maya ASCII':
            mc.select(cl=True)
            mc.select(camXform)
            mc.file(export_path, force=True, options="v=0;",
                    typ='mayaAscii', es=True)

        elif exportType == 'Maya Binary':
            mc.select(cl=True)
            mc.select(camXform)
            mc.file(export_path, force=True, options="v=0;",
                    typ='mayaBinary', es=True)

        elif exportType == 'Alembic':
            # load alem plug if needed
            if not mc.pluginInfo('AbcExport', q=True, loaded=True):
                mc.loadPlugin('AbcExport')

            # build the ABC export String
            export_obj_str = '-root |%s ' % camXform
            exportCmd = ('AbcExport -j "-frameRange %d %d ' %
                         (startFrame, endFrame))
            exportCmd += ('-uvWrite -eulerFilter -step %f -worldSpace %s ' %
                          (stepSize, export_obj_str))
            exportCmd += ('-file \\"%s\\""' % export_path)

            # export
            states = disableCamerasAndImagePlanes()
            mel.eval(exportCmd)
            enableCamerasAndImagePlanes(states)

        elif exportType == 'FBX':
            states = disableCamerasAndImagePlanes()
            exportFBX.exportFBXcam(camXform, export_path)
            enableCamerasAndImagePlanes(states)

    def exportCameraForNuke(self, startFrame, endFrame, stepSize, camXform, exportType, exportDirType):
        """ Contains the different paths for different nuke export types (alembic,fbx,etc). """
        # nuke
        #     from_maya
        if DEBUG:
            print 'Exporting cam %s for Nuke.' % camXform

        ####################################
        # Resolve path if needed
        ####################################
        try:
            ext = self.export_ext_dict[exportType]
        except KeyError:
            raise Exception(
                'Unknown export type specified for exportCameraForNuke(): %s' % exportType)

        export_dir = ''
        export_path = ''
        if exportDirType == 'Default Locations':

            project_path = mc.workspace(q=True, rd=True)
            scene_path = mc.file(q=True, sn=True)

            if project_path != '' and scene_path != '':
                nuke_dir = nukeDirFromMaya(project_path)
                export_dir = os.path.join(nuke_dir, 'from_maya')

                # pull out the filename from the scene_path
                head, file_name_ext = os.path.split(scene_path)
                file_name, file_ext = os.path.splitext(file_name_ext)

                # set file_name to RenderCam
                file_name += '_RenderCam'

                export_path = os.path.join(
                    export_dir, '%s.%s' % (file_name, ext))

                # create export directory if it doesn't exist
                if not os.path.exists(export_dir):
                    os.makedirs(export_dir)

        # have the user pick a file location because the default location couldn't be
        # found or because exportDirType == 'Choose Directories'
        if export_path == '':
            if exportDirType != 'Choose Directories':
                # we got here because the project wasn't set
                print 'Project was not set or the scene was not saved. Using export dialog.'
            export_path = mc.fileDialog2(
                fileFilter='%s (*.%s)' % (exportType, ext), dialogStyle=2, cap='Nuke Camera Export')
            if export_path == None:
                return
            else:
                export_path = export_path[0]
            export_dir = os.path.split(export_path)[0]

        if DEBUG:
            print 'Export dir:  %s' % export_dir
            print 'Export path: %s' % export_path

        ####################################
        # Maya export
        ####################################
        states = disableCamerasAndImagePlanes()
        if exportType == 'Alembic':
            # load alem plug if needed
            if not mc.pluginInfo('AbcExport', q=True, loaded=True):
                mc.loadPlugin('AbcExport')

            # will choke on windows backslashes
            export_path = export_path.replace('\\', '/')

            # build the ABC export String
            export_obj_str = '-root |%s ' % camXform
            exportCmd = ('AbcExport -j "-frameRange %d %d ' %
                         (startFrame, endFrame))
            exportCmd += ('-uvWrite -eulerFilter -step %f -worldSpace %s ' %
                          (stepSize, export_obj_str))
            exportCmd += ('-file \\"%s\\""' % export_path)

            # export
            mel.eval(exportCmd)

        elif exportType == 'FBX':
            exportFBX.exportFBXcam(camXform, export_path)

        elif exportType == 'Nuke Script':
            export_dir = str(export_dir) + '/'
            print "Export path: " + str(export_path)
            exportNuke.exportCam2Nuke(
                camXform, export_path, startFrame, endFrame, 1)
        enableCamerasAndImagePlanes(states)

    def exportCameraForHoudini(self, startFrame, endFrame, stepSize, camXform, exportType, exportDirType):
        """ Containts the different paths for different houdini export types (alembic,fbx,etc). """
        # houdini
        #     scenes
        #         Camera_Layout
        #             Publish
        if DEBUG:
            print 'Exporting cam %s for Houdini.' % camXform

        ####################################
        # Resolve path if needed
        ####################################
        try:
            ext = self.export_ext_dict[exportType]
        except KeyError:
            raise Exception(
                'Unknown export type specified for exportCameraForHoudini(): %s' % exportType)

        export_dir = ''
        export_path = ''
        if exportDirType == 'Default Locations':

            project_path = mc.workspace(q=True, rd=True)
            scene_path = mc.file(q=True, sn=True)

            if project_path != '' and scene_path != '':
                hou_dir = houdiniDirFromMaya(project_path)
                export_dir = os.path.join(
                    hou_dir, 'scenes', 'from_maya')
                export_dir = os.path.normpath(export_dir)

                # pull out the filename from the scene_path
                head, file_name_ext = os.path.split(scene_path)
                file_name, file_ext = os.path.splitext(file_name_ext)

                # set file_name to RenderCam
                file_name += '_RenderCam'

                export_path = os.path.join(
                    export_dir, '%s.%s' % (file_name, ext))

                # create export directory if it doesn't exist
                if not os.path.exists(export_dir):
                    os.makedirs(export_dir)

        # have the user pick a file location because the default location couldn't be
        # found or because exportDirType == 'Choose Directories'
        if export_path == '':
            if exportDirType != 'Choose Directories':
                # we got here because the project wasn't set
                print 'Project was not set or the scene was not saved. Using export dialog.'
            export_path = mc.fileDialog2(
                fileFilter='%s (*.%s)' % (exportType, ext), dialogStyle=2, cap='Houdini Camera Export')
            if export_path == None:
                return
            else:
                export_path = export_path[0]
            export_dir = os.path.split(export_path)[0]

        if DEBUG:
            print 'Export dir:  %s' % export_dir
            print 'Export path: %s' % export_path

        ####################################
        # Maya export
        ####################################
        if exportType == 'Alembic':
            # load alem plug if needed
            if not mc.pluginInfo('AbcExport', q=True, loaded=True):
                mc.loadPlugin('AbcExport')

            # fbx exporter will choke on windows backslashes
            export_path = export_path.replace('\\', '/')

            # build the ABC export String
            export_obj_str = '-root |%s ' % camXform
            exportCmd = ('AbcExport -j "-frameRange %d %d ' %
                         (startFrame, endFrame))
            exportCmd += ('-uvWrite -eulerFilter -step %f -worldSpace %s ' %
                          (stepSize, export_obj_str))
            exportCmd += ('-file \\"%s\\""' % export_path)

            # export
            states = disableCamerasAndImagePlanes()
            mel.eval(exportCmd)
            enableCamerasAndImagePlanes(states)

        elif exportType == 'FBX':
            states = disableCamerasAndImagePlanes()
            exportFBX.exportFBXcam(camXform, export_path)
            enableCamerasAndImagePlanes(states)

    def exportLayoutGroup(self, objsXform, layoutGrpName):
        """ UI helper, mirrors exportCamera() functionality but for layout export. """
        """ This UI helper function reads the relevent UI values and passes them
            to correct exporter function, but only if the optionMenuGrp for that
            export type (Maya,Nuke,Houdini) is not set to None. The geo/locators that
            get exported are a list (objsXform) which was passed in by exportUILayout. """
        startFrame = mc.intFieldGrp(self.frameRange, q=True, value1=True)
        endFrame = mc.intFieldGrp(self.frameRange,   q=True, value2=True)
        stepSize = mc.floatFieldGrp(self.stepSize,   q=True, value1=True)
        exportMayaType = mc.optionMenuGrp(
            self.exportLayoutMaya, q=True, value=True)
        exportNukeType = mc.optionMenuGrp(
            self.exportLayoutNuke, q=True, value=True)
        exportHouType = mc.optionMenuGrp(
            self.exportLayoutHou,  q=True, value=True)
        exportDirType = mc.optionMenuGrp(
            self.exportLayoutDir,  q=True, value=True)
        print "Inside Export Layout"

        # export requested formats
        if exportMayaType != 'None':
            if DEBUG:
                print 'Exporting Maya layout.'
            self.exportLayoutForMaya(startFrame, endFrame, stepSize,
                                     objsXform, layoutGrpName, exportMayaType, exportDirType)

        if exportNukeType != 'None':
            if DEBUG:
                print 'Exporting Nuke layout.'
            self.exportLayoutForNuke(startFrame, endFrame, stepSize,
                                     objsXform, layoutGrpName, exportNukeType, exportDirType)

        if exportHouType != 'None':
            if DEBUG:
                print 'Exporting Houdini layout.'
            self.exportLayoutForHoudini(
                startFrame, endFrame, stepSize, objsXform, layoutGrpName, exportHouType, exportDirType)

    # button cmd #
    def exportUILayout(self, *args):
        """ Called by the Export Layout button (mirrors exportUICamera()), calls exportLayout() with the value of the
            textFieldGrp containing the layout group name. """
        layoutGroupName = mc.textFieldButtonGrp(
            self.selectLayoutGrp, q=True, text=True)
        if layoutGroupName == '':
            # Check again to see if it exists
            if not mc.objExists('Layout_GRP'):
                mc.warning("No Layout Group to Export!")
                return
            else:
                mc.textFieldButtonGrp(
                    self.selectLayoutGrp, e=True, text='Layout_GRP')

        layoutGroupName = mc.textFieldButtonGrp(
            self.selectLayoutGrp, q=True, text=True)
        trackedPointsFolder = mc.listRelatives(layoutGroupName, children=True)
        objsToExport = mc.listRelatives(trackedPointsFolder, children=True)
        objsXform = []

        # verify export objects
        for objToExport in objsToExport:
            try:
                objXform, objShape = getLayoutXformAndShape(objToExport)
                objsXform.append(objXform)
            except:
                raise Exception('Layout format incorrect.')

        self.exportLayoutGroup(objsXform, layoutGroupName)

    def exportLayoutForMaya(self, startFrame, endFrame, stepSize, objsXform, layoutGrpName, exportType, exportDirType):
        """ Contains the different paths for different maya export types (alembic,fbx,etc). """
        # maya
        #     scenes
        #         Camera_Layout
        #             Publish (error check existance, create if needed)
        if DEBUG:
            print 'Exporting the following objects for Maya....'
            objectsString = ''
            for objXform in objsXform:
                objectsString = str(objectsString) + ' ' + str(objXform)
            print str(objectsString)

        ####################################
        # Resolve path if needed
        ####################################
        try:
            ext = self.export_ext_dict[exportType]
        except KeyError:
            raise Exception(
                'Unknown export type specified for exportLocatorsForMaya().')

        export_dir = ''
        export_path = ''
        if exportDirType == 'Default Locations':

            project_path = mc.workspace(q=True, rd=True)
            scene_path = mc.file(q=True, sn=True)

            if project_path != '' and scene_path != '':
                export_dir = '%sscenes/Camera_Layout' % (project_path)

                # pull out the filename from the scene_path
                head, file_name_ext = os.path.split(scene_path)
                file_name, file_ext = os.path.splitext(file_name_ext)

                # set file_name to RenderCam_Layout
                file_name += '_RenderCam_Layout'

                export_path = '%s/%s.%s' % (export_dir, file_name, ext)

                # create export directory if it doesn't exist
                if not os.path.exists(export_dir):
                    os.makedirs(export_dir)

        # have the user pick a file location because the default location couldn't be
        # found or because exportDirType == 'Choose Directories'
        if export_path == '':
            if exportDirType != 'Choose Directories':
                # we got here because the project wasn't set
                print 'Project was not set or the scene was not saved. Using export dialog.'
            export_path = mc.fileDialog2(
                fileFilter='%s (*.%s)' % (exportType, ext), dialogStyle=2, cap='Maya Locators Export')
            if export_path == None:
                return
            else:
                export_path = export_path[0]
            export_dir = os.path.split(export_path)[0]

        if DEBUG:
            print 'Export dir:  %s' % export_dir
            print 'Export path: %s' % export_path

        ####################################
        # Maya export
        ####################################
        if exportType == 'Maya ASCII':
            mc.select(cl=True)
            index = 0
            for objXform in objsXform:
                if index == 0:
                    mc.select(objXform)
                else:
                    mc.select(objXform, tgl=True)
                index = index + 1
            mc.file(export_path, force=True, options='v=0;',
                    type='mayaAscii', pr=True, es=True)

        elif exportType == 'Maya Binary':
            mc.select(cl=True)
            index = 0
            for objXform in objsXform:
                if index == 0:
                    mc.select(objXform)
                else:
                    mc.select(objXform, tgl=True)
                index = index + 1
            mc.file(export_path, force=True, options='v=0;',
                    type='mayaBinary', pr=True, es=True)

        elif exportType == 'Alembic':
            # load alem plug if needed
            if not mc.pluginInfo('AbcExport', q=True, loaded=True):
                mc.loadPlugin('AbcExport')

            # build the ABC export String
            exportCmd = ('AbcExport')
            export_obj_str = (' -root |%s' % layoutGrpName)
            exportCmd += (' -j "-frameRange %d %d ' % (startFrame, endFrame))
            exportCmd += ('-uvWrite -eulerFilter -step %f -worldSpace%s ' %
                          (stepSize, export_obj_str))
            exportCmd += ('-file \\"%s\\""' % export_path)

            # export
            states = disableCamerasAndImagePlanes()
            mel.eval(exportCmd)
            enableCamerasAndImagePlanes(states)

        elif exportType == 'FBX':
            # fbx exporter will choke on windows backslashes
            export_path = export_path.replace('\\', '/')

            states = disableCamerasAndImagePlanes()
            exportFBX.exportFBXLayout(objsXform, export_path)
            enableCamerasAndImagePlanes(states)

    def exportLayoutForNuke(self, startFrame, endFrame, stepSize, objsXform, layoutGrpName, exportType, exportDirType):
        """ Containts the different paths for different nuke export types (alembic,fbx,etc). """
        # nuke
        #     from_maya
        if DEBUG:
            print 'Exporting following objects for Nuke:'
            for objXform in objsXform:
                print objXform

        ####################################
        # Resolve path if needed
        ####################################
        exportTypes = []
        OBJandFBX = False
        if exportType == 'OBJ Geo / FBX Loc':
            exportTypes.append('OBJ')
            exportTypes.append('FBX')
            OBJandFBX = True
        else:
            exportTypes.append(exportType)
        for exportTypeNum in exportTypes:
            try:
                ext = self.export_ext_dict[exportTypeNum]
            except KeyError:
                raise Exception(
                    'Unknown export type specified for exportLayoutForNuke(): %s' % exportTypeNum)

            export_dir = ''
            export_path = ''
            if exportDirType == 'Default Locations':

                project_path = mc.workspace(q=True, rd=True)
                scene_path = mc.file(q=True, sn=True)

                if project_path != '' and scene_path != '':
                    nuke_dir = nukeDirFromMaya(project_path)
                    export_dir = os.path.join(nuke_dir, 'from_maya')

                    # pull out the filename from the scene_path
                    head, file_name_ext = os.path.split(scene_path)
                    file_name, file_ext = os.path.splitext(file_name_ext)

                    # set file_name to RenderCam_Layout
                    file_name += '_RenderCam_Layout'

                    export_path = os.path.join(
                        export_dir, '%s.%s' % (file_name, ext))

                    # create export directory if it doesn't exist
                    if not os.path.exists(export_dir):
                        os.makedirs(export_dir)

            # have the user pick a file location because the default location couldn't be
            # found or because exportDirType == 'Choose Directories'
            if export_path == '':
                if exportDirType != 'Choose Directories':
                    # we got here because the project wasn't set
                    print 'Project was not set or the scene was not saved. Using export dialog.'
                export_path = mc.fileDialog2(
                    fileFilter='%s (*.%s)' % (exportTypeNum, ext), dialogStyle=2, cap='Nuke Locators Export')
                if export_path == None:
                    return
                else:
                    export_path = export_path[0]
                export_dir = os.path.split(export_path)[0]

            if DEBUG:
                print 'Export dir:  %s' % export_dir
                print 'Export path: %s' % export_path

            ####################################
            # Nuke export
            ####################################
            if exportTypeNum == 'Alembic':
                # Will export both locators and geometry from the layout group

                # load alem plug if needed
                if not mc.pluginInfo('AbcExport', q=True, loaded=True):
                    mc.loadPlugin('AbcExport')

                # fbx exporter will choke on windows backslashes
                export_path = export_path.replace('\\', '/')

                # build the ABC export String
                exportCmd = ('AbcExport')
                export_obj_str = (' -root |%s' % layoutGrpName)
                exportCmd += (' -j "-frameRange %d %d ' %
                              (startFrame, endFrame))
                exportCmd += ('-uvWrite -eulerFilter -step %f -worldSpace%s ' %
                              (stepSize, export_obj_str))
                exportCmd += ('-file \\"%s\\""' % export_path)

                # export
                states = disableCamerasAndImagePlanes()
                mel.eval(exportCmd)
                enableCamerasAndImagePlanes(states)

            elif exportTypeNum == 'FBX':

                # fbx exporter will choke on windows backslashes
                export_path = export_path.replace('\\', '/')

                states = disableCamerasAndImagePlanes()

                if OBJandFBX == False:
                    exportFBX.exportFBXLayout(objsXform, export_path)
                else:
                    # Just handle the locators
                    locsXform = []
                    for objXform in objsXform:
                        tempShape = mc.listRelatives(
                            objXform, s=True, pa=True)[0]
                        if mc.nodeType(tempShape) == 'locator':
                            locsXform.append(objXform)
                    exportFBX.exportFBXLayout(locsXform, export_path)

                enableCamerasAndImagePlanes(states)

            elif exportTypeNum == 'Nuke Script':
                export_dir = str(export_dir) + '/'
                states = disableCamerasAndImagePlanes()
                exportNuke.exportObjects2Nuke(
                    objsXform, export_path, startFrame, endFrame, 1)
                enableCamerasAndImagePlanes(states)

            elif exportTypeNum == 'OBJ':
                # Assume just handling geometry (NOT locators)
                geoXform = []
                for objXform in objsXform:
                    tempShape = mc.listRelatives(objXform, s=True, pa=True)[0]
                    if mc.nodeType(tempShape) != 'locator':
                        geoXform.append(objXform)

                # load obj plug if needed
                if not mc.pluginInfo('objExport', q=True, loaded=True):
                    mc.loadPlugin('objExport')

                mc.select(cl=True)
                index = 0
                if len(geoXform) > 0:
                    for gXform in geoXform:
                        if index == 0:
                            mc.select(gXform)
                        else:
                            mc.select(gXform, tgl=True)
                        index = index + 1
                    mc.file(export_path, type="OBJexport", pr=True, es=True)
                else:
                    mc.warning("No geometry to export!")

    def exportLayoutForHoudini(self, startFrame, endFrame, stepSize, objsXform, layoutGrpName, exportType, exportDirType):
        """ Containts the different paths for different houdini export types (alembic,fbx,etc). """
        # houdini
        #     scenes
        #         Camera_Layout
        #             Publish
        if DEBUG:
            print 'Exporting the following locators for Houdini.'
            for objXform in objsXform:
                print objXform

        ####################################
        # Resolve path if needed
        ####################################
        try:
            ext = self.export_ext_dict[exportType]
        except KeyError:
            raise Exception(
                'Unknown export type specified for exportLayoutForHoudini(): %s' % exportType)

        export_dir = ''
        export_path = ''
        if exportDirType == 'Default Locations':

            project_path = mc.workspace(q=True, rd=True)
            scene_path = mc.file(q=True, sn=True)

            if project_path != '' and scene_path != '':
                hou_dir = houdiniDirFromMaya(project_path)
                export_dir = os.path.join(
                    hou_dir, 'scenes', 'from_maya')
                export_dir = os.path.normpath(export_dir)

                # pull out the filename from the scene_path
                head, file_name_ext = os.path.split(scene_path)
                file_name, file_ext = os.path.splitext(file_name_ext)

                # set file_name to RenderCam_Layout
                file_name += '_RenderCam_Layout'

                export_path = os.path.join(
                    export_dir, '%s.%s' % (file_name, ext))

                # create export directory if it doesn't exist
                if not os.path.exists(export_dir):
                    os.makedirs(export_dir)

        # have the user pick a file location because the default location couldn't be
        # found or because exportDirType == 'Choose Directories'
        if export_path == '':
            if exportDirType != 'Choose Directories':
                # we got here because the project wasn't set
                print 'Project was not set or the scene was not saved. Using export dialog.'
            export_path = mc.fileDialog2(
                fileFilter='%s (*.%s)' % (exportType, ext), dialogStyle=2, cap='Houdini Locators Export')
            if export_path == None:
                return
            else:
                export_path = export_path[0]
            export_dir = os.path.split(export_path)[0]

        if DEBUG:
            print 'Export dir:  %s' % export_dir
            print 'Export path: %s' % export_path

        ####################################
        # Houdini export
        ####################################
        if exportType == 'Alembic':
            # load alem plug if needed
            if not mc.pluginInfo('AbcExport', q=True, loaded=True):
                mc.loadPlugin('AbcExport')

            # fbx exporter will choke on windows backslashes
            export_path = export_path.replace('\\', '/')

            # build the ABC export String
            exportCmd = ('AbcExport')
            export_obj_str = (' -root |%s' % layoutGrpName)
            exportCmd += (' -j "-frameRange %d %d ' % (startFrame, endFrame))
            exportCmd += ('-uvWrite -eulerFilter -step %f -worldSpace%s ' %
                          (stepSize, export_obj_str))
            exportCmd += ('-file \\"%s\\""' % export_path)

            # export
            states = disableCamerasAndImagePlanes()
            mel.eval(exportCmd)
            enableCamerasAndImagePlanes(states)

        elif exportType == 'FBX':
            states = disableCamerasAndImagePlanes()
            exportFBX.exportFBXLayout(objsXform, export_path)
            enableCamerasAndImagePlanes(states)

    # button cmd #
    def close(self, *args):
        """ Close button, here for completeness, not currently used. """
        mc.deleteUI(self.name)


def ui():
    """ Builds the ui, but does a version check for sanity. """

    if mel.eval('getApplicationVersionAsFloat()') < 2013:
        raise Exception('This script only runs in Maya 2013 and later.')

    ui = ConsistentCameraExportUI()

# debug in scriptEd:
# ui()
