from google.appengine.ext import db
import twitter

class MMState( db.Model ):
	creds = db.ReferenceProperty( twitter.MMTwitterCreds )
	last_run = db.DateTimeProperty()

def get_state( creds ):
	state = MMState.all()
	state.filter( "creds = ", creds )
	state = state.get()
	if state is None:
		state = MMState( creds=creds )
	return state