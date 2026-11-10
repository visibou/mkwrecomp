"""MKW Recompiler: build MKW for Windows from your own dump, in one command.

  python build_mkw.py "D:/path/to/your/MKW dump" [--out FOLDER] [--jobs N] [--check] [--replace]

The dump folder holds exefs/ and romfs/ (or base/exefs and base/romfs), provided by you. Nothing from the game is
included with this tool: it builds the game on your PC from your copy, and what it makes must stay on your PC.

Steps (each one is skipped when its result is already there, so it can be run again after a stop):
  1. Your dump: the exact version this recompiler supports is checked.
  2. The tools and the free disk space.
  3. The game's code: translated to C and compiled with GCC (30-40 minutes).
  4. The shaders: found in the game's files and translated for Vulkan (about 5 minutes).
  5. The textures: every one converted once for your GPU, so new places do not stutter (about 5 minutes, ~21 GB).
  6. The settings: MKW's defaults, keeping any you already changed.
This file holds what is particular to MKW (its version, name, hints and defaults); the steps are Switch2Recomp's general tools."""
import argparse, os, re, shutil, struct, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))   # the MKW Recompiler: this file, MKW's hints and default settings


def find_s2r():
    """Switch2Recomp: S2R_ROOT, else the Switch2Recomp folder beside this file (the git submodule)."""
    for d in (os.environ.get('S2R_ROOT'), os.path.join(HERE, 'Switch2Recomp')):
        if d and os.path.isfile(os.path.join(d, 'switchrecomp.py')): return os.path.abspath(d)
    return None


ROOT = find_s2r()
if not ROOT:
    sys.exit('Switch2Recomp is missing. In this folder run:  git submodule update --init  (or set S2R_ROOT to a Switch2Recomp folder).')
TOOLS = os.path.join(ROOT, 'tools')
sys.path.insert(0, TOOLS)
import s2r_paths as P

# What this recompiler supports: MKW, the base game (no update)
GAME = 'MKW'   # the name of what is built: MKW.exe, MKW_code.dll, MKW.ini, MKW.hints, MKW.patches.py
PROGRAM_ID = '0400C3F00006E000'
BUILD_ID = '9E244438C3D8EF1C'
VERSION_NAME = 'version 1.0.0 (the base game, no update)'
NEED_GB = dict(code=5, shaders=6, textures=22, data=23)   # free space each step needs on the output drive, measured for MKW with room to spare (code 1.5 GB, shaders 4.3 GB, textures 20.8 GB); the drive also keeps 20 GB free


class Stop(Exception):
    pass


def say(msg):
    print(msg, flush=True)


def find_dump(path):
    """The folder holding exefs/ and romfs/: the given one, or its base/ (as dump tools lay games out)."""
    path = os.path.abspath(path)
    for d in (path, os.path.join(path, 'base')):
        if os.path.isfile(os.path.join(d, 'exefs', 'main')): return d
    if os.path.isfile(os.path.join(path, 'main')) and os.path.basename(path).lower() == 'exefs': return os.path.dirname(path)
    raise Stop('No game found in %s. Point to the folder with the decrypted files you provide: it holds exefs\\ (with "main" in it) and romfs\\.' % path)


def check_version(dump):
    """The program ID from main.npdm and the build ID of main (an NSO): this recompiler is made for one exact build."""
    npdm = os.path.join(dump, 'exefs', 'main.npdm')
    try:
        n = open(npdm, 'rb').read(); i = n.find(b'ACI0')
        pid = '%016X' % struct.unpack_from('<Q', n, i + 0x10)[0] if i >= 0 else ''
        with open(os.path.join(dump, 'exefs', 'main'), 'rb') as f: h = f.read(0x60)
        bid = h[0x40:0x48].hex().upper() if h[:4] == b'NSO0' else ''
    except OSError as e:
        raise Stop('Cannot read the game\'s code files in %s: %s' % (os.path.join(dump, 'exefs'), e))
    if pid != PROGRAM_ID:
        raise Stop('This is not MKW (program ID %s, expected %s). This recompiler builds MKW only.' % (pid or 'unknown', PROGRAM_ID))
    if bid != BUILD_ID:
        raise Stop('This MKW is a different version (build %s). This recompiler supports %s, build %s. '
                   'If your dump includes an update, point to the base game alone.' % (bid or 'unknown', VERSION_NAME, BUILD_ID))
    return pid, bid


