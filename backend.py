import sys,json,sqlite3,hashlib,shutil,tempfile,os,struct,datetime,base64,random,dataclasses
from pathlib import Path
from contextlib import closing
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import cat_engine as engine
from skill_slots import SKILL_SLOTS
CONFIG=engine.CONFIG
DATA=json.loads((HERE/'workbench.json').read_text(encoding='utf-8'))
ITEMS={x['id']:x for x in DATA['items']}
SKILLS={x['id']:x for kind in ['actives','passives','diseases'] for x in DATA.get(kind,[])}
SLOTS=['head','face','neck','weapon','trinket']
PARTS={'texture':'texture','body':'body','head':'head','tail':'tail','leg1':'leg_back_left','leg2':'leg_back_right','arm1':'arm_front_left','arm2':'arm_front_right','lefteye':'eye_left','righteye':'eye_right','lefteyebrow':'eyebrow_left','righteyebrow':'eyebrow_right','leftear':'ear_left','rightear':'ear_right','mouth':'mouth'}

def status():
    se,cb,hu=engine.api();sp=Path(CONFIG['save'])
    with closing(sqlite3.connect(sp.as_uri()+'?mode=ro',uri=True)) as c:
        cats=engine.owncats(se,c);props=se.get_properties(c);unlocked=sorted(engine.DEFAULT_CLASSES|{x.casefold() for x in se.get_unlocked_classes(c)})
        raw=c.execute("select data from files where key='house_unlocks'").fetchone()[0];rooms=hu.get_unlocked_rooms(hu.parse_house_unlocks(raw)[1]);inv=se.load_inventory_data(c)
    return {'ok':True,'count':len(cats),'unlocked':unlocked,'rooms':list(rooms),'onAdventure':bool(props.get('on_adventure')),'questItems':inv['quest_items'],'save':str(sp)}

def validate(cats,unlocked,rooms):
    pools = {
        kind: {entry['id']: entry for entry in DATA.get(kind, [])}
        for kind in ['actives', 'passives', 'diseases']
    }
    enabled=[x for x in cats if x.get('enabled',True)]
    if not 1<=len(enabled)<=4:raise ValueError('请启用 1～4 只猫咪。')
    for cat in enabled:
        if cat.get('room') not in rooms:raise ValueError('所选房间尚未开放。')
        if cat.get('gender') not in [0,1]:raise ValueError('请选择公猫或母猫。')
        if len(cat.get('name',''))>40:raise ValueError('猫名最多 40 个字符。')
        for key, spec in SKILL_SLOTS.items():
            pool = pools[spec['kind']]
            selection=cat.get(key) or {};skill=selection.get('id');cls=selection.get('class','empty')
            if not skill:continue
            if spec['kind'] == 'diseases':
                if skill not in pool:
                    raise ValueError('请选择疾病列表中的疾病，或留空。')
                continue
            if skill not in pool or pool[skill]['class'].casefold()!=cls:raise ValueError('技能必须来自所选职业的技能池。')
            if selection.get('upgraded') and not pool[skill].get('upgrade'):raise ValueError('该技能没有强化版本，请取消勾选或换一个技能。')
        for slot,key in enumerate(SLOTS):
            gear=cat.get('equipment',{}).get(key)
            if gear and (gear not in ITEMS or ITEMS[gear]['kind']!=key or ITEMS[gear].get('quest')):raise ValueError('装备类型不符，或所选物品属于任务装备。')
        visual=cat.get('visual') or {}
        if any(not isinstance(visual.get(field),int) or not -2<=visual[field]<=2000 for field in PARTS.values()):raise ValueError('部位配置无效，请重新选择外观。')
    return enabled

