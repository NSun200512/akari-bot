import os
import json

from datetime import datetime, timedelta
from decimal import Decimal

from config import Config
from core.builtins import Bot
from core.utils.http import get_url
from core.utils.storedata import get_stored_list, update_stored_list

ONE_K = Decimal('1000')
# https://openai.com/pricing
BASE_COST_GPT_3_5 = Decimal('0.002')  # gpt-3.5-turbo： $0.002 / 1K tokens
# We are not tracking specific tool usage like searches b/c I'm too lazy, use a universal multiplier
THIRD_PARTY_MULTIPLIER = Decimal('1.5')
PROFIT_MULTIPLIER = Decimal('1.1')  # At the time we are really just trying to break even
PRICE_PER_1K_TOKEN = BASE_COST_GPT_3_5 * THIRD_PARTY_MULTIPLIER * PROFIT_MULTIPLIER
USD_TO_CNY = Decimal('7.3')  # Assuming 1 USD = 7.3 CNY
CNY_TO_PETAL = 100  # 100 petal = 1 CNY


async def get_petal_exchange_rate():
    api_key = Config('exchange_rate_api_key')
    api_url = f'https://v6.exchangerate-api.com/v6/{api_key}/pair/USD/CNY/1.0'
    data = await get_url(api_url, 200, fmt='json')
    if data['result'] == "success":
        petal_value = data['conversion_result'] * CNY_TO_PETAL
        return {"petal": petal_value}
    return None


async def load_or_refresh_cache():
    cache_dir = Config('cache_path')
    file_path = os.path.join(cache_dir, 'petal_exchange_rate_cache.json')
    if os.path.exists(file_path):
        modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        next_day = modified_time + timedelta(days=1)
        expiration_time = datetime(next_day.year, next_day.month, next_day.day, 0, 0, 0)
        current_time = datetime.now()
        if current_time < expiration_time:
            with open(file_path, 'r') as file:
                data = json.load(file)
                return data["petal"]

    exchanged_petal_data = await get_petal_exchange_rate()
    if exchanged_petal_data:
        with open(file_path, 'w') as file:
            json.dump(exchanged_petal_data, file)
        return exchanged_petal_data["petal"]
    return None


async def count_petal(tokens):
    petal_exchange_rate = await load_or_refresh_cache()
    price = tokens / ONE_K * PRICE_PER_1K_TOKEN
    if petal_exchange_rate:
        petal = price * Decimal(petal_exchange_rate).quantize(Decimal('0.00'))
    else:
        petal = price * USD_TO_CNY * CNY_TO_PETAL
    return petal


async def gained_petal(msg: Bot.MessageSession, amount):
    if Config('openai_api_key') and Config('enable_get_petal'):
        limit = Config('gained_petal_limit', 10)
        p = get_stored_list(msg.target.client_name, 'gainedpetal')
        if not p:
            p = [{}]
        p = p[0]
        now = datetime.now().timestamp()
        if msg.target.target_id not in p:
            p[msg.target.target_id] = {'time': now, 'amount': amount}
            p = [p]
            update_stored_list(msg.target.client_name, 'gainedpetal', p)
            msg.data.modify_petal(amount)
            return msg.locale.t('petal.message.gained.success', amount=amount)
        else:
            if now - p[msg.target.target_id]['time'] > 60 * 60 * 24:
                p[msg.target.target_id] = {'time': now, 'amount': amount}
                p = [p]
                msg.data.modify_petal(amount)
                update_stored_list(msg.target.client_name, 'gainedpetal', p)
            else:
                if p[msg.target.target_id]['amount'] + amount > limit:
                    return msg.locale.t('petal.message.gained.limit')
                p[msg.target.target_id]['amount'] += amount
                p = [p]
                update_stored_list(msg.target.client_name, 'gainedpetal', p)
                msg.data.modify_petal(amount)
            return msg.locale.t('petal.message.gained.success', amount=amount)


async def lost_petal(msg: Bot.MessageSession, amount):
    if Config('openai_api_key') and Config('enable_get_petal'):
        limit = Config('lost_petal_limit', 5)
        p = get_stored_list(msg.target.client_name, 'lostpetal')
        if not p:
            p = [{}]
        p = p[0]
        now = datetime.now().timestamp()
        if msg.target.target_id not in p:
            p[msg.target.target_id] = {'time': now, 'amount': amount}
            p = [p]
            update_stored_list(msg.target.client_name, 'lostpetal', p)
            msg.data.modify_petal(-amount)
            return msg.locale.t('petal.message.lost.success', amount=amount)
        else:
            if now - p[msg.target.target_id]['time'] > 60 * 60 * 24:
                p[msg.target.target_id] = {'time': now, 'amount': amount}
                p = [p]
                msg.data.modify_petal(-amount)
                update_stored_list(msg.target.client_name, 'lostpetal', p)
            else:
                if p[msg.target.target_id]['amount'] + amount > limit:
                    return msg.locale.t('petal.message.lost.limit')
                p[msg.target.target_id]['amount'] += amount
                p = [p]
                update_stored_list(msg.target.client_name, 'lostpetal', p)
                msg.data.modify_petal(-amount)
            return msg.locale.t('petal.message.lost.success', amount=amount)
