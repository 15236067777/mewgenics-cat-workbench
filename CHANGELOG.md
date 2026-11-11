# Changelog

## 未发布 — 2026-11-11

- 疾病栏并入技能页：2 个疾病／障碍栏紧跟 4 主动、2 被动之后，不再单独占一个页签。
- 每个技能位新增「强化」勾选框：主动技能写入游戏内的 +2 变体，被动技能写入 2 级被动；技能选择面板同样可选强化版，工作台与选择面板都同时显示原效果和强化效果。
- 职业与技能不再受存档解锁限制：14 个职业全部可选，未解锁的标注出来；新增「解锁全部职业与技能」按钮，把全部职业、主动和被动技能写入存档解锁表（只改解锁表，写入前自动备份）。
- 职业彩色底板改由构建脚本直接生成，重新建目录后不会再退回单调的白色图标。
- 目录描述全中文化：残留的英文词（shield、STR/CON 等属性缩写、AI、Boss、公式里的 floor/max/clamp、{aux} 等占位符）都换成中文，重复的属性行已合并。
- 游戏本身没写文字的条目现在自动补说明：被动/疾病按 stats 与被动效果生成（如「幸运 +4」「护盾 +4、体质 +2、速度 -1」），装备按属性、诅咒/寄生虫、耐久和武器攻击概要生成，套装按件数效果生成；纯外观装备写「某部位饰品，没有额外属性。」。缺中文名的 44 件装备也补了中文名。

## 0.1.0-beta.2 — 2026-11-11

- Four optional active skills, two optional class passives and two optional diseases per cat.
- Active skill descriptions show mana cost and per-hit base damage or healing, with inherited template/variant values and conditional formulas.
- Disease selection includes locally extracted original game icons and descriptions.
- Existing drafts and presets keep their first two actives and first passive, with new fields empty.
- Upgrading regenerates the local asset catalog to include diseases.

## 0.1.0-beta.1 — 2026-11-10

- First public beta of the Chinese custom cat workbench and expedition diary.
- One to four custom cats, fixed base stats, independent optional class skills.
- Original game skill icons; item/detail list; inline set effects; mutation descriptions.
- Offline staged writes, automatic backups, protected task-item handling.
- Expedition records match the actual dispatched subset of a saved preparation.
- Portable first-launch configuration; all art, catalogs and cat templates generated locally.
- No publisher paths, saves, generated catalogs or game artwork distributed.
