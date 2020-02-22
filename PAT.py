import requests, time, json
import pandas as pd
import numpy as np
from collections import *
import matplotlib.pyplot as pl
from hmmlearn import hmm
import random
import multiprocessing
from multiprocessing import Pool
import multiprocessing.pool
from sklearn.preprocessing import MinMaxScaler
from sklearn.utils import check_random_state
from sklearn.model_selection import train_test_split
import time
from tqdm import tqdm
#import cupy as np
#import numba as nb


"""
 *  This program will be a little different from the last.
 *  Instead of sticking with normal timeseries data, I will
 *  use volume based data. What I mean by this is instead of
 *  having periods be completed after certain periods of time,
 *  periods will end after a certian amount of volume has been
 *  accumulated.
 *  
 *  The idealistic benefit of making this change is that
 *  the data will better represent 'true' price movements.
 *  Price movement isn't driven by time, price movement is
 *  driven by volume. To see this, time can move forward with
 *  no volume and the price will never change because of
 *  the lack of voulme.
 *
 *  Using volume will add challenges from a programming standpoints.
 *  Where in timeseries data, periods end regularly and are determined
 *  external from the market, with volume based data, trades aren't
 *  and depending on the market being conscious of these periods sizes 
 *  will be of much greater importance. 
 *  Along with this, visualizing will be very important for me to make
 *  sense of the data I'm seeing. I've been finding it difficult to
 *  locate anything on this form of analysis.
 Number of bullish/bearish periods and their ratio
 Body size of bullish/bearish periods
 Number of consecutive periods
 TODO:
    See what actual returns will be if you open a potistion at the beginning of a period (when theres positive movement) then close at the end
        compare this method to closing after with certain "high" percentages are reaches.
        then compare this to adding a stop loss
    GPU computations 
"""



#Load credentials from json
#cred = json.load(open("credentials.json"))
files = json.load(open("files.json"))

def readFiles():
    #da = pd.read_csv(''+files['BTC']+'/2013/merged.csv')
    #da.columns = ['time', 'open', 'close', 'high', 'min', 'volume']
    #dat = pd.read_csv(''+files['BTC']+'/2014/merged.csv')
    #dat.columns = ['time', 'open', 'close', 'high', 'min', 'volume']
    #data = pd.read_csv(''+files['BTC']+'/2015/merged.csv')
    #data.columns = ['time', 'open', 'close', 'high', 'min', 'volume']

    #sticking to more recent data
    data0 = pd.read_csv(''+files['BTC']+'/2016/merged.csv')
    data0.columns = ['time', 'open', 'close', 'high', 'min', 'volume']
    data1 = pd.read_csv(''+files['BTC']+'/2017/merged.csv')
    data1.columns = ['time', 'open', 'close', 'high', 'min', 'volume']
    data2 = pd.read_csv(''+files['BTC']+'/2018/merged.csv')
    data2.columns = ['time', 'open', 'close', 'high', 'min', 'volume']
    #print(sum(pd.concat([da, dat, data, data0, data1, data2], ignore_index=True)['close']))
    return pd.concat([data0, data1, data2], ignore_index=True)

def readTestFiles():
    data = pd.read_csv(''+files['BTC']+'/2019/merged.csv')
    data.columns = ['time', 'open', 'close', 'high', 'min', 'volume']
    return pd.concat([data], ignore_index=True)

def readTestFiles():
    data = pd.read_csv(''+files['BTC']+'/2019/merged.csv')
    data.columns = ['time', 'open', 'close', 'high', 'min', 'volume']
    return pd.concat([data], ignore_index=True)

def readTestModelFiles():
    dat = pd.read_csv(''+files['AMD']+'/AMD_2000_2009.csv')
    dat.columns = ['time', 'open', 'high', 'min', 'close', 'volume']
    #dat['time'] =  pd.to_datetime(dat['time'], infer_datetime_format=True)
    #dat = dat.set_index('time')
    
    
    
    
    data = pd.read_csv(''+files['AMD']+'/AMD_2010_2019.csv')
    data.columns = ['time', 'open', 'high', 'min', 'close', 'volume']
    #data['time'] =  pd.to_datetime(data['time'], infer_datetime_format=True)
    #data = data.set_index('time')

    #print(data)
    return pd.concat([dat, data])

