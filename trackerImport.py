#
# d = sensor dimension. 36mm for typical horzontal as an example.
# f = the effective focal length (f = F * (1+m) where m = magnification)
#
#               d
# a = 2 atan[ ----- ]
#              2*f
#
# camera aperature (film gate) should match the aspect of the
# plate. lens squeeze ratio should be 1.0. Nothing fancy is
# currently supported.

# Todo: wrong type - for example, loading syntheyes when set to nuke
#

import math
import os
import re
import maya
import maya.OpenMaya as om
import maya.api.OpenMaya as api
import maya.cmds as mc
import ConsistentCameraExport

UV_SET_NAME = 'tempUVForTrackerProjection'
TEMP_UV_GEO_NAME = 'temp_uv_geo'

DEFAULTS = {
    'z': 10,
    'offsetX': 0,
    'offsetY': 0,
    'frameOffset': 0,
    'displayScale': 0.2,
    'prefix': '',
    'createJoints': True,
    'animated': True,
    'projected': True,
    'targetMesh': '',
    'stickToLastHit': True,
    'inheritNormal': True,
    'stickMode': 2
}


def fnMeshFromName( transformNameOrShapeName ):
    # create an instance of MSelectionList and add to the list the mesh
    sel = api.MSelectionList()
    sel.add( transformNameOrShapeName )

    # MDagPath provides methods for obtaining one or all Paths to a specified DAG Node.
    # next, get the dag path of the given element of
    # the selection list. index is 0 being the last item added
    dagPathToMesh = sel.getDagPath( 0 )

    # make sure we have the shape for raycasting
    dagPathToMesh.extendToShape()

    # create a mesh function set using the MDagPath pointing to the shape node of mesh
    # MFnMesh contains the method closestIntersection which will intersect a ray with mesh
    # geometry optionally using an excelleration structure (an octree)
    fnMesh = api.MFnMesh( dagPathToMesh )

    return fnMesh



def closestRayIntersect( fnMesh, accelParams, point, direction, stickToLastHit=False ):
    """
        Returns a tuple with the bool hit value and the coords (tuple float) along with
        the hitFace, hitTriangle, hitBary1, hitBary2 which will be used to later to find
        the new position of the surface where it was hit:
        (True, (x,y,z), (hitFace, hitTriangle, hitBary1, hitBary2) )
    """

    # [in] parameters
    raySource    = api.MFloatPoint( point[0], point[1], point[2], 1.0 )
    rayDirection = api.MFloatVector( direction[0], direction[1], direction[2] )
    space        = api.MSpace.kWorld # specifies the space in which raySource and rayDirection are specified
    maxParam     = 999999           # specifies the maximum radius within which hits will be considered
    testBothDirections = False      # specifies that hits in the negative rayDirection should also be considered
    tolerance    = 0.0001           # numerical tolerance- it is wise to allow the routine to consider hits that lie a tiny bit outside mesh triangles

    # ray intersection test
    hit = fnMesh.closestIntersection(raySource,
                                     rayDirection,
                                     space,
                                     maxParam,
                                     testBothDirections,
                                     accelParams=accelParams,
                                     tolerance=tolerance)

    # if hit != None:
    # I am now comparing with not just the hit return value whether it's None or not
    # but I also make sure the hit position is not 0,0,0. For some reason sometimes it tells you
    # it got a valid hit even if it didn't and the hit location is 0,0,0
    if (hit and not (hit[0][0] == 0.0 and hit[0][1] == 0.0 and hit[0][2] == 0.0)):
        tracePoint = (hit[0].x, hit[0].y, hit[0].z)

        if stickToLastHit:
            try:
                hitInfo = fnMesh.getUVAtPoint(api.MPoint(tracePoint), space, uvSet='tempUVForTrackerProjection')
            except RuntimeError as e:
                if 'kInvalidParameter' in str(e):
                    mc.warning('Cannot find a nearest uv at world coordinates: %s %s %s on mesh %s' % (hit[0].x, hit[0].y, hit[0].z, fnMesh.fullPathName()))
                else:
                    raise e
        else:
            hitInfo = (0,0,0,0)
        return (True, tracePoint, hitInfo)
    else:
        #print "Ray missed."
        return (False, (0,0,0), (0,0,0,0) )


def radToDeg( x ):
    return ( x * 57.2957795131 ) # 180/pi


def degToRad( x ):
    return ( x * 0.01745329251 ) # pi/180


def asOMQuat( angle, axis ):
    return api.MQuaternion( axis.x * math.sin(angle/2),
                           axis.y * math.sin(angle/2),
                           axis.z * math.sin(angle/2),
                           math.cos(angle/2) )


def asOMVec( x ):
    """ returns a tuple of floats as an OpenMaya vector """
    return api.MVector( x[0], x[1], x[2] )


def asTVec( x ):
    """ returns OpenMaya vector as tuple of floats """
    return ( x[0], x[1], x[2] )


def loadPFTrackAscii2D( path, plateResX, plateResY, frameOffset ):
    """
        Comments start with hash, format is:
        # "Name"
        # clipNumber
        # frameCount
        # frame, xpos, ypos, similarity
        # blank line
    """
    with open( path, 'r' ) as f:
        rawData = f.readlines()

    trackingData = []
    markerCount = 0
    currentMarker = ''

    i = 0
    while i < len(rawData):

        line = rawData[i]

        # skip empty lines and comment lines
        if ((line.strip() != '') and (line[0] != '#')):

            words = re.split( r'\s+', line )

            # test to see if we've advanced to a new marker
            # which in this case starts with a quote
            if ( words[0][0] == '"' ):
                currentMarker = words[0].strip('"')
                markerCount += 1
                trackingData.append( [currentMarker,[]] )
                i += 3 # skip the clipnumber and frame count
                continue

            # add this frame to the current marker
            trackingData[markerCount-1][1].append(
                (int(words[0])+frameOffset,
                (((float(words[1])/float(plateResX)) * 2.0) - 1.0),
                ((((float(words[2])/float(plateResY)) * 2.0) - 1.0) * -1.0) ) )

        # next line
        i += 1

    return trackingData


def loadNukeASCII2D( path, plateResX, plateResY, frameOffset ):
    """
        Format of a line of tracker data (line#, starting at 1, is frame):
            xPixelFloat yPixelFloat
    """
    with open( path, 'r' ) as f:
        rawData = f.readlines()

    trackingData = []

    # only one tracker per file
    markerCount = 1
    trackingData.append( ['NukeTracker#',[]] )

    frame = 1
    for line in rawData:
        # skip empty lines and comment lines
        if ((line.strip() == '') or (line[0] == '#')):
            continue
        words = re.split( r'\s+', line )

        # only one tracker per file, hard coded as [0][1]
        # we convert from pixel values to center UV in the
        # range of -1 to 1
        trackingData[0][1].append( ( frame, (((float(words[0])/float(plateResX)) * 2.0) - 1.0), (((float(words[1])/float(plateResY)) * 2.0) - 1.0) * -1.0 ) )
        frame += 1

    return trackingData


