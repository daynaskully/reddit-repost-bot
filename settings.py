import os
import string

SYACR_CLIENT_ID = os.getenv('SYACR_CLIENT_ID')
SYACR_CLIENT_SECRET = os.getenv('SYACR_CLIENT_SECRET')
SYACR_ACCESS_TOKEN = os.getenv('SYACR_ACCESS_TOKEN')
SYACR_REFRESH_TOKEN = os.getenv('SYACR_REFRESH_TOKEN')
ARKENTHERA_BOT_TOKEN = os.getenv('SYACR_SLACK_BOT_TOKEN')
ARKENTHERA_BOT_ID = 'U314U4AS1'

UA = 'Syac repost catcher by u/arkenthera'
scopeString = 'account creddits edit flair history identity livemanage modconfig modcontributors modflair modlog modothers modposts modself modwiki mysubreddits privatemessages read report save submit subscribe vote wikiedit wikiread'

SCOPES = scopeString.split(' ', len(scopeString))
