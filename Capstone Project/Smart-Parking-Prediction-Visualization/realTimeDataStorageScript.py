import requests as rq
import time
import json
import pandas as pd
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

#setup Gdrive authentication
gauth = GoogleAuth()
gauth.GetFlow()
gauth.flow.params.update({'access_type': 'offline'})
gauth.flow.params.update({'approval_prompt': 'force'})
gauth.LocalWebserverAuth()

drive = GoogleDrive(gauth)


#Function that calls the API and saves it in a json file. Name of the json file contains timestamp of pull time.
def callAPI():
  timestr = time.strftime("%Y_%m_%d-%H_%M_%S")
  try:
    response = rq.get("https://data.melbourne.vic.gov.au/resource/vh2v-4nfs.json?$limit=5000")
  except requests.exceptions.ConnectionError:
    response = '"empty": {}'
    pass
    #r.status_code = "Connection Refused"
  responseDataDf = pd.read_json(response.text)
  with open('//home/moha6885/capstone/datasets/APIData/'+str(timestr)+'_data.csv', 'w') as writefile:
    responseDataDf.to_csv(writefile)   #write to local file
    csv = responseDataDf.to_csv()     #convert into csv and assign
    file1 = drive.CreateFile({'title': str(timestr)+'_data.csv','parents':[{'id':['1vk9b56J5MOY95AlzbEbaDOzXYjhRpy_l']}]})
    file1.SetContentString(csv)
    file1.Upload()
    time.sleep(300)

while True:
  callAPI()

