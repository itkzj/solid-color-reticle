# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a private test package against the user's exact, accepted V19 archive."""
import argparse
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import runpy
import struct
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_STORED
import zlib

ROOT = Path(__file__).resolve().parents[1]
AS3 = ROOT / 'src/as3'
CLIENT = ROOT / 'src/client'
FLASH = 'res/gui/flash/'
MODS = 'mods/2.4.1.1/'
BASELINE_MOD = MODS + 'whiteblade.crosshair_1.18.0.wotmod'
BASELINE_SHA = '9a755f0117278b56aa98eb459bb9a9866906993840dd877bb6f141c9e0b39e4e'
# ponytail: exact V19 only, re-audit linkage and placements for another baseline.
HUD_TAG = {'arcade': (69, 17, '11.4'), 'sniper': (107, 17, '11.4'),
           'strategic': (87, 15, '11.0')}
PYTHON = {'mod_white_blade': 'res/scripts/client/gui/mods/mod_white_blade.pyc',
          'white_blade_geometry': 'res/scripts/client/white_blade_geometry.pyc'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def archive_bytes(files):
    raw = BytesIO()
    with ZipFile(raw, 'w', compression=ZIP_STORED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    output = raw.getvalue()
    with ZipFile(BytesIO(output)) as archive:
        require(archive.testzip() is None and archive.namelist() == list(files)
                and all(archive.read(name) == data for name, data in files.items()),
                'ZIP readback mismatch')
    return output


def read_baseline(path):
    raw = path.read_bytes()
    require(sha256(raw).hexdigest() == BASELINE_SHA, 'Expected the accepted V19 ZIP (SHA-256 mismatch)')
    with ZipFile(BytesIO(raw)) as archive:
        mod = archive.read(BASELINE_MOD)
    with ZipFile(BytesIO(mod)) as archive:
        expected = {'meta.xml', FLASH + 'crosshairControls.swf', *PYTHON.values(),
                    *(FLASH + mode + 'Crosshair.swf' for mode in HUD_TAG)}
        require(len(archive.namelist()) == len(expected) and set(archive.namelist()) == expected,
                'Unexpected V19 members')
        return {name: archive.read(name) for name in archive.namelist()}


def read_swf(data):
    require(len(data) >= 9 and data[:3] in (b'FWS', b'CWS'), 'Expected FWS or CWS')
    length, = struct.unpack_from('<I', data, 4)
    require(length >= 9, 'Invalid SWF length')
    if data[:3] == b'CWS':
        stream = zlib.decompressobj()
        body = stream.decompress(data[8:], length - 7)
        require(stream.eof and not stream.unused_data and not stream.unconsumed_tail, 'Invalid CWS stream')
    else:
        body = data[8:]
    require(len(body) + 8 == length, 'SWF length mismatch')
    start = (5 + 4 * (body[0] >> 3) + 7) // 8 + 4
    tags = []
    pos = start
    while pos + 2 <= len(body):
        begin = pos
        word, = struct.unpack_from('<H', body, pos)
        pos += 2
        code, size = word >> 6, word & 63
        if size == 63:
            require(pos + 4 <= len(body), 'Truncated SWF tag header')
            size, = struct.unpack_from('<I', body, pos)
            pos += 4
        end = pos + size
        require(end <= len(body), 'Truncated SWF tag')
        tags.append((code, body[pos:end], body[begin:end]))
        if code == 0:
            require(size == 0 and end == len(body), 'Invalid SWF End tag')
            return body[:start], tags
        pos = end
    raise ValueError('Missing SWF End tag')


def uint_at(data, pos):
    value = 0
    for shift in range(0, 35, 7):
        require(pos < len(data), 'Truncated ABC integer')
        byte = data[pos]
        value |= (byte & 127) << shift
        pos += 1
        if byte < 128:
            require(value < 1 << 32, 'ABC integer overflow')
            return value, pos
    raise ValueError('Invalid ABC integer')


def rename_strings(abc, names):
    """Replace whole UTF-8 constant-pool entries, leaving all indices intact."""
    pos = abc.index(b'\0', 4) + 1
    require(abc[pos:pos + 4] == b'\x10\x00\x2e\x00', 'Unexpected ABC version')
    pos += 4
    for _ in range(2):
        count, pos = uint_at(abc, pos)
        for _ in range(max(0, count - 1)):
            _, pos = uint_at(abc, pos)
    count, pos = uint_at(abc, pos)
    count, pos = uint_at(abc, pos + 8 * max(0, count - 1))
    chunks = [abc[:pos]]
    seen = set()
    for _ in range(max(0, count - 1)):
        begin = pos
        size, pos = uint_at(abc, pos)
        end = pos + size
        require(end <= len(abc), 'Truncated ABC string')
        name = abc[pos:end]
        require(name not in names.values(), 'ABC already contains the replacement name')
        if name in names:
            require(name not in seen and len(names[name]) < 128, 'Invalid ABC name replacement')
            seen.add(name)
            chunks.append(bytes([len(names[name])]) + names[name])
        else:
            chunks.append(abc[begin:end])
        pos = end
    require(seen == names.keys(), 'Missing generated ABC names')
    return b''.join(chunks) + abc[pos:]


def replace_hud(original, donor, mode):
    index, version, _ = HUD_TAG[mode]
    header, tags = read_swf(original)
    _, donor_tags = read_swf(donor)
    require(original[3] == donor[3] == version, 'SWF version mismatch')
    require(len(tags) > index + 1 and tags[index][0] == 82
            and tags[index][1][4:11] == b'frame1\0'
            and tags[index + 1][0] == 76, 'Unexpected V19 HUD location')
    abc, = [payload for code, payload, _ in donor_tags if code == 82]
    if mode == 'strategic':
        abc = rename_strings(abc, {b'WhiteBladeHUD': b'WhiteBladeStrategicHUD',
                                   b'WhiteBladeMarkers': b'WhiteBladeStrategicMarkers'})
    output = [raw for _, _, raw in tags]
    output[index] = struct.pack('<HI', (82 << 6) | 63, len(abc)) + abc
    body = header + b''.join(output)
    data = (original[:4] + struct.pack('<I', len(body) + 8)
            + (zlib.compress(body, 9) if original[:3] == b'CWS' else body))
    checked_header, checked = read_swf(data)
    require(checked_header == header and [raw for _, _, raw in checked] == output,
            'SWF tag readback mismatch')
    return data


def stub_source(mode):
    title = mode.title()
    base = f'WhiteBlade{title}Base'
    common = ('public function as_setReloadingBaseTime(v:Number):void {}\n'
              'public function as_setAmmoQuantity(v:int,low:Boolean):void {}\n'
              'public function as_setShellParams(speed:Number,gravity:Number,name:String,splash:Number,type:Number,penetration:Number,damage:Number):void {}\n')
    if mode == 'strategic':
        extra = ('public function as_updateHeight(v:Number):void {}\n'
                 'public function as_setVehicleParams(vehicle:String,gun:String,maxHP:Number):* {return null;}\n')
    else:
        extra = ('public function as_updateHealth(v:Number):void {}\n'
                 'public function as_setVehicleParams(vehicle:String,gun:String,maxHP:Number,range:Number=400):void {}\n')
    return (f'package {{ import net.wg.gui.components.crosshairPanel.Crosshair{title};\n'
            f'public class {base} extends Crosshair{title} {{\n' + common + extra + '}}\n')


def compile_hud(mode, tools, scratch, render):
    base = f'WhiteBlade{mode.title()}Base'
    java = tools / 'jre/jdk-21.0.13+9-jre/bin/java.exe'
    flex = tools / 'flex'
    external = [tools / 'playerglobal32_0.swc', tools / 'extlib/battleCrosshairsApp.swc']
    version, target = HUD_TAG[mode][1:]
    common = ['+flexlib=' + str(flex / 'frameworks'), '-load-config=',
              '-compiler.library-path=', '-compiler.theme=', '-debug=false', '-optimize=true',
              '-compiler.actionscript-file-encoding=UTF-8', '-target-player=' + target,
              '-swf-version=' + str(version)]
    work = scratch / mode
    work.mkdir()
    (work / (base + '.as')).write_text(stub_source(mode), encoding='utf-8')
    wrapper = work / f'Crosshair{mode.title()}UI.as'
    wrapper.write_text(render(mode), encoding='utf-8')
    stub, donor = work / 'external.swc', work / 'donor.swf'

    def run(tool, libraries, *args):
        subprocess.run([str(java), '-Dfile.encoding=UTF-8', '-jar', str(flex / 'lib' / f'{tool}.jar'),
                        *common, '-compiler.external-library-path=' + ','.join(map(str, libraries)),
                        *args], check=True)

    run('compc', external, '-compiler.source-path=' + str(work), '-include-classes=' + base,
        '-output=' + str(stub))
    run('mxmlc', [stub, *external], '-compiler.source-path=' + str(AS3),
        '-output=' + str(donor), str(wrapper))
    return donor.read_bytes()


def build(baseline, tools, output):
    files = read_baseline(baseline)
    require(not output.exists(), 'Output already exists')
    render = runpy.run_path(str(AS3 / 'adapter.py'))['render']
    with TemporaryDirectory(prefix='solid-color-reticle-', dir=output.parent) as temp:
        scratch = Path(temp)
        for mode in HUD_TAG:
            name = FLASH + mode + 'Crosshair.swf'
            files[name] = replace_hud(files[name], compile_hud(mode, tools, scratch, render), mode)
        for module, member in PYTHON.items():
            pyc = scratch / (module + '.pyc')
            subprocess.run([str(tools / 'python27/python.exe'), '-B', '-c',
                            'import py_compile,sys; py_compile.compile(sys.argv[1],sys.argv[2],sys.argv[3],doraise=True)',
                            str(CLIENT / (module + '.py')), str(pyc), member[:-1]], check=True)
            files[member] = pyc.read_bytes()
            require(files[member][:4] == b'\x03\xf3\x0d\x0a', 'Expected CPython 2.7 bytecode')
    files['meta.xml'] = '''<root>
  <id>local.solid_color_reticle</id>
  <version>1.0</version>
  <name>纯色瞄准</name>
  <description>Solid Color Reticle V1.0. World of Tanks CN 2.4.1.1.</description>
</root>
'''.encode('utf-8')
    package = archive_bytes({MODS + 'solid_color_reticle_1.0.wotmod': archive_bytes(files)})
    with output.open('xb') as stream:
        stream.write(package)
    require(output.read_bytes() == package, 'Output readback mismatch')
    print(output, sha256(package).hexdigest())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path, help='Accepted V19 ZIP already on this machine')
    parser.add_argument('tools', type=Path, help='Existing local Java, Flex, SDK and Python 2.7 tools')
    parser.add_argument('output', type=Path, help='New private test ZIP outside the source repository')
    args = parser.parse_args()
    build(args.baseline.resolve(), args.tools.resolve(), args.output.resolve())
