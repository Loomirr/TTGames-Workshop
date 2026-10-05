"""Observed native material shader fields; game shading remains approximate."""
import struct
from pathlib import Path
from .cu3 import Reader, FormatError
from .material_flags import read_render_flags


def costume_slot(entry):
    """Authored material-role ID, not its display-table index or a name guess."""
    name = entry['name'].split(':', 1)[0].upper()
    if name.endswith('_DX11'):name=name[:-5]
    modern=entry.get('table_version') in (229,232,234,235)
    if not modern and not name.endswith('_GAME'):
        return None
    value = entry['render_flags'].get('special_id', 0)
    return value if value else None


def costume_uv_index(entry, mesh_version):
    """Observed CD print coordinates, distinct from the shared base atlas.

    LMSH1's UMTL 176 minifig arm prints use the first pair. Its other shared
    print roles use the second pair, as do the later shared DX11 GAME roles.
    This exception is layout/role gated; it does not rewrite source UVs.
    """
    name = entry['name'].split(':', 1)[0].upper()
    if name.endswith('_DX11'):
        name = name[:-5]
    role = costume_slot(entry)
    if (mesh_version == 169 and entry.get('table_version') == 176
            and (name, role) in (('LEFTARM_GAME', 24), ('RIGHTARM_GAME', 5))):
        return 0
    if name.endswith('_GAME'):
        return 1
    value = entry['fields']['uvSets'][0][1]
    return 0 if value == 0xffffffff else value


def surface_normal_binding(entry, mesh_version):
    """Verified packed surface0 layouts; other formats remain unassigned.

    The gated LMSH1/Hobbit/LB3-family layouts store the DXT5 normal in texture slot 6 and its UV
    selector in pair 4. Surface format 5 packs tangent X in alpha, Y in green
    and Z in blue. File payload validation happens before creating nodes.
    """
    fields = entry['fields']
    if (mesh_version, entry.get('table_version')) not in {
            (169, 176), (170, 191), (175, 196), (175, 202), (175, 232), (175, 234)}:
        return None
    if fields.get('surfaceMapMethod') != 1 or fields.get('surfaceMapFormat0') != 5:
        return None
    texture = entry['texture_ids'][6]
    enabled, uv = fields['uvSets'][4]
    if texture < 0 or enabled != 1 or uv not in range(16):
        return None
    return dict(texture=texture, uv=uv, packed_x_alpha=True)


