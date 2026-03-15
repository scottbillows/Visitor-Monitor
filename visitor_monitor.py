import os
import urllib.parse
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import sqlite3
import requests
import json
from datetime import datetime
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY")

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
    emails TEXT
)
""")

def enrich_ip(ip: str):
    try:
        r = requests.get(
            f"http://ip-api.com/json/{ip}?fields=status,org,isp,asname,country,city",
            timeout=5
        )
        data = r.json()
        if data.get("status") == "success":
            company = data.get("org") or data.get("isp") or data.get("asname") or "Unknown"
            location = f"{data.get('city', 'Unknown')}, {data.get('country', '')}"
            
            # Simple domain guess from company name (improve later if needed)
            domain = None
            if company != "Unknown" and " " in company:
                # e.g., "Microsoft Corporation" -> "microsoft.com"
                words = company.lower().split()
                domain = words[0] + ".com"  # naive, but works often
            
            return company, location, json.dumps(data), domain
    except:
        pass
    return "Unknown", "Unknown", "{}", None

@app.post("/track")
async def track_visitor(request: Request):
    body = await request.json()
    ip = body.get("ip") or request.client.host
    page = body.get("page", "Unknown")
    ua = body.get("user_agent", "")

    company, location, extra, domain = enrich_ip(ip)  # now returns domain too

    emails = []
    if domain and HUNTER_API_KEY:
        try:
            url = f"https://api.hunter.io/v2/domain-search?domain={urllib.parse.quote(domain)}&api_key={HUNTER_API_KEY}"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("data", {}).get("emails"):
                    emails = [e["value"] for e in data["data"]["emails"][:5]]  # top 5 emails
        except Exception as e:
            print(f"Hunter error: {e}")

    timestamp = datetime.utcnow().isoformat()
    
    conn.execute(
        "INSERT INTO visitors (timestamp, ip, page, user_agent, company, location, extra, emails) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (timestamp, ip, page, ua, company, location, extra, json.dumps(emails))
    )
    conn.commit()
    
    return {"status": "logged"}

@app.get("/dashboard", response_class=HTMLResponse)
async def show_dashboard():
    rows = conn.execute(
    "SELECT timestamp, ip, page, company, location, emails FROM visitors ORDER BY timestamp DESC LIMIT 100"
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
