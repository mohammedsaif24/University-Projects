import folium
import requests
from flask import Flask, render_template , redirect
import time
import json
import pandas as pd
from custom_modules import callAPI,bayLocations,realTimeExtractProcessPred, realTimeExtractProcessPred2

# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
app = Flask(__name__)


# source https://pengoox.pythonanywhere.com/blog/How_to_Add_Maps_to_Flask_Web_App_with_Mapbox/
@app.route('/', methods=['GET', 'POST'])
def my_maps():
    mapbox_access_token = 'pk.eyJ1Ijoic2hhd2FybWEyNCIsImEiOiJja2tvcGMzeGwwM2c0MnVxdGR5Z3dsYzk3In0.bvcWPuF0JhlkCt0DsYLHlg'
    responseData = callAPI()  #Download realtime data from API into dataframe
    #responseData = pd.read_json(responseData)
    statusList = responseData['status'].values.tolist()  #convert dataframe into lists
    latitudeList = responseData['lat'].values.tolist()  #convert dataframe into lists
    longitudeList = responseData['lon'].values.tolist()  #convert dataframe into lists
    descriptionList = responseData['Description'].values.tolist()  #convert dataframe into lists
    #bayLocationDf = bayLocations()
    bayLocationDf = realTimeExtractProcessPred()  #Dataframe that is formed by combining recent extracts and has predicted values
    bayLocationLongitudeList = bayLocationDf['Long'].values.tolist()  #convert to list
    bayLocationLatitudeList = bayLocationDf['Lat'].values.tolist()  #convert to list
    bayLocationStatusList = bayLocationDf['Status'].values.tolist()  #convert to list
    nonSensorLocations = bayLocations()   #all bay locations without sensors
    nonSensorLocationLongitudeList = nonSensorLocations['Long'].values.tolist()
    nonSensorLocationLatitudeList = nonSensorLocations['Lat'].values.tolist()
    #Sending variable values to front end
    return render_template('index_Combined.html',
                           mapbox_access_token=mapbox_access_token,
                           statusList=statusList,
                           latitudeList=latitudeList,
                           longitudeList=longitudeList,
                           bayLocationLongitudeList=bayLocationLongitudeList,
                           bayLocationLatitudeList=bayLocationLatitudeList,
                           descriptionList=descriptionList,
                           bayLocationStatusList=bayLocationStatusList,
                           nonSensorLocationLongitudeList=nonSensorLocationLongitudeList,
                           nonSensorLocationLatitudeList=nonSensorLocationLatitudeList
                           )





# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # print_hi('PyCharm')
    app.run(debug=True)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
