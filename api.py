from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import psycopg2 as dbconnector
from pydantic import BaseModel
import joblib as job
import pandas as pd
from datetime import datetime, timedelta
from fastapi import Cookie
import bcrypt
import numpy as np
from passlib.hash import bcrypt as pwd_context
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from fastapi import Depends
# from passlib.hash import bcrypt as pwd_context
import requests
import resend
from fastapi import FastAPI, HTTPException, Request
import io
from dotenv import load_dotenv
import os
from jose import JWTError, jwt
from fastapi import Depends, Cookie
import secrets
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

# CORS middleware (allows your frontend to call this API)---------------------------->

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
     allow_credentials=True,                    
    allow_headers=["*"],
)
# connection
load_dotenv()
conn=dbconnector.connect(
    host=os.getenv("host"),
    database=os.getenv("database"),
    password=os.getenv("password"),
    user=os.getenv("user"),
    port=int(os.getenv("port"))
)
cursor=conn.cursor()

#Token Validdity Parameters---------- Authentication Parameters----------------------------AUTH Parameters--------------->

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM  = os.getenv("ALGORITHM")
TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", 1440))


# generate token function------------------TOKEN -----------GENERATION---JWT------->



def generateToken(data: dict):
    toEncode = data.copy()
    
    # FIX: Use timezone-aware UTC datetime
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    
    toEncode.update({"exp": expire})
    token = jwt.encode(toEncode, SECRET_KEY, algorithm=ALGORITHM)
    return token

#  verify token function-------------TOKEN VERIFICATION------------------------->

def verifyToken(token: str = Cookie(None)):
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        # jwt.decode will now properly check the UTC 'exp' timestamp against current UTC time
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    

@app.get('/verify-token/')
async def verifyTokenEndpoint(email: str = Depends(verifyToken)):
    cursor.execute("SELECT fname FROM useraccount WHERE email=%s", (email,))
    record = cursor.fetchone()
    return JSONResponse(status_code=200, content={"email": email, "fname": record[0]})

# -----------------------TOKEN VERI------END------------------------------------->

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )



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
      
        
            "Deleted":"Successfully Deleted"

      
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

apiKey=os.getenv("weatherAPIKey")
Base="https://api.weatherapi.com/v1"
endpoint="/current.json"
@app.get('/current.json')
def getWeatherdata(region:str, email: str = Depends(verifyToken)):
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



# Create user account--------------------------------------------******************************************---------------------------------->
endpointAccount="/user-account/"
class useraccount(BaseModel):
    fname: str
    lname: str
    email:str
    phone:str
    address:str
    pwd: str
    
@app.post(endpointAccount)
async def accountdata(account: useraccount):
    try:
        cursor = conn.cursor()  # fresh cursor each request

        # Hash password here, per request
        hashed_pwd = bcrypt.hashpw(account.pwd.encode('utf-8'), bcrypt.gensalt())
        hashed_pwd_str = hashed_pwd.decode('utf-8')

        insert = "insert into useraccount(fname,lname,email,phone,address,pwd) values(%s,%s,%s,%s,%s,%s)"
        values = (account.fname, account.lname, account.email, account.phone, account.address, hashed_pwd_str)
        cursor.execute(insert, values)
        conn.commit()
        return JSONResponse(status_code=201, content={"Success": "Account Successfully Created"})

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=501, detail=str(e))

   
# Authentication -----------------------------------------+++TOKEN VERIFICATION BACKEND+++++++++++++++++++++++++----------------------->

def verifyToken(token: str = Cookie(None)):
    if token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    

class Authenticate(BaseModel):
    email:str
    password: str

@app.post('/authenticate/')
async def authenticate(cred:Authenticate):
    # @app.exception_handler(Exception)
    # async def global_exception_handler(cred: Authenticate, exc: Exception):
  
    try:
        select="select email,pwd,fname from useraccount where email=%s"
        cursor.execute(select,(cred.email,))
        record=cursor.fetchone()
    except Exception as error:
        # print(f"❌ Error: {error}")  
        raise HTTPException(status_code=500,detail=str(error))
    if record is None:
            raise HTTPException(status_code=401,detail="User not existsss")
    columns=[col[0] for col in cursor.description]
    recordFrame=pd.DataFrame([record],columns=columns)
    recordDict=recordFrame.to_dict(orient="records")[0]

# String to be sent to generate token---------------------------to be sent to GENERATE TOKEN-------------->
    token = generateToken({"sub": recordDict['email']})


    
  #Hashed password
    if not bcrypt.checkpw(cred.password[:72].encode('utf-8'), recordDict["pwd"].encode('utf-8')):
        raise HTTPException(status_code=401, detail="Incorrect Password")
    else:
        response= JSONResponse(status_code=200,content={"SuccessMessage":"Login Successful","fname":recordDict['fname'],"email":recordDict['email'],"Pass":recordDict['pwd']})
                # return JSONResponse(status_code=201,content=recordDict)
        response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400  # 24 hours
    )
        return response

    

