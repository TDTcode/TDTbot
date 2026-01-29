import logging


logger = logging.getLogger('discord')


# https://stackoverflow.com/a/35804945/2275975
def addLoggingLevel(levelName, levelNum, methodName=None):
    """
    Comprehensively adds a new logging level to the `logging` module and the
    currently configured logging class.

    `levelName` becomes an attribute of the `logging` module with the value
    `levelNum`. `methodName` becomes a convenience method for both `logging`
    itself and the class returned by `logging.getLoggerClass()` (usually just
    `logging.Logger`). If `methodName` is not specified, `levelName.lower()` is
    used.

    To avoid accidental clobberings of existing attributes, this method will
    raise an `AttributeError` if the level name is already an attribute of the
    `logging` module or if the method name is already present

    Example
    -------
    >>> addLoggingLevel('TRACE', logging.DEBUG - 5)
    >>> logging.getLogger(__name__).setLevel("TRACE")
    >>> logging.getLogger(__name__).trace('that worked')
    >>> logging.trace('so did this')
    >>> logging.TRACE
    5

    """
    if not methodName:
        methodName = levelName.lower()

    if hasattr(logging, levelName):
        return
        # raise AttributeError('{} already defined in logging module'.format(levelName))
    if hasattr(logging, methodName):
        raise AttributeError('{} already defined in logging module'.format(methodName))
    if hasattr(logging.getLoggerClass(), methodName):
        raise AttributeError('{} already defined in logger class'.format(methodName))

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def logForLevel(self, message, *args, **kwargs):
        if self.isEnabledFor(levelNum):
            self._log(levelNum, message, args, **kwargs)

    def logToRoot(message, *args, **kwargs):
        logging.log(levelNum, message, *args, **kwargs)

    logging.addLevelName(levelNum, levelName)
    setattr(logging, levelName, levelNum)
    setattr(logging.getLoggerClass(), methodName, logForLevel)
    setattr(logging, methodName, logToRoot)


addLoggingLevel("PRINTV", 25)


class CriticalExceptionFilter(logging.Filter):
    """Filter out critical exceptions"""
    def filter(self, record):
        return not record.exc_info or record.levelno != logging.CRITICAL


def init_logging(logfile=None, visual_log_level=logging.PRINTV, verbose=False, **kwargs):
    """Initialize log"""
    # setting this to zero gives output control to handler
    logging.basicConfig(level=visual_log_level)
    logger.propagate = False  # don't use default handler
    for h in list(logger.handlers):
        logger.removeHandler(h)
    if logfile:
        f_handler = logging.FileHandler(filename=logfile, encoding='utf-8', mode='a')
        fmt = '%(asctime)s:%(levelname)s:%(name)s: %(message)s'
        f_handler.setFormatter(logging.Formatter(fmt))
        f_handler.setLevel(0)
        logger.addHandler(f_handler)
    c_handler = logging.StreamHandler()  # console/terminal handler
    c_handler.setLevel(visual_log_level)
    c_handler.addFilter(CriticalExceptionFilter())  # let stderr print errors to screen
    c_handler.setFormatter(logging.Formatter('%(message)s'))  # only show the message
    if verbose:
        c_handler.setLevel(0)
        c_handler.setFormatter(logging.Formatter('%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(c_handler)
