from pathlib import Path
import sys,json,struct,csv,io,re,collections,os
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'vendor'))
import editor_bridge
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from PySide6.QtCore import Qt,QRectF
os.environ['QT_QPA_PLATFORM']='offscreen';app=QApplication([])
from catface import Swf,Faces
from gon_parser import parse_gon
import data.ability_descriptions as ad,data.mutation_descriptions as md
cfg=json.loads((ROOT/'settings.json').read_text(encoding='utf-8'));base=Path(cfg['game'])
f=(base/'resources.gpak').open('rb');entries=[]
for _ in range(struct.unpack('<I',f.read(4))[0]):
 n=struct.unpack('<H',f.read(2))[0];name=f.read(n).decode();size=struct.unpack('<I',f.read(4))[0];entries.append((name,size))
offset=f.tell();index={}
for name,size in entries:index[name]=(offset,size);offset+=size
def raw(name,overlay=True):
 for directory in reversed(cfg.get('overlays',[])):
  p=Path(directory)/name
  if overlay and p.is_file():return p.read_bytes()
 pos,n=index[name];f.seek(pos);return f.read(n)
texts={row['KEY']:row for row in csv.DictReader(io.StringIO(raw('data/text/combined.csv').decode('utf-8-sig')))}
def tr(key,default=''):
 if not isinstance(key,str):return default
 row=texts.get(key,{});t=row.get('zh-cn') or row.get('en') or default
 t=re.sub(r'\[img:([^\]]+)\]',lambda m:{'str':'力量','dex':'敏捷','con':'体质','int':'智力','spd':'速度','cha':'魅力','lck':'幸运','hp':'生命','mana':'法力'}.get(m[1],m[1]),t)
 return re.sub(r'\[/?[a-z]+(?::[^\]]*)?\]','',t).replace('\\n','\n').replace('\ufeff','').replace('\u200b','')
groups={k:{} for k in ['abilities','passives','items','mutations','classes']};quest=set()
for name in index:
 if not name.endswith('.gon'):continue
 kind=next((k for k in groups if name.startswith('data/'+k+'/')),None)
 if kind:
  try:parsed=parse_gon(raw(name).decode('utf-8-sig'));groups[kind].update(parsed)
  except Exception:continue
  if kind=='items' and any(x in name for x in ['beanies_quest','legacy_quest']):quest.update(parsed)
sets=parse_gon(raw('data/item_setbonuses.gon').decode('utf-8-sig'))
defs={};ability=Swf(raw('swfs/ability_icons.swf'),defs,'a',False);parts=Swf(raw('swfs/catparts.swf'),defs,'p',False);ui=Swf(raw('swfs/ui.swf'),defs,'u',False)
icons=ROOT/'images';icons.mkdir(exist_ok=True);stats={'rendered':0,'missing':[]};cache={}
def icon(doc,symbol,frame,key):
 if not symbol:return ''
 cachekey=(doc.px,symbol,frame)
 if cachekey in cache:return cache[cachekey]
 try:
  data=Faces._icon(doc,symbol,frame)
  if not data:return ''
  vb,mk=data;used=set();todo=re.findall(r'(?:href=["\']#|url\(#)([\w-]+)',mk)
  while todo:
   ident=todo.pop()
   if ident in used:continue
   used.add(ident);todo.extend(re.findall(r'(?:href=["\']#|url\(#)([\w-]+)',defs.get(ident,'')))
  svg=f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="{vb}" width="100" height="100"><style>.ln{{fill:none;stroke-linecap:round;stroke-linejoin:round}}</style><defs>'+''.join(defs.get(i,'') for i in used)+'</defs>'+mk+'</svg>'
  svg=svg.replace('href=', 'xlink:href=')
  im=QImage.fromData(svg.encode(),'SVG')
  if im.isNull():return ''
  filename=re.sub(r'[^a-zA-Z0-9_-]','_',key)+'.png';im.save(str(icons/filename));cache[cachekey]='images/'+filename;stats['rendered']+=1;return cache[cachekey]
 except Exception as e:stats['missing'].append([key,str(e)[:80]]);return ''
catalog=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))
for category,pool_key,kind in [('actives','ability_pool','abilities'),('passives','passive_pool','passives')]:
 catalog[category]=[];seen=set()
 for cls,definition in groups['classes'].items():
  if not isinstance(definition,dict):continue
  for ident in definition.get(pool_key,[]):
   if not isinstance(ident,str) or (ident,cls.lower()) in seen:continue
   seen.add((ident,cls.lower()));block=groups[kind].get(ident,{})
   if not isinstance(block,dict):continue
   meta=block.get('meta') if isinstance(block.get('meta'),dict) else block
   key=meta.get('name');name=tr(key,key if isinstance(key,str) and key not in texts and not key.isupper() else ident)
   catalog[category].append({'id':ident,'name':name,'class':cls.lower()})
