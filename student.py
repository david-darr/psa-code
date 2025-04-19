# student.py
import json
import datetime
from PIL import Image
import pytesseract
import re
import os

# OCR setup
pytesseract.pytesseract.tesseract_cmd = r"C:\\Users\\David\\AppData\\Local\\Programs\\Tesseract-OCR/tesseract.exe"

# === Models ===
class Student:
    def __init__(self, first_name, last_name):
        self.first_name = first_name
        self.last_name = last_name

    def to_dict(self):
        return {"first_name": self.first_name, "last_name": self.last_name}

    @staticmethod
    def from_dict(data):
        return Student(data['first_name'], data['last_name'])

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


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

        for line in lines:
            line = line.strip()
            if not line or "first name" in line.lower():
                continue

            if "|" in line:
                parts = [part.strip() for part in line.split("|")]
                if len(parts) == 2:
                    self.add_student(Student(parts[0].title(), parts[1].title()))
                    continue

            cleaned = re.sub(r'[^A-Za-z\s\-]', '', line).strip()
            parts = cleaned.split()
            if len(parts) >= 2:
                self.add_student(Student(parts[0].title(), ' '.join(parts[1:]).title()))

    def to_dict(self):
        return [s.to_dict() for s in self.students]

    @staticmethod
    def from_dict(data):
        roster = Roster()
        for student_data in data:
            roster.add_student(Student.from_dict(student_data))
        return roster


class SubSchool:
    def __init__(self, sport):
        self.sport = sport
        self.roster = Roster()
        self.schedule = {}

    def to_dict(self):
        return {"sport": self.sport, "roster": self.roster.to_dict(), "schedule": self.schedule}

    @staticmethod
    def from_dict(data):
        sub = SubSchool(data.get("sport", "General"))
        sub.roster = Roster.from_dict(data.get("roster", []))
        sub.schedule = data.get("schedule", {})
        return sub


class School:
    def __init__(self, name, address, phone_number):
        self.name = name
        self.address = address
        self.phone_number = phone_number
        self.sub_schools = {}

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
            "sub_schools": {sport: s.to_dict() for sport, s in self.sub_schools.items()}
        }

    @staticmethod
    def from_dict(data):
        school = School(data.get('name', ''), data.get('address', ''), data.get('phone_number', ''))
        for sport, sub_data in data.get("sub_schools", {}).items():
            school.sub_schools[sport] = SubSchool.from_dict(sub_data)
        return school


# === Data Persistence ===
DATA_FILE = "schools_data.json"


def normalize_name(name):
    return name.split(" - ")[0].strip().lower() if " - " in name else name.strip().lower()


def save_schools(schools):
    with open(DATA_FILE, 'w') as f:
        json.dump([s.to_dict() for s in schools], f, indent=2)


def load_schools():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r') as f:
        return [School.from_dict(s) for s in json.load(f)]


# === Sync Logic ===
def sync_from_humanity():
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    import time

    schools = load_schools()
    shift_data = []

    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get("https://www.humanity.com/app/")
        time.sleep(2)
        driver.find_element(By.ID, "email").send_keys("21316153cc853d45b8200f852ea277eb")
        driver.find_element(By.ID, "password").send_keys("15079David")
        driver.find_element(By.NAME, "login").click()
        time.sleep(3)

        driver.get("https://richardburke1.humanity.com/app/schedule/list/month/employee/employee/18%2c3%2c2025/")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

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

        for row in shift_rows:
            try:
                class_list = row.get_attribute("class").split()
                date_key = extract_date(class_list)
                if not date_key:
                    continue
                time_text = row.find_element(By.CSS_SELECTOR, "td.second").text.strip().split("\n")[-1]
                school_and_address = row.find_element(By.CSS_SELECTOR, "td.fourth").text.strip()
                parts = school_and_address.split("\n")
                school_name = parts[0].strip()
                raw_address = parts[1].strip() if len(parts) > 1 else "Unknown Address"
                shift_data.append({"school": school_name, "date": date_key, "time": time_text, "address": raw_address})
            except Exception as e:
                print(f"⚠️ Error reading row: {e}")

    finally:
        driver.quit()

    updated = 0
    added = 0
    common_sports = {"soccer", "basketball", "yoga", "football", "volleyball", "tennis", "track", "running", "chess"}

    for shift in shift_data:
        full_name = shift["school"]
        date_key = shift["date"]
        time_val = shift["time"]
        address = shift["address"]

        sport = "General"
        base_name = full_name
        for sport_name in common_sports:
            if sport_name in full_name.lower():
                sport = sport_name.capitalize()
                base_name = full_name.lower().replace(sport_name, "").strip()
                break

        normalized_name = normalize_name(base_name)
        match = next((s for s in schools if normalize_name(s.name) == normalized_name), None)

        if not match:
            match = School(name=base_name.title(), address=address, phone_number="Unknown")
            schools.append(match)
            added += 1

        if sport not in match.sub_schools:
            match.add_sub_school(sport)

        if date_key in match.sub_schools[sport].schedule:
            updated += 1
        else:
            added += 1

        match.sub_schools[sport].schedule[date_key] = time_val

    save_schools(schools)
    return f"✅ Sync complete – {updated} shifts updated, {added} new entries added."


__all__ = ['Student', 'Roster', 'SubSchool', 'School', 'normalize_name', 'load_schools', 'save_schools', 'sync_from_humanity']
