import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

# Configuration
TENDERS = [
    {"year": "2026", "number": "444788"},
    {"year": "2026", "number": "444785"},
    {"year": "2026", "number": "598415"},
    {"year": "2026", "number": "570958"},
    {"year": "2026", "number": "549455"},
    {"year": "2026", "number": "531982"},
    {"year": "2026", "number": "353620"},
    {"year": "2026", "number": "484044"},
    {"year": "2026", "number": "437317"},
    {"year": "2026", "number": "556654"},
    {"year": "2026", "number": "283833"},
    {"year": "2026", "number": "427559"},
    {"year": "2026", "number": "190629"},
    {"year": "2026", "number": "142560"},
    {"year": "2026", "number": "91317"},
    {"year": "2026", "number": "246282"},
    {"year": "2026", "number": "60005"},
    {"year": "2026", "number": "17363"},
    {"year": "2026", "number": "57104"}
]
STATE_FILE = "state.json"
URL = "https://ekapv2.kik.gov.tr/sorgulamalar/itirazen-sikayet-basvurusu-sorgulama"

EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECEIVERS = ["ege.turkuler@gmail.com", "batuhangunes26@gmail.com"]

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

def send_email(subject, body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("Email credentials not set. Skipping email.")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = ", ".join(EMAIL_RECEIVERS)
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVERS, text)
        server.quit()
        print(f"Email sent: {subject}")
    except Exception as e:
        print(f"Failed to send email: {e}")

def run():
    state = load_state()
    state_changed = False
    new_complaints = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for tender in TENDERS:
            tender_id = f"{tender['year']}/{tender['number']}"
            print(f"Checking tender {tender_id}...")
            
            try:
                page.goto(URL, timeout=60000)
                
                # Wait for elements
                page.wait_for_selector("dx-select-box#select-yil", state="visible")
                
                # Select Year from the DevExtreme dropdown
                page.locator("dx-select-box#select-yil").click()
                # Wait for the dropdown list to appear and click the matching year
                page.locator(".dx-list-item").get_by_text(tender['year'], exact=True).first.click()
                
                # Enter Number
                # Clicking the box itself and typing is safer for DevExtreme inputs
                page.locator("dx-number-box#select-no").click()
                page.keyboard.press("Control+A") # Clear existing text
                page.keyboard.press("Backspace")
                page.keyboard.type(tender['number'], delay=50) # Type slowly to simulate user
                page.keyboard.press("Enter")
                
                # Click Search
                page.locator("dx-button#search-button").click()
                
                # Wait for API response/results. The page might show a loading indicator.
                try:
                    # Wait for either the data grid or a potential "no data" element
                    # We give it 10 seconds to load the result
                    page.wait_for_timeout(3000)
                    page.wait_for_selector(".dx-datagrid-table", state="visible", timeout=10000)
                except Exception:
                    print(f"No results table or timeout waiting for table for {tender_id}")
                    continue
                
                # Check rows
                # The data rows typically have class 'dx-data-row'
                table_locator = page.locator(".dx-datagrid-table").last
                rows = table_locator.locator("tr.dx-data-row").all()
                
                if rows:
                    print(f"Found {len(rows)} complaints for {tender_id}.")
                    # To be robust, combine text of all rows or just the first row
                    latest_complaint_text = rows[0].inner_text()
                    
                    last_seen = state.get(tender_id, {}).get('last_seen_complaint', "")
                    
                    if latest_complaint_text != last_seen:
                        new_complaints.append(f"--- Tender {tender_id} ---\n{latest_complaint_text}")
                        state[tender_id] = {'last_seen_complaint': latest_complaint_text}
                        state_changed = True
                else:
                    print(f"No complaint rows found for {tender_id}.")
                    
            except Exception as e:
                print(f"Error checking tender {tender_id}: {e}")

        browser.close()

    if new_complaints:
        subject = f"EKAP Alert: {len(new_complaints)} New/Updated Complaints"
        body = f"Found updates for {len(new_complaints)} tender(s):\n\n" + "\n\n".join(new_complaints) + f"\n\nCheck at: {URL}"
        send_email(subject, body)

    if state_changed:
        save_state(state)

if __name__ == "__main__":
    run()
