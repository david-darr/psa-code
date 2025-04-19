import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from PIL import Image
import pytesseract
import re
import json
import os
import calendar
import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
import time
import pytz

# === Globals/Commands ===
pytesseract.pytesseract.tesseract_cmd = r"C:\\Users\\David\\AppData\\Local\\Programs\\Tesseract-OCR/tesseract.exe"
SYNC_LOG_FILE = "sync_log.txt"
SYNC_META_FILE = "last_sync.txt"

  
# Accessing Humanity
from selenium.webdriver.chrome.options import Options

# To get a schools base name
def normalize_name(name):
    # Strips sport suffix and standardizes whitespace/case
    if " - " in name:
        base_name = name.split(" - ")[0]
    else:
        base_name = name
    return base_name.strip().lower()


def sync_from_humanity():
    shift_data = []

    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=chrome_options)

        driver.get("https://www.humanity.com/app/")
        time.sleep(2)
        driver.find_element(By.ID, "email").send_keys("21316153cc853d45b8200f852ea277eb")
        driver.find_element(By.ID, "password").send_keys("15079David")
        driver.find_element(By.NAME, "login").click()
        time.sleep(2)

        driver.get("https://richardburke1.humanity.com/app/schedule/list/month/employee/employee/18%2c3%2c2025/")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        shift_rows = driver.find_elements(By.CSS_SELECTOR, "tr.shiftrow")

        def extract_date(class_list):
            for cls in class_list:
                if cls.startswith("tl_"):
                    try:
                        parts = cls.replace("tl_", "").split("__")
                        date_str = parts[0] + " " + parts[1]
                        date_obj = datetime.datetime.strptime(date_str, "%b_%d %Y")
                        return date_obj.strftime("%Y-%m-%d")
                    except:
                        return None
            return None

        def is_valid_address(text):
            # Regular expression to match common address patterns
            address_pattern = r"\d+\s+\w+(\s+\w+)*\s+(St|Ave|Rd|Blvd|Dr|Ln|Way|Ct|Circle|Pl|Terrace|Pkwy|Highway|Hwy|Loop|Square|Sq|Trail|Trl|Drive|Street|Avenue|Road|Boulevard|Place|Lane|Way|Court|Parkway|Circle|Terrace)\b"
            return re.search(address_pattern, text, re.IGNORECASE) is not None

        for row in shift_rows:
            try:
                class_list = row.get_attribute("class").split()
                date_key = extract_date(class_list)
                if not date_key:
                    continue

                time_text = row.find_element(By.CSS_SELECTOR, "td.second").text.strip().split("\n")[-1]
                school_and_address = row.find_element(By.CSS_SELECTOR, "td.fourth").text.strip()

                # Split the text to extract school name and address
                parts = school_and_address.split("\n")  # Adjust the delimiter if necessary
                school_name = parts[0].strip() if len(parts) > 0 else "Unknown School"
                raw_address = parts[1].strip() if len(parts) > 1 else ""

                # Validate the address
                address = raw_address if is_valid_address(raw_address) else "Unknown Address"

                shift_data.append({
                    "school": school_name,
                    "date": date_key,
                    "time": time_text,
                    "address": address
                })
            except Exception as e:
                append_log(f"⚠️ Error reading row: {e}")

    except Exception as e:
        append_log(f"❌ Sync failed: {e}")
        messagebox.showerror("Error", f"Sync failed: {e}")
    finally:
        driver.quit()

    # Group and add data
    updated = 0
    added = 0

    # List of common sports to check for in the school name
    common_sports = {"soccer", "basketball", "yoga", "football", "volleyball", "tennis", "track", "running", "chess"}

    for shift in shift_data:
        full_name = shift["school"]
        date_key = shift["date"]
        time_val = shift["time"]
        address = shift["address"]

        # Check if a sport is in the name
        sport = "General"
        base_name = full_name
        for sport_name in common_sports:
            if sport_name.lower() in full_name.lower():
                sport = sport_name.capitalize()
                base_name = full_name.lower().replace(sport_name.lower(), "").strip()
                break

        # Normalize the base name
        normalized_name = normalize_name(base_name)

        # Find an existing school by normalized base name or create a new one
        match = next((s for s in schools if normalize_name(s.name) == normalized_name), None)
        if not match:
            match = School(name=base_name.title(), address=address, phone_number="Unknown Phone Number")
            schools.append(match)
            added += 1

        # Add sub_school if necessary and update its schedule
        if sport not in match.sub_schools:
            match.add_sub_school(sport)
        previous_entry = match.sub_schools[sport].schedule.get(date_key)
        match.sub_schools[sport].schedule[date_key] = time_val
        if previous_entry:
            updated += 1
        else:
            added += 1  # new shift entry

    save_schools()
    refresh_school_list()
    refresh_school_info()
    refresh_calendar()

    status = f"✅ Sync complete – {updated} shifts updated, {added} new entries added."
    last_sync_time = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    sync_status_label.config(text=f"Last sync: {last_sync_time}")

    with open(SYNC_META_FILE, "w") as f:
        f.write(last_sync_time)

    append_log(status)
    print(status)



