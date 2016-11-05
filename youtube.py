#!/usr/bin/env python3
#! python3

import re
import time
import asyncio
from constants import *
from youtube_dl import YoutubeDL
from apricot.utils import parse_qs, urlparse

class YoutubeExtractor(object):

	def __init__(self, session):
		self.session = session
		self.ytdl	= YoutubeDL(YTDL_OPTS)

	def getVideoID(self, url):
		""" Extract the video id from a url, return video id as str. """
		idregx = re.compile(r'[\w-]{11}$')
		url = str(url)

		if idregx.match(url):
			return url # ID of video

		# extract info
		if '://' not in url:
			url = '//' + url
		parsedurl = urlparse(url)
		if parsedurl.netloc in ('youtube.com', 'www.youtube.com'):
			query = parse_qs(parsedurl.query)
			if 'v' in query and idregx.match(query['v'][0]):
				return query['v'][0]
		elif parsedurl.netloc in ('youtu.be', 'www.youtu.be'):
			vidid = parsedurl.path.split('/')[-1] if parsedurl.path else ''
			if idregx.match(vidid):
				return vidid

		# raise error if not found
		err = "Need 11 character video id or the URL of the video. Got %s"
		raise ValueError(err % url)

	def timeToSeconds(self, t):
		""" Convert time_dict to seconds """
		return t['seconds'] + (t['minutes'] * 60) + (t['hours'] * 60 * 60)

	def timeToText(self, _time):
		""" Convert time_dict to formatted text """
		secs   = self.timeToSeconds(_time)
		FORMAT = '%M:%S'
		if _time['hours'] > 0: FORMAT = '%H:' + FORMAT
		return time.strftime(FORMAT, time.gmtime(secs))

	async def getShorten(self, url):
		""" Use Google URL Shortener to shorten url """
		query   = GOOGLE_SHORT.format(key=GOOGLE_API_KEY)
		headers = {'content-type': 'application/json'}
		payload = {"longUrl": url}

		resp    = await self.session.post(query, headers=headers, json=payload)
		data    = await resp.json()
		return data['id']

	async def getThumbnail(self, url):
		""" Get the thumbnail url of a video """
		url   = self.getVideoID(url)
		thumb = MAX_THUMBNAIL.format(id=url)

		# see if maxres thumbnail is valid
		resp  = await self.session.head(thumb)

		# if not, fall back to default hq thumbnail
		if str(resp.status).startswith('4'):
			thumb = MIN_THUMBNAIL.format(id=url)

		return thumb

	async def getTitle(self, url):
		""" Get the title of a youtube url """
		link_copy   = str(YOUTUBE_LINK)
		oembed_copy = str(YOUTUBE_OEMBED)
		url  = self.getVideoID(url)
		url  = link_copy.format(id=url)
		url  = oembed_copy.format(url=url)

		resp = await self.session.get(url)
		data = await resp.json()

		return data['title']

	async def getAudioStream(self, url, future=None):
		""" Get the M4A audio stream url of a video """
		url  = self.getVideoID(url)
		info = self.ytdl.extract_info(url, download=False)

		# get audio url
		audio_info = [
			f for f in info['formats']
			if 'audio' in f['format'].lower()
		]
		audio_info = audio_info[0] # get first link

		# set future if any and return result
		if future is not None:
			try: future.set_result(audio_info['url'])
			except: pass
		return audio_info['url']

	async def getVideoTime(self, url):
		""" Get video duration in {"hours:int", "minutes":int, "seconds":int, "stream":bool} """
		gdata_copy = str(YOUTUBE_GDATA)
		url = self.getVideoID(url)
		url = gdata_copy.format(id=url, key=GOOGLE_API_KEY)

		# extract duration and create time_dict
		resp = await self.session.get(url)
		info = await resp.json()
		info = info['items'][0]['contentDetails']
		duration = str(info['duration'])
		duration = duration[2:].lower() # remove "PT"
		TIME = {'hours':0,'minutes':0,'seconds':0}

		# populate time_dict with values
		for unit in TIME:
			if unit[0] in duration:
				valid = duration.split(unit[0])[0]
				valid = re.sub('\D', '', valid)
				TIME[unit] = int(valid[-2:])
		if max([TIME[t] for t in TIME]) < 1:
			TIME['stream'] = True
		else:
			TIME['stream'] = False

		# return time_dict
		return TIME

	async def getSearchResults(self, search, results=1):
		""" return array of {'id':str, 'title':str} from youtube search """
		params = {
			"key": GOOGLE_API_KEY,
			"q": search,
			"maxResults": str(results),
			"part": "snippet"
		}

		# fetch json info
		resp = await self.session.get(YOUTUBE_SEARCH, params=params)
		data = await resp.json()

		# get results
		_results_ = []
		_found_   = 0
		for item in data['items']:
			video_id    = item['id']['videoId']
			video_title = item['snippet']['title']
			info = {'id': video_id, 'title': video_title}
			_found_ += 1
			if _found_ <= results:
				_results_.append(info)
			if _found_ == results:
				break

		return _results_

	async def getInfo(self, url, search=False):
		""" Get all info of video from id """

		# get first url from search if enabled
		if search:
			info = await self.getSearchResults(url, results=1)
			url = info[0]['id']
		url   = self.getVideoID(url)
		
		# spawn audio fetcher in a non blocking task
		# so that other operations can finish first
		def on_audio_complete(task):
			task.event.set()
		future     = asyncio.Future()
		audio_coro = lambda: self.getAudioStream(url, future)
		task       = self.session.loop.create_task(audio_coro())
		task.event = asyncio.Event()
		task.add_done_callback(on_audio_complete)

		# get info
		_thumb = await self.getThumbnail(url)
		_title = await self.getTitle(url)
		_time  = await self.getVideoTime(url)

		# wait for audio fetching to complete
		# and get result
		await task.event.wait()
		_audio = future.result()

		# create dict
		info = {}
		info['thumbnail'] = _thumb
		info['title']     = _title
		info['audio']     = _audio
		info['time']      = _time

		# return final built info
		return info
