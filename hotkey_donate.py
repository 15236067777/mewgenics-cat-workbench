"""F3 助手：让 NPC 捐献进度一直保持满（等于一直交够了猫/物品，不消耗猫）。

- 常驻监听存档：每次游戏保存后自动补满，下次读档就是满的；
- 按 F3 立刻补一次（游戏运行中也可以，写的是存档文件）；
- 托盘右键可开关常驻补满、看图志、退出。
"""
import ctypes
import ctypes.wintypes
import subprocess
import sys
import threading
import time
from pathlib import Path

if sys.stdout is None or sys.stderr is None:  # pythonw 下没有控制台
    _null = open('nul', 'w', encoding='utf-8') if sys.platform == 'win32' else open('/dev/null', 'w', encoding='utf-8')
    sys.stdout = sys.stdout or _null
    sys.stderr = sys.stderr or _null

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import editor_bridge  # 接上存档编辑器自带的 PySide6
import backend

from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

SAVE = Path(backend.CONFIG['save'])
LOG = ROOT / 'F3助手日志.txt'
VK_F3 = 0x72
WM_HOTKEY = 0x0312
KEEP_INTERVAL = 2.0
BACKUP_EVERY = 600.0
STATE = {'busy': False, 'keep': True, 'last_backup': 0.0}
STOP = threading.Event()


def log(text):
    try:
        if LOG.exists() and LOG.stat().st_size > 512 * 1024:
            LOG.replace(LOG.with_name('F3助手日志.old.txt'))
        with LOG.open('a', encoding='utf-8') as handle:
            handle.write(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {text}\n')
    except OSError:
        pass


def backup_due():
    now = time.time()
    if now - STATE['last_backup'] >= BACKUP_EVERY:
        STATE['last_backup'] = now
        return True
    return False


def patch(notify, reason):
    if STATE['busy']:
        return
    STATE['busy'] = True
    try:
        result = backend.donate_direct(backup=backup_due())
        text = result.get('message', '')
        if result.get('changed'):
            notify('已补满', text)
            log(f'{reason} | {text}')
        elif reason != '自动':
            notify('不用改', text)
            log(f'{reason} | {text}')
        else:
            log(f'{reason} | {text}')
    except Exception as error:
        notify('没有写入', str(error))
        log(f'{reason} | 失败：{error}')
    finally:
        STATE['busy'] = False


def game_running():
    try:
        output = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Mewgenics.exe', '/NH'], capture_output=True, text=True, errors='replace', creationflags=0x08000000).stdout
        return 'mewgenics.exe' in output.lower()
    except OSError:
        return False


def make_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor('#2867c6'))
    painter.setPen(QColor('#1b4c95'))
    painter.drawRoundedRect(2, 2, 60, 60, 16, 16)
    painter.setPen(QColor('white'))
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(30)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), 0x0084, 'F3')
    painter.end()
    return QIcon(pixmap)


def start_hotkey_thread(callback):
    """独立 Win32 线程注册 F3，不依赖 Qt 的消息分发。"""
    def run():
        user32 = ctypes.windll.user32
        if not user32.RegisterHotKey(None, 1, 0, VK_F3):
            log('热键注册失败：F3 可能被别的程序占用')
            return
        log('热键已注册：F3')
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY:
                callback()
    threading.Thread(target=run, daemon=True).start()


class Helper:
    def __init__(self, app):
        self.app = app
        self.tray = QSystemTrayIcon(make_icon(), app)
        self.tray.setToolTip('喵喵的结合 · NPC 捐献保持满（F3 立即补）')
        self.menu = QMenu()
        title = QAction('NPC 捐献保持满', self.menu)
        title.setEnabled(False)
        self.menu.addAction(title)
        self.keep_action = QAction('常驻补满（游戏保存后自动补）', self.menu)
        self.keep_action.setCheckable(True)
        self.keep_action.setChecked(True)
        self.keep_action.toggled.connect(self.set_keep)
        self.menu.addAction(self.keep_action)
        self.menu.addAction(QAction('立即补满（F3）', self.menu, triggered=self.trigger_now))
        self.menu.addAction(QAction('查看日志', self.menu, triggered=self.show_log))
        self.menu.addAction(QAction('退出', self.menu, triggered=self.quit))
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        self.window = QWidget()
        self.window.resize(1, 1)
        self.window.show()
        self.window.hide()
        start_hotkey_thread(self.on_hotkey)
        self.notify('F3 助手已启动', 'NPC 捐献会一直保持满：每次游戏保存后自动补一次；按 F3 可立刻补。')
        threading.Thread(target=self.keeper, daemon=True).start()

    def notify(self, title, text):
        self.tray.showMessage(title, text, QSystemTrayIcon.Information, 5000)

    def set_keep(self, enabled):
        STATE['keep'] = bool(enabled)
        log(f'常驻补满：{"开" if STATE["keep"] else "关"}')
        self.notify('常驻补满', '已开启' if STATE['keep'] else '已关闭，只能按 F3 手动补。')

    def trigger_now(self):
        log('手动补满（F3 / 菜单）')
        threading.Thread(target=patch, args=(self.notify, '手动'), daemon=True).start()

    def on_hotkey(self):
        self.trigger_now()

    def show_log(self):
        self.notify('日志位置', str(LOG))

    def keeper(self):
        stamp = None
        while not STOP.wait(KEEP_INTERVAL):
            try:
                stat = SAVE.stat()
                current = (stat.st_mtime_ns, stat.st_size)
            except OSError:
                continue
            if not STATE['keep']:
                stamp = current
                continue
            if current != stamp:
                if stamp is not None:
                    time.sleep(1.5)
                    patch(self.notify, '自动')
                stamp = current

    def quit(self):
        STOP.set()
        try:
            ctypes.windll.user32.UnregisterHotKey(None, 1)
        except OSError:
            pass
        self.app.quit()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    Helper(app)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