def loadSyntheyes2DTrackerPaths( path, offsetX, offsetY, frameOffset ):
    """
        Format of a line of tracker data:
            trackerName frameInt uValue vValue quality
        Default syntheyes data is centered, so u(x) values should be
        between -1 and 1. Likewise for v(y).
    """
    if not os.path.isfile(path):
        raise IOError('The following tracking file is invalid: {}'.format(path))

    with open( path, 'r' ) as f:
        rawData = f.readlines()

    trackingData = []
    markerCount = 0
    currentMarker = ''

    for line in rawData:
        # skip empty lines and comment lines
        if ((line.strip() == '') or (line[0] == '#')):
            continue
        words = re.split( r'\s+', line )

        # test to see if we've advanced to a new marker
        # words[0] = tracker name
        if ( words[0] != currentMarker ):
            currentMarker = words[0]
            markerCount += 1
            trackingData.append( [currentMarker,[]] )

        # words[1 to 3] = frame, xpos, ypos
        trackingData[markerCount-1][1].append(
            (int(words[1])+frameOffset,
             float(words[2])-offsetX,
             float(words[3])-offsetY) )

    return trackingData

def load3deTrackerPaths( path, plateResX, plateResY, offsetX, offsetY, frameOffset ):
    """
        Format of a line of tracker data:
            frameInt uValue vValue
        3d data is in pixel space, so the uValues(x)
        would be between 0 and 1920 for an HD plate. Our internal format is expected
        to be from -1 to 1 so we have convert to this ratio based on the plate resolution.
        The Y value is inverted so we have to to 1-Y after normalizing but before the -1 to 1 range.
    """
    if not os.path.isfile(path):
        raise IOError('The following tracking file is invalid: {}'.format(path))

    with open( path, 'r' ) as f:
        rawData = f.readlines()

    nbrTrackers = rawData[0].strip()
    try:
        nbrTrackers = int(nbrTrackers)
        rawData = rawData[1:] # remove the number of tracker line
    except ValueError:
        raise ValueError('The first line of the tracker file must be an integer representing the number of trackers.')

    trackingData = []
    # Loop through all trackers
    for t in range(nbrTrackers):
        trackerName = rawData[0].strip()
        if trackerName[0].isdigit(): # Maya does not support a numeric as a first character
            trackerName = '_{}'.format(trackerName)
        rawData = rawData[2:] # remove the tracker name and the next line
        nbrFrames = int(rawData[0].strip()) # extract the number of frames
        rawData = rawData[1:] # remove the number of frames
        if nbrFrames > 0:
            framesData = []
            for f in range(nbrFrames):
                lineData = rawData[0].strip().split(' ')
                frameNumber = float(lineData[0]) + frameOffset
                x = ((float(lineData[1]) / float(plateResX)) * 2.0) - 1.0 - offsetX
                y = ((1.0 - (float(lineData[2]) / float(plateResY))) * 2.0) - 1.0 - offsetY
                # Add the data to the list
                framesData.append((frameNumber, x, y))
                rawData = rawData[1:]
            trackingData.append([trackerName, framesData])

    return trackingData


def loadBoujouTracksFile( path, plateResX, plateResY, offsetX, offsetY, frameOffset ):
    """
        Format:
            # comments start with hash
            trackerName frameInt uValue vValue
        Default boujou data is in pixel space, so the uValues(x)
        would be between 0 and 1920 for an HD plate. Synthese would
        store this as a u value between -1 and 1 by default. Boujou
        can be setup of output centered data to match syntheyes.
    """
    with open( path, 'r' ) as f:
        rawData = f.readlines()

    trackingData = []
    markerCount = 0
    currentMarker = ''

    for line in rawData:
        # skip empty lines and comment lines
        if ((line.strip() == '') or (line[0] == '#')):
            continue
        words = re.split( r'\s+', line )

        # test to see if we've advanced to a new marker
        # words[0] = tracker name
        if ( words[0] != currentMarker ):
            currentMarker = words[0]
            markerCount += 1
            trackingData.append( [currentMarker,[]] )

        # words[1 to 3] = frame, xpos, ypos
        # trackingData[markerCount-1][1].append(
        #     (int(words[1])+frameOffset,
        #      float(words[2])-offsetX,
        #      float(words[3])-offsetY) )
        trackingData[markerCount-1][1].append(
            (int(words[1])+frameOffset,
             (((float(words[2])/float(plateResX)) * 2.0) - 1.0),
             (((float(words[3])/float(plateResY)) * 2.0) - 1.0) ) )
        #((float(words[0])/plateResX) * 2.0) - 1.0

    return trackingData

def createSingleLocator(tracker,
                        cameraShape,
                        locatorDisplayScale,
                        createJoints):

    print( 'Creating tracker: %s' % tracker[0] )
    loc = mc.spaceLocator( a=True, p=(0,0,0), n=tracker[0] )[0]
    # Maya will rename the created node in case of conflict with existing name
    # Set the name back into our data structure to stay consistent
    # We need to add the root unique identifier | to avoid
    #conflict with existing locators with the same name in other groups
    loc = '|%s' % loc
    tracker[0] = loc
    # Adjust the locator display scale
    locShape = mc.listRelatives( loc, s=True, pa=True )[0]
    mc.setAttr( ('%s.localScaleX' % locShape), locatorDisplayScale )
    mc.setAttr( ('%s.localScaleY' % locShape), locatorDisplayScale )
    mc.setAttr( ('%s.localScaleZ' % locShape), locatorDisplayScale )
    # Adjust the locator color
    mc.setAttr('%s.overrideEnabled' % locShape, 1)
    mc.setAttr('%s.overrideRGBColors' % locShape, 1)
    mc.setAttr('%s.overrideColorR' % locShape, 0.55)
    mc.setAttr('%s.overrideColorG' % locShape, 0.15)
    mc.setAttr('%s.overrideColorB' % locShape, 0.05)

    # Add the original translate attribute
    mc.addAttr(loc, shortName='origt', longName='originalTranslate', attributeType='double3', keyable=True)
    mc.addAttr(loc, shortName='origtx', longName='originalTranslateX', attributeType='double', parent='originalTranslate', keyable=True)
    mc.addAttr(loc, shortName='origty', longName='originalTranslateY', attributeType='double', parent='originalTranslate', keyable=True)
    mc.addAttr(loc, shortName='origtz', longName='originalTranslateZ', attributeType='double', parent='originalTranslate', keyable=True)
    # Add the offset attribute
    mc.addAttr(loc, shortName='of', longName='offset', attributeType='double', keyable=True)
    # Create the expression node and make the connections.
    exp = mc.createNode('expression', name='%s_exp' % loc)
    #mc.connectAttr('%s.output[0]' % exp, '%s.translateX' % loc, force=True)
    exp_string = '$cam = `firstParentOf %s`;\n' % cameraShape
    exp_string += '$cam_pos = `xform -query -translation -worldSpace $cam`;\n'
    exp_string += '$loc_pos[0] = %s.origtx;\n' % loc
    exp_string += '$loc_pos[1] = %s.origty;\n' % loc
    exp_string += '$loc_pos[2] = %s.origtz;\n' % loc
    exp_string += '$offset = %s.offset;\n' % loc
    exp_string += '$dir[0] = $cam_pos[0] - $loc_pos[0];\n'
    exp_string += '$dir[1] = $cam_pos[1] - $loc_pos[1];\n'
    exp_string += '$dir[2] = $cam_pos[2] - $loc_pos[2];\n'
    exp_string += 'normalize($dir);\n'
    exp_string += '$dir[0] = $dir[0] * -$offset;\n'
    exp_string += '$dir[1] = $dir[1] * -$offset;\n'
    exp_string += '$dir[2] = $dir[2] * -$offset;\n'
    exp_string += '%s.translateX = $loc_pos[0] + $dir[0];\n' % loc
    exp_string += '%s.translateY = $loc_pos[1] + $dir[1];\n' % loc
    exp_string += '%s.translateZ = $loc_pos[2] + $dir[2];\n' % loc
    mc.setAttr('%s.expression' % exp, exp_string, type='string')

    # Create a child offset locator
    locOffset = mc.spaceLocator( a=True, p=(0,0,0), n=('%s_offset' % tracker[0]) )[0]
    locOffset = '|%s' % locOffset
    mc.parent( locOffset, loc, relative=True )
    locOffset = '%s%s' % ( loc, locOffset ) # The pipe character that separates the two is already included in the locOffset name
    # Adjust the locator display scale
    locOffsetShape = mc.listRelatives( locOffset, s=True, pa=True )[0]
    mc.setAttr( ('%s.localScaleX' % locOffsetShape), locatorDisplayScale )
    mc.setAttr( ('%s.localScaleY' % locOffsetShape), locatorDisplayScale )
    mc.setAttr( ('%s.localScaleZ' % locOffsetShape), locatorDisplayScale )
    # Adjust the locator color
    mc.setAttr('%s.overrideEnabled' % locOffsetShape, 1)
    mc.setAttr('%s.overrideRGBColors' % locOffsetShape, 1)
    mc.setAttr('%s.overrideColorR' % locOffsetShape, 0.3)
    mc.setAttr('%s.overrideColorG' % locOffsetShape, 0.1)
    mc.setAttr('%s.overrideColorB' % locOffsetShape, 0.8)

    # Create a joint associated with the offset locator
    if createJoints:
        mc.select( clear=True )
        joint_name = loc.replace( 'Tracker', 'Joint')
        joint = mc.joint( p=(0,0,0), n=joint_name )
        mc.parentConstraint( locOffset, joint )
        mc.setAttr( '%s.radius' % joint, locatorDisplayScale * 0.5)
    else:
        joint = None

    return loc, joint