# === Student Class ===
class Student:
    def __init__(self, first_name, last_name):
        self.first_name = first_name
        self.last_name = last_name

    def to_dict(self):
        return {
            "first_name": self.first_name, "last_name": self.last_name}

    @staticmethod
    def from_dict(data):
        return Student(data['first_name'], data['last_name'])

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

# === Roster Class ===
class Roster:
    def __init__(self):
        self.students = []

    def add_student(self, student):
        self.students.append(student)

    def remove_student(self, student_name):
        self.students = [s for s in self.students if str(s) != student_name]

    def load_from_image(self, image_path):
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)

        lines = text.split('\n')
        buffer = ""

        for line in lines:
            line = line.strip()

            # Skip empty lines and header rows
            if not line or "first name" in line.lower() or "last name" in line.lower():
                continue

            # Try to split name if it contains "|"
            if "|" in line:
                parts = [part.strip() for part in line.split("|")]
                if len(parts) == 2:
                    first = parts[0].title()
                    last = parts[1].title()
                    self.add_student(Student(first, last))
                    continue

            # Handle normal names
            cleaned = re.sub(r'[^A-Za-z\s\-]', '', line).strip()
            parts = cleaned.split()

            if len(parts) >= 2:
                first = parts[0].title()
                last = ' '.join(parts[1:]).title()
                self.add_student(Student(first, last))


    def to_dict(self):
        return [s.to_dict() for s in self.students]

    @staticmethod
    def from_dict(data):
        roster = Roster()
        for student_data in data:
            roster.add_student(Student.from_dict(student_data))
        return roster

    def __str__(self):
        return "\n".join(f"{i+1}. {s}" for i, s in enumerate(self.students))


# === SubSchool Class ===
class SubSchool:
    def __init__(self, sport):
        self.sport = sport
        self.roster = Roster()  # Manages students
        self.schedule = {}      # Mapping: date -> time
        
    def to_dict(self):
        return {
            "sport": self.sport,
            "roster": self.roster.to_dict(),
            "schedule": self.schedule
        }
        
    @staticmethod
    def from_dict(data):
        sub_school = SubSchool(data.get("sport", "General"))
        sub_school.roster = Roster.from_dict(data.get("roster", []))
        sub_school.schedule = data.get("schedule", {})
        return sub_school

    def __str__(self):
        return f"Session: {self.sport}\nSchedule: {self.schedule}\nRoster: {self.roster}"


# === School Class ===
class School:
    def __init__(self, name, address, phone_number):
        self.name = name
        self.address = address
        self.phone_number = phone_number
        self.sub_schools = {}  # key = sport, value = SubSchool instance

    def add_sub_school(self, sport):
        if sport not in self.sub_schools:
            self.sub_schools[sport] = SubSchool(sport)

    def load_roster_from_image(self, image_path, sport):
        self.add_sub_school(sport)
        self.sub_schools[sport].roster.load_from_image(image_path)

    def to_dict(self):
        return {
            "name": self.name,
            "address": self.address,
            "phone_number": self.phone_number,
            "sub_schools": {
                sport: sub_school.to_dict() for sport, sub_school in self.sub_schools.items()
            }
        }

    @staticmethod
    def from_dict(data):
        school = School(
            data.get('name', ''),
            data.get('address', ''),
            data.get('phone_number', '')
        )
        for sport, sub_data in data.get("sub_schools", {}).items():
            school.sub_schools[sport] = SubSchool.from_dict(sub_data)
        return school

    def __str__(self):
        return f"{self.name}\n{self.address}\n{self.phone_number}"



