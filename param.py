import os
import json
import shelve

_dir = os.path.split(os.path.realpath(__file__))[0]
_config = os.path.join(_dir, 'config')


class _Struct(object):
    def __init__(self, **entries):
        self.__dict__.update(entries)

    def __contains__(self, item):
        return item in self.__dict__

    def __getitem__(self, item):
        return self.__dict__[item]


channels = _Struct(debugging=721427624483749991,
                   manual_page=558136628590280704,
                   general_chat=867464907266719754,
                   content_hub=782901700990074910,
                   shaxxs_lodge=867464907266719754,
                   bounty_board=889587767212900362,
                   lfg_pvp=560270058224615425,
                   lfg_pve=878403478987366490,
                   lfg_shenanigans=878403991195766844,
                   lenny_laboratory=562412283268169739,
                   spicy_clips=746441485917880330,
                   tdt_events=637134842911260673,
                   champions_landing=1084331687305023529,
                   wit_category=639147967131025453,
                   spicy_clips_supporters=1153123185043185694,
                   banning_channel=1239658247804420096,
                   welcome_wagon=932748539107356852,
                   art_atrium=1385350203522945075,
                   )

emojis = _Struct(destiny_2=878802171913732118,
                 minecraft=878806389399625789,
                 apex=878807665038491668,
                 overwatch2=1034229453817126984,
                 StrangeCoin=319276617727737866,
                 lenny=333101455856762890,
                 OGTriggered=433210982647595019,
                 never=588737463376412692,
                 call_of_duty=1046956005361188904,
                 gold=1058304371940655185,
                 tdt_bruh=857429157508284453,
                 wit=1069494785716518952,
                 helldiver2=1300244446025093132,
                 warframe=1300244078117781524,
                 space_marine_2=1300247394692239431,
                 cod_bo6=1324177150097490001,
                 deadlock=1324177148608516169,
                 marvel_rivals=1324177147602141254,
                 )

guilds = _Struct(tdt=164589623459184640)

messages = _Struct(CoC=563406038754394112,
                   wolfpack=945717800788447282,
                   trick_or_treat=1427003734751449298,
                   games=563406038754394112,
                   wit_pvp=1140151464732397628,
                   wit_pve=1109211558229323927,
                   )

roles = _Struct(
                # main roles
                recruit=563067424719634452,
                community=736052778396287026,
                community_plus=857702905934250025,
                member=318266595187228672,
                devoted=611745292899057694,
                admin=318255861002928129,
                supporter=1006390128907919411,
                tdt_peeps=878812130453905420,
                # game roles
                destiny_2=878812130453905420,  # kept for backwards compatibility
                d2pvp=1140789426319003738,
                d2pve=1140788917474426920,
                wit_initiate=1158152616782614668,
                space_marine_2=1300249852638396426,
                warframe=1300249523951505418,
                minecraft=1300249136645275688,
                helldivers2=1300249391088799764,
                call_of_duty=1320268864080187423,
                marvel_rivals=1320268692268908645,
                deadlock=1324178731333324912,
                artist=1385411116498157598,
                )

users = _Struct(electro=221778796250923008,
                mesome=160087397873221632,
                stellar=332355011919085582,
                wator=722927617740767344,
                em=533862306132787200,
                )

# roles
emoji2role = {emojis.tdt_bruh: roles.tdt_peeps,
              "⚔️": roles.d2pvp,
              "☠️": roles.d2pve,
              emojis.minecraft: roles.minecraft,
              emojis.helldiver2: roles.helldivers2,
              emojis.warframe: roles.warframe,
              emojis.space_marine_2: roles.space_marine_2,
              emojis.cod_bo6: roles.call_of_duty,
              emojis.deadlock: roles.deadlock,
              emojis.marvel_rivals: roles.marvel_rivals,
              }

role2emoji = {v: k for k, v in emoji2role.items()}


# Defaults for parameters
defaults = {
    'channel':         'devoted_chat',
    'cmd_prefix':      ['TDT$', 'Tdt$', 'tdt$'],
    'config_file':     os.path.join(_config, 'tdt.json'),
    'token_file':      os.path.join(_config, 'token.txt'),
    'roast_file':      os.path.join(_config, 'roasts.txt'),
    'lore_file':       os.path.join(_config, 'lore.md'),
    'welcome_file':    os.path.join(_config, 'welcome.md'),
    'art_file':        os.path.join(_config, 'art_atrium.md'),
    'nemeses':         [users.electro, users.wator, users.em],
    'add_bots':        [],
    'ignore_list':     ['lfg_pvp', 'lfg_pve', 'lenny_laboratory', 'manual_page',
                        'tdt_events', 'devoted_chat', 'banning_channel'],
    'event_channel':   'tdt_events',
    'log_channel':     'debugging',
    'chron_channel':   'debugging',
    'fashion_channel': 'debugging',
    'event_reminders': [360, 60, 0],  # in minutes
    'timezone':        'US/Pacific',
    'logfile':         os.path.join(_dir, 'logs', 'tdt.log'),
}


