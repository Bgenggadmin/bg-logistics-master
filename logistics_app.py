import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
from datetime import datetime
import pytz
import base64
from io import BytesIO
from PIL import Image
import streamlit.components.v1 as components

# --- 1. SETUP ---
IST = pytz.timezone('Asia/Kolkata')

st.set_page_config(page_title="B&G Logistics | Supabase", layout="wide")

# Initialize Supabase Connection
try:
    conn = st.connection("supabase", type=SupabaseConnection)
except Exception as e:
    st.error("❌ Supabase Connection Failed. Check your Secrets!")
    st.stop()

# --- 2. DATA UTILITIES ---
@st.cache_data(ttl=1) 
def load_data():
    # Fetch data from Supabase Table
    res = conn.table("logistics_logs").select("*").execute()
    if res.data:
        return pd.DataFrame(res.data)
    return pd.DataFrame(columns=[
        "timestamp", "vehicle", "driver", "authorized_by", 
        "start_km", "end_km", "distance", "fuel_ltrs", 
        "purpose", "location", "items", "photo_path"
    ])

df = load_data()

# Sidebar Refresh
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# --- 3. INPUT FORM ---
with st.form("logistics_form", clear_on_submit=True):
    st.subheader("📝 Log Vehicle Movement & Fuel (Supabase Cloud)")
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
    cam_photo = st.camera_input("Capture Bill / Odometer Photo")

    if st.form_submit_button("🚀 SUBMIT LOG"):
        if end_km < start_km and end_km != 0:
            st.error("❌ End KM cannot be less than Start KM!")
        elif not auth_by or not location:
            st.error("❌ Please fill in Authorization and Location.")
        else:
            # --- OPTIMIZED IMAGE PROCESSING & STORAGE UPLOAD ---
            photo_filename = ""
            if cam_photo:
                img = Image.open(cam_photo)
                img.thumbnail((400, 400)) 
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=40, optimize=True) 
                
                # Generate unique filename
                photo_filename = f"log_{datetime.now(IST).strftime('%Y%m%d_%H%M%S')}.jpg"
                
                # Upload to Supabase Storage
                try:
                    conn.client.storage.from_("logistics-photos").upload(
                        path=photo_filename,
                        file=buf.getvalue(),
                        file_options={"content-type": "image/jpeg"}
                    )
                except Exception as e:
                    st.warning(f"Photo upload failed, but log will continue: {e}")

            trip_distance = end_km - start_km if end_km > 0 else 0

            # Prepare entry for Supabase
            new_entry = {
                "timestamp": datetime.now(IST).strftime('%Y-%m-%d %H:%M'),
                "vehicle": vehicle, 
                "driver": driver, 
                "authorized_by": auth_by.upper(),
                "start_km": start_km, 
                "end_km": end_km, 
                "distance": trip_distance,
                "fuel_ltrs": fuel_qty, 
                "purpose": purpose, 
                "location": location.upper(), 
                "items": items.upper(), 
                "photo_path": photo_filename # Link to storage
            }
            
            # --- INSERT INTO SUPABASE ---
            try:
                conn.table("logistics_logs").insert(new_entry).execute()
                st.cache_data.clear() 
                st.success(f"✅ Logged {trip_distance}km trip by {driver}")
                st.rerun()
            except Exception as e:
                st.error(f"Database Error: {e}")

# --- 4. THE PROFESSIONAL LEDGER GRID ---
st.divider()
if not df.empty:
    st.subheader("📜 Recent Movement History (Cloud Sync)")
    # Normalize column names for display if Supabase changed casing
    view_df = df.sort_values(by="timestamp", ascending=False).head(15)
    
    grid_html = """
    <div style="overflow-x: auto; border: 1px solid #000;">
        <table style="width:100%; border-collapse: collapse; min-width: 1000px; font-family: sans-serif;">
            <tr style="background-color: #f2f2f2;">
                <th style="border:1px solid #000; padding:10px;">Time (IST)</th>
                <th style="border:1px solid #000; padding:10px;">Vehicle</th>
                <th style="border:1px solid #000; padding:10px;">Driver</th>
                <th style="border:1px solid #000; padding:10px;">Authorized By</th>
                <th style="border:1px solid #000; padding:8px;">Fuel (L)</th>
                <th style="border:1px solid #000; padding:8px;">Distance</th>
                <th style="border:1px solid #000; padding:8px;">Items</th>
                <th style="border:1px solid #000; padding:10px;">Photo</th>
            </tr>
    """
    for _, r in view_df.iterrows():
        # Check if photo_path exists in storage link
        p_stat = "✅ Yes" if str(r.get('photo_path', '')) != "" else "❌ No"
        grid_html += f"<tr>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{r['timestamp']}</td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'><b>{r['vehicle']}</b></td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{r.get('driver', 'N/A')}</td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{r.get('authorized_by', 'N/A')}</td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{r.get('fuel_ltrs', 0)} L</td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{r.get('distance', 0)} KM</td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{r.get('items', '')}</td>"
        grid_html += f"<td style='border:1px solid #000; padding:8px;'>{p_stat}</td>"
        grid_html += f"</tr>"
    grid_html += "</table></div>"
    components.html(grid_html, height=450, scrolling=True)

    # --- 5. PHOTO SELECTION VIEWER ---
    st.write("---")
    st.subheader("🔍 View Bill / Odometer Photo")
    photo_df = df[df["photo_path"].astype(str).str.len() > 2].copy()
    if not photo_df.empty:
        photo_df = photo_df.sort_values(by="timestamp", ascending=False)
        options = {i: f"{r['timestamp']} | {r['vehicle']} | {r['driver']}" for i, r in photo_df.iterrows()}
        selection = st.selectbox("Select trip:", options.keys(), format_func=lambda x: options[x])
        
        if selection is not None:
            file_path = photo_df.loc[selection, "photo_path"]
            # Generate Public URL from Supabase Storage
            img_url = conn.client.storage.from_("logistics-photos").get_public_url(file_path)
            st.image(img_url, width=400, caption=f"Verified Image: {file_path}")
else:
    st.info("No movement logs found yet.")