def make_blob(cb,cat,key,day):
    def edit(blob,fn,*args,**kw):return fn(cb.parse_cat_blob_full(blob),*args,**kw)
    blob=base64.b64decode(engine.CAT['templates'][0])
    for fn in [cb.apply_recall_flags,cb.apply_unretire,cb.apply_remove_all_birth_defects,cb.apply_remove_all_disorders,cb.apply_reset_adventure_counter]:blob=edit(blob,fn)
    for fn,value in [(cb.apply_super_retired,0),(cb.apply_life_state,0),(cb.apply_level_edit,0),(cb.apply_gender_code,cat['gender'])]:blob=edit(blob,fn,value)
    blob=edit(blob,cb.apply_age_days,day,5);blob=edit(blob,cb.apply_stat_edits,new_base=[7]*7,new_bonus=[0]*7,new_extra=[0]*7)
    visual=cat['visual'];blob=edit(blob,cb.apply_mutation_edits,{part:visual[field] for part,field in PARTS.items()})
    blob=edit(blob,cb.apply_visual_globals_edit,palette=visual.get('palette',0),class_palette=visual.get('class_palette',4294967295),claws=visual.get('claws',0))
    for slot,kind in enumerate(SLOTS):blob=cb.apply_item_edit(blob,slot,cat.get('equipment',{}).get(kind) or 'None')
    desired = {f'ability_{i}': 'None' for i in range(14)}
    desired.update({
        'ability_0': 'DefaultMove',
        'ability_1': 'BasicMelee',
        'class': 'Colorless',
        'voice': 'male11' if cat['gender'] == 0 else 'female54',
    })
    for key, spec in SKILL_SLOTS.items():
        selection = cat.get(key) or {}
        ability = selection.get('id') or 'None'
        if selection.get('upgraded') and spec['kind'] == 'actives':
            ability = (SKILLS.get(selection.get('id')) or {}).get('upgrade', {}).get('id') or ability
        for slot in spec['slots']:
            desired[f'ability_{slot}'] = ability
    parsed = cb.parse_cat_blob_full(blob)
    blob = cb.apply_all_edits(parsed, {
        field.index: desired[field.semantic]
        for field in parsed.string_fields if field.semantic in desired
    })
    tiers = {slot: 1 for slot in range(10, 14)}
    for key, spec in SKILL_SLOTS.items():
        selection = cat.get(key) or {}
        if spec['kind'] == 'passives' and selection.get('upgraded'):
            for slot in spec['slots']:
                tiers[slot] = 2
    for slot in range(10, 14):
        blob = edit(blob, cb.apply_passive_tier_edit, slot, tiers[slot])
    blob=edit(blob,cb.apply_personality_edits,libido=1.0,sexuality=0.0,lover_key=0,hater_key=0,aggression=0.0,sociability=1.0,mood=1.0,affinity=1.0)
    blob=edit(blob,cb.apply_unretire);name=cat.get('name','').strip() or engine.draw_name(random.SystemRandom(),cat['gender']);blob=edit(blob,cb.apply_name_edit,name)
    detail=engine.api()[0].parse_cat_details(blob);assert detail['base_stats']==[7]*7 and not detail['retired']
    return blob,name

def clear_stage(se,cb,c):
    import core.inventory_manager as im
    owned=engine.owncats(se,c);quest=set(DATA['questNames']);inv=se.load_inventory_data(c);quest.update(inv['quest_items'])
    for cat in owned:
        worn=[x.item_name for x in cat['_full_parsed'].item_slots if x.has_item and x.item_name in quest]
        if worn:raise ValueError(f"{cat['name']} 身上有任务物品，请先在游戏中卸到仓库，再清理，以保留任务物品的原始状态。")
    hs=c.execute("select data from files where key='house_state'").fetchone()[0]
    for cat in owned:
        blob=c.execute('select data from cats where key=?',(cat['key'],)).fetchone()[0]
        for slot in range(5):blob=cb.apply_item_edit(blob,slot,'None')
        parsed=cb.parse_cat_blob_full(blob);raw=bytearray(parsed.raw_data);off=parsed.pre_meta_offset+cb.CAT_RETIRED_COUNTER_INDEX*4
        struct.pack_into('<I',raw,off,struct.unpack_from('<I',raw,off)[0]|cb.CAT_TRASHED_FLAG_MASK)
        c.execute('update cats set data=? where key=?',(cb.pack_blob(bytes(raw),parsed.is_compressed),cat['key']));hs=se.remove_cat_from_house_state(hs,cat['key'])
    c.execute("update files set data=? where key='house_state'",(hs,));removed=0
    for inventory in ['inventory_storage','inventory_backpack','inventory_trash']:
        row=c.execute('select data from files where key=?',(inventory,)).fetchone()
        if not row:continue
        entries,tail=im._parse_inventory_blob(row[0],inventory_key=inventory);kept=[]
        for entry in entries:
            known=ITEMS.get(entry['name']);isquest=im._entry_is_quest(entry,quest) or entry['name'] in quest
            if known and not isquest:removed+=1
            else:kept.append(entry)
        c.execute('update files set data=? where key=?',(im._build_inventory_blob(kept,tail),inventory))
    c.commit();assert not engine.owncats(se,c)
    return {'clearedCats':len(owned),'removedEquipment':removed}

