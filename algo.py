import alpaca_trade_api as tradeapi
import requests
import time
import json
import ta
from ta import momentum
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression as lr
from datetime import datetime, timedelta
from pytz import timezone
import time
import copy
import pytz


"""
An attempt to make a TTM Squeeze Indicator
"""


#read credentials in from json file

cred = json.load(open("credentials.json"))
base_url = cred['endpoint']
api_key_id = cred['key']
api_secret = cred['secret']
mailgun = cred['mailgun']
mailgunURL = cred['URL']
email = cred['email']


api = tradeapi.REST(
    base_url=base_url,
    key_id=api_key_id,
    secret_key=api_secret
)

session = requests.session()

#sqzonl = False
#sqzoffl = False
#nosqzl = True
sqzl = {}

#times to aggregate to (have to manually do 5 minute increments because polygon doesnt allow 5 min for some reason)
ftimes = "8:30,8:35,8:40,8:45,8:50,8:55,9:00,9:05,9:10,9:15,9:20,9:25,9:30,9:35,9:40,9:45,9:50,9:55,10:00,10:05,10:10,10:15,10:20,10:25,10:30,10:35,10:40,10:45,10:50,10:55,11:00,11:05,11:10,11:15,11:20,11:25,11:30,11:35,11:40,11:45,11:50,11:55,12:00,12:05,12:10,12:15,12:20,12:25,12:30,12:35,12:40,12:45,12:50,12:55,13:00,13:05,13:10,13:15,13:20,13:25,13:30,13:35,13:40,13:45,13:50,13:55,14:00,14:05,14:10,14:15,14:20,14:25,14:30,14:35,14:40,14:45,14:50,14:55,15:00".split(",")


min_share_price = 5.0
max_share_price = 50.0
# Minimum previous-day dollar volume for a stock we might consider
min_last_dv = 2500000
# Stop limit to default to
#default_stop = .95


def get_historical(symbols_h):
    print("History")

    minn = {}
    day = {}
    coun = 0
    print(symbols_h)
    for s in symbols_h:
        
        day[s] = api.polygon.historic_agg(size="minute", symbol=s, limit=1200).df
        coun+=1
    print("{}/{}".format(coun, len(symbols_h)))
    print(day[symbols_h[0]])
    return day

def get_hour_historical(symbols_h):
    
    mins = {}
    hour = {}

    count = 0
    print("min5_history")
    for s in symbols_h:
        s = s.ticker
        truemins = api.polygon.historic_agg(size="minute", symbol=s, limit=4320).df
        truehourh = copy.deepcopy(truemins)
        #print(truemins)
        count+=1

        mins[s] = copy.deepcopy(truemins)
        truemins['volume'] = mins[s]['volume'].dropna().resample('5min', loffset='5min').sum()
        truemins['open'] = mins[s]['open'].dropna().resample('5min', loffset='5min').first()
        truemins['close']= mins[s]['close'].dropna().resample('5min', loffset='5min').last()
        truemins['high'] = mins[s]['high'].dropna().resample('5min', loffset='5min').max()
        truemins['low'] = mins[s]['low'].dropna().resample('5min', loffset='5min').min()
        #print(truemins)
        mins[s] = truemins.dropna().resample('5min', loffset='5min').sum()
        

        hour[s] = copy.deepcopy(truemins)
        truehourh['volume'] = hour[s]['volume'].dropna().resample('60min', loffset='30min').sum()
        truehourh['open'] = hour[s]['open'].dropna().resample('60min', loffset='30min').first()
        truehourh['close']= hour[s]['close'].dropna().resample('60min', loffset='30min').last()
        truehourh['high'] = hour[s]['high'].dropna().resample('60min', loffset='30min').max()
        truehourh['low'] = hour[s]['low'].dropna().resample('60min', loffset='30min').min()
        hour[s] = truehourh.dropna().resample('60min', loffset='30min').sum()
        #index = test[test[]]
        td = []
        for i in hour[s].index:
            for g in ftimes:
                if str(i)[11:16] not in ftimes:
                    td.append(i)
        hour[s] = hour[s].drop(td)

        td = []
        for i in mins[s].index:
            for g in ftimes:
                if str(i)[11:16] not in ftimes:
                    td.append(i)
        mins[s] = mins[s].drop(td)
    

    return mins, hour

"""
def find_stop(current_value, min5_history, now):
    series = min5_history['low'][-100:] \
                .dropna().resample('5min').min()
    series = series[now.floor('1D'):]
    diff = np.diff(series.values)
    low_index = np.where((diff[:-1] <= 0) & (diff[1:] > 0))[0] + 1
    if len(low_index) > 0:
        return series[low_index[-1]] - 0.01
    return current_value * default_stop

target_prices[symbol] = data.close + (
                (data.close - stop_price) * 3
            )
"""

