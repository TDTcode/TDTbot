import os
import json

_dir = os.path.split(os.path.realpath(__file__))[0]
_config = os.path.join(_dir, 'config')

# Defaults for parameters
defaults = {
    'channel':         'devoted_chat',
    'cmd_prefix':      ['TDT$', 'Tdt$', 'tdt$'],
    'config_file':     os.path.join(_config, 'tdt.json'),
    'token_file':      os.path.join(_config, 'token.txt'),
    'roast_file':      os.path.join(_config, 'roasts.txt'),
    'nemeses':         [221778796250923008,  # UnknownElectro
                        722927617740767344,  # wator
                        527171804851339274,  # potto
                        ],
    'add_bots':        ['Nowwut#4292'],
    'ignore_list':     ['badass_chat', 'lfg', 'lenny_laboratory', 'manual_page',
                        'tdt_events', 'movie_night', 'my_games'],
    'event_channel':   'tdt_events',
    'log_channel':     'debugging',
    'fashion_channel': 'debugging',
    'event_reminders': [360, 60, 0],
    'timezone':        'America/Los_Angeles',
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
        return list(self.data.keys()) + list(self._file_data.keys())

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

    def __call__(self, key, default=None):
        """Make this callable, allowing us to avoid/handle key errors"""
        return self.dget(key, default)

    def dget(self, key, default=None):
        """Like get, but check the defaults first"""
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


rc = Parameters(copy=defaults)
