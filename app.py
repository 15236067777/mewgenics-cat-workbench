import sys,os,json,copy,base64,dataclasses,tempfile,html,datetime,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import editor_bridge
from PySide6.QtCore import Qt,QSize,QTimer,QProcess,QUrl,QLockFile,QEvent,QRect
from PySide6.QtGui import QIcon,QPixmap,QDesktopServices,QPainter,QColor,QTextDocument
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QCheckBox,QComboBox,QLineEdit,QTabWidget,QSplitter,QScrollArea,QDialog,QListWidget,QListWidgetItem,QAbstractItemView,QTextBrowser,QDialogButtonBox,QMessageBox,QFileDialog,QFrame,QGroupBox,QToolTip,QStyledItemDelegate,QStyle,QSizePolicy
import core.cat_blob_editor as cb,core.cat_renderer as renderer,core.i18n as i18n
import ui.gui_cat_customize_dialog as customize
from skill_slots import SKILL_SLOTS,MAX_CATS
CONFIG=json.loads((ROOT/'settings.json').read_text(encoding='utf-8-sig'))
DATA=json.loads((ROOT/'workbench.json').read_text(encoding='utf-8-sig'))
BASE=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8-sig'))
CLASSES={x['id']:x for x in DATA['classes']}
SKILLS={x['id']:x for kind in ['actives','passives','diseases'] for x in DATA.get(kind,[])}
ITEMS={x['id']:x for x in DATA['items']}
ROOMS={'Floor1_Large':'一楼左','Floor1_Small':'一楼右','Floor2_Small':'二楼左','Floor2_Large':'二楼右','Attic':'阁楼'}
KINDS={'head':'头部','face':'面部','neck':'颈部','weapon':'武器','trinket':'饰品'}
def image(path):return str(ROOT/path) if path else ''
def show_hover(view,event):
    pos=event.position().toPoint() if event.type()==QEvent.MouseMove else event.pos()
    index=view.indexAt(pos);text=index.data(Qt.ToolTipRole) if index.isValid() else None
    if text:QToolTip.showText(view.viewport().mapToGlobal(pos),text,view.viewport(),view.visualRect(index),20000)
    else:QToolTip.hideText()
    return bool(text)

class HoverCombo(QComboBox):
    def __init__(self,*args):
        super().__init__(*args);self.view().setMouseTracking(True);self.view().viewport().installEventFilter(self)
        self.currentIndexChanged.connect(lambda _:self.setToolTip(self.currentData(Qt.ToolTipRole) or ''))
    def eventFilter(self,obj,event):
        if obj is self.view().viewport() and event.type() in (QEvent.ToolTip,QEvent.MouseMove):
            handled=show_hover(self.view(),event)
            if event.type()==QEvent.ToolTip:return handled
        return super().eventFilter(obj,event)

def compact_effect(text):
    for key,value in {'STR':'力量','DEX':'敏捷','CON':'体质','INT':'智力','SPD':'速度','CHA':'魅力','LCK':'幸运','Shield':'护盾'}.items():text=re.sub(r'\b'+key+r'\b',value,text)
    seen=set();lines=[]
    for line in re.split(r'[\n,，;；]+',text.replace('−','-')):
        normalized=re.sub(r'\s+','',line)
        if normalized and normalized not in seen:lines.append(line.strip());seen.add(normalized)
    return '\n'.join(sorted(lines,key=effect_rank))

def effect_rank(line):
    stat=re.fullmatch(r'\s*(?:力量|敏捷|体质|智力|速度|魅力|幸运|护盾|生命|生命上限|法力|法力上限|移动|攻击|闪避|暴击)\s*[:：]?\s*([+-]?\d+(?:\.\d+)?%?)\s*',line)
    if not stat:return 0
    return 2 if stat[1].startswith('-') else 1

def mutation_rank(description):
    ranks=[effect_rank(x) for x in compact_effect(description).splitlines() if x.strip()]
    return 0 if not ranks or 0 in ranks else 2 if 2 in ranks else 1

class SetOptionDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        painter.save();rect=option.rect.adjusted(7,5,-7,-5);selected=bool(option.state & QStyle.State_Selected)
        painter.fillRect(option.rect,QColor('#e5efff' if selected else '#ffffff'))
        icon=index.data(Qt.DecorationRole)
        if icon:icon.paint(painter,QRect(rect.left(),rect.top()+3,34,34))
        painter.translate(rect.left()+44,rect.top());doc=QTextDocument();doc.setDefaultFont(option.font);doc.setTextWidth(rect.width()-44);doc.setPlainText(index.data(Qt.DisplayRole) or '');doc.drawContents(painter);painter.restore()
    def sizeHint(self,option,index):
        doc=QTextDocument();doc.setDefaultFont(option.font);doc.setTextWidth(660);doc.setPlainText(index.data(Qt.DisplayRole) or '')
        return QSize(730,max(52,int(doc.size().height())+12))

class SetCombo(QComboBox):
    def __init__(self,*args):
        super().__init__(*args);self.view().setItemDelegate(SetOptionDelegate(self.view()));self.view().setMinimumWidth(760);self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon);self.setMinimumContentsLength(9);self.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);self.setMaxVisibleItems(9)

def skill_blocks(entry,upgraded):
    if not entry:return ''
    def block(title,text,active):
        return '<div style="margin:2px 0 8px"><b style="color:'+('#1a4f9c' if active else '#8b96a3')+'">'+('√ ' if active else '')+title+'</b><br>'+html.escape(text or '').replace('\n','<br>')+'</div>'
    upgrade=entry.get('upgrade')
    if not upgrade:return block('效果',entry.get('description',''),True)
    return block('原效果',entry.get('description',''),not upgraded)+block('强化效果',upgrade.get('description',''),upgraded)
