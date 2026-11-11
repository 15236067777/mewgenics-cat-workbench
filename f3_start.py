"""F3 助手启动器：崩溃时把 traceback 写到 F3助手崩溃.txt，方便排查。"""
import pathlib, sys, traceback

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
try:
    import hotkey_donate as helper
    helper.main()
except BaseException:
    (ROOT / 'F3助手崩溃.txt').write_text(traceback.format_exc(), encoding='utf-8')
