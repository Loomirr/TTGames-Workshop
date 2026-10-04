"""Verify the five reported GSC samples against independent DDS references.

Requires Pillow, the user-supplied GSC folder, and previously verified reference
DDS files. Game files and reference exports are not bundled.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import xml.etree.ElementTree as ET
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('samples', type=Path)
parser.add_argument('--work', required=True, type=Path, help='New validation directory')
parser.add_argument('--reference', required=True, type=Path)
parser.add_argument('--exe', type=Path, default=ROOT/'dist/LIJ1_360_Texture_Extractor.exe')
args = parser.parse_args()
args.work.mkdir(parents=True, exist_ok=False)
expected = {
    'ICON_COLONEL_DIETRITCH_360.GSC': [(32,32,'DXT1',1),(256,256,'DXT5',9)],
    'ICON_ENEMY_GUARD_360.GSC': [(256,256,'DXT5',9)],
    'ICON_ENEMY_PILOT_360.GSC': [(256,256,'DXT5',9)],
    'ICON_THUGGEE_SLAVEDRIVERCHIEF_360.GSC': [(32,32,'DXT1',1),(256,256,'DXT5',9)],
    'INDIANAJONES_ICON_360.GSC': [(64,64,'DXT5',7)],
}
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
sources = [args.samples/name for name in expected]
before = {p.name:sha(p) for p in sources}
out = args.work/'Exports'
def run(inputs, destination, code=0):
    result = subprocess.run([str(args.exe.resolve()), '--cli', '--out', str(destination.resolve()),
                             *map(str,inputs)],capture_output=True,text=True)
    assert result.returncode == code, (result.returncode,result.stdout,result.stderr)
    return result

result = run(sources,out)
assert result.stdout.count('WARNING:') == 1, result.stdout
textures = []
decoded = 0
for p in sources:
    folder = out/(p.stem+'_DDS')
    manifest = json.loads((folder/'Extraction.json').read_text())
    assert manifest['sourceSha256'] == before[p.name] and manifest['version'] == ET.parse(ROOT/'Source/LIJ1TextureExtractor.csproj').findtext('./PropertyGroup/Version')
    assert bool(manifest['warnings']) == (p.name == 'INDIANAJONES_ICON_360.GSC')
    assert len(manifest['outputs']) == len(expected[p.name])
    for item, (w,h,fmt,mips) in zip(manifest['outputs'],expected[p.name]):
        dds = folder/item['file']
        data = dds.read_bytes()
        assert data == (args.reference/dds.name).read_bytes(), dds.name
        assert sha(dds) == item['sha256']
        fields = list(struct.unpack('<31I',data[4:128]))
        assert data[:4] == b'DDS ' and (fields[3],fields[2],fields[6]) == (w,h,mips)
        assert fields[20] == int.from_bytes(fmt.encode(),'little')
        block = 8 if fmt == 'DXT1' else 16
        position = 128
        for level in range(mips):
            mw,mh = max(1,w>>level),max(1,h>>level)
            count = max(1,(mw+3)//4)*max(1,(mh+3)//4)*block
            one = fields.copy()
            one[1],one[2],one[3],one[4],one[6],one[26] = 0x81007,mh,mw,count,1,0x1000
            image = Image.open(io.BytesIO(b'DDS '+struct.pack('<31I',*one)+data[position:position+count])).convert('RGBA')
            image.load()
            assert image.size == (mw,mh)
            if level == 0: image.save(folder/(dds.stem+'_Preview.png'))
            position += count
            decoded += 1
        assert position == len(data)
        textures.append(dict(file=dds.name,sha256=sha(dds),mips=mips,
                             profile=item['texture']['DescriptorProfile']))
assert decoded == 45 and len(textures) == 7
run(sources,out)
assert len(list(out.glob('*_DDS*'))) == 10

# Test rejection on real duplicate and recovered descriptors, and batch isolation.
bad = args.work/'Malformed'
bad.mkdir()
colonel = bytearray(sources[0].read_bytes())
struct.pack_into('>I',colonel,0x88+140,0x7fffffff)
invalid_secondary = bad/'InvalidSecondary.GSC'
invalid_secondary.write_bytes(colonel)
legacy = bytearray(sources[-1].read_bytes())
struct.pack_into('>I',legacy,0x88+144,6)
invalid_legacy = bad/'InvalidLegacy.GSC'
invalid_legacy.write_bytes(legacy)
for p in (invalid_secondary,invalid_legacy):
    run([p],args.work/'Rejected',1)
    assert not (args.work/'Rejected').exists()
run([invalid_legacy,sources[1]],args.work/'Mixed',1)
assert len(list((args.work/'Mixed').rglob('*.dds'))) == 1
assert {p.name:sha(p) for p in sources} == before
report = dict(sourceHashes=before,textures=textures,summary=dict(
    sampleFiles=5,textures=7,decodedMips=decoded,byteIdenticalToReference=True,
    originalsUnchanged=True,repeatDoesNotOverwrite=True,recoveryWarningRecorded=True,
    inconsistentSecondaryRejected=True,inconsistentLegacyRejected=True,mixedBatchContinues=True))
(args.work/'Verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report['summary'],indent=2))
