import sys,os,importlib.abc,importlib.util,inspect
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader
root=Path(__import__('json').loads((Path(__file__).parent/'settings.json').read_text(encoding='utf-8-sig'))['editor']);internal=root/'_internal';sys._MEIPASS=str(internal);sys.path.insert(0,str(internal));handles=[os.add_dll_directory(str(internal/x)) for x in ['PySide6','shiboken6']]
z=CArchiveReader(str(root/'MewgenicsSaveEditor.exe')).open_embedded_archive('PYZ.pyz')
class Embedded(importlib.abc.MetaPathFinder,importlib.abc.Loader):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.startswith(('core','utils','ui','data','PySide6','shiboken6')) and fullname in z.toc:return importlib.util.spec_from_loader(fullname,self,is_package=z.toc[fullname][0]==1)
 def create_module(self,spec):return None
 def exec_module(self,module):
  if z.toc[module.__name__][0]==1:module.__path__=[str(internal/module.__name__.replace('.','/'))]
  module.__file__=str(internal/module.__name__.replace('.','/')/ '__init__.py') if z.toc[module.__name__][0]==1 else str(internal/module.__name__.replace('.','/'))+'.py';exec(z.extract(module.__name__),module.__dict__)
sys.meta_path.insert(0,Embedded())
