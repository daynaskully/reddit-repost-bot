import re
import praw
import datetime
import threading
import Queue
import time
import sys

from difflib import SequenceMatcher
from prawoauth2 import PrawOAuth2Mini
from common import Utility
from settings import ARKENTHERA_BOT_TOKEN,ARKENTHERA_BOT_ID
from slackclient import SlackClient

from settings import SYACR_CLIENT_ID, SYACR_CLIENT_SECRET,SYACR_ACCESS_TOKEN,SYACR_REFRESH_TOKEN,UA,SCOPES

reddit_client = praw.Reddit(user_agent=UA)
oauth_helper = PrawOAuth2Mini(reddit_client, app_key=SYACR_CLIENT_ID,
                              app_secret=SYACR_CLIENT_SECRET,
                              access_token=SYACR_ACCESS_TOKEN,
                              refresh_token=SYACR_REFRESH_TOKEN,
                              scopes=SCOPES)


DO_NOTHING = 0
DO_REPORT = 1
DO_REMOVE = 2
DO_IGNORE = 3

ALLOW_REPOSTS_THREE_MONTH = 1
ENABLE_SLACK_INTEGRATION = 1

# Shared variables must exist in all threads
REPORT_THRESHOLD = 0.60
REMOVE_THRESHOLD = 0.95

SUBREDDIT = 'AskReddit'

class QueuedSlackCommand():
    def __init__(self,type, **kwargs):
        self.type = type
        self.__dict__.update(kwargs)

class SyacRepostBot():
    def __init__(self,queue):
        self.sharedQueue = queue

        self.mainTitleOnly = r"\|.*"
        self.Sub = reddit_client.get_subreddit(SUBREDDIT)
        self.TopPosts = list(set([i for i in self.Sub.get_top_from_week(limit=100)] + [i for i in self.Sub.get_top_from_all(limit=100)]))
        self.NewPosts = [i for i in self.Sub.get_new(limit=None)]
        

        self.ReportThreshold = REPORT_THRESHOLD
        self.RemoveThreshold = REMOVE_THRESHOLD

        self.utility = Utility(praw)

        self.thread = threading.Thread(target=self.MainLoop,args=(self.sharedQueue,))
        self.thread.start()

        # Inform slack
        slackMessage = QueuedSlackCommand('send_message',channel='repost_notifications',message='Started analyzing new posts for */r/{}*. Report Threshold: {}. Remove Threshold: {}'.
            format(SUBREDDIT,self.ReportThreshold,self.RemoveThreshold))
        self.sharedQueue.put(slackMessage)
    
    # Main Loop
    # For every new submission, check if it's a repost
    def MainLoop(self,sharedQueue):
        for post in praw.helpers.submission_stream(reddit_client, self.Sub,20):
            RemoveOrReport = False

            for top in self.TopPosts:
                result = self.CompareAndRemove(top, post) 
                if result:
                    RemoveOrReport = True
                    break


            if not RemoveOrReport:
                for new in self.NewPosts:
                    if self.CompareAndRemove(new, post):
                        RemoveOrReport = True
                        break

            if not RemoveOrReport:
                self.NewPosts.append(post)

            self.Log("New Submission Analyzed {} - {} - Report: {} Remove: {}".format(post.id,str(RemoveOrReport),self.ReportThreshold,self.RemoveThreshold))
    

    # The actual logic of reporting/removing
    def CompareAndRemove(self,topPost,newPost):
        result = self.Compare(topPost,newPost)

        if result != DO_NOTHING:
            # Apply 3 month rule
            if ALLOW_REPOSTS_THREE_MONTH and self.CheckThreeMonthsRule(topPost,newPost) == True:
                # This post has been posted at least 3 months ago
                ratio = self.GetRatio(topPost,newPost) * 100
                self.Log("Ignoring report/remove {}. Reason: Three Month Rule. Original: {}".format(newPost.id,topPost.id))
                return DO_IGNORE

            # Ignore if mod post
            if self.utility.IsModPost(self.Sub,newPost):
                self.Log("Ignoring report/remove {}.Reason: Posted by a moderator ({}). Original: {}".format(newPost.id,newPost.author.name,topPost.id))
                return DO_IGNORE

            originalSubmission = datetime.datetime.fromtimestamp(topPost.created)
            newSubmission = datetime.datetime.fromtimestamp(newPost.created)

            if originalSubmission > newSubmission:
                #self.utility.Log("Ignoring report/remove because the new post seems to be not new.")
                return DO_IGNORE

        
        # Report if necessary
        if result == DO_REPORT:
            ratio = self.GetRatio(topPost,newPost) * 100 # For testing

            reason = "I'm *reporting* <{}|{}>... because it is *{:.4}%* similar to <{}|{}...>.".format(
                self.utility.GetPostLink(SUBREDDIT,newPost)
                ,newPost.title[:50].encode('utf-8')
                ,ratio
                ,self.utility.GetPostLink(SUBREDDIT,topPost)
                ,topPost.title[:50].encode('utf-8')
                )

            self.Report(newPost, reason)

        # Remove if necessary
        elif result == DO_REMOVE:
            ratio = self.GetRatio(topPost,newPost) * 100  # For testing
            reason = "I'm *removing* <{}|{}>... because it is *{:.4}%* similar to <{}|{}>....".format(
                self.utility.GetPostLink(SUBREDDIT,newPost)
                ,newPost.title[:50]
                ,ratio
                ,self.utility.GetPostLink(SUBREDDIT,topPost)
                ,topPost.title[:50]
                )

            
            self.Remove(newPost,reason)
        return result
    
    # Checks for the three month rules
    def CheckThreeMonthsRule(self,originalPost,similarPost):
        dateDifference = self.GetMonthDifference(originalPost,similarPost)

        if dateDifference >= 3:
            # Post is allowed
            return True
        else:
            return False
    
    # Compares original posts submission date with the newly submitted one and returns the month difference
    def GetMonthDifference(self,originalPost,similarPost):


        originalSubmission = datetime.datetime.fromtimestamp(originalPost.created)
        newSubmission = datetime.datetime.fromtimestamp(similarPost.created)

        monthDifference = abs(originalSubmission-newSubmission).days / 30

        return monthDifference

    
    def SetReportThreshold(self,new):
        if new >= 0 and new <= 1:
            self.ReportThreshold = new

    def SetRemoveThreshold(self,new):
        if new >= 0 and new <= 1:
            self.RemoveThreshold = new
    
    # Returns the similary ratio using SequenceMatcher
    def SimilarityRatio(self, a, b):
        return SequenceMatcher(None, a, b).ratio()
    
    #
    #
    def GetRatio(self,a,b):
        return self.SimilarityRatio(re.sub(self.mainTitleOnly, "", a.title), re.sub(self.mainTitleOnly, "", b.title))

    # Compares similary ratio against our predefined thresholds
    def Compare(self,a,b):
        if a == b:
            return 0
        ratio = self.GetRatio(a,b)

        if ratio < self.ReportThreshold:
            return DO_NOTHING
        elif ratio < self.RemoveThreshold:
            return DO_REPORT
        else:
            return DO_REMOVE

    
    # Report the post for repost
    def Report(self,post,reason):
        #post.report(reason=reason)

        self.Log("{}".format(reason),True)
    
    # Remove the post
    def Remove(self,post,reason):
        #post.remove()
        self.utility.Log("{}".format(reason),False)

    
    
    def JoinThread(self):
        self.thread.join()

    def Log(self,log,toSlack=False):
        now = datetime.datetime.now()
        formatted = now.strftime("%m/%d/%Y %H:%M:%S")
        logwithdate = "{} - {}".format(formatted,log)

        if ENABLE_SLACK_INTEGRATION == 1 and toSlack:
            slackMessage = QueuedSlackCommand('send_message',channel='repost_notifications',message=log)
            self.sharedQueue.put(slackMessage)

        
        self.utility.Log("Slack- {} - {}".format(str(toSlack),logwithdate))