def createLocators( trackingData,
                    xmin,
                    xmax,
                    ymin,
                    ymax,
                    zmax,
                    worldMMatrix,
                    cameraShape,
                    camPosMVector,
                    locatorDisplayScale,
                    createJoints ):
    xExtent = abs( xmax - xmin ) * 0.5
    yExtent = abs( ymax - ymin ) * 0.5
    xCenter = ( xmax + xmin ) * 0.5 # average of max and min
    yCenter = ( ymax + ymin ) * 0.5 # average of max and min

    result_trackers = [ ]
    result_joints = [ ]
    for tracker in trackingData:
        loc, joint = createSingleLocator( tracker, cameraShape, locatorDisplayScale, createJoints )
        result_trackers.append( loc )
        if createJoints:
            result_joints.append( joint )
        for frameData in tracker[1]:
            fnum = frameData[0]
            u = frameData[1]
            v = frameData[2]

            x = ( u * xExtent ) + xCenter
            y = ( v * -yExtent ) + yCenter

            z = -zmax
            locPosMVector = asOMVec( (x, y, z) )
            locPos = asTVec( (locPosMVector * worldMMatrix) + camPosMVector )
            # set key on current locator for this frame
            mc.setKeyframe( ('%s.originalTranslateX' % loc), t=fnum, v=locPos[0],  )
            mc.setKeyframe( ('%s.originalTranslateY' % loc), t=fnum, v=locPos[1] )
            mc.setKeyframe( ('%s.originalTranslateZ' % loc), t=fnum, v=locPos[2] )

    return result_trackers, result_joints

# def getCameraMatrix(cameraName):
#     # Get view matrix.
#     import maya.OpenMaya as OpenMaya
#     import maya.OpenMayaUI as OpenMayaUI
#
#     view = OpenMayaUI.M3dView.active3dView()
#     mayaProjMatrix = OpenMaya.MMatrix()
#     view.projectionMatrix(mayaProjMatrix)
#     print mayaProjMatrix
#     return mayaProjMatrix

# def printMatrix(matrix):
#     result = ''
#     for i in range(4):
#         for j in range(4):
#             result = result + str(matrix.getElement(i, j)) + ', '
#     print result

    # result = '% .06f, % .06f, % .06f, % .06f,\n% .06f, % .06f, % .06f, % .06f,\n% .06f, % .06f, % .06f, % .06f,\n% .06f, % .06f, % .06f, % .06f,\n'
    # print result % (matrix(0, 0), matrix(0, 1), matrix(0, 2), matrix(0, 3), matrix(1, 0), matrix(1, 1), matrix(1, 2), matrix(1, 3), matrix(2, 0), matrix(2, 1), matrix(2, 2 ), matrix(2, 3), matrix(3, 0), matrix(3, 1), matrix(3, 2), matrix(3, 3))

# def getCameraMatrix(camera):
#
#     sel = api.MSelectionList()
#     sel = api.MSelectionList()
#     sel.add(camera)
#     dag = sel.getDagPath(0)
#     cam = api.MFnCamera(dag)
#     floatMat = cam.projectionMatrix()
#     projMat = api.MMatrix(floatMat)
#     transMat = dag.inclusiveMatrix()
#     floatMat = cam.postProjectionMatrix()
#     postProjMat = api.MMatrix(floatMat)
#
#
#     return transMat.inverse() * projMat, postProjMat

# def createTorusLocators():
#
#     null = mc.group(empty=True)
#     for i in range(100):
#         pos = mc.pointPosition( 'pTorus1.vtx[{}]'.format(int(i)), world=True )
#         loc = mc.spaceLocator()[0]
#         mc.setAttr('{}.tx'.format(loc), pos[0])
#         mc.setAttr('{}.ty'.format(loc), pos[1])
#         mc.setAttr('{}.tz'.format(loc), pos[2])
#         locShape = mc.listRelatives(loc, shapes=True)[0]
#         mc.setAttr('{}.localScaleX'.format(locShape), 0.1)
#         mc.setAttr('{}.localScaleY'.format(locShape), 0.1)
#         mc.setAttr('{}.localScaleZ'.format(locShape), 0.1)
#         #locators.append(loc[0])
#         projPos = api.MPoint(pos[0], pos[1], pos[2], 1)
#         #projPos = projPos * transMat.inverse() * projMat # * transMat
#         camProjMat, camPostProjMat = getCameraMatrix('camera1')
#         camPos = mc.xform('camera1',q=1,ws=1,translation=1)
#         camPos = api.MPoint(camPos[0], camPos[1], camPos[2])
#
#
#         projDirMVector = projPos - camPos
#         vecLen = projDirMVector.length()
#         projDirMVector.normalize()
#         projPos = camPos + (projDirMVector  * vecLen*2)
#
#
#         mc.setKeyframe( '{}.tx'.format(loc), v=projPos[0]  )
#         mc.setKeyframe( '{}.ty'.format(loc), v=projPos[1]  )
#         mc.setKeyframe( '{}.tz'.format(loc), v=projPos[2]  )
#         # mc.setKeyframe( '{}.originalTranslateZ'.format(loc), t=f, v=projPos[2]  )
#         loc = mc.parent( loc, null, relative=True )


