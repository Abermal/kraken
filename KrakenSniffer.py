import pandas as pd
import numpy as np
import requests
import datetime
import os
import time
import uuid

import KrakenInterface as kI

from IPython.display import display_javascript, display_html, display
import json


if __name__ == '__main__':

    sym  = 'ETH'
    cSym = 'USD'

    i_max     =  1000000
    count     =  19
    limit     =  10
    aggregate =  5


    featureStr = kI.featuresString(count=count, limit=limit)

    oldState = kI.getState(symbol=sym, comparison_symbol=cSym, count=count, limit=limit, aggregate=aggregate)
    obStates = np.array([oldState])
    print(obStates.shape)

    for i in range(i_max):

        try:
            newState = kI.getState(symbol=sym, comparison_symbol=cSym, count=count, limit=limit, aggregate=aggregate)

        except Exception as e:
            print(e)
        else:
            if not np.array_equal(newState[1:], oldState[1:]):

                coppyOfStates = obStates                
                obStates = np.append(coppyOfStates, [newState.T], axis=0)
                oldState = newState
                
            if i%100==0:
                data = pd.DataFrame(obStates[:,1:], index=obStates[:,0], columns=featureStr)
                data.to_csv('KrakenValues_{}_LongTerm.csv'.format(count))
                print(i)
                print(obStates.shape)