def shader_prefix(data, start, version):
    if version == 163:
        # Older static NXG accessories have a separate bounded prefix. Boolean
        # meanings remain opaque; do not reuse the later flag offsets.
        r = Reader(data)
        fields = dict(version=r.get('I', start), shaderType=r.get('I', start+4),
                      lightingModel=r.get('I', start+8),
                      uvSets=[r.get('2I', start+120+i*8) for i in range(16)],
                      shaderVersion=r.get('I', start+319), GPUVendor=r.get('I', start+323),
                      colourSpace=r.get('I', start+327),
                      opaqueShaderFlags=list(data[start+248:start+319]),
                      vertAlbedo=None, canAlphaBlend=None, ignoreVertexOpacity=None)
        if fields['version'] != 2 or fields['shaderVersion'] != 4 or any(
                a not in (0, 1) or b not in (*range(16), 0xffffffff) for a,b in fields['uvSets']):
            raise FormatError('Unverified UMTL 163 static shader prefix')
        return fields, start+397
    if version == 229:
        # Older Avengers shaders retain a longer flag block. Its individual
        # boolean semantics are not established; expose only verified fields.
        r=Reader(data)
        fields=dict(version=r.get('I',start),shaderType=r.get('I',start+4),lightingModel=r.get('I',start+8),
                    numUVSets=r.get('I',start+0x88),numBones=r.get('B',start+0x99),
                    uvSets=[r.get('2I',start+0x9a+i*8) for i in range(16)],
                    shaderVersion=r.get('I',start+0x181),GPUVendor=r.get('I',start+0x185),
                    colourSpace=r.get('I',start+0x189),opaqueShaderFlags=list(r.get('103B',start+0x11a)),
                    vertAlbedo=None,canAlphaBlend=None,ignoreVertexOpacity=None)
        return fields,start+0x1ae
    modern = version in (232, 234, 235)
    if not 174 <= version <= 202 and not modern:
        raise ValueError('UMTL prefix version outside observed family')
    at, fields = start, {}
    def read(names, fmt='I'):
        nonlocal at
        for name in names.split():
            fields[name] = struct.unpack_from('>' + fmt, data, at)[0]
            at += struct.calcsize('>' + fmt)
    read('version')
    read('shaderType lightingModel', 'B' if version in (234,235) else 'I')
    read('substanceMode roughnessMode fresnelAlphaMode '
         'blendMode alphaTest alphaFadeSource surfaceMapMethod surfaceMapFormat0 surfaceMapFormat1 surfaceMapFormat2')
    if version >= 178:
        read('surfaceMapFormat3')
    read('surfaceMapFormatVTFN occlusion refraction reflection')
    if modern:
        read('opaqueModernPrefix')
    if version >= 201:
        read('baseDiffuseUsage')
    read('layerBlendDiffuse0 layerBlendDiffuse1 layerBlendDiffuse2')
    if modern:
        read('layerBlendDiffuse3')
    if version >= 200:
        read('usesDiffuseLayerColour0 usesDiffuseLayerColour1 usesDiffuseLayerColour2 usesDiffuseLayerColour3')
    elif version >= 197:
        read('usesDiffuseLayerColour0 usesDiffuseLayerColour1 usesDiffuseLayerColour2 usesDiffuseLayerColour3', 'B')
    read('layerBlendSpecular0 layerBlendSpecular1')
    if version >= 178:
        read('layerBlendSpecular2')
    read('dummySpecular layerBlendNormal0 layerBlendNormal1')
    if version >= 178:
        read('layerBlendNormal2')
    read('dummyNormal numUVSets lightmapUVSet motionBlurVertexType motionBlurPixelType')
    read('motionBlurSamples numBones','B')
    uv_count = (17 if version in (234,235) else 16) if modern else (14 if version >= 199 else 16) + (2 if version >= 178 else 0)
    fields['uvSets'] = [struct.unpack_from('>2I', data, at+i*8) for i in range(uv_count)]
    at += uv_count * 8
    if modern:
        read('opaqueModernUV')
    read('old_bitangentFlip tangentSwap water nextGenShine glow carpaint fractal fractalBump fog '
         'unlitNonSRGB hdrAlpha_diffuse hdrAlpha_envmap derivHeightMap smoothspec '
         'disableVaryingSpecular disableFresnel twoSidedLighting smoothLightmap rimLight ignoreExposure '
         'bakedSpecular semiLit refractionNearFix metallicSpecular dontReceiveShadow lateShader '
         'diffreflmaps perLayerUVScale', 'B')
    read('tintable', 'B')
    if version >= 175:
        read('generateCubeMap outputToonShaderData', 'B')
    read('disablePerPixelFade', 'B')
    read('vertAlbedo skinned fastBlend blendShape doPerspDivInVS numAlphaLayers use2DW unTransformed '
         'effectAmplitude ignoreVertexOpacity LODVerticalScale instancedLightmapping positionAccuracy '
         'uvAccuracy tangent2 vertexControlledTint zBias', 'B')
    if 175 <= version < 179:
        read('layer1VertAlbedo', 'B')
    elif version >= 179:
        read('layer1VertAlbedo layer2VertAlbedo layer3VertAlbedo','B')
    if version >= 177:
        read('disableSeparatePositionStream', 'B')
    if version >= 195:
        read('legoTerrain legoTerrainMeshType', 'B')
    if version >= 182:
        read('wind', 'B')
    read('WiiWater WiiGlass OLD_VisViewSpaceNormalZ OLD_VisTexelDensity OLD_VisShadowReceive '
         'OLD_VisComplexity OLD_VisXRayMode OLD_VisOverDrawMode greyAlbedo motionBlur UVAnimation '
         'canAlphaBlend DefunctOpaque isDecal creaseMeshMaterial TTAnimationMode culled '
         'isDeferredDecal DefunctIsGPAA requiresDiffuseAlphaMultiply isTPaged disableDynamicLighting '
         'useLayers234OnWii useWiiTintColours sRGBSupport useNormalEncodingTexture '
         'refractionIgnoreVertexNormal shadedGlow', 'B')
    if version >= 194:
        read('projectToFarPlane', 'B')
    if version >= 196:
        read('sortAfterPostEffects','B')
    read('colourRT normalRT albedoRT depthAsColourRT','B')
    read('shaderVersion GPUVendor colourSpace bakedLighting')
    for i in range(1 if modern else 5):
        read(f'lightType{i} lightModel{i}')
        read(f'softShadow{i}', 'B')
    read('sceneZAccess shadowZAccess PCFMethod rainSplashSurfaceType')
    if version in (232, 234, 235):
        # These records retain eighteen texture IDs. The previous reader
        # consumed the first as an opaque prefix, shifting every texture.
        # UVs likewise start before the guessed later flag block. Keep that
        # flag block opaque until its individual meanings are established.
        r = Reader(data)
        uv_at = 0x9a if version == 232 else 0x9c
        fields['numUVSets'] = r.get('I', start + uv_at - 18)
        fields['numBones'] = r.get('B', start + uv_at - 1)
        fields['uvSets'] = [r.get('2I', start + uv_at + i*8) for i in range(17)]
        if fields['numUVSets'] > 17 or fields['numBones'] > 4 or any(
                enabled not in (0, 1) or uv not in (*range(16), 0xffffffff)
                for enabled, uv in fields['uvSets']):
            raise FormatError('Unverified modern material UV/bone prefix')
        verified = ('version shaderType lightingModel substanceMode roughnessMode fresnelAlphaMode '
                    'blendMode alphaTest alphaFadeSource surfaceMapMethod surfaceMapFormat0 '
                    'surfaceMapFormat1 surfaceMapFormat2 surfaceMapFormat3 surfaceMapFormatVTFN '
                    'occlusion refraction reflection numUVSets numBones uvSets '
                    'shaderVersion GPUVendor colourSpace').split()
        fields = {key: fields[key] for key in verified}
        fields['opaqueShaderFlags'] = list(data[start+uv_at+17*8:start+(0x180 if version==232 else 0x182)])
        fields['vertAlbedo'] = fields['canAlphaBlend'] = fields['ignoreVertexOpacity'] = fields['zBias'] = None
    elif modern:
        read('opaqueModernTexturePrefix')
    if version == 174:
        # The verified earlier prefix is two bytes shorter. Its Boolean
        # semantics are still unresolved, so don't infer opacity/albedo flags
        # from the later shader's field names. UVs, IDs and footer are bounded.
        fields['vertAlbedo'] = fields['canAlphaBlend'] = fields['ignoreVertexOpacity'] = None
        if fields['version'] != 2 or fields['shaderVersion'] != 4 or fields['numUVSets'] > 16:
            raise FormatError('Unverified UMTL 174 shader prefix')
    return fields, at


