import os
import re
import maya.cmds as mc
import maya.mel as mel

def setFBXExportSettings():
    # Load FBX plugin if necessary
    if not mc.pluginInfo('fbxmaya', q=True, loaded=True):
        mc.loadPlugin('fbxmaya')

    # Set necessary FBX settings for camera export
    mel.eval('FBXProperty Export|IncludeGrp|Animation -v true;')
    mel.eval('FBXProperty Export|IncludeGrp|Animation|ExtraGrp|UseSceneName -v false;')
    mel.eval('FBXProperty Export|IncludeGrp|Animation|ExtraGrp|RemoveSingleKey -v false;')
    mel.eval('FBXProperty Export|IncludeGrp|Animation|ExtraGrp|Quaternion -v "Resample As Euler Interpolation";')
    mel.eval('FBXProperty Export|IncludeGrp|Animation|BakeComplexAnimation -v true;')
    mel.eval('FBXProperty Export|IncludeGrp|Animation|CurveFilter -v false;')
    mel.eval('FBXProperty Export|IncludeGrp|Animation|PointCache -v false;')
    mel.eval('FBXProperty Export|IncludeGrp|CameraGrp|Camera -v true;')
    mel.eval('FBXProperty Export|IncludeGrp|PivotToNulls -v false;')  # What does this do?
    mel.eval('FBXProperty Export|IncludeGrp|BypassRrsInheritance -v false;')  # What does this do?
    mel.eval('FBXProperty Export|IncludeGrp|InputConnectionsGrp|InputConnections -v false;')
    mel.eval('FBXProperty Export|AdvOptGrp|UnitsGrp|DynamicScaleConversion -v true;')
    mel.eval('FBXProperty Export|AdvOptGrp|AxisConvGrp|UpAxis -v "Y";')
    mel.eval('FBXProperty Export|AdvOptGrp|UI|ShowWarningsManager -v false;')
    mel.eval('FBXProperty Export|AdvOptGrp|UI|GenerateLogData -v false;')
    mel.eval('FBXProperty Export|AdvOptGrp|Fbx|AsciiFbx -v "ASCII";')
    mel.eval('FBXProperty Export|AdvOptGrp|Fbx|ExportFileVersion -v "FBX200900";')

    # The following settings are supposed to be redundant and the same as the above settings but the FBX plugin doesn't work entirely as documented so setting them here too just in case.
    mel.eval('FBXExportAnimationOnly -v true;')
    mel.eval('FBXExportBakeComplexAnimation -v true;')
    mel.eval('FBXExportBakeResampleAnimation -v false;')
    mel.eval('FBXExportCameras -v true;')
    mel.eval('FBXExportFileVersion -v FBX200900;')
    mel.eval('FBXExportGenerateLog -v false;')
    mel.eval('FBXExportInAscii -v true;')
    mel.eval('FBXExportInputConnections -v false;')
    mel.eval('FBXExportUseSceneName -v false;')

def exportFBXcam(cameraTf, outputPath):
    setFBXExportSettings()

    # Incase the path ends in a slash, remove it
    #if outputDir[-1] == '/':
        #outputDir = outputDir[0:-1]

    # Generate output file path based on camera name
    #FBXfile = os.path.join(outputDir, '%s.fbx' % cameraTf)
    #FBXfile = FBXfile.replace('\\', '/') # fbx exporter will choke on windows backslashes
    FBXmel  = 'FBXExport -s -f "%s";' % outputPath

    # Export the file
    mc.select(cl=True)
    mc.select(cameraTf)
    mel.eval(FBXmel)

def exportFBXLayout(locTfs, outputPath):
    mel.eval('FBXExportFileVersion "FBX201000"')
    mel.eval('FBXExportConvertUnitString "cm"')
    mel.eval('FBXExportInputConnections -v 0')

    # Incase the path ends in a slash, remove it
    #if outputDir[-1] == '/':
       # outputDir = outputDir[0:-1]

    # Generate output file path
    #FBXfile = os.path.join(outputDir, '%s.fbx' % "RenderCam_Layout")
    #FBXfile = FBXfile.replace('\\', '/') # fbx exporter will choke on windows backslashes
    FBXmel  = 'FBXExport -s -f "%s";' % outputPath

    # Export the file (After selecting all of the locators)
    mc.select(cl=True)
    index = 0
    for locTf in locTfs:
        if index == 0:
            mc.select(locTf)
        else:
            mc.select(locTf, tgl = True)
        index = index + 1
    print FBXmel
    mel.eval(FBXmel)