def createLocatorsAnimProjectCam( trackingData,
                                  zmax,
                                  cameraShape,
                                  locatorDisplayScale,
                                  createJoints,
                                  targetMesh=None,
                                  stickToLastHit=False,
                                  inheritNormal=False,
                                  stickMode=1 ): # 1 = Z stays at the last hit but the rest follows the 2D track, 2 = Stick to the geometry last hit

    # projection setup - currently rebuilt per frame bellow
    # build fnMesh and octree to pass to the closestRayIntersect
    # function - by only building it once, we save much time
    #fnMesh = fnMeshFromName( targetMesh )
    #accelParams = fnMesh.autoUniformGridParams() # octree acceleration structure


    # gather frame start, end and current for iterating the timeline
    timeOrig  = int( mc.currentTime( q=True ) + 0.5 )
    timeStart = int( mc.playbackOptions( q=True, minTime=True ) + 0.5 )
    timeEnd   = int( mc.playbackOptions( q=True, maxTime=True ) + 0.5 )

    # TODO
    # create all trackers at origin
    # ready for keying

    result_trackers = [ ]
    result_joints = [ ]
    previousUvHits = {} # Stores the hit info from the ray tracing.
    for tracker in trackingData:
        loc, joint = createSingleLocator( tracker, cameraShape, locatorDisplayScale, createJoints )
        result_trackers.append( loc )
        result_joints.append( joint )
        previousUvHits[ tracker[0] ] = None

    # step through time
    forwardRange = range( timeStart, timeEnd+1 )
    reverseRange = list(forwardRange)[:-1]
    reverseRange.reverse()
    forwardRange.extend(reverseRange)
    for f in forwardRange:
        # set frame
        print 'Tracking Frame: {}'.format(f)
        mc.currentTime( f, edit=True )
        # projection setup - rebuild every frame
        # build fnMesh and octree to pass to the closestRayIntersect
        # function - by only building it once, we save much time
        if targetMesh:
            fnMesh = fnMeshFromName( targetMesh )
            accelParams = fnMesh.autoUniformGridParams() # octree acceleration structure

        # query the camera attributes
        focalLength = mc.camera( cameraShape, q=True, fl=True )
        lensSqueezeRatio = mc.camera( cameraShape, q=True, lsr=True )
        horizontalFilmAperture = mc.camera( cameraShape, q=True, hfa=True ) * 25.4
        verticalFilmAperture = mc.camera( cameraShape, q=True, vfa=True ) * 25.4
        nearClippingPlane = mc.camera( cameraShape, q=True, ncp=True )
        farClippingPlane = mc.camera( cameraShape, q=True, fcp=True )
        worldPosition = mc.camera( cameraShape, q=True, p=True )
        worldCenterOfInterest = mc.camera( cameraShape, q=True, wci=True )

        # calculate FOV along both horizontal and vertical directions
        horizontalFOV = 2 * math.atan( horizontalFilmAperture / (2 * focalLength) )
        verticalFOV = 2 * math.atan( verticalFilmAperture / (2 * focalLength) )

        # create the x,y points of the plane with normal -z for
        # a camera at the origin. we then transform those points
        # with the camera's transform matrix
        xmax = zmax * math.tan( horizontalFOV /  2 )
        xmin = zmax * math.tan( horizontalFOV / -2 )
        ymax = zmax * math.tan( verticalFOV   /  2 )
        ymin = zmax * math.tan( verticalFOV   / -2 )

        xExtent = abs( xmax - xmin ) * 0.5
        yExtent = abs( ymax - ymin ) * 0.5
        xCenter = ( xmax + xmin ) * 0.5 # average of max and min
        yCenter = ( ymax + ymin ) * 0.5 # average of max and min

        # grab the new camera world matrix at this frame
        worldMatrix = mc.getAttr( ('%s.worldMatrix' % cameraShape) )
        wm = api.MMatrix( worldMatrix)
        camPosMVector = api.MVector( wm[12], wm[13], wm[14] )

        # walk through the trackers
        # print 'Frame number is %s ' % f
        for tracker in trackingData:
            # Create a normal constraint with the mesh
            #tracker_name = '|%s' % tracker[0] # to avoid conflict with another node of the same name inside a group
            if targetMesh and inheritNormal:
                mc.normalConstraint( targetMesh, tracker[0], weight=1, aimVector=(0, 0, 1), upVector=(0, 0, 1), worldUpType='scene')

            # see if they have data at this frame
            hit = False
            locPos = None
            for frameData in tracker[1]:
                fnum = frameData[0]
                # trackers frame matches current frame
                if fnum == f:
                    hasData = True

                    u = frameData[1]
                    v = frameData[2]

                    x = ( u * xExtent ) + xCenter
                    y = ( v * -yExtent ) + yCenter

                    z = -zmax
                    locPosMVector = asOMVec( (x, y, z) )
                    locPosMVector = (locPosMVector * wm) + camPosMVector
                    locPos = asTVec( locPosMVector )

                    if targetMesh:
                        # build a world projection vector
                        projDirMVector = locPosMVector - camPosMVector
                        projDirMVector.normalize()
                        projDir = asTVec( projDirMVector )
                        camPos  = asTVec( camPosMVector )

                        # Project the 2d tracked position on the geometry
                        liveHit, liveHitPos, liveHitInfo = closestRayIntersect( fnMesh, accelParams, camPos, projDir, stickToLastHit )
                        if liveHit:
                            locPos = liveHitPos
                            if stickToLastHit:
                                previousUvHits[ tracker[0] ] = liveHitInfo
                            break

                # trackers frame is greather than current frame
                # assuming trackers are sorted, skip to next tracker
                elif fnum > f:
                    break

            if stickToLastHit:
                #if previousUvHits[ tracker[0] ] and locPos == None:
                if previousUvHits[ tracker[0] ] and not liveHit:
                    previousHit = previousUvHits[ tracker[0] ]
                    try:
                        previousPos = fnMesh.getPointAtUV(previousHit[2], previousHit[0], previousHit[1], api.MSpace.kWorld, UV_SET_NAME)
                    except RuntimeError as e:
                        mc.warning('Cannot find world position from uv coordinates: %s %s %s on mesh %s at frame %s' % (previousHit[2], previousHit[0], previousHit[1], fnMesh.fullPathName(), f))
                        raise e

                    if stickMode == 1: # Stick to closest depth found
                        previousPosMVector = api.MVector(previousPos[0], previousPos[1], previousPos[2])
                        projDirMVector = previousPosMVector - camPosMVector
                        vecLen = projDirMVector.length()

                        projDirMVector = locPosMVector - camPosMVector
                        if locPos:
                            locPosMVector = api.MVector(locPos[0], locPos[1], locPos[2])
                            projDirMVector.normalize()
                            locPos = camPosMVector + (projDirMVector  * vecLen)

                    elif stickMode == 2: # Stick to closest geometry location found
                        locPos = previousPos

            # Set a key frame if a position has been found, either from the trace or the previous trace
            if locPos:
                # set key on current locator for this frame
                mc.setKeyframe( ('%s.originalTranslateX' % tracker[0]), t=f, v=locPos[0],  )
                mc.setKeyframe( ('%s.originalTranslateY' % tracker[0]), t=f, v=locPos[1] )
                mc.setKeyframe( ('%s.originalTranslateZ' % tracker[0]), t=f, v=locPos[2] )


    return result_trackers, result_joints


def debugPrintTrackers( trackingData, resX, resY ):
    """ Prints tracker name, frame, uv, xy(pixel) values """
    xExtent = resX * 0.5
    yExtent = resY * 0.5
    xCenter = resX * 0.5
    yCenter = resY * 0.5

    print( 'Tracking Data:' )

    for tracker in trackingData:
        print( '  %s' % tracker[0] )

        for frameData in tracker[1]:
            fnum = frameData[0]
            u = frameData[1]
            v = frameData[2]
            x = ( u * xExtent ) + xCenter
            y = ( v * yExtent ) + yCenter

            print( '    frame: %d' % fnum )
            print( '      u,v: %.4f, %.4f' % (u, v) )
            print( '      x,y: %.2f, %.2f' % (x, y) )

