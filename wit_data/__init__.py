import random
import re
import os
import logging


logger = logging.getLogger('discord.' + __name__)

_wit_data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'wit_data'))
_remap = {'bosses': 'boss', 'encounters': 'encounter', 'enemies': 'enemy'}
_tmp = None


def parse_encounter(txt):
    import re
    out = dict()
    txt = txt.strip()
    chunks = re.split(r"\n-{3,}", txt)
    lines = chunks[0].split('\n')
    out['title'] = lines[0].strip().strip('_*').lower()
    out['body'] = ('\n'.join(lines)).strip()
    tasks = {}
    for chunk in chunks[1:]:
        chunk = chunk.strip()
        match = re.search(r"tdt\$(?P<task>.*)", chunk)
        tasks[match['task']] = chunk[match.end():].strip()
    # if '' in tasks:
    #    raise ValueError("Empty task")
    out['tasks'] = tasks
    if not tasks:
        return out['body']
    return out


def safe_update(d, u, key=None):
    if key is not None:
        u = {key: u}
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = safe_update(d.get(k, {}), v)
        else:
            if k in d:
                if d[k] != v:
                    logger.warning(f"Overwriting {k} with {v}")
            d[k] = v
    return d


def make_decorator(dct):
    # *This* will be the function bound to the name 'wit_cmd'
    _tmp = None

    def _(meth=None, *, aliases=None):
        global _tmp
        if meth is None:
            _tmp = aliases
            return _
        if _tmp is not None:
            aliases = _tmp
            _tmp = None
        if aliases is None:
            aliases = []
        if isinstance(aliases, str):
            aliases = [aliases]
        dct[meth.__name__] = meth
        for i in aliases:
            dct[i] = meth
        return meth
    return _


def parse_roll(roll_str, max_sides=None):
    pattern = r"(?P<amount>[0-9]?)d(?P<sides>[0-9]+)[\s]?(?P<mod>[+-][\s]?[0-9]+)?"
    match = re.match(pattern, roll_str).groupdict()
    out = [match[i] for i in ("amount", "sides", "mod")]
    if not out[0]:
        out[0] = 1
    if not out[2]:
        out[2] = 0
    if isinstance(out[2], str):
        out[2] = out[2].replace(" ", "")
    out = [int(i) for i in out]
    if max_sides:
        out[1] = min(out[1], max_sides)
    if not out[0]:
        out[0] = 1
    return out


def roll(*args, max_sides=None):
    if len(args) == 1 and hasattr(args[0], "lower"):
        args = parse_roll(args[0], max_sides=max_sides)
    out = [random.randint(1, args[1]) for _ in range(args[0])]
    if args[2]:
        out.append(args[2])
    return out


