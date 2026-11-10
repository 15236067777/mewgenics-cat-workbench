import sys,json,sqlite3,hashlib,shutil,tempfile,os,struct,datetime,subprocess,importlib.abc,importlib.util,base64,random
from pathlib import Path
from contextlib import closing
HERE=Path(__file__).resolve().parent
CONFIG=json.loads((HERE/'settings.json').read_text(encoding='utf-8-sig'))
CAT=json.loads((HERE/'catalog.json').read_text(encoding='utf-8-sig'))
DEFAULT_CLASSES={'colorless','fighter','hunter','mage','tank'}
def closed():
    names=subprocess.run(['tasklist','/FO','CSV','/NH'],capture_output=True,creationflags=0x08000000).stdout.lower()
    if b'"mewgenics.exe"' in names or b'"mewgenicssaveeditor.exe"' in names:
        raise ValueError('请先在游戏中保存并退出，同时关闭存档编辑器，再添加猫咪。')

def api():
    from PyInstaller.archive.readers import CArchiveReader
    root=Path(CONFIG['editor']);z=CArchiveReader(str(root/'MewgenicsSaveEditor.exe')).open_embedded_archive('PYZ.pyz')
    class Embedded(importlib.abc.MetaPathFinder,importlib.abc.Loader):
        def find_spec(self,fullname,path=None,target=None):
            if fullname.startswith(('core','utils')) and fullname in z.toc:return importlib.util.spec_from_loader(fullname,self,is_package=z.toc[fullname][0]==1)
        def create_module(self,spec):return None
        def exec_module(self,module):
            module.__file__=str(root/'_internal'/module.__name__.replace('.','/'))+'.py';exec(z.extract(module.__name__),module.__dict__)
    sys.meta_path.insert(0,Embedded());sys.path.append(str(root/'_internal'))
    import core.save_editor as se,core.cat_blob_editor as cb,core.house_unlocks_parser as hu
    return se,cb,hu

def draw_name(rng,gender):
    pools=CAT['officialNames']
    names=pools['male' if gender==0 else 'female']+pools['neutral']
    if not names:raise ValueError('官方中文名字池为空，未添加猫咪。')
    return rng.choice(names)

def owncats(se,conn):return [x for x in se.get_all_cat_details(conn) if x['source']=='cats' and x['in_house']]

def snap(conn):return {t:dict(conn.execute(f'select key,data from {t}')) for t in ['cats','furniture','files','properties','winning_teams']}
