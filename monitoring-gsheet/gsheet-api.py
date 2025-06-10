from fastapi import FastAPI, Request, Header, HTTPException
import psycopg2
import datetime

app = FastAPI()

@app.post("/update-grievance")
async def update_grievance(request: Request, authorization: str = Header(None)):
    if authorization != "Bearer YOUR_API_TOKEN":
        raise HTTPException(status_code=403, detail="Invalid token")

    data = await request.json()

    conn = psycopg2.connect("dbname=yourdb user=youruser password=yourpass host=yourhost")
    cur = conn.cursor()

    cur.execute("""
        UPDATE grievances
        SET 
            user_full_name = %s,
            user_contact_phone = %s,
            user_municipality = %s,
            user_village = %s,
            user_address = %s,
            grievance_details = %s,
            grievance_summary = %s,
            grievance_categories = %s,
            grievance_creation_date = %s,
            status = %s
        WHERE grievance_id = %s
    """, (
        data["user_full_name"],
        data["user_contact_phone"],
        data["user_municipality"],
        data["user_village"],
        data["user_address"],
        data["grievance_details"],
        data["grievance_summary"],
        data["grievance_categories"],
        data["grievance_creation_date"],
        data["status"],
        data["grievance_id"]
    ))

    conn.commit()
    cur.close()
    conn.close()

    return {"status": "grievance updated"}
