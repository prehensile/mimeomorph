from google.appengine.ext import db
import twitter

class MMState( db.Model ):
	creds = db.ReferenceProperty( twitter.MMTwitterCreds )
	last_run = db.DateTimeProperty()

def get_state( creds ):
	q = MMState.all()
	q.filter( "creds = ", creds )
	bot_state = q.get()
	if bot_state is None:
		bot_state = MMState( creds=creds )
	return bot_state