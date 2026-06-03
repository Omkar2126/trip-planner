import os
from google import genai

# Initialize the client 
# TODO: Double-check that your key is pasted correctly inside the quotes!
client = genai.Client(api_key="AQ.Ab8RN6LccPp_NMojXKGcRnh6QgRRASjMLhCexZd6-AVxBNRojw")

print("📡 Sending a test request to Gemini clusters...")

try:
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents='Respond with the single word: "Success!"',
    )
    print(f"\n✅ AI Response: {response.text}")
    
except Exception as e:
    print(f"\n❌ Connection Failed!")
    print(f"Error Details: {e}")