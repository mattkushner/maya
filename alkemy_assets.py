import maya.cmds as mc
import os

def reference_assets_UI():
    """Reference Assets UI."""
    # window creation
    asset_dict = refresh_asset_dict()
    if asset_dict:
        if mc.window('referenceAssetsWindow', exists=1):
            mc.deleteUI('referenceAssetsWindow')
        reference_assets_window = mc.window('referenceAssetsWindow', title='Reference Asset', sizeable=0, width=200, height=100)
        mc.frameLayout(label='Master', visible=0, manage=0, labelVisible=0)
        mc.frameLayout(label='Choose your Asset Type and Asset Name', collapsable=0, collapse=0)
        mc.formLayout('assetInfoForm', numberOfDivisions=100)
        asset_dict_field = mc.textField('asset_dict_field', visible=False, text=str(asset_dict))
        asset_type_list = mc.optionMenu('asset_type_list', label='Asset Type', width=300, changeCommand=lambda *args: load_assets(asset_dict_field, asset_type_list, asset_name_list))
        asset_name_list = mc.optionMenu('asset_name_list', label='Asset Name', width=300)
        load_assets(asset_dict_field, asset_type_list, asset_name_list, load_types=True)
        refresh_asset_button = mc.button('refresh_asset_button', label='Refresh Assets', width=150, height=25, backgroundColor=[0.1, 0.1, 0.1], command=lambda *args: refresh_assets(asset_dict_field, asset_type_list, asset_name_list),
                                annotation='Refresh asset list from current job.')
        load_asset_button = mc.button('load_asset_button', label='Reference Asset', width=150, height=25, backgroundColor=[0.1, 0.1, 0.1], command=lambda *args: reference_asset(asset_dict_field, asset_type_list, asset_name_list),
                                annotation='Reference latest pub/work file for chosen asset.')
        mc.setParent('..')
        mc.formLayout('assetInfoForm', edit=1, attachForm=[('asset_type_list', 'top', 20), ('asset_type_list', 'left', 50),
                                                            ('asset_name_list', 'top', 50), ('asset_name_list', 'left', 50),
                                                            ('load_asset_button', 'top', 80), ('load_asset_button', 'left', 50),
                                                            ('refresh_asset_button', 'top', 80), ('refresh_asset_button', 'left', 200)])
        mc.window(reference_assets_window, edit=True, width=400, height=150)
        mc.showWindow(reference_assets_window)

def refresh_asset_dict(asset_dict_field=None):
    asset_dict = {}
    scene_path = mc.file(query=True, sceneName=True)
    if not scene_path:
        result = mc.fileDialog2(caption='Save Your File To a Job', dir='/mnt/ol03/Projects/', fileFilter="*.mb")
        if result:
            scene_path = result[0]
            if scene_path:
                mc.file(rename=scene_path)
                mc.file(save=True, type='mayaBinary')
    if scene_path:
        job_name = scene_path.split('/')[4]
        asset_dict = list_assets(job_name)
    if asset_dict_field:
        mc.textField(asset_dict_field, edit=True, text=str(asset_dict))

    return asset_dict

def load_assets(asset_dict_field, asset_type_list, asset_name_list, load_types=False):
    asset_dict = eval(mc.textField(asset_dict_field, query=True, text=True))
    if asset_dict:
        if load_types:
            asset_type_items = mc.optionMenu(asset_type_list, query=True, itemListLong=True)
            if asset_type_items:
                mc.deleteUI(asset_type_items)
            for asset_type in sorted(asset_dict.keys()):
                mc.menuItem(parent=asset_type_list, label=asset_type)
        asset_type = mc.optionMenu(asset_type_list, query=True, value=True)
        asset_name_items = mc.optionMenu(asset_name_list, query=True, itemListLong=True)
        if asset_name_items:
            mc.deleteUI(asset_name_items)
        asset_names = asset_dict[asset_type]['assets']
        for asset_name in sorted(asset_names):
            mc.menuItem(parent=asset_name_list, label=asset_name)

def refresh_assets(asset_dict_field, asset_type_list, asset_name_list):
    refresh_asset_dict(asset_dict_field)
    load_assets(asset_dict_field, asset_type_list, asset_name_list, load_types=True)

def list_assets(job_name):
    assets_dir = os.path.join('/mnt', 'ol03', 'Projects', job_name, '_shared', '_assets')
    asset_dict = {'Character': {'dir': '', 'assets': []},
                  'Environment': {'dir': '', 'assets': []},
                  'Prop': {'dir': '', 'assets': []},
                  'Vehicle': {'dir': '', 'assets': []}}
    for asset_type in asset_dict.keys():
        asset_dict[asset_type]['dir'] = os.path.join('/mnt', 'ol03', 'Projects', job_name, '_shared', '_assets', asset_type)
        asset_dict[asset_type]['assets'] = [f for f in os.listdir(asset_dict[asset_type]['dir']) if '.' not in f]
    return asset_dict

def reference_asset(asset_dict_field, asset_type_list, asset_name_list):
    asset_dict = eval(mc.textField(asset_dict_field, query=True, text=True))
    asset_type = mc.optionMenu(asset_type_list, query=True, value=True)
    asset_name = mc.optionMenu(asset_name_list, query=True, value=True)
    if asset_name in asset_dict[asset_type]['assets']:
        # try publish directory first
        asset_dir = os.path.join(asset_dict[asset_type]['dir'], asset_name, 'publish', 'maya')
        asset_files = [f for f in os.listdir(asset_dir) if os.path.isfile(os.path.join(asset_dir, f)) and any(f.endswith(e) for e in ['.ma', '.mb'])]
        # fall back on work directory
        if not asset_files:
            asset_dir = os.path.join(asset_dict[asset_type]['dir'], asset_name, 'work', 'maya', 'scenes')
            asset_files = [f for f in os.listdir(asset_dir) if os.path.isfile(os.path.join(asset_dir, f)) and any(f.endswith(e) for e in ['.ma', '.mb'])]
        if asset_files:
            latest_file = os.path.join(asset_dir, sorted(asset_files)[-1])
            file_type = "mayaBinary"
            if latest_file.endswith('.ma'):
                file_type = 'mayaAscii'
            mc.file(latest_file, r=1, type=file_type, ignoreVersion=True, mergeNamespacesOnClash=False, namespace=asset_name)
        else:
            print('No maya files in directory.')
    else:
        print(asset_name + ' not in job structure.')
