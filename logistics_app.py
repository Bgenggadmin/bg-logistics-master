import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import os
import base64
from github import Github
from io import BytesIO
from PIL import Image
import streamlit.components.v1 as components

# --- 1. SETUP ---
IST = pytz.timezone('Asia/Kolkata')
DB_FILE = "logistics_logs.csv"

st.set_page_config(page_title="B&G Logistics", layout="wide")

try:
    REPO_NAME = st.secrets["GITHUB_REPO"]
    TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Secrets missing in Streamlit Cloud!")
    st.stop()

# --- 2. DATA UTILITIES ---
@st.cache_data(ttl=1) 
def load_data():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    return pd.DataFrame(columns=[
        "Timestamp", "Vehicle", "Driver", "Authorized_By", 
        "Start_KM", "End_KM", "Distance", "Fuel_Ltrs", 
        "Purpose", "Location", "Items", "Photo"
    ])

df = load_data()

def save_to_github(dataframe):
    try:
        g = Github(TOKEN)
        repo = g.get_repo(REPO_NAME)
        csv_content = dataframe.to_csv(index=False)
        contents = repo.get_contents(DB_FILE)
        repo.update_file(contents.path, f"Logistics Sync {datetime.now(IST)}", csv_content, contents.sha)
        return True
    except Exception as e:
        st.error(f"GitHub Sync Error: {e}")
        return False

# --- 3. INPUT FORM ---
with st.form("logistics_form", clear_on_submit=True):
    st.subheader("📝 Log Vehicle Movement & Fuel")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        vehicle = st.selectbox("Vehicle", ["Ashok Leyland", "Mahindra"])
        driver = st.selectbox("Driver Name", ["Brahmiah", "Driver", "Other"])
        purpose = st.selectbox("Purpose", ["Inter-Unit (500m)", "Pickup", "Site Delivery", "Fueling"])

    with col2:
        start_km = st.number_input("Start KM Reading", min_value=0, step=1)
        end_km = st.number_input("End KM Reading", min_value=0, step=1)
        fuel_qty = st.number_input("Fuel Added (Litres)", min_value=0.0, step=0.1)

    with col3:
        auth_by = st.text_input("Authorized By", placeholder="e.g. Subodth")
        location = st.text_input("Location", placeholder="e.g. Unit 2 / Shop Name")

    items = st.text_area("Item Details / Remarks")
    cam_photo = st.camera_input("Capture Bill / Odometer / Loading")

    if st.form_submit_button("🚀 SUBMIT LOG"):
        if end_km < start_km and end_km != 0:
            st.error("❌ End KM cannot be less than Start KM!")
        elif not auth_by or not location:
            st.error("❌ Please fill in Authorization and Location.")
        else:
            img_str = ""
            if cam_photo:
                img = Image.open(cam_photo)
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=50) 
                img_str = base64.b64encode(buf.getvalue()).decode()
            
            trip_distance = end_km - start_km if end_km > 0 else 0

            new_log = pd.DataFrame([{
                "Timestamp": datetime.now(IST).strftime('%Y-%m-%d %H:%M'),
                "Vehicle": vehicle, "Driver": driver, "Authorized_By": auth_by.upper(),
                "Start_KM": start_km, "End_KM": end_km, "Distance": trip_distance,
                "Fuel_Ltrs": fuel_qty, "Purpose": purpose, "Location": location.upper(), 
                "Items": items.upper(), "Photo": img_str
            }])
            
            updated_df = pd.concat([df, new_log], ignore_index=True)
            updated_df.to_csv(DB_FILE, index=False)
            
            if save_to_github(updated_df):
                st.cache_data.clear() 
                st.success(f"✅ Logged {trip_distance}km trip by {driver}")
                st.rerun()

# --- 4. THE PROFESSIONAL LEDGER GRID ---
st.divider()
if not df.empty:
    st.subheader("📜 Recent Movement History")
    view_df = df.sort_values(by="Timestamp", ascending=False).head(15)
    
    grid_html = """
    <div style="overflow-x: auto; border: 1px solid #000;">
        <table style="width:100%; border-collapse: collapse; min-width: 850px; font-family: sans-serif;">
            <tr style="background-color: #f2f2f2;">
                <th style="border:1px solid #000; padding:10px;">Time (IST)</th>
                <th style="border:1px solid #000; padding:10px;">Vehicle</th>
                <th style="border:1px solid #000; padding:10px;">Purpose</th>
                <th style="border:1px solid #000; padding:8px;">Location</th>
                <th style="border:1px solid #000; padding:8px;">Distance</th>
                <th style="border:1px solid #000; padding:8px;">Items</th>
                <th style="border:1px solid #000; padding:10px;">Photo</th>
            </tr>
    """
    for _, r in view_df.iterrows():
        p_stat = "✅ Yes" if isinstance(r['Photo'], str) and len(r['Photo']) > 50 else "❌ No"
        grid_html += f"<tr>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{r['Timestamp']}</td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'><b>{r['Vehicle']}</b></td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{r['Purpose']}</td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{r['Location']}</td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{r.get('Distance', 0)} KM</td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{r.get('Items', '')}</td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{p_stat}</td>"
        grid_html += f"</tr>"
    grid_html += "</table></div>"
    components.html(grid_html, height=400, scrolling=True)
else:
    st.info("No movement logs found yet.")
