from flask import Flask,request,abort
from linebot import LineBotApi,WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage, TextSendMessage
from datetime import datetime
import time
import schedule 
import json
import requests
from flask_apscheduler import APScheduler                          # 任務排程

from apscheduler.schedulers.blocking import BlockingScheduler# 任務排程
from apscheduler.schedulers.background import BackgroundScheduler  # 調整APScheduler時區使用
from linebot.exceptions import InvalidSignatureError

import certifi
import pymongo
from pymongo import MongoClient

handler=WebhookHandler='...' #change to your token
line_bot_api=LineBotApi('...') #change to your token
line_ID = '...' #change to your line ID

# 連入資料庫
ca = certifi.where()
cluster=pymongo.MongoClient(f"...", tlsCAFile=ca)#I use mongoDB
db = cluster["..."] 
collection = db["..."] 

sched = BlockingScheduler(timezone='Asia/Taipei')

app= Flask(__name__)  
@app.route("/callback",methods=['POST'])###
def callback():
    signature=request.headers['X-Line-Signature']
    body=request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent,message=TextMessage)
def handle_message(event) :
    userMessage = event.message.text
    print(event)
    
    if userMessage == 'Jarvis, u there?':
        line_bot_api.reply_message(event.reply_token, TextSendMessage( text='At your service madame ' ))
        
    if userMessage[0:4] == 'Sch ' and len(userMessage)>4:        
        push_db(userMessage[4:])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=userMessage[4:]+' scheduled ma\'am' ))

    if userMessage[0:4] == 'Del ' and len(userMessage)>4:
        data =userMessage[4:]
        mes=''
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=sch(data,mes)))
        
    if userMessage[0:4] == 'Del*':
        data ='0'
        mes=''
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=sch(data,mes)))
        
    if userMessage[0:4] == 'Sch.':
        mes=''
        data='-1'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=sch(data,mes)))
        
    if userMessage=='Good morning':
        good_morning()
        
    if userMessage=='Wea':
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=get_weather()))

def sch(data,mes):

    cursor = collection.find({},{ "_id": 0,"task": 1,"detail": 1 })
    all_data = list(cursor)
    count=collection.count_documents({}) 
    
    if data =='0': #delete *
        collection.delete_many({})
        return 'All done mam'
    else: 
        if data!='-1': #delete one
            collection.delete_one({'task': data})
        
            for i in range(int(data),count):
                collection.update_one({"task" : str(i+1)},  {"$set": {"task": str(i)}})
  
    cursor = collection.find({},{ "_id": 0,"task": 1,"detail": 1 })
    all_data = list(cursor)
    count=collection.count_documents({}) 
    
    if count==0:
        mes='There is nothing on schedule mam.'
    con=0
    for x in all_data:
        con=con+1
        mes=mes+str(con)+'. '+x['detail']
        if con!=count:
            mes=mes+'\n'
            
    return mes       

# 單筆匯入
def push_db(mes) :
    count=collection.count_documents({})+1
    doc = {"task":str(count),"detail":mes}# event[0]}
    collection.insert_one(doc)

@sched.scheduled_job('cron', hour=7, minute=50)
def good_morning() :
    mes='Morning madame,'+'\n'+ 'Here\'s today\'s schedule '
    
    reply_arr=[]
    reply_arr.append( TextSendMessage(mes) )
    reply_arr.append( TextSendMessage(text=sch('-1','') ))
    reply_arr.append( TextSendMessage(get_weather()) )
    
    line_bot_api.push_message( line_ID, reply_arr )
    
    #line_bot_api.push_message(line_ID, TextSendMessage(text=sch('-1',mes)))
    
#天氣
def get_weather():
    url = "https://opendata.cwb.gov.tw/api/v1/rest/datastore/F-C0032-001"
    params = {
        "Authorization": "CWB-73005E65-95A3-4EB8-8CDF-90E1890AA312",
        "locationName": "桃園市",    }

    response = requests.get(url, params=params)
    #print(response.status_code)

    mes=''
    if response.status_code == 200:
        # print(response.text)
        data = json.loads(response.text)

        location = data["records"]["location"][0]["locationName"]

        weather_elements = data["records"]["location"][0]["weatherElement"]
        start_time = weather_elements[0]["time"][0]["startTime"]
        #end_time = weather_elements[0]["time"][0]["endTime"]
        weather_state = weather_elements[0]["time"][0]["parameter"]["parameterName"]
        rain_prob = weather_elements[1]["time"][0]["parameter"]["parameterName"]
        min_tem = weather_elements[2]["time"][0]["parameter"]["parameterName"]
        comfort = weather_elements[3]["time"][0]["parameter"]["parameterName"]
        max_tem = weather_elements[4]["time"][0]["parameter"]["parameterName"]
        
        day=datetime.today().weekday()+1
        if day==1:
            day=' (一)'
        if day==2:
            day=' (二)'
        if day==3:
            day=' (三)'
        if day==4:
            day=' (四)'
        if day==5:
            day=' (五)'
        if day==6:
            day=' (六)'
        if day==7:
            day=' (七)'
        
        mes='Date: '+start_time[5:7]+'/'+start_time[8:10]+day+'\ntemp: '+min_tem+'°C~'+max_tem+'°C \npop: '+ rain_prob+'% \nweather: '+comfort
        #print(location)
        #print(weather_state)
        #print(rain_prob)
        #print(min_tem)
        #print(max_tem)
        #print(comfort)

    else:
        mes="Can't get data!"
    return mes


if __name__=='__main__':
    sched.start()
    app.run()