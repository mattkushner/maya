# Exports cameras and locaters to a .nk file for Nuke.
# This is for cameras, not camera and aim, or camera, aim and up.

import os
import maya.cmds as mc
import maya.mel


def _getWorkDirFromPath(theFile):
    # Returns the path of a file's containing "work" folder.
    # theDir = theFile.rsplit('work', 1)[0] + 'work'
    theDir = theFile.split('_3D')[0]
    theDir = os.path.normpath(theDir)
    return theDir

def getCams(mode):
    # Searches for cameras and generates array of strings, one for each camera's transform node.
    # Three modes to choose from:
    # selected  Return all cameras in the current selection.
    # render  Return all render cameras in current layer.
    # auto  Return all cameras in the current selection, or if no cameras are selected then return all render cameras in current layer.

    cams = []

    if mode == "":
        mode = "auto"

    if mode == "selected" or mode == "auto":
        selection = mc.ls(sl=True, l=True)

        for each in selection:
            # Make sure that the object exists
            if mc.objExists(each):
                # Check for camera shape or transform node
                if mc.nodeType(each) == "transform":
                    temp = mc.listRelatives(each, c=True, f=True)
                    if mc.objExists(temp[0]):
                        if mc.nodeType(temp[0]) == "camera":
                            cams.append(each)
                elif mc.nodeType(each) == "camera":
                    temp = mc.listRelatives(each, p=True, f=True)
                    if mc.objExists(temp[0]):
                        cams.append(temp[0])
        # Clear the selection list
        del selection[:]

    if mode == "render" or mode == "auto":
        if len(cams) == 0:
            allCams = mc.ls(ca=True, l=True)
            for each in allCams:
                # Make sure object exists
                if mc.objExists(each):
                    if mc.getAttr(str(each) + ".renderable"):
                        temp = mc.listRelatives(each, p=True, f=True)
                        if mc.objExists(temp[0]):
                            cams.append(temp[0])
            # Clear the allCams list
            del allCams[:]

    return cams

def getTransforms(_type):
    # Searches the current selection for locators/transforms and generates array of strings, one for each transform node.
    # Two modes to choose from:
    # [type]  Return the transform parent nodes of nodeType == [type].
    # all  Returns all selected transforms.

    transforms = []
    selection = mc.ls(sl=True, l=True)

    for each in selection:
        # Make sure object exists
        if mc.objExists(each):
            # Check for shape or transform node
            if mc.nodeType(each) == "transform":
                if _type != "all":
                    temp = mc.listRelatives(each, c=True, f=True)
                    # Make sure object exists
                    if mc.objExists(temp[0]):
                        if mc.nodeType(temp[0]) == _type:
                            transforms.append(each)
                else:
                    transforms.append(each)

    del selection[:]
    return transforms