def readModel():
    data0 = pd.read_csv(''+ files['local']+'/Model-V1.csv')
    data0.columns = ['index', 'fracC', 'fracH', 'fracL']
    return np.column_stack((data0['fracC'], data0['fracH'], data0['fracL']))

def getHistorical(period, data):
    hist = []
    conv = []
    o = -1
    vals = [o, -1, float('inf'), -1]
    s = 0

    for ind, p in data.iterrows():
        # get the open, close, min, and max for each volume period given the minute based data.
        if(vals[0] == -1 or vals[0] == 0):
            vals[0] = p['open']
        vals = [vals[0], -1, min(vals[2], p['min']), max(vals[3], p['high'])]
        s += p['volume']
        
        if (s >= period):
            
            dif = s - period 
            vals[1] = p['close']
            if(vals[2] > vals[1]):
                print(vals)
            hist.append(vals)
            if(dif!=0):
                o = p['close']
            else:
                o = -1
            vals = [o, -1, float('inf'), -1]
            s = dif
            
    # Make sure to catch the last data point, even if it isn't full.
    if(not (vals[1] == -1)):
        hist.append(vals)

    hist = pd.DataFrame(hist, columns = ['open', 'close', 'min', 'max'])
    return (hist, period)


"""
Calcuate the EMA of a given dataset
"""
def ema(length, data):
    return data.ewm(span=length, adjust=False, min_periods=length-1).mean()
    
    #return (hist, period)

"""
Tag data as either bullish or bearish
Length - Length of EMA to lag
Data - Dataframe
"""
def tagData(length, data):
    EMA = ema(length, data['close'])
    slope = EMA.diff().copy()      # rough estimate
    #tagged = data.copy()
    data = data.copy()
    data['tag'] = pd.Series([0 for x in range(data['close'].__len__())], index=data.index)

    condition = slope.loc[slope > 0].index
    data.loc[condition, ['tag']] = 1
    
    return data


"""
Tag data as either bullish or bearish
minSize - Min size of success for dataframe to accept
Data - Dataframe
Vers - String to identify in parallelism.
"""
def splitData(minSize, data, vers):
    split = []
    indP = data.index.tolist()[0]
    s = False
    print()
    for ind, row in tqdm(data.iterrows(), desc = vers + " Splitting"):
        d = (ind - indP)/np.timedelta64(1, 'm')
        if(d == 1):
            if(not s):
                split.append(pd.DataFrame())
                split[-1] = split[-1].append(row)
                s = True
            else:
                split[-1] = split[-1].append(row)
        # Only if in next day because the double removal between days can be killer
        elif(d < 390):
            s = False
            if(len(split)>0 and split[-1].__len__() < minSize):
                del split[-1]
        indP = ind
    return split

