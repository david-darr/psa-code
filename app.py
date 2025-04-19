# streamlit_app.py
import streamlit as st
import json
import datetime
from PIL import Image
import pytesseract
import os
import threading
import time
from student import School, Student, Roster, SubSchool, normalize_name, load_schools, save_schools, sync_from_humanity
import student

# Initial Load
if 'schools' not in st.session_state:
    st.session_state.schools = load_schools()

if 'last_sync_time' not in st.session_state:
    st.session_state.last_sync_time = None

st.set_page_config(page_title="David's Magic Program", layout="wide")
st.title("🎩 David's Magic Program")

# Sidebar Navigation
st.sidebar.header("Navigation")
view = st.sidebar.radio("Go to", ["School List", "Calendar View", "Sync Log"])

school_names = [school.name for school in st.session_state.schools]

def get_school_by_name(name):
    for s in st.session_state.schools:
        if s.name == name:
            return s

def refresh_data():
    save_schools(st.session_state.schools)

def sync_now():
    try:
        st.session_state.schools = sync_from_humanity(st.session_state.schools)
        save_schools(st.session_state.schools)
        st.session_state.last_sync_time = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    except Exception as e:
        st.error(f"Sync failed: {e}")

def auto_sync():
    while True:
        try:
            time.sleep(900)  # 15 minutes
            st.session_state.schools = sync_from_humanity(st.session_state.schools)
            save_schools(st.session_state.schools)
            st.session_state.last_sync_time = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        except Exception as e:
            print(f"Auto-sync failed: {e}")

# Launch background auto-sync thread only once
if 'auto_sync_started' not in st.session_state:
    threading.Thread(target=auto_sync, daemon=True).start()
    st.session_state.auto_sync_started = True

# School List Tab
if view == "School List":
    st.header("🏫 School List")

    selected_school_name = st.selectbox("Select a School", ["None"] + school_names)
    if selected_school_name != "None":
        school = get_school_by_name(selected_school_name)

        st.subheader("Basic Info")
        st.write(f"**Name:** {school.name}")
        st.write(f"**Address:** {school.address}")
        st.write(f"**Phone:** {school.phone_number}")

        if school.sub_schools:
            selected_sport = st.selectbox("Select a Sport/SubSchool", ["None"] + list(school.sub_schools.keys()))
            if selected_sport != "None":
                subschool = school.sub_schools[selected_sport]

                st.subheader(f"📘 {selected_sport} Info")

                st.markdown("**📅 Schedule**")
                for date, time in sorted(subschool.schedule.items()):
                    st.markdown(f"- **{date}**: {time}")

                st.markdown("**📋 Roster**")
                with st.container():
                    roster_scroll = st.container()
                    with roster_scroll:
                        for i, student in enumerate(subschool.roster.students):
                            st.markdown(f"{i+1}. {student.first_name} {student.last_name}")

                # Edit Button and Panel
                if st.button("✏️ Edit Info"):
                    st.session_state.show_edit_panel = not st.session_state.get("show_edit_panel", False)

                if st.session_state.get("show_edit_panel", False):
                    st.subheader("🔧 Edit Options")

                    # Edit Schedule
                    st.markdown("**Edit Weekly Schedule**")
                    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                    for day in weekdays:
                        subschool.schedule[day] = st.text_input(f"{day} shift time", value=subschool.schedule.get(day, ""))
                    if st.button("Save Weekly Schedule"):
                        refresh_data()
                        st.success("Schedule updated!")

                    # Add Roster
                    st.markdown("**Add Roster Image**")
                    uploaded_file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])
                    if uploaded_file:
                        img = Image.open(uploaded_file)
                        subschool.roster.load_from_image(uploaded_file)
                        refresh_data()
                        st.success("Roster updated successfully.")

                    # Delete Roster
                    if st.button("🗑️ Delete Entire Roster"):
                        subschool.roster = Roster()
                        refresh_data()
                        st.warning("Roster deleted.")

                    # Edit School Info
                    st.markdown("**Edit School Info**")
                    name = st.text_input("Edit Name", value=school.name)
                    address = st.text_input("Edit Address", value=school.address)
                    phone = st.text_input("Edit Phone", value=school.phone_number)
                    if st.button("Save School Info"):
                        school.name = name
                        school.address = address
                        school.phone_number = phone
                        refresh_data()
                        st.success("School info updated!")

                    # Delete Subschool
                    if st.button(f"🗑️ Delete {selected_sport} SubSchool"):
                        del school.sub_schools[selected_sport]
                        refresh_data()
                        st.warning(f"{selected_sport} SubSchool deleted.")
                        st.rerun()

        # Add SubSchool section
        st.subheader("➕ Add Sport/SubSchool")
        new_sport = st.text_input("Enter new sport name")
        if st.button("Add Sport"):
            if new_sport and new_sport not in school.sub_schools:
                school.add_sub_school(new_sport)
                refresh_data()
                st.success(f"Sport '{new_sport}' added.")
                st.rerun()

        if st.button(f"🗑️ Delete {school.name} School"):
            st.session_state.schools.remove(school)
            refresh_data()
            st.warning(f"{school.name} deleted.")
            st.rerun()

    st.subheader("+ Add School")
    with st.form("add_school_form"):
        name = st.text_input("School Name")
        address = st.text_input("Address")
        phone = st.text_input("Phone Number")
        sports = st.multiselect("Assign Sports", ["Soccer", "Basketball", "Tennis", "Track", "Volleyball", "General"])
        submitted = st.form_submit_button("Add School")
        if submitted:
            new_school = School(name, address, phone)
            for sport in sports:
                new_school.add_sub_school(sport)
            st.session_state.schools.append(new_school)
            refresh_data()
            st.success("School added!")
            st.rerun()

    if st.button("🗑️ Delete All Schools"):
        st.session_state.schools.clear()
        refresh_data()
        st.success("All schools deleted.")
        st.rerun()

# Calendar View
elif view == "Calendar View":
    st.header("📆 Calendar")
    month = st.selectbox("Select Month", range(1, 13), index=datetime.date.today().month - 1)
    year = st.selectbox("Select Year", range(datetime.date.today().year, datetime.date.today().year + 2))
    st.markdown("---")

    cal = datetime.date(year, month, 1)
    month_days = (datetime.date(year + int(month == 12), (month % 12) + 1, 1) - cal).days

    for day in range(1, month_days + 1):
        date_str = datetime.date(year, month, day).strftime('%Y-%m-%d')
        entries = []
        for school in st.session_state.schools:
            for sport, subschool in school.sub_schools.items():
                if date_str in subschool.schedule:
                    entries.append(f"- **{school.name} ({sport})**: {subschool.schedule[date_str]}")
        if entries:
            st.markdown(f"### {date_str}")
            for e in entries:
                st.markdown(e)

# Sync Log View
elif view == "Sync Log":
    st.header("🔁 Sync Log Viewer")
    if st.button("🔁 Refresh Humanity Now"):
        sync_now()
        st.success("Synced with Humanity!")
        st.rerun()

    if os.path.exists("sync_log.txt"):
        with open("sync_log.txt", "r") as f:
            log = f.read()
            st.text_area("Log", log, height=300)
    else:
        st.info("No log file found.")

    if st.session_state.last_sync_time:
        st.markdown(f"**Last Auto-Sync:** {st.session_state.last_sync_time}")
