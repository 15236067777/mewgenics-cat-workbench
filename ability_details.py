"""Read display values from game ability definitions, including inherited values."""
import copy
import re


def merge_definitions(base, override):
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_definitions(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def resolve_ability(identifier, abilities, templates, parents=()):
    if identifier in parents:
        raise ValueError('Circular ability inheritance: ' + identifier)
    definition = abilities.get(identifier, templates.get(identifier, {}))
    if not isinstance(definition, dict):
        return {}
    result = {}
    template = definition.get('template')
    if isinstance(template, str):
        template_key = template if template in templates else 'template_' + template
        result = resolve_ability(template_key, abilities, templates, parents + (identifier,))
    variant = definition.get('variant_of')
    if isinstance(variant, str):
        result = merge_definitions(result, resolve_ability(variant, abilities, templates, parents + (identifier,)))
    return merge_definitions(result, definition)


def readable_formula(value):
    names = {
        'bonus_melee_damage': '近战伤害加成',
        'bonus_melee_ability_damage': '近战技能伤害加成',
        'bonus_ranged_damage': '远程伤害加成',
        'bonus_basic_spell_damage': '基础法术伤害加成',
        'bonus_spell_damage': '法术伤害加成',
        'str': '力量', 'dex': '敏捷', 'con': '体质', 'int': '智力',
        'spd': '速度', 'cha': '魅力', 'lck': '幸运',
    }
    return re.sub(r'\b[A-Za-z_][A-Za-z_0-9]*\b', lambda match: names.get(match[0], match[0]), str(value))


def combat_summary(identifier, abilities, templates):
    definition = resolve_ability(identifier, abilities, templates)
    cost = definition.get('cost', {})
    damage = definition.get('damage_instance', {})
    if not isinstance(cost, dict):
        cost = {}
    if not isinstance(damage, dict):
        damage = {}
    mana = readable_formula(cost['mana']) if 'mana' in cost else '未标注'
    parts = ['蓝耗 ' + mana]
    if 'heal' in damage:
        parts.append('基础治疗 ' + readable_formula(damage['heal']))
    elif 'damage' in damage:
        parts.append('单段基础伤害 ' + readable_formula(damage['damage']))
    else:
        parts.append('直接伤害未标注')
    damage_types = {'melee':'近战', 'ranged':'远程', 'spell':'法术', 'status_spell':'状态法术'}
    if damage.get('type') in damage_types:
        parts.append(damage_types[damage['type']])
    if re.search(r'\bX\b', ' '.join(parts)):
        parts.append('X 随技能条件变化')
    return ' · '.join(parts)
