import sys,json,sqlite3,datetime,importlib.abc,importlib.util,hashlib,os,csv,io
from pathlib import Path
from contextlib import closing
sys.stdout.reconfigure(encoding='utf-8')
HERE=Path(__file__).resolve().parent
CONFIG=json.loads((HERE/'settings.json').read_text(encoding='utf-8-sig'))
LABELS=json.loads((HERE/'labels.json').read_text(encoding='utf-8-sig'))
CLASSES={'colorless':'无职业','fighter':'战士','hunter':'猎手','mage':'法师','medic':'牧师','tank':'坦克','thief':'盗贼','necromancer':'死灵法师','monk':'武僧','butcher':'屠户','druid':'德鲁伊','tinkerer':'工匠','psychic':'灵能士','jester':'小丑'}

def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')
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
    import core.save_editor as se,core.adventure_state_editor as adv
    return se,adv

def cat_view(d):
    p=d.get('_full_parsed')
    return {k:d.get(k) for k in ['key','name','cat_class','gender','base_stats','bonus_stats','extra_stats','abilities','dead','retired','life_state','in_house','room','donated','trashed']}|{'equipment':[x.item_name if x.has_item else '' for x in p.item_slots] if p else [],'mutations':dict(p.mutation_data.mutations) if p and p.mutation_data else {}}

def read_sample(path):
    se,adv=api();p=Path(path).resolve(strict=True)
    # Never open the source in a write-capable mode, even during game autosaves.
    with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=2)) as c:
        c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
        props=se.get_properties(c);row=c.execute("select data from files where key='adventure_state'").fetchone()
        state=adv.parse_adventure_state(row[0]) if row else None
        on=bool(props.get('on_adventure'));ids=[int(x) for x in state.header_ids if x>0] if state and on else []
        cats=[cat_view(d) for d in se.get_all_cat_details(c) if d.get('source')=='cats']
        roster={d['key']:d for d in cats}
        if on and (not ids or any(x not in roster for x in ids)):raise ValueError('出征存档尚未写完整，等待下一次自动保存。')
        if state and on and state.parse_warnings:raise ValueError('出征信息尚不完整，等待下一次自动保存。')
        party=[roster[i] for i in ids]
        if state and len(state.classes)==len(party):
            party=[dict(cat,cat_class=cls) for cat,cls in zip(party,state.classes)]
        return {'save':str(p),'observed':now(),'on':on,'day':int(props.get('current_day',0)),'timer':float(props.get('savefile_timer',0)),'party':party,'cats':cats,'team':state.team_name if state and on else '', 'tokens':list(state.tokens) if state and on else [],'weathers':list(state.weathers) if state and on else []}

def database():
    path=HERE/'记录'/'出征日记.sqlite3';path.parent.mkdir(exist_ok=True)
    c=sqlite3.connect(path);c.row_factory=sqlite3.Row
    c.executescript('CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,save TEXT NOT NULL,start TEXT NOT NULL,end TEXT,result TEXT NOT NULL,manual TEXT,detail TEXT NOT NULL); CREATE TABLE IF NOT EXISTS state(save TEXT PRIMARY KEY,sample TEXT NOT NULL,active INTEGER);')
    return c

def note(detail,text,at):
    if not detail['events'] or detail['events'][-1]['text']!=text:detail['events'].append({'time':at,'text':text})

def matching_preparation(sample):
    folder=Path(CONFIG.get('preparations',str(HERE.parent/'出征方案')))
    ids={x['key'] for x in sample['party']}
    if not ids or not folder.is_dir():return None
    for path in sorted(folder.glob('*.json'),reverse=True):
        try:
            plan=json.loads(path.read_text(encoding='utf-8'))
            if str(Path(plan['save']).resolve())!=sample['save']:continue
            prepared={int(x['key']):x for x in plan['cats']}
            if ids<=set(prepared) and all(prepared[x['key']]['name']==x['name'] for x in sample['party']):
                return {'id':plan['id'],'title':plan['title'],'cats':[x for x in plan['cats'] if int(x['key']) in ids]}
        except (ValueError,KeyError,TypeError,OSError):continue
    return None

def finish(c,run,sample,result):
    detail=json.loads(run['detail']);byid={d['key']:d for d in sample['cats']}
    detail['endParty']=[byid.get(d['key'],{'key':d['key'],'name':d['name'],'missing':True}) for d in detail['startParty']]
    note(detail,result,sample['observed'])
    c.execute('update runs set end=?,result=?,detail=? where id=?',(sample['observed'],result,json.dumps(detail,ensure_ascii=False),run['id']))