result={'actives':[],'passives':[],'items':[],'sets':[],'classes':[],'mutations':{},'questNames':sorted(quest),'source':'本机 resources.gpak + 用户选定的模组覆盖数据'}
for kind,symbol,group in [('actives','AbilityIcon','abilities'),('passives','PassiveIcon','passives')]:
 frames=ability.labels(ability.sym[symbol])
 for entry in catalog[kind]:
  cls=next((v for c,v in groups['classes'].items() if c.casefold()==entry['class'].casefold() and isinstance(v,dict)),{})
  if entry['id'] not in cls.get('ability_pool' if kind=='actives' else 'passive_pool',[]):continue
  k=entry['id'];b=groups[group].get(k,{});b=b if isinstance(b,dict) else {};meta=b.get('meta',{}) if isinstance(b.get('meta'),dict) else b;level=b.get('1',{}) if isinstance(b.get('1'),dict) else {}
  desc=tr(meta.get('desc') or level.get('desc') or b.get('desc'),getattr(ad,'ABILITY_DESCRIPTIONS',{}).get(k,''))
  label=next((x for x in [str(meta.get('icon','')),str(b.get('icon','')),k,re.sub(r'\d+$','',k)] if x in frames),None)
  img=icon(ability,ability.sym[symbol],frames[label],kind+'-'+k) if label else ''
  result[kind].append(dict(entry,description=desc or '游戏未提供文字说明。',image=img))

from ability_details import combat_summary
templates = parse_gon(raw('data/ability_templates/ability_templates.gon').decode('utf-8-sig'))
for entry in result['actives']:
    summary = combat_summary(entry['id'], groups['abilities'], templates)
    entry['combatSummary'] = summary
    entry['description'] = summary + '\n' + entry['description']

for entry in result['actives']:
    variant_id = entry['id'] + '2'
    variant = groups['abilities'].get(variant_id)
    if not isinstance(variant, dict):
        continue
    meta = variant.get('meta') if isinstance(variant.get('meta'), dict) else variant
    summary = combat_summary(variant_id, groups['abilities'], templates)
    text = tr(meta.get('desc'), '')
    if not text and '\n' in entry['description']:
        text = entry['description'].split('\n', 1)[1]
    entry['upgrade'] = {'id': variant_id, 'name': entry['name'], 'combatSummary': summary, 'description': summary + '\n' + text, 'image': entry['image']}
for entry in result['passives']:
    definition = groups['passives'].get(entry['id'])
    tier = definition.get('2') if isinstance(definition, dict) else None
    if not isinstance(tier, dict):
        continue
    text = tr(tier.get('desc'), '')
    if not text:
        continue
    entry['upgrade'] = {'id': entry['id'], 'tier': 2, 'name': entry['name'], 'description': text, 'image': entry['image']}

import core.cat_blob_editor as cb
result['diseases'] = []
disease_frames = ability.labels(ability.sym['PassiveIcon'])
known_disorders = cb.DISORDER_PASSIVES | cb.BIRTH_DEFECT_PASSIVES
for ident, definition in groups['passives'].items():
    if not isinstance(definition, dict):
        continue
    if definition.get('class') != 'Disorder' and ident not in known_disorders:
        continue
    label = next((candidate for candidate in [definition.get('icon'), ident] if candidate in disease_frames), None)
    picture = icon(ability, ability.sym['PassiveIcon'], disease_frames[label], 'disease-' + ident) if label else ''
    description = tr(definition.get('desc'), getattr(ad, 'ABILITY_DESCRIPTIONS', {}).get(ident, ''))
    result['diseases'].append({
        'id': ident,
        'class': 'disorder',
        'name': tr(definition.get('name'), ident),
        'description': description or '游戏未提供文字说明。',
        'image': picture,
    })
result['diseases'].sort(key=lambda entry: entry['name'])

