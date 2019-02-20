import maya.cmds as mc
import os

def list_assets(job_name):
    assets_dir = os.path.join('/mnt', 'ol03', 'Projects', job_name, '_shared', '_assets')
    asset_dict = {'Character': {'dir': '', 'assets': []},
                  'Environment': {'dir': '', 'assets': []},
                  'Prop': {'dir': '', 'assets': []},
                  'Vehicle': {'dir': '', 'assets': []}}
    for asset_type in asset_dict.keys():
        asset_dict[asset_type]['dir'] = os.path.join('/mnt', 'ol03', 'Projects', job_name, '_shared', '_assets', asset_type)
        asset_dict[asset_type]['assets'] = os.listdir(asset_dict[asset_type]['dir'])
    return asset_dict


def reference_asset(asset_name, asset_type='Prop'):
    job_name = mc.file(query=True, sceneName=True).split('/')[4]
    asset_dict = list_assets(job_name)
    if asset_name in asset_dict[asset_type]['assets']:
        asset_dir = os.path.join(asset_dict[asset_type]['dir'], asset_name, 'work', 'maya', 'scenes')
        asset_files = [f for f in os.listdir(asset_dir) if os.path.isfile(os.path.join(asset_dir, f))]
        latest_file = os.path.join(asset_dir, sorted(asset_files)[-1])
        mc.file(latest_file, r=1, type="mayaBinary", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=asset_name)
