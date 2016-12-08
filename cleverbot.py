#!/usr/bin/env python3
#! python3

import hashlib
import collections
from datetime import datetime, timedelta
from apricot.utils import urlencode, generateID, json

SIMPLY_CLEVER = False
SESSION_EXPIRE_MIN = 30
CLEVER_DICT = collections.OrderedDict(
	(
		# must be the first pairs
		('stimulus', ''),
		('cb_settings_language', ''),
		('cb_settings_scripting', 'no'),
		('islearning', 1),  # Never modified
		('icognoid', 'wsf'),  # Never modified
		('icognocheck', ''),

		('start', 'y'),  # Never modified
		('sessionid', ''),
		('vText8', ''),
		('vText7', ''),
		('vText6', ''),
		('vText5', ''),
		('vText4', ''),
		('vText3', ''),
		('vText2', ''),
		('fno', 0),  # Never modified
		('prevref', ''),
		('emotionaloutput', ''),  # Never modified
		('emotionalhistory', ''),  # Never modified
		('asbotname', ''),  # Never modified
		('ttsvoice', ''),  # Never modified
		('typing', ''),  # Never modified
		('lineref', ''),
		('sub', 'Say'),  # Never modified
		('cleanslate', False),  # Never modified
	)
)


class CleverbotAPIError(Exception):
	"""Cleverbot returned an error (it probably recognized us as a bot)"""

class Cleverbot(object):

	HOST = "www.cleverbot.com"
	PROTOCOL = "http://"
	RESOURCE = "/webservicemin?uc=165&"
	API_URL = PROTOCOL + HOST + RESOURCE

	headers = {
		'User-Agent': 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.0)',
		'Accept': 'text/html,application/xhtml+xml,'
				  'application/xml;q=0.9,*/*;q=0.8',
		'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
		'Accept-Language': 'en-us,en;q=0.8,en-us;q=0.5,en;q=0.3',
		'Cache-Control': 'no-cache',
		'Host': HOST,
		'Referer': PROTOCOL + HOST + '/',
		'Pragma': 'no-cache'
	}

	def __init__(self, session):
		self.session = session
		self.sessions = {}

		# save cookies
		self.hasCookies = False

	def manage_sessions(self, session_id):
		""" Manage cleverbot sessions to save memory """
		now_date	 = datetime.now()
		expr_date	 = now_date + timedelta(minutes=SESSION_EXPIRE_MIN)

		# create a new session if none
		if session_id not in self.sessions:
			entry = {}
			entry['expires']		  = expr_date
			entry['conversation']	  = []
			entry['data']			  = CLEVER_DICT.copy()
			self.sessions[session_id] = entry

		# if exists, update expire time
		else:
			self.sessions[session_id]['expires'] = expr_date

		# purge any sessions that have expired
		for sess in self.sessions:
			info = self.sessions[sess]
			if info['expires'] < now_date:
				del self.sessions[sess]

	async def ask(self, question, session_id=None):
		"""Ask a question (make sure using id)
	
		each conversation has a session id.
		session ids as well as conversations -
		expires after a certain time period

		"""

		# make sure to save cookies
		if not self.hasCookies:
			resp = await self.session.get(self.PROTOCOL + self.HOST)
			self.hasCookies = True

		# get session id
		session_id = session_id if session_id is not None else generateID().upper()
		self.manage_sessions(session_id)
		s_id = session_id

		# set the current question
		self.sessions[s_id]['data']['stimulus'] = question

		# Connect to Cleverbot's API and remember the response
		resp_text = await self._send(s_id)

		# Add the current question to the conversation log
		self.sessions[s_id]['conversation'].append(question)

		# parse the info
		parsed = await self._parse(resp_text, s_id)

		# Set data as appropriate
		if self.sessions[s_id]['data']['sessionid'] != '':
			self.sessions[s_id]['data']['sessionid'] = parsed['conversation_id']

		# Add Cleverbot's reply to the conversation log
		self.sessions[s_id]['conversation'].append(parsed['answer'])

		# return answer & session id
		answer = parsed['answer'].encode('latin-1').decode('utf-8')
		return answer, s_id

	async def _send(self, s_id):
		"""POST the user's question and all required information to the
		Cleverbot API

		Cleverbot tries to prevent unauthorized access to its API by
		obfuscating how it generates the 'icognocheck' token. The token is
		currently the md5 checksum of the 10th through 36th characters of the
		encoded data. This may change in the future.

		TODO: Order is not guaranteed when urlencoding dicts. This hasn't been
		a problem yet, but we should look into ordered dicts or tuples instead.
		"""

		# Set data as appropriate
		if self.sessions[s_id]['conversation']:
			linecount = 1
			for line in reversed(self.sessions[s_id]['conversation']):
				linecount += 1
				self.sessions[s_id]['data']['vText' + str(linecount)] = line
				if linecount == 8:
					break

		# Generate the token
		enc_data = urlencode(self.sessions[s_id]['data'])
		digest_txt = enc_data[9:35]
		token = hashlib.md5(digest_txt.encode('utf-8')).hexdigest()
		self.sessions[s_id]['data']['icognocheck'] = token
		enc_data = urlencode(self.sessions[s_id]['data'])

		# POST the data to Cleverbot's API and return
		info = [self.API_URL, enc_data.encode('utf-8'), self.headers]
		resp = await self.session.post(info[0], data=info[1], headers=info[2])
		return await resp.text()


	async def _parse(self, resp_text, s_id):
		""" Parse the cleverbot response """

		parsed = [
			item.split('\r') for item in resp_text.split('\r\r\r\r\r\r')[:-1]
			]

		if parsed[0][1] == 'DENIED':
			raise CleverbotAPIError()

		parsed_dict = {
			'answer': parsed[0][0],
			'conversation_id': parsed[0][1],
		}

		try:
			parsed_dict['unknown'] = parsed[1][-1]
		except IndexError:
			parsed_dict['unknown'] = None
		return parsed_dict
