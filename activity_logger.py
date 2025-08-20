import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont
import time
import json
import os
import platform
import threading
import queue
import webbrowser
from datetime import datetime, date, timedelta
from collections import defaultdict

# --- Dependency Checks & Conditional Imports ---
try:
    from PIL import Image, ImageTk
    PIL_ENABLED = True
except ImportError:
    PIL_ENABLED = False

try:
    import psutil
    if platform.system() == "Windows": import wmi
    SPECS_ENABLED = True
except ImportError:
    SPECS_ENABLED = False

try:
    from pynput import mouse, keyboard
    IDLE_DETECTION_ENABLED = True
except ImportError:
    IDLE_DETECTION_ENABLED = False

try:
    import pyperclip
    CLIPBOARD_ENABLED = True
except ImportError:
    CLIPBOARD_ENABLED = False

try:
    import google.generativeai as genai
    AI_ENABLED = True
except ImportError:
    AI_ENABLED = False

try:
    from pystray import MenuItem as item
    import pystray
    TRAY_ENABLED = True
except ImportError:
    TRAY_ENABLED = False
    
# --- NEW: Calendar and Google API Imports ---
try:
    from tkcalendar import Calendar
    CALENDAR_ENABLED = True
except ImportError:
    CALENDAR_ENABLED = False

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
    import io
    GOOGLE_API_ENABLED = True
except ImportError:
    GOOGLE_API_ENABLED = False

# --- Google API Settings ---
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/userinfo.profile']
# --- IMPORTANT: Apnake 'credentials.json' file ti dite hobe ---
# Google Cloud theke credentials file download kore project folder e rakhun
CREDENTIALS_FILE = 'credentials.json'


# --- Global variables & Listener Functions ---
event_queue = queue.Queue()
last_activity_time = time.time()

def on_activity(*args):
    global last_activity_time
    last_activity_time = time.time()

def on_click(x, y, button, pressed):
    if pressed:
        event_queue.put(('click', None))
        on_activity()

def start_listeners():
    if not IDLE_DETECTION_ENABLED: return
    mouse_listener = mouse.Listener(on_click=on_click, on_move=on_activity, on_scroll=on_activity)
    keyboard_listener = keyboard.Listener(on_press=on_activity)
    mouse_listener.start()
    keyboard_listener.start()

def get_active_window_title():
    # ... (No changes in this function)
    system = platform.system()
    try:
        if system == 'Windows':
            import win32gui
            return win32gui.GetWindowText(win32gui.GetForegroundWindow())
        elif system == 'Linux':
            import subprocess
            root = subprocess.check_output(['xprop', '-root', '_NET_ACTIVE_WINDOW'], stderr=subprocess.DEVNULL)
            window_id = root.split()[-1]
            window_name = subprocess.check_output(['xprop', '-id', window_id, 'WM_NAME'], stderr=subprocess.DEVNULL)
            return window_name.decode().split('"', 1)[1].rsplit('"', 1)[0]
        elif system == 'Darwin':
            from AppKit import NSWorkspace
            active_app = NSWorkspace.sharedWorkspace().activeApplication()
            return active_app.get('NSApplicationName', 'Unknown')
        else:
            return f"Unsupported OS: {system}"
    except Exception:
        return "Could not get window title"