def gen_weapon(roll_str):
    prefixes = [
        "**Basic**: No bonus [+1 <:gold:1058304371940655185>]",
        "**Ornate**: +10 in <:gold:1058304371940655185> value",
        "**Lightweight**: +⚡ [+3 <:gold:1058304371940655185>]",
        "**Relentless** (-1 🔷): +🚫 [+4 <:gold:1058304371940655185>]",
        "**Honed** (-2 🔷): +🎯 [+5 <:gold:1058304371940655185>]",
        "**Heavy** (-1 🔷): +🛡️ [+6 <:gold:1058304371940655185>]",
        "**Robust** (-2 🔷): +<:Sturdy:1152516154192044142> [+7 <:gold:1058304371940655185>]",
        "**Concealed** (-1 🔷): +<:stealthIcon:943248201790677052> [+8 <:gold:1058304371940655185>]",
        "**Unbreaking** (-2 🔷): +<:Persistence:1151788148322484234> [+9 <:gold:1058304371940655185>]",
        "**Sweeping** (-2 🔷): +🌀 [+10 <:gold:1058304371940655185>]",
    ]
    weapons = [
        "**Short Sword**: 💥💥 [+1 <:gold:1058304371940655185>]",
        "**Buckler**: 🛡️🛡️🛡️ [+2 <:gold:1058304371940655185>]",
        "**Kunai**: 💥⚡ [+3 <:gold:1058304371940655185>]",
        "**Axe**: 💥🚫 [+4 <:gold:1058304371940655185>]",
        "**Crossbow** (-1 🔷): 💥🎯 [+5 <:gold:1058304371940655185>]",
        "**Halberd**: 💥🛡️ [+6 <:gold:1058304371940655185>]",
        "**Focus Rune**: <:Persistence:1151788148322484234>🔀+🔷🔷 [+7 <:gold:1058304371940655185>]",
        "**Siphon Rune**: <:Persistence:1151788148322484234>🔀+❤️ [+8 <:gold:1058304371940655185>]",
        "**Fang**: 💥<:stealthIcon:943248201790677052> [+9 <:gold:1058304371940655185>]",
        "**Knights Shield**: <:Sturdy:1152516154192044142><:Sturdy:1152516154192044142> [+10 <:gold:1058304371940655185>]",
        "**Scroll**: +3 🔷 {OR} +1 ❤️ [+11 <:gold:1058304371940655185>]",
        "**Wand**: Gain a random tdt$draft spell, it has as many uses as your current stacks of __empower__ +1. [+12 <:gold:1058304371940655185>]",
        "**Runic Flintlock** (-2 🔷): 💥, +💥 per stack of __weak__ your target has [+13 <:gold:1058304371940655185>]",
        "**Graven Shield** (-1 🔷): <:Sturdy:1152516154192044142>, +<:Sturdy:1152516154192044142> per stack of __heal__ you have [+14 <:gold:1058304371940655185>]",
        "**Gilded Hammer** (-2 🔷): 🛡️🛡️, +💥 per stack of __protect__ you you have [+15 <:gold:1058304371940655185>]",
        "**Tome**: Summon a champions conjuration. It costs 1 extra 🔷 [+16 <:gold:1058304371940655185>]",
        "**Spell Book** (-4 🔷): Double your next move's efficacy [+17 <:gold:1058304371940655185>]",
        "**Protection Rune** (-2 🔷): <:Persistence:1151788148322484234><:Persistence:1151788148322484234> [+18 <:gold:1058304371940655185>]",
        "**Staff** (-2 🔷): 💥💥, +🔷 per stack of __burn__ your target has [+19 <:gold:1058304371940655185>]",
        "**Sword of the Spirit** Remove all __will__ at the end of next turn [+20 <:gold:1058304371940655185>]",
    ]
    rolls = zip(roll(roll_str, max_sides=len(prefixes)), roll(roll_str, max_sides=len(weapons)))
    return [(prefixes[r[0] - 1], weapons[r[1] - 1], (r[0] if r[0] != 2 else 10) + r[1]) for r in rolls]


def gen_potion(roll_str):
    prefixes = [
        "**Tincture of**: --Effect [+1 <:gold:1058304371940655185>]",
        "**Tonic of**: -Effect [+2 <:gold:1058304371940655185>]",
        "**Potion of**: No bonus [+3 <:gold:1058304371940655185>]",
        "**Elixir of**: +Effect [+4 <:gold:1058304371940655185>]",
        "**Grand Mixture of**: ++Effect [+5 <:gold:1058304371940655185>]",
        "**Splash Tincture of**: --Effect, +🌀 [+6 <:gold:1058304371940655185>]",
        "**Splash Tonic of**: -Effect, +🌀 [+7 <:gold:1058304371940655185>]",
        "**Splash Potion of**: +🌀 [+8 <:gold:1058304371940655185>]",
        "**Splash Elixir of**: +Effect, +🌀 [+9 <:gold:1058304371940655185>]",
        "**Grand Splash Mixture of**: ++Effect, +🌀] [+10 <:gold:1058304371940655185>]",
    ]
    potions = [
        "**Regeneration**: +4 ❤️ ( +/- 1 per effect) [+1 <:gold:1058304371940655185>]",
        "**Rejuvenation**: +4 🔷 ( +/- 1 per effect) [+2 <:gold:1058304371940655185>]",
        "**Strength**: Empower x4 [+3 <:gold:1058304371940655185>]",
        "**Toughness**: Protect x4 [+4 <:gold:1058304371940655185>]",
        "**Healing**: Heal x6 [+5 <:gold:1058304371940655185>]",
        "**Weakness**: Weak x4 [+6 <:gold:1058304371940655185>]",
        "**Sapping**: Vulnerable x4 [+7 <:gold:1058304371940655185>]",
        "**Flames**: Burn x6 [+8 <:gold:1058304371940655185>]",
        "**Foritude**: +<:stealthIcon:943248201790677052><:Persistence:1151788148322484234><:Sturdy:1152516154192044142> for the next 3 turn(s) [+9 <:gold:1058304371940655185>]",
        "**Proficiency**: +🚫🎯⚡ for the next 3 turn(s) [+10 <:gold:1058304371940655185>]",
        "**Impact**: Cause +💥💥💥💥⚡ [+11 <:gold:1058304371940655185>]",
        "**Demolition**: Cause +:💥💥💥💥🚫 in 2 turns [+12 <:gold:1058304371940655185>]",
        "**Needling**: Cause +💥💥💥💥🎯 in 3 turns [+13 <:gold:1058304371940655185>]",
        "**Smoke**: Cause +🛡️🛡️🛡️<:stealthIcon:943248201790677052> next turn [+14 <:gold:1058304371940655185>]",
        ]
    rolls = zip(roll(roll_str, max_sides=len(prefixes)), roll(roll_str, max_sides=len(potions)))
    return [(prefixes[r[0] - 1], potions[r[1] - 1], r[0] + r[1]) for r in rolls]


