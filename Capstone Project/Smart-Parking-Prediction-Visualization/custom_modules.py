import requests
import numpy as np
import re
from flask import Flask, render_template, redirect
import time
import json
import pandas as pd
from geopy.geocoders import Nominatim
from weather_au import api
import warnings
import folium
import pickle
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

warnings.filterwarnings('ignore')


# Function that calls the API and saves it in a json file. Name of the json file contains timestamp of pull time.
def callAPI():
    timestr = time.strftime("%Y_%m_%d-%H:%M:%S")
    try:
        response = requests.get("https://data.melbourne.vic.gov.au/resource/vh2v-4nfs.json?$limit=5000")
    except requests.exceptions.ConnectionError:
        response = ''
        pass
        # r.status_code = "Connection Refused"
    responseData = pd.read_json(response.text) #storing response data
    bayRestrictionsDf = pd.read_csv("otherFiles/bayRestrictionsConsolidated.csv") #reading restriction data from CSV file
    bayRestrictionsDf = bayRestrictionsDf.astype(str).groupby('BayID').agg('\n'.join).reset_index() #combining multiple row restriction info to 1 row
    bayRestrictionsDf[["BayID"]] = bayRestrictionsDf[["BayID"]].apply(pd.to_numeric)
    bayRestrictionsDf['Description'] = bayRestrictionsDf[['Description', 'DisabilityExt', 'Duration', 'Exemption']].stack().groupby(level=0).agg('|'.join) #Taking relevant columns only
    responseData = pd.merge(left=responseData, right=bayRestrictionsDf, how='left', left_on='bay_id',
                             right_on='BayID') #getting restriction info for bays that were reported by realtime api
    bayRestrictionsDf.to_csv('otherFiles/out.csv', index=False) #for testing purposes
    #responseData = responseData.drop(["location", ":@computed_region_evbi_jbp8", "st_marker_id", "bay_id"], axis=1)
    return responseData


def bayLocations():
    bayLocationDf = pd.read_csv("otherFiles/bl_df_2.csv")
    #print("bays with sensors")
    #bayLocationDf2 = bayLocationDf[(bayLocationDf['Sensor'] == 1)]
    #print(bayLocationDf2)
    #Filtering only those bays that do not have in ground sensors
    bayLocationDf = bayLocationDf[(bayLocationDf['Lat'] >= -37.8066) & (bayLocationDf['Lat'] <= -37.792085) &
                    (bayLocationDf['Long'] > 0.065 + 1.449e2) & (bayLocationDf['Long'] < 0.08 + 1.449e2) & (bayLocationDf['Sensor'] == 0)]
    return bayLocationDf

#test function, not used in main.oy
def bayRestrictions():
    bayLocationDf = pd.read_csv("otherFiles/bl_df_2.csv")
    bayRestrictionsDf = pd.read_csv("otherFiles/bayRestrictionsConsolidated.csv")
    bayLocationDf = pd.merge(left=bayLocationDf, right=bayRestrictionsDf, how='right', left_on='BayId', right_on='BayID')
    bayLocationDf.to_csv('otherFiles/out.csv', index=False)
    return bayLocationDf

