"""Configure local dependencies; generate all private/game-derived data locally."""
import argparse,base64,json,os,sqlite3,subprocess,sys,tkinter as tk
from pathlib import Path
from contextlib import closing
from tkinter import filedialog,messagebox
ROOT=Path(__file__).resolve().parent

def configure(game,editor,save,overlays=None):
    game=Path(game).resolve();editor=Path(editor).resolve();save=Path(save).resolve()
    if editor.is_file():editor=editor.parent
    if not (game/'resources.gpak').is_file():raise ValueError('游戏目录中没有 resources.gpak。')
    if not (editor/'MewgenicsSaveEditor.exe').is_file() or not (editor/'_internal'/'PySide6').is_dir():raise ValueError('请选择完整解压后的 Mewgenics Save Editor 4.2.1。')
    if not save.is_file():raise ValueError('存档文件不存在。')
    cfg={'python':sys.executable,'editor':str(editor),'save':str(save),'game':str(game),'overlays':[str(Path(x).resolve()) for x in (overlays or [])],'backupRoot':str(ROOT/'备份'),'journal':str(ROOT/'journal'/'记录'/'出征日记.sqlite3')}
    (ROOT/'settings.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    # Seed templates come from this user's selected save, never from the publisher.
    from PyInstaller.archive.readers import CArchiveReader
    import importlib.abc,importlib.util
    z=CArchiveReader(str(editor/'MewgenicsSaveEditor.exe')).open_embedded_archive('PYZ.pyz')
    class Embedded(importlib.abc.MetaPathFinder,importlib.abc.Loader):
        def find_spec(self,fullname,path=None,target=None):
            if fullname.startswith(('core','utils','data')) and fullname in z.toc:return importlib.util.spec_from_loader(fullname,self,is_package=z.toc[fullname][0]==1)
        def create_module(self,spec):return None
        def exec_module(self,module):module.__file__=str(editor/'_internal'/module.__name__.replace('.','/'))+'.py';exec(z.extract(module.__name__),module.__dict__)
    sys.meta_path.insert(0,Embedded());sys.path.insert(0,str(editor/'_internal'))
    import core.cat_blob_editor as cb
    templates=[]
    with closing(sqlite3.connect(save.as_uri()+'?mode=ro',uri=True)) as c:
        for blob, in c.execute('select data from cats order by key desc'):
            try:
                parsed=cb.parse_cat_blob_full(blob)
                if parsed.visual_data and len(parsed.item_slots)==5:templates.append(base64.b64encode(blob).decode())
            except Exception:continue
            if len(templates)>=8:break
        if not templates:
            row=c.execute("select data from files where key='save_file_cat'").fetchone()
            if row:
                parsed=cb.parse_cat_blob_full(row[0])
                if parsed.visual_data:templates.append(base64.b64encode(row[0]).decode())
    if not templates:raise ValueError('存档中还没有可读取的猫。请在游戏中完成最初的猫咪生成并保存，再初始化。')
    import struct
    with (game/'resources.gpak').open('rb') as f:
        entries=[]
        for _ in range(struct.unpack('<I',f.read(4))[0]):
            n=struct.unpack('<H',f.read(2))[0];name=f.read(n).decode();size=struct.unpack('<I',f.read(4))[0];entries.append((name,size))
        offset=f.tell();pools={}
        for name,size in entries:
            for kind in ['male','female','neutral']:
                if name==f'data/catnames_{kind}_zh-cn.txt':f.seek(offset);pools[kind]=[line.strip() for line in f.read(size).decode('utf-8-sig').splitlines() if line.strip()]
            offset+=size
    if len(pools)!=3:raise ValueError('找不到完整的官方中文名字池。')
    (ROOT/'catalog.json').write_text(json.dumps({'templates':templates,'officialNames':pools},ensure_ascii=False),encoding='utf-8')
    (ROOT/'journal').mkdir(exist_ok=True)
    journal_cfg={**cfg,'preparations':str(ROOT/'出征方案'),'saves':[{'name':'同目录存档 1','path':str(save.with_name('steamcampaign01.sav'))},{'name':'同目录存档 2','path':str(save.with_name('steamcampaign02.sav'))},{'name':'当前选择：'+save.name,'path':str(save)}]}
    (ROOT/'journal'/'settings.json').write_text(json.dumps(journal_cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    subprocess.run([sys.executable,'-X','utf8',str(ROOT/'build_assets.py')],cwd=ROOT,check=True)
    (ROOT/'.configured').write_text('0.1.0-beta.1',encoding='ascii')

def gui():
    window=tk.Tk();window.title('猫咪出征工作台 · 首次配置');window.geometry('780x300');window.resizable(False,False)
    tk.Label(window,text='选择你自己的游戏、存档和原版编辑器。素材在本机生成，不上传存档。',anchor='w').pack(fill='x',padx=18,pady=14)
    values=[tk.StringVar() for _ in range(3)];labels=['Mewgenics 游戏目录','MewgenicsSaveEditor.exe（4.2.1）','要编辑的游戏存档（.sav）']
    for index,label in enumerate(labels):
        row=tk.Frame(window);row.pack(fill='x',padx=18,pady=5);tk.Label(row,text=label,width=33,anchor='w').pack(side='left');tk.Entry(row,textvariable=values[index],width=52).pack(side='left',fill='x',expand=True)
        def choose(i=index):
            path=filedialog.askdirectory(parent=window,title=labels[i]) if i==0 else filedialog.askopenfilename(parent=window,title=labels[i],filetypes=[('Editor executable','*.exe')] if i==1 else [('Mewgenics save','*.sav')])
            if path:values[i].set(path)
        tk.Button(row,text='选择',command=choose).pack(side='right',padx=5)
    note=tk.Label(window,text='初始化会读取游戏素材，通常需要十几秒到一分钟。不会改写游戏存档。',anchor='w');note.pack(fill='x',padx=18,pady=12)
    success=[False]
    def run():
        button.config(state='disabled');note.config(text='正在生成本地素材，请稍候…');window.update_idletasks()
        try:configure(*(v.get() for v in values));success[0]=True;messagebox.showinfo('初始化完成','现在可以打开工作台。\n生成猫咪或清理前，请先回家保存并退出游戏。',parent=window);window.destroy()
        except Exception as e:messagebox.showerror('配置未完成',str(e),parent=window);button.config(state='normal');note.config(text='请检查路径、Python 版本和编辑器版本后重试。')
    button=tk.Button(window,text='初始化本地素材',command=run,width=25);button.pack(pady=5);window.mainloop();return success[0]

if __name__=='__main__':
    if sys.version_info[:2]!=(3,13):raise SystemExit('This beta requires Python 3.13 (matching Save Editor 4.2.1).')
    args=argparse.ArgumentParser();args.add_argument('--game');args.add_argument('--editor');args.add_argument('--save');args.add_argument('--overlay',action='append',default=[]);args.add_argument('--reconfigure',action='store_true');options=args.parse_args()
    if options.game and options.editor and options.save:configure(options.game,options.editor,options.save,options.overlay)
    elif not options.reconfigure and (ROOT/'.configured').exists() and all((ROOT/name).exists() for name in ['settings.json','catalog.json','workbench.json','journal/labels.json']):pass
    elif not gui():sys.exit(1)
