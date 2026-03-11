import os
import urllib.parse
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import sqlite3
import requests
import json
from datetime import datetime

app = FastAPI(title="My Website Visitor Monitor")

# Database setup
import os
DB_PATH = "/app/visitors.db"  # Matches the mount path you just set
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute("""
CREATE TABLE IF NOT EXISTS visitors (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    ip TEXT,
    page TEXT,
    user_agent TEXT,
    company TEXT,
    location TEXT,
    extra TEXT
)
""")

def enrich_ip(ip: str):
    """Free company + location lookup (no API key needed)"""
    try:
        r = requests.get(
            f"http://ip-api.com/json/{ip}?fields=status,org,isp,asname,country,city",
            timeout=5
        )
        data = r.json()
        if data.get("status") == "success":
            company = data.get("org") or data.get("isp") or data.get("asname") or "Unknown"
            location = f"{data.get('city', 'Unknown')}, {data.get('country', '')}"
            return company, location, json.dumps(data)
    except:
        pass
    return "Unknown", "Unknown", "{}"

@app.post("/track")
async def track_visitor(request: Request):
    body = await request.json()
    
    ip = body.get("ip") or request.client.host
    page = body.get("page", "Unknown")
    ua = body.get("user_agent", "")

    company, location, extra = enrich_ip(ip)

    timestamp = datetime.now().isoformat()
    
    conn.execute(
        "INSERT INTO visitors (timestamp, ip, page, user_agent, company, location, extra) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (timestamp, ip, page, ua, company, location, extra)
    )
    conn.commit()
    
    return {"status": "logged"}

@app.get("/dashboard", response_class=HTMLResponse)
async def show_dashboard():
    rows = conn.execute(
        "SELECT timestamp, ip, page, company, location FROM visitors ORDER BY timestamp DESC LIMIT 100"
    ).fetchall()
    
    html = """
    <html><head><title>Visitor Monitor</title>
    <style>table {border-collapse: collapse; width: 100%;} th, td {padding: 8px; border: 1px solid #ccc;}</style>
    </head><body>
    <h1>Recent Website Visitors (Company Names)</h1>
    <table>
    <tr><th>Time</th><th>IP</th><th>Page</th><th>Company</th><th>Location</th></tr>
    """
    for row in rows:
        html += f"<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td><td><b>{row[3]}</b></td><td>{row[4]}</td></tr>"
    html += "</table></body></html>"
    return html

if __name__ == "__main__":
    print("🚀 Visitor Monitor running! Visit http://localhost:8000/dashboard")
    uvicorn.run(app, host="0.0.0.0", port=8000)
