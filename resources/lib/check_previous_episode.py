import xbmcgui

from bossanova808.constants import TRANSLATE
from bossanova808.logger import Logger
from bossanova808.notify import Notify
# noinspection PyPackages
from .store import Store
# noinspection PyPackages
from .monitor import KodiEventMonitor
# noinspection PyPackages
from .player import KodiPlayer


def manage_ignored():
    """
    Manage ignored shows in settings...

    :return:
    """

    Logger.info("Managing ignored shows...")
    dialog = xbmcgui.Dialog()
    Store.get_ignored_shows_from_config_file()

    # Short circuit if no ignored shows, so nothing to manage...
    if len(Store.ignored_shows) < 1:
        Notify.info(TRANSLATE(32060), 5000)
        return

    # OK, there are ignored shows in the list...

    # Convert our dict to a sorted list for the dialog...
    ignored_list = sorted(Store.ignored_shows.values(), key=lambda s:s.casefold())

    if ignored_list:
        selected = dialog.select(TRANSLATE(32062), ignored_list)
        if selected != -1:
            show_title = ignored_list[selected]
            Logger.info("User has requested we stop ignoring: " + show_title)
            Logger.debug("Ignored shows before removal is: " + str(Store.ignored_shows))
            # find the key (new_to_ignore_tv_show_id) for this show& remove from dict
            key = list(Store.ignored_shows.keys())[list(Store.ignored_shows.values()).index(show_title)]
            Store.ignored_shows.pop(key, None)
            Logger.debug("Ignored shows  after removal is: " + str(Store.ignored_shows))
            Store.write_ignored_shows_to_config()


def run(args):
    """
    This is 'main'

    :return:
    """
    try:
        Logger.start()
        # Initialise the global store and load the addon settings
        Store()

        # TWO RUN-MODES - we're either running as a service, or we're running the tool to manage ignored shows...

        # MANAGE IGNORED SHOWS
        if len(args) > 1 and args[1].startswith('ManageIgnored'):
            manage_ignored()
        # DEFAULT - RUN AS A SERVICE & WATCH PLAYBACK EVENTS
        else:
            Logger.info("Listening to onAvStarted for episode playback.")
            kodi_event_monitor = KodiEventMonitor()
            # noinspection PyUnusedLocal
            kodi_player = KodiPlayer()

            while not kodi_event_monitor.abortRequested():
                if kodi_event_monitor.waitForAbort(1):
                    Logger.debug('Abort Requested')
                    break
    finally:
        Logger.stop()
