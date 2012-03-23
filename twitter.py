import tweepy
import config
from google.appengine.ext import db
from google.appengine.api import users
import logging
from gaesessions import delete_expired_sessions
from gaesessions import get_current_session
from google.appengine.api import namespace_manager


class MMTwitterCreds( db.Model ):
	token_key = db.StringProperty()
	token_secret = db.StringProperty()	
	screen_name = db.StringProperty()
	owner = db.UserProperty()
	follower_ids = db.ListProperty(long)

class MMTwitterUser( db.Model ):
	screen_name = db.StringProperty()
	id_str = db.StringProperty()
	last_id = db.StringProperty()
	historywindow_upperidstr = db.StringProperty()

	def fetch_timeline( self, api, num_statuses, since_id=None, max_id=None, page=None ):
		statuses = None
		if self.id_str:
			statuses = api.user_timeline( count=num_statuses, user_id=self.id_str, since_id=since_id, include_rts=False, max_id=max_id, page=page )	
		elif self.screen_name:
			statuses = api.user_timeline( count=num_statuses, screen_name=self.screen_name, since_id=since_id, include_rts=False, max_id=max_id, page=page )	
		return statuses

	def description( self ):
		return( "<MMTwitterUser: screen_name is %s, id_str is %s>" % ( self.screen_name, self.id_str ) )

class MMTwitterList( db.Model ):
	name = db.StringProperty()
	id_str = db.StringProperty()
	creds = db.ReferenceProperty( MMTwitterCreds, collection_name="lists" )

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
	except tweepy.TweepError, err:
		logging.debug( "auth.get_access_token had an error: %s" % err )

	token_key = auth.access_token.key
	token_secret = auth.access_token.secret

	auth.set_access_token( token_key, token_secret)
	api = tweepy.API(auth)
	
	screen_name = api.me().screen_name
	creds = get_twitter_creds( screen_name=screen_name )
	creds.token_key = token_key
	creds.token_secret = token_secret
	user = users.get_current_user()
	if user is not None:
		creds.owner = user
	creds.put()

	tw_lists = api.lists()
	for tw_list in tw_lists:
		mm_list = MMTwitterList( name=tw_list.name, id_str=tw_list.id_str, creds=creds )
		mm_list.put()
	
	return api

def get_twitter_creds( screen_name ):
	ns = namespace_manager.get_namespace()
	namespace_manager.set_namespace( None )
	creds = MMTwitterCreds.all()
	creds.filter( "screen_name = ", screen_name )
	creds = creds.get()
	if creds is None:
		creds = MMTwitterCreds( screen_name=screen_name )
	namespace_manager.set_namespace( ns )
	return creds

def get_all_creds():
	ns = namespace_manager.get_namespace()
	namespace_manager.set_namespace( None )
	creds = MMTwitterCreds.all()
	namespace_manager.set_namespace( ns )
	return creds.fetch( 1000 )

def get_user( screen_name=None, id_str=None ):
	ns = namespace_manager.get_namespace()
	namespace_manager.set_namespace( None )
	user = MMTwitterUser.all()
	if screen_name:
		user.filter( "screen_name = ", screen_name )
	elif id_str:
		user.filter( "id_str = ", id_str )
	user = user.get()
	if user is None:
		user = MMTwitterUser( screen_name=screen_name, id_str=id_str )
	namespace_manager.set_namespace( ns )
	return user

def api_for_token( token_key, token_secret ):
	auth = tweepy.OAuthHandler( config.CONSUMER_KEY, config.CONSUMER_SECRET )
	auth.set_access_token( token_key, token_secret)
	api = tweepy.API(auth)
	return( api )

def get_api( creds ):
	return api_for_token( creds.token_key, creds.token_secret )