import io
import os
import secrets
from datetime import datetime, timedelta, timezone
import bcrypt
import joblib as job
import numpy as np
import pandas as pd
import psycopg2 as dbconnector
import requests
import resend
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends, Cookie, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from pydantic import BaseModel

# Load models
model       = job.load("model.joblib")
bounds      = job.load("bounds.joblib")
numberedCols = job.load("numberedCols.joblib")
encoder     = job.load("encoder.joblib")

app = FastAPI(
    title="Weather Prediction API",
    version="1.0.0",
    description="Weather Prediction API"
)

# --- MIDDLEWARE TO HIDE .HTML EXTENSIONS ---
@app.middleware("http")
async def hide_html_extensions(request: Request, call_next):
    path = request.url.path
    
    # Check if the request is targeting an API endpoint or static asset file
    if not path.startswith("/api") and "." not in path.split("/")[-1]:
        # Construct the expected path inside your frontend templates directory
        potential_html_file = f"templates{path}.html" if path != "/" else "templates/index.html"
        
        if os.path.exists(potential_html_file):
            return FileResponse(potential_html_file)
            
    response = await call_next(request)
    return response

#  Middleware 
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://weather-prediction-model-bfql.onrender.com",  # Render (backend serves frontend)
        "https://weather-application-model.vercel.app",        # Vercel frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()
conn = dbconnector.connect(
    host=os.getenv("host"),
    database=os.getenv("database"),
    password=os.getenv("password"),
    user=os.getenv("user"),
    port=int(os.getenv("port"))
)
cursor = conn.cursor()

SECRET_KEY           = os.getenv("SECRET_KEY")
ALGORITHM            = os.getenv("ALGORITHM")
TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", 1440))


# JWT Generation
def generateToken(data: dict):
    toEncode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    toEncode.update({"exp": expire})
    return jwt.encode(toEncode, SECRET_KEY, algorithm=ALGORITHM)


# JWT Validation
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


# Root redirect 
@app.get("/")
def root():
    return RedirectResponse(url="/dash/index.html")


@app.get('/verify-token/')
async def verifyTokenEndpoint(email: str = Depends(verifyToken)):
    cursor.execute("SELECT fname FROM useraccount WHERE email=%s", (email,))
    record = cursor.fetchone()
    fname = record[0] if record else "User"
    return JSONResponse(status_code=200, content={"email": email, "fname": fname})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


# --- DATA SCHEMAS ---
class WeatherData(BaseModel):
    precipitation: float
    tempMax: float
    tempMin: float
    windSpeed: float
    year: int
    month: int
    day: int
    weather: str

class updateData(BaseModel):
    precipitation: float
    max_temp: float
    min_temp: float
    wind_speed: float
    year: int
    month: int
    day: int
    weather: str

class predictionData(BaseModel):
    Precipitation: float
    Temp_Max: float
    Temp_Min: float
    Wind: float
    Year: int
    Month: int
    Day: int

class useraccount(BaseModel):
    fname: str
    lname: str
    email: str
    phone: str
    address: str
    pwd: str

class Authenticate(BaseModel):
    email: str
    password: str
    remember_me: bool = False

class forgotPass(BaseModel):
    email: str

class resetPass(BaseModel):
    password: str
    token: str

class WeatherPrediction(BaseModel):
    temperature: float
    precipitation: float
    wind: float
    humidity: float


# --- ROUTES ---

