#
# Common stuff that can be reused
#
#

import datetime

DEBUG_MODE = 1
ENABLE_LOGGING = 1
ENABLE_SLACK_INTEGRATION = 1

class Utility():
    cacheMods = True
    def __init__(self,praw):
        self.praw = praw
        self.mods = []

         



    def IsModPost(self,sub,post):
        mods = self.GetMods(sub)

        result = False
        for mod in mods:
            if mod.name == post.author.name:
                result = True
                break
        
        return result

    # Retrieves the moderator list
    # If `cacheMods` is true, it wont call reddit after the first request
    # 
    def GetMods(self,sub):
        if self.cacheMods:
            if len(self.mods) == 0:
                self.mods = self._GetMods(sub)
                return self.mods
            else:
                return self.mods
        else:
            return self._GetMods(sub)


    def _GetMods(self,sub):
        if __debug__:
            self.Log("Retrieving mods...")
        return sub.get_moderators()



    def GetPostLink(self,subname,post):
        return "https://www.reddit.com/r/{}/{}".format(subname,post.id).encode('utf-8')

    def Log(self,log):
        if ENABLE_LOGGING:
            print log
            


