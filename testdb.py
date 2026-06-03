import psycopg2

print("🐘 Attempting to connect to PostgreSQL...")

try:
    # TODO: Replace 'YOUR_DATABASE_PASSWORD_HERE' with your real PostgreSQL master password!
    conn = psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password="YOUR_DATABASE_PASSWORD_HERE",
        host="localhost",
        port="5432"
    )
    
    cursor = conn.cursor()
    # Let's check if the PostGIS extension is installed and active
    cursor.execute("SELECT PostGIS_Version();")
    version = cursor.fetchone()
    
    print(f"\n✅ Database Connection Success!")
    print(f"🌍 PostGIS Version Active: {version[0]}")
    
    cursor.close()
    conn.close()

except Exception as e:
    print(f"\n❌ Database Connection Failed!")
    print(f"Error Details: {e}")
    