# === Load/Save Functions ===
DATA_FILE = "schools_data.json"

def save_schools(schools_override=None):
    global schools
    consolidated = {}

    data_to_save = schools_override if schools_override is not None else schools
    for s in data_to_save:
        base_name = normalize_name(s.name)
        if base_name not in consolidated:
            consolidated[base_name] = s
        else:
            existing = consolidated[base_name]
            # Use sub_schools instead of sports_data
            for sport, sub in s.sub_schools.items():
                if sport not in existing.sub_schools:
                    existing.sub_schools[sport] = sub
                else:
                    existing.sub_schools[sport].schedule.update(sub.schedule)
                    for student in sub.roster.students:
                        if str(student) not in map(str, existing.sub_schools[sport].roster.students):
                            existing.sub_schools[sport].roster.add_student(student)

    sorted_schools = sorted(consolidated.values(), key=lambda s: s.name.lower())
    with open(DATA_FILE, 'w') as f:
        json.dump([s.to_dict() for s in sorted_schools], f, indent=2)

    if schools_override is None:
        schools = list(consolidated.values())




def load_schools():
    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, 'r') as f:
        raw_data = json.load(f)

    consolidated = {}

    for item in raw_data:
        school = School.from_dict(item)
        base_name = normalize_name(school.name)

        if base_name not in consolidated:
            consolidated[base_name] = school
        else:
            existing = consolidated[base_name]
            for sport, sub in school.sub_schools.items():
                if sport not in existing.sub_schools:
                    existing.sub_schools[sport] = sub
                else:
                    existing.sub_schools[sport].schedule.update(sub.schedule)
                    for student in sub.roster.students:
                        if str(student) not in map(str, existing.sub_schools[sport].roster.students):
                            existing.sub_schools[sport].roster.add_student(student)
    return list(consolidated.values())


# Load schools
schools = load_schools()
__all__ = ['schools']


# === GUI Setup ===
root = tk.Tk()
root.title("School Roster Viewer")
root.geometry("850x600")

notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True)

# === Tab 1: Roster Viewer ===
roster_tab = tk.Frame(notebook)
notebook.add(roster_tab, text="List of Schools")

left_frame = tk.Frame(roster_tab)
left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

school_listbox = tk.Listbox(left_frame, height=20, width=30)
school_listbox.pack()

button_frame = tk.Frame(left_frame)
button_frame.pack(pady=5)

tk.Button(button_frame, text="+ Add School", command=lambda: add_school()).pack(fill=tk.X)
tk.Button(button_frame, text="- Delete School", command=lambda: delete_school()).pack(fill=tk.X)
tk.Button(button_frame, text="✎ Edit School Info", command=lambda: edit_school_info()).pack(fill=tk.X)
tk.Button(button_frame, text="🎯 Add Sport(s)", command=lambda: assign_sports()).pack(fill=tk.X)
tk.Button(button_frame, text="🗑️ Delete Sport", command=lambda: delete_sub_school()).pack(fill=tk.X)
tk.Button(button_frame, text="📅 Edit Weekly Schedule", command=lambda: edit_school_schedule()).pack(fill=tk.X)
tk.Button(button_frame, text="+ Add Roster Image", command=lambda: upload_roster_image()).pack(fill=tk.X)
tk.Button(button_frame, text="🗑️ Delete Roster", command=lambda: delete_roster()).pack(fill=tk.X)
tk.Button(button_frame, text="- Remove Student", command=lambda: remove_student()).pack(fill=tk.X)
tk.Button(button_frame, text="🔁 Refresh Humanity Now", command=lambda: run_manual_sync()).pack(fill=tk.X)
tk.Button(button_frame, text="🗑️ Delete All Schools", command=lambda: delete_all_schools()).pack(fill=tk.X)



right_frame = tk.Frame(roster_tab)
right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

