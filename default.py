import xbmc
import xbmcaddon
import xbmcgui
import os
import json
import yaml

__addon__ = xbmcaddon.Addon()
__cwd__ = __addon__.getAddonInfo('path')
__scriptname__ = __addon__.getAddonInfo('name')
__version__ = __addon__.getAddonInfo('version')
__kodiversion__ = float(xbmcaddon.Addon('xbmc.addon').getAddonInfo('version')[0:4])
__icon__ = __addon__.getAddonInfo('icon')
__ID__ = __addon__.getAddonInfo('id')
__ignoredshowsfile__ = xbmc.translatePath("special://profile/addon_data/" + __ID__ + "/ignoredshows.yaml")
__language__ = __addon__.getLocalizedString

global g_jumpBackSecs
global g_ignoredShows

g_jumpBackSecs = 0


def log(msg):
    xbmc.log("### [%s] - %s" % (__scriptname__,msg,),level=xbmc.LOGDEBUG )

def getSetting(setting):
    return __addon__.getSetting(setting).strip()

# Odd this is needed, it should be a testable state on Player really...
def isPlaybackPaused():
    return bool(xbmc.getCondVisibility("Player.Paused"))

def setShowAsIgnored(tvshowtitle, tvshowid):
    log("Set show title " + tvshowtitle + ", id [" + str(tvshowid) + "], to ignore from now on.")
    g_ignoredShows = {'tvshowid':'tvshowtitle'}
    with open('__ignoredshowsfile__', 'w') as yaml_file:
        yaml.dump(g_ignoredShows, yaml_file, default_flow_style=False)

# Check if the previous episode is present, and if so if it has been watched
def checkPreviousEpisode():

    log('Playback started!')
    command='{"jsonrpc": "2.0", "method": "Player.GetActivePlayers", "id": 1}'
    jsonobject = json.loads(xbmc.executeJSONRPC(command))
    
    log(str(jsonobject))

    if(len(jsonobject['result']) == 1):
    
        resultitem = jsonobject['result'][0]
        log("Player running with ID: %d" % resultitem['playerid'])
        
        command='{"jsonrpc": "2.0", "method": "Player.GetItem", "params": { "playerid": %d }, "id": 1}' % resultitem['playerid']
        jsonobject = json.loads(xbmc.executeJSONRPC(command))
        
        if(jsonobject['result']['item']['type'] == 'episode'):
            log("An Episode is playing!")
            
            command='{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodeDetails", "params": { "episodeid": %d, "properties": ["tvshowid", "showtitle", "season", "episode"] }, "id": 1}' % jsonobject['result']['item']['id']
            jsonobject = json.loads(xbmc.executeJSONRPC(command))
            
            log(jsonobject)

            if(len(jsonobject['result']) == 1):
                playingTvshowid = jsonobject['result']['episodedetails']['tvshowid']
                playingTvshowTitle = jsonobject['result']['episodedetails']['showtitle']
                playingSeason = jsonobject['result']['episodedetails']['season']
                playingEpisode = jsonobject['result']['episodedetails']['episode']
                log("Playing Info: SHOWTITLE '%s', TVSHOWID '%d', SEASON: '%d', EPISODE: '%d'" % (playingTvshowTitle, playingTvshowid, playingSeason, playingEpisode))
            
                #Lets see if we have the previous episode
                if(jsonobject['result']['episodedetails']['episode'] > 1): #debuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuuug
                    command='{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": { "tvshowid": %d, "season": %d, "properties": ["episode", "playcount"] }, "id": 1}' % (jsonobject['result']['episodedetails']['tvshowid'], jsonobject['result']['episodedetails']['season'])
                    jsonobject = json.loads(xbmc.executeJSONRPC(command))
                    
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
                            
                            # Only trigger the pause if the player is actually playing as other addons may also have paused the player
                            if not isPlaybackPaused(): 
                                #log("Pausing playback!")                           
                                xbmc.Player().pause()

                            # if not found:
                            #     playon = xbmcgui.Dialog().yesno(__language__(32001), __language__(32002), __language__(32003))
                            # else:
                            #     playon = xbmcgui.Dialog().yesno(__language__(32004), __language__(32005), __language__(32003))                            

                            result = xbmcgui.Dialog().select('Previous episode not watched!  Play on?', ['Yes', 'No', 'Yes - and from now on, ignore this show'], preselect=1)

                            log("Result is")
                            log(result)

                            if (result==0 or result==2):
                                playon = True
                            else:
                                playon = False

                            if result==2:
                                setShowAsIgnored(playingTvshowTitle, playingTvshowid)

                            if playon:
                                 # Only trigger unpause if the player is actually not playing
                                if isPlaybackPaused():
                                    xbmc.Player().pause()
                            else:
                                if(getSetting("BrowseForShow").lower() == "true"):
                                    browsenow = xbmcgui.Dialog().yesno(__language__(32006), __language__(32007))
                                else:
                                    browsenow = False
                                
                                xbmc.Player().stop()
                                if browsenow:
                                    command='{"jsonrpc": "2.0", "method": "GUI.ActivateWindow", "params": { "window": "videos", "parameters": [ "videodb://2/2/%d/%d" ] }, "id": 1}' % (playingTvshowid, playingSeason)
                                    result = xbmc.executeJSONRPC( command )
                                    result = unicode(result, 'utf-8', errors='ignore')


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


# Initial setup

log( "Version: %s Started" % (__version__))
# # Kodi Krypton and below:
if __kodiversion__ < 17.9:
    log('Kodi ' + str(__kodiversion__) + ', listen to onPlayBackStarted')
# Kodi Leia and above:
else:
    log('Kodi ' + str(__kodiversion__) + ', listen to onAVStarted')

g_ignoredShows = yaml.load(__ignoredshowsfile__)
log("Ignored Shows List:")
log(g_ignoredShows)

player_monitor = MyPlayer()
while not xbmc.abortRequested:
      xbmc.sleep(100)
