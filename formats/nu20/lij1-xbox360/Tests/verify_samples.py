"""Local regression/visual-decoder checks. Requires Pillow; the shipped EXE does not."""
from pathlib import Path
import argparse
import hashlib, io, json, struct, subprocess, sys
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('samples', type=Path, help='Folder containing the two original samples')
parser.add_argument('--work', type=Path, default=ROOT / 'Tests' / 'RunOutput', help='New validation output directory')
parser.add_argument('--reference', type=Path, default=ROOT / 'SampleOutput', help='Independent Python DDS output directory')
parser.add_argument('--exe', type=Path, default=ROOT / 'dist' / 'LIJ1_360_Texture_Extractor.exe')
args = parser.parse_args()
EXE, INPUT, WORK = args.exe.resolve(), args.samples, args.work
WORK.mkdir(parents=True, exist_ok=False)
samples = [INPUT / 'CAPTAIN_KATANGA_360.GHG', INPUT / 'ICON_ARMYINTELMAN_A_360.GSC']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
before = {p.name: sha(p) for p in samples}
results = []

def run(paths, out, expected=0):
    completed = subprocess.run([str(EXE), '--cli', '--out', str(out), *map(str, paths)], capture_output=True, text=True)
    assert completed.returncode == expected, (completed.returncode, completed.stdout, completed.stderr)
    return completed

run(samples, WORK / 'Valid')
folders = sorted((WORK / 'Valid').glob('*_DDS*'))
assert len(folders) == 2, 'Use a fresh RunOutput directory when rerunning this test.'
decoded_count = 0
for folder in folders:
    manifest = json.loads((folder / 'Extraction.json').read_text())
    assert manifest['sourceSha256'] == before[manifest['source']]
    for p in folder.glob('*.dds'):
        data = p.read_bytes()
        assert data[:4] == b'DDS ' and len(data) > 128
        reference = args.reference / p.name
        assert data == reference.read_bytes(), f'Independent Python untile mismatch: {p.name}'
        fields = list(struct.unpack('<31I', data[4:128]))
        height, width, mips = fields[2], fields[3], fields[6]
        block_bytes = 8 if fields[20] == int.from_bytes(b'DXT1', 'little') else 16
        assert fields[0] == 124 and fields[18:20] == [32, 4] and fields[26] == 0x401008
        position = 128
        alpha_ranges = []
        for level in range(mips):
            w, h = max(1, width >> level), max(1, height >> level)
            size = max(1, (w+3)//4) * max(1, (h+3)//4) * block_bytes
            one = fields.copy()
            one[1], one[2], one[3], one[4], one[6], one[26] = 0x81007, h, w, size, 1, 0x1000
            image = Image.open(io.BytesIO(b'DDS ' + struct.pack('<31I', *one) + data[position:position+size])).convert('RGBA')
            image.load()
            assert image.size == (w, h)
            alpha_ranges.append(image.getchannel('A').getextrema())
            if level == 0:
                image.save(folder / (p.stem + '_Preview.png'))
            position += size
            decoded_count += 1
        assert position == len(data), 'DDS mip lengths do not match its header.'
        results.append(dict(file=p.name, sha256=sha(p), mipCount=mips, decodedMipLevels=mips, alphaRanges=alpha_ranges))
assert decoded_count == 38
run(samples, WORK / 'Valid')
assert len(list((WORK / 'Valid').glob('*_DDS*'))) == 4, 'Repeat extraction must use new folders.'

bad = WORK / 'Malformed'
bad.mkdir(exist_ok=True)
base = samples[1].read_bytes()
def malformed(name, change):
    data = bytearray(base)
    change(data)
    p = bad / (name + '.GSC')
    p.write_bytes(data)
    run([p], WORK / 'Rejected', expected=1)
    assert not (WORK / 'Rejected').exists(), 'Invalid input must not create output.'

malformed('UnknownFormat', lambda d: struct.pack_into('>I', d, 0x88+56, 99))
malformed('PointerOutOfBounds', lambda d: struct.pack_into('>i', d, 0x88+60, 0x7fffffff))
malformed('UnknownPadding', lambda d: d.__setitem__(0x200, 1))
malformed('UnsupportedDimensions', lambda d: struct.pack_into('>I', d, 0x88, 255))
malformed('BadAllocation', lambda d: struct.pack_into('>I', d, 0x88+68, 0x1000))
malformed('BadChunkLength', lambda d: struct.pack_into('>I', d, 20, 0xffffffff))
malformed('WrongContainer', lambda d: d.__setitem__(slice(0,4), b'NU20'))
truncated = bad / 'Truncated.GSC'
truncated.write_bytes(base[:1000])
run([truncated], WORK / 'Rejected', expected=1)
run([bad / 'UnknownFormat.GSC', samples[1]], WORK / 'MixedBatch', expected=1)
assert len(list((WORK / 'MixedBatch').rglob('*.dds'))) == 1
run([samples[1].parent / 'does-not-exist.GSC'], WORK / 'Rejected', expected=1)
assert {p.name: sha(p) for p in samples} == before, 'Source files must remain unchanged.'
report = dict(version=manifest['version'], sourceHashes=before, textures=results,
              summary=dict(sampleFiles=2, textures=4, decodedMips=decoded_count,
                           byteIdenticalToPythonReference=True, originalsUnchanged=True,
                           repeatExportDoesNotOverwrite=True, malformedCasesRejected=8,
                           missingFileRejected=True, mixedBatchContinues=True))
(WORK / 'Verification.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report['summary'], indent=2))