text_scrollbar = tk.Scrollbar(right_frame)
text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

info_text = tk.Text(right_frame, wrap=tk.WORD, yscrollcommand=text_scrollbar.set, font=("Arial", 12))
info_text.pack(fill=tk.BOTH, expand=True)
text_scrollbar.config(command=info_text.yview)

# === Tab 2: Monthly Calendar ===
calendar_tab = tk.Frame(notebook)
notebook.add(calendar_tab, text="Calendar")

clock_label = tk.Label(calendar_tab, font=("Arial", 14), fg="blue")
clock_label.pack(pady=(10, 0))

def update_clock():
    eastern = pytz.timezone("US/Eastern")
    now_est = datetime.datetime.now(eastern)
    clock_label.config(text=now_est.strftime("Current Eastern Time: %I:%M:%S %p"))
    clock_label.after(1000, update_clock)

eastern = pytz.timezone("US/Eastern")
now_est = datetime.datetime.now(eastern)


update_clock()


calendar_frame = tk.Frame(calendar_tab)
calendar_frame.pack(padx=10, pady=10, expand=True, fill=tk.BOTH)

sync_status_label = tk.Label(calendar_tab, text="Last sync: Never", font=("Arial", 10), fg="gray")
sync_status_label.pack(pady=(5, 0))

now = datetime.datetime.now()
current_year = now.year
current_month_num = now.month

def open_day_tab(day):
    date_obj = datetime.date(current_year, current_month_num, day)
    date_str = date_obj.strftime("%Y-%m-%d")

    day_tab = tk.Toplevel(root)
    day_tab.title(f"{calendar.month_name[current_month_num]} {day}, {current_year}")
    day_tab.geometry("350x300")

    tk.Label(day_tab, text=f"Shifts for {date_str}", font=("Arial", 14)).pack(pady=10)

    found = False
    for school in schools:
        for sport, sub_school in school.sub_schools.items():
            if date_str in sub_school.schedule:
                time = sub_school.schedule[date_str]
                if time and time != ":-:":
                    tk.Label(day_tab, text=f"{school.name} ({sport}): {time}", font=("Arial", 12)).pack(anchor="w", padx=10)
                    found = True

    if not found:
        tk.Label(day_tab, text="No schools scheduled.", font=("Arial", 12, "italic")).pack(pady=10)


def draw_calendar(year, month):
    for widget in calendar_frame.winfo_children():
        widget.destroy()

    cal = calendar.Calendar()
    tk.Label(calendar_frame, text=f"{calendar.month_name[month]} {year}", font=("Arial", 16, "bold")).grid(row=0, column=0, columnspan=7, pady=10)

    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for i, day in enumerate(days):
        tk.Label(calendar_frame, text=day, font=("Arial", 12)).grid(row=1, column=i)

    row = 2
    col = 0
    today = datetime.datetime.now().day if month == datetime.datetime.now().month and year == datetime.datetime.now().year else None
    for day in cal.itermonthdays(year, month):
        if day == 0:
            tk.Label(calendar_frame, text="").grid(row=row, column=col)
        else:
            b = tk.Button(calendar_frame, text=str(day), width=4, command=lambda d=day: open_day_tab(d))
            if today == day:
                b.config(bg='lightblue')
            b.grid(row=row, column=col, padx=2, pady=2)
        col += 1
        if col > 6:
            col = 0
            row += 1
    
    # === Side panel for rest of week schedule ===
    week_schedule_frame = tk.Frame(calendar_frame)
    week_schedule_frame.grid(row=row+1, column=0, columnspan=7, pady=10)

    tk.Label(week_schedule_frame, text="This Week's Remaining Schedule", font=("Arial", 12, "bold")).pack(anchor="w")

    eastern = pytz.timezone("US/Eastern")
    now_est = datetime.datetime.now(eastern)
    today = now_est.date()

    for i in range(0, 7 - today.weekday()):  # Include today to Sunday
        date_obj = today + datetime.timedelta(days=i)
        date_str = date_obj.strftime("%Y-%m-%d")
        day_label = date_obj.strftime("%A")

        schools_today = []
        for s in schools:
            for sport, sub_school in s.sub_schools.items():
                shift_time = sub_school.schedule.get(date_str, "")  # Access schedule from SubSchool
                if shift_time:
                    if i > 0:
                        schools_today.append((f"{s.name} ({sport})", shift_time))  # Future day
                    else:
                        # Only show today's if it's still upcoming
                        try:
                            shift_start = shift_time.split("-")[0].strip().lower()
                            shift_dt = datetime.datetime.strptime(shift_start, "%I:%M%p").time()
                            if now_est.time() < shift_dt:
                                schools_today.append((f"{s.name} ({sport})", shift_time))
                        except Exception as e:
                            print(f"⚠️ Error parsing time for {s.name}: {e}")

        if schools_today:
            tk.Label(week_schedule_frame, text=f"{day_label} ({date_str}):", font=("Arial", 11, "underline")).pack(anchor="w", pady=(5, 0))
            for name, time_str in schools_today:
                tk.Label(week_schedule_frame, text=f"  {name}: {time_str}", font=("Arial", 10)).pack(anchor="w")

