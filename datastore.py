from google.appengine.ext import db

class TWAccessToken( db.Model ):
	access_key = db.StringProperty(required=True)
	secret = db.StringProperty(required=True)

def put_token( key, secret ):
	token = TWAccessToken.all()
	token = token.get()
	if token is None:
		token = TWAccessToken( access_key=key, secret=secret )
	else:
		token.access_key = key
		token.secret = secret
	token.put()