#Function that extracts recent real time data and makes prediction
def realTimeExtractProcessPred():
    # setup Gdrive authentication
    gauth = GoogleAuth()
    gauth.GetFlow()
    gauth.flow.params.update({'access_type': 'offline'})
    gauth.flow.params.update({'approval_prompt': 'force'})
    gauth.LocalWebserverAuth()

    drive = GoogleDrive(gauth)

    # use file id of the folder from Gdrive  1vk9b56J5MOY95AlzbEbaDOzXYjhRpy_l

    file_list = drive.ListFile(
        {'q': "'1vk9b56J5MOY95AlzbEbaDOzXYjhRpy_l' in parents and trashed=false", 'maxResults': 5}).GetList()
    for file1 in file_list:  #list the names of the files in the directory
        print('title: %s, id: %s' % (file1['title'], file1['id']))
        driveFile = drive.CreateFile({'id': file1['id']})
        driveFile.GetContentFile('ml_models/datasets/realtime/' + file1['title'])

    path = 'ml_models/datasets/realtime/'

    def csvtodf(file, path=path):
        filename = path + file

        df = pd.read_csv(filename, thousands=',')
        return df

    from os import listdir
    from os.path import isfile, join

    files = [f for f in listdir(path) if isfile(join(path, f))]  # list of files in the directory
    files.reverse()
    files = files[0:5]

    last_file_flag = 1
    df = ''

    for f in files:
        if f[-3:] == 'csv':
            if last_file_flag == 1:
                datetime_raw = f[:-9]
                print(datetime_raw)

                temp_df = csvtodf(f, path + '/')

                temp_df = temp_df[['bay_id', 'status']]
                temp_df['DatetimeRaw'] = pd.to_datetime(datetime_raw, format='%Y_%m_%d-%H_%M_%S')
                temp_df['Datetime'] = temp_df['DatetimeRaw'].dt.floor("15min")

                if len(df) == 0:
                    df = temp_df
                else:
                    df = pd.concat([df, temp_df])

    df = df.rename(columns={'bay_id': 'BayId', 'status': 'Status'})

    df['Status'] = np.where(df['Status'] == 'Present', 1, 0)

    df = df[['BayId', 'Datetime', 'Status']].groupby(by=['BayId', 'Datetime']).sum().reset_index()

    df['Status'] = np.where(df['Status'] >= 1, 1, 0)

    ts_df = df.copy(deep=True)

    ts_df['Date'] = ts_df['Datetime'].dt.date
    ts_df['Time'] = ts_df['Datetime'].dt.time
    ts_df['Year'] = ts_df['Datetime'].dt.year
    ts_df['Month'] = ts_df['Datetime'].dt.month
    ts_df['Day'] = ts_df['Datetime'].dt.day
    ts_df['DayOfWeek'] = ts_df['Datetime'].dt.dayofweek
    ts_df['Hour'] = ts_df['Datetime'].dt.hour
    ts_df['Minute'] = ts_df['Datetime'].dt.minute  # combined past real time data in ts_df

    path = 'ml_models/datasets'

    ph_df = csvtodf('/Australian Public Holidays.csv', path=path)

    ph_df = ph_df[ph_df['Jurisdiction'] == 'vic']

    ph_df['Date'] = pd.to_datetime(ph_df['Date'], format='%Y%m%d')
    ph_df['Date'] = ph_df['Date'].dt.date

    ph_df.head()  # ph_df public holidays of victoria

    # Check if date is public holiday

    print('Checking if date is public holiday.')

    ts_df = ts_df.assign(PublicHoliday=ts_df.Date.isin(ph_df['Date']).astype(int))

    ts_df['PublicHoliday'].value_counts()

    # Import Bay Restrictions dataset

    br_df = csvtodf('/br_df_2.csv', path=path)

    br_df.head()

    # Import Bay Locations dataset

    bl_df = csvtodf('/bl_df_2.csv', path=path)

    br_df['StartTime'] = pd.to_datetime(br_df['StartTime'], format='%H:%M:%S').dt.time
    br_df['EndTime'] = pd.to_datetime(br_df['EndTime'], format='%H:%M:%S').dt.time

    df_intersection = pd.merge(ts_df, br_df, how='inner', left_on='BayId', right_on='BayID')
    df_intersection = df_intersection[(df_intersection['DayOfWeek'] >= df_intersection['FromDay']) & (
            df_intersection['DayOfWeek'] <= df_intersection['ToDay']) & \
                                      (df_intersection['Time'] >= df_intersection['StartTime']) & (
                                              df_intersection['Time'] < df_intersection['EndTime']) & \
                                      ((df_intersection['PublicHoliday'] == 0) | (
                                                  df_intersection['PublicHoliday'] == 1) & (
                                               df_intersection['EffectiveOnPH'] == 1))]

    df = pd.merge(ts_df, df_intersection, how='left', left_on=list(ts_df.columns), right_on=list(ts_df.columns))

    df = pd.merge(df, bl_df[['BayId', 'RoadSegmentCode', 'Lat', 'Long']], how='left', left_on='BayId', right_on='BayId')

    df['Lat'] = df['Lat'].round(decimals=6)
    df['Long'] = df['Long'].round(decimals=6)

    df = df.drop_duplicates()

    df = df.fillna(0)

    df['DisabilityExt'] = df['DisabilityExt'].astype('int')
    df['Duration'] = df['Duration'].astype('int')
    df['DisabledOnly'] = df['DisabledOnly'].astype('int')
    df['Metered'] = df['Metered'].astype('int')
    df['LoadingZone'] = df['LoadingZone'].astype('int')
    df['Clearway'] = df['Clearway'].astype('int')
    df['NoParking'] = df['NoParking'].astype('int')
    df['NoStopping'] = df['NoStopping'].astype('int')
    df['ResidentExempted'] = df['ResidentExempted'].astype('int')

    print('Importing weather dataset.')

    w_df = csvtodf('/w_df_2.csv', path=path)

    w_df.head()

    # Left join weather dataset to combined dataset

    df = pd.merge(df, w_df, how='left', left_on='Date', right_on='Date')

    df.head()
    # print(df.columns)
    # print(df.head())
    # print(df.shape)
    df['BayId'].nunique()

    # Filter relevant fields

    df = df[['BayId', 'Status', 'Lat', 'Long', 'Year', 'Month', 'Day', 'DayOfWeek', 'Hour', 'Minute', 'PublicHoliday',
             'RoadSegmentCode', 'DisabilityExt', 'Duration', 'DisabledOnly', 'Metered', 'LoadingZone', 'Clearway',
             'NoParking', 'NoStopping', 'ResidentExempted']]

    df.head()

    filter_list = [567, 568, 569, 570, 571, 572, 574, 576, 577, 578, 579, 581, 584, 585, 586, 590, 591, 592, 593, 594,
                   595,
                   597, 604, 605, 606, 610, 611, 612, 613, 614, 615, 616, 617, 618, 619, 621, 622, 623, 625, 626, 627,
                   628,
                   629, 630, 631, 632, 634, 635, 637, 638, 639, 641, 642, 643, 644, 645, 646, 647, 649, 650, 651, 652,
                   654,
                   656, 657, 658, 660, 661, 663, 673, 674, 676, 677, 678, 679, 680, 683, 684, 685, 686, 687, 696, 697,
                   698,
                   699, 700, 701, 702, 703, 704, 705, 706, 708, 710, 712, 716, 718, 719, 721, 723, 724, 725, 726, 727,
                   728,
                   729, 730, 732, 733, 734, 736, 738, 739, 740, 742, 743, 744, 745, 747, 748, 749, 750, 751, 752, 754,
                   756,
                   757, 758, 763, 765, 766, 768, 769, 770, 771, 772, 774, 775, 776, 790, 796, 797, 798, 799, 800, 802,
                   803,
                   805, 806, 807, 808, 809, 811, 812, 814, 815, 823, 824, 825, 826, 827, 828, 829, 830, 831, 832, 833,
                   834,
                   835, 836, 840, 842, 850, 856, 858, 862, 864, 866, 867, 868, 869, 870, 873, 874, 875, 876, 877, 878,
                   879,
                   881, 882, 885, 886, 887, 888, 909, 910, 911, 912, 913, 914, 915, 916, 917, 918, 919, 920, 927, 928,
                   930,
                   932, 934, 937, 938, 939, 940, 941, 942, 943, 944, 945, 946, 947, 948, 949, 951, 953, 955, 957, 973,
                   975,
                   977, 978, 980, 981, 982, 983, 984, 985, 986, 1005, 1006, 1007, 1011, 1012, 1013, 1014, 1015, 1017,
                   1019,
                   1022, 1024, 1027, 1028, 1029, 1030, 1031, 1032, 1033, 1034, 1035, 1036, 1038, 1039, 1040, 1041, 1058,
                   1087, 1089, 1090, 1092, 1094, 1095, 1097, 1098, 1099, 1101, 1102, 1103, 1104, 1105, 1106, 1108, 1109,
                   1110, 1111, 1112, 1114, 1115, 1118, 1119, 1120, 1121, 1122, 1123, 1124, 1125, 1129, 1130, 1132, 1133,
                   1134, 1137, 1138, 1139, 1140, 1141, 1142, 1143, 1144, 1145, 1146, 1147, 1148, 1149, 1150, 1152, 1153,
                   1154, 1155, 1156, 1157, 1158, 1159, 1160, 1162, 1163, 1175, 1177, 1178, 1179, 1180, 1181, 1182, 1184,
                   1185, 1186, 1187, 1188, 1190, 1192, 1193, 1194, 1195, 1197, 1199, 1200, 1202, 1203, 1206, 1208, 1209,
                   1210, 1211, 1212, 1213, 1214, 1215, 1216, 1218, 1219, 1220, 1222, 1223, 1224, 1226, 1227, 1229, 1230,
                   1232, 1233, 1235, 1236, 1237, 1238, 1239, 1243, 1244, 1245, 1247, 1248, 1249, 1250, 1251, 1253, 1255,
                   1256, 1257, 1258, 1259, 1260, 1261, 1262, 1263, 1264, 1265, 1266, 1268, 1270, 1272, 1273, 1274, 1276,
                   1278, 1279, 1280, 1282, 1283, 1284, 1285, 1286, 1287, 1288, 1290, 1291, 1292, 1293, 1294, 1295, 1296,
                   1297, 1298, 1304, 1305, 1306, 1307, 1309, 1310, 1316, 1318, 1332, 1334, 1337, 1338, 1340, 1341, 1342,
                   1344, 1367, 1368, 1370, 1371, 1373, 1374, 1378, 1379, 1380, 1381, 1382, 1383, 1385, 1387, 1389, 1397,
                   1398, 1400, 1407, 1410, 1411, 1414, 1419, 1433, 1434, 1435, 1437, 1439, 1440, 1441, 1442, 1444, 1445,
                   1446, 1447, 1448, 1451, 1452, 1454, 1456, 1457, 1458, 1470, 1471, 1472, 1473, 1474, 1475, 1495, 1497,
                   1501, 1503, 1504, 1505, 1510, 1511, 1512, 1514, 1519, 1520, 1521, 1526, 1528, 1530, 1533, 1534, 1535,
                   1539, 1540, 1541, 1542, 1544, 1545, 1586, 1589, 1590, 1591, 1593, 1594, 1595, 1596, 1599, 1647, 1648,
                   1654, 1655, 1657, 1658, 1659, 1672, 1674, 1679, 1680, 1681, 1682, 1683, 1684, 1685, 1686, 1688, 1689,
                   1693, 1694, 1696, 1697, 1702, 1704, 1705, 1706, 1707, 1709, 1710, 1711, 1713, 1722, 1723, 1724, 1725,
                   1728, 1729, 1730, 1732, 1733, 1734, 1735, 1736, 1737, 1738, 1739, 1740, 1741, 1744, 1745, 1746, 1748,
                   1749, 1752, 1753, 1755, 1757, 1759, 1761, 1762, 1763, 1764, 1765, 1766, 1767, 1768, 1772, 1901, 1902,
                   1904, 1905, 1920, 1921, 1941, 1942, 1943, 1944, 1945, 1946, 1949, 1950, 1951, 1952, 1954, 1955, 1957,
                   1959, 1961, 1962, 1963, 1964, 1965, 1966, 1967, 1978, 1979, 1980, 1981, 1982, 1983, 1984, 1985, 1986,
                   1987, 1989, 1990, 1991, 1992, 1993, 1995, 1996, 1997, 1998, 1999, 2004, 2005, 2006, 2007, 2008, 2009,
                   2011, 2012, 2014, 2017, 2018, 2019, 2020, 2033, 2035, 2036, 2040, 2042, 2043, 2045, 2046, 2047, 2059,
                   2060, 2061, 2062, 2063, 2071, 2073, 2098, 2099, 2100, 2128, 2129, 2130, 2131, 2143, 2146, 2147, 2153,
                   2158, 2160, 2161, 2162, 2163, 2174, 2412, 2413, 2414, 2415, 2416, 2417, 2419, 2421, 2422, 2427, 2428,
                   2429, 2430, 2431, 2432, 2433, 2434, 2435, 2436, 2437, 2438, 2439, 2440, 2441, 2442, 2443, 2444, 2445,
                   2449, 2450, 2451, 2452, 2454, 2455, 2456, 2457, 2459, 2460, 2462, 2463, 2465, 2466, 2467, 2469, 2470,
                   2471, 2472, 2473, 2474, 2477, 2480, 2481, 2483, 2484, 2490, 2492, 2494, 2495, 2496, 2497, 2499, 2501,
                   2504, 2506, 2510, 2518, 2524, 2527, 2530, 2531, 2532, 2533, 2534, 2535, 2536, 2537, 2538, 2539, 2540,
                   2541, 2542, 2543, 2544, 2545, 2547, 2548, 2549, 2553, 2554, 2555, 2556, 2557, 2558, 2559, 2560, 2562,
                   2564, 2565, 2566, 2567, 2569, 2570, 2571, 2572, 2573, 2622, 2626, 2627, 2628, 2632, 2633, 2637, 2640,
                   2641, 2644, 2645, 2646]
    df = df[df['BayId'].isin(filter_list)]

    df['DateTime'] = pd.to_datetime(
        df['Year'] * 100000000 + df['Month'] * 1000000 + df['Day'] * 10000 + df['Hour'] * 100 + df['Minute'],
        format='%Y%m%d%H%M')

    df['StatusChange'] = np.where((df['Status'] != df['Status'].shift()) & (df['BayId'] == df['BayId'].shift()), 1,
                                  np.where(df['BayId'] != df['BayId'].shift(), 1, 0))

    def custcum(x):
        total = 0
        for i, v in x.iterrows():
            if v['StatusChange'] == 1:
                total = 0
            x.loc[i, 'StatusPeriod'] = total
            total += 15
        return x

    df = df.groupby('BayId').apply(custcum)

    def custcum2(x):
        total = 0
        for i, v in x.iterrows():
            if v['Duration'] > 0:
                if v['Status'] == 1:
                    x.loc[i, 'Period'] = total
                    total += 15
                else:
                    total = 0
            else:
                total = 0
            x.loc[i, 'Period'] = total
        return x

    df = df.groupby('BayId').apply(custcum2)

    df['DurationThreshold'] = np.where(df['Duration'] > 0, df['Period'] / df['Duration'], 0)

    df['NormalOvertime'] = np.where((df['Period'] > df['Duration']) & (df['Duration'] > 0), 1, 0)

    occupied_df = df[df['Status'] == 1].groupby(by=['RoadSegmentCode', 'DateTime'], as_index=False).count()
    occupied_df.rename(columns={'BayId': 'TotalOccupied'}, inplace=True)
    occupied_df = occupied_df[['RoadSegmentCode', 'DateTime', 'TotalOccupied']]

    df = pd.merge(df, occupied_df, how='left', on=['DateTime', 'RoadSegmentCode'])

    total_df = df.groupby(by=['RoadSegmentCode', 'DateTime'], as_index=False).count()
    total_df.rename(columns={'BayId': 'TotalBays'}, inplace=True)
    total_df = total_df[['RoadSegmentCode', 'DateTime', 'TotalBays']]

    df = pd.merge(df, total_df, how='left', on=['DateTime', 'RoadSegmentCode'])

    df['OccupancyRate'] = df['TotalOccupied'] / df['TotalBays']

    df['PrevOccupancyRate'] = df['OccupancyRate'].shift()
    df['PrevOccupancyRate'] = np.where(df['PrevOccupancyRate'].isna(), df['OccupancyRate'], df['PrevOccupancyRate'])

    df['RestrictionEffective'] = np.where(df['Duration'] > 0, 1, 0)

    df['PrevDurationThreshold'] = df['DurationThreshold'].shift()
    df['PrevDurationThreshold'] = np.where(df['PrevDurationThreshold'].isna(), df['DurationThreshold'],
                                           df['PrevDurationThreshold'])

    df['PrevOvertime'] = df['NormalOvertime'].shift()
    df['PrevOvertime'] = np.where(df['PrevOvertime'].isna(), df['NormalOvertime'], df['PrevOvertime'])

    # df['Rainfall'] = np.where(df['Rainfall'].isna(), 0, df['Rainfall'])
    # df['AvgTemp'] = np.where(df['AvgTemp'].isna(), 0, df['AvgTemp'])

    df = df[['BayId', 'Status', 'Year', 'Month', 'Day', 'DayOfWeek',
             'Hour', 'Minute', 'RoadSegmentCode', 'Metered',
             'PrevDurationThreshold', 'PrevOvertime', 'PrevOccupancyRate',
             # 'Rainfall', 'AvgTemp',
             'DateTime', 'Period', 'TotalOccupied', 'TotalBays', 'OccupancyRate', 'DurationThreshold']]

    df['PrevOvertime'] = df['PrevOvertime'].astype(int)

    # Get latest time for each bay

    latest_df = df[['BayId', 'DateTime']].groupby(by='BayId').max()

    df = pd.merge(df, latest_df, how='right', on=['BayId', 'DateTime'])

    df = pd.DataFrame(df, columns=['BayId', 'Day', 'DayOfWeek', 'Hour', 'Minute',
                                   'RoadSegmentCode', 'Metered', 'PrevDurationThreshold', 'PrevOvertime',
                                   'PrevOccupancyRate'])

    def getpostcode(lat_lon):
        geolocator = Nominatim(user_agent="http")
        location = geolocator.reverse(lat_lon)
        address = location.address
        postcode = re.split("[/,]", address)[-2].strip().lower()
        return postcode

    def callAPI2():
        url = "https://data.melbourne.vic.gov.au/resource/vh2v-4nfs.csv"
        obs_df = pd.read_csv(url)
        # obs_df = obs_df.loc[:20,]
        postcodes, temperatures, prcp = [], [], []
        for i in range(len(obs_df)):
            postcode = getpostcode(str(obs_df['lat'][i]) + ',' + str(obs_df['lon'][i]))
            w = api.WeatherApi(search=postcode, debug=0)
            temperature = w.observations()['temp']
            try:
                rain_amount = (w.forecast_rain()['amount']['min'] + w.forecast_rain()['amount']['max']) / 2
            except:
                rain_amount = 0
            temperatures.append(temperature)
            prcp.append(rain_amount)
        obs_df['AvgTemp'] = temperatures
        obs_df['Rainfall'] = prcp
        obs_df.drop(['location', 'st_marker_id', 'lat', 'lon', 'location', 'status'], axis='columns', inplace=True)
        obs_df = obs_df.rename(columns={'bay_id': 'BayId'})
        return obs_df

    obs_df = callAPI2()
    filter_list = [567, 568, 569, 570, 571, 572, 574, 576, 577, 578, 579, 581, 584, 585, 586, 590, 591, 592, 593, 594,
                   595,
                   597, 604, 605, 606, 610, 611, 612, 613, 614, 615, 616, 617, 618, 619, 621, 622, 623, 625, 626, 627,
                   628,
                   629, 630, 631, 632, 634, 635, 637, 638, 639, 641, 642, 643, 644, 645, 646, 647, 649, 650, 651, 652,
                   654,
                   656, 657, 658, 660, 661, 663, 673, 674, 676, 677, 678, 679, 680, 683, 684, 685, 686, 687, 696, 697,
                   698,
                   699, 700, 701, 702, 703, 704, 705, 706, 708, 710, 712, 716, 718, 719, 721, 723, 724, 725, 726, 727,
                   728,
                   729, 730, 732, 733, 734, 736, 738, 739, 740, 742, 743, 744, 745, 747, 748, 749, 750, 751, 752, 754,
                   756,
                   757, 758, 763, 765, 766, 768, 769, 770, 771, 772, 774, 775, 776, 790, 796, 797, 798, 799, 800, 802,
                   803,
                   805, 806, 807, 808, 809, 811, 812, 814, 815, 823, 824, 825, 826, 827, 828, 829, 830, 831, 832, 833,
                   834,
                   835, 836, 840, 842, 850, 856, 858, 862, 864, 866, 867, 868, 869, 870, 873, 874, 875, 876, 877, 878,
                   879,
                   881, 882, 885, 886, 887, 888, 909, 910, 911, 912, 913, 914, 915, 916, 917, 918, 919, 920, 927, 928,
                   930,
                   932, 934, 937, 938, 939, 940, 941, 942, 943, 944, 945, 946, 947, 948, 949, 951, 953, 955, 957, 973,
                   975,
                   977, 978, 980, 981, 982, 983, 984, 985, 986, 1005, 1006, 1007, 1011, 1012, 1013, 1014, 1015, 1017,
                   1019,
                   1022, 1024, 1027, 1028, 1029, 1030, 1031, 1032, 1033, 1034, 1035, 1036, 1038, 1039, 1040, 1041, 1058,
                   1087, 1089, 1090, 1092, 1094, 1095, 1097, 1098, 1099, 1101, 1102, 1103, 1104, 1105, 1106, 1108, 1109,
                   1110, 1111, 1112, 1114, 1115, 1118, 1119, 1120, 1121, 1122, 1123, 1124, 1125, 1129, 1130, 1132, 1133,
                   1134, 1137, 1138, 1139, 1140, 1141, 1142, 1143, 1144, 1145, 1146, 1147, 1148, 1149, 1150, 1152, 1153,
                   1154, 1155, 1156, 1157, 1158, 1159, 1160, 1162, 1163, 1175, 1177, 1178, 1179, 1180, 1181, 1182, 1184,
                   1185, 1186, 1187, 1188, 1190, 1192, 1193, 1194, 1195, 1197, 1199, 1200, 1202, 1203, 1206, 1208, 1209,
                   1210, 1211, 1212, 1213, 1214, 1215, 1216, 1218, 1219, 1220, 1222, 1223, 1224, 1226, 1227, 1229, 1230,
                   1232, 1233, 1235, 1236, 1237, 1238, 1239, 1243, 1244, 1245, 1247, 1248, 1249, 1250, 1251, 1253, 1255,
                   1256, 1257, 1258, 1259, 1260, 1261, 1262, 1263, 1264, 1265, 1266, 1268, 1270, 1272, 1273, 1274, 1276,
                   1278, 1279, 1280, 1282, 1283, 1284, 1285, 1286, 1287, 1288, 1290, 1291, 1292, 1293, 1294, 1295, 1296,
                   1297, 1298, 1304, 1305, 1306, 1307, 1309, 1310, 1316, 1318, 1332, 1334, 1337, 1338, 1340, 1341, 1342,
                   1344, 1367, 1368, 1370, 1371, 1373, 1374, 1378, 1379, 1380, 1381, 1382, 1383, 1385, 1387, 1389, 1397,
                   1398, 1400, 1407, 1410, 1411, 1414, 1419, 1433, 1434, 1435, 1437, 1439, 1440, 1441, 1442, 1444, 1445,
                   1446, 1447, 1448, 1451, 1452, 1454, 1456, 1457, 1458, 1470, 1471, 1472, 1473, 1474, 1475, 1495, 1497,
                   1501, 1503, 1504, 1505, 1510, 1511, 1512, 1514, 1519, 1520, 1521, 1526, 1528, 1530, 1533, 1534, 1535,
                   1539, 1540, 1541, 1542, 1544, 1545, 1586, 1589, 1590, 1591, 1593, 1594, 1595, 1596, 1599, 1647, 1648,
                   1654, 1655, 1657, 1658, 1659, 1672, 1674, 1679, 1680, 1681, 1682, 1683, 1684, 1685, 1686, 1688, 1689,
                   1693, 1694, 1696, 1697, 1702, 1704, 1705, 1706, 1707, 1709, 1710, 1711, 1713, 1722, 1723, 1724, 1725,
                   1728, 1729, 1730, 1732, 1733, 1734, 1735, 1736, 1737, 1738, 1739, 1740, 1741, 1744, 1745, 1746, 1748,
                   1749, 1752, 1753, 1755, 1757, 1759, 1761, 1762, 1763, 1764, 1765, 1766, 1767, 1768, 1772, 1901, 1902,
                   1904, 1905, 1920, 1921, 1941, 1942, 1943, 1944, 1945, 1946, 1949, 1950, 1951, 1952, 1954, 1955, 1957,
                   1959, 1961, 1962, 1963, 1964, 1965, 1966, 1967, 1978, 1979, 1980, 1981, 1982, 1983, 1984, 1985, 1986,
                   1987, 1989, 1990, 1991, 1992, 1993, 1995, 1996, 1997, 1998, 1999, 2004, 2005, 2006, 2007, 2008, 2009,
                   2011, 2012, 2014, 2017, 2018, 2019, 2020, 2033, 2035, 2036, 2040, 2042, 2043, 2045, 2046, 2047, 2059,
                   2060, 2061, 2062, 2063, 2071, 2073, 2098, 2099, 2100, 2128, 2129, 2130, 2131, 2143, 2146, 2147, 2153,
                   2158, 2160, 2161, 2162, 2163, 2174, 2412, 2413, 2414, 2415, 2416, 2417, 2419, 2421, 2422, 2427, 2428,
                   2429, 2430, 2431, 2432, 2433, 2434, 2435, 2436, 2437, 2438, 2439, 2440, 2441, 2442, 2443, 2444, 2445,
                   2449, 2450, 2451, 2452, 2454, 2455, 2456, 2457, 2459, 2460, 2462, 2463, 2465, 2466, 2467, 2469, 2470,
                   2471, 2472, 2473, 2474, 2477, 2480, 2481, 2483, 2484, 2490, 2492, 2494, 2495, 2496, 2497, 2499, 2501,
                   2504, 2506, 2510, 2518, 2524, 2527, 2530, 2531, 2532, 2533, 2534, 2535, 2536, 2537, 2538, 2539, 2540,
                   2541, 2542, 2543, 2544, 2545, 2547, 2548, 2549, 2553, 2554, 2555, 2556, 2557, 2558, 2559, 2560, 2562,
                   2564, 2565, 2566, 2567, 2569, 2570, 2571, 2572, 2573, 2622, 2626, 2627, 2628, 2632, 2633, 2637, 2640,
                   2641, 2644, 2645, 2646]
    obs_df = obs_df[obs_df['BayId'].isin(filter_list)]

    observation_bayid_list = list(obs_df['BayId'].unique())

    df = df[df['BayId'].isin(observation_bayid_list)]

    df_final = pd.merge(obs_df, df, how='left', on='BayId')

    print(df_final)
    df_final.to_csv("ml_models/datasets/realtime/combined/features_df.csv")
    df_final = df_final.dropna()
    # df_final = df_final.drop(df_final.columns[0], axis=1)

    # replacement code
    replace_map_comp = {
        'BayId': {567.0: 0, 568.0: 1, 569.0: 2, 570.0: 3, 571.0: 4, 572.0: 5, 574.0: 6, 576.0: 7, 577.0: 8, 578.0: 9,
                  579.0: 10, 581.0: 11, 584.0: 12, 585.0: 13, 586.0: 14, 590.0: 15, 591.0: 16, 592.0: 17, 593.0: 18,
                  594.0: 19, 595.0: 20, 597.0: 21, 604.0: 22, 605.0: 23, 606.0: 24, 610.0: 25, 611.0: 26, 612.0: 27,
                  614.0: 28, 615.0: 29, 616.0: 30, 617.0: 31, 618.0: 32, 619.0: 33, 621.0: 34, 622.0: 35, 623.0: 36,
                  625.0: 37, 626.0: 38, 627.0: 39, 628.0: 40, 629.0: 41, 630.0: 42, 631.0: 43, 632.0: 44, 634.0: 45,
                  635.0: 46, 637.0: 47, 638.0: 48, 639.0: 49, 641.0: 50, 642.0: 51, 643.0: 52, 644.0: 53, 645.0: 54,
                  646.0: 55, 647.0: 56, 649.0: 57, 650.0: 58, 651.0: 59, 652.0: 60, 654.0: 61, 656.0: 62, 657.0: 63,
                  658.0: 64, 660.0: 65, 661.0: 66, 663.0: 67, 673.0: 68, 674.0: 69, 676.0: 70, 677.0: 71, 678.0: 72,
                  679.0: 73, 680.0: 74, 683.0: 75, 684.0: 76, 685.0: 77, 686.0: 78, 687.0: 79, 696.0: 80, 697.0: 81,
                  698.0: 82, 699.0: 83, 700.0: 84, 701.0: 85, 702.0: 86, 703.0: 87, 704.0: 88, 705.0: 89, 706.0: 90,
                  708.0: 91, 710.0: 92, 712.0: 93, 716.0: 94, 718.0: 95, 719.0: 96, 721.0: 97, 723.0: 98, 724.0: 99,
                  725.0: 100, 726.0: 101, 727.0: 102, 728.0: 103, 729.0: 104, 730.0: 105, 732.0: 106, 733.0: 107,
                  734.0: 108, 736.0: 109, 738.0: 110, 739.0: 111, 740.0: 112, 742.0: 113, 743.0: 114, 744.0: 115,
                  745.0: 116, 747.0: 117, 748.0: 118, 749.0: 119, 750.0: 120, 751.0: 121, 752.0: 122, 754.0: 123,
                  756.0: 124, 757.0: 125, 758.0: 126, 763.0: 127, 765.0: 128, 766.0: 129, 768.0: 130, 769.0: 131,
                  770.0: 132, 771.0: 133, 772.0: 134, 774.0: 135, 775.0: 136, 776.0: 137, 790.0: 138, 796.0: 139,
                  797.0: 140, 798.0: 141, 799.0: 142, 800.0: 143, 802.0: 144, 803.0: 145, 805.0: 146, 806.0: 147,
                  807.0: 148, 808.0: 149, 809.0: 150, 811.0: 151, 812.0: 152, 814.0: 153, 815.0: 154, 823.0: 155,
                  824.0: 156, 825.0: 157, 826.0: 158, 827.0: 159, 828.0: 160, 829.0: 161, 830.0: 162, 831.0: 163,
                  832.0: 164, 833.0: 165, 834.0: 166, 835.0: 167, 836.0: 168, 840.0: 169, 842.0: 170, 850.0: 171,
                  856.0: 172, 858.0: 173, 862.0: 174, 864.0: 175, 866.0: 176, 867.0: 177, 868.0: 178, 869.0: 179,
                  870.0: 180, 873.0: 181, 874.0: 182, 875.0: 183, 876.0: 184, 877.0: 185, 878.0: 186, 879.0: 187,
                  881.0: 188, 882.0: 189, 885.0: 190, 886.0: 191, 887.0: 192, 888.0: 193, 909.0: 194, 910.0: 195,
                  911.0: 196, 912.0: 197, 913.0: 198, 914.0: 199, 915.0: 200, 916.0: 201, 917.0: 202, 918.0: 203,
                  919.0: 204, 920.0: 205, 927.0: 206, 928.0: 207, 930.0: 208, 932.0: 209, 934.0: 210, 937.0: 211,
                  938.0: 212, 939.0: 213, 940.0: 214, 941.0: 215, 942.0: 216, 943.0: 217, 944.0: 218, 945.0: 219,
                  946.0: 220, 947.0: 221, 948.0: 222, 949.0: 223, 951.0: 224, 953.0: 225, 955.0: 226, 957.0: 227,
                  973.0: 228, 975.0: 229, 977.0: 230, 978.0: 231, 980.0: 232, 981.0: 233, 982.0: 234, 983.0: 235,
                  984.0: 236, 985.0: 237, 986.0: 238, 1005.0: 239, 1006.0: 240, 1007.0: 241, 1011.0: 242, 1012.0: 243,
                  1013.0: 244, 1015.0: 245, 1019.0: 246, 1022.0: 247, 1024.0: 248, 1027.0: 249, 1028.0: 250,
                  1029.0: 251, 1030.0: 252, 1031.0: 253, 1032.0: 254, 1033.0: 255, 1034.0: 256, 1035.0: 257,
                  1036.0: 258, 1038.0: 259, 1039.0: 260, 1040.0: 261, 1041.0: 262, 1058.0: 263, 1087.0: 264,
                  1089.0: 265, 1090.0: 266, 1092.0: 267, 1094.0: 268, 1095.0: 269, 1097.0: 270, 1098.0: 271,
                  1099.0: 272, 1101.0: 273, 1102.0: 274, 1103.0: 275, 1104.0: 276, 1105.0: 277, 1106.0: 278,
                  1108.0: 279, 1109.0: 280, 1110.0: 281, 1111.0: 282, 1112.0: 283, 1114.0: 284, 1115.0: 285,
                  1118.0: 286, 1119.0: 287, 1120.0: 288, 1121.0: 289, 1122.0: 290, 1123.0: 291, 1124.0: 292,
                  1125.0: 293, 1129.0: 294, 1130.0: 295, 1132.0: 296, 1133.0: 297, 1134.0: 298, 1137.0: 299,
                  1138.0: 300, 1139.0: 301, 1140.0: 302, 1141.0: 303, 1142.0: 304, 1143.0: 305, 1144.0: 306,
                  1145.0: 307, 1146.0: 308, 1147.0: 309, 1148.0: 310, 1149.0: 311, 1150.0: 312, 1152.0: 313,
                  1153.0: 314, 1154.0: 315, 1155.0: 316, 1156.0: 317, 1157.0: 318, 1158.0: 319, 1159.0: 320,
                  1160.0: 321, 1162.0: 322, 1163.0: 323, 1175.0: 324, 1177.0: 325, 1178.0: 326, 1179.0: 327,
                  1180.0: 328, 1181.0: 329, 1182.0: 330, 1184.0: 331, 1185.0: 332, 1186.0: 333, 1187.0: 334,
                  1188.0: 335, 1190.0: 336, 1192.0: 337, 1193.0: 338, 1194.0: 339, 1195.0: 340, 1197.0: 341,
                  1199.0: 342, 1200.0: 343, 1202.0: 344, 1203.0: 345, 1206.0: 346, 1208.0: 347, 1209.0: 348,
                  1210.0: 349, 1211.0: 350, 1212.0: 351, 1213.0: 352, 1214.0: 353, 1215.0: 354, 1216.0: 355,
                  1218.0: 356, 1219.0: 357, 1220.0: 358, 1222.0: 359, 1223.0: 360, 1224.0: 361, 1226.0: 362,
                  1227.0: 363, 1229.0: 364, 1230.0: 365, 1232.0: 366, 1233.0: 367, 1235.0: 368, 1236.0: 369,
                  1237.0: 370, 1238.0: 371, 1239.0: 372, 1243.0: 373, 1244.0: 374, 1245.0: 375, 1247.0: 376,
                  1248.0: 377, 1249.0: 378, 1250.0: 379, 1251.0: 380, 1253.0: 381, 1255.0: 382, 1256.0: 383,
                  1257.0: 384, 1258.0: 385, 1259.0: 386, 1260.0: 387, 1261.0: 388, 1262.0: 389, 1263.0: 390,
                  1264.0: 391, 1265.0: 392, 1266.0: 393, 1268.0: 394, 1270.0: 395, 1272.0: 396, 1273.0: 397,
                  1274.0: 398, 1276.0: 399, 1278.0: 400, 1279.0: 401, 1280.0: 402, 1282.0: 403, 1283.0: 404,
                  1284.0: 405, 1285.0: 406, 1286.0: 407, 1287.0: 408, 1288.0: 409, 1290.0: 410, 1291.0: 411,
                  1292.0: 412, 1293.0: 413, 1294.0: 414, 1295.0: 415, 1296.0: 416, 1297.0: 417, 1298.0: 418,
                  1304.0: 419, 1305.0: 420, 1306.0: 421, 1307.0: 422, 1316.0: 423, 1318.0: 424, 1332.0: 425,
                  1334.0: 426, 1337.0: 427, 1338.0: 428, 1340.0: 429, 1341.0: 430, 1342.0: 431, 1344.0: 432,
                  1367.0: 433, 1368.0: 434, 1370.0: 435, 1371.0: 436, 1374.0: 437, 1378.0: 438, 1379.0: 439,
                  1380.0: 440, 1381.0: 441, 1382.0: 442, 1383.0: 443, 1385.0: 444, 1387.0: 445, 1389.0: 446,
                  1397.0: 447, 1398.0: 448, 1400.0: 449, 1407.0: 450, 1410.0: 451, 1411.0: 452, 1414.0: 453,
                  1419.0: 454, 1433.0: 455, 1434.0: 456, 1435.0: 457, 1437.0: 458, 1439.0: 459, 1440.0: 460,
                  1441.0: 461, 1442.0: 462, 1444.0: 463, 1445.0: 464, 1446.0: 465, 1447.0: 466, 1448.0: 467,
                  1451.0: 468, 1452.0: 469, 1454.0: 470, 1456.0: 471, 1457.0: 472, 1458.0: 473, 1470.0: 474,
                  1471.0: 475, 1472.0: 476, 1473.0: 477, 1474.0: 478, 1475.0: 479, 1495.0: 480, 1497.0: 481,
                  1501.0: 482, 1503.0: 483, 1504.0: 484, 1505.0: 485, 1510.0: 486, 1511.0: 487, 1512.0: 488,
                  1514.0: 489, 1519.0: 490, 1520.0: 491, 1521.0: 492, 1526.0: 493, 1528.0: 494, 1530.0: 495,
                  1533.0: 496, 1534.0: 497, 1535.0: 498, 1539.0: 499, 1540.0: 500, 1541.0: 501, 1542.0: 502,
                  1544.0: 503, 1545.0: 504, 1586.0: 505, 1589.0: 506, 1590.0: 507, 1591.0: 508, 1593.0: 509,
                  1594.0: 510, 1595.0: 511, 1596.0: 512, 1599.0: 513, 1647.0: 514, 1648.0: 515, 1654.0: 516,
                  1655.0: 517, 1657.0: 518, 1658.0: 519, 1659.0: 520, 1672.0: 521, 1674.0: 522, 1679.0: 523,
                  1680.0: 524, 1681.0: 525, 1682.0: 526, 1683.0: 527, 1684.0: 528, 1685.0: 529, 1686.0: 530,
                  1688.0: 531, 1689.0: 532, 1693.0: 533, 1694.0: 534, 1696.0: 535, 1697.0: 536, 1702.0: 537,
                  1704.0: 538, 1705.0: 539, 1706.0: 540, 1707.0: 541, 1709.0: 542, 1710.0: 543, 1711.0: 544,
                  1713.0: 545, 1722.0: 546, 1723.0: 547, 1724.0: 548, 1725.0: 549, 1728.0: 550, 1729.0: 551,
                  1730.0: 552, 1732.0: 553, 1733.0: 554, 1734.0: 555, 1735.0: 556, 1736.0: 557, 1737.0: 558,
                  1738.0: 559, 1739.0: 560, 1740.0: 561, 1741.0: 562, 1744.0: 563, 1745.0: 564, 1746.0: 565,
                  1748.0: 566, 1749.0: 567, 1752.0: 568, 1753.0: 569, 1755.0: 570, 1757.0: 571, 1759.0: 572,
                  1761.0: 573, 1762.0: 574, 1763.0: 575, 1764.0: 576, 1765.0: 577, 1766.0: 578, 1767.0: 579,
                  1768.0: 580, 1772.0: 581, 1901.0: 582, 1902.0: 583, 1904.0: 584, 1905.0: 585, 1920.0: 586,
                  1921.0: 587, 1941.0: 588, 1942.0: 589, 1943.0: 590, 1944.0: 591, 1945.0: 592, 1946.0: 593,
                  1949.0: 594, 1950.0: 595, 1951.0: 596, 1952.0: 597, 1954.0: 598, 1955.0: 599, 1957.0: 600,
                  1959.0: 601, 1961.0: 602, 1962.0: 603, 1963.0: 604, 1964.0: 605, 1965.0: 606, 1966.0: 607,
                  1967.0: 608, 1978.0: 609, 1979.0: 610, 1980.0: 611, 1981.0: 612, 1982.0: 613, 1983.0: 614,
                  1984.0: 615, 1985.0: 616, 1986.0: 617, 1987.0: 618, 1989.0: 619, 1990.0: 620, 1991.0: 621,
                  1992.0: 622, 1993.0: 623, 1995.0: 624, 1996.0: 625, 1997.0: 626, 1998.0: 627, 1999.0: 628,
                  2004.0: 629, 2005.0: 630, 2006.0: 631, 2007.0: 632, 2008.0: 633, 2009.0: 634, 2011.0: 635,
                  2014.0: 636, 2017.0: 637, 2018.0: 638, 2019.0: 639, 2020.0: 640, 2033.0: 641, 2035.0: 642,
                  2036.0: 643, 2040.0: 644, 2042.0: 645, 2043.0: 646, 2045.0: 647, 2046.0: 648, 2047.0: 649,
                  2059.0: 650, 2060.0: 651, 2061.0: 652, 2062.0: 653, 2063.0: 654, 2073.0: 655, 2098.0: 656,
                  2099.0: 657, 2100.0: 658, 2128.0: 659, 2129.0: 660, 2130.0: 661, 2131.0: 662, 2143.0: 663,
                  2146.0: 664, 2147.0: 665, 2153.0: 666, 2158.0: 667, 2160.0: 668, 2161.0: 669, 2162.0: 670,
                  2163.0: 671, 2174.0: 672, 2412.0: 673, 2413.0: 674, 2414.0: 675, 2415.0: 676, 2416.0: 677,
                  2417.0: 678, 2419.0: 679, 2421.0: 680, 2422.0: 681, 2427.0: 682, 2428.0: 683, 2429.0: 684,
                  2430.0: 685, 2431.0: 686, 2432.0: 687, 2433.0: 688, 2434.0: 689, 2435.0: 690, 2436.0: 691,
                  2437.0: 692, 2438.0: 693, 2439.0: 694, 2440.0: 695, 2441.0: 696, 2442.0: 697, 2443.0: 698,
                  2444.0: 699, 2445.0: 700, 2449.0: 701, 2450.0: 702, 2451.0: 703, 2452.0: 704, 2454.0: 705,
                  2455.0: 706, 2456.0: 707, 2457.0: 708, 2459.0: 709, 2460.0: 710, 2473.0: 711, 2474.0: 712,
                  2477.0: 713, 2480.0: 714, 2481.0: 715, 2483.0: 716, 2484.0: 717, 2490.0: 718, 2492.0: 719,
                  2494.0: 720, 2495.0: 721, 2496.0: 722, 2497.0: 723, 2499.0: 724, 2501.0: 725, 2504.0: 726,
                  2506.0: 727, 2510.0: 728, 2518.0: 729, 2524.0: 730, 2527.0: 731, 2530.0: 732, 2531.0: 733,
                  2532.0: 734, 2533.0: 735, 2534.0: 736, 2535.0: 737, 2536.0: 738, 2537.0: 739, 2538.0: 740,
                  2539.0: 741, 2540.0: 742, 2541.0: 743, 2542.0: 744, 2543.0: 745, 2544.0: 746, 2545.0: 747,
                  2547.0: 748, 2548.0: 749, 2549.0: 750, 2553.0: 751, 2554.0: 752, 2555.0: 753, 2556.0: 754,
                  2557.0: 755, 2558.0: 756, 2559.0: 757, 2560.0: 758, 2562.0: 759, 2564.0: 760, 2565.0: 761,
                  2566.0: 762, 2567.0: 763, 2569.0: 764, 2570.0: 765, 2571.0: 766, 2572.0: 767, 2573.0: 768,
                  2622.0: 769, 2626.0: 770, 2627.0: 771, 2628.0: 772, 2632.0: 773, 2633.0: 774, 2637.0: 775,
                  2640.0: 776, 2641.0: 777, 2644.0: 778, 2645.0: 779, 2646.0: 780}}
    df_final.replace(replace_map_comp, inplace=True)
    replace_map_comp = {
        'Day': {1.0: 0, 2.0: 1, 3.0: 2, 4.0: 3, 5.0: 4, 6.0: 5, 7.0: 6, 8.0: 7, 9.0: 8, 10.0: 9, 11.0: 10, 12.0: 11,
                13.0: 12, 14.0: 13, 15.0: 14, 16.0: 15, 17.0: 16, 18.0: 17, 19.0: 18, 20.0: 19, 21.0: 20, 22.0: 21,
                23.0: 22, 24.0: 23, 25.0: 24, 26.0: 25, 27.0: 26, 28.0: 27, 29.0: 28, 30.0: 29, 31.0: 30}}
    df_final.replace(replace_map_comp, inplace=True)
    replace_map_comp = {'DayOfWeek': {0.0: 0, 1.0: 1, 2.0: 2, 3.0: 3, 4.0: 4, 5.0: 5, 6.0: 6}}
    df_final.replace(replace_map_comp, inplace=True)
    replace_map_comp = {
        'Hour': {0.0: 0, 1.0: 1, 2.0: 2, 3.0: 3, 4.0: 4, 5.0: 5, 6.0: 6, 7.0: 7, 8.0: 8, 9.0: 9, 10.0: 10, 11.0: 11,
                 12.0: 12, 13.0: 13, 14.0: 14, 15.0: 15, 16.0: 16, 17.0: 17, 18.0: 18, 19.0: 19, 20.0: 20, 21.0: 21,
                 22.0: 22, 23.0: 23}}
    df_final.replace(replace_map_comp, inplace=True)
    replace_map_comp = {'Minute': {0.0: 0, 15.0: 1, 30.0: 2, 45.0: 3}}
    df_final.replace(replace_map_comp, inplace=True)
    replace_map_comp = {
        'RoadSegmentCode': {28.0: 0, 30.0: 1, 59.0: 2, 62.0: 3, 64.0: 4, 74.0: 5, 110.0: 6, 113.0: 7, 120.0: 8,
                            130.0: 9, 158.0: 10, 197.0: 11, 199.0: 12, 226.0: 13, 232.0: 14, 276.0: 15, 278.0: 16,
                            286.0: 17, 290.0: 18, 291.0: 19, 305.0: 20, 310.0: 21, 321.0: 22, 355.0: 23, 363.0: 24}}
    df_final.replace(replace_map_comp, inplace=True)
    replace_map_comp = {'Metered': {0.0: 0, 1.0: 1}}
    df_final.replace(replace_map_comp, inplace=True)
    replace_map_comp = {'PrevOvertime': {0.0: 0, 1.0: 1}}

    categorical_columns = ['BayId', 'Day', 'DayOfWeek', 'Hour', 'Minute', 'RoadSegmentCode', 'Metered', 'PrevOvertime']

    for category in categorical_columns:
        df_final[category] = df_final[category].astype('category')

    logisticregression_classifier = pickle.load(open('ml_models/randomforest_classifier.sav', 'rb'))
    df_final['Status'] = logisticregression_classifier.predict(df_final)
    df_final.to_csv("ml_models/datasets/realtime/combined/predicted_features_df.csv")
    #bayLocationDf = bayLocations()
    #predicted_locations_df = pd.merge(left=bayLocationDf, right=df_final, how='left', left_on='BayId',
                             #right_on='BayId')
    bayLocationDf = pd.read_csv("otherFiles/bl_df_2.csv")

    predicted_locations_df = pd.merge(left=bayLocationDf, right=df_final, how='right', left_on='BayId',
                                      right_on='BayId')
    predicted_locations_df["Status"].fillna("X", inplace=True)
    predicted_locations_df.to_csv("ml_models/datasets/realtime/combined/predicted_locations_df.csv")
    return predicted_locations_df