def run(tickers):
    # steam connection
    
    conn = tradeapi.StreamConn(base_url=base_url, key_id=api_key_id, secret_key=api_secret)

    # Update initial state with information from tickers
    
    symbols = tickers

    #initialize sqz states

    for s in tickers:
        sqzl[s.ticker] = [False, False, True]

    #minute_history = get_historical([symbol])
    min5_history, hour_history = get_hour_historical(symbols)

    print(min5_history)
    # Use trade updates to keep track of our portfolio
    
    @conn.on(r'trade_update')
    async def handle_trade_update(conn, channel, data):
        print("hi")

    @conn.on(r'A\..*')
    async def handle_second_bar(conn, channel, data):
        symbol = data.symbol
        
        #global sqzonl
        #global sqzoffl
        #global nosqzl

        global sqzl
        sqzon = False
        sqzoff = False
        nosqz = False


        ts = data.start
        print(data.symbol)
        ts -= timedelta(minutes= ts.minute//5, seconds=ts.second, microseconds=ts.microsecond)
        try:
            current = min5_history[data.symbol].loc[ts]
        except KeyError:
            current = None
        new_data = []
        if current is None:
            new_data = [
                data.open,
                data.high,
                data.low,
                data.close,
                data.volume
            ]
        else:
            new_data = [
                current.open,
                data.high if data.high > current.high else current.high,
                data.low if data.low < current.low else current.low,
                data.close,
                current.volume + data.volume
            ]
    
        min5_history[symbol].loc[ts] = new_data

        try:
            current = hour_history[data.symbol].loc[ts]
        except KeyError:
            current = None
        new_data = []
        if current is None:
            new_data = [
                data.open,
                data.high,
                data.low,
                data.close,
                data.volume
            ]
        else:
            new_data = [
                current.open,
                data.high if data.high > current.high else current.high,
                data.low if data.low < current.low else current.low,
                data.close,
                current.volume + data.volume
            ]
        hour_history[symbol].loc[ts] = new_data

        #print(min5_history[symbol].loc[ts])
        bbh = ta.bollinger_hband(min5_history[symbol]['close'].dropna(), n = 20, ndev=2)
        bbl = ta.bollinger_lband(min5_history[symbol]['close'].dropna(), n = 20, ndev=2)
        bba = ta.bollinger_mavg(min5_history[symbol]['close'].dropna(), n=20)

        kca = ta.keltner_channel_central(min5_history[symbol]['high'],min5_history[symbol]['low'], min5_history[symbol]['close'], n=20)
        kcl = ta.keltner_channel_lband(min5_history[symbol]['high'],min5_history[symbol]['low'], min5_history[symbol]['close'], n=20)
        kch = ta.keltner_channel_hband(min5_history[symbol]['high'],min5_history[symbol]['low'], min5_history[symbol]['close'], n=20)

        bbhh = ta.bollinger_hband(hour_history[symbol]['close'].dropna(), n = 20, ndev=2)
        bblh = ta.bollinger_lband(hour_history[symbol]['close'].dropna(), n = 20, ndev=2)
        bbah = ta.bollinger_mavg(hour_history[symbol]['close'].dropna(), n=20)

        kcah = ta.keltner_channel_central(hour_history[symbol]['high'],hour_history[symbol]['low'], hour_history[symbol]['close'], n=20)
        kclh = ta.keltner_channel_lband(hour_history[symbol]['high'],hour_history[symbol]['low'], hour_history[symbol]['close'], n=20)
        kchh = ta.keltner_channel_hband(hour_history[symbol]['high'],hour_history[symbol]['low'], hour_history[symbol]['close'], n=20)


        
        mom = momentum.ao(min5_history[symbol]['high'], min5_history[symbol]['low'])
        momh= momentum.ao(hour_history[symbol]['high'], hour_history[symbol]['low'])
        
        print(bbl[-1], kcl[-1], bbh[-1], kch[-1])


        
        sqzon = (bbl[-1]>kcl[-1]) and (bbh[-1]<kch[-1])
        sqzoff = bbl[-1]<kcl[-1] and bbh[-1]>kch[-1]
        nosqz = sqzon==False and sqzoff==False
        
        """
        value = (Highest[lengthKC](high)+Lowest[lengthKC](low)+average[lengthKC](close))/3
        val = linearregression[lengthKC](close-value)
        """

        val = (max(min5_history[symbol]['high'][-20:-1]) + min(min5_history[symbol]['low'][-20:-1]) + min5_history[symbol]['close'].mean())/3.0
        v = lr(min5_history[symbol]['close'] - val)

        valh = (max(hour_history[symbol]['high'][-20:-1]) + min(hour_history[symbol]['low'][-20:-1]) + hour_history[symbol]['close'].mean())/3.0
        vh = lr(hour_history[symbol]['close'] - val)

        flag = -1
        #print("hi")
        if sqzl[symbol][0] and sqzon:
            pass

        if sqzl[symbol][0] and sqzoff:
            sqzl[symbol][0] = False
            sqzl[symbol][1] = True
            flag = 0

        if sqzl[symbol][1] and sqzoff:
            pass

        if sqzl[symbol][1] and sqzon:
            sqzl[symbol][1] = False
            sqzl[symbol][0] = True
            flag = 1

        if sqzl[symbol][2] and sqzon:
            sqzl[symbol][2] = False
            sqzl[symbol][0] = True
            flag = 1

        if sqzl[symbol][2] and sqzoff:
            sqzl[symbol][2] = False
            sqzl[symbol][1] = True
            print("sqeeze is OFF")
            print(time.time())
            flag = -1


        if flag == -1:
            print('No Change')
        if flag == 0:
            send_message(symbol, "Pop ::: " + str(mom[-1]))

        if flag == 1:
            send_message(symbol, "Squeeze On")

        #print(type(symbol))
        """
        print(symbol)
        if len(symbols) <= 0:
            conn.close()
        conn.deregister([
            'A.{}'.format(symbol),
            'AM.{}'.format(symbol)
        ])
        """

    # Replace aggregated 1s bars with incoming 1m bars

    #IDEA: RUN A MINUTE BASED TTM SQUEEZE ALGORITHM AND AN HOUR BASED ALGORITHM.
    #CURRENT: Aggregates new minute bar data to help resolve any potential data loss from the second based data.
    @conn.on(r'AM\..*')
    async def handle_minute_bar(conn, channel, data):
        ts = data.start
        ts -= timedelta(minutes= ts.minute//5, seconds=ts.second, microseconds=ts.microsecond)
        current = min5_history[data.symbol].loc[ts]
        min5_history[data.symbol].loc[ts] = [
            data.open,
            data.high if data.high > current.high else current.high,
            data.low if data.low < current.low else current.low,
            data.close,
            data.volume+current.volume
        ]
        #print(min5_history)
    
    #have to aggregate minute data into hour based data.
    #

    channels = ['trade_updates']
    for s in symbols:
        symbol_channels = ['A.{}'.format(s.ticker), 'AM.{}'.format(s.ticker)]
        channels += symbol_channels
    print("watching {} symbols".format(len(symbols)))
    run_ws(conn, channels)


#Handle failed websocket connections by reconnecting 
def run_ws(conn, channels):
    try:
        conn.run(channels)
    except Exception as e:
        #print(e)
        conn.close
        run_ws(conn, channels)

def send_message(symbol, action):
    n = datetime.now()
    n = n - timedelta(microseconds=n.microsecond)
    n = n.time()
    return requests.post(
	"https://api.mailgun.net/v3/"+ mailgunURL +"/messages",
	auth=("api", mailgun),
	data={"from": "TRADE NOTIFICATION<postmaster@"+ mailgunURL +">",
			"to": email,
			"subject": "{} - {}".format(symbol, action),
			"text": "Time: {}".format(n)})


def get_tickers():
    print('Getting current ticker data...')
    tickers = api.polygon.all_tickers()

    print('Success.')
    assets = api.list_assets()
    symbols = [asset.symbol for asset in assets if asset.tradable]

    return [ticker for ticker in tickers if (ticker.ticker in ['TTD', 'SPY', 'AMD', 'ROKU', 'PINS', "SQ", 'TSLA'])]
    """
    return [ticker for ticker in tickers if (
        ticker.ticker in symbols and
        ticker.lastTrade['p'] >= min_share_price and
        ticker.lastTrade['p'] <= max_share_price and
        ticker.prevDay['v'] * ticker.lastTrade['p'] > min_last_dv #and
        #ticker.todaysChangePerc >= 3.5
    )]
    """

if __name__ == "__main__":
    t = api.get_clock()
    #print(get_hour_historical(["AMD"]))
    #print("symbol: ")
    #sym = input()
    #if t.is_open == False:
    #    tillopen = (t.next_open - t.timestamp).total_seconds()
    #    print("market closed. Sleep for ", int(tillopen), " seconds")
    #    time.sleep(int(tillopen))
    
    #print(sym)
    run(get_tickers())
