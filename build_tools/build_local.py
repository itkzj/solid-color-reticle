# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a local test package from the matching installed game client."""
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
GAME_VERSION = '2.4.2.0'
MOD_VERSION = '4.6.1'
MODS = f'mods/{GAME_VERSION}/'
# ponytail: pinned to the tested client build, verify linkages before updating.
HUD_TAG = {'arcade': (2, 175, 'b01afd2d80f050c5ea557088a0cad88c00f3fd4753ee6806b9d6e1bc96b2838d'),
           'sniper': (4, 249, '4a7323c746bd0657951b5381035d87625aacf922d328e45095fa656c59a3e6be'),
           'strategic': (3, 61, '1174e9997e83c47c820fe3a13ea99ad52abee71dd6a8c93e06e40d6068bd1734')}
CONTROLS_SHA = 'a0e318c7ee469629e86c6b72282fae5d1423c28e0f3bfbd589feaaf7e65c4565'
PYTHON = {'mod_white_blade': 'res/scripts/client/gui/mods/mod_white_blade.pyc',
          'white_blade_minimum': 'res/scripts/client/white_blade_minimum.pyc',
          'white_blade_geometry': 'res/scripts/client/white_blade_geometry.pyc',
          'white_blade_penetration': 'res/scripts/client/white_blade_penetration.pyc'}


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
        require(archive.namelist() == list(files)
                and all(archive.read(name) == data for name, data in files.items()),
                'ZIP readback mismatch')
    return output


def read_stock(packages, part, filename, expected):
    member = 'gui/flash/' + filename
    with ZipFile(packages / f'gui-part{part}.pkg') as archive:
        data = archive.read(member)
    require(sha256(data).hexdigest() == expected, 'Unsupported client SWF: ' + member)
    return data


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


def insert_adapter(original, donor, bindings, aliases=None):
    header, tags = read_swf(original)
    _, donor_tags = read_swf(donor)
    require(original[3] == donor[3] == 17, 'SWF version mismatch')
    (abc_index,) = [index for index, tag in enumerate(tags) if tag[0] == 82]
    (symbol_index,) = [index for index, tag in enumerate(tags) if tag[0] == 76]
    require(abc_index < symbol_index, 'Official ABC must precede SymbolClass')
    table = tags[symbol_index][1]
    count, = struct.unpack_from('<H', table)
    cursor = 2
    symbols = {}
    for _ in range(count):
        symbol_id, = struct.unpack_from('<H', table, cursor)
        end = table.index(bytes(1), cursor + 2)
        symbols[table[cursor + 2:end].decode('utf-8')] = symbol_id
        cursor = end + 1
    require(cursor == len(table) and len(symbols) == count
            and all(symbols.get(name) == symbol_id for name, (symbol_id, _) in bindings.items()),
            'Unexpected official SWF binding')
    native = rename_strings(tags[abc_index][1],
                            {name.encode(): base.encode() for name, (_, base) in bindings.items()})
    donor_abc, = [payload for code, payload, _ in donor_tags if code == 82]
    if aliases:
        donor_abc = rename_strings(donor_abc, aliases)
    output = [raw for _, _, raw in tags]
    output[abc_index] = abc_tag(native)
    output.insert(symbol_index, abc_tag(donor_abc))
    body = header + b''.join(output)
    data = (original[:4] + struct.pack('<I', len(body) + 8)
            + (zlib.compress(body, 9) if original[:3] == b'CWS' else body))
    checked_header, checked = read_swf(data)
    require(checked_header == header and [raw for _, _, raw in checked] == output,
            'SWF tag readback mismatch')
    return data


def abc_tag(payload):
    return struct.pack('<HI', (82 << 6) | 63, len(payload)) + payload


def stub_source(mode):
    title = mode.title()
    parent = f'Crosshair{title}'
    return (f'package {{ import net.wg.gui.components.crosshairPanel.{parent};\n'
            f'public class WhiteBlade{title}Base extends {parent} {{}} }}\n')