class DataContainer:
    def __init__(self, fn):
        self.fn = fn
        self.data = dict()
        self._file_data = self._load_own_data()
        if self._file_data is not None:
            for i in self._file_data:
                self.data[i] = self._file_data[i]

    def __getitem__(self, key):
        try:
            return self.data[key]
        except KeyError:
            pass
        try:
            out = self._file_data[key]
            self.data[key] = out
            return out
        except (KeyError, TypeError):
            pass
        try:
            func = getattr(self, str(key), getattr(self, '_' + str(key)), None)
            if callable(func):
                self.data[key] = func()
                self._save()
                return self.data[key]
        except AttributeError:
            pass
        try:
            self._gen_data(key)
            out = self.data[key]
            self._save()
            return out
        except (NotImplementedError, KeyError):
            pass
        raise KeyError('Could not find or generate "{0}".'.format(key))

    def __setitem__(self, key, value):
        self.data[key] = value
        self._save()

    def _load_own_data(self):
        try:
            with open(self.fn, 'r') as f:
                return json.load(f)
        except IOError:
            self._gen_data(None)
            self._save()

    def _save(self):
        with open(self.fn, 'w') as f:
            f.write(json.dumps(self.data, indent=4))
        self._file_data = self._load_own_data()

    def _gen_data(self, *args):
        raise NotImplementedError

    def keys(self):
        return set(list(self.data.keys()) + list(self._file_data.keys()))

    def set_if_not_set(self, key, value):
        try:
            return self[key]
        except KeyError:
            self[key] = value
            return self[key]

    def __contains__(self, item):
        return item in self.keys()


class Parameters(dict):
    """Class providing parameters (dict subclass)"""
    def __init__(self, copy=None, config=None, token=None, roasts=None):
        super().__init__()
        if copy is not None:
            self.update(copy)
        self['roasts'] = []
        self.read_config(config)
        self.read_token(token)
        self.read_roasts(roasts)
        self.string2ids()

    def __call__(self, key, default=None):
        """Make this callable, allowing us to avoid/handle key errors"""
        return self.dget(key, default)

    def dget(self, key, default=None):
        """Like get, but check the defaults if we don't have the key"""
        return self.get(key, defaults.get(key, default))

    def read_config(self, fn=None):
        """Parse the config file, and update self with content"""
        if fn is None:
            fn = self.dget('config_file')
        if not fn:
            return
        try:
            with open(fn, 'r') as f:
                out = json.load(f)
        except IOError:
            return
        self.update(out)

    def read_token(self, fn=None):
        """Read token from file, and update self"""
        if fn is None:
            fn = self.dget('token_file')
        try:
            with open(fn, 'r') as f:
                lines = filter(None, [i.split('#')[0].strip() for i in f.readlines()])
                lines = list(lines)
        except IOError:
            self['token'] = fn
            return self['token']
        if len(lines) != 1:
            raise ValueError('Token file not properly formatted.')
        self['token'] = lines[0]
        return self['token']

    def read_roasts(self, fn=None, add=True):
        """Read roast file, one line per roast"""
        if fn is None:
            fn = self.dget('roast_file')
        with open(fn, 'r') as f:
            lines = list(filter(None, [i.strip() for i in f.readlines()]))
        if add:
            self['roasts'].extend(lines)
        else:
            self['roasts'] = lines
        return self['roasts']

    def string2ids(self, *keys):
        """Convert strings to integer IDs if possible, silently ignore if not"""
        if not keys:
            keys = self.keys()
        for key in keys:
            if key not in self:
                continue
            if not isinstance(self[key], str):
                continue
            if self[key].isdigit():
                self[key] = int(self[key])
            elif "channel" in key or key == "ignore_list":
                if self[key] in channels:
                    self[key] = channels[self[key]]
            elif key == "nemeses":
                self[key] = [users[i] for i in self[key].split(',')]


class PermaDict:
    def __init__(self, fn):
        self.fn = fn
        self.file = shelve.open(fn)

    def __del__(self):
        self.file.sync()
        self.file.close()

    def __getitem__(self, key):
        return self.file[str(key)]

    def __setitem__(self, key, value):
        self.file[str(key)] = value

    def get(self, key, default):
        return self.file.get(str(key), default)

    def __contains__(self, item):
        return str(item) in self.file

    def keys(self):
        return list(self.file.keys())

    def items(self):
        return self.file.items()

    def delete(self, key):
        del self.file[str(key)]

    def pop(self, key):
        return self.file.pop(str(key))


class IntPermaDict(PermaDict):
    def __setitem__(self, key, value):
        self.file[str(int(key))] = value

    def keys(self):
        return [int(k) for k in self.file.keys()]


rc = Parameters(copy=defaults)
