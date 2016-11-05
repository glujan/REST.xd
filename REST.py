#!/usr/bin/env python3
#! python3

import socket
import asyncio
from constants import *
from cleverbot import Cleverbot
from youtube import YoutubeExtractor
from urbandict import UrbanDictionary
from apricot.server import ApricotServer
from apricot.client import ApricotSession
from apricot.client import ApricotResponse
from apricot.utils import json, unquote, __version__

class REST_Api(object):

	def __init__(self):
		# create apricot objects
		self.server  = ApricotServer(port=1234)
		self.session = ApricotSession()

		# display info
		self.session.loop.create_task(self.getIpInfo())
		self.info = {'version': str(__version__), 'name': 'REST Api via apricot'}

		# create api objects
		self.yt        = YoutubeExtractor(self.session)
		self.urbandict = UrbanDictionary(self.session)
		self.cbot      = Cleverbot(self.session)

		# route http paths to functions
		self.add_route('GET', "/youtube", self.youtube)
		self.add_route('GET', "/define", self.define)
		self.add_route('GET', "/hastebin", self.hastebin)
		self.add_route('GET', "/cleverbot", self.cleverbot)
		self.add_route('GET', "/shorten", self.shorten)
		self.add_route('GET', "/insult", self.insult)
		self.add_route('GET', "/osu_user", self.osu_user)
		self.add_route('GET', "/", self.index)

	### Routed Paths ###

	async def index(self, request):
		""" display basic info of server """
		return self.RESTify(self.info)

	async def youtube(self, request):
		""" handle youtube requests 

		:param url: the url of the video (either this or search)
		:param search: query to lookup and get first search result

		"""
		params = request.query_dict
		search = False
		query  = ''


		if 'url' not in params and 'search' not in params:
			return self._404()
		if 'url' in params:
			query  = unquote(params['url'])
		if 'search' in params:
			query  = unquote(params['search'])
			search = True

		info = await self.yt.getInfo(query, search)
		return self.RESTify(info)


	async def define(self, request):
		""" handle urbandict definition """
		params = request.query_dict
		if 'term' not in params: return self._404()
		term       = unquote(params['term'])
		definition = await self.urbandict.define(term)
		info = {'term': term, 'definition': definition}
		return self.RESTify(info)

	async def hastebin(self, request):
		""" handle hastebin post """
		params = request.query_dict
		if 'data' not in params: return self._404()
		data   = unquote(params['data'])
		data   = await self.urbandict.hastebin_post(data)
		return self.RESTify(data)

	async def cleverbot(self, request):
		""" handle cleverbot ask """
		params = request.query_dict
		if 'ask' not in params: return self._404()

		question = params['ask']
		s_id = params['session'] if 'session' in params else None
		response, session = await self.cbot.ask(question, s_id)
		info = {"response": response, "session": session}

		return self.RESTify(info)

	async def insult(self, request):
		""" generate an insult """
		insult = await self.urbandict.gen_insult()
		insult = {'insult': insult}
		return self.RESTify(insult)

	async def shorten(self, request):
		""" goo.gl shorten url """
		params = request.query_dict
		if 'url' not in params: return self._404()
		try:
			url   = unquote(params['url'])
			short = await self.youtube.getShorten(url)
			info  = {"original":url, "id":short}
			return self.RESTify(info)
		except:
			return self._404()

	async def osu_user(self, request):
		""" handle osu under info """
		params = request.query_dict
		if 'u' not in params: return self._404()
		user = unquote(params['u'])
		try:
			resp = await self.session.get(OSU_USER, params={'k':OSU_KEY,'u':user})
			data = await resp.json()
			return self.RESTify(data)
		except Exception as e:
			print("Osu error: " + str(e))
		return self._404()


	#### Server Functions ####


	def _404(self):
		""" Return a default 404 response """
		return ApricotResponse(status=404, body="Error")

	async def getIpInfo(self):
		""" Get current ipv4 address & public address"""
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect(('8.8.8.8', 53)) # google dns servers
		lan = s.getsockname()[0]
		s.close()

		resp = await self.session.get("http://ip.42.pl/raw")
		pub  = await resp.text()

		print("LAN IP: {0}".format(lan))
		print("Public IP: {0}".format(pub))

	def RESTify(self, data):
		""" Convert Data to ApricotResponse """
		if not isinstance(data, dict):
			data = {}
		data    = json.dumps(data)
		data    = data.encode('utf-8')
		ctype   = 'application/json'
		charset = 'utf-8'
		return ApricotResponse(status=200, body=data, content_type=ctype, charset=charset)

	def add_route(self, method, path, route):
		""" link an http request to a route """
		if method.lower() == 'GET':
			add = self.server.router.add_get
		elif method.lower() == 'POST':
			add = self.server.router.add_post
		elif method.lower() == 'HEAD':
			add = self.server.router.add_head
		else:
			add = None
		if add is not None:
			add(path, route)
		else:
			self.server.router.add_route(method, path, route)




#### Run the server ####
if __name__ == '__main__':
	rest = REST_Api()
	rest.server.start()
	try:
		rest.server.wait_until_stopped()
	except KeyboardInterrupt:
		pass
	print("Quitting...")
	rest.server.stop()