def compile_adapter(tools, work, main, stubs, adapters):
    java = tools / 'jre/jdk-21.0.13+9-jre/bin/java.exe'
    flex = tools / 'flex'
    external = [tools / 'playerglobal32_0.swc', tools / 'extlib/battleCrosshairsApp.swc']
    common = ['+flexlib=' + str(flex / 'frameworks'), '-load-config=',
              '-compiler.library-path=', '-compiler.theme=', '-debug=false', '-optimize=true',
              '-compiler.actionscript-file-encoding=UTF-8', '-target-player=11.4', '-swf-version=17']
    work.mkdir()
    for name, text in {**stubs, **adapters}.items():
        (work / (name + '.as')).write_text(text, encoding='utf-8')
    wrapper = work / (main + '.as')
    stub, donor = work / 'external.swc', work / 'donor.swf'

    def run(tool, libraries, *args):
        subprocess.run([str(java), '-Dfile.encoding=UTF-8', '-jar', str(flex / 'lib' / f'{tool}.jar'),
                        *common, '-compiler.external-library-path=' + ','.join(map(str, libraries)),
                        *args], check=True)

    run('compc', external, '-compiler.source-path=' + str(work), '-include-classes=' + ','.join(stubs),
        '-output=' + str(stub))
    run('mxmlc', [stub, *external], '-compiler.source-path=' + str(AS3), '-compiler.source-path+=' + str(work),
        '-output=' + str(donor), str(wrapper))
    return donor.read_bytes()


def build(packages, tools, output):
    require(not output.exists(), 'Output already exists')
    controls_filename = 'crosshairControls.swf'
    stock_controls = read_stock(packages, 1, controls_filename, CONTROLS_SHA)
    files = {}
    render = runpy.run_path(str(AS3 / 'adapter.py'))['render']
    with TemporaryDirectory(prefix='solid-color-reticle-', dir=output.parent) as temp:
        scratch = Path(temp)
        for mode, (part, symbol_id, fingerprint) in HUD_TAG.items():
            filename = mode + 'Crosshair.swf'
            title = mode.title()
            name, base = f'Crosshair{title}UI', f'WhiteBlade{title}Base'
            stock = read_stock(packages, part, filename, fingerprint)
            donor = compile_adapter(tools, scratch / mode, name, {base: stub_source(mode)}, {name: render(mode)})
            aliases = None
            if mode == 'strategic':
                aliases = {b'WhiteBladeHUD': b'WhiteBladeStrategicHUD',
                           b'WhiteBladeMarkers': b'WhiteBladeStrategicMarkers'}
            files[FLASH + filename] = insert_adapter(stock, donor, {name: (symbol_id, base)}, aliases)
        controls = runpy.run_path(str(AS3 / 'controls.py'))
        links = controls['LINKAGES']
        bases = {name: controls['base'](name) for name in links}
        adapters = {name: controls['render'](name) for name in links}
        adapters['SolidReticleLinkages'] = (
            'package { import flash.display.Sprite; public class SolidReticleLinkages extends Sprite {'
            'public function SolidReticleLinkages() {} '
            'private var linkages:Array = [' + ','.join(links) + ']; }}')
        donor = compile_adapter(tools, scratch / 'controls', 'SolidReticleLinkages',
                                {bases[name]: controls['stub'](name) for name in links}, adapters)
        files[FLASH + controls_filename] = insert_adapter(
            stock_controls, donor, {name: (link[0], bases[name]) for name, link in links.items()})
        for module, member in PYTHON.items():
            pyc = scratch / (module + '.pyc')
            subprocess.run([str(tools / 'python27/python.exe'), '-B', '-c',
                            'import py_compile,sys; py_compile.compile(sys.argv[1],sys.argv[2],sys.argv[3],doraise=True)',
                            str(CLIENT / (module + '.py')), str(pyc), member[:-1]], check=True)
            files[member] = pyc.read_bytes()
            require(files[member][:4] == b'\x03\xf3\x0d\x0a', 'Expected CPython 2.7 bytecode')
    files['meta.xml'] = f'''<root>
  <id>local.solid_color_reticle</id>
  <version>{MOD_VERSION}</version>
  <name>纯色瞄准</name>
  <description>Solid Color Reticle. World of Tanks CN {GAME_VERSION}.</description>
</root>
'''.encode('utf-8')
    package = archive_bytes({f'{MODS}solid_color_reticle_{MOD_VERSION}.wotmod': archive_bytes(files)})
    with output.open('xb') as stream:
        stream.write(package)
    require(output.read_bytes() == package, 'Output readback mismatch')
    print(output, sha256(package).hexdigest())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packages', type=Path, help='Installed client res/packages directory')
    parser.add_argument('tools', type=Path, help='Existing local Java, Flex, SDK and Python 2.7 tools')
    parser.add_argument('output', type=Path, help='New private test ZIP outside the source repository')
    args = parser.parse_args()
    build(args.packages.resolve(), args.tools.resolve(), args.output.resolve())