def unlock_all(se,stage):
    with closing(sqlite3.connect(stage)) as c:
        before=engine.snap(c);categories=se.get_all_unlocked_categories(c)
        cache_counts={'cats':len(before['cats'])}
    class_ids=sorted(set(categories[0])|{entry['id'].capitalize() for entry in DATA['classes']})
    active_ids=sorted(set(categories[1])|{entry['id'] for entry in DATA['actives']})
    passive_ids=sorted(set(categories[2])|{entry['id'] for entry in DATA['passives']})
    se.save_all_changes(stage,unlock_updates={0:class_ids,1:active_ids,2:passive_ids})
    with closing(sqlite3.connect(stage)) as c:
        after_categories=se.get_all_unlocked_categories(c);after=engine.snap(c)
        assert set(class_ids)<=set(after_categories[0]) and set(active_ids)<=set(after_categories[1]) and set(passive_ids)<=set(after_categories[2])
        assert all(categories[index]==after_categories[index] for index in range(3,len(categories)))
        ignore={'save_editor_name','save_editor_version','save_editor_tables_touched'}
        assert {k:v for k,v in before['properties'].items() if k not in ignore}=={k:v for k,v in after['properties'].items() if k not in ignore}
        assert {k:v for k,v in before['files'].items() if k!='unlocks'}=={k:v for k,v in after['files'].items() if k!='unlocks'}
        assert before['cats']==after['cats'] and before['furniture']==after['furniture'] and before['winning_teams']==after['winning_teams']
        assert len(after['cats'])==cache_counts['cats']
        assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
    return {'unlockedClasses':len(after_categories[0]),'unlockedActives':len(after_categories[1]),'unlockedPassives':len(after_categories[2])}

def donate_complete(stage):
    import core.npc_progress_parser as npc
    with closing(sqlite3.connect(stage)) as c:
        before=engine.snap(c)
        row=c.execute("select data from files where key='npc_progress'").fetchone()
    if not row:raise ValueError('这份存档没有 NPC 进度数据。')
    blob=row[0];data=npc.parse_npc_progress(blob)
    if not data.counter_editable:raise ValueError('这份存档的 NPC 计数器不可写，已停止。')
    plan={};report=[]
    for counter in data.donation_counters:
        target=int(counter.target or 0)
        if target<=0 or counter.value>=target:continue
        plan[counter.npc]=target;report.append({'npc':counter.npc,'quest':counter.quest_name,'from':counter.value,'to':target})
    if not plan:return {'npcUpdates':[],'message':'所有 NPC 的捐献进度都已经满了，没有改动。'}
    new_blob=npc.set_npc_donation_counters(blob,plan)
    values={counter.npc:counter.value for counter in npc.parse_npc_progress(new_blob).donation_counters}
    for name,target in plan.items():assert values.get(name,0)>=target,name
    with closing(sqlite3.connect(stage)) as c:
        c.execute("update files set data=? where key='npc_progress'",(new_blob,));c.commit()
        after=engine.snap(c)
        assert {k:v for k,v in before['files'].items() if k!='npc_progress'}=={k:v for k,v in after['files'].items() if k!='npc_progress'}
        assert before['cats']==after['cats'] and before['properties']==after['properties'] and before['furniture']==after['furniture'] and before['winning_teams']==after['winning_teams']
        assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
    return {'npcUpdates':report,'message':'已把 '+'、'.join(f"{item['npc']} {item['to']}/{item['to']}" for item in report)+' 的捐献进度补满；相当于已经交够猫和物品，没有消耗猫咪。'}

