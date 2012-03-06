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
import logging
import config
from gaesessions import delete_expired_sessions
from gaesessions import get_current_session
import datastore

class MainHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write('Hello world!')

REQUEST_TOKEN_KEY = "request_token"

class AuthHandler( webapp.RequestHandler ):
	
	def get(self):
		
		callback_url = self.request.url
		callback_url = callback_url[:callback_url.rfind("/")]
		callback_url += "/oauth_return"
		logging.debug( callback_url )

		# cooked up from http://packages.python.org/tweepy/html/auth_tutorial.html
		# and https://github.com/dound/gae-sessions/blob/master/README.markdown

		auth = tweepy.OAuthHandler( config.consumer_key, config.consumer_secret, callback_url )
		redirect_url = None
		tw_error = None
		try:
			redirect_url = auth.get_authorization_url()
		except tweepy.TweepError as err:
			tw_error = err
		
		session = get_current_session()
		session[ REQUEST_TOKEN_KEY ] = (auth.request_token.key, auth.request_token.secret)

		if redirect_url:
			self.response.out.write( "Redirecting to twitter for authorisation..." )
			self.redirect( redirect_url )
		else:
			self.response.out.write( "Error! Failed to get request token." )	


class AuthReturnHandler( webapp.RequestHandler ):

	def get(self):

		self.response.out.write( "Returned from auth!<br/>" )

		# cooked up from http://packages.python.org/tweepy/html/auth_tutorial.html
		# and https://github.com/dound/gae-sessions/blob/master/README.markdown
		verifier = self.request.get('oauth_verifier')
		auth = tweepy.OAuthHandler( config.consumer_key, config.consumer_secret )
		session = get_current_session()
		token = session[ REQUEST_TOKEN_KEY ]
		del session[ REQUEST_TOKEN_KEY ]
		auth.set_request_token(token[0], token[1])

		tw_error = None
		try:
			auth.get_access_token(verifier)
		except tweepy.TweepError as err:
			tw_error = err

		if tw_error is None:
			datastore.put_token( auth.access_token.key, auth.access_token.secret )
			api = tweepy.API(auth)
			self.response.out.write( "Auth complete for %s" % api.me().name )
		else:
			self.response.out.write( "Error! Failed to get access token." )

		


class SessionCleanupHandler():
	
	def get(self):
		while not delete_expired_sessions():
			pass
		message = "Cleaned up expired sessions."
		logging.log( 1, message )
		self.response.out.write( message )


def main():
    application = webapp.WSGIApplication( [ ('/', MainHandler),
    										('/twitter_auth', AuthHandler),
    										('/oauth_return', AuthReturnHandler),
    										('/session_cleanup', SessionCleanupHandler) ],
                                         debug=True ) 
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
