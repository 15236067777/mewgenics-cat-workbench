import sys,json,sqlite3,hashlib,shutil,tempfile,os,struct,datetime,base64,random,dataclasses
from pathlib import Path
from contextlib import closing
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import cat_engine as engine
CONFIG=engine.CONFIG
DATA=json.loads((HERE/'workbench.json').read_text(encoding='utf-8'))
ITEMS={x['id']:x for x in DATA['items']}
SLOTS=['head','face','neck','weapon','trinket']
PARTS={'texture':'texture','body':'body','head':'head','tail':'tail','leg1':'leg_back_left','leg2':'leg_back_right','arm1':'arm_front_left','arm2':'arm_front_right','lefteye':'eye_left','righteye':'eye_right','lefteyebrow':'eyebrow_left','righteyebrow':'eyebrow_right','leftear':'ear_left','rightear':'ear_right','mouth':'mouth'}

def status():
    se,cb,hu=engine.api();sp=Path(CONFIG['save'])
    with closing(sqlite3.connect(sp.as_uri()+'?mode=ro',uri=True)) as c:
        cats=engine.owncats(se,c);props=se.get_properties(c);unlocked=sorted(engine.DEFAULT_CLASSES|{x.casefold() for x in se.get_unlocked_classes(c)})
        raw=c.execute("select data from files where key='house_unlocks'").fetchone()[0];rooms=hu.get_unlocked_rooms(hu.parse_house_unlocks(raw)[1]);inv=se.load_inventory_data(c)
    return {'ok':True,'count':len(cats),'unlocked':unlocked,'rooms':list(rooms),'onAdventure':bool(props.get('on_adventure')),'questItems':inv['quest_items'],'save':str(sp)}

def validate(cats,unlocked,rooms):
    active={x['id']:x for x in DATA['actives']};passive={x['id']:x for x in DATA['passives']}
    enabled=[x for x in cats if x.get('enabled',True)]
    if not 1<=len(enabled)<=4:raise ValueError('请启用 1～4 只猫咪。')
    for cat in enabled:
        if cat.get('room') not in rooms:raise ValueError('所选房间尚未开放。')
        if cat.get('gender') not in [0,1]:raise ValueError('请选择公猫或母猫。')
        if len(cat.get('name',''))>40:raise ValueError('猫名最多 40 个字符。')
        for key,pool in [('active1',active),('active2',active),('passive',passive)]:
            selection=cat.get(key) or {};skill=selection.get('id');cls=selection.get('class','empty')
            if not skill:continue
            if skill not in pool or cls not in unlocked or pool[skill]['class'].casefold()!=cls:raise ValueError('技能必须来自所选已解锁职业的技能池。')
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
    desired={f'ability_{i}':'None' for i in range(14)};a=(cat.get('active1') or {}).get('id') or 'None';b=(cat.get('active2') or {}).get('id') or 'None';p=(cat.get('passive') or {}).get('id') or 'None'
    desired.update({'ability_0':'DefaultMove','ability_1':'BasicMelee','ability_2':a,'ability_3':b,'ability_6':a,'ability_7':b,'ability_10':p,'class':'Colorless','voice':'male11' if cat['gender']==0 else 'female54'})
    parsed=cb.parse_cat_blob_full(blob);blob=cb.apply_all_edits(parsed,{x.index:desired[x.semantic] for x in parsed.string_fields if x.semantic in desired});blob=edit(blob,cb.apply_passive_tier_edit,10,1)
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

def operate(req):
    action=req.get('action','status')
    if action=='status':return status()
    engine.closed();se,cb,hu=engine.api();sp=Path(CONFIG['save']);info=status()
    if info['onAdventure']:raise ValueError('请先结束冒险回家、保存并退出游戏。')
    cats=validate(req.get('cats',[]),info['unlocked'],info['rooms']) if action=='generate' else []
    if action not in ['generate','clear']:raise ValueError('不支持的操作。')
    oldhash=hashlib.sha256(sp.read_bytes()).hexdigest();stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');backup=Path(CONFIG['backupRoot'])/stamp;backup.mkdir(parents=True)
    with closing(sqlite3.connect(sp.as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(backup/sp.name)) as dst:src.backup(dst)
    fd,temp=tempfile.mkstemp(prefix='cat-workbench-',suffix='.sav',dir=sp.parent);os.close(fd);stage=Path(temp);shutil.copy2(backup/sp.name,stage)
    made=[];result={}
    try:
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
    else:result['message']=f"已清空 {result['clearedCats']} 只家中猫咪及 {result['removedEquipment']} 件非任务装备；任务物品、消耗品和历史记录保留。"
    (backup/'操作记录.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result

if __name__=='__main__':
    try:print(json.dumps(operate(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))),ensure_ascii=False))
    except Exception as e:print(json.dumps({'ok':False,'error':str(e)},ensure_ascii=False));sys.exit(1)
