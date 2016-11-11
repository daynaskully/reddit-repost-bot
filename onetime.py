import praw
from prawoauth2 import PrawOAuth2Server
import os

from settings import SYACR_CLIENT_ID, SYACR_CLIENT_SECRET,UA,SCOPES

reddit_client = praw.Reddit(user_agent=UA)
oauthserver = PrawOAuth2Server(reddit_client, app_key=SYACR_CLIENT_ID,
                               app_secret=SYACR_CLIENT_SECRET, state=UA,
                               scopes=SCOPES)                               


oauthserver.start()
tokens = oauthserver.get_access_codes()
print(tokens)

print tokens['access_token']
print tokens['refresh_token']