draw_calendar(current_year, current_month_num)

def refresh_calendar():
    draw_calendar(current_year, current_month_num)


# === Tab 3: Sync Log Viewer ===
log_tab = tk.Frame(notebook)
notebook.add(log_tab, text="Sync Log")

log_text = tk.Text(log_tab, wrap=tk.WORD, font=("Consolas", 10))
log_text.pack(fill=tk.BOTH, expand=True)

# === Load sync log and last sync time if available ===
if os.path.exists(SYNC_LOG_FILE):
    with open(SYNC_LOG_FILE, "r", encoding="utf-8") as f:
        log_text.insert(tk.END, f.read())
        log_text.see(tk.END)

if os.path.exists(SYNC_META_FILE):
    with open(SYNC_META_FILE, "r") as f:
        last_time = f.read().strip()
        sync_status_label.config(text=f"Last sync: {last_time}")

def append_log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    log_entry = f"[{timestamp}] {message}"
    log_text.insert(tk.END, log_entry + "\n")
    log_text.see(tk.END)

    with open(SYNC_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry + "\n")



# === GUI Logic ===

def refresh_school_list():
    global sorted_school_list
    school_listbox.delete(0, tk.END)
    sorted_school_list = sorted(schools, key=lambda s: s.name.lower())  # Ensure sorted_school_list is updated
    for school in sorted_school_list:
        school_listbox.insert(tk.END, school.name)

refresh_school_list()

def refresh_school_info():
    on_school_select(None)


def display_school_info(selected_school, sport, sport_window):
    if sport_window:
        sport_window.destroy()
    
    full_info = f"{selected_school.name}\n{selected_school.address}\n{selected_school.phone_number}\n\n"
    
    sub_school = selected_school.sub_schools[sport]
    full_info += f"🏅 Sport: {sport}\n"
    full_info += "\nSchedule:\n"
    for date, time in sorted(sub_school.schedule.items()):
        full_info += f"  {date}: {time}\n"
    full_info += f"\nRoster (Total Students: {len(sub_school.roster.students)}):\n"
    full_info += str(sub_school.roster) + "\n\n"
    
    info_text.delete("1.0", tk.END)
    info_text.insert(tk.END, full_info)


def on_school_select(event):
    selection = school_listbox.curselection()
    if selection:
        index = selection[0]
        selected_school = sorted_school_list[index]  # Use sorted_school_list to get the correct school
        
        # If there's more than one session, open a popup to select one:
        if len(selected_school.sub_schools) > 1:
            sport_window = tk.Toplevel(root)
            sport_window.title(f"Select Session for {selected_school.name}")
            sport_window.geometry("300x400")
            tk.Label(sport_window, text=f"Select session for {selected_school.name}:", font=("Arial", 12)).pack(pady=10)
            for sport in selected_school.sub_schools.keys():
                tk.Button(sport_window, text=sport,
                          command=lambda s=sport: display_school_info(selected_school, s, sport_window)
                         ).pack(fill=tk.X, pady=5)
        else:
            sport = list(selected_school.sub_schools.keys())[0] if selected_school.sub_schools else "General"
            display_school_info(selected_school, sport, None)


