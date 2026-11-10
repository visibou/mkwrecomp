"""MKW Recomp: the builder's window. Pick your dump, press Build; the steps, a progress bar and plain-English messages
show what is happening. It runs tools/mkw/build_mkw.py (which does the work) and reads its output.

  pythonw builder_gui.py      (or double-click "MKW Recompiler.bat")

Shows the SwitchRECOMP startup screen first (NOTICE.txt, additional term 1) and credits SwitchRecomp by MZ Labs (term 3)."""
import json, os, queue, re, subprocess, sys, threading, time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

HERE = os.path.dirname(os.path.abspath(__file__))   # MKW Recomp: this file, MKW's hints and default settings


def find_s2r():
    """Switch2Recomp: S2R_ROOT, else the Switch2Recomp folder beside this file (the git submodule)."""
    for d in (os.environ.get('S2R_ROOT'), os.path.join(HERE, 'Switch2Recomp')):
        if d and os.path.isfile(os.path.join(d, 'switchrecomp.py')): return os.path.abspath(d)
    return None


ROOT = find_s2r()
BUILDER = os.path.join(HERE, 'build_mkw.py')
PREFS = os.path.join(HERE, 'builder_gui.json')   # the last folders used (this PC only)
STEPS = ['Check your dump', 'Check tools and space', 'Build the game\'s code', 'Prepare the shaders', 'Convert the textures', 'Write the settings']
TIPS = ['', '', 'About 30-40 minutes: the game\'s code is translated to C and compiled.', 'About 5 minutes.', 'About 5 minutes, ~21 GB.', '']


def splash_image():
    """The SwitchRECOMP startup screen from tool/splash_img.h (1280x720 coverage, run-length pairs), as a 640x360 grey image."""
    src = os.path.join(ROOT, 'tool', 'splash_img.h')
    nums = [int(x) for x in re.findall(r'\d+', open(src, encoding='utf-8').read().split('{', 1)[1].split('}', 1)[0])]
    px = bytearray()
    for i in range(0, len(nums) - 1, 2): px += bytes([nums[i + 1]]) * nums[i]
    px = bytes(px[:1280 * 720]).ljust(1280 * 720, b'\0')
    img = tk.PhotoImage(data=b'P5 1280 720 255\n' + px, format='PPM')
    return img.subsample(2, 2)


