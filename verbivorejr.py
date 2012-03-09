from google.appengine.ext import db
from google.appengine.api import memcache
import re
import logging
import datetime

class VBWord( db.Model ):
	word				= db.StringProperty( required=True )
	frequency			= db.IntegerProperty( required=True, default=0 )

class VBWordForwardLink( db.Model ):
	root_word			= db.ReferenceProperty( VBWord, required=True, collection_name="root_reference_set" )
	next_word		 	= db.ReferenceProperty( VBWord, required=True, collection_name="following_word_set" )
	frequency			= db.IntegerProperty( required=True, default=0 )

def tokenise( text ):
		#tokens = nltk.word_tokenize( text )
		tokens = re.findall(r"[\w@#']+|[.,!?;]", text )
		return tokens

def vbword_for_word( word ):
	db_word = memcache.get( word )
	if db_word is None:
		db_word = VBWord.all()
		db_word.filter( "word = ", word )
		db_word = db_word.get()
		if db_word is None:
			db_word = VBWord( word=word )
			db_word.put()
		memcache.set( word, db_word, 0 )
	return db_word

class VerbivoreWorker:
	
	def __init__( self ):
		self.words = {}
		self.forward_links = {}

	def digest( self, text, deadline ):

		# logging.debug( "VerbivoreWorker.digest()" )
		then = datetime.datetime.now()

		tokens = tokenise( text )
		now = datetime.datetime.now()
		elapsed =  now - then
		# logging.debug( "-> got %d tokens in %d seconds" % ( len(tokens), elapsed.total_seconds() ) )

		last_token = None
		for token in tokens:
			
			if( datetime.datetime.now() >= deadline ):
				break

			if last_token is not None:
				
				# get link frequency between this and last token
				token_links = None
				if last_token in self.forward_links:
					last_token_links = self.forward_links[ last_token ]
				else:
					last_token_links = {}
				
				# increment count
				count = 0
				if token in last_token_links:
					count = last_token_links[ token ]
				count += 1

				# store link
				last_token_links[ token ] = count
				self.forward_links[ last_token ]  = last_token_links

			# increment frequency for this word
			count = 0
			if token in self.words:
				count = self.words[ token ]
			count += 1
			self.words[ token ] = count

			last_token = token

	def put( self, deadline ):

		logging.debug( "VerbivoreWorker.put()" )
		logging.debug( "-> %d words" % len(self.words) )	

		for word in self.words:
			if( datetime.datetime.now() >= deadline ):
				break
			vb_word = vbword_for_word( word )
			vb_word.frequency = self.words[ word ]
			vb_word.put()

			if word in self.forward_links:
				forward_links = self.forward_links[ word ]
				for to_word in forward_links:
					if( datetime.datetime.now() >= deadline ):
						break
					db_link = VBWordForwardLink.all()
					vb_to_word = vbword_for_word( to_word )
					db_link.filter( "root_word = ", vb_word )
					db_link.filter( "next_word = ", vb_to_word )
					db_link = db_link.get()
					if db_link is None:
						db_link = VBWordForwardLink( root_word=vb_word, next_word=vb_to_word )
					db_link.count = forward_links[ to_word ]
					db_link.put()