school_listbox.bind("<<ListboxSelect>>", on_school_select)

def upload_roster_image():
    selection = school_listbox.curselection()
    if not selection:
        messagebox.showinfo("Select School", "Please select a school first.")
        return

    selected_school = schools[selection[0]]

    # If there are multiple sub-schools, prompt the user to select one
    if len(selected_school.sub_schools) > 1:
        sport_window = tk.Toplevel(root)
        sport_window.title(f"Select Sport for {selected_school.name}")
        sport_window.geometry("300x400")

        tk.Label(sport_window, text=f"Select a sport for {selected_school.name}:", font=("Arial", 12)).pack(pady=10)

        for sport in selected_school.sub_schools.keys():
            tk.Button(
                sport_window,
                text=sport,
                command=lambda s=sport: upload_roster_for_sport(selected_school, s, sport_window)
            ).pack(fill=tk.X, pady=5)
    else:
        # If there's only one sub-school, use it directly
        sport = list(selected_school.sub_schools.keys())[0] if selected_school.sub_schools else "General"
        upload_roster_for_sport(selected_school, sport, None)


def upload_roster_for_sport(school, sport, window):
    if window:
        window.destroy()

    file_path = filedialog.askopenfilename(
        title="Select Roster Image",
        filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff")]
    )

    if file_path:
        school.load_roster_from_image(file_path, sport)
        save_schools()
        on_school_select(None)
        messagebox.showinfo("Success", f"Roster updated for {school.name} ({sport}).")

def delete_roster():
    selection = school_listbox.curselection()
    if not selection:
        messagebox.showinfo("Select School", "Please select a school first.")
        return

    selected_school = schools[selection[0]]

    # If there are multiple sub-schools, prompt the user to select one
    if len(selected_school.sub_schools) > 1:
        sport_window = tk.Toplevel(root)
        sport_window.title(f"Select Sport for {selected_school.name}")
        sport_window.geometry("300x400")

        tk.Label(sport_window, text=f"Select a sport to delete the roster for {selected_school.name}:", font=("Arial", 12)).pack(pady=10)

        for sport in selected_school.sub_schools.keys():
            tk.Button(
                sport_window,
                text=sport,
                command=lambda s=sport: confirm_delete_roster(selected_school, s, sport_window)
            ).pack(fill=tk.X, pady=5)
    else:
        # If there's only one sub-school, use it directly
        sport = list(selected_school.sub_schools.keys())[0] if selected_school.sub_schools else "General"
        confirm_delete_roster(selected_school, sport, None)


def confirm_delete_roster(school, sport, window):
    if window:
        window.destroy()

    if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the roster for '{sport}'?"):
        school.sub_schools[sport].roster = Roster()  # Reset the roster
        save_schools()
        refresh_school_info()
        messagebox.showinfo("Deleted", f"Roster for '{sport}' has been deleted.")


def add_school():
    name = simpledialog.askstring("New School", "Enter school name:")
    if not name:
        return

    address = simpledialog.askstring("New School", "Enter address:")
    phone = simpledialog.askstring("New School", "Enter phone number:")

    # Create a new window to select sports
    sports_window = tk.Toplevel(root)
    sports_window.title(f"Select Sports for {name}")
    sports_window.geometry("300x400")

    common_sports = ["Soccer", "Basketball", "Tennis", "Track", "Volleyball"]
    check_vars = {}

    tk.Label(sports_window, text="Select Provided Sports:", font=("Arial", 12)).pack(pady=10)

    for sport in common_sports:
        var = tk.BooleanVar(value=False)
        check = tk.Checkbutton(sports_window, text=sport, variable=var)
        check.pack(anchor="w")
        check_vars[sport] = var

    # Custom sport entry
    custom_label = tk.Label(sports_window, text="Add Custom Sport:")
    custom_label.pack(pady=(20, 5))
    custom_entry = tk.Entry(sports_window)
    custom_entry.pack()

    def save_school():
        new_school = School(name, address, phone)

        # Add selected sports as sub-schools
        for sport, var in check_vars.items():
            if var.get():
                new_school.add_sub_school(sport)

        # Add custom sport if provided
        custom_sport = custom_entry.get().strip()
        if custom_sport:
            new_school.add_sub_school(custom_sport)

        schools.append(new_school)
        save_schools()
        refresh_school_list()
        sports_window.destroy()

    tk.Button(sports_window, text="Save School", command=save_school).pack(pady=10)