for k,b in groups['items'].items():
 if not isinstance(b,dict) or b.get('kind') not in ['head','face','neck','weapon','trinket']:continue
 kind=b['kind'];symbol={'head':'HeadItemIcon','face':'FaceItemIcon','neck':'NeckItemIcon','weapon':'WeaponIcon','trinket':'TrinketIcon'}[kind]
 try:frame=int(b.get('frame','0'))
 except:frame=0
 img=icon(parts,parts.sym.get(symbol),frame-1,'item-'+k) if frame>0 else ''
 ss=b.get('set',[]);ss=[ss] if isinstance(ss,str) else ss
 result['items'].append({'id':k,'name':tr(b.get('name'),k),'description':tr(b.get('desc'),'游戏未提供文字说明。'),'kind':kind,'sets':ss,'image':img,'quest':k in quest})
for k,b in sets.items():
 if not isinstance(b,dict):continue
 members=[i for i in result['items'] if k in i['sets']]
 if members:result['sets'].append({'id':k,'name':tr(b.get('name'),k),'description':tr(b.get('desc'),'游戏未提供套装说明。'),'required':b.get('pieces_required','3'),'image':next((i['image'] for i in members if i['image']),''),'members':[i['id'] for i in members]})
for k,b in groups['classes'].items():
 if not isinstance(b,dict):continue
 meta=b.get('meta',{}) if isinstance(b.get('meta'),dict) else {};symbol=ui.sym.get('FontIcon_'+k.lower()) or ui.sym.get('FontIcon_'+k) or (ui.sym.get('FontIcon_Cleric') if k=='Medic' else None)
 result['classes'].append({'id':k.lower(),'name':tr(meta.get('name'),k),'description':tr(meta.get('description') or meta.get('desc'),'无职业没有项圈职业加成。' if k.lower()=='colorless' else ''),'image':icon(ui,symbol,0,'class-'+k)})
class_colors={'fighter':'#b44545','hunter':'#427b52','mage':'#7353ae','medic':'#a36b25','tank':'#82623f','thief':'#535b8c','colorless':'#5d7184','monk':'#ad7b33','butcher':'#a04852','necromancer':'#80588b','druid':'#3c8273','tinkerer':'#557786','psychic':'#9b5b94','jester':'#a35a7e'}
from PySide6.QtGui import QColor
from PySide6.QtCore import QRect
for entry in result['classes']:
 if not entry['image'] or not (ROOT/entry['image']).is_file():continue
 glyph_source=QImage(str(ROOT/entry['image']));assert not glyph_source.isNull(),entry['id']
 tile_glyph=QImage(glyph_source.size(),QImage.Format_ARGB32_Premultiplied);tile_glyph.fill(Qt.transparent)
 painter=QPainter(tile_glyph);painter.drawImage(0,0,glyph_source);painter.setCompositionMode(QPainter.CompositionMode_SourceIn);painter.fillRect(tile_glyph.rect(),QColor('white'));painter.end()
 tile=QImage(100,100,QImage.Format_ARGB32_Premultiplied);tile.fill(Qt.transparent)
 painter=QPainter(tile);painter.setRenderHint(QPainter.Antialiasing);painter.setPen(Qt.NoPen);painter.setBrush(QColor(class_colors.get(entry['id'],'#556b87')));painter.drawRoundedRect(1,1,98,98,15,15);painter.drawImage(QRect(14,14,72,72),tile_glyph);painter.end()
 entry['image']='images/class-choice-'+entry['id']+'.png';assert tile.save(str(ROOT/entry['image']))
partnames={'body':'body','head':'head','tail':'tail','leg':'legs','ear':'ears','eye':'eyes','eyebrow':'eyebrows','mouth_closed':'mouth','texture':'texture'}
for folder,group in partnames.items():
 entries=groups['mutations'].get(group,{})
 if not isinstance(entries,dict):entries={}
 result['mutations'][folder]={}
 for k,b in entries.items():
  if not isinstance(b,dict) or not str(k).lstrip('-').isdigit():continue
  fields={'str':'力量','dex':'敏捷','con':'体质','int':'智力','spd':'速度','cha':'魅力','lck':'幸运','shield':'护盾','thorns':'荆棘'}
  stats_text='；'.join(fields[key]+(' +' if not str(value).startswith('-') else ' ')+str(value) for key,value in b.items() if key in fields)
  fallback=getattr(md,'MUTATION_DESCRIPTIONS',{}).get(group,{}).get(int(k),'')
  desc=tr(b.get('desc'),fallback)
  if isinstance(b.get('passives'),dict):
   names={'Thorns':'荆棘','Shield':'护盾','Regen':'再生','Flying':'飞行','ExtraAttack':'额外攻击','ExtraMove':'额外移动','CounterAttack':'反击'}
   raw_effect='；'.join(names.get(key,tr(groups['passives'].get(key,{}).get('name') if isinstance(groups['passives'].get(key),dict) else '',key))+': '+(str(value) if not isinstance(value,dict) else json.dumps(value,ensure_ascii=False)) for key,value in b['passives'].items())
   if not desc:desc=raw_effect
  combined='\n'.join(x for x in [stats_text,desc] if x) or '无额外属性效果。'
  result['mutations'][folder][str(k)]={'name':tr(b.get('name'),str(k)),'description':combined,'tag':b.get('tag','')}