# exportObjects2Nuke
# Exports locators and cameras to Nuke, also exports any transforms as locators.
def exportObjects2Nuke(objects, outputPath, minFrame, maxFrame, auto_scale):
    # if world_bake == 1:
    #   objects = maya.mel.eval('string $objects[] = `lfx_worldBake ' + str(objs) + ' ' + str(minFrame) + ' ' + str(maxFrame) + ' 1`;')

    curWord = ""
    curData = 0.0
    frIndex = 0
    curTime = 0

    # Generate output file path based on scene name
    # scene = mc.file(q = True, exn = True)
    # base = maya.mel.eval('string $baseValue = `basenameEx "' + str(scene) + '"`;')
    # NKfile = str(outputDir) + str(base) + "_cams_locators.nk"

    NKfile = outputPath

    # Turn off cycle checking (spews out warning for things attached to paths)
    cycleCheckState = mc.cycleCheck(q=True, e=True)
    maya.mel.eval("cycleCheck -e off;")

    # Convert linear units to cm if auto_scale is set to 1.
    scale_multiplier = 1
    units = mc.currentUnit(q=True, l=True)

    if auto_scale == 1:
        if units == "mm":
            scale_multiplier = 0.1
        if units == "cm":
            scale_multiplier = 1
        if units == "m":
            scale_multiplier = 100
        if units == "km":
            scale_multiplier = 1000000
        if units == "in":
            scale_multiplier = 2.54
        if units == "ft":
            scale_multiplier = 30.48
        if units == "yd":
            scale_multiplier = 91.44
        if units == "mi":
            scale_multiplier = 160934.4

    # Open The File
    eiFileID = open(NKfile, 'w')

    if eiFileID == 0:
        print "Could not create file: " + NKfile + "\n"
        return 0

    print "Writing to: "
    # Write out objects
    for each in objects:
        maya_object_type = ""
        nuke_object_type = ""

        temp = mc.listRelatives(each, c=True, f=True)
        if len(temp) > 0:
            if mc.objExists(temp[0]):
                maya_object_type = mc.nodeType(temp[0])
            else:
                maya_object_type = mc.nodeType(each)

        if maya_object_type == "camera":
            nuke_object_type = "Camera"
        else:
            nuke_object_type = "Axis2"

        curWord = str(each) + ".rotateOrder"
        mayaRotOrder = mc.getAttr(curWord)

        rotOrder = ""
        xTran = ""
        yTran = ""
        zTran = ""
        xRot = ""
        yRot = ""
        zRot = ""

        if mayaRotOrder == 0:
            rotOrder = "XYZ"
        if mayaRotOrder == 1:
            rotOrder = "YZX"
        if mayaRotOrder == 2:
            rotOrder = "ZXY"
        if mayaRotOrder == 3:
            rotOrder = "XZY"
        if mayaRotOrder == 4:
            rotOrder = "YXZ"
        if mayaRotOrder == 5:
            rotOrder = "ZYX"

        # Write header
        eiFileID.write("push 0\n")
        eiFileID.write(str(nuke_object_type) + " {\n")
        eiFileID.write(" selected false\n")
        eiFileID.write(" rot_order " + str(rotOrder) + "\n")

        # Get the data for each frame and write it out.

        # Write TransX Data
        eiFileID.write(" translate {{curve x" + str(minFrame))

        frIndex = minFrame
        while frIndex <= maxFrame:
            curTime = frIndex
            curWord = str(each) + ".translateX"
            xTran = mc.getAttr(curWord, t=curTime) * scale_multiplier

            eiFileID.write(" " + str(xTran))
            frIndex = frIndex + 1

        # Write TransY Data
        eiFileID.write("} {curve x" + str(minFrame))

        frIndex = minFrame
        while frIndex <= maxFrame:
            curTime = frIndex
            curWord = str(each) + ".translateY"
            yTran = mc.getAttr(curWord, t=curTime) * scale_multiplier

            eiFileID.write(" " + str(yTran))
            frIndex = frIndex + 1

        # Write TransZ Data
        eiFileID.write("} {curve x" + str(minFrame))

        frIndex = minFrame
        while frIndex <= maxFrame:
            curTime = frIndex
            curWord = str(each) + ".translateZ"
            zTran = mc.getAttr(curWord, t=curTime) * scale_multiplier

            eiFileID.write(" " + str(zTran))
            frIndex = frIndex + 1


        eiFileID.write("}}\n")

        # Write rotX Data
        eiFileID.write(" rotate {{curve x" + str(minFrame))

        frIndex = minFrame
        while frIndex <= maxFrame:
            curTime = frIndex
            curWord = str(each) + ".rotateX"
            xRot = mc.getAttr(curWord, t=curTime)

            eiFileID.write(" " + str(xRot))
            frIndex = frIndex + 1

        # Write rotY Data
        eiFileID.write("} {curve x" + str(minFrame))

        frIndex = minFrame
        while frIndex <= maxFrame:
            curTime = frIndex
            curWord = str(each) + ".rotateY"
            yRot = mc.getAttr(curWord, t=curTime)

            eiFileID.write(" " + str(yRot))
            frIndex = frIndex + 1

        # Write rotZ Data
        eiFileID.write("} {curve x" + str(minFrame))

        frIndex = minFrame
        while frIndex <= maxFrame:
            curTime = frIndex
            curWord = str(each) + ".rotateZ"
            zRot = mc.getAttr(curWord, t=curTime)

            eiFileID.write(" " + str(zRot))
            frIndex = frIndex + 1

        eiFileID.write("}}\n")

        # Write scaleX Data
        eiFileID.write(" scaling {{curve x" + str(minFrame))

        frIndex = minFrame
        while frIndex <= maxFrame:
            curTime = frIndex
            curWord = str(each) + ".scaleX"
            xScale = mc.getAttr(curWord, t=curTime)

            eiFileID.write(" " + str(xScale))
            frIndex = frIndex + 1

        # Write scaleY Data
        eiFileID.write("} {curve x" + str(minFrame))

        frIndex = minFrame
        while frIndex <= maxFrame:
            curTime = frIndex
            curWord = str(each) + ".scaleY"
            yScale = mc.getAttr(curWord, t=curTime)

            eiFileID.write(" " + str(yScale))
            frIndex = frIndex + 1

        # Write scaleZ Data
        eiFileID.write("} {curve x" + str(minFrame))

        frIndex = minFrame
        while frIndex <= maxFrame:
            curTime = frIndex
            curWord = str(each) + ".scaleZ"
            zScale = mc.getAttr(curWord, t=curTime)

            eiFileID.write(" " + str(zScale))
            frIndex = frIndex + 1


        eiFileID.write("}}\n")


        # Write data for cameras
        if nuke_object_type == "Camera":
            # Focal length
            eiFileID.write(" focal {{curve x" + str(minFrame))
            frIndex = minFrame
            while frIndex <= maxFrame:
                curTime = frIndex
                curWord = str(each) + ".focalLength"
                focal = mc.getAttr(curWord, t=curTime)

                eiFileID.write(" " + str(focal))
                frIndex = frIndex + 1

            eiFileID.write("}}\n")

            # Write out Apertures, etc.
            curWord = str(each) + ".horizontalFilmAperture"
            hMayaApert = mc.getAttr(curWord)
            hApert = hMayaApert * 25.4

            curWord = str(each) + ".verticalFilmAperture"
            vMayaApert = mc.getAttr(curWord)
            vApert = vMayaApert * 25.4

            curWord = str(each) + ".nearClipPlane"
            nearClipPlane = mc.getAttr(curWord)
            curWord = str(each) + ".farClipPlane"
            farClipPlane = mc.getAttr(curWord)

            eiFileID.write(" haperture " + str(hApert) + "\n")
            eiFileID.write(" vaperture " + str(vApert) + "\n")
            eiFileID.write(" near " + str(nearClipPlane) + "\n")
            eiFileID.write(" far " + str(farClipPlane) + "\n")
            eiFileID.write(" win_scale {1 1}\n")


        # Write name and label
        short_name = maya.mel.eval('string $name = `shortNameOf("' + str(each) + '")`;')

        eiFileID.write(" name " + str(short_name) + "\n")
        # eiFileID.write(" label " + str(base) + "\n")
        eiFileID.write("}\n")

    eiFileID.close()

    # Put cycleCheck back how it was.
    print str(NKfile)
    return NKfile

def exportCam2Nuke(cam, outputPath, minFrame, maxFrame, auto_scale):
    objects = []
    objects.append(cam)
    exportObjects2Nuke(objects, outputPath, minFrame, maxFrame, auto_scale)

def lfx_exportNukeCombo():
    minFrame = mc.playbackOptions(query=True, min=True)
    maxFrame = mc.playbackOptions(query=True, max=True)
    world_bake = 0

    scene = mc.file(q=True, exn=True)
    folder = _getWorkDirFromPath(str(scene) + "/_2D/nuke/from_maya/")
    if os.path.exists(folder) == 0:
        os.makedirs(folder)

    cams = getCams("selected")
    locators = getTransforms("locator")
    objects = mc.stringArrayCatenate(cams, locators)

    exportObjects2Nuke(objects, folder, minFrame, maxFrame, 1, world_bake)

# for testing in scriptEd
# selected = mc.ls(sl = True)
# exportObjects2Nuke(selected, 'C:/Users/lookadmin/Desktop/work/nuke', 1, 363, 1)
