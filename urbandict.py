#!/usr/bin/env python3
#! python3

from constants import INSULT_LINK, URBAN_DICT
from constants import HASTEBIN, HASTEBIN_POST
import lxml.html as lxml

class UrbanDictionary(object):

	def __init__(self, session):
		self.session = session

	async def define(self, query):
		""" Urban dictionary define """
		params = {"term":query}
		resp = await self.session.get(URBAN_DICT, params=params)
		data = await resp.json()
		return data['list'][0]['definition']

	async def gen_insult(self):
		""" Generate an insult """
		resp   = await self.session.get(INSULT_LINK)
		text   = await resp.text()
		html   = lxml.fromstring(text)
		div    = html.xpath("//div[@class='wrap']")
		insult = div[0].text_content()[2:]
		return insult

	async def hastebin_post(self, data):
		""" Post data to hastbin and get url """
		if not isinstance(data, bytes):
			data = str(data).encode('utf-8')
		resp = await self.session.post(HASTEBIN_POST, data=data)
		info = await resp.json()
		return HASTEBIN + "/" + info['key']

