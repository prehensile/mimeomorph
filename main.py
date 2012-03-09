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
from google.appengine.ext.webapp import template
import constants
import os

def get_url( request, path ):
	callback_url = request.url
	callback_url = callback_url[:callback_url.rfind("/")]
	callback_url += path
	return callback_url

class MainHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write('Hello world!')

class AuthHandler( webapp.RequestHandler ):
	def get(self):
		
		callback_url = get_url( self.request, "/oauth_return" )
		redirect_url = None
		tw_error = None

		try:
			redirect_url = twitter.get_authurl( callback_url )
		except tweepy.TweepError as err:
			tw_error = err
		
		if redirect_url:
			self.response.out.write( "Redirecting to twitter for authorisation..." )
			self.redirect( redirect_url )
		else:
			self.response.out.write( "Error! Failed to get request token.\not" )
			self.response.out.write( tw_error )	


class AuthReturnHandler( webapp.RequestHandler ):
	def get(self):
		verifier = self.request.get('oauth_verifier')
		
		tw_error = None
		api = None
		try:
			api = twitter.consume_verifier( verifier )	
		except tweepy.TweepError as err:
			tw_error = err

		if tw_error is None:
			self.response.out.write( "Auth complete for %s" % api.me().name )
			redirect_url = get_url( self.request, "/settings" )
			self.redirect( redirect_url )
		else:
			self.response.out.write( "Error! Failed to get access token." )
			self.response.out.write( tw_error )

class SessionCleanupHandler( webapp.RequestHandler ):
	def get(self):
		while not delete_expired_sessions():
			pass
		message = "Cleaned up expired sessions."
		logging.log( 1, message )
		self.response.out.write( message )

class RunHandler( webapp.RequestHandler ):
	def get(self):
		brains.run()

def path_for_template( template_name ):
	return os.path.join( os.path.dirname(__file__), 'templates', template_name )

class SettingsHandler( webapp.RequestHandler ):
	
	def render_template( self, values=None, settings=None ):
		
		if( settings is None ):
			settings = config.get_settings()
		
		creds = twitter.get_twitter_creds()
		
		template_values = {}
		if values is not None:
			template_values.update( values )
		template_values[ "form_action" ] = get_url( self.request, "/settings" )
		template_values[ "twitter_auth" ] = get_url( self.request, "/twitter_auth" )

		if creds.screen_name is not None:
			template_values[ 'twitter_username' ] = creds.screen_name

		template_values[ 'guru_name' ] = settings.learning_guru
		template_values[ "tweet_frequency" ] = settings.tweet_frequency
		template_values[ "tweet_chance" ] = settings.tweet_chance

		if settings.learning_style == constants.learning_style_oneuser:
			template_values[ 'learnfrom_oneuser_checked' ] = "checked"
		elif settings.learning_style == constants.learning_style_followers:
			template_values[ 'learnfrom_followers_checked' ] = "checked"
		elif settings.learning_style == constants.learning_style_followed:
			template_values[ 'learnfrom_followed_checked' ] = "checked"
		elif settings.learning_style == constants.learning_style_list:
			template_values[ 'learnfrom_list_checked' ] = "checked"

		if settings.locquacity_onschedule: 
			template_values[ 'locquacity_onschedule_checked' ] = "checked"
		if settings.locquacity_reply:
			template_values[ 'locquacity_reply_checked' ] = "checked"
		if settings.locquacity_speakonnew:
			template_values[ 'locquacity_speakonnew_checked' ] = "checked"

		path = path_for_template( "settings.html" )
		self.response.out.write( template.render( path, template_values ) )


	# straight page load, dish out template
	def get(self):
		self.render_template() 
	
	# form data has been posted, process it
	def post(self):
		settings = config.get_settings()
		settings.learning_style = self.request.get( 'learnfrom' )
		settings.learning_guru = self.request.get( 'guru_name' )
		settings.locquacity_onschedule = self.request.get( 'locquacity_onschedule' ) == "true"
		settings.locquacity_reply = self.request.get( 'locquacity_reply' ) == "true"
		settings.locquacity_speakonnew = self.request.get( 'locquacity_speakonnew' ) == "true"
		tweet_frequency = self.request.get( 'tweet_frequency' )
		if tweet_frequency is not None and len(tweet_frequency) > 0:
			settings.tweet_frequency = float( tweet_frequency )
		tweet_chance = self.request.get( 'tweet_chance' )
		if tweet_chance is not None and len(tweet_chance) > 0:
			settings.tweet_chance = float( tweet_chance )
		self.render_template( { "saved" : True }, settings )
		settings.put()


def main():
    application = webapp.WSGIApplication( [ ('/', MainHandler),
    										('/twitter_auth', AuthHandler),
    										('/oauth_return', AuthReturnHandler),
    										('/session_cleanup', SessionCleanupHandler),
    										('/settings', SettingsHandler),
    										('/run', RunHandler) ],
                                         debug=True ) 
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
