from google.appengine.ext import db
from google.appengine.api import memcache
import re
import logging
import datetime
import random
import twitter

class VBWord( db.Model ):
	word				= db.StringProperty( required=True )
	lc_word				= db.StringProperty( required=True )
	frequency			= db.IntegerProperty( required=True, default=0 )

	def description(self):
		return( "VBWord: %s" % self.word )

class VBWordForwardLink( db.Model ):
	root_word			= db.ReferenceProperty( VBWord, required=True, collection_name="root_reference_set" )
	next_word		 	= db.ReferenceProperty( VBWord, required=True, collection_name="following_word_set" )
	frequency			= db.IntegerProperty( required=True, default=0 )

	def description(self):
		return( "VBWordForwardLink: %s -> %s" % (self.root_word.word, self.next_word.word) )

def uc_first( string ):
	return string[:1].upper() + string[1:]

def tokenise( text ):
	#tokens = nltk.word_tokenize( text )
	# regex matches: HTML entities | URLS | smileys | words | strings of punctuation
	tokens = re.findall(r"&[\S]+;|http://[^\s]+|[:;][\S]|[\w@#&']+|[.,!?;]+", text )
	return tokens

def join_sentence( arr_words ):
	str_out = None
	last_word = None
	for db_word in arr_words:
		word = db_word.word
		if last_word is not None and last_word == ".":
			word = uc_first( word )
		if str_out is None:
			str_out = word
		elif re.match( """[\w@#&']+""", word ):
			str_out = "%s %s" % ( str_out, word )
		else:
			str_out = "%s%s" % ( str_out, word )
		last_word = word
	if re.match( "\w", str_out[-1:] ):
		str_out = "%s." % str_out
	return str_out

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
	
	def __init__( self, api, settings_in ):
		self.words = {}
		self.forward_links = {}
		self.api = api
		self.deadline = None
		self.settings = settings_in

	def link_tokens( self, root_token, next_token ):
		
		# get link frequency between this and last token
		token_links = None
		if root_token in self.forward_links:
			root_token_links = self.forward_links[ root_token ]
		else:
			root_token_links = {}
		
		# increment count
		count = 0
		if next_token in root_token_links:
			count = root_token_links[ next_token ]
		count += 1

		# store link
		root_token_links[ next_token ] = count
		self.forward_links[ root_token ]  = root_token_links


	def digest( self, text ):

		# then = datetime.datetime.now()

		tokens = tokenise( text )
		# now = datetime.datetime.now()
		# elapsed =  now - then
		
		# logging.debug( "VerbivoreWorker.digest(): tokens are: %s" % tokens )

		last_token = "." # assume we can start a new sentence with the first token
		tokens.append( last_token ) # ... and the last token ends a sentence
		first_token = True

		for token in tokens:
			
			if self.deadline is not None and ( datetime.datetime.now() >= self.deadline ):
				break

			self.link_tokens( last_token, token )

			# increment frequency for this word
			count = 0
			if token in self.words:
				count = self.words[ token ]
			count += 1
			self.words[ token ] = count

			# minor hack - if we're digesting a reply, also connect this token to "."
			if last_token[:1] == "@" and first_token:
				self.link_tokens( ".", token )
			first_token = False

			last_token = token


	def digest_history( self, mm_twitteruser ):
		
		statuses_digested = 0

		max_id = mm_twitteruser.historywindow_upperidstr

		logging.debug( "VerbivoreWorker.digest_history(%s)" % mm_twitteruser.description() )
		logging.debug( "-> max id is %s" % max_id );

		if max_id is not None:

			num_tweets = 4 # softly softly catchee monkey
			statuses = mm_twitteruser.fetch_timeline( self.api, num_tweets, since_id=None, max_id=max_id )

			if len(statuses) < 1:
				# no more history to digest
				self.settings.learn_retrospectively = False
				self.settings.put()
			else:
				oldest_id = None
				oldest_date = None
				for status in statuses:
					if self.deadline is not None and ( datetime.datetime.now() >= self.deadline ):
						break
					if status.id_str != max_id: # status with max_id will already have been digested
						self.digest( status.text )
						status_date = status.created_at
						if oldest_date is None or status_date < oldest_date:
							oldest_id = status.id_str
							oldest_date = status_date
				if oldest_id is not None:
					logging.debug( "-> new oldest_id=%s" % oldest_id )
					mm_twitteruser.historywindow_upperidstr = oldest_id
					mm_twitteruser.put()

		logging.debug( "--> digested %d statuses" % statuses_digested )

		return statuses_digested

	def digest_user( self, mm_twitteruser ):
	
		last_id = mm_twitteruser.last_id
		num_statuses = 20
		if last_id is None:
			# if we haven't seen this user before, get more statuses for better input
			num_statuses = 100

		lowest_id = None
		statuses_digested = 0
		statuses = mm_twitteruser.fetch_timeline( self.api, num_statuses, since_id=last_id )

		if statuses is not None:	
			if len(statuses) > 0:
				for status in reversed(statuses): # reversed so we start at the oldest, in case we have to abort 
					if self.deadline is not None and ( datetime.datetime.now() >= self.deadline ):
						logging.debug( "VerbivoreWorker.digest_user(), hit deadline at %d statuses" % statuses_digested )
						break
					last_id = status.id_str
					if lowest_id is None or ( long(last_id) < long(lowest_id) ):
						lowest_id = last_id
					self.digest( status.text )
					statuses_digested += 1
				
				mm_twitteruser.historywindow_upperidstr = lowest_id
				mm_twitteruser.last_id = last_id
				mm_twitteruser.put()
		
		if self.settings.learn_retrospectively:
			logging.debug( "VerbivoreWorker.digest_user(), will learn retrospectively" )
			statuses_digested += self.digest_history( mm_twitteruser )

		return statuses_digested


	def digest_ids( self, tasty_ids ):
		statuses_digested = 0
		for tasty_id in tasty_ids:
			guru = twitter.get_user( id_str=tasty_id )
			statuses_digested += self.digest_user( guru )	
			if self.deadline is not None and ( datetime.datetime.now() >= self.deadline ):
				break
		return( statuses_digested )


	def put( self ):

		for word in self.words:
			if self.deadline is not None and ( datetime.datetime.now() >= self.deadline ):
				break
			vb_word = vbword_for_word( word )
			vb_word.frequency = self.words[ word ]
			vb_word.put()

			if word in self.forward_links:
				forward_links = self.forward_links[ word ]
				for to_word in forward_links:
					if( datetime.datetime.now() >= self.deadline ):
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