def zh_fix(text):
 if not isinstance(text,str):return text
 text=text.replace('10% chance to cancel actions.','10% 几率抵消行动。').replace('Deja Vu will go away when this cat returns to the house.','猫回到家后，既视感会消失。').replace('Give a familiar +1 divineshield.','给跟班 +1 神圣护盾。').replace('Bleed 1 on basic attack','普通攻击时施加 1 层流血')
 text=text.replace('{aux_cat_name}','某只猫').replace('{str_aux_passive_name}','随机被动').replace('{str_aux_passive_desc}','对应效果').replace('{str_aux_active_name}','随机主动').replace('{str_aux_active_desc}','对应效果').replace('{str_aux_item_desc}','随机物品说明').replace('{str_aux}','该属性').replace('{aux}','N').replace('{v0}','N')
 text=re.sub(r'\{[A-Za-z_0-9]+\}','',text)
 for source,target in [('divineshield','神圣护盾'),('Shield','护盾'),('shield','护盾'),('STR','力量'),('DEX','敏捷'),('CON','体质'),('INT','智力'),('SPD','速度'),('CHA','魅力'),('LCK','幸运'),('HP','生命'),('Dodge','闪避'),('Bleed','流血'),('Poison','中毒'),('Thorns','荆棘'),('champion','精英'),('elite','精英'),('Boss','首领'),('AI','电脑'),('comfort','舒适'),('stimulation','刺激'),('appeal','吸引力')]:
  text=re.sub(r'(?<![A-Za-z_])'+source+r'(?![A-Za-z_])',target,text)
 text=re.sub(r'(?<![0-9])\.(?=\d)','0.',text)
 for source,target in [('floor(','向下取整('),('ceil(','向上取整('),('max(','取较大值('),('min(','取较小值('),('clamp(','限制('),('level','等级'),('*','×')]:
  text=text.replace(source,target)
 lines=[]
 for line in text.split('\n'):
  line=re.sub(r'[ \t]+',' ',line).strip()
  simplified=re.sub(r'[\s，,；;、]+','',line)
  if not simplified:continue
  if re.fullmatch(r'[-–—\s]*(随机被动|随机主动|随机物品说明|对应效果|该属性)[-–—\s]*(随机被动|随机主动|随机物品说明|对应效果|该属性)?[-–—\s]*',line):continue
  if any(simplified==kept[0] for kept in lines):continue
  lines.append((simplified,line))
 return '\n'.join(line for _,line in lines)

for entry in result['actives']+result['passives']+result['diseases']:
 entry['name']=zh_fix(entry.get('name',''))
 entry['description']=zh_fix(entry.get('description',''))
 if 'combatSummary' in entry:entry['combatSummary']=zh_fix(entry['combatSummary'])
 upgrade=entry.get('upgrade')
 if isinstance(upgrade,dict):
  upgrade['description']=zh_fix(upgrade.get('description',''))
  if 'combatSummary' in upgrade:upgrade['combatSummary']=zh_fix(upgrade['combatSummary'])
for entry in result['items']+result['sets']+result['classes']:
 entry['name']=zh_fix(entry.get('name',''))
 entry['description']=zh_fix(entry.get('description',''))
for folder in result['mutations'].values():
 for effect in folder.values():
  effect['name']=zh_fix(effect.get('name',''))
  effect['description']=zh_fix(effect.get('description',''))

missing={kind:sum(not x['image'] for x in result[kind]) for kind in ['actives','passives','diseases','items','classes']}
(ROOT/'workbench.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');(ROOT/'asset-report.json').write_text(json.dumps({'icons':stats['rendered'],'missing':missing,'errors':stats['missing'][:20]},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'icons':stats['rendered'],'missing':missing,'mutations':{k:len(v) for k,v in result['mutations'].items()}},ensure_ascii=False))

labels={x['id']:x['name'] for kind in ['actives','passives','items'] for x in result[kind]}
(ROOT/'journal'/'labels.json').write_text(json.dumps(labels,ensure_ascii=False),encoding='utf-8')