def gen_artifact(roll_str):
    artifacts = [
        "**Honey Money** 🍯: Succesful combats while you have an __effect__ hits grant +1 <:gold:1058304371940655185> per stack remaining. [+1 <:gold:1058304371940655185>]",
        "**Safety Scissors** ✂️: Redo your Floor or Boss roll. (Destroyed on Use) [+2 <:gold:1058304371940655185>]",
        "**Cook Book** 🍔: You may raise your max ❤️ and 🔷 by 1 at ⛺ instead of resting. [+3 <:gold:1058304371940655185>]",
        "**Port-a-Forge** 🛠️: Increase a 🗡️'s 💥, 🛡️, or __effect__. If used on an upgraded 🗡️, this costs -1 max 🔷 to use. (Destroyed on use). [+4 <:gold:1058304371940655185>]",
        "**Ring of Momentum** 💍: 🗡️ kills grant __Empower__. [+5 <:gold:1058304371940655185>]",
        "**Safety Hook** 🪝: Succesful 🗡️ hits grant __Protect__. [+6 <:gold:1058304371940655185>]",
        "**Vitamins** 💊: Start combat with __Heal__ [+7 <:gold:1058304371940655185>]",
        "**Lucky Clover** 🍀: Successful 🗡️ blocks cause __Weak__ [+8 <:gold:1058304371940655185>]",
        "**War Drum** 🥁: Succesful 🗡️ blocks cause __vulnerable__ [+9 <:gold:1058304371940655185>]",
        "**Eternal Lantern** 🪔: Successful 🗡️ hits cause __Burn__ [+10 <:gold:1058304371940655185>]",
        "**Potion Pack** 🎒: Increase 🧪 capacity by +2. [11 <:gold:1058304371940655185>]",
        "**Bandolier** 🎽: Increase 🗡️ capacity by +2. [12 <:gold:1058304371940655185>]",
        "**Foreboding Omen** ☠️: +1 👥. [+13 <:gold:1058304371940655185>]",
    ]
    return [(None, artifacts[r - 1], r) for r in roll(roll_str, max_sides=len(artifacts))]


def item_card(item, gold=None):
    gold_str = ""
    prefix, kind, price = item
    if gold is not None and gold is not False:
        gold = 0 if gold is True else gold
        gold += price
        gold_str = f" ({gold} <:gold:1058304371940655185>)"
    if prefix is None:
        name = re.match(r"\*\*(.*)\*\*", kind).group(1)
        return f"**__{name}__**{gold_str}\n{kind}"
    else:
        name = re.match(r"\*\*(.*)\*\*", prefix).group(1) + " " + re.match(r"\*\*(.*)\*\*", kind).group(1)
        return f"**__{name}__**{gold_str}\n{prefix}\n{kind}"


def gen_shop():
    # must return a list of strings which are essentially paragraphs
    out = ["# __WEAPONS__"]
    out.extend(item_card(item, gold=5) for item in gen_weapon("3d19"))
    out.append("# __POTIONS__")
    out.extend(item_card(item, gold=5) for item in gen_potion("3d10"))
    out.append("# __ARTIFACTS__")
    out.extend(item_card(item, gold=5) for item in gen_artifact("3d10"))
    out.append("# __SINGLE USE GOODS__")
    out.append("[-5 <:gold:1058304371940655185>] **Ancient Key**: :key2: Opens one chest.")
    out.append("[-10 <:gold:1058304371940655185>] **Tavern Meal** +1 max ❤️ or 🔷")
    out.append("[-10 <:gold:1058304371940655185>] **Ancient Relic** Roll 3 rare 🏺, you may buy one")
    out.append("[-15 <:gold:1058304371940655185>] **Spell Book** +1 tdt$draft spell 📜")
    out.append("**Sell Items**: Remove any items 💰, gain their listed <:gold:1058304371940655185> value")
    return out