def free_gb(path):
    while path and not os.path.exists(path): path = os.path.dirname(path)
    try: return shutil.disk_usage(path).free / 1e9
    except OSError: return -1


def step(cmd, log_name, out, env=None, cwd=None):
    """Runs one of Switch2Recomp's tools, showing its output and keeping it in the build log."""
    log = open(os.path.join(out, 'build_mkw.log'), 'a', encoding='utf-8', errors='replace')
    log.write('\n==== %s: %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), ' '.join(cmd))); log.flush()
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, cwd=cwd or ROOT, text=True, encoding='utf-8', errors='replace', bufsize=1)
    for line in p.stdout:
        log.write(line)
        line = line.rstrip()
        if line and not line.startswith('Switch2Recomp: recompile'): print('   ' + line, flush=True)
    p.wait(); log.close()
    if p.returncode: raise Stop('The %s step failed (exit %d). Its output is above and in %s.' % (log_name, p.returncode, os.path.join(out, 'build_mkw.log')))


def merge_ini(template, ini):
    """MKW's defaults, keeping every value the player already set; the native GPU path on."""
    t = open(template, encoding='utf-8', errors='replace').read()
    if os.path.isfile(ini):
        mine = {}
        for line in open(ini, encoding='utf-8', errors='replace'):
            m = re.match(r'^([A-Za-z_0-9]+)=(.*)$', line.rstrip('\n'))
            if m: mine[m[1]] = m[2]
        t = re.sub(r'(?m)^([A-Za-z_0-9]+)=(.*)$', lambda m: '%s=%s' % (m[1], mine.get(m[1], m[2])), t)
    t = re.sub(r'(?m)^gpu=.*$', 'gpu=nvn', t)
    open(ini, 'w', encoding='utf-8').write(t)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('dump', help='the folder you extracted MKW into (exefs\\ and romfs\\ inside)')
    ap.add_argument('--out', default=os.path.join(HERE, 'game'), help='where the game is built (default: the game folder here)')
    ap.add_argument('--jobs', type=int, default=max(2, (os.cpu_count() or 4) - 2), help='compilers at a time (fewer if memory runs out)')
    ap.add_argument('--check', action='store_true', help='only check the dump, the tools and the space; build nothing')
    ap.add_argument('--replace', action='store_true', help='build the code again over an existing build (saves and settings stay)')
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    try:
        say('SwitchRECOMP (c) 2026 MZ Labs. GNU AGPL v3. MKW Recomp is built on Switch2Recomp, based on SwitchRecomp by MZ Labs.')
        say('MKW Recomp. No game files, code or keys are included: it builds from the decrypted files you provide.\n')
        say('1. Your dump')
        dump = find_dump(a.dump)
        pid, bid = check_version(dump)
        romfs = os.path.join(dump, 'romfs')
        if not os.path.isdir(romfs): raise Stop('The dump has no romfs\\ folder (the game\'s data). Extract the whole game, then run this again.')
        say('   %s\n   MKW, %s: supported' % (dump, VERSION_NAME))

        say('2. Tools and space')
        gcc = os.path.join(P.gcc_bin() or os.path.join(ROOT, 'gcc', 'Library', 'bin'), 'x86_64-w64-mingw32-gcc.exe')
        if not os.path.isfile(gcc): raise Stop('GCC is missing. Double-click Install.bat in the Switch2Recomp folder once (it downloads Python and GCC into it), then run this again.')
        try: import zstandard  # noqa: F401  (texture step)
        except ImportError: raise Stop('The Python package "zstandard" is missing: run  python -m pip install zstandard  and then this again.')
        if not os.path.isfile(os.path.join(TOOLS, 'texprep', 'texprep.dll')):   # built once, from the runtime's own code
            say('   building the texture converter (once)...')
            r = subprocess.run([sys.executable, os.path.join(TOOLS, 'texprep', 'build.py')], capture_output=True, text=True)
            if r.returncode: raise Stop('The texture converter could not be built: ' + (r.stdout + r.stderr)[-1500:])
        prof = P.ext('nxnative', 'dm', 'games', PROGRAM_ID)
        if not os.path.isdir(prof): raise Stop('The shader tools are missing (%s). Run  python Switch2Recomp\\tools\\get_external.py  once, then this again.' % prof)
        if not P.spirv_tool('spirv-val'): raise Stop('spirv-val is missing: install the Vulkan SDK (vulkan.lunarg.com), then run this again.')
        exe = os.path.join(out, GAME + '.exe'); dll = os.path.join(out, GAME + '_code.dll')
        need = (NEED_GB['code'] if (a.replace or not os.path.isfile(dll)) else 0) + NEED_GB['shaders'] \
            + (NEED_GB['textures'] if not os.path.isfile(os.path.join(out, 'astc_cache', 'pack2.bin')) else 0)
        same_drive = os.path.splitdrive(os.path.abspath(romfs))[0].lower() == os.path.splitdrive(out)[0].lower()
        if not same_drive and not os.path.isdir(os.path.join(out, GAME + '_data', 'romfs')): need += NEED_GB['data']   # copied, not linked, from another drive
        gb = free_gb(out)
        if 0 <= gb < need + 20:
            raise Stop('Only %.0f GB free on the drive of %s; the build needs about %d GB, and the drive should keep 20 GB free. '
                       'Free some space or pick another folder with --out.' % (gb, out, need))
        say('   GCC, Python, texture converter, shader profile: ready\n   %.0f GB free on the output drive (needs about %d GB)' % (gb, need))
        if a.check:
            say('\nReady. Run the same command without --check to build MKW into %s.' % out); return 0

        os.makedirs(out, exist_ok=True)
        env = dict(os.environ, PATH=os.path.dirname(gcc) + os.pathsep + os.environ.get('PATH', ''), PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
        t_all = time.time()

        say('3. The game\'s code (30-40 minutes)')
        if os.path.isfile(dll) and not a.replace:
            say('   already built (--replace builds it again)')
        else:
            hints = os.path.join(out, GAME + '.hints')
            if not os.path.isfile(hints): shutil.copyfile(os.path.join(HERE, GAME + '.hints'), hints)   # code addresses found in play: no game code
            shutil.copyfile(os.path.join(HERE, GAME + '.patches.py'), os.path.join(out, GAME + '.patches.py'))   # MKW's frame-rate option (Switch2Recomp has no game patches)
            cmd = [sys.executable, os.path.join(TOOLS, 'recompile_game.py'), dump, '--name', GAME, '--out', out, '--jobs', str(a.jobs)]
            if os.path.isfile(exe): cmd.append('--replace')
            step(cmd, 'code', out, env)

        say('4. The shaders')
        step([sys.executable, os.path.join(TOOLS, 'port_game.py'), dump, GAME, '--outdir', out, '--skip-cpu', '--jobs', str(a.jobs)], 'shader', out, env)

        say('5. The textures (converted once for your GPU)')
        step([sys.executable, os.path.join(TOOLS, 'texprep', 'texprep.py'), '--romfs', romfs, '--pack', os.path.join(out, 'astc_cache'),
              '--jobs', str(max(2, a.jobs))], 'texture', out, env)

        say('6. Settings')
        merge_ini(os.path.join(HERE, GAME + '.default.ini'), os.path.join(out, GAME + '.ini'))
        say('   %s (edit it while the game runs: most settings apply live; F1 in game shows the keys)' % os.path.join(out, GAME + '.ini'))

        say('\nDone in %d min. Play: %s\nWhat was built stays on your PC: do not share it.' % ((time.time() - t_all) / 60 + 0.5, exe))
        return 0
    except Stop as e:
        say('\nStopped: %s' % e); return 1
    except KeyboardInterrupt:
        say('\nStopped (Ctrl+C). Run the same command again to carry on where it stopped.'); return 1


if __name__ == '__main__':
    sys.exit(main())
