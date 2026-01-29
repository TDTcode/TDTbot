import os
import tweepy  # type: ignore
import logging


logger = logging.getLogger('discord.' + __name__)

_auth_file = os.path.split(os.path.realpath(__file__))[0]
_auth_file = os.path.join(_auth_file, 'config', 'twitter_auth.txt')


class AuthKeys:
    def __init__(self, fn):
        self.fn = fn
        with open(_auth_file) as f:
            lines = [line.split('#')[0].strip() for line in f.readlines()]
            lines = [line for line in lines if line]
        self.api_key = lines[0]
        self.api_secret = lines[1]
        self.bearer = lines[2]
        self.access_token = lines[3]
        self.access_secret = lines[4]

    @property
    def consumer_key(self):
        return self.api_key

    @property
    def consumer_secret(self):
        return self.api_secret

    @property
    def consumer(self):
        return self.consumer_key, self.consumer_secret

    @property
    def access(self):
        return self.access_token, self.access_secret


_auth_keys = AuthKeys(_auth_file)

# Authenticate to Twitter
auth = tweepy.OAuthHandler(*_auth_keys.consumer)
auth.set_access_token(*_auth_keys.access)

# Create API object
api = tweepy.API(auth)


def tweet(message):
    """Create a tweet"""
    return api.update_status(message)
