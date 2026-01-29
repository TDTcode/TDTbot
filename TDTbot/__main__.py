from aiohttp.client_exceptions import ClientConnectorError
import argparse
import importlib
import sys
import time
import tracemalloc
from . import log_init

# for traceback info to debug
tracemalloc.start()

# setup and parse command line options
parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config',
                    default=None,
                    type=str,
                    help='Load given config file.')
parser.add_argument('-t', '--token',
                    default=None,
                    type=str,
                    help='Use provided API token/file.')
parser.add_argument('-r', '--roasts',
                    default=None,
                    type=str,
                    help='Use provided roast file.')
parser.add_argument('-v', '--verbose',
                    default=False,
                    action='store_true',
                    help="print all output, timestamps and logging information")
parser.add_argument('-l', '--logfile',
                    type=str,
                    default=None,
                    help='Set filename of logfile')
args = parser.parse_args()

now = 0
logger = log_init.logger
reissue, startup = None, None
# while it takes more than 5 second to complete this loop
while time.time() - now > 5:
    now = time.time()
    from . import param, bot, git_manage, reloader, wit_data
    # init param
    param.rc.read_config(args.config)
    token = param.rc.read_token(args.token)
    param.rc.read_roasts(args.roasts, add=False)
    kwargs = dict()
    kwargs.update(vars(args))
    kwargs.update(param.rc)
    log_init.init_logging(**kwargs)

    # init bot
    tdt_bot = bot.MainBot(reissue=reissue, startup=startup)
    try:
        # start bot loop
        tdt_bot.run(token)
    except KeyboardInterrupt as e:
        raise e
    except RuntimeError as e:
        logger.info(e)
    except KeyError as e:
        logger.error(e)
    except ClientConnectorError as e:
        logger.error(e)
        time.sleep(60)
    # if we get here, bot loop has ended
    try:
        # try to update own code via git
        git_manage.update()
    except Exception as e:
        logger.error(e)
    reissue, startup = tdt_bot.reissue, tdt_bot.startup
    # reload all packages
    for i in range(2):
        reloader.reload_package(sys.modules[__name__])
        importlib.reload(wit_data)
        importlib.reload(param)
        importlib.reload(git_manage)
        importlib.reload(reloader)
        importlib.reload(bot)
    del param, bot, git_manage, reloader, wit_data
    logger.info("End of loop.")
