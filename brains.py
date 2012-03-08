import datastore
import constants
import twitter
import verbivorejr
import datetime
import config

# don't take any longer than this to process.
TIME_LIMIT = datetime.timedelta( minutes=5 )

def digest_user( api, vb, screen_name, then ):
	user = twitter.get_user( screen_name )
	statuses = api.user_timeline( screen_name=screen_name, since_id=user.last_id )
	last_id = None
	for status in reversed(statuses): # reversed so we start at the oldest, in case we have to abort
		vb.digest( status.text )
		last_id = status.id_str
		elapsed = datetime.datetime.now() - then
		if elapsed >= TIME_LIMIT:
			break
	user.last_id = last_id
	user.put()

def run():

	then = datetime.datetime.now()
	settings = config.get_settings()
	learning_style = settings.learning_style
	api = twitter.get_api()
	vb = verbivorejr.VerbivoreWorker()
	
	if learning_style == constants.learning_style_oneuser:
		# learn from one user
		guru_name = settings.learning_guru
		digest_user( api, vb, guru_name, then )
			
	vb.put()



		