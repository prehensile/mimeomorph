from google.appengine.ext import db
from google.appengine.api import memcache
import re
import logging
import datetime
import random

class VBWord( db.Model ):
	word				= db.StringProperty( required=True )
	lc_word				= db.StringProperty( required=True )
	frequency			= db.IntegerProperty( required=True, default=0 )

class VBWordForwardLink( db.Model ):
	root_word			= db.ReferenceProperty( VBWord, required=True, collection_name="root_reference_set" )
	next_word		 	= db.ReferenceProperty( VBWord, required=True, collection_name="following_word_set" )
	frequency			= db.IntegerProperty( required=True, default=0 )

def tokenise( text ):
	#tokens = nltk.word_tokenize( text )
	tokens = re.findall(r"http://[^\s]+|[[\w@#&']+|[.,!?;]]", text )
	return tokens

def vbword_for_word( word ):
	lc_word = word.lower()
	db_word = memcache.get( lc_word )
	if db_word is None:
		db_word = VBWord.all()
		db_word.filter( "lc_word = ", lc_word )
		db_word = db_word.get()
		if db_word is None:
			db_word = VBWord( word=word, lc_word=lc_word )
			db_word.put()
		db_word.word = word
		memcache.set( lc_word, db_word, 0 )
	return db_word

def word_is_special( cw ):
	return cw[:1] == "@" or cw[:1] == "#" or cw[:7] == "http://"

class VerbivoreWorker:
	
	def __init__( self ):
		self.words = {}
		self.forward_links = {}

	def digest( self, text, deadline ):

		then = datetime.datetime.now()

		tokens = tokenise( text )
		now = datetime.datetime.now()
		elapsed =  now - then
		
		last_token = "." # assume we can start a new sentence with the first token
		tokens.append( last_token ) # ... and the last token ends a sentence

		for token in tokens:
			
			if( datetime.datetime.now() >= deadline ):
				break

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
					db_link.frequency = forward_links[ to_word ]
					db_link.put()

def ucfirst( string ):
	return string[:1].upper() + string[1:]

class VerbivoreQueen:
	
	def candidates_for_dbword( self, db_word ):
		q = VBWordForwardLink.all()
		q.filter( "root_word = ", db_word )
		q.order( "-frequency" )
		return q.fetch( 1000 )

	def secrete_from_dbword( self, db_word, length, deadline, include_dbword=False ):
		out = None
		if db_word is not None:
			done = False
			if include_dbword:
				out = db_word.word
			else:
				out = ""
			while not done:
				next_word = None
				candidates = self.candidates_for_dbword( db_word )
				if candidates is not None and len( candidates ) > 0:
					random.shuffle( candidates ) 
					for link_candidate in candidates:
						candidate_word = link_candidate.next_word
						cw = candidate_word.word
						if word_is_special( cw ):
							pass
						else:
							next_word = candidate_word
							break

				if next_word is not None:
					word = next_word.word
					db_word = next_word
				else:
					db_word = vbword_for_word( "." )
					word = "."

				if out[-1:] == ".":
					word = ucfirst( word )
				#else:
				#	word = word.lower()

				# append word to outstring
				if( len(out) == 0 ):
					out = ucfirst( word )
				elif re.match( """[\w@#&']+""", word ):
					out = "%s %s" % ( out, word )
				else:
					out = "%s%s" % ( out, word )

				if len(out) >= length:
					done = True
				if datetime.datetime.now() >= deadline:
					done = True
				if word == ".":
					done = True

			# finish with a full stop
			if out[-1:] != ".":
				out += "."

		return out

	def secrete_reply( self, text, length, deadline):

		logging.debug( "VerbivoreQueen.secrete_reply()" )

		tokens = tokenise( text )
		tokens.reverse()
		pivot_dbword = None
		for token in tokens:
			logging.debug( "-> looking for matches for token: %s" % token )
			db_word = vbword_for_word( token )
			candidates = self.candidates_for_dbword( db_word )
			if len( candidates ) > 0:
				pivot_dbword = db_word
				break

		if pivot_dbword is not None:
			logging.debug( "-> pivot_dbword is %s" % pivot_dbword.word )
			return self.secrete_from_dbword( pivot_dbword, length, deadline, include_dbword=True )
		else:
			return self.secrete( length, deadline )

	def secrete( self, length, deadline ):
		db_word = vbword_for_word( "." )
		return self.secrete_from_dbword( db_word, length, deadline )