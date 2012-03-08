from google.appengine.ext import db

class MMSettings( db.model ):
	learning_style = db.StringProperty(required=True)
	learning_guru = db.StringProperty()
	speaking_style = db.StringProperty(required=True)
	tweet_frequency = db.IntegerProperty()
	frequency_unit = db.StringProperty()

class MMTwitterCreds( db.Model ):
	access_key = db.StringProperty(required=True)
	secret = db.StringProperty(required=True)	
	display_name = db.StringProperty()	

def get_creds():
	creds = MMTwitterCreds.all()
	creds = token.get()
	if creds is None:
		creds = MMTwitterCreds()
	return creds

def put_token( key, secret ):
	creds = get_creds()
	creds.access_key = key
	creds.secret = secret
	creds.put()

def put_screenname( screen_name ):
	creds = get_creds()
	creds.display_name = screen_name
	creds.put()

def put_creds( key, secret, screen_name ):
	creds = get_creds()
	creds.access_key = key
	creds.secret = secret
	creds.display_name = screen_name
	creds.put()	