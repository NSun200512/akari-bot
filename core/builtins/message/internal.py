﻿import base64
import re
import uuid
from datetime import datetime
from os.path import abspath
from typing import List
from urllib import parse

import aiohttp
import filetype
from PIL import Image as PImage
from tenacity import retry, stop_after_attempt

from config import Config
from core.builtins.utils import shuffle_joke
from core.types.message.internal import (Plain as PlainT, Image as ImageT, Voice as VoiceT, Embed as EmbedT,
                                         EmbedField as EmbedFieldT, Url as UrlT, ErrorMessage as EMsg)
from core.types.message import MessageSession
from core.utils.i18n import Locale


class Plain(PlainT):
    def __init__(self, text, *texts, disable_joke: bool = False):
        self.text = str(text)
        for t in texts:
            self.text += str(t)
        if not disable_joke:
            self.text = shuffle_joke(self.text)

    def __str__(self):
        return self.text

    def __repr__(self):
        return f'Plain(text="{self.text}")'

    def to_dict(self):
        return {'type': 'plain', 'data': {'text': self.text}}

class Url(UrlT):
    mm = False
    disable_mm = False
    md_format = False

    def __init__(self, url: str, use_mm: bool = False, disable_mm: bool = False):
        self.url = url
        if (Url.mm and not disable_mm) or (use_mm and not Url.disable_mm):
            mm_url = f'https://mm.teahouse.team/?source=akaribot&rot13=%s'
            rot13 = str.maketrans(
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
                "nopqrstuvwxyzabcdefghijklmNOPQRSTUVWXYZABCDEFGHIJKLM")
            self.url = mm_url % parse.quote(parse.unquote(url).translate(rot13))

    def __str__(self):
        if Url.md_format:
            return f'[{self.url}]({self.url})'
        return self.url

    def __repr__(self):
        return f'Url(url="{self.url}")'

    def to_dict(self):
        return {'type': 'url', 'data': {'url': self.url}}


class FormattedTime:
    def __init__(self, timestamp: float, date=True, iso=False, time=True, seconds=True, timezone=True):
        self.timestamp = timestamp
        self.date = date
        self.iso = iso
        self.time = time
        self.seconds = seconds
        self.timezone = timezone

    def to_str(self, msg: MessageSession = None):
        ftime_template = []
        if msg:
            if self.date:
                if self.iso:
                    ftime_template.append(msg.locale.t("time.date.iso.format"))
                else:
                    ftime_template.append(msg.locale.t("time.date.format"))
            if self.time:
                if self.seconds:
                    ftime_template.append(msg.locale.t("time.time.format"))
                else:
                    ftime_template.append(msg.locale.t("time.time.nosec.format"))
            if self.timezone:
                if msg._tz_offset == "+0":
                    ftime_template.append("(UTC)")
                else:
                    ftime_template.append(f"(UTC{msg._tz_offset})")
        else:
            ftime_template.append('%Y-%m-%d %H:%M:%S')
        if not msg:
            return datetime.fromtimestamp(self.timestamp).strftime(' '.join(ftime_template))
        else:
            return (datetime.utcfromtimestamp(self.timestamp) + msg.timezone_offset).strftime(' '.join(ftime_template))

    def __str__(self):
        return self.to_str()

    def __repr__(self):
        return f'FormattedTime(timestamp={self.timestamp})'

    def to_dict(self):
        return {
            'type': 'formatted_time',
            'data': {
                'timestamp': self.timestamp,
                'date': self.date,
                'iso': self.iso,
                'time': self.time,
                'seconds': self.seconds,
                'timezone': self.timezone}}


class I18NContext:
    def __init__(self, key, **kwargs):
        self.key = key
        self.kwargs = kwargs

    def __str__(self):
        return str(self.to_dict())

    def __repr__(self):
        return f'I18NContext(key="{self.key}", kwargs={self.kwargs})'

    def to_dict(self):
        return {'type': 'i18n', 'data': {'key': self.key, 'kwargs': self.kwargs}}


class ErrorMessage(EMsg):
    def __init__(self, error_message, locale=None):
        self.error_message = error_message
        if locale:
            locale = Locale(locale)
            if locale_str := re.findall(r'\{(.*)}', error_message):
                for l in locale_str:
                    error_message = error_message.replace(f'{{{l}}}', locale.t(l))
            self.error_message = locale.t('error') + error_message
            if Config('bug_report_url', cfg_type = str):
                self.error_message += '\n' + locale.t('error.prompt.address', url=str(Url(Config('bug_report_url', cfg_type = str))))

    def __str__(self):
        return self.error_message

    def __repr__(self):
        return self.error_message

    def to_dict(self):
        return {'type': 'error', 'data': {'error': self.error_message}}


