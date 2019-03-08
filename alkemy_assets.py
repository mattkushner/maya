import maya.cmds as mc
import os

def reference_assets_UI():
    """Reference Assets UI."""
    file_pieces = mc.file(query=True, sceneName=True).split('/')
    if len(file_pieces)>1:
        job_name = file_pieces[4]
        asset_dict = list_assets(job_name)
        # window creation
        if mc.window('referenceAssetsWindow', exists=1):
            mc.deleteUI('referenceAssetsWindow')
        reference_assets_window = mc.window('referenceAssetsWindow', title='Reference Asset', sizeable=0, width=200, height=100)
        mc.frameLayout(label='Master', visible=0, manage=0, labelVisible=0)
        mc.frameLayout(label='Choose your Asset Type and Asset Name', collapsable=0, collapse=0)
        mc.formLayout('assetInfoForm', numberOfDivisions=100)
        asset_type_list = mc.optionMenu('asset_type_list', label='Asset Type', width=300, changeCommand=lambda *args: load_assets(asset_dict, asset_type_list, asset_name_list))
        for asset_type in sorted(asset_dict.keys()):
            mc.menuItem(asset_type_list, label=asset_type)
        asset_name_list = mc.optionMenu('asset_name_list', label='Asset Name', width=300)
        load_asset_button = mc.button('load_asset_button', label='Reference Asset', width=150, height=25, backgroundColor=[0.1, 0.1, 0.1], command=lambda *args: reference_asset(asset_dict, asset_type_list, asset_name_list),
                             annotation='Reference latest work file for chosen asset.')
        mc.setParent('..')
        mc.formLayout('assetInfoForm', edit=1, attachForm=[('asset_type_list', 'top', 10), ('asset_type_list', 'left', 60),
                                                           ('asset_name_list', 'top', 40), ('asset_name_list', 'left', 60),
                                                           ('load_asset_button', 'top', 70), ('load_asset_button', 'left', 150)])
        mc.window(reference_assets_window, edit=True, width=400, height=150)
        load_assets(asset_dict, asset_type_list, asset_name_list)
        mc.showWindow(reference_assets_window)
    else:
        mc.error('Please open a file.')

def load_assets(asset_dict, asset_type_list, asset_name_list):
    asset_type = mc.optionMenu(asset_type_list, query=True, value=True)
    menu_items = mc.optionMenu(asset_name_list, query=True, itemListLong=True)
    if menu_items:
        mc.deleteUI(menu_items)
    asset_names = asset_dict[asset_type]['assets']
    for asset_name in sorted(asset_names):
        mc.menuItem(asset_type_list, label=asset_name)
        
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

def reference_asset(asset_dict, asset_type_list, asset_name_list):
    asset_type = mc.optionMenu(asset_type_list, query=True, value=True)
    asset_name = mc.optionMenu(asset_name_list, query=True, value=True)
    if asset_name in asset_dict[asset_type]['assets']:
        asset_dir = os.path.join(asset_dict[asset_type]['dir'], asset_name, 'work', 'maya', 'scenes')
        asset_files = [f for f in os.listdir(asset_dir) if os.path.isfile(os.path.join(asset_dir, f))]
        latest_file = os.path.join(asset_dir, sorted(asset_files)[-1])
        file_type = "mayaBinary"
        if latest_file.endswith('.ma'):
            file_type = 'mayaAscii'
        mc.file(latest_file, r=1, type=file_type, ignoreVersion=True, mergeNamespacesOnClash=False, namespace=asset_name)
        if mc.window('referenceAssetsWindow', exists=1):
            mc.deleteUI('referenceAssetsWindow')
        
def intestine_constraints(curve_list):
    for crv in curve_list:
        crv_pieces = crv.split('_')
        points = [crv+'.cv[0]', crv+'.cv[3]']
        for i in range(len(points)):
            parent_locator = '_'.join([crv_pieces[i*2], crv_pieces[i*2+1]])
            clstr = mc.cluster(points[i], name=locator+'cluster')
            mc.parentConstraint(parent_locator, clstr[1])