class SlackIntegration():

    def __init__(self,sharedQueue,syac):
        self.syac = syac
        self.sharedQueue = sharedQueue
        self.slack = SlackClient(ARKENTHERA_BOT_TOKEN)
        

        self.thread = threading.Thread(target=self.MainLoop,args=(self.sharedQueue,))
        self.thread.start()

    def MainLoop(self,queue):
        connectToSlack = self.slack.rtm_connect()
        if connectToSlack:
            while True:
                self.OnSlackMessage(self.slack.rtm_read())

                if queue.qsize() != 0:
                    queuedCommand = queue.get()

                    if queuedCommand.type == 'send_message':
                        self.SendMessage(queuedCommand.channel,queuedCommand.message)
                    queue.task_done()
    
    def HandleCommand(self,command,channel):
        print "{} - {}".format(command,channel)

    def SendMessage(self,channel,message):
        self.slack.api_call(
            "chat.postMessage",
            channel=channel,
            text=message,
            as_user=True)
        #self.slack.rtm_send_message(channel, message)

    def HandleBotCommand(self,channel,command):
        if command == 'help':
            message = 'Available commands: \n *!syac status* : Return current thresholds. \n *!syac reportThreshold [number]*: Set the report threshold [0,1] \n *!syac removeThreshold [number]*: Set the remove threshold [0,1]'
            self.SendMessage(channel,message)

        if command == 'status':
            message = "Current report threshold is *{}* and remove threshold *{}*.".format(self.syac.ReportThreshold,self.syac.RemoveThreshold)
            self.SendMessage(channel,message)
        
        # Report
        if command.startswith('reportThreshold'):
            number = command.split('reportThreshold')[1].strip()

            
            try:
                number = float(number)

                if number >= 0 and number <= 1:
                    message = "Set report threshold to *{}*".format(str(number))
                    self.SendMessage(channel,message)

                    self.syac.ReportThreshold = number
                else:
                    self.SendMessage(channel,"Threshold must be between 0 and 1.")
            except:
                self.SendMessage(channel,"Threshold is invalid.")
        
        # Remove
        if command.startswith('removeThreshold'):
            number = command.split('removeThreshold')[1].strip()

            
            try:
                number = float(number)

                if number >= 0 and number <= 1:
                    message = "Set remove threshold to *{}*".format(str(number))
                    self.SendMessage(channel,message)

                    self.syac.RemoveThreshold = number
                else:
                    self.SendMessage(channel,"Threshold must be between 0 and 1.")
            except:
                self.SendMessage(channel,"Threshold is invalid.")

        


    def OnSlackMessage(self,message):
        output_list = message
        if output_list and len(output_list) > 0:
            for output in output_list:
                if output and 'type' in output and 'text' in output:
                    if output['type'] == 'message':
                        channel = output['channel']
                        message = output['text'].encode('utf-8')
                        
                        if message.startswith('!syac'):
                            split = message.split('!syac')[1].strip()
                            self.HandleBotCommand(channel,split)

    def JoinThread(self):
        self.thread.join()


def main():
    threadSafeQueue = Queue.Queue()

    SyacBot = SyacRepostBot(threadSafeQueue)
    Slack = SlackIntegration(threadSafeQueue,SyacBot)


    SyacBot.JoinThread()
    Slack.JoinThread()

    # except:
    #     e = sys.exc_info()[0]
    #     print e


if __name__ == '__main__':
    main()

