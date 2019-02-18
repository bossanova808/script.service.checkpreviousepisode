import xbmc
import xbmcaddon
import xbmcgui
import os
import json
import yaml
from traceback import format_exc

__addon__ = xbmcaddon.Addon()
__cwd__ = __addon__.getAddonInfo('path')
__scriptname__ = __addon__.getAddonInfo('name')
__version__ = __addon__.getAddonInfo('version')
__kodiversion__ = float(xbmcaddon.Addon('xbmc.addon').getAddonInfo('version')[0:4])
__icon__ = __addon__.getAddonInfo('icon')
__ID__ = __addon__.getAddonInfo('id')
__ignoredshowsfile__ = xbmc.translatePath("special://profile/addon_data/" + __ID__ + "/ignoredShows.yaml")
__language__ = __addon__.getLocalizedString

def log(msg):
    xbmc.log("### [%s] - %s" % (__scriptname__,msg,),level=xbmc.LOGDEBUG )

def getSetting(setting):
    return __addon__.getSetting(setting).strip()

# Odd this is needed, it should be a testable state on Player really...
def isPlaybackPaused():
    return bool(xbmc.getCondVisibility("Player.Paused"))

def getIgnoredShowsFromConfig():

    ignoredShows = {}

    # Update our internal list of ignored shows if there are any...
    if os.path.exists(__ignoredshowsfile__):
        log("Loading ignored shows from " + __ignoredshowsfile__)
        with open(__ignoredshowsfile__, 'r') as yaml_file:
            ignoredShows = yaml.load(yaml_file)

    log("Ignored Shows from config is: " + str(ignoredShows))
    return ignoredShows;            


def writeIgnoredShowsToConfig(ignoredShows, tvshowtitle=None, tvshowid=None):
    
    
    
    # Add new show to our dict of ignored shows if there is one...
    if tvshowid:
        log("Set show title " + tvshowtitle + ", id [" + str(tvshowid) + "], to ignore from now on.")
        ignoredShows[tvshowid] = tvshowtitle
    
    # ...and dump the whole dict to our yaml file
    with open(__ignoredshowsfile__, 'w') as yaml_file:
        log("Ignored Shows to write to config is: " + str(ignoredShows))
        yaml.dump(ignoredShows, yaml_file, default_flow_style=False)



# Check if the previous episode is present, and if so if it has been watched
def checkPreviousEpisode():

    ignoredShows = getIgnoredShowsFromConfig()

    log('Playback started!')
    command='{"jsonrpc": "2.0", "method": "Player.GetActivePlayers", "id": 1}'
    jsonobject = json.loads(xbmc.executeJSONRPC(command))
    
    log(str(jsonobject))

    # Only do something is we get a result for our query back from Kodi
    if(len(jsonobject['result']) == 1):
    
        resultitem = jsonobject['result'][0]
        log("Player running with ID: %d" % resultitem['playerid'])
        
        command='{"jsonrpc": "2.0", "method": "Player.GetItem", "params": { "playerid": %d }, "id": 1}' % resultitem['playerid']
        jsonobject = json.loads(xbmc.executeJSONRPC(command))
        
        # Only do something is this is an episode of a TV show
        if(jsonobject['result']['item']['type'] == 'episode'):
            
            log("An Episode is playing!")
            
            command='{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodeDetails", "params": { "episodeid": %d, "properties": ["tvshowid", "showtitle", "season", "episode"] }, "id": 1}' % jsonobject['result']['item']['id']
            jsonobject = json.loads(xbmc.executeJSONRPC(command))
            log(jsonobject)

            # Only do something if we can get the episode details from Kodi
            if(len(jsonobject['result']) == 1):

                playingTvshowid = jsonobject['result']['episodedetails']['tvshowid']
                playingTvshowTitle = jsonobject['result']['episodedetails']['showtitle']
                playingSeason = jsonobject['result']['episodedetails']['season']
                playingEpisode = jsonobject['result']['episodedetails']['episode']
                log("Playing Info: SHOWTITLE '%s', TVSHOWID '%d', SEASON: '%d', EPISODE: '%d'" % (playingTvshowTitle, playingTvshowid, playingSeason, playingEpisode))
            
                # Ignore first episodes...
                if(jsonobject['result']['episodedetails']['episode'] > 1):                    
             
                    command='{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": { "tvshowid": %d, "season": %d, "properties": ["episode", "playcount"] }, "id": 1}' % (jsonobject['result']['episodedetails']['tvshowid'], jsonobject['result']['episodedetails']['season'])
                    jsonobject = json.loads(xbmc.executeJSONRPC(command))
                    
                    # We found some episodes for this show...
                    if(len(jsonobject['result']) > 0):
                        #log("Finding...")
                        found = False
                        playcount = 0
                        for episode in jsonobject['result']['episodes']:
                            if(episode['episode'] == (playingEpisode - 1)):
                                #log("FOUND!")
                                playcount += episode['playcount']
                                found = True
                        
                        #log("Found: " + str(found) + " playcount: " + str(playcount)) 

                        if (not found and getSetting("IgnoreIfEpisodeAbsentFromLibrary").lower() != 'true') or (found and playcount == 0):

                            if playingTvshowid in ignoredShows:
                                log("Unplayed previous episode detected, but show set to ignore: " + playingTvshowTitle)
                            else:
                                # Only trigger the pause if the player is actually playing as other addons may also have paused the player
                                if not isPlaybackPaused(): 
                                    #log("Pausing playback!")                           
                                    xbmc.Player().pause()

                                result = xbmcgui.Dialog().select('Previous episode not watched!  Play on?', ['No','Yes', 'Yes - and from now on, ignore this show'], preselect=0)

                                # User has requested we ignore this particular show from now on...
                                if result==2:
                                    writeIgnoredShowsToConfig(ignoredShows, playingTvshowTitle, playingTvshowid)

                                if (result==1 or result==2):
                                    if isPlaybackPaused():
                                        xbmc.Player().pause()
                                else:
                                    xbmc.Player().stop()

                                    if(getSetting("BrowseForShow").lower() == "true"):                                    
                                        # Jump to this shows Episode in the Kodi library
                                        command='{"jsonrpc": "2.0", "method": "GUI.ActivateWindow", "params": { "window": "videos", "parameters": [ "videodb://2/2/%d/%d" ] }, "id": 1}' % (playingTvshowid, playingSeason)
                                        xbmc.executeJSONRPC( command )

