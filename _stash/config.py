from google.appengine.ext import db

class MMSettings( db.Model ):
	learning_style = db.StringProperty()
	learning_guru = db.StringProperty()
	locquacity_onschedule = db.BooleanProperty( required=True, default=False )
	locquacity_reply = db.BooleanProperty( required=True, default=False )
	locquacity_speakonnew = db.BooleanProperty( required=True, default=False )
	tweet_frequency = db.FloatProperty( required=True, default=1.0 )
	tweet_chance = db.FloatProperty( required=True, default=1.0 )

class MMState( db.Model ):
	last_run = db.DateTimeProperty()

def get_settings():
	settings = MMSettings.all()
	settings = settings.get()
	if settings is None:
		settings = MMSettings()
	return settings

def get_state():
	state = MMState.all()
	state = state.get()
	if state is None:
		state = MMState()
	return state

CONSUMER_KEY = "ZLuhs5eQIsuyTyE3mJOg"
CONSUMER_SECRET = "2UOQ2Xnpd42CX7S5oRtkE8FMT1tkqZy3fw7uIrQfQ"