"""
    converts from open, close, min, max
    to period change, max/min, fractional high, and fractional low
    TODO: DEBUGGGGGGGGG (DATA PRESENTATION IS THE MOST IMPORTANT PART OF THIS PROCESS)
"""
def convert(hist):
    #print("Converting data")
    conv = []

    o = np.array(hist['open'])
    c = np.array(hist['close'])
    h = np.array(hist['max'])
    l = np.array(hist['min'])
    
    fracC = []
    fracH = []
    fracL = []


    for i in range(len(o.tolist())):
        if(c[i]-o[i] < 0):
            if((o[i]-c[i])/o[i] >= 1 and (o[i]-c[i])/o[i] <=1.5):
                fracC.append(-.75)
            elif((o[i]-c[i])/o[i] > 1.5):
                fracC.append(-1)
            else:
                fracC.append(1/np.log((o[i]-c[i])/o[i]))
        elif(c[i]-o[i] > 0):
            if((c[i]-o[i])/o[i] >= 1 and (c[i]-o[i])/o[i] <= 1.5):
                fracC.append(.75)
            elif((c[i]-o[i])/o[i] > 1.5):
                fracC.append(1)
            else:
                fracC.append(-1/np.log((c[i]-o[i])/o[i]))
        else:
            fracC.append(0)

        #upward movements are unbound. should consider a way to account for this.
        if((h[i]-o[i]) <= 0):
            fracH.append(0)
        elif(np.log((h[i]-o[i])/o[i]) >= 0):
            fracH.append(1)
        else:
            fracH.append(-1/np.log((h[i]-o[i])/o[i]))
       
        #l is bound by zero
        if((o[i]-l[i]) <= 0):
            fracL.append(0)
        elif(np.log((o[i]-l[i])/o[i]) == 0):
            fracL.append(1)
        else:
            fracL.append(-1/np.log((o[i]-l[i])/o[i]))

    
    
    scalar = MinMaxScaler()
    scalar.fit(np.array(fracC).reshape(-1, 1))
    

    # Standardize data to a normal distribution centered around 0
    # Make price movements more priminent AND more consistent
    # Hopefully will increase the effectiveness of the model and its training.
    fracC = (scalar.transform(np.array(fracC).reshape(-1, 1)).flatten()-.5)
    fracH = (scalar.transform(np.array(fracH).reshape(-1, 1)).flatten()-.5)
    fracL = (scalar.transform(np.array(fracL).reshape(-1, 1)).flatten()-.5)
    
    return np.column_stack((fracC, fracH, fracL))
        


def run(period):
    #print('getting historical')
    #hist = getHistorical(period, readFiles())[0]
    #print('getting historical test')
    

    testFiles = readTestModelFiles()
    testFiles['time'] =  pd.to_datetime(testFiles['time'], infer_datetime_format=True)
    testFiles = testFiles.set_index('time').loc['1/1/2018':'1/1/2019']
    print(testFiles)

    vol = int(testFiles['volume'].sum())

    print(vol)

    histT = getHistorical(period, testFiles)[0]

    #conv = convert(hist)

    #hist.to_csv('models/Hist-V1.csv')
    #histT.to_csv('models/Test-V1.csv')
    #pd.DataFrame(conv).to_csv('models/Model-V1.csv')
    

    #for i in conv:
    #    print(i)
    
    #-------------------------------------------------------------------------------------------------------------------

    print('make hmm')
    
    HMM = hmm.GaussianHMM(n_components = 11 , covariance_type="full", random_state=7, n_iter = 1000)

    HMM.fit(readModel())
    print(HMM.sample(10))
    print(HMM.transmat_)
    print('complete')
    
    #-------------------------------------------------------------------------------------------------------------------
    scores  = defaultdict(list)
    pSize = random.randint(10, 75)
    strt = random.randint(8, histT.__len__()-pSize)
    for j in range(15):
        pSize = random.randint(10, 75)
        
        
        for i in range(75):
            #if(i == 0 and not scores[pSize] == None):
            #    break
            strt = random.randint(6, histT.__len__()-pSize)
            pred, sc, ret = predict(HMM, histT, strt, strt+pSize, 5, 25000, False)
            scores[pSize].append((pred, sc, ret))
        

    #-------------------------------------------------------------------------------------------------------------------

    predictedCloseForTest, _, _ = predict(HMM, histT, strt, strt+pSize, 3, 25000, True)
    trueOpenForTest       = histT.iloc[strt:strt+pSize]['open'].values
    trueCloseForTest      = histT.iloc[strt:strt+pSize]['close'].values

    print("50 random periods w/50 different random tests resuts::")

    for i in scores.keys():
        s = str(sum(n for _, n, _ in scores[i])/len(scores[i]))[0:5]
        ret = str(sum(n for _, _, n in scores[i])/len(scores[i]))[0:5]
        print("For the 75 random tests over " + str(i) + " periods, the HMM determined the direction correctly: " + s + "% of the time. Ret: " + ret)
        #plotter(trueCloseForTest, predictedCloseForTest, trueOpenForTest, )