def entry_html(entry,upgraded):
    if not entry:return ''
    pic='<img width="88" height="88" src="'+QUrl.fromLocalFile(image(entry.get('image',''))).toString()+'"><br>' if entry.get('image') else ''
    body=skill_blocks(entry,upgraded) if entry.get('upgrade') else html.escape(entry.get('description','')).replace('\n','<br>')
    return '<div style="width:340px">'+pic+'<b>'+html.escape(entry.get('name',''))+'</b><br>'+body+'</div>'
def tooltip(entry):
    pic='<img width="88" height="88" src="'+QUrl.fromLocalFile(image(entry.get('image',''))).toString()+'"><br>' if entry.get('image') else ''
    return '<div style="width:350px">'+pic+'<b>'+html.escape(entry.get('name',''))+'</b><br>'+html.escape(entry.get('description','')).replace('\n','<br>')+'</div>'
def picture_button(entry,empty='空（没有）'):
    button=QPushButton(entry.get('name',empty) if entry else empty);button.setMinimumHeight(56);button.setIconSize(QSize(44,44));button.setMinimumWidth(0);button.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
    if entry:button.setIcon(QIcon(image(entry.get('image',''))));button.setToolTip(tooltip(entry))
    return button
def default_cat(i):
    blob=base64.b64decode(BASE['templates'][i%len(BASE['templates'])]);visual=dataclasses.asdict(cb.parse_cat_blob_full(blob).visual_data)
    for field in ['body','head','tail','leg_back_left','leg_back_right','arm_front_left','arm_front_right','ear_left','ear_right','eye_left','eye_right','eyebrow_left','eyebrow_right','mouth','texture']:
        if visual.get(field, 0) < 1 or visual.get(field, 0) >= 300:
            visual[field] = 1
    for field in visual:
        if field.endswith('_mut'):
            visual[field] = 0
    return {'enabled':i==0,'name':'','gender':i%2,'room':list(ROOMS)[i%4],'visual':visual,**{key:{'class':'empty','id':None} for key in SKILL_SLOTS},'equipment':{k:None for k in KINDS}}

class Gallery(QDialog):
    def __init__(self,parent,title,entries,current=None,detail_rows=False,upgrades=False):
        super().__init__(parent);self.setWindowTitle(title);self.resize(1060,760);self.selected=None;self.entries={x['id']:x for x in entries};self.upgrades=upgrades;self.upgraded=False;self.upgrade_box=None
        root=QVBoxLayout(self);search=QLineEdit();search.setPlaceholderText('搜索中文名、效果或内部名称');root.addWidget(search)
        if upgrades:
            self.upgrade_box=QCheckBox('使用强化版（已升级）');self.upgrade_box.setToolTip('勾选后写入这个技能的强化版本。右边始终同时列出原效果和强化效果。');self.upgrade_box.toggled.connect(self.set_upgraded);root.addWidget(self.upgrade_box)
        split=QSplitter();root.addWidget(split,1);self.list=QListWidget();self.list.setViewMode(QListWidget.IconMode);self.list.setResizeMode(QListWidget.Adjust);self.list.setMovement(QListWidget.Static);self.list.setIconSize(QSize(64,64));self.list.setGridSize(QSize(128,108));self.list.setWordWrap(True);self.list.setMouseTracking(True);split.addWidget(self.list)
        self.preview=QTextBrowser();self.preview.setMinimumWidth(285);split.addWidget(self.preview);split.setSizes([720,300])
        for entry in [{'id':'','name':'空（没有）','description':'不添加此技能或装备。','image':''}]+entries:
            item=QListWidgetItem(QIcon(image(entry.get('image',''))),entry['name']+(' ＋' if upgrades and entry.get('upgrade') else ''));item.setData(Qt.UserRole,entry['id']);item.setData(Qt.UserRole+1,entry_html(entry,False) if upgrades else '<b>'+html.escape(entry['name'])+'</b><br>'+html.escape(entry['description']).replace('\n','<br>'));item.setSizeHint(QSize(128,108));item.setTextAlignment(Qt.AlignHCenter);item.setToolTip(entry_html(entry,False) if upgrades else tooltip(entry));self.list.addItem(item)
            if entry['id']==(current or ''):self.list.setCurrentItem(item)
        self.list.setUniformItemSizes(True)
        if detail_rows:
            self.list.setViewMode(QListWidget.ListMode);self.list.setGridSize(QSize());self.list.setItemDelegate(MutationDelegate(self.list))
            for i in range(self.list.count()):self.list.item(i).setSizeHint(QSize(0,104))
        self.list.currentItemChanged.connect(lambda item,old:self.show_entry(item));self.list.itemEntered.connect(self.show_entry);self.list.itemDoubleClicked.connect(lambda item:self.choose())
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Ok).setText('选择这一个');buttons.button(QDialogButtonBox.Cancel).setText('取消');buttons.accepted.connect(self.choose);buttons.rejected.connect(self.reject);root.addWidget(buttons)
        search.textChanged.connect(lambda text:[self.list.item(j).setHidden(bool(text) and text.casefold() not in (self.list.item(j).text()+' '+self.list.item(j).data(Qt.UserRole)+' '+self.entries.get(self.list.item(j).data(Qt.UserRole),{}).get('description','')).casefold()) for j in range(self.list.count())]);self.show_entry(self.list.currentItem())
    def show_entry(self,item):
        if not item:return
        entry=self.entries.get(item.data(Qt.UserRole),{'name':'空（没有）','description':'不添加此技能或装备。'})
        body=entry_html(entry,self.upgraded) if self.upgrades else tooltip(entry)
        if self.upgrades and entry.get('upgrade'):
            body='<div style="color:#2b5c9b;font-weight:700;margin-bottom:6px">'+('当前写入：强化版' if self.upgraded else '当前写入：原版')+'</div>'+body
        self.preview.setHtml(body)
    def set_upgraded(self,value):
        self.upgraded=bool(value);self.show_entry(self.list.currentItem())
    def choose(self):
        item=self.list.currentItem()
        if item:self.selected=item.data(Qt.UserRole) or None;self.accept()

class MutationDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        painter.save();rect=option.rect.adjusted(3,3,-3,-3);selected=bool(option.state & QStyle.State_Selected)
        painter.setPen(QColor('#3e7ddb' if selected else '#d5dfeb'));painter.setBrush(QColor('#e5efff' if selected else '#ffffff'));painter.drawRoundedRect(rect,6,6)
        icon=index.data(Qt.DecorationRole)
        if icon:icon.paint(painter,QRect(rect.left()+5,rect.top()+12,64,64))
        text_rect=rect.adjusted(78,8,-7,-7);painter.setClipRect(text_rect);painter.translate(text_rect.topLeft());doc=QTextDocument();doc.setDefaultFont(option.font);doc.setTextWidth(text_rect.width());doc.setHtml('<div style="color:#203047">'+index.data(Qt.UserRole+1)+'</div>');doc.drawContents(painter);painter.restore()
    def sizeHint(self,option,index):return QSize(310,112)

class MutationPicker(customize._CatalogPicker):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self._list.setItemDelegate(MutationDelegate(self._list));self._list.setMouseTracking(True);self._list.viewport().installEventFilter(self);self._list.setUniformItemSizes(True);self._list.setStyleSheet('QListWidget{background:#f4f7fb;border:1px solid #cbd6e4;}');self.layout_cells()
    def layout_cells(self):
        width=max(300,self._list.viewport().width());columns=max(1,width//315);self._list.setGridSize(QSize(max(290,(width-8)//columns),112))
    def eventFilter(self,obj,event):
        if obj is self._list.viewport():
            if event.type()==QEvent.Resize:QTimer.singleShot(0,self.layout_cells)
            elif event.type() in (QEvent.ToolTip,QEvent.MouseMove):
                handled=show_hover(self._list,event)
                if event.type()==QEvent.ToolTip:return handled
        return super().eventFilter(obj,event)
    def _frames_for_filter(self):
        frames=super()._frames_for_filter();effects=DATA['mutations'].get(self._folder,{})
        return sorted(frames,key=lambda f:(mutation_rank(effects[str(f)]['description']),f) if str(f) in effects else (3,f))
    def _populate(self):
        super()._populate();entries=DATA['mutations'].get(self._folder,{})
        for frame,item in self._item_by_frame.items():
            effect=entries.get(str(frame),{'name':'普通部位' if frame<300 else f'部位 #{frame}','description':'普通外观，无额外变异效果。' if frame<300 else '当前数据未提供效果说明。'})
            effect=dict(effect,description=compact_effect(effect['description']));name=effect['name'];name=f'变异 #{frame}' if name==str(frame) else name+f' #{frame}'
            item.setText(name+' · '+effect['description']);item.setData(Qt.UserRole+1,'<b>'+html.escape(name)+'</b><br>'+html.escape(effect['description']).replace('\n','<br>'));item.setToolTip(tooltip(dict(effect,name=name)));item.setSizeHint(QSize(310,112))
        if self._list.itemDelegate():self.layout_cells()
customize._CatalogPicker=MutationPicker

class Window(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('喵喵的结合 · 自定义猫咪出征工作台');self.resize(1380,930);self.setMinimumSize(1120,800);self.cats=[default_cat(i) for i in range(4)];self.selected=0;self.tab_index=0;self.info={'unlocked':['colorless','fighter','hunter','mage','tank'],'rooms':list(ROOMS)[:4]};self.loading=False;self.process=None
        try:
            saved=json.loads((ROOT/'当前草稿.json').read_text(encoding='utf-8'));self.cats=saved['cats'] if 1<=len(saved.get('cats',[]))<=MAX_CATS else self.cats
        except Exception:pass
        central=QWidget();self.setCentralWidget(central);root=QVBoxLayout(central);root.setContentsMargins(22,18,22,18)
        title=QLabel('自定义猫咪 · 出征工作台');title.setObjectName('heading');root.addWidget(title)
        description=QLabel('基础属性全 7  ·  左侧可加多只自定义猫（最多 '+str(MAX_CATS)+' 只），启用几只就生成几只  ·  职业与技能不受存档解锁限制  ·  悬停查看效果');root.addWidget(description)
        toolbar=QHBoxLayout();root.addLayout(toolbar);self.title=QLineEdit('我的出征方案');self.title.setPlaceholderText('给这次配置起个名字');toolbar.addWidget(self.title,1)
        for text,fn in [('保存方案',self.save_preset),('载入方案',self.load_preset),('查看出征日记',self.open_journal),('刷新存档',lambda:self.call({'action':'status'},self.status_received)),('解锁全部职业与技能',self.unlock_all),('NPC 交猫直接完成',self.donate_all)]:
            b=QPushButton(text);b.clicked.connect(fn);toolbar.addWidget(b)
        self.helper_button=QPushButton('启动 F3 助手');self.helper_button.setToolTip('常驻补满 NPC 捐献（等于交够猫，不消耗猫）。不随机启动，需要时点这里。');self.helper_button.clicked.connect(self.toggle_helper);toolbar.addWidget(self.helper_button)
        self.refresh_helper_button()
        self.status=QLabel('正在读取当前存档…');self.status.setWordWrap(True);root.addWidget(self.status)
        split=QSplitter();root.addWidget(split,1);side=QWidget();self.side_layout=QVBoxLayout(side);side.setMinimumWidth(255);side.setMaximumWidth(335);split.addWidget(side)
        self.editor=QWidget();self.editor_layout=QVBoxLayout(self.editor);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(self.editor);split.addWidget(scroll);split.setSizes([280,1060])
        bottom=QHBoxLayout();root.addLayout(bottom);self.clear=QPushButton('备份并清空猫咪及非任务装备');self.clear.setObjectName('danger');self.clear.clicked.connect(self.clear_save);bottom.addWidget(self.clear);bottom.addStretch();self.generate=QPushButton('备份并生成已启用的猫咪');self.generate.setObjectName('primary');self.generate.setMinimumHeight(46);self.generate.clicked.connect(self.generate_cats);bottom.addWidget(self.generate)
        footer=QLabel('写入前请回家、保存并退出游戏。生成前自动备份；任务装备和消耗品受保护。生成方案会关联实际出征队伍，人数不限于 4 只。');footer.setWordWrap(True);root.addWidget(footer)
        self.draft_timer=QTimer(self);self.draft_timer.setSingleShot(True);self.draft_timer.setInterval(450);self.draft_timer.timeout.connect(self.write_draft)
        self.title.textChanged.connect(self.changed);self.build_side();self.build_editor();QTimer.singleShot(100,lambda:self.call({'action':'status'},self.status_received))
    def changed(self,*args):
        if not self.loading:self.draft_timer.start()
    def write_draft(self):
        (ROOT/'当前草稿.json').write_text(json.dumps({'title':self.title.text(),'cats':self.cats},ensure_ascii=False,indent=2),encoding='utf-8');self.build_side()
    def clear_layout(self,layout):
        while layout.count():
            item=layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
            elif item.layout():self.clear_layout(item.layout())
    def visual(self,cat):
        fields=cb.CatVisualData.__dataclass_fields__;return cb.CatVisualData(**{k:v for k,v in cat['visual'].items() if k in fields})
    def portrait(self,cat,size):
        image=renderer.render_cat_image(self.visual(cat),size);return QPixmap.fromImage(image) if image is not None else QPixmap()
    def build_side(self):
        self.clear_layout(self.side_layout)
        tools=QHBoxLayout();plus=QPushButton('＋ 新增一只');plus.setToolTip(f'再加一只自定义猫（最多 {MAX_CATS} 只），启用后会一起生成。');plus.clicked.connect(self.add_cat);tools.addWidget(plus)
        minus=QPushButton('－ 删除这只');minus.setToolTip('删除当前选中的这一只配置。');minus.clicked.connect(self.remove_cat);minus.setEnabled(len(self.cats)>1);tools.addWidget(minus);self.side_layout.addLayout(tools)
        for i,cat in enumerate(self.cats):
            box=QFrame();box.setObjectName('selectedCard' if i==self.selected else 'catCard');layout=QVBoxLayout(box);layout.setContentsMargins(8,6,8,8);layout.setSpacing(4);check=QCheckBox(f'启用第 {i+1} 只');check.setChecked(cat['enabled']);check.toggled.connect(lambda value,n=i:self.set_enabled(n,value));layout.addWidget(check)
            button=QPushButton(cat.get('name') or f'第 {i+1} 只 · 官方随机名字');button.setIcon(QIcon(self.portrait(cat,82)));button.setIconSize(QSize(82,82));button.setMinimumHeight(86);button.clicked.connect(lambda checked=False,n=i:self.select_cat(n));layout.addWidget(button)
            names=[SKILLS[x['id']]['name']+(' ＋' if x.get('upgraded') else '') for key in SKILL_SLOTS if (x:=cat.get(key)) and x.get('id') in SKILLS];small=QLabel(' / '.join(names) if names else '技能与疾病留空');small.setWordWrap(True);layout.addWidget(small);self.side_layout.addWidget(box)
        self.side_layout.addStretch();count=sum(c.get('enabled',True) for c in self.cats);self.generate.setText(f'备份并生成 {count} 只猫咪')
    def set_enabled(self,n,value):self.cats[n]['enabled']=value;self.changed();self.generate.setText(f"备份并生成 {sum(c.get('enabled',True) for c in self.cats)} 只猫咪")
    def select_cat(self,n):self.selected=n;self.build_side();self.build_editor()
    def add_cat(self):
        if len(self.cats)>=MAX_CATS:QMessageBox.information(self,'已经到上限',f'最多 {MAX_CATS} 只。');return
        cat=default_cat(len(self.cats));cat['enabled']=True;cat['name']=''
        for key in SKILL_SLOTS:cat[key]={'class':'empty','id':None}
        self.cats.append(cat);self.selected=len(self.cats)-1;self.changed();self.build_side();self.build_editor()
        self.status.setText(f'已新增第 {len(self.cats)} 只，配置好再点生成。')
    def remove_cat(self):
        if len(self.cats)<=1:return
        index=self.selected;self.cats.pop(index);self.selected=max(0,min(index,len(self.cats)-1));self.changed();self.build_side();self.build_editor()
    def build_editor(self):
        self.loading=True;self.clear_layout(self.editor_layout);cat=self.cats[self.selected]
        head=QHBoxLayout();portrait=QLabel();portrait.setPixmap(self.portrait(cat,128));portrait.setFixedSize(138,138);head.addWidget(portrait)
        fields=QVBoxLayout();head.addLayout(fields,1);fields.addWidget(QLabel(f'第 {self.selected+1} 只 · 七项基础属性全 7'))
        name=QLineEdit(cat.get('name',''));name.setPlaceholderText('留空使用官方中文随机名字');name.textChanged.connect(lambda t:self.update_cat('name',t));fields.addWidget(name)
        row=QHBoxLayout();fields.addLayout(row);gender=HoverCombo();gender.addItems(['公猫','母猫']);gender.setCurrentIndex(cat['gender']);gender.currentIndexChanged.connect(lambda n:self.update_cat('gender',n));row.addWidget(gender)
        room=HoverCombo()
        for key,label in ROOMS.items():
            if key in self.info['rooms']:room.addItem(label,key)
        room.setCurrentIndex(max(0,room.findData(cat['room'])));room.currentIndexChanged.connect(lambda i:self.update_cat('room',room.itemData(i)));row.addWidget(room);hint=QLabel('全 7 指基础属性；变异和装备仍会产生额外加成。');hint.setWordWrap(True);fields.addWidget(hint);self.editor_layout.addLayout(head)
        tabs=QTabWidget();self.editor_layout.addWidget(tabs);tabs.currentChanged.connect(lambda n:setattr(self,'tab_index',n) if not self.loading else None)
        skills=QWidget();skill_layout=QVBoxLayout(skills)
        disease_box=None;disease_grid=None
        for key, spec in SKILL_SLOTS.items():
            label, kind = spec['label'], spec['kind']
            chosen=cat.get(key) or {'class':'empty','id':None}
            if kind=='diseases':
                if disease_box is None:
                    hint=QLabel('疾病 / 障碍：和技能一起选，最多 2 个，也可以留空。疾病按游戏规则影响猫咪的属性与行为。')
                    hint.setWordWrap(True);hint.setStyleSheet('font-weight:700;color:#2b5c9b;padding:10px 2px 0;');skill_layout.addWidget(hint)
                    disease_box=QGroupBox('疾病 / 障碍 · 可选 2 个');disease_grid=QGridLayout(disease_box);disease_grid.setContentsMargins(8,8,8,8);disease_grid.setSpacing(5);skill_layout.addWidget(disease_box)
                grid=disease_grid;row=grid.rowCount();slot=QLabel(label);slot.setFixedWidth(170);grid.addWidget(slot,row,0)
            else:
                group=QGroupBox(label);grid=QGridLayout(group);grid.setContentsMargins(8,8,8,8);grid.setSpacing(5);row=0
                combo=HoverCombo();combo.setIconSize(QSize(30,30));combo.addItem('空（没有该技能）','empty')
                for cls in DATA['classes']:
                    locked = cls['id'] not in self.info['unlocked']
                    combo.addItem(QIcon(image(cls['image'])),cls['name']+('（未解锁）' if locked else ''),cls['id']);combo.setItemData(combo.count()-1,tooltip(cls),Qt.ToolTipRole)
                combo.view().setMouseTracking(True);combo.setCurrentIndex(max(0,combo.findData(chosen.get('class','empty'))));combo.currentIndexChanged.connect(lambda i,k=key,c=combo:self.set_skill_class(k,c.itemData(i)));combo.setFixedWidth(170);grid.addWidget(combo,row,0)
            entry=SKILLS.get(chosen.get('id'));button=QPushButton();button.setObjectName('skillSquare');button.setFixedSize(68,68);button.setIconSize(QSize(58,58));button.setToolTip(tooltip(entry) if entry else '选择该职业的具体技能')
            if entry:button.setIcon(QIcon(image(entry.get('image',''))))
            else:button.setText('选择' if kind=='diseases' or chosen.get('class')!='empty' else '空')
            button.setEnabled(kind=='diseases' or chosen.get('class')!='empty');button.clicked.connect(lambda checked=False,k=key,t=kind:self.pick_skill(k,t));grid.addWidget(button,row,1)
            upgraded=bool(chosen.get('upgraded')) and kind!='diseases' and bool((entry or {}).get('upgrade'))
            tick=QCheckBox('强化');tick.setChecked(upgraded)
            if kind=='diseases':tick.setEnabled(False);tick.setToolTip('疾病没有强化版本。')
            elif not entry:tick.setEnabled(False);tick.setToolTip('先选择具体技能，再决定是否使用强化版。')
            elif not entry.get('upgrade'):tick.setEnabled(False);tick.setToolTip('这个技能没有强化版本。')
            else:tick.setToolTip('勾选后生成强化版（已升级）：\n'+str(entry['upgrade'].get('description','')))
            tick.toggled.connect(lambda value,k=key:self.set_upgraded(k,value));grid.addWidget(tick,row,2)
            text=skill_blocks(entry,upgraded) if entry else ('可选择疾病，也可留空。' if kind=='diseases' else '先选具体技能，或留空。' if chosen.get('class')!='empty' else '没有该技能。')
            desc=QLabel(text);desc.setTextFormat(Qt.RichText);desc.setWordWrap(True);desc.setToolTip(tooltip(entry) if entry else '');grid.addWidget(desc,row,3);grid.setColumnStretch(3,1)
            if kind!='diseases':skill_layout.addWidget(group)
        skill_layout.addStretch();tabs.addTab(skills,'技能与疾病 · 4 主动 / 2 被动 / 2 疾病')
        body=QWidget();bl=QVBoxLayout(body);bodybutton=QPushButton('打开部位图片面板 · 选择外观与变异');bodybutton.setMinimumHeight(55);bodybutton.clicked.connect(self.customize_body);bl.addWidget(bodybutton)
        summary=QLabel(self.mutation_summary(cat));summary.setWordWrap(True);bl.addWidget(summary);bl.addStretch();tabs.addTab(body,'部位 / 变异')
        equipment=QWidget();el=QGridLayout(equipment);el.setContentsMargins(4,4,4,4);el.setSpacing(8)
        self.set_effect_labels={}
        for number,(kind,label) in enumerate(KINDS.items()):
            box=QGroupBox(label);grid=QGridLayout(box);grid.setContentsMargins(8,9,8,8);grid.setSpacing(5);sets=SetCombo();sets.addItem('全部套装 / 散件','all');sets.addItem('仅散件','loose')
            valid=[s for s in DATA['sets'] if any(ITEMS.get(k,{}).get('kind')==kind for k in s['members'])]
            for suit in valid:
                shown=dict(suit,description=f"{suit['required']} 件套效果：\n"+suit['description']);sets.addItem(QIcon(image(suit['image'])),suit['name']+' ｜ '+str(suit['required'])+'件：'+' '.join(suit['description'].split()),suit['id']);sets.setItemData(sets.count()-1,tooltip(shown),Qt.ToolTipRole)
            sets.setIconSize(QSize(26,26));sets.setCurrentIndex(max(0,sets.findData(cat.get('setFilters',{}).get(kind,'all'))));sets.setToolTip(sets.currentData(Qt.ToolTipRole) or '');sets.currentIndexChanged.connect(lambda i,c=sets,k=kind:self.set_filter(k,c.itemData(i)));grid.addWidget(sets,0,0,1,2)
            effect=QLabel();effect.setWordWrap(True);effect.setMaximumHeight(58);self.set_effect_labels[kind]=effect;grid.addWidget(effect,1,0,1,2);self.update_set_effect(kind,cat.get('setFilters',{}).get(kind,'all'))
            entry=ITEMS.get(cat.get('equipment',{}).get(kind));button=picture_button(entry,'选择具体装备（可空）');button.clicked.connect(lambda checked=False,k=kind:self.pick_item(k));grid.addWidget(button,2,0,1,2)
            desc=QLabel(entry['description'] if entry else '先看套装效果，再选择装备。');desc.setWordWrap(True);desc.setMaximumHeight(48);desc.setToolTip(tooltip(entry) if entry else '');grid.addWidget(desc,3,0,1,2);el.addWidget(box,number//3,number%3)
        for column in range(3):el.setColumnStretch(column,1)
        el.setRowStretch(2,1);tabs.addTab(equipment,'装备 / 套装');self.editor_layout.addStretch();tabs.setCurrentIndex(self.tab_index);self.loading=False
    def update_cat(self,key,value):self.cats[self.selected][key]=value;self.changed()
    def set_skill_class(self,key,cls):
        self.cats[self.selected][key]={'class':cls,'id':None};self.changed();self.build_editor()
    def pick_skill(self,key,kind):
        cat = self.cats[self.selected]
        chosen = cat.get(key) or {'class':'empty','id':None}
        pool = DATA.get(kind, [])
        if kind != 'diseases':
            pool = [entry for entry in pool if entry['class'].casefold()==chosen['class']]
        dlg = Gallery(self, '选择'+SKILL_SLOTS[key]['label'], pool, chosen['id'], upgrades=kind!='diseases')
        if kind!='diseases' and dlg.upgrade_box and chosen.get('upgraded'):dlg.upgrade_box.setChecked(True)
        if dlg.exec()==QDialog.Accepted:
            picked = SKILLS.get(dlg.selected) or {}
            cat[key] = {'class':'disorder' if kind=='diseases' else chosen['class'], 'id':dlg.selected, 'upgraded':bool(kind!='diseases' and dlg.upgraded and picked.get('upgrade'))}
            self.changed()
            self.build_editor()
    def set_upgraded(self,key,value):
        cat=self.cats[self.selected];selection=cat.get(key) or {'class':'empty','id':None};selection['upgraded']=bool(value);cat[key]=selection;self.changed();self.build_editor()
    def update_set_effect(self,kind,chosen):
        label=self.set_effect_labels.get(kind)
        if label is None:return
        suit=next((x for x in DATA['sets'] if x['id']==chosen),None)
        if suit:
            label.setText(f"{suit['required']} 件套："+suit['description']);label.setToolTip(tooltip(suit))
        else:label.setText('展开套装列表，名称后直接显示效果。');label.setToolTip('')
    def set_filter(self,kind,chosen):
        self.cats[self.selected].setdefault('setFilters',{})[kind]=chosen;self.update_set_effect(kind,chosen);self.changed()
    def pick_item(self,kind):
        cat=self.cats[self.selected];filter=cat.get('setFilters',{}).get(kind,'all');pool=[dict(x,name=x['name']+('【任务】' if x.get('quest') else '')) for x in DATA['items'] if x['kind']==kind and x.get('image') and (filter=='all' or filter=='loose' and not x['sets'] or filter in x['sets'])];dlg=Gallery(self,'选择'+KINDS[kind]+'（含任务/支线道具）',pool,cat['equipment'].get(kind),detail_rows=True)
        if dlg.exec()==QDialog.Accepted:cat['equipment'][kind]=dlg.selected;self.changed();self.build_editor()
    def mutation_summary(self,cat):
        mapping={'body':('身体','body'),'head':('头部','head'),'tail':('尾巴','tail'),'leg_back_left':('左后腿','leg'),'leg_back_right':('右后腿','leg'),'arm_front_left':('左前腿','leg'),'arm_front_right':('右前腿','leg'),'ear_left':('左耳','ear'),'ear_right':('右耳','ear'),'eye_left':('左眼','eye'),'eye_right':('右眼','eye'),'eyebrow_left':('左眉','eyebrow'),'eyebrow_right':('右眉','eyebrow'),'mouth':('嘴巴','mouth_closed'),'texture':('毛皮','texture')};lines=[]
        for field,(label,folder) in mapping.items():
            frame=cat['visual'][field];effect=DATA['mutations'].get(folder,{}).get(str(frame));lines.append(f"{label} #{frame}："+(compact_effect(effect['description']) if effect else '正常外观，无额外变异效果。'))
        return '\n\n'.join(lines)
    def customize_body(self):
        cat=self.cats[self.selected];dlg=customize.CustomizeCatDialog(self,self.visual(cat),cat.get('name') or f'第 {self.selected+1} 只');dlg.setWindowTitle('自定义部位与变异 · 悬停图片查看效果')
        if dlg.exec()==QDialog.Accepted:cat['visual']=dataclasses.asdict(dlg.result_visual());self.changed();self.build_editor()
    def call(self,request,callback):
        if self.process:return
        self.request_action=request.get('action','status')
        fd,temp=tempfile.mkstemp(prefix='mew-workbench-',suffix='.json');os.close(fd);self.request_temp=temp;Path(temp).write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8');self.process=QProcess(self);self.process.setWorkingDirectory(str(ROOT));self.process.setProcessEnvironment(__import__('PySide6.QtCore',fromlist=['QProcessEnvironment']).QProcessEnvironment.systemEnvironment());self.generate.setEnabled(False);self.clear.setEnabled(False)
        self.process.finished.connect(lambda code,status:self.finished(temp,callback));self.process.start(CONFIG['python'],['-X','utf8',str(ROOT/'backend.py'),temp])
    def finished(self,temp,callback):
        process=self.process;self.process=None;self.generate.setEnabled(True);self.clear.setEnabled(True)
        try:
            output=bytes(process.readAllStandardOutput()).decode('utf-8');err=bytes(process.readAllStandardError()).decode('utf-8',errors='replace');Path(temp).unlink(missing_ok=True);answer=json.loads(output.splitlines()[-1])
            if not answer.get('ok'):raise ValueError(answer.get('error','操作未完成。'))
            callback(answer)
        except Exception as e:self.status.setText(str(e));QMessageBox.information(self,'操作未完成',str(e))
        process.deleteLater()
    def status_received(self,info):
        self.info=info;self.status.setText(f"当前存档 · 家中 {info['count']} 只猫 · 已解锁 {len(info['unlocked'])}/{len(DATA['classes'])} 个职业 · "+('正在冒险，请先回家保存退出' if info['onAdventure'] else '编辑配置后，退出游戏再生成'));self.build_editor()
    def unlock_all(self):
        answer=QMessageBox.question(self,'解锁所有职业与技能','将把全部职业、全部主动技能和被动技能写入当前存档的解锁表。\n只改解锁表，不动猫咪、装备和冒险进度；操作前自动备份。\n\n请确认游戏已保存并退出。继续解锁？',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if answer==QMessageBox.Yes:self.call({'action':'unlock'},self.unlocked)
    def unlocked(self,result):
        QMessageBox.information(self,'已解锁',result['message']+'\n\n备份位置：'+result['backup']);self.call({'action':'status'},self.status_received)
    def donate_all(self):
        answer=QMessageBox.question(self,'NPC 交猫直接完成','将把各 NPC 的捐献进度直接补到目标值，等于你已经交够了猫和物品。游戏里再去找他们（布恩县的豆博士等）就能领对应奖励，过程中不会消耗任何猫咪。\n只改 NPC 进度，不动猫咪、装备和金币；操作前自动备份。\n\n请确认游戏已保存并退出。继续？',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if answer==QMessageBox.Yes:self.call({'action':'donate'},self.donated)
    def donated(self,result):
        QMessageBox.information(self,'已完成',result['message']+'\n\n备份位置：'+result['backup']);self.call({'action':'status'},self.status_received)
    def helper_pid(self):
        lock=ROOT/'F3助手.lock'
        if not lock.exists():return 0
        try:pid=int(lock.read_text(encoding='utf-8').strip() or 0)
        except (OSError,ValueError):return 0
        if not pid:return 0
        output=subprocess.run(['tasklist','/FI',f'PID eq {pid}','/FO','CSV','/NH'],capture_output=True,text=True,errors='replace').stdout
        return pid if 'python' in output.lower() else 0
    def refresh_helper_button(self):
        if not hasattr(self,'helper_button'):return
        running=bool(self.helper_pid());self.helper_button.setText('F3 助手运行中 · 点击关闭' if running else '启动 F3 助手')
        self.helper_button.setObjectName('primary' if running else '')
        self.helper_button.setStyleSheet('')
    def toggle_helper(self):
        pid=self.helper_pid()
        if pid:
            if QMessageBox.question(self,'停止 F3 助手','F3 助手正在后台运行（托盘有蓝色 F3 图标）。\n要关掉它吗？关掉后 NPC 捐献不会再自动补满。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
                subprocess.run(['taskkill','/PID',str(pid),'/F'],capture_output=True)
                (ROOT/'F3助手.lock').unlink(missing_ok=True)
                self.status.setText('F3 助手已停止。')
                self.refresh_helper_button()
            return
        script=ROOT/'f3_start.py'
        if not script.exists():QMessageBox.information(self,'找不到助手文件',str(script));return
        exe=Path(sys.executable)
        pythonw=exe.with_name('pythonw.exe')
        subprocess.Popen([str(pythonw if pythonw.exists() else exe),'-X','utf8',str(script)],cwd=str(ROOT),creationflags=0x00000008|0x00000200)
        self.status.setText('F3 助手已启动：后台常驻，NPC 捐献会一直保持满。')
        QTimer.singleShot(1500,self.refresh_helper_button)
    def clear_save(self):
        answer=QMessageBox.question(self,'确认备份并清理','将清空当前存档家中所有猫咪和所有非任务装备。\n任务物品、消耗品和猫咪历史保留；操作前自动备份。\n\n请确认游戏已保存并退出。继续清理？',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if answer==QMessageBox.Yes:self.call({'action':'clear'},self.operation_done)
    def generate_cats(self):
        self.write_draft();self.call({'action':'generate','cats':copy.deepcopy(self.cats),'title':self.title.text()},self.generated)
    def generated(self,result):
        self.operation_done(result);self.open_journal()
    def operation_done(self,result):
        self.status.setText(result['message']+'  备份：'+result['backup']);QMessageBox.information(self,'已完成',result['message']+'\n\n备份位置：'+result['backup'])
    def save_preset(self):
        folder=ROOT/'方案模板';folder.mkdir(exist_ok=True);filename,_=QFileDialog.getSaveFileName(self,'保存可复用方案',str(folder/'我的方案.json'),'猫咪方案 (*.json)')
        if filename:Path(filename).write_text(json.dumps({'title':self.title.text(),'cats':self.cats},ensure_ascii=False,indent=2),encoding='utf-8');self.status.setText('方案已保存：'+filename)
    def load_preset(self):
        filename,_=QFileDialog.getOpenFileName(self,'载入方案',str(ROOT/'方案模板'),'猫咪方案 (*.json)')
        if not filename:return
        try:
            saved=json.loads(Path(filename).read_text(encoding='utf-8-sig'));cats=saved['cats'];assert 1<=len(cats)<=MAX_CATS
            self.cats=cats;self.selected=0;self.title.setText(saved.get('title','我的出征方案'));self.build_side();self.build_editor();self.changed()
        except Exception as e:QMessageBox.information(self,'方案无法载入',str(e))
    def open_journal(self):
        exe=Path(CONFIG['journal']).parents[1]/'MewRunJournal.exe'
        if exe.exists():QProcess.startDetached(str(exe),[],str(exe.parent))
    def closeEvent(self,event):
        if self.process:
            if getattr(self,'request_action','status')!='status':
                self.status.setText('正在完成存档操作，请完成后再关闭。');event.ignore();return
            self.process.finished.disconnect();self.process.kill();self.process.waitForFinished(1000);self.process.deleteLater();self.process=None
            if getattr(self,'request_temp',None):Path(self.request_temp).unlink(missing_ok=True)
        self.write_draft();super().closeEvent(event)

STYLE='''QWidget{font-family:"Microsoft YaHei UI";font-size:14px;color:#203047;} QMainWindow{background:#eef2f7;} QLabel#heading{font-size:28px;font-weight:700;} QGroupBox{font-weight:600;border:1px solid #ced8e6;border-radius:9px;margin-top:11px;padding:10px 8px 8px;background:white;} QGroupBox::title{subcontrol-origin:margin;left:12px;} QPushButton{padding:5px;border:1px solid #bfcddd;border-radius:7px;background:white;} QPushButton:hover{background:#edf5ff;border-color:#5b8dd9;} QLineEdit,QComboBox{min-height:25px;padding:3px;background:white;border:1px solid #c4d0de;border-radius:5px;} QFrame#catCard,QFrame#selectedCard{border:1px solid #c9d5e3;border-radius:9px;background:white;} QFrame#selectedCard{border:2px solid #3e7ddb;} QPushButton#primary{background:#2867c6;color:white;font-weight:700;} QPushButton#danger{color:#a53939;} QToolTip{background:#fffbed;color:#17283e;border:1px solid #d3bc7c;padding:10px;font-weight:normal;} QListWidget{background:white;border:1px solid #c7d3e2;} QListWidget::item:selected{background:#dbeaff;color:#153d75;}'''
if __name__=='__main__':
    app=QApplication(sys.argv);lock=QLockFile(str(ROOT/'.workbench.lock'))
    if not lock.tryLock(100):QMessageBox.information(None,'工作台已打开','工作台已经运行，请用 Alt+Tab 切换。');sys.exit(0)
    app.setStyleSheet(STYLE);i18n.init('zh-cn');window=Window();window.show();code=app.exec();lock.unlock();sys.exit(code)
