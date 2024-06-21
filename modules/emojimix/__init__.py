import os
from typing import List, Optional, Tuple

import emoji
import ujson as json

from config import Config
from core.builtins import Bot, Image
from core.component import module
from core.logger import Logger

data_path = os.path.abspath('./assets/emojimix/emoji_data.json')
API = "https://www.gstatic.com/android/keyboard/emojikitchen"


class EmojimixGenerator:
    def __init__(self):
        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.known_supported_emoji: List[str] = data["knownSupportedEmoji"]
        self.data: dict = data["data"]
        self.date_mapping: dict = {idx: date for idx, date in enumerate(data["date"])}


    @staticmethod
    def make_emoji_tuple(emoji1: str, emoji2: str) -> Tuple[str, str]:
        unicode_emoji1 = '-'.join(f'{ord(char):x}' for char in emoji1)
        unicode_emoji2 = '-'.join(f'{ord(char):x}' for char in emoji2)
        return (unicode_emoji1, unicode_emoji2)


    def check_supported(self, emoji_tuple: Tuple[str, str]) -> List[str]:
        unsupported_emojis: List[str] = []
        checked: set = set()
        for emoji in emoji_tuple:
            if emoji not in self.known_supported_emoji and emoji not in checked:
                emoji_symbol = ''.join(chr(int(segment, 16)) for segment in emoji.split('-'))
                unsupported_emojis.append(emoji_symbol)
                checked.add(emoji)
        return unsupported_emojis


    def mix_emoji(self, emoji_tuple: Tuple[str, str]) -> Optional[str]:
        str_tuple_1 = f"({emoji_tuple[0]}, {emoji_tuple[1]})"
        str_tuple_2 = f"({emoji_tuple[1]}, {emoji_tuple[0]})"

        if str_tuple_1 in self.data:
            date_index = self.data[str_tuple_1]
            date = self.date_mapping[date_index]
            left_emoji = emoji_tuple[0]
            right_emoji = emoji_tuple[1]
        elif str_tuple_2 in self.data:
            date_index = self.data[str_tuple_2]
            date = self.date_mapping[date_index]
            left_emoji = emoji_tuple[1]
            right_emoji = emoji_tuple[0]
        else:
            return None
        
        left_code_point = '-'.join(f'u{segment}' for segment in left_emoji.split('-'))
        right_code_point = '-'.join(f'u{segment}' for segment in right_emoji.split('-'))
        url = f"{API}/{date}/{left_code_point}/{left_code_point}_{right_code_point}.png"
        return url


    def list_supported_emojis(self, emoji: Optional[str] = None) -> List[str]:
        supported_combinations: List[str] = []

        if emoji:
            emoji_symbol = emoji

            if emoji_symbol in self.known_supported_emoji:
                supported_combinations.append(emoji_symbol)

            emoji_code = '-'.join(f'{ord(char):x}' for char in emoji_symbol)

            for key in self.data:
                if emoji_code in key:
                    pair = key.replace('(', '').replace(')', '').split(', ')
                    pair = [p.strip() for p in pair]
                    if pair[0] == emoji_code:
                        pair_emoji = ''.join(chr(int(segment, 16)) for segment in pair[1].split('-'))
                        supported_combinations.append(pair_emoji)
                    elif pair[1] == emoji_code:
                        pair_emoji = ''.join(chr(int(segment, 16)) for segment in pair[0].split('-'))
                        supported_combinations.append(pair_emoji)
        else:
            for emoji_code in self.known_supported_emoji:
                emoji_char = ''.join(chr(int(segment, 16)) for segment in emoji_code.split('-'))
                supported_combinations.append(emoji_char)

        return supported_combinations

mixer = EmojimixGenerator()


emojimix = module('emojimix', developers=['DoroWolf'])


@emojimix.handle('<emoji1> <emoji2> {{emojimix.help}}')
async def _(msg: Bot.MessageSession, emoji1: str, emoji2: str):
    if not (check_valid_emoji(emoji1) and check_valid_emoji(emoji2)):
        await msg.finish(msg.locale.t("emojimix.message.invalid"))
    combo = mixer.make_emoji_tuple(emoji1, emoji2)
    Logger.debug(str(combo))
    unsupported_emojis = mixer.check_supported(combo)
    if unsupported_emojis:
        await msg.finish(f"{msg.locale.t('emojimix.message.unsupported')}{' '.join(unsupported_emojis)}")
    result = mixer.mix_emoji(combo)
    Logger.debug(result)
    if result:
        await msg.finish(Image(result))
    else:
        await msg.finish(msg.locale.t("emojimix.message.not_found"))

def check_valid_emoji(str):
    return emoji.is_emoji(str)


@emojimix.handle('list [<emoji>] {{emojimix.help.list}}')
async def _(msg: Bot.MessageSession, emoji: str = None):
    supported_emojis = mixer.list_supported_emojis(emoji)
    if emoji:
        await msg.finish(msg.locale.t('emojimix.message.combine_supported', emoji=emoji) + '\n' + ' '.join(supported_emojis))
    else:
        await msg.finish(msg.locale.t('emojimix.message.all_supported') + '\n' + ' '.join(supported_emojis))
