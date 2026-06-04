import os
import json
import time
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from google import genai
from google.genai import types
import psycopg2
from xhtml2pdf import pisa
from fastapi.responses import FileResponse

app = FastAPI(title="AI Spatial Travel Planner Engine")

# CORS Middleware Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gemini AI Client Initialization
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6IXqAm87nxBhD3F5vKQcJtt603SCdvyAdKMLpY2YgJy1g"))

# Pydantic Schemas for validation
class DailyItineraryNode(BaseModel):
    day_number: int
    morning_activity: str
    afternoon_activity: str
    evening_activity: str
    estimated_cost_usd: float

class CompleteTravelBlueprint(BaseModel):
    destination: str
    duration_days: int
    travel_style: str
    interests: str
    latitude: float
    longitude: float
    daily_itinerary: List[DailyItineraryNode]

class UserRequest(BaseModel):
    prompt: str

# Fixed and Secure Database Connection Routing
def get_db_connection():
    database_url = os.environ.get("DATABASE_URL")
    
    if database_url:
        # Render Environment connection
        return psycopg2.connect(database_url)
    else:
        # Fallback local connection string with valid python quotation syntax
        return psycopg2.connect("postgresql://omkar:oUz7Pk31DYZf1XhBPFgwNc024CpQNLB9@dpg-d8geqv9kh4rs73akc97g-a/postgres1_6fpn")


@app.post("/api/plan-trip")
async def plan_trip(request: UserRequest):
    try:
        max_retries = 5
        initial_delay = 2
        response_text = None
        
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=request.prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=CompleteTravelBlueprint,
                        temperature=0.2
                    ),
                )
                response_text = response.text
                break  
            except Exception as e:
                if "503" in str(e) and attempt < max_retries - 1:
                    sleep_time = initial_delay * (2 ** attempt)
                    print(f"⚠️ Server Overloaded (503). Retrying attempt {attempt + 2}/{max_retries} in {sleep_time}s...")
                    time.sleep(sleep_time)
                else:
                    raise e

        if not response_text:
            raise HTTPException(status_code=503, detail="Gemini infrastructure is completely unresponsive.")
            
        ai_data = json.loads(response_text)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        insert_master_query = """
        INSERT INTO user_itineraries (destination, duration_days, travel_style, interests, coordinates)
        VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) RETURNING id;
        """
        cursor.execute(insert_master_query, (
            ai_data['destination'], ai_data['duration_days'], 
            ai_data['travel_style'], ai_data['interests'],
            ai_data['longitude'], ai_data['latitude']
        ))
        master_id = cursor.fetchone()[0]
        
        insert_day_query = """
        INSERT INTO itinerary_days (itinerary_id, day_number, morning_activity, afternoon_activity, evening_activity, estimated_cost_usd)
        VALUES (%s, %s, %s, %s, %s, %s);
        """
        for day in ai_data['daily_itinerary']:
            cursor.execute(insert_day_query, (
                master_id, day['day_number'], day['morning_activity'],
                day['afternoon_activity'], day['evening_activity'], day['estimated_cost_usd']
            ))
            
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            "status": "success",
            "master_trip_id": master_id,
            "payload": ai_data
        }
        
    except Exception as e:
        print("\n💥 --- DETECTED BACKEND CRASH TRACEBACK --- 💥")
        traceback.print_exc()
        print("💥 ---------------------------------------- 💥\n")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/itinerary/{trip_id}/map-data")
async def get_map_data(trip_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "SELECT destination, ST_X(coordinates), ST_Y(coordinates) FROM user_itineraries WHERE id = %s;"
        cursor.execute(query, (trip_id,))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not result:
            raise HTTPException(status_code=404, detail="Itinerary record coordinates not located.")
            
        return {
            "destination": result[0],
            "longitude": result[1],
            "latitude": result[2]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/itinerary/{trip_id}/export")
async def export_pdf(trip_id: int):
    pdf_filename = f"itinerary_trip_{trip_id}.pdf"
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT destination, duration_days, travel_style FROM user_itineraries WHERE id = %s;", (trip_id,))
        master = cursor.fetchone()
        
        cursor.execute("SELECT day_number, morning_activity, afternoon_activity, evening_activity FROM itinerary_days WHERE itinerary_id = %s ORDER BY day_number;", (trip_id,))
        days = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        if not master:
            raise HTTPException(status_code=404, detail="Target document metadata matching ID not found.")

        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Helvetica, Arial, sans-serif; color: #2d3748; padding: 20px; }}
                h1 {{ color: #1a365d; border-bottom: 2px solid #3182ce; padding-bottom: 10px; }}
                .meta {{ font-size: 14px; color: #4a5568; margin-bottom: 20px; }}
                .day-card {{ margin-bottom: 20px; padding: 15px; border: 1px solid #e2e8f0; background: #f7fafc; }}
                .day-title {{ font-size: 16px; font-weight: bold; color: #2c5282; margin-bottom: 10px; }}
                .act {{ margin-bottom: 5px; font-size: 13px; }}
                .label {{ font-weight: bold; color: #4a5568; }}
            </style>
        </head>
        <body>
            <h1>🎒 Your AI Vacation Blueprint: {master[0]}</h1>
            <div class="meta"><b>Duration:</b> {master[1]} Days | <b>Travel Style Constraints:</b> {master[2]}</div>
        """
        
        for day in days:
            html_content += f"""
            <div class="day-card">
                <div class="day-title">Day {day[0]}</div>
                <div class="act"><span class="label">🌅 Morning:</span> {day[1]}</div>
                <div class="act"><span class="label">☀️ Afternoon:</span> {day[2]}</div>
                <div class="act"><span class="label">🌙 Evening:</span> {day[3]}</div>
            </div>
            """
            
        html_content += "</body></html>"
        
        with open(pdf_filename, "wb") as pdf_file:
            pisa.CreatePDF(html_content, dest=pdf_file)
            
        return FileResponse(pdf_filename, media_type="application/pdf", filename=pdf_filename)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