@app.patch('/weather-data/{id}/')
def updateWeather(id: int, update: updateData):
    if update.min_temp > update.max_temp:
        raise HTTPException(status_code=400, detail="Max Temp must be greater than Min Temp")
    query = """UPDATE weather_table SET 
        precipitation=%s, temp_max=%s, temp_min=%s, wind=%s, year=%s, month=%s, day=%s, weather=%s 
        WHERE id=%s"""
    try:
        cursor.execute(query, (update.precipitation, update.max_temp, update.min_temp,
                               update.wind_speed, update.year, update.month, update.day,
                               update.weather, id))
        conn.commit()
        return {"message": "updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/user-data')
async def weatherData(data: WeatherData):
    if data.tempMax < data.tempMin:
        raise HTTPException(status_code=400, detail="Max Temp must be greater than Min Temp")
    insert = "INSERT INTO weather_table (precipitation,temp_max,temp_min,wind,year,month,day,weather) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)"
    values = (data.precipitation, data.tempMax, data.tempMin, data.windSpeed,
              data.year, data.month, data.day, data.weather)
    try:
        cursor.execute(insert, values)
        conn.commit()
        return {"Precipitation": data.precipitation}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get('/weather-data/')
async def getWeatherdata():
    cursor.execute("SELECT * FROM weather_table")
    allRecords = cursor.fetchall()
    frame = pd.DataFrame(allRecords)
    return frame.to_dict(orient="records")


@app.delete('/weather-data/{id}')
async def deleteData(id: int):
    try:
        cursor.execute("DELETE FROM weather_table WHERE id=%s", (id,))
        conn.commit()
        return {"Deleted": "Successfully Deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/upload-csv/')
async def upload(file: UploadFile = File(...)):
    insertUploaded = """INSERT INTO weather_table (precipitation,temp_max,temp_min,wind,year,month,day,weather) 
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s)"""
    file_content = await file.read()
    uploadedFile = pd.read_csv(io.BytesIO(file_content))
    try:
        for i, records in uploadedFile.iterrows():
            values = (records['Precipitation'], records['Temp_Max'], records['Temp_Min'],
                      records['Wind'], records['Year'], records['Month'], records['Day'], records['Weather'])
            cursor.execute(insertUploaded, values)
        conn.commit()
        return {"Message": "Added Successfully"}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.post('/prediction/')
async def predictionInput(userData: predictionData):
    df = pd.DataFrame({
        "precipitation": [userData.Precipitation],
        "temp_max":      [userData.Temp_Max],
        "temp_min":      [userData.Temp_Min],
        "wind":          [userData.Wind],
        "year":          [userData.Year],
        "month":         [userData.Month],
        "day":           [userData.Day],
    })
    for cols in numberedCols:
        df[cols] = df[cols].clip(lower=bounds[cols]['Lower'], upper=bounds[cols]['Upper'])
    predict = model.predict(df)
    predict = encoder.inverse_transform(predict)
    return {"Predicted": str(predict[0])}


@app.get('/current.json')
def getLiveWeatherdata(region: str, email: str = Depends(verifyToken)):
    url = "https://api.weatherapi.com/v1/current.json"
    params = {"key": os.getenv("weatherAPIKey"), "q": region}
    try:
        response = requests.get(url, params=params)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/user-account/")
async def accountdata(account: useraccount):
    try:
        hashed_pwd = bcrypt.hashpw(account.pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        insert = "INSERT INTO useraccount(fname,lname,email,phone,address,pwd) VALUES(%s,%s,%s,%s,%s,%s)"
        cursor.execute(insert, (account.fname, account.lname, account.email,
                                account.phone, account.address, hashed_pwd))
        conn.commit()
        return JSONResponse(status_code=201, content={"Success": "Account Successfully Created"})
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def create_refresh_token_string() -> str:
    return secrets.token_urlsafe(32)


@app.post('/authenticate/')
async def authenticate(cred: Authenticate):
    try:
        cursor.execute("SELECT email, pwd, fname FROM useraccount WHERE email=%s", (cred.email,))
        record = cursor.fetchone()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    if record is None:
        raise HTTPException(status_code=401, detail="Incorrect Username or Password")

    columns = [col[0] for col in cursor.description]
    recordDict = dict(zip(columns, record))

    if not bcrypt.checkpw(cred.password[:72].encode('utf-8'), recordDict["pwd"].encode('utf-8')):
        raise HTTPException(status_code=401, detail="Incorrect Password")

    if cred.remember_me:
        refresh_cookie_max_age = 60 * 60 * 24 * 30
        db_lifespan_days = 30
    else:
        refresh_cookie_max_age = None
        db_lifespan_days = 1

    token         = generateToken({"sub": recordDict['email']})
    refresh_token = create_refresh_token_string()

    try:
        expires_at = datetime.utcnow() + timedelta(days=db_lifespan_days)
        cursor.execute(
            "INSERT INTO user_sessions (user_email, refresh_token, expires_at) VALUES (%s, %s, %s)",
            (recordDict['email'], refresh_token, expires_at)
        )
        conn.commit()
    except Exception as db_error:
        print(f"Database Error: {db_error}")
        raise HTTPException(status_code=500, detail="Failed to establish secure session state.")

    response = JSONResponse(
        status_code=200,
        content={"SuccessMessage": "Login Successful", "fname": recordDict['fname'], "email": recordDict['email']}
    )
    response.set_cookie(key="token", value=token, httponly=True, samesite="none",
                        max_age=1800, secure=True)
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True,
                        samesite="none", max_age=refresh_cookie_max_age, secure=True)
    return response


@app.post('/forgot-password/')
async def resetPassRequest(emailaddress: forgotPass):
    try:
        cursor.execute("SELECT email FROM useraccount WHERE email=%s", (emailaddress.email,))
        fetchOne = cursor.fetchone()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

    if fetchOne is None:
        raise HTTPException(status_code=404, detail="User Associated with email does not exist!!")

    token  = secrets.token_urlsafe(32)
    expiry = datetime.now(timezone.utc) + timedelta(hours=1)

    try:
        cursor.execute("UPDATE useraccount SET reset_token=%s, reset_token_expiry=%s WHERE email=%s",
                       (token, expiry, emailaddress.email))
        conn.commit()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save reset token")

    resend.api_key = os.getenv("resendkey")
    resetLink = f"https://weather-prediction-model-bfql.onrender.com/dash/reset-password.html?token={token}"

    try:
        resend.Emails.send({
            "from": os.getenv("sender"),
            "to": emailaddress.email,
            "subject": "Password Reset Request",
            "html": f'<h2>Password Reset</h2><p>Click below to reset your password within 1 hour.</p><a href="{resetLink}">Reset My Password</a>'
        })
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))

    return JSONResponse(status_code=200, content={"Success": "Reset Link sent", "email": emailaddress.email})