def read_materials(path):
    data = Path(path).read_bytes()
    r = Reader(data)
    marker = data.find(b'LTMU')
    if marker < 0:
        raise FormatError('Native material table missing')
    version, count = r.get('2I', marker+4)
    if version not in (163, 174, 175, 176, 177, 183, 185, 186, 187, 191, 194, 195, 196, 198, 199, 200, 201, 202, 229, 232, 234, 235) or count > 65536:
        raise FormatError(f'Unverified native material table version/count: {version}/{count}')
    start = marker+12
    if version < 190:
        if r.get('I', start) != count:
            raise FormatError('Native material counts disagree')
        start += 4
    if count == 0:
        return {'version':version, 'materials':[]}
    limit = data.find(b'TDML', start)
    if limit < 0:
        raise FormatError('Native material boundary missing')
    # Names have a version-specific position inside a fixed shader prefix.
    # Require a unique position and exactly the declared number of records.
    lengths = []
    for offset in range(0x300, min(0x600, limit-start-2)):
        length = r.get('H', start+offset)
        raw = data[start+offset+2:start+offset+2+length]
        if 5 <= length < 256 and len(raw)==length and raw.endswith(b'\0') and all(32 <= c <= 126 for c in raw[:-1]):
            lengths.append(offset)
    if len(lengths) != 1:
        raise FormatError('Ambiguous native material name layout')
    name_offset = lengths[0]
    entries = []
    cursor = start
    while cursor < limit:
        candidate = data.find(b'\0\0\0\2', cursor, limit)
        if candidate < 0:
            break
        cursor = candidate+4
        if candidate+name_offset+2 > limit:
            continue
        length = r.get('H', candidate+name_offset)
        end = candidate+name_offset+2+length
        raw = data[candidate+name_offset+2:end]
        if not 1 <= length < 512 or end > limit or not raw.endswith(b'\0') or any(c<32 or c>126 for c in raw[:-1]):
            continue
        fields, texture_at = shader_prefix(data, candidate, version)
        modern = version in (229, 232, 234, 235)
        slots = 17 if version == 229 else 18
        ids = list(r.get(f'{slots}i', texture_at))
        if any(i < -1 or i > 65536 for i in ids):
            continue
        if texture_at+slots*4 > candidate+name_offset:
            raise FormatError('Overlapping native material fields')
        formats = []
        if modern:
            format_count = r.get('I', texture_at+slots*4)
            if format_count != 17:
                raise FormatError('Native material texture-format count differs from slots')
            formats = list(r.get(f'{format_count}B', texture_at+slots*4+4))
            if fields['version'] != 2 or fields['shaderVersion'] != 4 or fields['numUVSets'] > 17:
                raise FormatError('Unverified modern shader prefix values')
        entries.append({'index':len(entries), 'offset':candidate, 'table_version':version, 'name':raw[:-1].decode('ascii'),
                        'texture_ids':ids, 'texture_formats':formats, 'fields':fields})
    if len(entries) != count or entries[0]['offset'] != start:
        raise FormatError('Native material record count disagrees with table')
    flags = read_render_flags(data, entries, version)
    for entry, footer in zip(entries, flags):
        entry['render_flags'] = footer['flags']
    return {'version':version, 'materials':entries}