# Uses static files. Only used for development
def realTimeExtractProcessPred2():
    # setup Gdrive authentication
    gauth = GoogleAuth()
    gauth.GetFlow()
    gauth.flow.params.update({'access_type': 'offline'})
    gauth.flow.params.update({'approval_prompt': 'force'})
    gauth.LocalWebserverAuth()

    drive = GoogleDrive(gauth)

    # use file id of the folder from Gdrive  1vk9b56J5MOY95AlzbEbaDOzXYjhRpy_l

    file_list = drive.ListFile(
        {'q': "'1vk9b56J5MOY95AlzbEbaDOzXYjhRpy_l' in parents and trashed=false", 'maxResults': 5}).GetList()
    for file1 in file_list:
        print('title: %s, id: %s' % (file1['title'], file1['id']))
        driveFile = drive.CreateFile({'id': file1['id']})
        driveFile.GetContentFile('ml_models/datasets/realtime/' + file1['title'])

    path = 'ml_models/datasets/realtime/'
    df_final = pd.read_csv("ml_models/datasets/realtime/combined/features_df.csv")
    df_final = df_final.dropna()

    logisticregression_classifier = pickle.load(open('ml_models/randomforest_classifier.sav', 'rb'))
    df_final['Status'] = logisticregression_classifier.predict(df_final)
    df_final.to_csv("ml_models/datasets/realtime/combined/predicted_features_df.csv")
    #bayLocationDf = bayLocations()
    bayLocationDf = pd.read_csv("otherFiles/bl_df_2.csv")

    predicted_locations_df = pd.merge(left=bayLocationDf, right=df_final, how='right', left_on='BayId',
                                      right_on='BayId')
    predicted_locations_df["Status"].fillna("X", inplace=True)
    predicted_locations_df.to_csv("ml_models/datasets/realtime/combined/predicted_locations_df.csv")
    return predicted_locations_df


#=======================
data = callAPI()
data2 = bayLocations()
print(data.head())
print(data2)