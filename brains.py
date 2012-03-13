import datastore
import constants
import twitter
import verbivorejr
import datetime
import config
import logging
import random
from google.appengine.api import taskqueue
from google.appengine.api import namespace_manager
import settings
import state


# don't take any longer than this to process.
TIME_LIMIT = datetime.timedelta( minutes=9 )

def digest_user( api, deadline, mm_twitteruser ):
	
	last_id = mm_twitteruser.last_id
	num_statuses = 20
	if last_id is None:
		# if we haven't seen this user before, get more statuses for better input
		num_statuses = 100

	if mm_twitteruser.id_str:
		statuses = api.user_timeline( count=num_statuses, user_id=mm_twitteruser.id_str, since_id=last_id, include_rts=False )	
	elif mm_twitteruser.screen_name:
		statuses = api.user_timeline( count=num_statuses, screen_name=mm_twitteruser.screen_name, since_id=last_id, include_rts=False )	

	statuses_digested = 0
	if statuses is not None:
		if len(statuses) > 0:
			worker = verbivorejr.VerbivoreWorker()
			for status in reversed(statuses): # reversed so we start at the oldest, in case we have to abort 
				last_id = status.id_str
				worker.digest( status.text, deadline )
				statuses_digested = statuses_digested + 1
				if datetime.datetime.now() >= deadline:
					logging.debug( "brains.digest_user(), hit deadline at %d statuses" % statuses_digested )
					break
			worker.put( deadline )
			mm_twitteruser.last_id = last_id
			mm_twitteruser.put()
	
	return statuses_digested

def post_tweet( api, tweet, in_reply_to_status_id=None ):
	if tweet is not None:
		try:
			api.update_status( status=tweet, in_reply_to_status_id=in_reply_to_status_id )
			# print tweet
			# logging.debug( tweet )
		except Exception, err:
			logging.debug( "brains.run(): error from twitter api: %s" % err )

def run( creds, force_tweet=False ):

	logging.debug( "brains.run(), force_tweet is %s" % force_tweet )

	then = datetime.datetime.now()
	bot_settings = settings.get_settings( creds )

	if force_tweet is False:
		bot_state = state.get_state( creds )
		lastrun = bot_state.last_run
		if lastrun is not None:
			nextrun = lastrun + datetime.timedelta( hours=bot_settings.tweet_frequency )
			if nextrun > then:
				logging.debug( "-> not due yet" )
				return

		bot_state.last_run = then
		bot_state.put()

	deadline = then + TIME_LIMIT
	learning_style = bot_settings.learning_style
	api = twitter.get_api( creds )
	statuses_digested = 0

	namespace_manager.set_namespace( creds.screen_name )

	logging.debug( "brains.run(): learning_style is: %s" % learning_style )
	if learning_style == constants.learning_style_oneuser:
		# learn from one user
		guru_name = bot_settings.learning_guru
		guru = twitter.get_user( screen_name=guru_name )
		statuses_digested = digest_user( api, deadline, guru )
	elif learning_style == constants.learning_style_following:
		guru_ids = api.friends_ids( stringify_ids=True )
		for guru_id in guru_ids:
			guru = twitter.get_user( id_str=guru_id )
			statuses_digested += digest_user( api, deadline, guru )
	
	logging.debug( "brains.run(): digested %d new statuses" % statuses_digested )

	# check deadline
	if datetime.datetime.now() >= deadline:
		logging.debug( "brains.run(): aborted after put()'ing worker, deadline is looming." )
		taskqueue.add( url="/%s/run" % api.me().screen_name )
		return

	# only continue if chance is met
	if bot_settings.tweet_chance < random.random() and force_tweet is False:
		logging.debug( "brains.run(): didn't meet tweet_chance of %2.1f" % bot_settings.tweet_chance )
		return

	do_tweet = False

	if force_tweet:
		logging.debug( "brains.run(): force_tweet is set" )
		do_tweet = True
	elif bot_settings.locquacity_onschedule:
		logging.debug( "brains.run(): will tweet on schedule" )
		do_tweet = True
	elif bot_settings.locquacity_speakonnew and statuses_digested > 0 :
		logging.debug( "brains.run(): locquacity_speakonnew, statuses_digested: %s" % statuses_digested )
		do_tweet = True
	
	if do_tweet:
		queen = verbivorejr.VerbivoreQueen()
		tweet = None
		safety = 3
		while tweet is None and safety > 0:
			tweet = queen.secrete( 130, deadline )
			safety = safety - 1
		if tweet is not None:
			post_tweet( api, tweet )

	if bot_settings.locquacity_reply:
		
		last_replied_id = creds.last_replied_id
		mentions = api.mentions( since_id=last_replied_id )
		
		for mention in mentions:
			
			reply = "@%s" % mention.author.screen_name
			tweet = None
			safety = 3
			while tweet is None and safety > 0:
				if datetime.datetime.now() >= deadline:
					break
				tweet = queen.secrete_reply( mention.text, 130 - len(reply), deadline )
				safety = safety -1

			if tweet is not None:
				last_replied_id = mention.id_str
				reply = "%s %s" % (reply, tweet)
				post_tweet( api, reply, last_replied_id )
				

		creds.last_replied_id = last_replied_id
		creds.put()

	now = datetime.datetime.now()
	elapsed = now - then
	logging.debug( "brains.run(): completed in %d seconds" % elapsed.seconds )