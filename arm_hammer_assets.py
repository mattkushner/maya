import maya.cmds as mc
import os
import camera_match


def setup_anim_scene(shot_name):
    """Arm and Hammer specific anim scene setup, imports, references and constrains necessary files from Tracking/Layout"""
    # import files
    seq_name = shot_name.split('_')[0]
    key_dict = {}
    import_dict = {'locator_path': '', 'camera_path': '', 'layout_path': '', 'references': {}}
    
    scene_dir = '/mnt/ol03/Projects/ArmHammer/'+seq_name+'/'+shot_name+'/_3D/maya/scenes/'
    import_dict['locator_path'] = os.path.join(scene_dir, shot_name+'_mm_loc.mb')
    camera_layouts  = os.listdir(os.path.join(scene_dir, 'Camera_Layout'))
    for camera_layout in camera_layouts:
        kind = 'camera'
        if 'Layout' in camera_layout:
            kind = 'layout'
        import_dict[kind+'_path'] = os.path.join(scene_dir, 'Camera_Layout', camera_layout)
    
    for key, value in import_dict.iteritems():
        if value and os.path.isfile(value):
            if 'locator' in key:
                mc.file(value, r=1, type="mayaBinary", ignoreVersion=True, mergeNamespacesOnClash=False, namespace='mm')
            else:
                mc.file(value, i=1, ignoreVersion=True, mergeNamespacesOnClash=False, rpr=key.split('_')[0], options='v=0;', pr=1)

    # determine which cat assets are needed
    mm_grp = mc.listRelatives('mm:MM_GRP', allDescendents=True)
    # set up references in dictionary
    for mm in mm_grp:
        if '_head_ctrl_loc' in mm and mc.nodeType(mm) != 'locator':
            cat = cat_asset = mm.replace('_head_ctrl_loc', '').split(':')[1]
            # since only one ChildCat asset
            if 'Child' in cat:
                cat_asset = 'ChildCat_1'
            import_dict['references'][cat] = {'path': '/mnt/ol03/Projects/ArmHammer/_shared/_assets/Character/'+cat_asset+'/publish/maya/', 'asset': cat_asset}
            key_dict = camera_match.get_keys(mm, 'translateX')
    mc.playbackOptions(minTime=key_dict['first'], animationStartTime=key_dict['first'], maxTime=key_dict['last'], animationEndTime=key_dict['last'])
    mc.currentTime(key_dict['first'])
    # get reference file and constrain cats to locators
    for cat, cat_dict in import_dict['references'].iteritems():
        ref_files = sorted([f for f in os.listdir(cat_dict['path']) if cat_dict['asset'] in f])
        ref_path = os.path.join(cat_dict['path'], ref_files[-1])
        ns = ref_files[-1].split('.')[0]
        # for Child cats, asset name and cat instance are different, so swap in namespace
        ns = ns.replace(cat_dict['asset'], cat)
        referenced = mc.file(ref_path, r=1, type="mayaAscii", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=ns, returnNewNodes=True)
        head_ctrls = [f for f in referenced if f.split(':')[-1] == 'head_ctrl']
        if head_ctrls:
            mc.parentConstraint('mm:'+cat+'_head_ctrl_loc', head_ctrls[0], maintainOffset=False)
            mc.scaleConstraint('mm:'+cat+'_head_ctrl_loc', head_ctrls[0], maintainOffset=False, skip=["y", "z"])
