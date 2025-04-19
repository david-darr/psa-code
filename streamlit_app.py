# app.py (Streamlit frontend)
import streamlit as st
import datetime
import os
import time
from student import School, Roster, load_schools, save_schools, sync_from_humanity

# Initialize session state
if 'schools' not in st.session_state:
    st.session_state.schools = load_schools()

if 'last_sync' not in st.session_state:
    st.session_state.last_sync = "Never"

# Auto-sync logic
if 'auto_sync_started' not in st.session_state:
    def auto_sync():
        while True:
            time.sleep(900)  # every 15 minutes
            st.session_state.schools = sync_from_humanity()
            save_schools(st.session_state.schools)
            st.session_state.last_sync = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    import threading
    threading.Thread(target=auto_sync, daemon=True).start()
    st.session_state.auto_sync_started = True

# Page UI
st.set_page_config(page_title="School Schedule App", layout="wide")
st.title("📚 School Scheduler")

view = st.sidebar.radio("Navigate", ["School List", "Calendar", "Sync Log"])

# === School List View ===
if view == "School List":
    st.header("🏫 Schools")
    school_names = [s.name for s in st.session_state.schools]
    selected = st.selectbox("Select School", ["None"] + school_names)

    if selected != "None":
        school = next(s for s in st.session_state.schools if s.name == selected)
        st.subheader("Details")
        st.text(f"Address: {school.address}\nPhone: {school.phone_number}")

        subs = list(school.sub_schools.keys())
        if subs:
            sub = st.selectbox("Select Sport", subs)
            if sub:
                st.text(f"Schedule: {school.sub_schools[sub].schedule}")
                st.text("Roster:")
                for student in school.sub_schools[sub].roster.students:
                    st.markdown(f"- {student}")

# === Calendar View ===
elif view == "Calendar":
    st.header("📅 Calendar")
    today = datetime.date.today()
    for day in range(1, 32):
        try:
            date_obj = today.replace(day=day)
            date_str = date_obj.strftime("%Y-%m-%d")
            entries = []
            for school in st.session_state.schools:
                for sport, sub in school.sub_schools.items():
                    if date_str in sub.schedule:
                        entries.append(f"{school.name} ({sport}): {sub.schedule[date_str]}")
            if entries:
                st.markdown(f"### {date_str}")
                for e in entries:
                    st.markdown(f"- {e}")
        except: break

# === Sync Log ===
elif view == "Sync Log":
    st.header("🔁 Sync Log")
    if st.button("Manual Sync Now"):
        st.session_state.schools = sync_from_humanity()
        save_schools(st.session_state.schools)
        st.session_state.last_sync = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        st.success("Synced!")

    st.markdown(f"**Last Sync:** {st.session_state.last_sync}")

    if os.path.exists("sync_log.txt"):
        with open("sync_log.txt") as f:
            st.text_area("Log", f.read(), height=300)
