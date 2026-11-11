"""Workbench fields and their native save ability slots.

The first passive keeps its original key so older drafts and presets load intact.
Active skills have both a current slot and an inherited/base slot in the save.
"""

SKILL_SLOTS = {
    'active1': {'label': '主动技能 1', 'kind': 'actives', 'slots': (2, 6)},
    'active2': {'label': '主动技能 2', 'kind': 'actives', 'slots': (3, 7)},
    'active3': {'label': '主动技能 3', 'kind': 'actives', 'slots': (4, 8)},
    'active4': {'label': '主动技能 4', 'kind': 'actives', 'slots': (5, 9)},
    'passive': {'label': '被动技能 1', 'kind': 'passives', 'slots': (10,)},
    'passive2': {'label': '被动技能 2', 'kind': 'passives', 'slots': (11,)},
    'disease1': {'label': '疾病 1', 'kind': 'diseases', 'slots': (12,)},
    'disease2': {'label': '疾病 2', 'kind': 'diseases', 'slots': (13,)},
}