def delete_sub_school():
    selection = school_listbox.curselection()
    if not selection:
        messagebox.showinfo("Select School", "Please select a school first.")
        return

    selected_school = schools[selection[0]]

    # If the school has only one sub_school, prevent deletion
    if len(selected_school.sub_schools) == 1:
        messagebox.showinfo("Cannot Delete", "A school must have at least one sub-school.")
        return

    # Create a popup to select which sub_school to delete
    sub_school_window = tk.Toplevel(root)
    sub_school_window.title(f"Delete Sub-School - {selected_school.name}")
    sub_school_window.geometry("300x400")

    tk.Label(sub_school_window, text=f"Select a sub-school to delete for {selected_school.name}:", font=("Arial", 12)).pack(pady=10)

    for sport in selected_school.sub_schools.keys():
        tk.Button(
            sub_school_window,
            text=sport,
            command=lambda s=sport: confirm_delete_sub_school(selected_school, s, sub_school_window)
        ).pack(fill=tk.X, pady=5)

def confirm_delete_sub_school(school, sport, window):
    if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the sub-school '{sport}'?"):
        del school.sub_schools[sport]
        save_schools()
        refresh_school_info()
        window.destroy()
        messagebox.showinfo("Deleted", f"Sub-school '{sport}' has been deleted.")


def delete_school():
    selection = school_listbox.curselection()
    if selection:
        index = selection[0]
        school = sorted_school_list[index]  # Use sorted_school_list to get the correct school
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {school.name}?"):
            schools.remove(school)
            save_schools()
            refresh_school_list()
            info_text.delete("1.0", tk.END)
            info_text.insert(tk.END, "Select a school to view details")

def delete_all_schools():
    if messagebox.askyesno("Confirm Delete All", "Are you sure you want to delete ALL schools? This cannot be undone."):
        schools.clear()
        save_schools()
        refresh_school_list()
        info_text.delete("1.0", tk.END)
        info_text.insert(tk.END, "All schools have been deleted.")
        refresh_calendar()


def edit_school_info():
    selection = school_listbox.curselection()
    if not selection:
        messagebox.showinfo("Select School", "Please select a school first.")
        return
    school = sorted_school_list[selection[0]]  # Use sorted_school_list to get the correct school

    new_name = simpledialog.askstring("Edit School", "Enter new school name:", initialvalue=school.name)
    new_address = simpledialog.askstring("Edit School", "Enter new address:", initialvalue=school.address)
    new_phone = simpledialog.askstring("Edit School", "Enter new phone number:", initialvalue=school.phone_number)

    if new_name and new_address and new_phone:
        school.name = new_name
        school.address = new_address
        school.phone_number = new_phone
        save_schools()
        refresh_school_list()
        refresh_school_info()
        on_school_select(None)

def remove_student():
    selection = school_listbox.curselection()
    if not selection:
        messagebox.showinfo("Select School", "Please select a school first.")
        return
    student_name = simpledialog.askstring("Remove Student", "Enter full name of student to remove:")
    if student_name:
        selected_school = schools[selection[0]]
        selected_school.roster.remove_student(student_name)
        save_schools()
        on_school_select(None)