class Image(ImageT):
    def __init__(self,
                 path, headers=None):
        self.need_get = False
        self.path = path
        self.headers = headers
        if isinstance(path, PImage.Image):
            save = f'{Config("cache_path", "./cache/")}{str(uuid.uuid4())}.png'
            path.convert('RGBA').save(save)
            self.path = save
        elif re.match('^https?://.*', path):
            self.need_get = True

    async def get(self):
        if self.need_get:
            return abspath(await self.get_image())
        return abspath(self.path)

    @retry(stop=stop_after_attempt(3))
    async def get_image(self):
        url = self.path
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as req:
                raw = await req.read()
                ft = filetype.match(raw).extension
                img_path = f'{Config("cache_path", "./cache/")}{str(uuid.uuid4())}.{ft}'
                with open(img_path, 'wb+') as image_cache:
                    image_cache.write(raw)
                return img_path

    async def get_base64(self):
        file = await self.get()
        with open(file, 'rb') as f:
            return str(base64.b64encode(f.read()), "UTF-8")

    def __str__(self):
        return self.path

    def __repr__(self):
        return f'Image(path="{self.path}", headers={self.headers})'

    def to_dict(self):
        return {'type': 'image', 'data': {'path': self.path}}


class Voice(VoiceT):
    def __init__(self,
                 path=None):
        self.path = path

    def __str__(self):
        return self.path

    def __repr__(self):
        return f'Voice(path={self.path})'

    def to_dict(self):
        return {'type': 'voice', 'data': {'path': self.path}}


class EmbedField(EmbedFieldT):
    def __init__(self,
                 name: str = None,
                 value: str = None,
                 inline: bool = False):
        self.name = name
        self.value = value
        self.inline = inline

    def __str__(self):
        return f'{self.name}: {self.value}'

    def __repr__(self):
        return f'EmbedField(name="{self.name}", value="{self.value}", inline={self.inline})'

    def to_dict(self):
        return {'type': 'field', 'data': {'name': self.name, 'value': self.value, 'inline': self.inline}}


class Embed(EmbedT):
    def __init__(self,
                 title: str = None,
                 description: str = None,
                 url: str = None,
                 timestamp: float = datetime.now().timestamp(),
                 color: int = 0x0091ff,
                 image: Image = None,
                 thumbnail: Image = None,
                 author: str = None,
                 footer: str = None,
                 fields: List[EmbedField] = None):
        self.title = title
        self.description = description
        self.url = url
        self.timestamp = timestamp
        self.color = color
        self.image = image
        self.thumbnail = thumbnail
        self.author = author
        self.footer = footer
        self.fields = []
        if fields:
            for f in fields:
                if isinstance(f, EmbedField):
                    self.fields.append(f)
                elif isinstance(f, dict):
                    self.fields.append(EmbedField(f['data']['name'], f['data']['value'], f['data']['inline']))
                else:
                    raise TypeError(f"Invalid type {type(f)} for EmbedField")

    def to_message_chain(self, msg: MessageSession = None):
        text_lst = []
        if self.title:
            text_lst.append(self.title)
        if self.description:
            text_lst.append(self.description)
        if self.url:
            text_lst.append(self.url)
        if self.fields:
            for f in self.fields:
                text_lst.append(f"{f.name}{msg.locale.t('message.colon')}{f.value}")
        if self.author:
            text_lst.append(msg.locale.t('message.embed.author') + self.author)
        if self.footer:
            text_lst.append(self.footer)
        message_chain = []
        if text_lst:
            message_chain.append(Plain('\n'.join(text_lst)))
        if self.image:
            message_chain.append(self.image)
        return message_chain

    def __str__(self):
        return str(self.to_message_chain())

    def __repr__(self):
        return f'Embed(title="{self.title}", description="{self.description}", url="{self.url}", ' \
            f'timestamp={self.timestamp}, color={self.color}, image={self.image.__repr__()}, ' \
            f'thumbnail={self.thumbnail.__repr__()}, author="{self.author}", footer="{self.footer}", ' \
            f'fields={self.fields})'

    def to_dict(self):
        return {
            'type': 'embed',
            'data': {
                'title': self.title,
                'description': self.description,
                'url': self.url,
                'timestamp': self.timestamp,
                'color': self.color,
                'image': self.image,
                'thumbnail': self.thumbnail,
                'author': self.author,
                'footer': self.footer,
                'fields': [f.to_dict() for f in self.fields]}}


__all__ = ["Plain", "Image", "Voice", "Embed", "EmbedField", "Url", "ErrorMessage", "FormattedTime", "I18NContext"]