def donate_direct(backup=True):
    """游戏运行中也能用的就地补满：只改 npc_progress，写前复制一份备份。"""
    import core.npc_progress_parser as npc
    engine.api()
    sp=Path(CONFIG['save'])
    if backup:
        root=Path(CONFIG['backupRoot']);root.mkdir(parents=True,exist_ok=True)
        target=root/('hotkey-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        target.mkdir(parents=True,exist_ok=True);shutil.copy2(sp,target/sp.name)
    last=''
    for attempt in range(8):
        try:
            with closing(sqlite3.connect(str(sp),timeout=4)) as c:
                row=c.execute("select data from files where key='npc_progress'").fetchone()
                if not row:return {'ok':False,'changed':False,'message':'存档里没有 NPC 进度数据。'}
                data=npc.parse_npc_progress(row[0])
                plan={counter.npc:int(counter.target) for counter in data.donation_counters if counter.target and counter.value<int(counter.target)}
                if not plan:return {'ok':True,'changed':False,'message':'NPC 捐献进度已经是满的。'}
                blob=npc.set_npc_donation_counters(row[0],plan)
                c.execute("update files set data=? where key='npc_progress'",(blob,));c.commit()
            return {'ok':True,'changed':True,'message':'已补满 '+'、'.join(f'{name} {value}/{value}' for name,value in plan.items())}
        except sqlite3.OperationalError as error:
            last=str(error)
            if 'locked' in last.lower() or 'busy' in last.lower():time.sleep(1.2);continue
            raise
    return {'ok':False,'changed':False,'message':'存档被游戏占用，稍后自动重试：'+last}

def operate(req):
    action=req.get('action','status')
    if action=='status':return status()
    engine.closed();se,cb,hu=engine.api();sp=Path(CONFIG['save']);info=status()
    if info['onAdventure']:raise ValueError('请先结束冒险回家、保存并退出游戏。')
    cats=validate(req.get('cats',[]),info['unlocked'],info['rooms']) if action=='generate' else []
    if action not in ['generate','clear','unlock','donate']:raise ValueError('不支持的操作。')
    oldhash=hashlib.sha256(sp.read_bytes()).hexdigest();stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');backup=Path(CONFIG['backupRoot'])/stamp;backup.mkdir(parents=True)
    with closing(sqlite3.connect(sp.as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(backup/sp.name)) as dst:src.backup(dst)
    fd,temp=tempfile.mkstemp(prefix='cat-workbench-',suffix='.sav',dir=sp.parent);os.close(fd);stage=Path(temp);shutil.copy2(backup/sp.name,stage)
    made=[];result={}
    try:
        if action=='unlock':result=unlock_all(se,stage)
        elif action=='donate':result=donate_complete(stage)
        else:
            with closing(sqlite3.connect(stage)) as c:
                before=engine.snap(c);day=int(se.get_properties(c)['current_day'])
                if action=='clear':result=clear_stage(se,cb,c)
                else:
                    hs=before['files']['house_state']
                    for config in cats:
                        key=int(c.execute('select coalesce(max(key),0)+1 from cats').fetchone()[0]);blob,name=make_blob(cb,config,key,day)
                        actual=c.execute('insert into cats(data) values(?)',(blob,)).lastrowid;assert actual==key
                        hs=se.add_cat_to_house_state(hs,key,room=config['room'],position=(random.uniform(-4,4),1.0,3.0));made.append({'key':key,'name':name,'config':config})
                    c.execute("update files set data=? where key='house_state'",(hs,));se._maybe_grow_pedigree_after_cat_insert(c);c.commit()
                after=engine.snap(c)
                for table in ['furniture','winning_teams','properties']:assert before[table]==after[table],table
                if action=='generate':assert all(after['cats'][key]==blob for key,blob in before['cats'].items())
                assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
        if se.validate_save_integrity(stage):raise ValueError('存档校验失败，已停止写入。')
        engine.closed()
        if hashlib.sha256(sp.read_bytes()).hexdigest()!=oldhash:raise ValueError('存档在操作期间发生变化，请重新读取。')
        os.replace(stage,sp)
    finally:
        if stage.exists():stage.unlink()
    result.update({'ok':True,'backup':str(backup),'added':len(made),'cats':made})
    if action=='generate':
        record={'id':stamp,'title':req.get('title','自定义出征方案'),'created':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'save':str(sp),'cats':made}
        folder=HERE/'出征方案';folder.mkdir(exist_ok=True);(folder/(stamp+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        result['message']=f'已生成 {len(made)} 只自定义全7猫，出征方案已保存。'
    elif action=='clear':result['message']=f"已清空 {result['clearedCats']} 只家中猫咪及 {result['removedEquipment']} 件非任务装备；任务物品、消耗品和历史记录保留。"
    elif action=='unlock':result['message']=f"已解锁 {result['unlockedClasses']} 个职业、{result['unlockedActives']} 个主动技能和 {result['unlockedPassives']} 个被动技能；猫咪、装备和进度未变。"
    (backup/'操作记录.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result

if __name__=='__main__':
    try:print(json.dumps(operate(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))),ensure_ascii=False))
    except Exception as e:print(json.dumps({'ok':False,'error':str(e)},ensure_ascii=False));sys.exit(1)