def assign_sports():
    selection = school_listbox.curselection()
    if not selection:
        messagebox.showinfo("Select School", "Please select a school first.")
        return
    school = sorted_school_list[selection[0]]  # Use sorted_school_list to get the correct school

    sports_window = tk.Toplevel(root)
    sports_window.title(f"Assign Sports - {school.name}")
    sports_window.geometry("300x400")

    common_sports = ["Soccer", "Basketball", "Tennis", "Track", "Volleyball"]
    check_vars = {}

    tk.Label(sports_window, text="Select Provided Sports:", font=("Arial", 12)).pack(pady=10)

    for sport in common_sports:
        var = tk.BooleanVar(value=sport in school.sub_schools)
        check = tk.Checkbutton(sports_window, text=sport, variable=var)
        check.pack(anchor="w")
        check_vars[sport] = var

    # Custom sport entry
    custom_label = tk.Label(sports_window, text="Add Custom Sport:")
    custom_label.pack(pady=(20, 5))
    custom_entry = tk.Entry(sports_window)
    custom_entry.pack()

    def save_sports():
        general_sub_school = school.sub_schools.get("General")

        for sport, var in check_vars.items():
            if var.get():
                if general_sub_school:
                    school.sub_schools[sport] = general_sub_school
                    school.sub_schools[sport].sport = sport
                    del school.sub_schools["General"]
                else:
                    school.add_sub_school(sport)

        custom = custom_entry.get().strip()
        if custom:
            if general_sub_school:
                school.sub_schools[custom] = general_sub_school
                school.sub_schools[custom].sport = custom
                del school.sub_schools["General"]
            else:
                school.add_sub_school(custom)

        save_schools()
        refresh_school_info()
        sports_window.destroy()

    tk.Button(sports_window, text="Save", command=save_sports).pack(pady=10)


def edit_school_schedule():
    selection = school_listbox.curselection()
    if not selection:
        messagebox.showinfo("Select School", "Please select a school first.")
        return
    school = schools[selection[0]]

    schedule_window = tk.Toplevel(root)
    schedule_window.title(f"Edit Weekly Schedule - {school.name}")
    schedule_window.geometry("400x450")

    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    time_vars = {}

    def make_time_picker(parent, label_text):
        frame = tk.Frame(parent)
        frame.pack(pady=2)
        tk.Label(frame, text=label_text).pack(side=tk.LEFT)
        hour_var = tk.StringVar(value="")
        minute_var = tk.StringVar(value="")
        ampm_var = tk.StringVar(value="")
        hours = [str(h) for h in range(1, 13)]
        minutes = ["00", "15", "30", "45"]
        ampm = ["am", "pm"]

        hour_box = ttk.Combobox(frame, textvariable=hour_var, values=hours, width=2, state="readonly")
        minute_box = ttk.Combobox(frame, textvariable=minute_var, values=minutes, width=2, state="readonly")
        ampm_box = ttk.Combobox(frame, textvariable=ampm_var, values=ampm, width=2, state="readonly")

        hour_box.pack(side=tk.LEFT)
        tk.Label(frame, text=":").pack(side=tk.LEFT)
        minute_box.pack(side=tk.LEFT)
        ampm_box.pack(side=tk.LEFT)

        return hour_var, minute_var, ampm_var

    for day in weekdays:
        tk.Label(schedule_window, text=day, font=("Arial", 10, "bold")).pack(pady=5)
        start_vars = make_time_picker(schedule_window, "Start")
        end_vars = make_time_picker(schedule_window, "End")
        time_vars[day] = (start_vars, end_vars)

    def save_schedule():
        for day, ((sh, sm, sap), (eh, em, eap)) in time_vars.items():
            start_time = f"{sh.get()}:{sm.get()}{sap.get()}"
            end_time = f"{eh.get()}:{em.get()}{eap.get()}"
            if not (sh.get() and sm.get() and sap.get() and eh.get() and em.get() and eap.get()):
                school.schedule[day] = ""
            else:
                school.schedule[day] = f"{start_time}-{end_time}"
        save_schools()
        messagebox.showinfo("Saved", "Schedule updated successfully.")
        schedule_window.destroy()
        refresh_calendar()
        refresh_school_info()

    tk.Button(schedule_window, text="Save Schedule", command=save_schedule).pack(pady=10)


# Runs a manual sync to Humanity
def run_manual_sync():
    sync_status_label.config(text="Syncing...")
    root.after(100, sync_from_humanity)


# Constantly gets updates from Humanity every 15 minutes
def auto_sync():
    try:
        print("🔄 Auto-syncing from Humanity...")
        sync_from_humanity()
    except Exception as e:
        print(f"⚠️ Auto-sync failed: {e}")
    finally:
        # Schedule the next auto-sync in 15 minutes (900000 ms)
        root.after(900000, auto_sync)  # 15 minutes


refresh_calendar()
refresh_school_info()
# Run the GUI
root.mainloop()











