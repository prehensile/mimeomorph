from google.appengine.ext import db
import twitter

class MMSettings( db.Model ):
	creds = db.ReferenceProperty( twitter.MMTwitterCreds )
	learning_style = db.StringProperty()
	learning_guru = db.StringProperty()
	locquacity_onschedule = db.BooleanProperty( required=True, default=False )
	locquacity_reply = db.BooleanProperty( required=True, default=False )
	locquacity_speakonnew = db.BooleanProperty( required=True, default=False )
	tweet_frequency = db.FloatProperty( required=True, default=1.0 )
	tweet_chance = db.FloatProperty( required=True, default=1.0 )

def get_settings( creds ):
	settings = MMSettings.all()
	settings.filter( "creds = ", creds )
	settings = settings.get()
	if settings is None:
		settings = MMSettings()
	return settings