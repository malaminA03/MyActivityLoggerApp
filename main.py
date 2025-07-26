import os
import threading
import time
from kivy.lang import Builder
from kivy.properties import StringProperty
from kivy.clock import Clock
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.datatables import MDDataTable
from kivy.metrics import dp

# Attempt to import google.generativeai
try:
    import google.generativeai as genai
    AI_ENABLED = True
except ImportError:
    AI_ENABLED = False

# --- KivyMD UI Layout (KV Language) ---
# এটি আপনার অ্যাপের সম্পূর্ণ ডিজাইন তৈরি করে
KV = '''
MDBoxLayout:
    orientation: 'vertical'
    md_bg_color: app.theme_cls.bg_light

    MDTopAppBar:
        title: app.title_text
        elevation: 4
        md_bg_color: app.theme_cls.primary_color
        specific_text_color: 1, 1, 1, 1 # White color for title

    MDBoxLayout:
        id: table_container
        padding: "10dp"

    MDBoxLayout:
        orientation: 'vertical'
        size_hint_y: None
        height: "140dp"
        padding: "10dp"
        spacing: "10dp"
        
        MDLabel:
            text: "AI Assistant"
            font_style: "H6"
            theme_text_color: "Primary"
            size_hint_y: None
            height: self.texture_size[1]

        MDLabel:
            id: ai_response_label
            text: "> AI: How can I help you analyze your activity?"
            theme_text_color: "Secondary"
            size_hint_y: None
            height: self.texture_size[1]

        MDTextField:
            id: query_input
            hint_text: "Ask AI about your activity"
            on_text_validate: app.ask_ai_assistant()

'''

class MainApp(MDApp):
    title_text = StringProperty("Activity Logger")

    def build(self):
        # --- Theme and Colors ---
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "SeaGreen" # আপনার পছন্দের সবুজ রঙ
        
        # --- Load UI from KV String ---
        self.screen = Builder.load_string(KV)
        
        # --- Create DataTable (টেবিল তৈরির কোড) ---
        self.data_table = MDDataTable(
            size_hint=(1, 1),
            use_pagination=True,
            rows_num=10,
            column_data=[
                ("Time", dp(40)),
                ("Activity", dp(60)),
            ],
        )
        self.screen.ids.table_container.add_widget(self.data_table)

        return self.screen

    def on_start(self):
        """অ্যাপটি চালু হওয়ার পর এই ফাংশনটি কাজ করে"""
        self.title_text = time.strftime("%B %Y").upper()
        # অ্যাপ চালু হলে কিছু ডেমো ডেটা দেখানো হচ্ছে
        self.load_initial_logs()
        
    def load_initial_logs(self):
        # সত্যিকারের অ্যাপে, আপনি এখানে ডেটাবেস থেকে লগ লোড করবেন
        dummy_data = [
            (time.strftime('%H:%M:%S'), "Application Started"),
            (time.strftime('%H:%M:%S'), "Viewing Home Screen"),
        ]
        for row in dummy_data:
            self.add_log_row(row)

    def add_log_row(self, row_data):
        """টেবিলে নতুন লগ যোগ করে"""
        self.data_table.add_row(row_data)

    def ask_ai_assistant(self):
        """AI-কে প্রশ্ন করার ফাংশন"""
        query_input = self.screen.ids.query_input
        user_question = query_input.text
        
        if not user_question:
            return

        query_input.text = "" # প্রশ্ন করার পর বক্স খালি হয়ে যাবে
        
        ai_response_label = self.screen.ids.ai_response_label
        ai_response_label.text = f"> User: {user_question}\n> AI: Thinking..."

        if not AI_ENABLED:
            ai_response_label.text = "> AI Error: 'google-generativeai' is not installed."
            return
            
        # UI ফ্রিজ হওয়া আটকাতে AI এর কাজ থ্রেডে চালানো হচ্ছে
        threading.Thread(target=self.get_ai_response_from_api, args=(user_question,)).start()

    def get_ai_response_from_api(self, user_question):
        """Gemini API থেকে উত্তর নিয়ে আসে"""
        try:
            # আপনার দেওয়া API কী এখানে বসানো আছে
            API_KEY = "AIzaSyCWnBU2dTeuYp6CsZicd0vjm4BW7IfIAVc"
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # সত্যিকারের অ্যাপে, আপনি এখানে আসল লগ ডেটা পাঠাবেন
            log_data = "2025-07-26 10:00 - YouTube, 2025-07-26 10:30 - VS Code"

            prompt = f"Analyze this log: '{log_data}'. Now answer: '{user_question}'"
            
            response = model.generate_content(prompt)
            final_response = f"> User: {user_question}\n> AI: {response.text}"
            
            # UI আপডেট করার জন্য মূল থ্রেডে অনুরোধ পাঠানো হচ্ছে
            Clock.schedule_once(lambda dt: self.update_ai_label(final_response))

        except Exception as e:
            error_message = f"> AI Error: {str(e)}"
            Clock.schedule_once(lambda dt: self.update_ai_label(error_message))
            
    def update_ai_label(self, text):
        self.screen.ids.ai_response_label.text = text


if __name__ == '__main__':
    MainApp().run()