# Send Reset Link-----------FORGOT PASSWORD- FORM----------------------------------------------------------------------->
resend.api_key=os.getenv("resendkey")
senderEmail=os.getenv("sender")

class forgotPass(BaseModel):
    email:str

@app.post('/forgot-password/')
async def resetPass(emailaddress:forgotPass):
    try:
        selectEmail="select email from useraccount where email=%s"
        cursor.execute(selectEmail,(emailaddress.email,))
        fetchOne=cursor.fetchone()
        
    except Exception as error:
        # print(error)
        raise HTTPException(status_code=500,detail=str(error))

    if fetchOne is None:
       
        raise HTTPException(status_code=404,detail="User Associated with that email not exist!!")
    records=pd.DataFrame(fetchOne,columns=[cols[0] for cols in cursor.description])
    recordDict=records.to_dict(orient="records")
    
    # return JSONResponse(status_code=200,content={"Email":recordDict[0]['email']})

     # 1. generate token
    token  = secrets.token_urlsafe(32)
    expiry = datetime.utcnow() + timedelta(hours=1)
    try:
        update="""update useraccount 
        set reset_token=%s,
        reset_token_expiry=%s
        where email=%s


        """
        cursor.execute(update,(token,expiry,emailaddress.email))
        conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500,detail="Failed to save reset token")
    else:
        base_="http://127.0.0.1:8000/dash"
        resetLink=f"{base_}/reset-password.html/?token={token}"
 
        try:
            resend.Emails.send({
                "from": senderEmail,
                # "to": emailaddress.email,
                "to": "bitech20th@gmail.com",
                "subject": "Password Reset Request",
                "html": f"""
                    <h2>Password Reset</h2>
                    <p>Click the link below to reset your password.</p>
                    <p>This link expires in <strong>1 hour</strong>.</p>
                    <a href="{resetLink}" style="
                        background:#7F77DD;
                        color:white;
                        padding:10px 20px;
                        border-radius:6px;
                        text-decoration:none;
                    ">Reset My Password</a>
                    <p style="color:#888; font-size:12px;">
                        If you didn't request this, ignore this email.
                    </p>
                """
             })
        except Exception as err:
            raise HTTPException(status_code=500,detail=str(err))
        return JSONResponse(status_code=200,content={"Success":"Reset Link sent, check your email","email":emailaddress.email})

    
    
    
  
# RESET PASSWORD FORM-------------------------------------------------------------------->
     
resetendpoint = "/reset-password/"
class resetPass(BaseModel):
    password: str
    token: str

@app.post(resetendpoint)
async def resetPassword(resetData:resetPass):
    try:
        selectToken="select reset_token,pwd from useraccount where reset_token=%s"
        cursor.execute(selectToken,(resetData.token,))
        fetchRecord=cursor.fetchone()
    except Exception as ex:
        raise HTTPException(status_code=500,detail=str(ex))
    if fetchRecord is None:
            raise HTTPException(status_code=404,detail="Not Found")
    df=pd.DataFrame([fetchRecord],columns=[cols[0] for cols in cursor.description])
    records=df.to_dict(orient="records")
    # hashedPassword = bcrypt.hash(resetData.password)  # ✅ hash first
    hashedPassword = bcrypt.hashpw(resetData.password[:72].encode('utf-8'), bcrypt.gensalt())  
    hashedPassword = hashedPassword.decode('utf-8')  # convert bytes to string for DB storage
    

    try:
        # return JSONResponse(status_code=200,content={"Success":"User Found","token":resetData.token,"pass":records['pwd']})
            updatePass="""
            update useraccount set 
            pwd=%s,reset_token=NULL,reset_token_expiry=NULL
            where reset_token=%s


            """
            cursor.execute(updatePass,(hashedPassword,resetData.token))
            conn.commit()
    except Exception as err:
        raise HTTPException(status_code=500,detail=str(err))
    return JSONResponse(status_code=200,content={"Success":"You have successful updated your password"})




        
   



# TOKEN GENERATION GOES HERE-----------------------------TOKEN---------------------------->

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM  = os.getenv("ALGORITHM")
TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES"))

def generateToken(data: dict):
    toEncode = data.copy()
    expire   = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    toEncode.update({"exp": expire})
    token = jwt.encode(toEncode, SECRET_KEY, algorithm=ALGORITHM)
    return token


# Verify token------------------------*************************-------------------
@app.get('/verify-token/')
async def verifyTokenEndpoint(email: str = Depends(verifyToken)):
    return JSONResponse(status_code=200, content={"email": email})




# Logout---------------------LOGOUT---------------------------------------------->
@app.post('/logout/')
async def logout():
    response = JSONResponse(status_code=200, content={"message": "Logged out"})
    response.delete_cookie("token")  # ✅ clears the httponly cookie
    return response

# @app.get("/me/")
# async def get_me(request: Request):
#     user = request.session.get("user")  # or however you store session
#     if not user:
#         raise HTTPException(status_code=401, detail="Not authenticated")
#     return {"user": user}

app.mount("/dash", StaticFiles(directory="dash", html=True), name="dash")