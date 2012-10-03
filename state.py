# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from google.appengine.ext import db
import twitter

class MMState( db.Model ):
	creds = db.ReferenceProperty( twitter.MMTwitterCreds )
	last_replied_id = db.StringProperty()
	last_run = db.DateTimeProperty()
	
def get_state( creds ):
	q = MMState.all()
	q.filter( "creds = ", creds )
	bot_state = q.get()
	if bot_state is None:
		bot_state = MMState( creds=creds )
	return bot_state