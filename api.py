from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import psycopg2 as dbconnector
from pydantic import BaseModel
import joblib as job
import pandas as pd
import numpy as np
import requests
import io
from dotenv import load_dotenv
import os
from fastapi import UploadFile, File
from fastapi import HTTPException

# load model
model=job.load("model.joblib")
bounds=job.load("bounds.joblib")
numberedCols=job.load("numberedCols.joblib")
encoder=job.load("encoder.joblib")

import pandas as pd

app = FastAPI(
    title="Weather Prediction API",
    version="1.0.0",
    description="Weather Prediction API"
    
    )


# CORS middleware (allows your frontend to call this API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# connection
conn=dbconnector.connect(
    host="localhost",
    database="weather_db",
    password="passcode2000!!!",
    user="postgres",
    port=5432,
)
cursor=conn.cursor()
# For insert Moddel------------------------------------------***Model-->
class WeatherData(BaseModel):

    precipitation :float
    tempMax:float
    tempMin :float
    windSpeed :float
    year :int
    month:int
    day :int 
    weather:str

# For update -----------------------Model------------------------------>
class updateData(BaseModel):
    precipitation: float
    max_temp:  float    
    min_temp:  float   
    wind_speed: float     
    year:      int    
    month:    int     
    day:       int  
    weather:  str   

#
@app.patch('/weather-data/{id}/')
def updateWeather(id: int,update: updateData):
    query="""UPDATE weather_table
    set 
    precipitation=%s,
    temp_max=%s,
    temp_min=%s,
    wind=%s,
    year=%s,
    month=%s,
    day=%s,
    weather=%s where id=%s


    """;
    if update.min_temp>update.max_temp:
            raise HTTPException(status_code=500,detail="Max Temp must be greater than Min Temp")
    try:
        cursor.execute(query,(
        update.precipitation,
        update.max_temp,
        update.min_temp,
        update.wind_speed,
        update.year,
        update.month,
        update.day,
            update.weather,
            id))
        
        conn.commit()
        return{
                "message":"updated"
        }
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))



# POST method-----------------------------------------***************--------------------->

@app.post('/user-data')
async def weatherData(data:WeatherData):
    insert="insert into weather_table (precipitation,temp_max,temp_min,wind,year,month,day,weather) values(%s,%s,%s,%s,%s,%s,%s,%s)"
    values=(data.precipitation,data.tempMax,data.tempMin,data.windSpeed,data.year,data.month,data.day,data.weather)
    if data.tempMax<data.tempMin:
        raise HTTPException(status_code=400,detail="Max Temp must be greater than Min Temp")
    try:
     cursor.execute(insert,values)
    
   
     conn.commit()
     return{
        "Precipitation":data.precipitation,
        }
    except Exception as error:
         raise HTTPException(status_code=500,detail=str(error))



# GET method---Fetch data------------------------>------------------------------------------->

@app.get('/weather-data/')
async def getWeatherdata():
    select="select * from weather_table"
    cursor.execute(select)
    allRecords=cursor.fetchall()
    frame=pd.DataFrame(allRecords)
    rows=frame.to_dict(orient="records")
    return rows
    
   
# DELETE METHOD -------------------------Delete record--------------->--------------------------->
@app.delete('/weather-data/{id}')
async def deleteData(id:int):
    delete="delete from weather_table where id=%s"
    try:
        cursor.execute(delete,(id,))
        conn.commit()

        return {
        "Message":"Deleted"

           }
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))




# UPLOAD------------------------------POST VIA UPLOAD-------------------------------------------->
class addViaUpload(BaseModel):
        precipitation: float
        max_temp:  float    
        min_temp:  float   
        wind_speed: float     
        year:      int    
        month:    int     
        day:       int  
        weather:  str   

@app.post('/upload-csv/')
async def upload(file: UploadFile = File(...)):
  
    insertUploaded=""" insert into weather_table (precipitation,temp_max,temp_min,wind,year,month,day,weather) 
    values(%s,%s,%s,%s,%s,%s,%s,%s)

    """
    # get uploaded file and format
    file= await file.read()
    uploadedFile=pd.read_csv(io.BytesIO(file))

    # readCSV=pd.read_csv(fi)
    for  i,records in uploadedFile.iterrows():
        precipitation=records['Precipitation']
        max_temp=records['Temp_Max']
        min_temp=records['Temp_Min']
        wind_speed=records['Wind']
        year=records['Year']
        month=records['Month']
        day=records['Day']
        weather=records['Weather']
        
        values=(precipitation,max_temp,min_temp,wind_speed,year,month,day,weather)
        try:
            cursor.execute(insertUploaded,values)
            conn.commit()
            return{
                "Message":"Added Successfully"
            }
        except Exception as error:
            raise HTTPException(status_code=500,detail=str(error))



# Prediction endpoint------------------------################---------------------------->
class predictionData(BaseModel):
    Precipitation: float
    Temp_Max:  float    
    Temp_Min:  float   
    Wind: float     
    Year:      int    
    Month:    int     
    Day:       int  
    # weather:  str 

@app.post('/prediction/')
async def predictionInput(userData:predictionData):
    df=pd.DataFrame(

    {
        "precipitation":userData.Precipitation,
        "temp_max":[userData.Temp_Max],
        "temp_min":[userData.Temp_Min],
        "wind":[userData.Wind],
        "year":[userData.Year],
        "month":[userData.Month],
        "day":[userData.Day],  
    }
    )
    for cols in numberedCols:
        df[cols]=df[cols].clip(lower=bounds[cols]['Lower'],upper=bounds[cols]['Upper'])
    predict=model.predict(df)
    predict=encoder.inverse_transform(predict)
    df['Predicted']=predict
    
    return{
       "Predicted": str(df['Predicted'].iloc[0])  # convert to string since it's a weather label

       

    }
  

    
# Get weather data-----------------------------*******WEAther data************************----------------------->
load_dotenv()
apiKey=os.getenv("weatherAPIKey")
Base="https://api.weatherapi.com/v1"
endpoint="/current.json"
@app.get('/current.json')
def getWeatherdata(region:str):
    url=Base+endpoint
    headers={
        "Accept":"application/json"
    }
    params={
        "key":apiKey,
         "q":region

    }
    try:
        response=requests.get(url,params=params,headers=headers)
        results=response.json()
        return results
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))



    # MOUNT BOOTSTRAP
app.mount("/dash", StaticFiles(directory="dash"), name="dash")