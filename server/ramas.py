"""Canonical branch IDs shared by the IGG, Simplified and Traditional clients."""

SHADOWBLADE = 30
MANTLE = 32
AVATAR = 35
ASSAULT = 36

NOMBRES = {
    1: 'Life', 2: 'Wraith', 3: 'Chaos', 4: 'Earth', 5: 'Curse',
    6: 'Meditate', 7: 'Hit', 8: 'Staff Hit', 9: 'Sword', 10: 'Axe',
    11: 'Spear', 12: 'Enhance', 13: 'Grapple', 14: 'Shield', 15: 'Reserve',
    16: 'Finesse', 17: 'Longbow', 18: 'Snipe', 19: 'Eagle Eye',
    20: 'Collect', 21: 'Fishing', 22: 'Dig', 23: 'Lumber',
    24: 'Mechanism', 25: 'Drive', 26: 'Weapon', 27: 'Armor',
    28: 'Sew', 29: 'Technics', SHADOWBLADE: 'ShadowBlade', 31: 'Cook',
    MANTLE: 'Mantle', 33: 'Garment', 34: 'Vestment', AVATAR: 'Avatar', ASSAULT: 'Assault',
}

PRODUCCION = frozenset({20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31})
CLASES_PRODUCCION = frozenset({10, 11, 12, 13, 15, 19, 20})


def tope_nivel(skill_id, nivel_personaje):
    import combate
    return min(combate.nivel_maximo(), int(nivel_personaje) + (11 if int(skill_id) in PRODUCCION else 0))
