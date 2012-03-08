from google.appengine.ext import db

class MMSettings( db.Model ):
	learning_style = db.StringProperty()
	learning_guru = db.StringProperty()
	locquacity = db.StringProperty()
	tweet_frequency = db.FloatProperty()
	frequency_unit = db.StringProperty()

def get_settings():
	settings = MMSettings.all()
	settings = settings.get()
	if settings is None:
		settings = MMSettings()
	return settings

CONSUMER_KEY = "replace me"
CONSUMER_SECRET = "replace me"