class VerbivoreQueen:
	
	def __init__(self):
		self.deadline = None

	def candidates_for_dbword( self, db_word, look_backwards=False ):
		q = None
		if look_backwards is True:
			q = db_word.following_word_set
		else:
			q = db_word.root_reference_set
		q.order( "-frequency" )
		return q.fetch( 1000 )

	def check_candidate_dbword( self, candidate_word, arr_out ):
		ok = False
		cw = candidate_word.word
		if len( arr_out ) < 1 and cw == ".":
			pass
		elif word_is_special( cw ):
			pass
		#elif candidate_word in arr_out:
		#	pass
		else:
			ok = True
		return ok

	def secrete_from_dbword( self, db_word, length, include_dbword=False, bidirectional=False, min_words=0 ):
		
		logging.debug( "VerbivoreQueen.secrete_from_dbword(%s,%d)" % (db_word.word, length) )

		str_out = None
		if db_word is not None:
			
			# bidirectional makes no sense if include_dbword is False
			if not include_dbword:
				bidirectional = False

			if include_dbword:
				arr_out = [ db_word ]
			else:
				arr_out = []
			finished_left = False
			finished_right = False
			done = False
			leftmost_dbword = db_word
			rightmost_dbword = db_word
			next_dbword = None
			long_enough = False
			while not done:

				long_enough = len( arr_out ) > min_words

				# extend rightwards
				next_dbword = None
				candidates = self.candidates_for_dbword( rightmost_dbword )
				if candidates is not None and len( candidates ) > 0:
					random.shuffle( candidates ) 
					for link_candidate in candidates:
						candidate_word = link_candidate.next_word
						if self.check_candidate_dbword( candidate_word, arr_out ):
							next_dbword = candidate_word
							break
				
				if next_dbword is None:
					finished_right = True
				else:
					arr_out.append( next_dbword )
					rightmost_dbword = next_dbword
					if next_dbword.word[-1] == "." and long_enough:
						finished_right = True

				if bidirectional:
					# extend leftwards
					next_dbword = None
					candidates = self.candidates_for_dbword( leftmost_dbword, look_backwards=True )
					if candidates is not None and len( candidates ) > 0:
						random.shuffle( candidates ) 
						for link_candidate in candidates:
							candidate_word = link_candidate.root_word
							if self.check_candidate_dbword( candidate_word, arr_out ):
								next_dbword = candidate_word
								break
					
					if next_dbword is None or (next_dbword.word[-1] == "." and long_enough):
						finished_left = True
					else:
						arr_out.insert( 0, next_dbword )
						leftmost_dbword = next_dbword
						
				# check doneness
				if bidirectional:
					done = finished_right and finished_left
				else: 
					done = finished_right

				if not done:
					str_out = join_sentence( arr_out )
					if len( str_out ) >= length:
						done = True

					if not done and (self.deadline is not None)  and ( datetime.datetime.now() >= self.deadline ):
						done = True
							
			# done, concatenate arr_out
			if len(arr_out) > 2:
				str_out = join_sentence( arr_out )
			else:
				str_out = None
			
		return str_out

	def secrete_reply( self, text, length ):

		logging.debug( "VerbivoreQueen.secrete_reply()" )

		tokens = tokenise( text )
		tokens.reverse()
		pivot_dbword = None
		reply = None
		for token in tokens:
			if not word_is_special( token ):
				#logging.debug( "-> looking for matches for token: %s" % token )
				db_word = vbword_for_word( token )
				#logging.debug( "-> db_word is %s" % db_word.description() )
				q = db_word.following_word_set
				q.order( "-frequency" )
				candidates = q.fetch( 10 )
				num_candidates = len( candidates )

				#logging.debug( "--> found %d candidates" %  len( candidates ) )
				for candidate in candidates:
					if word_is_special( candidate.root_word.word ):
						num_candidates = num_candidates -1 
					#logging.debug( "---> candidate: %s" % candidate.description() )

				if num_candidates > 0:
					pivot_dbword = db_word
					break

		if pivot_dbword is not None:
			logging.debug( "-> pivot_dbword is %s" % pivot_dbword.word )
			reply = self.secrete_from_dbword( pivot_dbword, length, include_dbword=True, bidirectional=True, min_words=3 )
		
		if reply is None:
			reply = self.secrete( length )
		return reply

	def secrete( self, length ):
		logging.debug( "VerbivoreQueen.secrete(%d)" % length )
		db_word = vbword_for_word( "." )
		return self.secrete_from_dbword( db_word, length )

	def secrete_greeting( self, screen_name, length ):
		greeting = None
		greeting_prefix = "@%s" % screen_name
		
		# first, try to construct a sentence starting with screen_name
		db_word = vbword_for_word( greeting_prefix )
		candidates = self.candidates_for_dbword( db_word )
		if len(candidates) > 0:
			greeting = self.secrete_from_dbword( db_word, length, include_dbword=True, bidirectional=False, min_words=3 )
		# if we fail...
		if greeting is None:
			# try starting from some genric greeting words
			generic_greetings = [ 'hello', 'hi', 'hey', 'heya', 'hola' ]
			for generic_greeting in generic_greetings:
				db_word = vbword_for_word( generic_greeting )
				candidates = self.candidates_for_dbword( db_word )
				if len(candidates) > 0:
					greeting = self.secrete_from_dbword( db_word, length, include_dbword=True, bidirectional=False, min_words=3 )
					if greeting is not None:
						break
			# if that fails, just generate anything
			greeting = self.secrete( length - len(greeting_prefix) - 1 )
			if greeting is not None:
				greeting = "%s %s" % (greeting_prefix,greeting)
		
		return greeting