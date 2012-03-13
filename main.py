#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
import tweepy
import twitter
import logging
import config
import datastore
import brains
import settings
from google.appengine.ext.webapp import template
import constants
import os
from google.appengine.api import users
from google.appengine.api import taskqueue


def get_url( request, path ):
	callback_url = request.url
	callback_url = callback_url[:callback_url.rfind("/")]
	callback_url += path
	return callback_url

class MainHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write('Hello world!')

class SessionCleanupHandler( webapp.RequestHandler ):
	def get(self):
		while not delete_expired_sessions():
			pass
		message = "Cleaned up expired sessions."
		logging.log( 1, message )
		self.response.out.write( message )

class RunHandler( webapp.RequestHandler ):
	
	def run_one( self, bot_name ):
		creds = twitter.get_twitter_creds( bot_name )
		force_tweet = self.request.get( "force_tweet") == "true"
		brains.run( creds, force_tweet )

	def run_all( self ):
		creds = twitter.get_all_creds()
		for mm_twittercreds in creds:
			taskqueue.add( "%s/run" % mm_twittercreds.screen_name )

	def handle_both( self, bot_name=None ):
		if bot_name is None:
			self.run_all()
		else:
			self.run_one( bot_name )

	def get( self, bot_name=None ):
		self.handle_both( bot_name )
	
	def post( self, bot_name=None ):
		self.handle_both( bot_name )  

def path_for_template( template_name ):
	return os.path.join( os.path.dirname(__file__), 'templates', template_name )

class SettingsHandler( webapp.RequestHandler ):
	
	def render_template( self, creds, bot_settings=None, values=None ):
		
		template_values = {}
		if values is not None:
			template_values.update( values )
		template_values[ "form_action" ] = self.request.path

		if creds.screen_name is not None:
			template_values[ 'twitter_username' ] = creds.screen_name

		if( bot_settings is None ):
			bot_settings = settings.get_settings( creds )

		template_values[ 'guru_name' ] = bot_settings.learning_guru
		template_values[ "tweet_frequency" ] = bot_settings.tweet_frequency
		template_values[ "tweet_chance" ] = bot_settings.tweet_chance

		try:
			lists_in = creds.lists
			if lists_in:
				lists_out = []
				for list_in in lists_in:
					lists_out.append( { 'name' : list_in.name, 'id' : list_in.id_str } )  
				template_values[ 'lists' ] = lists_out
		except Exception, err:
			pass

		if bot_settings.learning_style == constants.learning_style_oneuser:
			template_values[ 'learnfrom_oneuser_checked' ] = "checked"
		elif bot_settings.learning_style == constants.learning_style_followers:
			template_values[ 'learnfrom_followers_checked' ] = "checked"
		elif bot_settings.learning_style == constants.learning_style_following:
			template_values[ 'learnfrom_following_checked' ] = "checked"
		elif bot_settings.learning_style == constants.learning_style_list:
			template_values[ 'learnfrom_list_checked' ] = "checked"

		if bot_settings.locquacity_onschedule: 
			template_values[ 'locquacity_onschedule_checked' ] = "checked"
		if bot_settings.locquacity_reply:
			template_values[ 'locquacity_reply_checked' ] = "checked"
		if bot_settings.locquacity_speakonnew:
			template_values[ 'locquacity_speakonnew_checked' ] = "checked"

		path = path_for_template( "settings.html" )
		self.response.out.write( template.render( path, template_values ) )

	def authenticate_user( self, creds ):
		user = users.get_current_user()
		return user is not None and user == creds.owner

	# straight page load, dish out template
	def get( self, bot_name ):
		creds = twitter.get_twitter_creds( bot_name )
		if self.authenticate_user( creds ):
			self.render_template( creds ) 
		else:
			path = path_for_template( "notowner.html" )
			self.response.out.write( template.render( path, template_values ) )
	
	# form data has been posted, process it
	def post( self, bot_name ):
		
		creds = twitter.get_twitter_creds( bot_name )

		if not self.authenticate_user( creds ):
			path = path_for_template( "notowner.html" )
			self.response.out.write( template.render( path, template_values ) )
		else:
			bot_settings = settings.get_settings( creds )
			bot_settings.learning_style = self.request.get( 'learnfrom' )
			bot_settings.learning_guru = self.request.get( 'guru_name' )
			bot_settings.locquacity_onschedule = self.request.get( 'locquacity_onschedule' ) == "true"
			bot_settings.locquacity_reply = self.request.get( 'locquacity_reply' ) == "true"
			bot_settings.locquacity_speakonnew = self.request.get( 'locquacity_speakonnew' ) == "true"
			tweet_frequency = self.request.get( 'tweet_frequency' )
			if tweet_frequency is not None and len(tweet_frequency) > 0:
				bot_settings.tweet_frequency = float( tweet_frequency )
			tweet_chance = self.request.get( 'tweet_chance' )
			if tweet_chance is not None and len(tweet_chance) > 0:
				bot_settings.tweet_chance = float( tweet_chance )
			self.render_template( creds, bot_settings, { "saved" : True } )
			bot_settings.creds = creds
			bot_settings.put()

class NewHandler( webapp.RequestHandler ):
	
	# vanilla get, serve up new bot page
	def get(self):
		
		template_values = {}
		user = users.get_current_user()

		if user is None:
			msg = "Sorry, you need to be logged in to a Google account to create bots.<br/>"
			msg += "<a href=\"%s\">Sign in or register</a>." % users.create_login_url("/new")
			template_values[ 'message' ] = msg
		else:
			redirect_url = None
			tw_error = None
			callback_url = get_url( self.request, "/oauth_return" )
			template_values[ 'form_action' ] = "/twitter_return"

			try:
				redirect_url = twitter.get_authurl( callback_url )
			except tweepy.TweepError, err:
				tw_error = err

			if tw_error is not None:
				template_values[ 'message' ] = "Error! Failed to get request token."
			else:
				template_values[ "twitter_auth" ] = redirect_url

		path = path_for_template( "new.html" )
		self.response.out.write( template.render( path, template_values ) )

class OAuthReturnHandler( webapp.RequestHandler ):
	def get(self):

		verifier = self.request.get('oauth_verifier')
		tw_error = None
		api = None
		
		try:
			api = twitter.consume_verifier( verifier )	
		except tweepy.TweepError, err:
			tw_error = err

		if tw_error is None:
			me = api.me()
			self.response.out.write( "Auth complete for %s, redirecting..." % me.name )
			redirect_url = get_url( self.request, "/%s/settings" % me.screen_name )
			self.redirect( redirect_url )
		else:
			self.response.out.write( "Error! Failed to get access token." )
			self.response.out.write( tw_error )

def main():
    application = webapp.WSGIApplication( [ ('/', MainHandler),
    										('/new', NewHandler),
    										('/oauth_return', OAuthReturnHandler),
    										('/session_cleanup', SessionCleanupHandler),
    										('/run', RunHandler),
    										('/(.*)/run', RunHandler),
    										('/(.*)/settings', SettingsHandler) ],
                                         debug=True ) 
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
