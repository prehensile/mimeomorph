# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

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
import types


# don't take any longer than this to process.
TIME_LIMIT = datetime.timedelta( minutes=9 )


def post_tweet( api, tweet, in_reply_to_status_id=None, debug=False ):
	if tweet is not None:
		if debug:
			logging.debug( "brains.post_tweet()[DEBUG MODE]: would post: %s" % tweet )
		else:
			try:
				api.update_status( status=tweet, in_reply_to_status_id=in_reply_to_status_id )
				# print tweet
				# logging.debug( tweet )
			except Exception, err:
				logging.debug( "brains.run(): error from twitter api: %s" % err )

def run( creds, force_tweet=False, debug=False ):	

	if not debug:
		try:
			debug = config.DEBUG_MODE
		except AttributeError:
			pass

	if debug:
		force_tweet = True

	logging.debug( "brains.run(), force_tweet is %s, debug is %s" % (force_tweet, debug) )

	then = datetime.datetime.now()
	bot_settings = settings.get_settings( creds )

	bot_state = state.get_state( creds )
	bot_state.last_run = then
	bot_state.put()

	deadline = then + TIME_LIMIT
	learning_style = bot_settings.learning_style
	api = twitter.get_api( creds )
	statuses_digested = 0

	namespace_manager.set_namespace( creds.screen_name )

	logging.debug( "brains.run(): learning_style is: %s" % learning_style )
	worker = verbivorejr.VerbivoreWorker( api, bot_settings )
	worker.deadline = deadline
	if learning_style == constants.learning_style_oneuser:
		# learn from one user
		guru_name = bot_settings.learning_guru
		guru = twitter.get_user( screen_name=guru_name )
		statuses_digested = worker.digest_user( guru )
	elif learning_style == constants.learning_style_following:
		guru_ids = api.friends_ids( stringify_ids=True )
		statuses_digested = worker.digest_ids( guru_ids )
	elif learning_style == constants.learning_style_followers:
		guru_ids = api.followers_ids( stringify_ids=True )
		statuses_digested = worker.digest_ids( guru_ids )
	
	worker.put()

	logging.debug( "brains.run(): digested %d new statuses" % statuses_digested )

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

	# check deadline, defer tweeting if necessary
	if datetime.datetime.now() >= deadline:
		logging.debug( "brains.run(): aborted after put()'ing worker, deadline is looming." )
		taskqueue.add( url="/%s/run" % api.me().screen_name )
		return
	
	queen = verbivorejr.VerbivoreQueen()
	queen.deadline = deadline

	if do_tweet:
		tweet = None
		safety = 10
		while tweet is None and safety > 0:
			tweet = queen.secrete( 130 )
			safety = safety - 1
		if tweet is not None:
			tweet = verbivorejr.uc_first( tweet )
			post_tweet( api, tweet, debug=debug )

	replied_userids = []
	if bot_settings.locquacity_reply:
		
		last_replied_id = bot_state.last_replied_id	
		logging.debug( "brains.run(): last_replied_id is %s" % last_replied_id )
		mentions = api.mentions( since_id=last_replied_id )
		logging.debug( "-> %d mentions" % len(mentions) )

		my_name = "@%s" % creds.screen_name
		last_timestamp = None
		for mention in mentions:
			
			if datetime.datetime.now() >= deadline:
				break

			# only reply when we've been directly addressed
			#if mention.text[:len(my_name)] != my_name:
			#	break
			logging.debug( "-> reply to %s" % mention.author.screen_name )
			reply = "@%s" % mention.author.screen_name
			tweet = None
			safety = 5
			while tweet is None and safety > 0:
				logging.debug( "--> generate reply, safety=%d" % safety )
				if datetime.datetime.now() >= deadline:
					break
				tweet = queen.secrete_reply( mention.text, 130 - len(reply) )
				safety = safety -1

			if tweet is not None:
				reply = "%s %s" % (reply, tweet)
				post_tweet( api, reply, in_reply_to_status_id=mention.id, debug=debug )
				replied_userids.append( mention.author.id )

			this_timestamp = mention.created_at
			if last_timestamp is None or this_timestamp > last_timestamp:
				last_replied_id = mention.id_str
				last_timestamp = this_timestamp

		bot_state.last_replied_id = last_replied_id
		bot_state.put()


	if bot_settings.locquacity_greetnew:

		if datetime.datetime.now() >= deadline:
			logging.debug( "brains.run(): aborted before greeting new followers, deadline is looming." )
			return

		new_follower_ids = None
		stored_follower_ids = creds.follower_ids
		api_follower_ids = api.followers_ids()
		if stored_follower_ids is None:
			new_follower_ids = api_follower_ids
		else:
			new_follower_ids = []
			for api_follower_id in api_follower_ids:
				if api_follower_id not in stored_follower_ids:
					new_follower_ids.append( api_follower_id )

		if new_follower_ids is not None and len(new_follower_ids) > 0:
			logging.debug( "brains.run(): new_follower_ids: %s" % new_follower_ids )
			for new_follower_id in new_follower_ids:
				if new_follower_id not in replied_userids:
					tw_user = api.get_user( user_id=new_follower_id )
					screen_name = tw_user.screen_name
					safety = 5
					greeting = None
					while greeting is None and safety > 0:
						greeting = queen.secrete_greeting( screen_name, 130 )
					if greeting is not None:
						post_tweet( api, greeting, debug=debug )
		else:
			logging.debug( "brains.run(): no new followers" )

		creds.follower_ids = api_follower_ids
		creds.put()

	now = datetime.datetime.now()
	elapsed = now - then
	logging.debug( "brains.run(): completed in %d seconds" % elapsed.seconds )