def gen_loot(roll_str=None):
    if roll_str is None:
        roll_str = "1d10"
    if hasattr(roll_str, "lower"):
        if roll_str.isdigit():
            roll_str = int(roll_str)
    if isinstance(roll_str, int):
        roll_str = f"1d{roll_str}"
    choice = random.randint(1, 3)
    if choice == 1:
        items = gen_weapon(roll_str)
    elif choice == 2:
        items = gen_potion(roll_str)
    else:
        items = gen_artifact(roll_str)
    return [item_card(item, gold=False) for item in items]


class WitData:
    _wit_cmds = dict()
    wit_cmd = make_decorator(_wit_cmds)

    def __init__(self, parent=None):
        self._data = dict()
        self._aliases = dict()
        self._active_commands = []
        self.parent = parent
        self.load_data()

    def get_data(self, *keys):
        """Retrieve preloaded wit data"""
        data = self._data
        for key in keys:
            data = data[key]
        return data

    def get_command(self, cmd, exicute=True):
        """Get command from wit data files"""
        if cmd in self._wit_cmds:
            out = getattr(self, cmd)
        else:
            try:
                out = self._data['tasks'][cmd]
            except KeyError:
                out = self.get_data(*self._aliases[cmd])
        if exicute:
            while isinstance(out, dict):
                out = random.choice(list(out.values()))
            while callable(out):
                out = out()
        return out

    def set_command(self, cmd):
        """Set command in wit data files"""
        # if not cmd:
        #    raise ValueError("cmd must be a non-empty string")
        key = cmd[:]
        if self.parent:
            key = self.parent.set_command(cmd)
        self._active_commands.append(key)

    def load_data(self, overwrite=True):
        """Load wit data from files"""

        def path2dict(path, data=None):
            data = dict() if data is None else data
            for key in os.listdir(path):
                if key.endswith(".py") or key.startswith("."):
                    continue
                if key == '__pycache__':
                    continue
                if not key:
                    continue
                fn = os.path.join(path, key)
                if os.path.isfile(fn):
                    key = os.path.splitext(key)[0]
                    with open(fn, 'r') as f:
                        info = parse_encounter(f.read())
                        if isinstance(info, dict):
                            data[key] = info['body']
                            safe_update(self._data, info['tasks'], 'tasks')
                        else:
                            data[key] = info
                elif os.path.isdir(fn):
                    data[key] = path2dict(fn)
                else:
                    logger.warning(f"Unknown file type: {fn}")
            return data

        if overwrite or not self._data:
            for cmd in self._active_commands:
                delattr(self, cmd)
            self._active_commands = []
            self._data = dict()
            self._data = path2dict(_wit_data_path, data=self._data)

            self._aliases = dict()
            for zone in self._data['zones']:
                for key in self._data['zones'][zone]:
                    if key == "additional_commands":
                        tmp = {k: ('zones', zone, key, k) for k in self._data['zones'][zone][key]}
                    else:
                        tmp = {zone + "_" + _remap.get(key, key): ('zones', zone, key)}
                    safe_update(self._aliases, tmp)
            tmp = {champ: ('random_champion', champ) for champ in self._data['random_champion']}
            safe_update(self._aliases, tmp)

            for key in self._data['tasks']:
                if key in self._aliases:
                    logger.warning(f"Collision between task and alias {key}")

        tmp = {k: (k,) for k in self._data.keys() if k not in ['zones', 'tasks']}
        safe_update(self._aliases, tmp)
        for cmd in self._wit_cmds:
            self.set_command(cmd)
        for cmd in self._data['tasks'].keys():
            self.set_command(cmd)
        for cmd in self._aliases.keys():
            self.set_command(cmd)
        return

    @wit_cmd
    def floor(self):
        options = ["💀 Enemy",
                   "☠️ Major",
                   "❔ Encounter",
                   "⛺ Camping Spot",
                   "🎇 Blessing",
                   "🔒 Chest",
                   "🛖 Shop"
                   ]
        return ', '.join(random.choices(options, weights=[7, 3, 7, 3, 2, 2, 4], k=3))