@app.post("/reset-password/")
async def resetPassword(resetData: resetPass):
    try:
        cursor.execute("SELECT reset_token FROM useraccount WHERE reset_token=%s", (resetData.token,))
        fetchRecord = cursor.fetchone()
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))

    if fetchRecord is None:
        raise HTTPException(status_code=404, detail="Token Not Found")

    hashedPassword = bcrypt.hashpw(resetData.password[:72].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    try:
        cursor.execute(
            "UPDATE useraccount SET pwd=%s, reset_token=NULL, reset_token_expiry=NULL WHERE reset_token=%s",
            (hashedPassword, resetData.token)
        )
        conn.commit()
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))

    return JSONResponse(status_code=200, content={"Success": "You have successfully updated your password"})


@app.get('/predict', response_model=WeatherPrediction)
def predictWeather(year: int):
    try:
        cursor.execute("SELECT avg(temp_max), avg(precipitation), avg(wind) FROM weather_table WHERE year=%s", (year,))
        record = cursor.fetchone()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if record is None or record[0] is None:
        raise HTTPException(status_code=404, detail="No data found for that year")

    return WeatherPrediction(
        temperature=round(float(record[0]), 1),
        precipitation=round(float(record[1]), 1),
        wind=round(float(record[2]), 1),
        humidity=0.0
    )


@app.post('/logout/')
async def logout():
    response = JSONResponse(status_code=200, content={"message": "Logged out"})
    response.delete_cookie("token")
    response.delete_cookie("refresh_token")
    return response


#MOUNT DASH STATIC FILES
app.mount("/dash", StaticFiles(directory="dash", html=True), name="dash")