def validate_scene_unit():
    """Display a message when the units are not set to centimeters and return False"""
    translate = {'mm': 'millimeter', 'cm': 'centimeter', 'm': 'meter', 'in': 'inch', 'ft': 'foot', 'yd': 'yard'}

    unit = mc.currentUnit( query=True, linear=True )
    if unit == "cm":
        return True
    else:
        mc.confirmDialog(title='Wrong linear units', message='The current linear unit is set to {}, please change to centimeters'.format(translate[unit]))
        return False

class   TrackerImportUI:

    def __init__(self):

        if not validate_scene_unit(): # Quit right here if the settings are not in centimeters
            return None

        self.name = "trackerImportUI"
        self.title = "2D Tracker Import"

        self.path_2d = '/mnt/ol03/Projects/'

        file_path = mc.file(query=True, sceneName=True)
        if file_path:
            self.path_2d = os.path.join(self.path_2d, file_path.split('/')[4], file_path.split('/')[5], file_path.split('/')[6], '_3D')

        # begin creating the UI, cleaning up the old
        if (mc.window(self.name, q=True, exists=True)):
            mc.deleteUI(self.name)
        self.window = mc.window(self.name, title=self.title)

        # default to first camera in the scene
        defaultCam = mc.ls(type='camera')[0]

        # main form layout (keepin it simple - one column)
        self.form = mc.formLayout()

        self.format = mc.optionMenuGrp( label='Tracker Format: ', columnWidth=(2, 200) )
        mc.menuItem( label='Nuke 2D Ascii (single)' )
        mc.menuItem( label='Boujou 2D Ascii (multi)' )
        mc.menuItem( label='Syntheyes 2D Ascii (multi)' )
        mc.menuItem( label='3DEqualizer 2D Ascii (multi)' )
        mc.menuItem( label='PFTrack 2D Ascii (multi)' )
        mc.optionMenuGrp(self.format, e=True, sl=3)

        self.z = mc.floatSliderGrp( label='Z Depth: ', field=True, minValue=0.01, maxValue=100.0,
            fieldMinValue=0.001, fieldMaxValue=1000.0, value=DEFAULTS['z'] )

        # defaultWidth = mc.getAttr('defaultResolution.width')
        # defaultHeight = mc.getAttr('defaultResolution.height')
        self.resX = mc.intSliderGrp( label='X Pixel Resolution: ', field=True, minValue=512, maxValue=2048,
            fieldMinValue=1, fieldMaxValue=8192, value=mc.getAttr('defaultResolution.width') )
        self.resY = mc.intSliderGrp( label='Y Pixel Resolution: ', field=True, minValue=512, maxValue=2048,
            fieldMinValue=1, fieldMaxValue=16384, value=mc.getAttr('defaultResolution.height'))

        self.camera = mc.textFieldButtonGrp( label='Camera: ', text=defaultCam, buttonLabel='...', bc=self.loadCamera )

        self.path_2d = maya.ax_context.entity.get_work_dir()
        # Temporary path for dev
        #self.path_2d = '/mnt/ol03/Projects/InTheHeights/100/DRB/120/3dtrack/work/3dequalizer/exported_files/100_DRB_120_3dtrack_points_v02.txt'
        #self.path_2d = '/mnt/ol03/Projects/Emergence/103/050/050/3dtrack/work/syntheyes/exported_files/103_050_050_3dtrack_v02.txt'
        #self.path_2d = '/mnt/ol03/Projects/sandbox/603/004/050/3dtrack/work/3dequalizer/exported_files/603_003_050_3dtrack_points_v02.txt'
        self.filePath = mc.textFieldButtonGrp( label='Tracking File: ', text=self.path_2d, buttonLabel='...', bc=self.findFilePath )

        self.offsetX = mc.floatSliderGrp( label='Offset X: ', field=True, minValue=-1.0, maxValue=1.0,
            fieldMinValue=-8192.0, fieldMaxValue=8192.0, value=DEFAULTS['offsetX'], visible=False)
        self.offsetY = mc.floatSliderGrp( label='Offset Y: ', field=True, minValue=-1.0, maxValue=1.0,
            fieldMinValue=-8192.0, fieldMaxValue=8192.0, value=DEFAULTS['offsetY'], visible=False )

        self.frameOffset = mc.intSliderGrp( label='Frame Offset: ', field=True, minValue=-100, maxValue=100,
            fieldMinValue=-100000, fieldMaxValue=100000, value=DEFAULTS['frameOffset'] )

        self.displayScale = mc.floatSliderGrp( label='Locator Display Scale: ', field=True, minValue=0.1, maxValue=10.0,
            fieldMinValue=0.001, fieldMaxValue=100, precision=3, value=DEFAULTS['displayScale'] )

        self.createJoints = mc.checkBoxGrp( numberOfCheckBoxes=1, label='Create Joints: ', v1=DEFAULTS['createJoints'])

        self.prefix = mc.textFieldGrp( label='Group Prefix: ', text=DEFAULTS['prefix'] )

        self.animated = mc.checkBoxGrp( numberOfCheckBoxes=1, label='Animated Camera: ', changeCommand=self.animatedChangeCommand, v1=DEFAULTS['animated'], visible=False)

        self.projected = mc.checkBoxGrp( numberOfCheckBoxes=1, label='Project Points: ', changeCommand=self.projectedChangeCommand, enable=False, v1=DEFAULTS['projected'] )

        self.targetMesh = mc.textFieldButtonGrp( label='Target Mesh: ', text=DEFAULTS['targetMesh'], buttonLabel='...', bc=self.loadTargetMesh,
            enable=False )

        self.stickToLastHit = mc.checkBoxGrp( numberOfCheckBoxes=1, label='Stick To Last Hit: ', enable=False, v1=DEFAULTS['stickToLastHit'] )
        self.inheritNormal = mc.checkBoxGrp( numberOfCheckBoxes=1, label='Inherit Normal From Mesh: ', enable=False, v1=DEFAULTS['inheritNormal'] )

        self.stickMode = mc.optionMenuGrp( label='Stick Mode: ', columnWidth=(2, 200), enable=False )
        mc.menuItem( label='Stick To Closest Depth Found' )
        mc.menuItem( label='Stick To Closest Geometry Location Found' )
        mc.optionMenuGrp(self.stickMode, e=True, sl=DEFAULTS['stickMode'])

        self.debug = mc.checkBoxGrp( numberOfCheckBoxes=1, label='Debug Mode: ' )

        self.importTrack = mc.button(label='Import', w=140, c=self.execute)
        self.defaults = mc.button(label='Defaults', w=140, c=self.defaults)
        self.close = mc.button(label='Close', w=140, c=self.close)

        # Run the enable/disable rules on creation
        self.animatedChangeCommand()
        self.projectedChangeCommand()

        # Attach elements to form
        mc.formLayout( self.form,
            edit=True,
            attachForm=[
                (self.format, 'top', 2),
                (self.format, 'left', 2),
                (self.format, 'right', 2),
                (self.z, 'left', 2),
                (self.z, 'right', 2),
                (self.resX, 'left', 2),
                (self.resX, 'right', 2),
                (self.resY, 'left', 2),
                (self.resY, 'right', 2),
                (self.camera, 'left', 2),
                (self.camera, 'right', 2),
                (self.filePath, 'left', 2),
                (self.filePath, 'right', 2),
                (self.offsetX, 'left', 2),
                (self.offsetX, 'right', 2),
                (self.offsetY, 'left', 2),
                (self.offsetY, 'right', 2),
                (self.frameOffset, 'left', 2),
                (self.frameOffset, 'right', 2),
                (self.displayScale, 'left', 2),
                (self.displayScale, 'right', 2),
                (self.prefix, 'left', 2),
                (self.prefix, 'right', 2),
                (self.createJoints, 'left', 2),
                (self.createJoints, 'right', 2),
                (self.animated, 'left', 2),
                (self.animated, 'right', 2),
                (self.projected, 'left', 2),
                (self.projected, 'right', 2),
                (self.targetMesh, 'left', 2),
                (self.targetMesh, 'right', 2),
                (self.stickToLastHit, 'left', 2),
                (self.stickToLastHit, 'right', 2),
                (self.inheritNormal, 'left', 2),
                (self.inheritNormal, 'right', 2),
                (self.stickMode, 'left', 2),
                (self.stickMode, 'right', 2),
                (self.debug, 'left', 2),
                (self.debug, 'right', 2),
                (self.importTrack, 'left', 2)
                ],
            attachControl=[
                (self.z, 'top', 2, self.format),
                (self.resX, 'top', 2, self.z),
                (self.resY, 'top', 2, self.resX),
                (self.camera, 'top', 2, self.resY),
                (self.filePath, 'top', 2, self.camera),
                (self.offsetX, 'top', 2, self.filePath),
                (self.offsetY, 'top', 2, self.offsetX),
                (self.frameOffset, 'top', 2, self.offsetY),
                (self.displayScale, 'top', 2, self.frameOffset),
                (self.prefix, 'top', 2, self.displayScale),
                (self.createJoints, 'top', 2, self.prefix),
                (self.animated, 'top', 2, self.createJoints),
                (self.projected, 'top', 2, self.animated),
                (self.targetMesh, 'top', 2, self.projected),
                (self.stickToLastHit, 'top', 2, self.targetMesh),
                (self.inheritNormal, 'top', 2, self.stickToLastHit),
                (self.stickMode, 'top', 2, self.inheritNormal),
                (self.debug, 'top', 2, self.stickMode),
                (self.importTrack, 'top', 2, self.debug),
                (self.defaults, 'top', 2, self.debug),
                (self.defaults, 'left', 2, self.importTrack),
                (self.close, 'top', 2, self.debug),
                (self.close, 'left', 2, self.defaults)
            ]
        )

        mc.window(self.window, e=1, w=430, h=352)
        mc.showWindow(self.window)

    def loadCamera(self, *args):
        sel = mc.ls(sl=True)
        if len(sel):
            if (mc.nodeType(sel[0]) == 'transform'):
                rel = mc.listRelatives(sel[0], s=True)
                if (mc.nodeType(rel[0]) == 'camera'):
                    # Load first selected
                    mc.textFieldButtonGrp(self.camera, e=True, text=rel[0])
                else:
                    mc.confirmDialog( title='Error', message='Not a camera transform.', icon='warning', button=['Oh noes!'] )
                    #mc.textFieldButtonGrp(self.camera, e=True, text='')

    def loadTargetMesh(self, *args):
        sel = mc.ls(sl=True)
        if len(sel):
            if (mc.nodeType(sel[0]) == 'transform'):
                rel = mc.listRelatives(sel[0], s=True)
                if (mc.nodeType(rel[0]) == 'mesh'):
                    # Load first selected
                    mc.textFieldButtonGrp(self.targetMesh, e=True, text=rel[0])
                else:
                    mc.confirmDialog( title='Error', message='Not a mesh transform.', icon='warning', button=['Oh noes!'] )
                    mc.textFieldButtonGrp(self.targetMesh, e=True, text='')

    def projectedChangeCommand(self, *args):
        if mc.checkBoxGrp(self.projected, q=True, v1=True):
            """ Project is ticked, so enable targetMesh and stickToLastHit. """
            mc.textFieldButtonGrp(self.targetMesh, e=True, enable=True)
            mc.checkBoxGrp(self.stickToLastHit, e=True, enable=True)
            mc.checkBoxGrp(self.inheritNormal, e=True, enable=True)
            mc.optionMenuGrp(self.stickMode, e=True, enable=True)
        else:
            """ Project is not ticked, so disable targetMesh. """
            mc.textFieldButtonGrp(self.targetMesh, e=True, enable=False)
            mc.checkBoxGrp(self.stickToLastHit, e=True, enable=False)
            mc.checkBoxGrp(self.inheritNormal, e=True, enable=False)
            mc.optionMenuGrp(self.stickMode, e=True, enable=False)

    def animatedChangeCommand(self, *args):
        if mc.checkBoxGrp(self.animated, q=True, v1=True):
            """ Animated is ticked, so enable project. """
            mc.checkBoxGrp(self.projected, e=True, enable=True)
            # query if projected is still checked, enable/disable mesh appropriately
            self.projectedChangeCommand()
        else:
            """ Animated is not ticked, so disable project mode (and therefore targetMesh). """
            mc.checkBoxGrp(self.projected, e=True, enable=False)
            mc.textFieldButtonGrp(self.targetMesh, e=True, enable=False)
            mc.checkBoxGrp(self.stickToLastHit, e=True, enable=False)
            mc.checkBoxGrp(self.inheritNormal, e=True, enable=False)
            mc.optionMenuGrp(self.stickMode, e=True, enable=False)

    def findFilePath(self, *args):
        basicFilter = "*"
        result = mc.fileDialog2(fileFilter=basicFilter, dialogStyle=2, fileMode=1, dir=self.path_2d)
        if (result):
            mc.textFieldButtonGrp(self.filePath, e=True, text=result[0])

    def defaults(self, *args):
        # print mc.optionMenuGrp(self.format, q=True, v=True)
        # mc.optionMenuGrp(self.format, e=True, v=2)
        mc.floatSliderGrp(self.z, e=True, v=DEFAULTS['z'])
        mc.intSliderGrp(self.resX, e=True, v=mc.getAttr('defaultResolution.width'))
        mc.intSliderGrp(self.resY, e=True, v=mc.getAttr('defaultResolution.height'))
        mc.floatSliderGrp(self.offsetX, e=True, v=DEFAULTS['offsetX'])
        mc.floatSliderGrp(self.offsetY, e=True, v=DEFAULTS['offsetY'])
        mc.intSliderGrp(self.frameOffset, e=True, v=DEFAULTS['frameOffset'])
        mc.floatSliderGrp(self.displayScale, e=True, v=DEFAULTS['displayScale'])
        mc.textFieldGrp(self.prefix, e=True, text=DEFAULTS['prefix'])
        mc.checkBoxGrp(self.createJoints, e=True, v1=DEFAULTS['createJoints'])
        mc.checkBoxGrp(self.animated, e=True, v1=DEFAULTS['animated'])
        mc.checkBoxGrp(self.projected, e=True, v1=DEFAULTS['projected'])
        mc.textFieldButtonGrp(self.targetMesh, e=True, text=DEFAULTS['targetMesh'])
        mc.checkBoxGrp(self.stickToLastHit, e=True, enable=False, v1=DEFAULTS['stickToLastHit'])
        mc.checkBoxGrp(self.inheritNormal, e=True, enable=False, v1=DEFAULTS['inheritNormal'])
        mc.optionMenuGrp(self.stickMode, e=True, sl=DEFAULTS['stickMode'])
        mc.checkBoxGrp(self.debug, e=True, v1=False)

        # Run the enable/disable rules on creation
        self.animatedChangeCommand()
        self.projectedChangeCommand()

    def close(self, *args):
        mc.deleteUI(self.name)

    def execute(self, *args):
        # query the gui
        format = mc.optionMenuGrp(self.format, q=True, sl=True) #1=nuke, 2=boujou, 3=syntheyes
        z = mc.floatSliderGrp(self.z, q=True, v=True)
        resolutionX = mc.intSliderGrp(self.resX, q=True, v=True)
        resolutionY = mc.intSliderGrp(self.resY, q=True, v=True)
        # resolutionX = mc.getAttr('defaultResolution.width')
        # resolutionY = mc.getAttr('defaultResolution.height')
        # print 'res x is: %s' % resolutionX
        cameraShape = mc.textFieldButtonGrp(self.camera, q=True, text=True)
        trackingDataPath = mc.textFieldButtonGrp(self.filePath, q=True, text=True)
        offsetX = mc.floatSliderGrp(self.offsetX, q=True, v=True)
        offsetY = mc.floatSliderGrp(self.offsetY, q=True, v=True)
        frameOffset = mc.intSliderGrp(self.frameOffset, q=True, v=True)
        locatorDisplayScale = mc.floatSliderGrp(self.displayScale, q=True, v=True)
        prefix = mc.textFieldGrp(self.prefix, q=True, text=True)
        createJoints = mc.checkBoxGrp(self.createJoints, q=True, v1=True)
        animatedCamera = mc.checkBoxGrp(self.animated, q=True, v1=True)
        projected = mc.checkBoxGrp(self.projected, q=True, v1=True)
        targetMesh = mc.textFieldButtonGrp(self.targetMesh, q=True, text=True)
        stickToLastHit = mc.checkBoxGrp(self.stickToLastHit, q=True, v1=True)
        inheritNormal = mc.checkBoxGrp(self.inheritNormal, q=True, v1=True)
        stickMode = mc.optionMenuGrp(self.stickMode, q=True, sl=True)

        debugMode = mc.checkBoxGrp(self.debug, q=True, v1=True)

        # query the camera attributes
        focalLength = mc.camera( cameraShape, q=True, fl=True )
        lensSqueezeRatio = mc.camera( cameraShape, q=True, lsr=True )
        horizontalFilmAperture = mc.camera( cameraShape, q=True, hfa=True ) * 25.4
        verticalFilmAperture = mc.camera( cameraShape, q=True, vfa=True ) * 25.4
        nearClippingPlane = mc.camera( cameraShape, q=True, ncp=True )
        farClippingPlane = mc.camera( cameraShape, q=True, fcp=True )
        worldPosition = mc.camera( cameraShape, q=True, p=True )
        worldCenterOfInterest = mc.camera( cameraShape, q=True, wci=True )

        # query the render attributes
        # renderWidth = mc.getAttr( 'defaultResolution.width' )
        # renderHeight = mc.getAttr( 'defaultResolution.height' )

        # make sure film gate aspect and render aspect are identical
        epsilon = 0.0001
        filmAspect  = horizontalFilmAperture / verticalFilmAperture
        #pixelAspect = float(renderWidth) / float(renderHeight)
        pixelAspect = float(resolutionX) / float(resolutionY)
        # if ( (filmAspect-pixelAspect) > epsilon ):
        #     errorMsg =  'Camera film gate ascpect ratio does not match render\n'
        #     errorMsg += 'resolution aspect ratio.\n\n'
        #     errorMsg += 'Camera: %s\n' % cameraShape
        #     errorMsg += 'Film Gate (mm): %.3f/%.3f = %.3f \n' % ( horizontalFilmAperture, verticalFilmAperture, filmAspect )
        #     errorMsg += 'Resolution (pixels): %d/%d = %.3f\n' % ( renderWidth, renderHeight, pixelAspect )
        #     mc.confirmDialog( title='Error', message=errorMsg, icon='warning', button=['Oh Shit'] )
        #     return

        # read the data from the file
        if   (format == 1):
            trackingData = loadNukeASCII2D( trackingDataPath, resolutionX, resolutionY, frameOffset )
        elif (format == 2):
            trackingData = loadBoujouTracksFile( trackingDataPath, resolutionX, resolutionY, offsetX, offsetY, frameOffset )
        elif (format == 3):
            trackingData = loadSyntheyes2DTrackerPaths( trackingDataPath, offsetX, offsetY, frameOffset )
        elif (format == 4):
            trackingData = load3deTrackerPaths( trackingDataPath, resolutionX, resolutionY, offsetX, offsetY, frameOffset )
        else:
            trackingData = loadPFTrackAscii2D( trackingDataPath, resolutionX, resolutionY, frameOffset )

        # # Add the | suffixe to make sure these don't refer to other tracking points within groups
        # for tracking in trackingData:
        #     print 'aaaaaaa', tracking[0]
        #     tracking[0] = '|' + tracking[0]

        # dubug parsed ascii file data in UV and pixel space
        if (debugMode):
            debugPrintTrackers( trackingData, resolutionX, resolutionY )

        # camera aim vectors using OpenMaya
        aimUp = mc.camera( cameraShape, q=True, wup=True )
        wc = asOMVec( worldCenterOfInterest )
        wp = asOMVec( worldPosition )
        au = asOMVec( aimUp )
        au.normalize()
        ad = wc-wp # veiwing direction towards world center of interest
        ad.normalize()
        at = ad^au # image x axis vector is the cross between up and direction
        at.normalize()
        aimDir = asTVec( ad )
        aimTan = asTVec( at )

        # calculate FOV along both horizontal and vertical directions
        horizontalFOV = 2 * math.atan( horizontalFilmAperture / (2 * focalLength) )
        verticalFOV = 2 * math.atan( verticalFilmAperture / (2 * focalLength) )

        # debug camera attributes
        if (debugMode):
            print( 'focalLength: %.3f mm' % focalLength )
            print( 'lensSqueezeRatio: %.3f' % lensSqueezeRatio )
            print( 'horizontalFilmAperture: %.3f mm' % horizontalFilmAperture )
            print( 'verticalFilmAperture: %.3f mm' % verticalFilmAperture )
            print( 'nearClippingPlane: %.3f' % nearClippingPlane )
            print( 'farClippingPlane: %.3f' % farClippingPlane )
            print( 'horizontalFOV: %.3f degrees' % radToDeg(horizontalFOV) )
            print( 'verticalFOV: %.3f degrees' % radToDeg(verticalFOV) )
            print( 'worldPosition: %.3f %.3f %.3f' % (worldPosition[0],
                                                      worldPosition[1],
                                                      worldPosition[2]) )
            print( 'worldCenterOfInterest: %.3f %.3f %.3f' % (worldCenterOfInterest[0],
                                                              worldCenterOfInterest[1],
                                                              worldCenterOfInterest[2]) )
            print( 'aimUp: %.3f %.3f %.3f' % (aimUp[0], aimUp[1], aimUp[2]) )
            print( 'aimDir: %.3f %.3f %.3f' % (aimDir[0], aimDir[1], aimDir[2]) )
            print( 'aimTan: %.3f %.3f %.3f' % (aimTan[0], aimTan[1], aimTan[2]) )
            print( 'renderWidth: %d' % resolutionX )
            print( 'renderHeight: %d' % resolutionY )


        # create the x,y points of the plane with normal -z for
        # a camera at the origin. we then transform those points
        # with the camera's transform matrix
        xpos = z * math.tan( horizontalFOV /  2 )
        xneg = z * math.tan( horizontalFOV / -2 )
        ypos = z * math.tan( verticalFOV   /  2 )
        yneg = z * math.tan( verticalFOV   / -2 )

        topRight  = ( xpos, ypos, -z )
        topLeft   = ( xneg, ypos, -z )
        downRight = ( xpos, yneg, -z )
        downLeft  = ( xneg, yneg, -z )

        worldMatrix = mc.getAttr( ('%s.worldMatrix' % cameraShape) )
        wm = api.MMatrix( worldMatrix )
        #api.MScriptUtil().createMatrixFromList(worldMatrix, wm)
        #camWorldPos = api.MVector(wm(3,0), wm(3,1), wm(3,2))
        camWorldPos = api.MVector( wm[12], wm[13], wm[14] )

        topRight  = asTVec( asOMVec(topRight)  * wm + camWorldPos )
        topLeft   = asTVec( asOMVec(topLeft)   * wm + camWorldPos )
        downRight = asTVec( asOMVec(downRight) * wm + camWorldPos )
        downLeft  = asTVec( asOMVec(downLeft)  * wm + camWorldPos )

        # debug corners
        if (debugMode):
            temp = mc.spaceLocator( a=True, p=topRight, n='topRight' )
            tempShape = mc.listRelatives( temp, s=True, pa=True )[0]
            mc.setAttr( ('%s.localScaleX' % tempShape), locatorDisplayScale )
            mc.setAttr( ('%s.localScaleY' % tempShape), locatorDisplayScale )
            mc.setAttr( ('%s.localScaleZ' % tempShape), locatorDisplayScale )

            temp = mc.spaceLocator( a=True, p=topLeft, n='topLeft' )
            tempShape = mc.listRelatives( temp, s=True, pa=True )[0]
            mc.setAttr( ('%s.localScaleX' % tempShape), locatorDisplayScale )
            mc.setAttr( ('%s.localScaleY' % tempShape), locatorDisplayScale )
            mc.setAttr( ('%s.localScaleZ' % tempShape), locatorDisplayScale )

            temp = mc.spaceLocator( a=True, p=downRight, n='downRight' )
            tempShape = mc.listRelatives( temp, s=True, pa=True )[0]
            mc.setAttr( ('%s.localScaleX' % tempShape), locatorDisplayScale )
            mc.setAttr( ('%s.localScaleY' % tempShape), locatorDisplayScale )
            mc.setAttr( ('%s.localScaleZ' % tempShape), locatorDisplayScale )

            temp = mc.spaceLocator( a=True, p=downLeft, n='downLeft' )
            tempShape = mc.listRelatives( temp, s=True, pa=True )[0]
            mc.setAttr( ('%s.localScaleX' % tempShape), locatorDisplayScale )
            mc.setAttr( ('%s.localScaleY' % tempShape), locatorDisplayScale )
            mc.setAttr( ('%s.localScaleZ' % tempShape), locatorDisplayScale )


        # place the tracking locators with keyframes
        if not animatedCamera:
            trackers, joints = createLocators( trackingData, xneg, xpos, yneg, ypos, z, wm, cameraShape, camWorldPos, locatorDisplayScale, createJoints )
        else:

            # Deactivate the image planes
            states = ConsistentCameraExport.disableCamerasAndImagePlanes()

            if not projected:
                trackers, joints = createLocatorsAnimProjectCam( trackingData, z, cameraShape, locatorDisplayScale, createJoints )
            else:
                # Create a temporay UV set. Valid UVs must exist for each polygons in order to
                # keep a reference of the previous location in UV space.
                # (Maya doesn't seem to have functions to access the position of location on a polygon based on the primitive number and barymetric coordinate)
                # We have to create a copy of the original geo so the mesh doesn't have any deformation coming
                # from Alembic for example. From there we create the automatic uv and then transfer them on the animated geo.
                if not targetMesh:
                    raise NameError('The target mesh is invalid')

                if stickToLastHit:
                    uv_geo = mc.duplicate(targetMesh, returnRootsOnly=True, name=TEMP_UV_GEO_NAME)[0]
                    # Delete the uv set if it already exists
                    if UV_SET_NAME in mc.polyUVSet(uv_geo, query=True, allUVSets=True):
                        mc.polyUVSet (uv_geo, delete=True, uvSet=UV_SET_NAME)
                    mc.polyAutoProjection ( uv_geo, layoutMethod=0, projectBothDirections=0, insertBeforeDeformers=0, createNewMap=True, layout=2, scaleMode=1, optimize=0, planes=12, uvSetName=UV_SET_NAME, percentageSpace=0.2, worldSpace=0)
                    mc.polyUVSet( uv_geo, currentUVSet=True, uvSet=UV_SET_NAME)
                    # if mc.pluginInfo ( 'Unfold3D.so', query=True, loaded=True) == False:
                    #     mc.loadPlugin( 'Unfold3D.so' )
                    # u3dUnfold( TEMP_UV_GEO_NAME, unfold=True, iterations=1, pack=True, borderintersection=True, triangleflip=True, mapsize=1024, roomspace=2)
                    #mc.Unfold3D( TEMP_UV_GEO_NAME, unfold=True, iterations=1, pack=True, borderintersection=True, triangleflip=True, mapsize=1024, roomspace=2) # maya 2016
                    # polyAutoProjection -lm 0 -pb 0 -ibd 1 -cm 0 -l 2 -sc 2 -o 0 -p 6 -ps 0.2 -ws 0
                    # u3dUnfold -ite 1 -p 0 -bi 1 -tf 1 -ms 1024 -rs 0
                    #u3dLayout -res 256 -scl 1 -box 0 1 0 1 -ls 3

                    transfer_node = mc.transferAttributes(uv_geo, targetMesh, transferPositions=0, transferNormals=0, transferUVs=1, transferColors=0, sampleSpace=4, sourceUvSet=UV_SET_NAME, targetUvSet=UV_SET_NAME, sourceUvSpace=UV_SET_NAME, targetUvSpace=UV_SET_NAME, searchMethod=3, flipUVs=0, colorBorders=1)

                trackers, joints = createLocatorsAnimProjectCam( trackingData, z, cameraShape, locatorDisplayScale, createJoints, targetMesh, stickToLastHit, inheritNormal, stickMode )

                if stickToLastHit:
                    # Delete the temporary uv mesh
                    mc.delete ( uv_geo )
                    mc.delete ( transfer_node )

            # Reactivate the previous planes
            ConsistentCameraExport.enableCamerasAndImagePlanes(states)


        # Create the trackers group
        print( 'Creating trackers group' )
        if prefix:
            prefix = '{}_'.format(prefix)
        tracker_group = mc.group( empty=True, name='{}tracker_group'.format(prefix))
        # Add each tracker to the group
        for tracker in trackers:
            mc.parent( tracker, tracker_group, relative=True)

        # Create the joints group
        if createJoints:
            print( 'Creating joints group' )
            joint_group = mc.group( empty=True, name='{}joint_group'.format(prefix))
            # Add each tracker to the group
            for joint in joints:
                mc.parent( joint, joint_group, relative=True)

if __name__ == '__main__':
    TrackerImportUI()
