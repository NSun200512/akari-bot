from datetime import datetime

from core.builtins import Bot
from core.builtins import Image, Plain, ErrorMessage
from core.utils.http import get_url


async def get_info(message: Bot.MessageSession, url, get_detail=False):
    try:
        data = await get_url(url, 200, fmt='json')
    except ValueError as e:
        if str(e).startswith('404'):
            await msg.finish(msg.locale.t("bilibili.message.error"))
        else:
           await msg.finish(ErrorMessage(str(e)))
        

    view = data['data']['View']
    stat = view['stat']
    
    pic = view['pic']
    video_url = f"https://www.bilibili.com/video/{view['bvid']}"
    title = view['title']
    tname = view['tname']

    timestamp = view['ctime']
    dt_object = datetime.fromtimestamp(timestamp)
    time = dt_object.strftime('%Y-%m-%d %H:%M:%S')

    if len(view['pages']) > 1:
        pages = f" ({len(view['pages'])} P)"
    else:
        pages = ''

    stat_view = format_num(stat['view'])
    stat_danmaku = format_num(stat['danmaku'])
    stat_reply = format_num(stat['reply'])
    stat_favorite = format_num(stat['favorite'])
    stat_coin = format_num(stat['coin'])
    stat_share = format_num(stat['share'])
    stat_like = format_num(stat['like'])

    owner = view['owner']['name']
    fans = format_num(data['data']['Card']['card']['fans'])

    if get_detail:
        msg = video_url + message.locale.t('bilibili.message', title=title, tname=tname, owner=owner, time=time)
    else:
        msg = video_url + message.locale.t('bilibili.message.detail', title=title, pages=pages, tname=tname,
                                                            owner=owner, fans=fans, view=stat_view, danmaku=stat_danmaku, reply=stat_reply,
                                                            like=stat_like, coin=stat_coin, favorite=stat_favorite, share=stat_share)
        
    await msg.finish([Image(pic), Plain(msg)])


def format_num(number):
    if number >= 1000000000:
        return f'{number/1000000000:.1f}B'
    elif number >= 1000000:
        return f'{number/1000000:.1f}M'
    elif number >= 1000:
        return f'{number/1000:.1f}k'
    else:
        return str(number)



    