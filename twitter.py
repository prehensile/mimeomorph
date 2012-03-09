import tweepy
import config
from google.appengine.ext import db
import logging
from gaesessions import delete_expired_sessions
from gaesessions import get_current_session

class MMTwitterCreds( db.Model ):
	token_key = db.StringProperty()
	token_secret = db.StringProperty()	
	screen_name = db.StringProperty()

class MMTwitterUser( db.Model ):
	screen_name = db.StringProperty(required=True)
	last_id = db.StringProperty()

REQUEST_TOKEN_KEY = "request_token"

def get_authurl( callback_url ):
	# cooked up from http://packages.python.org/tweepy/html/auth_tutorial.html
	# and https://github.com/dound/gae-sessions/blob/master/README.markdown
	auth = tweepy.OAuthHandler( config.CONSUMER_KEY, config.CONSUMER_SECRET, callback_url )
	redirect_url = None
	tw_error = None
	redirect_url = auth.get_authorization_url()
	session = get_current_session()
	session[ REQUEST_TOKEN_KEY ] = (auth.request_token.key, auth.request_token.secret)
	return redirect_url

def consume_verifier( verifier ):
	# cooked up from http://packages.python.org/tweepy/html/auth_tutorial.html
	# and https://github.com/dound/gae-sessions/blob/master/README.markdown
	session = get_current_session()
	if REQUEST_TOKEN_KEY not in session:
		raise Exception( "No request token for session." )

	token = session[ REQUEST_TOKEN_KEY ]
	del session[ REQUEST_TOKEN_KEY ]

	logging.debug( "twitter.consume_verifier: token is (%s,%s) " % token )
	auth = tweepy.OAuthHandler( config.CONSUMER_KEY, config.CONSUMER_SECRET )
	auth.set_request_token( token[0], token[1] )
	
	try:
		auth.get_access_token( verifier )
		logging.debug( "auth.get_access_token had no error." )
	except tweepy.TweepError as err:
		logging.debug( "auth.get_access_token had an error: %s" % err )

	token_key = auth.access_token.key
	token_secret = auth.access_token.secret

	auth.set_access_token( token_key, token_secret)
	api = tweepy.API(auth)
	screen_name = api.me().name

	put_twitter_creds( token_key, token_secret, screen_name )
	return api

def get_twitter_creds( token_key=None, token_secret=None ):
	creds = MMTwitterCreds.all()
	creds = creds.get()
	if creds is None:
		creds = MMTwitterCreds()
	return creds

def put_twitter_creds( key, secret, screen_name ):
	creds = get_twitter_creds()
	creds.token_key = key
	creds.token_secret = secret
	creds.screen_name = screen_name
	creds.put()	

def get_user( screen_name ):
	user = MMTwitterUser.all()
	user = user.get()
	if user is None:
		user = MMTwitterUser( screen_name=screen_name )
	return user

def api_for_token( token_key, token_secret ):
	auth = tweepy.OAuthHandler( config.CONSUMER_KEY, config.CONSUMER_SECRET )
	auth.set_access_token( token_key, token_secret)
	api = tweepy.API(auth)
	return( api )

def get_api():
	creds = get_twitter_creds()
	if creds is not None:
		return api_for_token( creds.token_key, creds.token_secret )
	else:
		raise Exception( "No stored Twitter credentials." )