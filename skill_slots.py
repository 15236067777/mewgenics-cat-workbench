"""Workbench fields and their native save ability slots.

The first passive keeps its original key so older drafts and presets load intact.
Active skills have both a current slot and an inherited/base slot in the save.
"""

FLAG_LABELS={'mapflag_MeatWorldUnlocked':'肉世界','mapflag_MeatWorldUnlockedFull':'肉世界（完整）','mapflag_IceAgeUnlocked':'冰河世纪','mapflag_DimensionXUnlocked':'次元X','mapflag_EndOfTimeUnlocked':'终末之时','mapflag_MoonObeliskUnlocked':'月亮方尖碑','mapflag_CoreObeliskUnlocked':'核心方尖碑','mapflag_BothObelisksUnlocked':'双方尖碑','mapflag_ThrobbingArteryDone':'搏动动脉','mapflag_WallOfFleshDone':'肉墙','mapflag_ChaosAntennaAttached':'混沌天线','mapflag_OrbAntennaAttached':'光球天线','mapflag_VolcanoAntennaAttached':'火山天线'}
MAX_CATS = 20

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
