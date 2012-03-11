import datastore
import constants
import twitter
import verbivorejr
import datetime
import config
import logging
import random
from google.appengine.api import taskqueue

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

def run( force_tweet=False ):

	logging.debug( "brains.run(), force_tweet is %s" % force_tweet )

	then = datetime.datetime.now()
	settings = config.get_settings()

	if force_tweet is False:
		state = config.get_state()
		lastrun = state.last_run
		if lastrun is not None:
			nextrun = lastrun + datetime.timedelta( hours=settings.tweet_frequency )
			if nextrun > then:
				logging.debug( "-> not due yet" )
				return

		state.last_run = then
		state.put()

	deadline = then + TIME_LIMIT
	learning_style = settings.learning_style
	api = twitter.get_api()
	statuses_digested = 0

	logging.debug( "brains.run(): learning_style is: %s" % learning_style )
	if learning_style == constants.learning_style_oneuser:
		# learn from one user
		guru_name = settings.learning_guru
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
		taskqueue.add( url="/run" )
		return

	# only continue if chance is met
	if settings.tweet_chance < random.random() and force_tweet is False:
		logging.debug( "brains.run(): didn't meet tweet_chance of %2.1f" % settings.tweet_chance )
		return

	queen = verbivorejr.VerbivoreQueen()
	tweet = None

	if settings.locquacity_onschedule:
		logging.debug( "brains.run(): will tweet on schedule" )
		tweet = queen.secrete( 130, deadline )
	elif settings.locquacity_speakonnew and statuses_digested > 0 :
		logging.debug( "brains.run(): locquacity_speakonnew, statuses_digested: %s" % statuses_digested )
		tweet = queen.secrete( 130, deadline )

	
	if tweet is not None:
		try:
			api.update_status( status=tweet )
			# print tweet
			#logging.debug( tweet )
		except Exception, err:
			logging.debug( "brains.run(): error from twitter api: %s" % err )

	now = datetime.datetime.now()
	elapsed = now - then
	logging.debug( "brains.run(): completed in %d seconds" % elapsed.seconds )