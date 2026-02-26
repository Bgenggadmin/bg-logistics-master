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

try:
    REPO_NAME = st.secrets["GITHUB_REPO"]
    TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Secrets missing in Streamlit Cloud!")
    st.stop()

st.set_page_config(page_title="B&G Logistics", layout="wide")

# --- 2. DATA UTILITIES ---
def load_data():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    return pd.DataFrame(columns=["Timestamp", "Vehicle", "Purpose", "Item_Details", "Location", "Photo"])

def save_to_github(dataframe):
    try:
        g = Github(TOKEN)
        repo = g.get_repo(REPO_NAME)
        csv_content = dataframe.to_csv(index=False)
        contents = repo.get_contents(DB_FILE)
        repo.update_file(contents.path, f"Logistics Sync {datetime.now(IST)}", csv_content, contents.sha)
        return True
    except: return False

df = load_data()

# --- 3. INPUT FORM ---
st.title("🚛 B&G Logistics & Inter-Unit Tracker")

with st.form("logistics_form", clear_on_submit=True):
    st.subheader("📝 Log Vehicle Movement")
    col1, col2 = st.columns(2)
    
    with col1:
        vehicle = st.selectbox("Select Vehicle", ["Ashok Leyland", "Mahindra"])
        purpose = st.selectbox("Purpose", [
            "Inter-Unit Transfer (500m)", 
            "Consumable Pickup (Vendor)", 
            "Machining Item Pickup", 
            "MEE Site Delivery",
            "Fueling / Service"
        ])
    
    with col2:
        location = st.text_input("Destination / Vendor Name (e.g. Unit 2, MEE Site, Shop Name)")
        items = st.text_area("Item Details (e.g. 5kg Electrodes, SSR501 Shell, Grinding Wheels)")

    cam_photo = st.camera_input("Capture Challan / Bill / Loading Photo")

    if st.form_submit_button("🚀 SUBMIT LOG"):
        if not items or not location:
            st.error("❌ Please enter Item Details and Location.")
        else:
            img_str = ""
            if cam_photo:
                img = Image.open(cam_photo)
                buffered = BytesIO()
                img.save(buffered, format="JPEG", quality=50) # Compression for space
                img_str = base64.b64encode(buffered.getvalue()).decode()
            
            new_log = pd.DataFrame([{
                "Timestamp": datetime.now(IST).strftime('%Y-%m-%d %H:%M'),
                "Vehicle": vehicle, "Purpose": purpose,
                "Item_Details": items.upper(), "Location": location.upper(), 
                "Photo": img_str
            }])
            
            updated_df = pd.concat([df, new_log], ignore_index=True)
            updated_df.to_csv(DB_FILE, index=False)
            if save_to_github(updated_df):
                st.success(f"✅ Logged: {vehicle} moving {purpose}")
                st.rerun()

# --- 4. THE PROFESSIONAL LEDGER GRID ---
st.divider()
if not df.empty:
    st.subheader("📜 Recent Movement History")
    view_df = df.sort_values(by="Timestamp", ascending=False).head(15)
    
    # Grid CSS
    grid_html = """
    <div style="overflow-x: auto; border: 1px solid #000;">
        <table style="width:100%; border-collapse: collapse; min-width: 850px; font-family: sans-serif;">
            <tr style="background-color: #f2f2f2;">
                <th style="border:1px solid #000; padding:10px;">Time (IST)</th>
                <th style="border:1px solid #000; padding:10px;">Vehicle</th>
                <th style="border:1px solid #000; padding:10px;">Purpose</th>
                <th style="border:1px solid #000; padding:8px;">Location</th>
                <th style="border:1px solid #000; padding:8px;">Items</th>
                <th style="border:1px solid #000; padding:10px;">Photo</th>
            </tr>
    """
    for _, r in view_df.iterrows():
        p_stat = "✅ Yes" if len(str(r['Photo'])) > 50 else "❌ No"
        grid_html += f"<tr><td style='border:1px solid #000; padding:8px;'>{r['Timestamp']}</td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'><b>{r['Vehicle']}</b></td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{r['Purpose']}</td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{r['Location']}</td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{r['Item_Details']}</td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{p_stat}</td></tr>"
    grid_html += "</table></div>"
    components.html(grid_html, height=400, scrolling=True)

    # --- 5. PHOTO SELECTION VIEWER ---
    st.write("---")
    st.subheader("🔍 View Bill / Challan Photo")
    photo_df = df[df["Photo"].astype(str).str.len() > 50].copy()
    if not photo_df.empty:
        photo_df = photo_df.sort_values(by="Timestamp", ascending=False)
        options = {i: f"{r['Timestamp']} | {r['Vehicle']} | {r['Location']}" for i, r in photo_df.iterrows()}
        selection = st.selectbox("Select a record to view photo:", options.keys(), format_func=lambda x: options[x])
        if selection is not None:
            st.image(base64.b64decode(photo_df.loc[selection, "Photo"]), use_container_width=True)
else:
    st.info("No movement logs found yet.")
