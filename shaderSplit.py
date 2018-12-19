

def connect2DToFileTexture(twod_texture, file_texture, file_texture_path):
    attrs = ['.coverage', '.translateFrame', '.rotateFrame', '.mirrorU', '.mirrorV',
             '.stagger', '.wrapU', '.wrapV', '.repeatUV', '.offset', '.rotateUV',
             '.noiseUV', '.vertexUvOne', '.vertexUvTwo', '.vertexUvThree', '.vertexCameraOne']
    for attr in attrs:
        mc.connectAttr(twod_texture+attr, file_texture+attr, force=True)
    mc.setAttr(file_texture+'.fileTextureName', file_texture_path, type='string')
    mc.connectAttr(twod_texture+'.outUV', file_texture+'.uv', force=True)
    mc.connectAttr(twod_texture+'.outUvFilterSize', file_texture+'.uvFilterSize', force=True)


def shaderSplit():
    # construct dictionary sorted by texture path of shaders and members (faces or transform)
    data_dict = {}
    file_textures = mc.ls(type='file')
    for file_texture in file_textures:
        texture_path = str(mc.getAttr(file_texture+'.fileTextureName'))
        shaders = [f.split('.')[0] for f in mc.listConnections(file_texture, plugs=1) if f.endswith('.color')]
        if shaders:
            shading_groups = [f.split('.')[0] for f in mc.listConnections(shaders[0], plugs=1) if f.endswith('.surfaceShader')]
            if shading_groups:
                members = mc.sets(shading_groups[0], query=True)
                if texture_path in data_dict.keys() and shading_groups and members:
                    data_dict[texture_path]['ShadingGroups'].append(str(shading_groups[0]))
                    data_dict[texture_path]['Members'] += members
                else:
                    if members:
                        data_dict[texture_path] = {'ShadingGroups': [str(shading_groups[0])],
                                                   'Members': members}
    # generate clean shader per texture path
    # if faces, duplicate geometry, extract faces, delete the rest and assign clean shader
    # else, just assign clean shader
    shader_num = 0
    for texture_path, sub_dict in data_dict.iteritems():
        # construct clean shader
        shader_name = 'shader_'+str(shader_num).zfill(2)
        shading_group = shader_name+'SG'
        mc.shadingNode('phong', name=shader_name, asShader=1)
        mc.sets(renderable=True, noSurfaceShader=True, empty=True, name=shading_group)
        mc.connectAttr(shader_name+'.outColor', shading_group+'.surfaceShader', force=1)
        twod_texture = mc.shadingNode('place2dTexture', asUtility=True, name=shader_name+'_2d')
        file_texture = mc.shadingNode('file', asTexture=True, isColorManaged=True, name=shader_name+'_fileTexture')
        connect2DToFileTexture(twod_texture, file_texture, texture_path)
        mc.connectAttr(file_texture+'.outColor', shader_name+'.color', force=True)
        shader_num += 1
        face_dict = {}
        for i in range(len(sub_dict['Members'])):
            # face assignments
            if '.f[' in sub_dict['Members'][i]:
                geo, faces = sub_dict['Members'][i].split('.')
                dupe = mc.duplicate(geo, name='temp')
                mc.polyChipOff(dupe[0]+'.'+faces, constructionHistory=False, keepFacesTogether=True)
                pieces = mc.polySeparate([dupe[0]+'.'+faces, dupe[0]], removeShells=1, constructionHistory=False)
                mc.parent(pieces[1], world=True)
                temp_face_geo = geo+str(i).zfill(2)+'_'+shader_name
                mc.rename(pieces[1], temp_face_geo)
                mc.delete('temp')
                if geo in face_dict.keys():
                    face_dict[geo].append(temp_face_geo)
                else:
                    face_dict[geo] = [temp_face_geo]
            else:
                face_dict[sub_dict['Members'][i]] = [sub_dict['Members'][i]]
        for geo, temp_list in face_dict.iteritems():
            new_geo = temp_list[0]
            if len(temp_list) > 1:
                new_geo = geo+'_'+shader_name
                # hide original, merge split geos, merge vertices, smooth normals, delete history
                mc.hide(geo)
                mc.polyUnite(temp_list, constructionHistory=False, mergeUVSets=True, name=new_geo)
                mc.polyMergeVertex(new_geo, distance=0.01, alwaysMergeTwoVertices=True, constructionHistory=False)
                mc.polySoftEdge(new_geo, angle=180, constructionHistory=False)
                mc.delete(new_geo, constructionHistory=True)
            # assign clean shader
            print 'Assigning', shading_group, 'to', new_geo
            mc.sets(new_geo, edit=1, forceElement=shading_group)
    mc.select(deselect=True)