class NoDaemonProcess(multiprocessing.Process):
    # make 'daemon' attribute always return False
    def _get_daemon(self):
        return False
    def _set_daemon(self, value):
        pass
    daemon = property(_get_daemon, _set_daemon)

# We sub-class multiprocessing.pool.Pool instead of multiprocessing.Pool
# because the latter is only a wrapper function, not a proper class.
class MyPool(multiprocessing.pool.Pool):
    Process = NoDaemonProcess


def optimizeGen():
    # Optimse the volumetric period for a given stock on the given model.
    # This will be a test to see if we can use 'generic' models as I theorize we can.

    scores = []
    testFiles = readTestModelFiles()
    testFiles['time'] =  pd.to_datetime(testFiles['time'], infer_datetime_format=True)
    testFiles = testFiles.set_index('time').last('1Y')
    print(testFiles)
    vol = int(testFiles['volume'].sum())
    model = readModel()
    HMM = hmm.GaussianHMM(n_components = 11, covariance_type="full", random_state=7, n_iter = 1000)
    HMM.fit(model)
    for i in tqdm(range(vol//365//6, vol//92, vol//365//4)):
        his = []
        res = []

        with Pool() as p:
            his = p.starmap(getHistorical, [(x, testFiles) for x in range(i, i + vol//365//4 - 10, ( vol//365//4)//4)])

        with Pool() as p:
            res = p.starmap(runTests, [(HMM, j[0], 15, 75, 5, j[1], -1) for j in his])


        for j in res:
            s = 0
            for k in j[0].keys():
                s+=sum(j[0][k])/len(j[0][k])
                t = k

            s = s/len(j[0].keys())
            scores.append((j[1], s))
        
        scores.sort(key = lambda x: x[1], reverse = True)
        print(scores[0:5])
    return scores


"""
Data - Trainging Dataframe
DataT - Testing Datafram 
Mult - Multiplier from smallest accepted timeframe (will change if smaller data sizes can be acquired) (SECOND DATA ON THE COMEUP??)
vers - String to identify in parallelism
"""
def optimize(data, dataT, mult, vers):
    # Dictionary from Period to dict from HMM components to dict from HMM lookBack size to list of tuples of test length and score
    optimizer = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    
    v  = sum([x['volume'].sum() for x in data])//sum([len(x.index) for x in data])       # Average vol/min across all training periods.
    #v = data[0]['volume'].sum() // data[0].index.normalize().unique().__len__()         # Average vol/min on most recent (and representative) dataset
    vtr = [x['volume'].sum()//len(x.index) for x in data]       # Average Vol/Min in each given train period
    vT = [x['volume'].sum()//len(x.index) for x in dataT]       # Average Vol/min in each given test period
    
    volAdjust  = [x/v for x in vtr]                             # Attempt to standardize the avg vol per min throughout training data.
    volAdjustT = [x/v for x in vT]                              # same thing for test data.
    
    vol = sum([x['volume'].sum() for x in data])                # Total Volume across all periods

    dataPoints = sum([len(x.index) for x in data])              # Total number of datapoints in training
    dataPointsT = sum([len(x.index) for x in dataT])            # Total number of datapoints in testing

    # Document all acquired info above for potential debugging purposes
    with open(vers+'.txt', 'w') as f:
        f.write(vers+'\n')
        f.write('Volume: ' + str(vol)+ '\nTrain Data points: ' + str(dataPoints) + '\nTest Data Points: '+str(dataPointsT) + '\n')
        f.write('Vol/Min: ' + str(vol/dataPoints) + '\n')
        #f.write("Train AdjVol: " + str(volAdjust) + '\n')
        #f.write("Test  AdjVol: " + str(volAdjustT) + '\n')
    
    averageBest50 = []
    for i in tqdm(range(int(vol/(dataPoints/mult)), int(vol/(dataPoints/3)), int(vol/(dataPoints/mult*2))), desc=vers+" volume Progress"):
        print() #add some spacing and stuff...
        hist = [convert(getHistorical(i*volAdjust[x], data[x])[0]) for x in range(len(data))]

        # Keep all datapoints seperate@@@@@@@
        histT = [getHistorical(i*volAdjustT[j], dataT[j])[0] for j in range(len(dataT))]
        
        for j in tqdm(range(3, 13), desc=vers+" Components Progress"):
            HMM = hmm.GaussianHMM(n_components = j , covariance_type="full", random_state=7, tol = 1e-3, n_iter = 750, verbose = False)
            HMM.fit(np.concatenate(hist), lengths = [x.__len__() for x in hist])
            res = []
            for k in range(2):
                with Pool() as p:
                    res = p.starmap(runTests, [(HMM, histT, 350, (x+k*4), vol, i, dataPoints) for x in range(1, 5)])
                optimizer[i][j][0+k*4] = res[0]
                optimizer[i][j][1+k*4] = res[1]
                optimizer[i][j][2+k*4] = res[2]
                optimizer[i][j][3+k*4] = res[3]                
                
        for j in optimizer[i].keys():
            for k in optimizer[i][j].keys():
                s = 0
                for l in optimizer[i][j][k][0].keys():
                    s += sum(optimizer[i][j][k][0][l])/len(optimizer[i][j][k][0][l])

                sc = s/len(optimizer[i][j][k][0].keys())

                if len(averageBest50) == 0 or averageBest50[-1][3] < sc:
                    averageBest50.append((i, j, k+1, sc))
                    averageBest50.sort(key = lambda x: x[3], reverse=True)
                    if len(averageBest50) > 50:
                        averageBest50.pop()
        with open(vers+'.txt', 'a') as f:
            f.write(vers + " ::: " + str(averageBest50[0:5])+"\n")

    # Log all results
    for i in optimizer.keys():
        for j in optimizer[i].keys():
            for k in optimizer[i][j].keys():
                s = 0
                for l in optimizer[i][j][k][0].keys():
                    s += sum(optimizer[i][j][k][0][l])/len(optimizer[i][j][k][0][l])
                sc = s/len(optimizer[i][j][k][0].keys())

                with open(vers+'.txt', 'a') as f:
                    f.write(vers+" : " + str(i) + " : " + str(j) + " : " + str(k+1) + " : " + str(sc) + " : " + str(optimizer[i][j][k][3]) +  " : " + str(optimizer[i][j][k][2])+"\n")

    return averageBest50

def runTests(HMM, histT, iter1, lookBack, v, p, days):
    scores  = defaultdict(list)
    strt = 0
    f = 0
    avgRet = 0
    for j in range(iter1):
        # Pick random histT period
        randInd = random.randint(0, len(histT)-1)
    
        if(len(histT[randInd]) > lookBack):
            pred, sc, ret = predict(HMM, histT[randInd], lookBack, 25000, False)
            scores[randInd].append(sc)
            avgRet += ret
        else:
            f += 1
    return (scores, p, f, avgRet/(iter1-f))


# Need to smooth data out before hand so i can get all datapoints in a given period. But if this is accurate, might just need to have the model make
# less decisions that are more accurate.
def predict(hmm, histT, lookBack, ret, plot):
    pred = []

    for i in range(lookBack, len(histT.index)):
        oPrice = histT.iloc[i]['open']
        cPrice = histT.iloc[i]['close']

        prevD = histT.iloc[i-lookBack:i]
        
        conv = convert(prevD)
        
        stateSeq = hmm.predict(conv)
        randstate = check_random_state(hmm.random_state)
        nextState = (np.cumsum(hmm.transmat_, axis=1)[stateSeq[-1]] > randstate.rand()).argmax()
        nextObs = hmm._generate_sample_from_state(nextState,randstate)
        pred.append(oPrice * (1+nextObs[0]))

    c = 0
    s = 0
    for i in histT.iloc[lookBack:]['open'].values:
        if not ret == -1:
            if(pred[s]-i > 0):
                temp = ret*.1
                ret -= temp
                ret += (temp) * histT.iloc[s+lookBack]['close']/i
        if((histT.iloc[s+lookBack]['close']-i)*(pred[s]-i)>=0):
            c+=1
        s+=1
    #print("for this sample, the HMM predicted the correct direction " + str(100*(c/s)) + "% of the time. P = " + str(endInd-startInd) + ".")
    
    if(plot):
        #plotter(histT.iloc[startInd:endInd]['close'].values)
        plotter(histT['close'].values, pred, histT['open'].values, "-"+str(100*(c/s))[0:8])

    return pred, (100*(c/s)), ret


def plotter(data, dataP, dataPO, name):
    #print(data)
    #print(dataP)
    pl.style.use('ggplot')
    plot = pl.figure()
    axis = plot.add_subplot(111)
    axis.plot([x for x in range(data.__len__())], data, 'bo-', label='real close')
    axis.plot([x for x in range(data.__len__())], dataP, 'r+-', label='predicted close (based on realO)')
    axis.plot([x for x in range(data.__len__())], dataPO, 'b+-', label='real open')
    pl.legend()
    pl.savefig("plots/"+name+".png")
    pl.close(plot)

def start():
    #t = api.get_clock()

    # PERIODS::: (average 12 ticks a day)
    #   XRP: 1934152
    #   XRP: ‭23209824‬ (average of a day)
    #   ETH: 248185   (works really well.) 11 - 3 - 60%
    #   BTC: 27040    (should mirror ETH)  11 - 5 - 65%      - Basis for general model
    #   AMD  129376990                     11 - 5 - 59.64%   - First result from general model
    data = readTestModelFiles()
    data['time'] =  pd.to_datetime(data['time'], infer_datetime_format=True)
    data = data.set_index('time')
    res = []

    # Automatically tag data as bearish or bullish with a simple EMA
    #   (keeping the tagging simple will provide proof of concept.
    #    more technical indicators can be used in the future)
    # This will maintain consistency in training data.

    data = tagData(50, data)
    
    # Split data into two Dataframes based on ragging results
    conditionBear = data.loc[data['tag'] == 0].index
    conditionBull = data.loc[data['tag'] == 1].index
    BearTag = data.loc[conditionBear]
    BullTag = data.loc[conditionBull]
    
    # Split data into continous sections
    with MyPool(2) as p:
        res = p.starmap(splitData, [(45, BearTag, 'Bull'), (45, BullTag, 'Bear')])
    
    # Log lost datapoints
    print("Split:: " + str(sum([len(x.index) for x in res[0]])))
    print("Original:: " + str(len(BearTag.index)))

    random.shuffle(res[0])
    random.shuffle(res[1])
    Bear, BearT = train_test_split(res[0], train_size = .75, shuffle = False)
    Bull, BullT = train_test_split(res[1], train_size = .75, shuffle = False)
    
    with MyPool(2) as p:
         res = p.starmap(optimize, [(Bull, BullT, 2, "BULL"),
                                    (Bear, BearT, 2, "BEAR")])

    # with MyPool(2) as p:
    #     res = p.starmap(optimize, [([data.loc['10/8/2019':'12/31/2019'], data.loc['5/1/2018':'9/17/2018'], data.loc['1/1/2019':'8/1/2019'], data.loc['1/1/2009':'1/1/2010'], data.loc['5/5/2005':'2/8/2006']],
    #                                 [data.loc['2/2/2016':'5/1/2017'], data.loc['3/1/2009':'1/1/2010']], .005, "BULL"),
    #                                ([data.loc['8/12/19':'10/4/19'], data.loc['9/2/18':'12/26/18'], data.loc['2/2/18':'4/20/18'], data.loc['4/11/12':'12/13/12'], data.loc['3/3/06':'8/16/06'], data.loc['10/4/06':'5/24/07'], data.loc['11/1/07':'5/2/08']],
    #                                 [data.loc['2/27/18':'4/17/18'], data.loc['5/19/11':'12/21/11'], data.loc['5/4/10':'9/1/10'], data.loc['9/10/08':'3/4/09'], data.loc['9/4/14':'10/5/15']], .005, "BEAR")])
    
    
        # TIME PERIODS FOR FIRST BULL/BEAR OPTIMIZATION
        #res = p.starmap(optimize, [([data.loc['1/1/2019':'12/31/2019'], data.loc['5/5/2005':'2/8/2006'], data.loc['1/1/2008':'1/1/2009'], data.loc['5/1/2018':'8/1/2018']], [data.loc['8/15/2019':'12/31/2019'], data.loc['2/2/2016':'2/17/2017']], "BULL"), ([data.loc['2/24/2006':'1/1/2009']], [data.loc['4/1/2010':'12/1/2012']], "BEAR")])
    
    #optimize([data.loc['5/1/2018':'8/1/2018'], data.loc['8/15/2019':'12/31/2019']], [data.loc['2/2/2016':'2/17/2017'], data.loc['1/1/2019':'6/1/2019']], "BULL")
    #optimize([data.loc['2/24/2006':'1/1/2009']], [data.loc['4/1/2010':'12/1/2012']], "BEAR")
    

    #optimize()

    #period = int(input("INPUT VOLUME PERIOD SIZE: "))
    #run(period)
    # CRYTO CURRENTLY 
    #if t.is_open == False:
    #        tillopen = (t.next_open - t.timestamp).total_seconds()
    #        print("market closed. Sleep for ", int(tillopen)-60, " seconds")
    #        time.sleep(int(tillopen))
    


if __name__ == "__main__":

    #print(optimize())
    #print(optimizeGen())
    start()
    



"""
base_url = cred['endpoint']
api_key_id = cred['key']
api_secret = cred['secret']
mailgun = cred['mailgun']
mailgunURL = cred['URL']
email = cred['email']
#Connecte to Alpaca Trade API
api = tradeapi.REST(
    base_url=base_url,
    key_id=api_key_id,
    secret_key=api_secret
)
session = requests.session()
def run(tickers, period):
       
    # stream connection
    conn = tradeapi.StreamConn(base_url=base_url, key_id=api_key_id, secret_key=api_secret)
    # Update initial state with information from tickers
    
    symbols = tickers
    #get historical minute data to populate df.
    minHist = getHistorical(symbols, period)
    print('running')
    
    
    #@conn.on('trade_update')
    #async def handle_trade_update(conn, channel, data):
    #    print("handle portfolio changes if live trading")
    # Second-based data.
    @conn.on('A.*')
    async def handle_second_bar(conn, channel, data):
        symbol = data.symbol
        
        if(not api.get_clock().is_open):
            symbols.remove(symbol)
            if len(symbols) <= 0:
                conn.close()
                start()
            conn.deregister([
            'AM.{}'.format(symbol),
            'A.{}'.format(symbol)])
        
    
    # Minute-based data.
    @conn.on('AM.*')
    async def handle_minute_bar(conn, channel, data):
        ts = data.start
   
    #If live trading, make sure to add 'trade_updates' to the beginning of channels
    #and implement the 'trade_updates' websocket.
    channels = []
    for s in symbols:
        print(s.ticker)
        symbol_channels = ['A.{}'.format(s.ticker), 'AM.{}'.format(s.ticker)]
        channels += symbol_channels
    print("watching {} symbols".format(len(symbols)))
    print(channels)
    run_ws(conn, channels)
def tickers(period):
    # return stocks symbols with volume above 
    ticks = api.polygon.all_tickers()
    # If you want tradable assets, get api.list_assets() and filter the ones that are .tradable
    # Since I'm not trading and making an indicator, I won't be needing this
    #Given how much volume you want in a period, make sure the stock can see 10 periods in a day. 
    return [t for t in tick if (t.prevDay['v'] > 10*period)]
"""