class App:
    def __init__(self, root):
        self.root = root; self.proc = None; self.q = queue.Queue(); self.step = -1; self.ok = False
        root.title('MKW Recomp'); root.minsize(720, 560)
        try: self.prefs = json.load(open(PREFS, encoding='utf-8'))
        except Exception: self.prefs = {}
        pad = dict(padx=12, pady=4)
        f = ttk.Frame(root); f.pack(fill='both', expand=True)
        ttk.Label(f, text='MKW Recomp', font=('Segoe UI', 16, 'bold')).pack(anchor='w', padx=12, pady=(12, 0))
        ttk.Label(f, text='Builds MKW (version 1.0.0) for Windows on your PC, from decrypted files you provide. No game files, code or keys are included;\n'
                          'what it builds stays on your PC. Not affiliated with, endorsed, sponsored or supported by Nintendo.', foreground='#555').pack(anchor='w', **pad)

        g = ttk.Frame(f); g.pack(fill='x', **pad); g.columnconfigure(1, weight=1)
        self.dump = tk.StringVar(value=self.prefs.get('dump', '')); self.out = tk.StringVar(value=self.prefs.get('out', os.path.join(HERE, 'game')))
        ttk.Label(g, text='Your dump:').grid(row=0, column=0, sticky='w')
        ttk.Entry(g, textvariable=self.dump).grid(row=0, column=1, sticky='ew', padx=6)
        ttk.Button(g, text='Browse...', command=lambda: self.pick(self.dump, 'The folder with the decrypted files you provide (exefs and romfs inside)')).grid(row=0, column=2)
        ttk.Label(g, text='Build into:').grid(row=1, column=0, sticky='w', pady=(4, 0))
        ttk.Entry(g, textvariable=self.out).grid(row=1, column=1, sticky='ew', padx=6, pady=(4, 0))
        ttk.Button(g, text='Browse...', command=lambda: self.pick(self.out, 'Where to build the game')).grid(row=1, column=2, pady=(4, 0))

        s = ttk.LabelFrame(f, text='Steps'); s.pack(fill='x', **pad)
        self.marks = []
        for i, name in enumerate(STEPS):
            m = ttk.Label(s, text='○', width=2, font=('Segoe UI', 11)); m.grid(row=i, column=0, padx=(8, 2))
            ttk.Label(s, text=name).grid(row=i, column=1, sticky='w')
            ttk.Label(s, text=TIPS[i], foreground='#777').grid(row=i, column=2, sticky='w', padx=12)
            self.marks.append(m)
        self.bar = ttk.Progressbar(f, mode='determinate', maximum=1000); self.bar.pack(fill='x', **pad)
        self.status = tk.StringVar(value='Choose your dump, then press Check or Build.')
        ttk.Label(f, textvariable=self.status, wraplength=680).pack(anchor='w', **pad)

        b = ttk.Frame(f); b.pack(fill='x', **pad)
        self.bcheck = ttk.Button(b, text='Check', command=lambda: self.start(True)); self.bcheck.pack(side='left')
        self.bbuild = ttk.Button(b, text='Build', command=lambda: self.start(False)); self.bbuild.pack(side='left', padx=6)
        self.bstop = ttk.Button(b, text='Stop', command=self.stop, state='disabled'); self.bstop.pack(side='left')
        self.bplay = ttk.Button(b, text='Play', command=self.play, state='disabled'); self.bplay.pack(side='right')
        ttk.Button(b, text='Open folder', command=lambda: os.startfile(self.out.get()) if os.path.isdir(self.out.get()) else None).pack(side='right', padx=6)

        self.log = scrolledtext.ScrolledText(f, height=10, font=('Consolas', 9), state='disabled'); self.log.pack(fill='both', expand=True, **pad)
        ttk.Label(f, text='Switch2Recomp, based on SwitchRecomp by MZ Labs (GNU AGPL v3). Source and licenses: see README and NOTICE.txt.',
                  foreground='#777').pack(anchor='w', padx=12, pady=(0, 10))
        self.update_play(); root.protocol('WM_DELETE_WINDOW', self.close); root.after(100, self.pump)

    def pick(self, var, title):
        d = filedialog.askdirectory(title=title, initialdir=var.get() or None)
        if d: var.set(os.path.normpath(d))

    def write(self, text):
        self.log.configure(state='normal'); self.log.insert('end', text + '\n'); self.log.see('end'); self.log.configure(state='disabled')

    def mark(self, i, state):
        if 0 <= i < len(self.marks): self.marks[i].configure(text={'run': '●', 'ok': '✔', 'bad': '✖', 'wait': '○'}[state],
                                                              foreground={'run': '#1a73e8', 'ok': '#188038', 'bad': '#d93025', 'wait': '#000'}[state])

    def update_play(self):
        self.bplay.configure(state='normal' if os.path.isfile(os.path.join(self.out.get(), 'MKW.exe')) and
                             os.path.isfile(os.path.join(self.out.get(), 'MKW_code.dll')) and not self.proc else 'disabled')

    def start(self, check):
        if not self.dump.get(): messagebox.showinfo('Your dump', 'Choose the folder with your files (exefs and romfs inside) first.'); return
        self.prefs.update(dump=self.dump.get(), out=self.out.get())
        try: json.dump(self.prefs, open(PREFS, 'w', encoding='utf-8'))
        except OSError: pass
        for i in range(len(STEPS)): self.mark(i, 'wait')
        self.step = -1; self.ok = False; self.bar.configure(mode='determinate', value=0)
        self.log.configure(state='normal'); self.log.delete('1.0', 'end'); self.log.configure(state='disabled')
        cmd = [sys.executable.replace('pythonw.exe', 'python.exe'), '-u', BUILDER, self.dump.get(), '--out', self.out.get()] + (['--check'] if check else [])
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1,
                                     cwd=ROOT, creationflags=flags, env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8'))
        threading.Thread(target=self.reader, args=(self.proc,), daemon=True).start()
        for w in (self.bcheck, self.bbuild): w.configure(state='disabled')
        self.bstop.configure(state='normal'); self.update_play()
        self.status.set('Checking...' if check else 'Building... you can leave this window open and use your PC; the build uses every CPU core.')

    def reader(self, p):
        for line in p.stdout: self.q.put(line.rstrip('\n'))
        self.q.put(None)

    def pump(self):
        try:
            while True:
                line = self.q.get_nowait()
                if line is None: self.finished(); break
                self.handle(line)
        except queue.Empty: pass
        self.root.after(100, self.pump)

    def handle(self, line):
        m = re.match(r'^(\d)\. ', line)
        if m:
            n = int(m[1]) - 1
            if self.step >= 0: self.mark(self.step, 'ok')
            self.step = n; self.mark(n, 'run'); self.bar.configure(mode='determinate', value=0); self.status.set(STEPS[n] + '...')
        m = re.search(r'(compiling|translating to C) \[[#-]+\] (\d+)/(\d+)(, about \d+ min left)?', line)
        if m:
            self.bar.configure(value=1000 * int(m[2]) / max(int(m[3]), 1)); self.status.set('%s: %s of %s files%s' % (m[1].capitalize(), m[2], m[3], m[4] or '')); return
        m = re.match(r'^\s*([\d.]+)%\s+(\d+)/(\d+) files.*?(\S+) left$', line)
        if m:
            self.bar.configure(value=10 * float(m[1])); self.status.set('Converting textures: %s of %s files, %s left' % (m[2], m[3], m[4])); return
        if line.startswith('Stopped:'): self.status.set(line[len('Stopped:'):].strip())
        elif line.startswith('Ready.') or line.startswith('Done in'): self.ok = True; self.status.set(line)
        self.write(line)

    def finished(self):
        rc = self.proc.wait() if self.proc else 1; self.proc = None
        if self.step >= 0: self.mark(self.step, 'ok' if rc == 0 else 'bad')
        for w in (self.bcheck, self.bbuild): w.configure(state='normal')
        self.bstop.configure(state='disabled'); self.update_play()
        if rc == 0 and self.ok: self.bar.configure(value=1000)
        elif rc: messagebox.showwarning('Stopped', self.status.get())

    def stop(self):
        if self.proc and messagebox.askyesno('Stop', 'Stop the build? Press Build again later to carry on where it stopped.'):
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(self.proc.pid)], capture_output=True)

    def play(self):
        exe = os.path.join(self.out.get(), 'MKW.exe')
        if os.path.isfile(exe): subprocess.Popen([exe], cwd=self.out.get())

    def close(self):
        if self.proc and not messagebox.askyesno('Quit', 'A build is running. Stop it and quit? You can carry on later.'): return
        if self.proc: subprocess.run(['taskkill', '/T', '/F', '/PID', str(self.proc.pid)], capture_output=True)
        self.root.destroy()


def main():
    root = tk.Tk(); root.withdraw()
    if not ROOT:
        messagebox.showerror('MKW Recomp', 'Switch2Recomp is missing. Download the full package, or in this folder run:\n'
                             'git submodule update --init'); return
    try:   # the SwitchRECOMP startup screen, 2 seconds (NOTICE.txt term 1)
        sp = tk.Toplevel(root); sp.overrideredirect(True); sp.configure(bg='black'); img = splash_image()
        w, h = img.width(), img.height(); sp.geometry('%dx%d+%d+%d' % (w, h, (sp.winfo_screenwidth() - w) // 2, (sp.winfo_screenheight() - h) // 2))
        tk.Label(sp, image=img, bg='black', bd=0).pack(); sp.img = img
        root.after(2000, lambda: (sp.destroy(), root.deiconify()))
    except Exception:
        root.deiconify()
    App(root); root.mainloop()


if __name__ == '__main__':
    main()
