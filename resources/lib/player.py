from bossanova808.logger import Logger
from bossanova808.utilities import *
# noinspection PyPackages
from .store import Store
import xbmc
import json


class KodiPlayer(xbmc.Player):
    """
    This class represents/monitors the Kodi video player
    """

    def __init__(self, *args):
        xbmc.Player.__init__(self)
        Logger.debug('KodiPlayer __init__')

    def onAVStarted(self):
        """
        This does all the actual work...check if the previous episode exists, and if it has been watched.

        :return:
        """
        Logger.debug('onAVStarted')

        command = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "Player.GetActivePlayers",
        })
        json_object = send_kodi_json("Get active players", command)

        # Only do something is we get a result for our query back from Kodi
        if len(json_object['result']) == 1:

            Logger.debug(f"Player running with ID: {json_object['result'][0]['playerid']}")

            command = json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "Player.GetItem",
                "params": {
                    "playerid": json_object['result'][0]['playerid']
                }
            })
            json_object = send_kodi_json("Get playing item", command)

            # Only do something is this is an episode of a TV show
            if json_object['result']['item']['type'] == 'episode':

                if 'id' not in json_object['result']['item']:
                    Logger.warning("An episode is playing, but it doesn't have an id, so can't check previous episode in Kodi library.")
                    return

                Logger.info(f"A TV show episode is playing (id: {json_object['result']['item']['id']}).")

                command = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "VideoLibrary.GetEpisodeDetails",
                    "params": {
                        "episodeid": json_object['result']['item']['id'],
                        "properties": ["tvshowid", "showtitle", "season", "episode", "resume"]
                    }
                })
                json_object = send_kodi_json("Get episode details", command)

                # Only do something if we can get the episode details from Kodi
                if len(json_object['result']) == 1:

                    playing_tvshowid = json_object['result']['episodedetails']['tvshowid']
                    playing_tvshow_title = json_object['result']['episodedetails']['showtitle']
                    playing_season = json_object['result']['episodedetails']['season']
                    playing_episode = json_object['result']['episodedetails']['episode']
                    resume_point = json_object['result']['episodedetails']['resume']['position']

                    Logger.info(f'Playing - title: {playing_tvshow_title} , id: {playing_tvshowid} , season: {playing_season}, episode: {playing_episode}, resume: {resume_point}')

                    # Is show set to be ignored?
                    if Store.ignored_shows and playing_tvshowid in Store.ignored_shows:
                        Logger.info(f'Show {playing_tvshow_title} set to ignore, so allowing.')
                        return

                    # Is the resume point is non-zero - then we've previously made a decision about playing this episode, so don't make the user make it again
                    if resume_point > 0.0:
                        Logger.info(f"Show {playing_tvshow_title} Season {playing_season} Episode {playing_episode} has a non-zero resume point, so decision has been previously made to play this episode, so allowing.")
                        return

                    # We ignore first episodes...
                    if json_object['result']['episodedetails']['episode'] > 1:

                        command = json.dumps({
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "VideoLibrary.GetEpisodes",
                            "params": {
                                "tvshowid": json_object['result']['episodedetails']['tvshowid'],
                                "season": json_object['result']['episodedetails']['season'],
                                "properties": ["episode", "playcount"]
                            }
                        })
                        json_object = send_kodi_json("Get episodes for season", command)

                        # We found some episodes for this show...
                        if len(json_object['result']) > 0:
                            found = False
                            playcount = 0
                            for episode in json_object['result']['episodes']:
                                if episode['episode'] == (playing_episode - 1):
                                    playcount += episode['playcount']
                                    found = True

                            Logger.info(f'Found previous episode: {found}, playcount: {playcount}, ignore if absent: {Store.ignore_if_episode_absent_from_library}')

                            # If we couldn't find the previous episode in the library
                            # AND the user has asked us to ignore this, we're done.
                            if not found and Store.ignore_if_episode_absent_from_library:
                                Logger.info("Previous episode was not found in library, and setting ignore if absent from library is true, so allowing.")
                                return

                            # If we couldn't find the previous episode in the library,
                            # OR we have found the previous episode AND it is unwatched...
                            if not found or (found and playcount == 0):

                                # Only trigger the pause if the player is actually playing as other addons may also have paused the player
                                if not is_playback_paused():
                                    Logger.info("Prior episode not watched! -> pausing playback")
                                    self.pause()

                                # Set a window property per Hitcher's request - https://forum.kodi.tv/showthread.php?tid=355464&pid=3191615#pid3191615
                                HOME_WINDOW.setProperty("CheckPreviousEpisode", "MissingPreviousEpisode")
                                result = xbmcgui.Dialog().select(LANGUAGE(32020), [LANGUAGE(32021), LANGUAGE(32022), LANGUAGE(32023)], preselect=0)
                                HOME_WINDOW.setProperty("CheckPreviousEpisode", "")

                                # User has requested we ignore this particular show from now on...
                                if result == 2:
                                    Logger.info(f"User has requested we ignore ({playing_tvshowid}) {playing_tvshow_title} from now on.")
                                    Store.write_ignored_shows_to_config(playing_tvshow_title, playing_tvshowid)

                                if result == 1 or result == 2:
                                    if is_playback_paused():
                                        Logger.info(f"Unpausing playback due to user input ({result})")
                                        self.pause()
                                else:
                                    Logger.info(f"Stopping playback due to user input ({result})")
                                    self.stop()

                                    if Store.force_browse:
                                        Logger.info("Force browsing to show/season, as per user configuration")
                                        # Special case is the user wants to go to the All Seasons view
                                        if Store.force_all_seasons:
                                            playing_season = -1

                                        command = json.dumps({
                                            "jsonrpc": "2.0",
                                            "id": 1,
                                            "method": "GUI.ActivateWindow",
                                            "params": {
                                                "window": "videos",
                                                "parameters": [f'videodb://tvshows/titles/{playing_tvshowid}/{playing_season}'],
                                            }
                                        })
                                        send_kodi_json(f'Browse to {playing_tvshow_title}', command)