def manageIgnored():

    log("Managing ignored shows...")

    dialog = xbmcgui.Dialog()

    ignoredShows = getIgnoredShowsFromConfig()

    if len(ignoredShows) < 1:
        dialog.notification(__scriptname__, __language__(32012) , xbmcgui.NOTIFICATION_INFO, 5000)
    else:        

        # Convert our dict to a list for the dialog...
        ignoredlist = []
        for key, value in ignoredShows.iteritems():
            ignoredlist.append(value)
        
        if ignoredlist != []:
            selected = dialog.select("Select show to stop ignoring:", ignoredlist)
            if selected != -1:
                showtitle = ignoredlist[selected]
                log("User has requested we stop ignoring: " + showtitle)
                log("Ignored shows before removal is: " + str(ignoredShows))
                # find the key (tvshowid) for this show& remove from dict
                key = ignoredShows.keys()[ignoredShows.values().index(showtitle)]
                ignoredShows.pop(key, None)
                log("Ignored shows  after removal is: " + str(ignoredShows))

                # No ignored shows?  Delete the empty file..
                if len(ignoredShows) == 0:
                    if os.path.exists(__ignoredshowsfile__):
                        os.remove(__ignoredshowsfile__)                
                else:    
                    # write the ignored list back out
                    writeIgnoredShowsToConfig(ignoredShows)


# Listen to appropriate events for different Kodi versions

class MyPlayer( xbmc.Player ):

    def __init__( self, *args, **kwargs ):
        xbmc.Player.__init__( self )
        log('MyPlayer - init ')

    def onPlayBackStarted( self ):
        if __kodiversion__ < 17.9:
            checkPreviousEpisode()

    def onAVStarted( self ):
        if __kodiversion__ >= 17.9:
            checkPreviousEpisode()

# RUNMODES - we're either running as a service, or we're running the tool to manage ignored shows..

# Initial setup
ignoredShows = {}

### MANAGE IGNORED SHOWS
if len(sys.argv) > 1:
    try:
        if sys.argv[1].startswith('ManageIgnored'):
            manageIgnored()
    #if not, carry on, nothing to see here...
    except Exception as inst:
        log("Exception in ManageIgnored: " + format_exc(inst))

###  RUNNING AS A SERVICE
else:

    log( "Version: %s Started" % (__version__))
    # # Kodi Krypton and below:
    if __kodiversion__ < 17.9:
        log('Kodi ' + str(__kodiversion__) + ', listen to onPlayBackStarted')
    # Kodi Leia and above:
    else:
        log('Kodi ' + str(__kodiversion__) + ', listen to onAVStarted')

    player_monitor = MyPlayer()
    while not xbmc.abortRequested:
          xbmc.sleep(100)