def observe(c,sample):
    path=sample['save'];state=c.execute('select * from state where save=?',(path,)).fetchone();prev=json.loads(state['sample']) if state else None
    active=c.execute('select * from runs where id=?',(state['active'],)).fetchone() if state and state['active'] else None
    backwards=prev and (sample['day']<prev['day'] or sample['timer']+1<prev['timer'])
    if active:
        detail=json.loads(active['detail']);beforeids=[x['key'] for x in detail['startParty']];afterids=[x['key'] for x in sample['party']]
        if not sample['on']:
            byid={x['key']:x for x in sample['cats']}
            all_dead=bool(beforeids) and all(i in byid and byid[i].get('dead') is True for i in beforeids)
            result='回档后中断（待确认）' if backwards else '团灭（存档判定）' if all_dead else '已回家（结果待确认）'
            finish(c,active,sample,result);active=None
        elif not set(afterids).issubset(set(beforeids)):
            finish(c,active,sample,'监控间隔中队伍已更换（待确认）');active=None
        else:
            if backwards:note(detail,'检测到存档回退／SL，继续归入本次出征。',sample['observed'])
            oldids={x['key'] for x in detail['latestParty']}
            if oldids!=set(afterids):note(detail,'出征队伍成员发生变化。',sample['observed'])
            detail['latestParty']=sample['party'];detail['lastSeen']=sample['observed'];detail['tokens']=sample['tokens'];detail['weathers']=sample['weathers']
            c.execute('update runs set detail=? where id=?',(json.dumps(detail,ensure_ascii=False),active['id']))
    if sample['on'] and not active:
        partial=prev is None or prev['on'];detail={'startParty':sample['party'],'latestParty':sample['party'],'startDay':sample['day'],'team':sample['team'],'partial':partial,'lastSeen':sample['observed'],'events':[],'tokens':sample['tokens'],'weathers':sample['weathers']}
        preparation=matching_preparation(sample)
        if preparation:
            detail['preparation']=preparation
            note(detail,'关联自定义配置：'+preparation['title']+f"（本次实际出征 {len(sample['party'])} 只）",sample['observed'])
        note(detail,'中途开始观察：出发时的完整状态可能未记录。' if partial else '观察到新的出征。',sample['observed'])
        rid=c.execute('insert into runs(save,start,result,detail) values(?,?,?,?)',(path,sample['observed'],'出征中',json.dumps(detail,ensure_ascii=False))).lastrowid
    else:rid=active['id'] if active else None
    # Keep the last known roster to preserve cats lost during later adventures.
    c.execute('insert into state(save,sample,active) values(?,?,?) on conflict(save) do update set sample=excluded.sample,active=excluded.active',(path,json.dumps(sample,ensure_ascii=False),rid));c.commit()

def run_view(row):
    d=dict(row);d['detail']=json.loads(d['detail']);return d

def operate(req):
    action=req.get('action','poll');path=req.get('save',CONFIG['save'])
    with closing(database()) as c:
        if action=='set_result':
            result=req['result'];allowed={'胜利／通关','撤退回家','团灭','回档／放弃','待确认'}
            if result not in allowed:raise ValueError('请选择有效的结果。')
            row=c.execute('select * from runs where id=?',(int(req['id']),)).fetchone()
            if not row:raise ValueError('该记录不存在。')
            if row['end'] is None:raise ValueError('该队伍仍在出征中，请结束后再标注。')
            c.execute('update runs set manual=? where id=?',(None if result=='待确认' else result,row['id']));c.commit()
        message=''
        if action=='poll':
            try:sample=read_sample(path);observe(c,sample);message=f"监控中 · 游戏第 {sample['day']} 天 · "+('正在出征' if sample['on'] else '家中')
            except Exception as e:message='等待存档：'+str(e)
        records=[run_view(x) for x in c.execute('select * from runs where save=? order by id desc',(str(Path(path).resolve()),))]
        return {'ok':True,'message':message,'records':records,'directory':str(HERE/'记录'),'save':path}

if __name__=='__main__':
    try:print(json.dumps(operate(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))),ensure_ascii=False))
    except Exception as e:print(json.dumps({'ok':False,'error':str(e)},ensure_ascii=False));sys.exit(1)