# --- Main Application Class ---
class ActivityLoggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Activity Logger")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)

        self.config = {
            'idle_threshold_minutes': 5,
            'daily_work_goal_hours': 4,
        }

        font_family = "Segoe UI" if platform.system() == "Windows" else "Helvetica"
        self.fonts = {
            "primary": (font_family, 10), "header": (font_family, 11, "bold"),
            "card_title": (font_family, 12, "bold"), "card_value": (font_family, 22, "bold"),
            "sidebar_title": (font_family, 18, "bold"), "link": (font_family, 11, "underline"),
        }

        self.setup_theme()

        self.log_file = os.path.expanduser('~/.activity_log.jsonl')
        self.data = [] # Initially empty, will be loaded
        
        self.active_time_seconds = 0
        self.idle_time_seconds = 0
        self.app_usage = defaultdict(float)
        self.last_app = None
        self.last_app_start_time = time.time()
        self.mouse_clicks = 0
        
        # --- NEW: Google API variables ---
        self.google_creds = None
        self.user_profile = None
        self.drive_service = None

        self.icons = self.load_icons()
        self.create_widgets()
        
        self.is_idle = False
        self.running = True
        self.start_background_tasks()
        self.show_page("Dashboard")
        
        # --- NEW: Initial load and login check ---
        self.load_initial_data()
        
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        threading.Thread(target=self.setup_tray_icon, daemon=True).start()

    def load_initial_data(self):
        """Checks for Google token, loads data from Drive or local file."""
        if GOOGLE_API_ENABLED:
            self.check_google_login()
        else:
            self.data = self.load_log_from_local_file()
            self.pre_calculate_today_stats()
            self.update_dashboard_live()

    def create_widgets(self):
        self.sidebar_frame = tk.Frame(self.root, width=220, bg=self.theme_colors["sidebar"])
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)
        
        self.main_content_frame = tk.Frame(self.root, bg=self.theme_colors["bg"])
        self.main_content_frame.pack(side="left", fill="both", expand=True)

        self.create_sidebar()
        self.create_top_bar()
        
        self.main_page_container = tk.Frame(self.main_content_frame, bg=self.theme_colors["bg"])
        self.main_page_container.pack(fill="both", expand=True)
        
        # --- NEW: Reports page added ---
        self.pages = {
            "Dashboard": DashboardPage(self.main_page_container, self),
            "Reports": ReportsPage(self.main_page_container, self),
            "Logs": LogsPage(self.main_page_container, self),
            "System Info": SystemInfoPage(self.main_page_container, self),
            "About": AboutPage(self.main_page_container, self)
        }
    
    def create_sidebar(self):
        # ... (Previous sidebar creation code)
        tk.Label(self.sidebar_frame, text="Activity Logger", font=self.fonts["sidebar_title"], 
                 bg=self.theme_colors["sidebar"], fg=self.theme_colors["accent"]).pack(pady=20, padx=20, anchor="w")
        
        # --- NEW: Profile Frame ---
        self.profile_frame = tk.Frame(self.sidebar_frame, bg=self.theme_colors["sidebar"])
        self.profile_frame.pack(fill="x", pady=10, padx=20)
        
        self.login_button = tk.Button(self.profile_frame, text="Login with Google", command=self.google_login, font=self.fonts["header"])
        self.login_button.pack()
        
        self.profile_name_label = tk.Label(self.profile_frame, text="", font=self.fonts["header"], bg=self.theme_colors["sidebar"], fg="white")
        self.logout_button = tk.Button(self.profile_frame, text="Logout", command=self.google_logout, font=self.fonts["primary"])

        self.sidebar_buttons = {}
        # --- NEW: Reports button added ---
        buttons_to_create = ["Dashboard", "Reports", "Logs"]
        for text in buttons_to_create:
            self.create_sidebar_button(text, self.icons.get(text.lower()))
        
        bottom_frame = tk.Frame(self.sidebar_frame, bg=self.theme_colors["sidebar"])
        bottom_frame.pack(side="bottom", fill="x", pady=10)
        self.create_sidebar_button("System Info", self.icons.get("info"), parent=bottom_frame)
        self.create_sidebar_button("About", self.icons.get("about"), parent=bottom_frame)

    # --- NEW: Google API Functions ---
    def check_google_login(self):
        """Checks if a valid token.json exists."""
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        if creds and creds.valid:
            self.google_creds = creds
            self.on_google_login_success()
        else:
            self.data = self.load_log_from_local_file()
            self.pre_calculate_today_stats()
            self.update_dashboard_live()

    def google_login(self):
        """Starts the Google login flow."""
        if not os.path.exists(CREDENTIALS_FILE):
            messagebox.showerror("Error", f"'{CREDENTIALS_FILE}' not found. Please download it from Google Cloud Console.")
            return
        
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        self.google_creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(self.google_creds.to_json())
        self.on_google_login_success()

    def on_google_login_success(self):
        """Called after a successful login."""
        self.login_button.pack_forget()
        self.profile_name_label.pack()
        self.logout_button.pack(pady=5)
        
        # Get user profile
        profile_service = build('oauth2', 'v2', credentials=self.google_creds)
        self.user_profile = profile_service.userinfo().get().execute()
        self.profile_name_label.config(text=self.user_profile.get('name', 'User'))
        
        # Build Drive service
        self.drive_service = build('drive', 'v3', credentials=self.google_creds)
        
        # Load data from Drive
        self.load_data_from_drive()

    def google_logout(self):
        """Logs the user out."""
        if os.path.exists('token.json'):
            os.remove('token.json')
        self.google_creds = None
        self.user_profile = None
        self.drive_service = None
        
        self.profile_name_label.pack_forget()
        self.logout_button.pack_forget()
        self.login_button.pack()
        
        self.data = self.load_log_from_local_file()
        self.pre_calculate_today_stats()

    def load_data_from_drive(self):
        """Loads the log file from Google Drive."""
        messagebox.showinfo("Syncing", "Loading data from Google Drive...")
        try:
            folder_id = self.get_or_create_drive_folder()
            
            response = self.drive_service.files().list(
                q=f"'{folder_id}' in parents and name='activity_log.jsonl'",
                spaces='drive', fields='files(id, name)').execute()
            files = response.get('files', [])

            if files:
                file_id = files[0].get('id')
                request = self.drive_service.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                
                fh.seek(0)
                # Decode and parse the file content
                lines = fh.read().decode('utf-8').splitlines()
                self.data = [json.loads(line) for line in lines if line]
                # Save a local copy
                with open(self.log_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
            else:
                self.data = self.load_log_from_local_file()
            
            self.pre_calculate_today_stats()
            self.update_dashboard_live()
            messagebox.showinfo("Sync Complete", "Data loaded successfully from Google Drive.")

        except Exception as e:
            messagebox.showerror("Drive Error", f"Could not load data from Drive: {e}")
            self.data = self.load_log_from_local_file()
            self.pre_calculate_today_stats()
            self.update_dashboard_live()

    def backup_data_to_drive(self):
        """Uploads the current local log file to Google Drive."""
        if not self.drive_service or not os.path.exists(self.log_file):
            return

        try:
            folder_id = self.get_or_create_drive_folder()
            
            # Check if file already exists
            response = self.drive_service.files().list(
                q=f"'{folder_id}' in parents and name='activity_log.jsonl'",
                spaces='drive', fields='files(id)').execute()
            files = response.get('files', [])

            file_metadata = {'name': 'activity_log.jsonl'}
            media = MediaFileUpload(self.log_file, mimetype='application/json')

            if files:
                # Update existing file
                file_id = files[0].get('id')
                self.drive_service.files().update(fileId=file_id, media_body=media).execute()
            else:
                # Create new file
                file_metadata['parents'] = [folder_id]
                self.drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            
            print("Backup to Drive successful.")
        except Exception as e:
            print(f"Backup to Drive failed: {e}")

    def get_or_create_drive_folder(self):
        """Finds or creates the 'Activity Logger Backups' folder in Drive."""
        response = self.drive_service.files().list(
            q="mimeType='application/vnd.google-apps.folder' and name='Activity Logger Backups'",
            spaces='drive', fields='files(id, name)').execute()
        files = response.get('files', [])
        
        if files:
            return files[0].get('id')
        else:
            file_metadata = {
                'name': 'Activity Logger Backups',
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.drive_service.files().create(body=file_metadata, fields='id').execute()
            return folder.get('id')

    def log_event(self, event_type, event_description):
        timestamp = datetime.now().isoformat()
        entry = {'time': timestamp, 'type': event_type, 'event': event_description}
        self.data.append(entry)
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + '\n')
        
        # Schedule a backup to Drive
        self.root.after(300000, self.backup_data_to_drive) # Backup every 5 mins
            
        if self.pages["Logs"].winfo_exists() and self.pages["Logs"].winfo_ismapped():
            self.pages["Logs"].on_show()

    def load_log_from_local_file(self):
        if not os.path.exists(self.log_file): return []
        data = []
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return data

    def pre_calculate_today_stats(self):
        # ... (No changes in this function)
        today_str = date.today().isoformat()
        self.active_time_seconds = 0
        self.idle_time_seconds = 0
        last_time = None
        last_state_idle = False

        for entry in self.data:
            if not entry.get('time', '').startswith(today_str): continue
            
            current_time = datetime.fromisoformat(entry['time'])
            if last_time:
                duration = (current_time - last_time).total_seconds()
                if duration < 600:
                    if last_state_idle: self.idle_time_seconds += duration
                    else: self.active_time_seconds += duration

            if 'User is Idle' in entry.get('event', ''): last_state_idle = True
            elif 'User is Active' in entry.get('event', ''): last_state_idle = False
            last_time = current_time
    
    # ... (Other functions like setup_tray_icon, hide_window, etc. remain the same)
    def setup_tray_icon(self):
        if not TRAY_ENABLED or not PIL_ENABLED: return
        try:
            image = Image.open("assets/tray_icon.png")
            menu = (item('Show Logger', self.show_window), item('Quit', self.quit_app))
            self.icon = pystray.Icon("Activity Logger", image, "Activity Logger", menu)
            self.icon.run()
        except FileNotFoundError:
            print("Tray icon not found at 'assets/tray_icon.png'. Tray feature will be disabled.")

    def hide_window(self):
        self.root.withdraw()

    def show_window(self):
        self.root.deiconify()

    def quit_app(self):
        self.running = False
        self.update_app_usage()
        if self.icon:
            self.icon.stop()
        self.root.destroy()

    def load_icons(self):
        if not PIL_ENABLED: return {}
        icons = {}
        # --- NEW: reports icon added ---
        icon_names = ["dashboard", "reports", "logs", "info", "about"]
        for name in icon_names:
            try:
                path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", f"{name}.png")
                image = Image.open(path).resize((20, 20), Image.Resampling.LANCZOS)
                icons[name] = ImageTk.PhotoImage(image)
            except Exception:
                icons[name] = None
        return icons
        
    def show_page(self, page_name):
        for page in self.pages.values(): page.pack_forget()
        for button in self.sidebar_buttons.values(): button.config(bg=self.theme_colors["sidebar"], fg=self.theme_colors["sidebar_text"])
        
        self.pages[page_name].pack(fill="both", expand=True, padx=20, pady=10)
        self.sidebar_buttons[page_name].config(bg=self.theme_colors["accent"], fg="#FFFFFF")
        self.page_title_var.set(page_name)
        if hasattr(self.pages[page_name], 'on_show'):
            self.pages[page_name].on_show()

    def start_background_tasks(self):
        threading.Thread(target=self.track_activity, daemon=True).start()
        if CLIPBOARD_ENABLED: 
            threading.Thread(target=self.track_clipboard, daemon=True).start()
        if IDLE_DETECTION_ENABLED:
            threading.Thread(target=start_listeners, daemon=True).start()
        self.root.after(200, self.process_queue)
    
    def track_clipboard(self):
        last_content = ""
        while self.running:
            time.sleep(2)
            try:
                current_content = pyperclip.paste()
                if current_content and current_content != last_content:
                    last_content = current_content
                    log_content = (current_content[:100] + '...') if len(current_content) > 100 else current_content
                    event_queue.put(('clipboard', f'Copied: "{log_content}"'))
            except Exception: pass

    def process_queue(self):
        try:
            while not event_queue.empty():
                event_type, event_description = event_queue.get_nowait()
                if event_type == 'click':
                    self.mouse_clicks += 1
                else:
                    self.log_event(event_type, event_description)
        finally:
            self.root.after(200, self.process_queue)

    def track_activity(self):
        while self.running:
            time.sleep(1)
            time_since_last_activity = time.time() - last_activity_time
            
            if time_since_last_activity > self.config.get('idle_threshold_minutes', 5) * 60:
                if not self.is_idle:
                    self.is_idle = True
                    self.log_event('activity', "Status: User is Idle")
                    self.update_app_usage()
                self.idle_time_seconds += 1
            else:
                if self.is_idle:
                    self.is_idle = False
                    self.log_event('activity', "Status: User is Active")
                    self.last_app_start_time = time.time()
                self.active_time_seconds += 1
                
                title = get_active_window_title()
                if title and title != self.last_app:
                    self.update_app_usage(title)
                    self.log_event('window', f"Switched to: {title}")
    
    def update_app_usage(self, new_app=None):
        now = time.time()
        if self.last_app:
            duration = now - self.last_app_start_time
            self.app_usage[self.last_app] += duration
        self.last_app = new_app
        self.last_app_start_time = now

    def update_dashboard_live(self):
        if self.pages["Dashboard"].winfo_exists():
            self.pages["Dashboard"].update_stats()
        self.root.after(2000, self.update_dashboard_live)


# --- NEW: ReportsPage Class ---
class ReportsPage(BasePage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        
        # Top frame for calendar and controls
        top_frame = tk.Frame(self, bg=self.controller.theme_colors["bg"])
        top_frame.pack(fill="x", pady=(0, 10))
        
        if CALENDAR_ENABLED:
            self.cal = Calendar(top_frame, selectmode='day', date_pattern='y-mm-dd')
            self.cal.pack(side="left", padx=10, fill="y")
            
            tk.Button(top_frame, text="Show Report", command=self.show_report_for_date).pack(side="left", padx=10)
        else:
            tk.Label(top_frame, text="Please install 'tkcalendar' to use this feature.", fg="red").pack()

        # Main frame for the report details
        self.report_frame = tk.Frame(self, bg=self.controller.theme_colors["frame"], relief="solid", borderwidth=1)
        self.report_frame.pack(fill="both", expand=True)
        
        self.report_widgets = {}
        self.create_report_ui()

    def create_report_ui(self):
        # This UI will be populated with data for the selected date
        self.report_widgets['date_label'] = tk.Label(self.report_frame, text="Select a date to view report", font=self.controller.fonts["card_title"], bg="white")
        self.report_widgets['date_label'].pack(pady=20)
        
        stats_frame = tk.Frame(self.report_frame, bg="white")
        stats_frame.pack(fill="x", pady=10)

        self.report_widgets['active_var'] = tk.StringVar(value="N/A")
        self.report_widgets['idle_var'] = tk.StringVar(value="N/A")
        
        self.create_stat_display(stats_frame, "Active Time", self.report_widgets['active_var']).pack(side="left", expand=True)
        self.create_stat_display(stats_frame, "Idle Time", self.report_widgets['idle_var']).pack(side="left", expand=True)
        
        tk.Label(self.report_frame, text="Top Applications", font=self.controller.fonts["header"], bg="white").pack(pady=(20, 5))
        self.report_widgets['app_tree'] = ttk.Treeview(self.report_frame, columns=("App", "Time"), show="headings", height=10)
        self.report_widgets['app_tree'].heading("App", text="Application")
        self.report_widgets['app_tree'].heading("Time", text="Usage")
        self.report_widgets['app_tree'].pack(fill="x", padx=20, pady=10)

    def create_stat_display(self, parent, title, string_var):
        frame = tk.Frame(parent, bg="white")
        tk.Label(frame, text=title, font=self.controller.fonts["header"], bg="white").pack()
        tk.Label(frame, textvariable=string_var, font=self.controller.fonts["card_value"], bg="white", fg=self.controller.theme_colors["accent"]).pack()
        return frame

    def show_report_for_date(self):
        selected_date_str = self.cal.get_date()
        self.report_widgets['date_label'].config(text=f"Report for: {selected_date_str}")
        
        # Filter data for the selected date
        selected_date_logs = [entry for entry in self.controller.data if entry.get('time', '').startswith(selected_date_str)]
        
        if not selected_date_logs:
            self.report_widgets['active_var'].set("0h 0m")
            self.report_widgets['idle_var'].set("0h 0m")
            for i in self.report_widgets['app_tree'].get_children():
                self.report_widgets['app_tree'].delete(i)
            self.report_widgets['app_tree'].insert("", "end", values=("No activity recorded on this day.", ""))
            return

        # Calculate stats for the selected date
        active_s, idle_s = 0, 0
        app_usage = defaultdict(float)
        last_time = None
        last_state_idle = False
        last_app_title = None
        last_app_start = None

        for entry in selected_date_logs:
            current_time = datetime.fromisoformat(entry['time'])
            
            if last_time:
                duration = (current_time - last_time).total_seconds()
                if duration < 1800: # Ignore large gaps
                    if last_state_idle:
                        idle_s += duration
                    else:
                        active_s += duration
                    if last_app_title:
                        app_usage[last_app_title] += duration

            if entry['type'] == 'activity':
                if 'User is Idle' in entry['event']:
                    last_state_idle = True
                elif 'User is Active' in entry['event']:
                    last_state_idle = False
            
            if entry['type'] == 'window':
                last_app_title = entry['event'].replace("Switched to: ", "")
            
            last_time = current_time

        # Update UI
        self.report_widgets['active_var'].set(self.controller.pages["Dashboard"].format_time(active_s))
        self.report_widgets['idle_var'].set(self.controller.pages["Dashboard"].format_time(idle_s))
        
        for i in self.report_widgets['app_tree'].get_children():
            self.report_widgets['app_tree'].delete(i)
            
        sorted_apps = sorted(app_usage.items(), key=lambda item: item[1], reverse=True)
        for app, duration in sorted_apps[:10]:
            app_name = (app[:50] + '...') if len(app) > 50 else app
            time_str = self.controller.pages["Dashboard"].format_time(duration)
            self.report_widgets['app_tree'].insert("", "end", values=(app_name, time_str))

# --- Other Page Classes (Dashboard, Logs, etc.) remain largely the same ---
# ... (Paste the existing DashboardPage, LogsPage, SystemInfoPage, AboutPage classes here)
class DashboardPage(BasePage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.stat_vars = {
            "active": tk.StringVar(value="0h 0m"), "idle": tk.StringVar(value="0h 0m"),
            "clicks": tk.StringVar(value="0"), "top_app": tk.StringVar(value="N/A")
        }
        
        card_frame = tk.Frame(self, bg=self.controller.theme_colors["bg"])
        card_frame.pack(fill="x", pady=10)
        
        self.create_stat_card(card_frame, "Active Time Today", self.stat_vars["active"]).pack(side="left", expand=True, fill="x", padx=5)
        self.create_stat_card(card_frame, "Idle Time Today", self.stat_vars["idle"]).pack(side="left", expand=True, fill="x", padx=5)
        self.create_stat_card(card_frame, "Total Mouse Clicks", self.stat_vars["clicks"]).pack(side="left", expand=True, fill="x", padx=5)
        self.create_stat_card(card_frame, "Top Application", self.stat_vars["top_app"]).pack(side="left", expand=True, fill="x", padx=5)
        
        ai_frame = tk.Frame(self, bg=self.controller.theme_colors["frame"], relief="solid", borderwidth=1, highlightbackground="#E0E0E0")
        ai_frame.pack(fill="both", expand=True, pady=10)
        
        ai_top_frame = tk.Frame(ai_frame, bg="white")
        ai_top_frame.pack(fill="x", padx=15, pady=10)

        tk.Label(ai_top_frame, text="AI Productivity Assistant", font=self.controller.fonts["card_title"], bg="white", fg=self.controller.theme_colors["text"]).pack(side="left")
        
        self.ai_button = tk.Button(ai_top_frame, text="Get AI Summary", command=self.run_ai_summary_thread, font=self.controller.fonts["primary"])
        self.ai_button.pack(side="right")

        self.ai_response_text = tk.Text(ai_frame, font=self.controller.fonts["primary"], relief="flat", wrap="word", height=10, state="disabled", bg=self.controller.theme_colors["frame"])
        self.ai_response_text.pack(fill="both", expand=True, padx=15, pady=10)
        
        if not AI_ENABLED:
            self.ai_button.config(state="disabled")
            self.update_ai_response("AI feature disabled. Please install 'google-generativeai' and add your API Key in the code.")
        
        self.update_stats()

    def create_stat_card(self, parent, title, string_var):
        frame = tk.Frame(parent, bg=self.controller.theme_colors["frame"], relief="solid", borderwidth=1, highlightbackground="#E0E0E0")
        tk.Label(frame, text=title, font=self.controller.fonts["card_title"], bg="white", fg=self.controller.theme_colors["text"]).pack(pady=(15, 5))
        tk.Label(frame, textvariable=string_var, font=self.controller.fonts["card_value"], bg="white", fg=self.controller.theme_colors["accent"]).pack(pady=(5, 20))
        return frame

    def format_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0: return f"{h}h {m}m"
        elif m > 0: return f"{m}m {s}s"
        else: return f"{s}s"

    def update_stats(self):
        self.controller.pre_calculate_today_stats() # Recalculate for live update
        self.stat_vars["active"].set(self.format_time(self.controller.active_time_seconds))
        self.stat_vars["idle"].set(self.format_time(self.controller.idle_time_seconds))
        self.stat_vars["clicks"].set(f"{self.controller.mouse_clicks}")

        if self.controller.app_usage:
            top_app_name = max(self.controller.app_usage, key=self.controller.app_usage.get)
            top_app_duration = self.controller.app_usage[top_app_name]
            
            top_app_display_name = (top_app_name[:20] + '...') if len(top_app_name) > 20 else top_app_name
            top_app_display_time = self.format_time(top_app_duration)
            self.stat_vars["top_app"].set(f"{top_app_display_name}\n{top_app_display_time}")
        else:
            self.stat_vars["top_app"].set("N/A")

    def update_ai_response(self, text):
        self.ai_response_text.config(state="normal")
        self.ai_response_text.delete(1.0, "end")
        self.ai_response_text.insert("end", text)
        self.ai_response_text.config(state="disabled")

    def run_ai_summary_thread(self):
        threading.Thread(target=self.get_ai_summary, daemon=True).start()

    def get_ai_summary(self):
        self.controller.root.after(0, self.ai_button.config, {"state": "disabled"})
        self.controller.root.after(0, self.update_ai_response, "AI is thinking... Please wait.")
        
        try:
            active_time_str = self.format_time(self.controller.active_time_seconds)
            idle_time_str = self.format_time(self.controller.idle_time_seconds)
            top_apps = sorted(self.controller.app_usage.items(), key=lambda item: item[1], reverse=True)[:5]
            top_apps_str = "\n".join([f"- {name} ({self.format_time(duration)})" for name, duration in top_apps])

            prompt = f"""
            You are a productivity assistant. Analyze the following user activity data for today and provide a brief, encouraging summary (2-3 sentences) and one actionable suggestion for improvement.
            Keep the tone friendly and positive.

            Today's Data:
            - Total Active Time: {active_time_str}
            - Total Idle Time: {idle_time_str}
            - Total Mouse Clicks: {self.controller.mouse_clicks}
            - Top 5 Most Used Applications:
            {top_apps_str}

            Your summary and suggestion:
            """
            
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            
            self.controller.root.after(0, self.update_ai_response, response.text)

        except Exception as e:
            error_message = f"AI request failed. Please check your API key and internet connection.\nError: {e}"
            self.controller.root.after(0, self.update_ai_response, error_message)
        finally:
            self.controller.root.after(0, self.ai_button.config, {"state": "normal"})

class LogsPage(BasePage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        
        paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, bg=self.controller.theme_colors["bg"])
        paned_window.pack(fill=tk.BOTH, expand=True)

        summary_frame = tk.Frame(paned_window, bg="white")
        tk.Label(summary_frame, text="Application Summary (Today)", font=self.controller.fonts["card_title"], bg="white").pack(pady=10)
        self.summary_tree = ttk.Treeview(summary_frame, columns=("App", "Time"), show="headings")
        self.summary_tree.heading("App", text="Application")
        self.summary_tree.heading("Time", text="Total Usage")
        self.summary_tree.column("App", width=250)
        self.summary_tree.column("Time", width=100, anchor='e')
        self.summary_tree.pack(fill=tk.BOTH, expand=True)
        self.summary_tree.bind("<<TreeviewSelect>>", self.show_app_details)
        paned_window.add(summary_frame, width=400)

        detail_frame = tk.Frame(paned_window, bg="white")
        tk.Label(detail_frame, text="Detailed Timeline (Today)", font=self.controller.fonts["card_title"], bg="white").pack(pady=10)
        self.detail_tree = ttk.Treeview(detail_frame, columns=("Time", "Event"), show="headings")
        self.detail_tree.heading("Time", text="Timestamp")
        self.detail_tree.heading("Event", text="Event Details")
        self.detail_tree.column("Time", width=150, anchor='w')
        self.detail_tree.column("Event", width=450, anchor='w')
        self.detail_tree.pack(fill=tk.BOTH, expand=True)
        paned_window.add(detail_frame)

    def on_show(self):
        for i in self.summary_tree.get_children(): self.summary_tree.delete(i)
        for i in self.detail_tree.get_children(): self.detail_tree.delete(i)

        app_usage = self.controller.app_usage
        sorted_apps = sorted(app_usage.items(), key=lambda item: item[1], reverse=True)

        for app, duration in sorted_apps:
            if duration < 1: continue
            app_name = (app[:40] + '...') if len(app) > 40 else app
            time_str = self.controller.pages["Dashboard"].format_time(duration)
            self.summary_tree.insert("", "end", values=(app_name, time_str), iid=app)

    def show_app_details(self, event):
        for i in self.detail_tree.get_children(): self.detail_tree.delete(i)

        selected_item = self.summary_tree.selection()
        if not selected_item: return
        
        selected_app_name = self.summary_tree.item(selected_item[0])['values'][0]
        full_app_name = ""
        for app in self.controller.app_usage.keys():
            if app.startswith(selected_app_name.replace("...", "")):
                full_app_name = app
                break
        if not full_app_name: return

        today_str = date.today().isoformat()
        is_app_active = False
        
        for entry in self.controller.data:
            if not entry['time'].startswith(today_str): continue
            
            event_desc = entry['event']
            
            if event_desc == f"Switched to: {full_app_name}":
                is_app_active = True
                self.add_detail_entry(entry)
            elif event_desc.startswith("Switched to:") and is_app_active:
                is_app_active = False
                switched_away_entry = entry.copy()
                switched_away_entry['event'] = f"--- Switched away to another app ---"
                self.add_detail_entry(switched_away_entry, "away")
            elif is_app_active:
                self.add_detail_entry(entry)

    def add_detail_entry(self, entry, tag=None):
        time_str = datetime.fromisoformat(entry['time']).strftime('%H:%M:%S')
        self.detail_tree.insert("", "end", values=(time_str, entry['event']), tags=(tag,) if tag else ())
        self.detail_tree.tag_configure("away", foreground="gray")
        self.detail_tree.yview_moveto(1)

class SystemInfoPage(BasePage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.info_text = tk.Text(self, font=("Courier", 10), 
                                 bg=self.controller.theme_colors["frame"], 
                                 fg=self.controller.theme_colors["text"], 
                                 relief="flat", state="disabled", wrap="word",
                                 padx=20, pady=20)
        self.info_text.pack(fill="both", expand=True)
    
    def on_show(self):
        specs = "System specifications would be displayed here."
        if SPECS_ENABLED:
            specs = f"OS: {platform.system()} {platform.release()}\n"
            specs += f"CPU: {platform.processor() or 'N/A'}\n"
            try:
                ram = psutil.virtual_memory()
                specs += f"RAM: {ram.total / (1024**3):.2f} GB\n"
            except:
                specs += "RAM: N/A\n"

        self.info_text.config(state="normal")
        self.info_text.delete(1.0, "end")
        self.info_text.insert("end", specs)
        self.info_text.config(state="disabled")

class AboutPage(BasePage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        container = tk.Frame(self, bg=self.controller.theme_colors["frame"], relief="solid", borderwidth=1)
        container.pack(expand=True, padx=50, pady=50)

        tk.Label(container, text="Activity Logger v5.0", font=controller.fonts["card_title"], bg="white").pack(pady=(20, 5))
        tk.Label(container, text="Developed By Muhammad Al-amin", font=controller.fonts["header"], bg="white").pack()
        
        self.create_link_row(container, "Email:", "mdalaminkhalifa2002@gmail.com", "mailto:mdalaminkhalifa2002@gmail.com")
        self.create_link_row(container, "Facebook:", "View Profile", "https://www.facebook.com/mdalamins20")

    def create_link_row(self, parent, title, text, url):
        frame = tk.Frame(parent, bg="white")
        frame.pack(pady=10)
        tk.Label(frame, text=title, font=self.controller.fonts["primary"], bg="white").pack(side="left")
        link = tk.Label(frame, text=text, font=self.controller.fonts["link"], bg="white", fg=self.controller.theme_colors["accent"], cursor="hand2")
        link.pack(side="left", padx=5)
        link.bind("<Button-1>", lambda e: webbrowser.open_new(url))

if __name__ == '__main__':
    root = tk.Tk()
    # To start the app hidden in the tray, uncomment the next line
    # root.withdraw() 
    app = ActivityLoggerApp(root)
    root.mainloop()
