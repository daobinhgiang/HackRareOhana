from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
import speech_recognition as sr
import datetime
import threading
import requests
import json
import zipcodes
import matplotlib
matplotlib.use('Agg')  # So we can render on servers without a GUI
import matplotlib.pyplot as plt
import io
import base64
import numpy as np
from zipcode_utils import distance_between_zips, is_valid_zipcode, get_location_info,get_zipcode_info,format_location
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

calorieninjaapi_url = 'https://api.calorieninjas.com/v1/nutrition?query='
query = '31b carrots and a chicken sandwich'
response = requests.get(calorieninjaapi_url + query, headers = {'X-API-Key':'EjYbv/xYjRBFu7NcoIUM+g==OVU3eWStXQdFPnGL'})
if response.status_code == requests.codes.ok:
    print(response.text)
else:
    print("Error:", response.status_code, response.text)

app = Flask(__name__)

app.secret_key = 'your_secret_key_here'  # Replace with a secure secret key

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="User")
    
    # Standardized values (stored in metric)
    height = db.Column(db.Float, nullable=True)  # in meters
    weight = db.Column(db.Float, nullable=True)  # in kilograms
    
    # Fields for storing the original user inputs and units (optional)
    height_input = db.Column(db.Float, nullable=True)
    height_unit = db.Column(db.String(10), nullable=True)
    weight_input = db.Column(db.Float, nullable=True)
    weight_unit = db.Column(db.String(10), nullable=True)
    
    rare_diseases = db.Column(db.String(256), nullable=True)
    dob = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    nationality = db.Column(db.String(100), nullable=True)
    zip_code = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(20), nullable=True)

    @property
    def bmi(self):
        if self.height and self.weight and self.height > 0:
            return round(self.weight / (self.height ** 2), 2)
        return None
    @property
    def age(self):
        if self.dob:
            today = datetime.date.today()
            # Compute age based on year difference and adjust if birthday hasn't occurred yet this year.
            return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))
        return None

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # Check the user's password
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class MedicationInjection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medication_name = db.Column(db.String(200), nullable=False)
    injection_frequency = db.Column(db.String(50), nullable=False)  # e.g., daily, twice a day, etc.
    injection_area = db.Column(db.String(50), nullable=False)         # e.g., upper arm, thigh, hip, buttocks
    dose = db.Column(db.String(50), nullable=False)
    log_date_time = db.Column(db.DateTime)    

class FoodLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    food_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # e.g., serving size
    calories = db.Column(db.Float, nullable=False)
    nutrients = db.Column(db.String(200))  # e.g., "protein: 10g, carbs: 20g"
    log_date_time = db.Column(db.DateTime)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    activity = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.Float, nullable=False)  # in minutes
    water_intake = db.Column(db.Float, nullable=True)  # in liters
    log_date_time = db.Column(db.Date, default=datetime.date.today)

class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reminder_text = db.Column(db.String(200), nullable=False)
    reminder_time = db.Column(db.Time, nullable=False)

    


    # Set the user's password (hashing for security)
   

# Create the database tables if they don't exist yet
with app.app_context():
    db.create_all()


voice_assistant_active = False
is_listening = False
voice_thread = None

# Global variables to store the navigation command and command mode state
command = None
command_mode = False


def voice_assistant_thread():
    global voice_assistant_active, is_listening, command, command_mode
    voice_assistant_active = True
    is_listening = True

    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=2)
        print("Listening for 'Hey Buddy'...")
        while is_listening:
            try:
                # Listen for audio input (this call blocks until audio is captured)
                audio = recognizer.listen(source)
                text = recognizer.recognize_google(audio).lower()
                print(f"Heard: {text}")
                
                # If not in command mode, check for wake word
                if not command_mode:
                    if "hey buddy" in text:
                        print("Wake word detected! Command mode activated.")
                        command_mode = True
                else:
                    # If command mode is active, capture any spoken command (ignoring additional wake words)
                    if text and "hey buddy" not in text:
                        command = text.strip()
                        print(f"Command stored: {command}")
                        command_mode = False
                    else:
                        print("Still waiting for a command...")
            except sr.UnknownValueError:
                print("Could not understand audio.")
            except sr.RequestError as e:
                print(f"Request error from Google Speech Recognition service: {e}")
                time.sleep(1)

@app.route('/')
def index():
    # If user is not logged in, redirect to the login page
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['username'] = user.username
            session['role'] = user.role  # Save the user's role in the session
            return redirect(url_for('index'))
        else:
            error = 'Invalid username or password'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['username']).first()
    if not user:
        flash("User not found. Please log in again.")
        return redirect(url_for('login'))

    # For Admins, skip profile details update since only username and password are required
    if user.role == "Admin":
        # Optionally, you can allow admins to change their password or view basic info.
        if request.method == 'POST':
            # Example: allow admin to update their password
            new_password = request.form.get('password')
            if new_password:
                user.set_password(new_password)
                db.session.commit()
                flash('Password updated successfully.')
            return redirect(url_for('profile'))
        return render_template('profile.html', user=user)
    
    # For non-admin users, handle full profile update (POST) and display profile details (GET)
    if request.method == 'POST':
        # Update profile for non-admin users
        try:
            user.height = float(request.form.get('height')) if request.form.get('height') else None
        except ValueError:
            user.height = None
        try:
            user.weight = float(request.form.get('weight')) if request.form.get('weight') else None
        except ValueError:
            user.weight = None
        user.rare_diseases = request.form.get('rare_diseases')
        try:
            user.dob = datetime.datetime.strptime(request.form.get('dob'), "%Y-%m-%d").date() if request.form.get('dob') else None
        except ValueError:
            user.dob = None
        user.gender = request.form.get('gender')
        user.nationality = request.form.get('nationality')
        user.zip_code = request.form.get('zip_code')
        db.session.commit()
        flash('Profile updated successfully.')
        return redirect(url_for('profile'))

    # For GET requests, if the user has provided a rare disease, optionally call the FindZebra API.
    disease_info = None
    if user.rare_diseases:
        api_url = "https://www.findzebra.com/api/search"
        params = {"q": user.rare_diseases}
        try:
            response = requests.get(api_url, params=params)
            response.raise_for_status()
            disease_info = response.json()
        except Exception as e:
            disease_info = {"error": str(e)}

    return render_template('profile.html', user=user, disease_info=disease_info)

@app.route('/mapuser')
def mapuser():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('map.html')

@app.route('/start_voice', methods=['POST'])
def start_voice():
    global voice_assistant_active, voice_thread
    if not voice_assistant_active:
        voice_thread = threading.Thread(target=voice_assistant_thread, daemon=True)
        voice_thread.start()
    return jsonify({"status": "started"})

@app.route('/stop_voice', methods=['POST'])
def stop_voice():
    global voice_assistant_active, is_listening
    voice_assistant_active = False
    is_listening = False
    return jsonify({"status": "stopped"})

# Endpoint to check for navigation commands
@app.route('/check_navigation', methods=['GET'])
def check_navigation():
    global command
    current_command = command
    command = None  # Clear the command after retrieval
    return jsonify({"command": current_command})

@app.route('/register', methods=['GET', 'POST'])

def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Check if username already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists!')
            return redirect(url_for('register'))

        # Create a new user with the default role "User"
        new_user = User(username=username)
        new_user.set_password(password)
        # new_user.role is automatically "User" by default; 
        # To create an admin manually, you could set: new_user.role = "Admin"
        db.session.add(new_user)
        db.session.commit()
        flash('User registered successfully! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/users')

def list_users():
    if 'username' not in session or session.get('role') != 'Admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    all_users = User.query.all()
    return render_template('users.html', users=all_users)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user = User.query.filter_by(username=session['username']).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    print("DATA RECEIVED:", data)
    
    user.rare_diseases = data.get('rare_diseases',None)

    # Rest of the existing update_profile route remains the same
    try:
        # Handle height conversion (only "cm" or "ft" allowed)
        try:
            height_val = float(data.get('height')) if data.get('height') else None
        except ValueError:
            height_val = None

        height_unit = data.get('height_unit')
        height_in_m = None
        if height_val is not None:
            if height_unit == 'cm':
                height_in_m = height_val / 100.0
            elif height_unit == 'ft':
                height_in_m = height_val * 0.3048

        # Handle weight conversion (only "kg" or "lb" allowed)
        try:
            weight_val = float(data.get('weight')) if data.get('weight') else None
        except ValueError:
            weight_val = None

        weight_unit = data.get('weight_unit')
        weight_in_kg = None
        if weight_val is not None:
            if weight_unit == 'lb':
                weight_in_kg = weight_val * 0.453592
            elif weight_unit == 'kg':
                weight_in_kg = weight_val

        # Update user's metric values and store original inputs
        user.height = height_in_m
        user.weight = weight_in_kg
        user.height_input = height_val
        user.height_unit = height_unit
        user.weight_input = weight_val
        user.weight_unit = weight_unit

        # Handle DOB conversion: expected format "YYYY-MM-DD"
        dob_str = data.get('dob')
        if dob_str:
            try:
                user.dob = datetime.datetime.strptime(dob_str, "%Y-%m-%d").date()
            except ValueError as ve:
                print("DOB conversion error:", ve)
                user.dob = None
        else:
            user.dob = None

        user.gender = data.get('gender')
        user.nationality = data.get('nationality')
        user.zip_code = data.get('zip_code')
        user.email = data.get('email')
        user.phone = data.get('phone')

        # Commit and log the results
        db.session.commit()
        print("Profile update committed successfully")
        
        # Verify the saved rare disease
        user_after_update = User.query.get(user.id)
        print("Rare diseases after update:", user_after_update.rare_diseases)

    except Exception as e:
        db.session.rollback()
        print("DB commit error:", e)
        return jsonify({"error": str(e)}), 500

    bmi_value = float(user.bmi) if user.bmi is not None else None
    age_value = user.age if user.age is not None else None

    return jsonify({
        "message": "Profile updated successfully",
        "bmi": bmi_value,
        "age": age_value,
        "rare_diseases": user.rare_diseases  # Include rare_diseases in the response
    })


@app.route('/search_disease', methods=['GET'])
def search_disease():
    query = request.args.get('query', '')
    if not query:
        return jsonify({'error': 'No query provided'}), 400

    # Your personal API key from FindZebra (make sure to keep this secure)
    api_key = "587f2678-3107-4d50-9652-a809b725e260"  # Replace with your actual API key

    # Use the correct endpoint per FindZebra's documentation
    api_url = "https://www.findzebra.com/api/v1/query"

    # Set up the parameters
    params = {
        "api_key": api_key,
        "q": query,
        "response_format": "json",  # optional; defaults to json
        "rows": 1,  # maximum number of results (adjust as needed)
        # "start": 0,  # optional: offset in the results, if needed
        # "fl": "title,display_content,source,source_url,genes,cui,score"  # optional: fields you want
    }

    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()  # raise an error if the request failed
        data = response.json()
        print(json.dumps(data, indent=2))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(data)


@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if 'username' not in session or session.get('role') != 'Admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('list_users'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role', 'User')  # Default role is 'User'
        
        # Standardized values
        try:
            height = float(request.form.get('height')) if request.form.get('height') else None
        except ValueError:
            height = None
        try:
            weight = float(request.form.get('weight')) if request.form.get('weight') else None
        except ValueError:
            weight = None

        # Original input values and units
        try:
            height_input = float(request.form.get('height_input')) if request.form.get('height_input') else None
        except ValueError:
            height_input = None
        height_unit = request.form.get('height_unit')
        
        try:
            weight_input = float(request.form.get('weight_input')) if request.form.get('weight_input') else None
        except ValueError:
            weight_input = None
        weight_unit = request.form.get('weight_unit')
        
        # Additional metadata
        rare_diseases = request.form.get('rare_diseases')
        dob = None
        dob_str = request.form.get('dob')
        if dob_str:
            try:
                dob = datetime.datetime.strptime(dob_str, "%Y-%m-%d").date()
            except ValueError:
                dob = None
        gender = request.form.get('gender')
        nationality = request.form.get('nationality')
        zip_code = request.form.get('zip_code')
        
        # Check if username already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'warning')
            return redirect(url_for('add_user'))
        
        # Create the new user with full metadata
        new_user = User(
            username=username,
            role=role,
            height=height,
            weight=weight,
            height_input=height_input,
            height_unit=height_unit,
            weight_input=weight_input,
            weight_unit=weight_unit,
            rare_diseases=rare_diseases,
            dob=dob,
            gender=gender,
            nationality=nationality,
            zip_code=zip_code
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()

        flash('User added successfully with full metadata!', 'success')
        return redirect(url_for('list_users'))

    return render_template('add_user.html')


@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'username' not in session or session.get('role') != 'Admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('list_users'))
    
    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully!', 'success')
    else:
        flash('User not found!', 'danger')
    return redirect(url_for('list_users'))


@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    # Only allow Admins to access this route
    if 'username' not in session or session.get('role') != 'Admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('list_users'))

    user = User.query.get(user_id)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for('list_users'))

    if request.method == 'POST':
        # Update profile fields
        try:
            user.height = float(request.form.get('height')) if request.form.get('height') else None
        except ValueError:
            user.height = None
        try:
            user.weight = float(request.form.get('weight')) if request.form.get('weight') else None
        except ValueError:
            user.weight = None

        try:
            user.height_input = float(request.form.get('height_input')) if request.form.get('height_input') else None
        except ValueError:
            user.height_input = None
        user.height_unit = request.form.get('height_unit')

        try:
            user.weight_input = float(request.form.get('weight_input')) if request.form.get('weight_input') else None
        except ValueError:
            user.weight_input = None
        user.weight_unit = request.form.get('weight_unit')

        user.rare_diseases = request.form.get('rare_diseases')
        dob_str = request.form.get('dob')
        if dob_str:
            try:
                user.dob = datetime.datetime.strptime(dob_str, "%Y-%m-%d").date()
            except ValueError:
                user.dob = None
        else:
            user.dob = None
        user.gender = request.form.get('gender')
        user.nationality = request.form.get('nationality')
        user.zip_code = request.form.get('zip_code')

        db.session.commit()
        flash("User updated successfully", "success")
        return redirect(url_for('list_users'))

    return render_template('edit_user.html', user=user)

@app.route('/nutritiontracker', methods=['GET', 'POST'])
def nutritiontracker():
    result = None
    error = None
    if request.method == 'POST':
        # Get the user input from the form
        query = request.form.get('query')
        # Build the CalorieNinjas API URL
        calorieninjaapi_url = 'https://api.calorieninjas.com/v1/nutrition?query='
        headers = {'X-API-Key': 'EjYbv/xYjRBFu7NcoIUM+g==OVU3eWStXQdFPnGL'}
        response = requests.get(calorieninjaapi_url + query, headers=headers)
        
        # Print the API response to the console
        print("CalorieNinjas API response status:", response.status_code)
        if response.status_code == requests.codes.ok:
            result = response.json()
            print("CalorieNinjas API response data:", json.dumps(result, indent=2))
        else:
            error = f"Error: {response.status_code} {response.text}"
    return render_template('nutritiontracker.html', result=result, error=error)

@app.route('/calorie', methods=['GET', 'POST'])
def calorie():
    error = None
    food_items = []  # ✅ Store multiple food entries

    if request.method == 'POST':
        query = request.form.get('query')
        calorieninjaapi_url = 'https://api.calorieninjas.com/v1/nutrition?query=' + query
        headers = {'X-API-Key': 'EjYbv/xYjRBFu7NcoIUM+g==OVU3eWStXQdFPnGL'}  # Replace with your API key
        response = requests.get(calorieninjaapi_url, headers=headers)

        print("CalorieNinjas API response status:", response.status_code)
        
        if response.status_code == requests.codes.ok:
            result = response.json()
            print("CalorieNinjas API response data:", json.dumps(result, indent=2))

            if result.get("items"):  # Ensure "items" exists and is not empty
                for item in result["items"]:  # ✅ Loop through all items
                    food_name = item.get("name", "N/A")
                    calorie_result = item.get("calories", 0)
                    quantity = item.get("serving_size_g", 0)
                    nutrients_str = (
                        f"Protein: {item.get('protein_g', 0)}g, "
                        f"Carbs: {item.get('carbohydrates_total_g', 0)}g, "
                        f"Fat: {item.get('fat_total_g', 0)}g"
                    )

                    # Store log time
                    log_date_time = datetime.datetime.now()

                    # ✅ Save each entry to the database
                    food_log_entry = FoodLog(
                        food_name=food_name,
                        quantity=quantity,
                        calories=calorie_result,
                        nutrients=nutrients_str,
                        log_date_time=log_date_time
                    )
                    db.session.add(food_log_entry)
                    food_items.append(food_log_entry)  # ✅ Append to list

                db.session.commit()  # ✅ Commit all at once
            else:
                error = "No food items found in API response."
        else:
            error = f"Error: {response.status_code} {response.text}"

    # Retrieve all stored entries from the database for display
    stored_food_logs = FoodLog.query.order_by(FoodLog.log_date_time.desc()).all()

    return render_template('calorie.html',
                           food_items=food_items,
                           stored_food_logs=stored_food_logs,  # ✅ Pass stored logs to template
                           error=error)


def voice_assistant_thread():
    global voice_assistant_active, is_listening, command, command_mode
    voice_assistant_active = True
    is_listening = True
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Calibrating for ambient noise...")
        # Adjust ambient noise level; increase duration if needed.
        recognizer.adjust_for_ambient_noise(source, duration=3)
        print("Energy threshold set to:", recognizer.energy_threshold)
        # Optionally, fine-tune manually:
        # recognizer.energy_threshold = 400  # Example value for a noisy environment

        print("Listening for 'Hey Buddy'...")
        while is_listening:
            try:
                audio = recognizer.listen(source)
                text = recognizer.recognize_google(audio).lower()
                print(f"Heard: {text}")
                
                if not command_mode:
                    if "hey buddy" in text:
                        print("Wake word detected! Command mode activated.")
                        command_mode = True
                else:
                    if text and "hey buddy" not in text:
                        command = text.strip()
                        print(f"Command stored: {command}")
                        command_mode = False
                    else:
                        print("Still waiting for a command...")
            except sr.UnknownValueError:
                print("Could not understand audio.")
            except sr.RequestError as e:
                print(f"Request error from Google Speech Recognition service: {e}")
                time.sleep(1)

from datetime import datetime

@app.route('/medication', methods=['GET', 'POST'])
def medication():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        medication_name = request.form.get('medication_name')
        injection_frequency = request.form.get('injection_frequency')
        injection_area = request.form.get('injection_area')
        dose = request.form.get('dose')

        # Create a new medication log with log_date_time set to the current timestamp
        new_med = MedicationInjection(
            medication_name=medication_name,
            injection_frequency=injection_frequency,
            injection_area=injection_area,
            dose=dose,
            log_date_time=datetime.now()  # ✅ Automatically set log date time
        )

        db.session.add(new_med)
        db.session.commit()
        flash("Medication injection record added successfully!", "success")
        return redirect(url_for('medication'))

    return render_template('medication.html')



@app.route('/search', methods=['GET'])
def search():
    if 'username' not in session:
        flash('Please log in to access this feature!', 'danger')
        return redirect(url_for('login'))
    
    # Get filter parameters
    min_age = request.args.get('min_age', type=int, default=0)
    max_age = request.args.get('max_age', type=int, default=100)
    zip_code = request.args.get('zip_code', '')
    radius = request.args.get('radius', type=int, default=50)
    email_query = request.args.get('email', '').strip().lower()
    phone_query = request.args.get('phone', '').strip().lower()

    all_users = User.query.all()
    
    # Filter users based on age
    filtered_users = [user for user in all_users if user.age is not None and min_age <= user.age <= max_age]
    
    # NEW: Rare disease filter
    rare_diseases_search = request.args.get('rare_diseases', '').strip()  # e.g. "Down"
    if rare_diseases_search:
        # Filter further to only those with matching text in user.rare_diseases
        # We'll do a simple "substring" match (case-insensitive)
        search_lower = rare_diseases_search.lower()
        filtered_users = [
            u for u in filtered_users
            if u.rare_diseases and search_lower in u.rare_diseases.lower()
        ]
    
    # Then do your existing ZIP/radius filter
    zip_error = None
    location_info = None
    if zip_code:
    # Validate ZIP code
        if not zipcodes.is_real(zip_code):
            zip_error = f"Invalid or unknown ZIP code: {zip_code}"
        else:
            zip_info = get_zipcode_info(zip_code)
            if zip_info:
                location_info = f"{zip_info['city']}, {zip_info['state']}"
                nearby_users = []
            
                for user in filtered_users:
                    if user.zip_code and zipcodes.is_real(user.zip_code):
                        # Calculate distance between ZIP codes
                        dist = distance_between_zips(zip_code, user.zip_code)
                        if dist is not None and dist <= radius:
                            # Add distance property to user object
                            user.distance = round(dist, 1)
                            # Add location info to user object
                            user.location = format_location(user.zip_code)
                            nearby_users.append(user)
                
                # Sort by distance
                nearby_users.sort(key=lambda x: x.distance)
                filtered_users = nearby_users
            else:
                zip_error = f"Could not find information for ZIP code: {zip_code}"
    if email_query:
        filtered_users = [u for u in filtered_users
                          if u.email and email_query in u.email.lower()]
    if phone_query:
        filtered_users = [u for u in filtered_users
                          if u.phone and phone_query in u.phone.lower()]
    
    is_admin = session.get('role') == 'Admin'
    
    return render_template(
        'search.html', 
        users=filtered_users, 
        min_age=min_age, 
        max_age=max_age,
        zip_code=zip_code,
        radius=radius,
        zip_error=zip_error,
        location_info=location_info,
        is_admin=is_admin
    )

import matplotlib.pyplot as plt
import io
import base64
import pandas as pd

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()
    if not user:
        flash("User not found. Please log in again.")
        return redirect(url_for('login'))

    # Generate growth charts
    male_height_plot   = make_chart("Male",   "Height", user)
    female_height_plot = make_chart("Female", "Height", user)
    male_weight_plot   = make_chart("Male",   "Weight", user)
    female_weight_plot = make_chart("Female", "Weight", user)
    male_bmi_plot      = make_chart("Male",   "BMI",    user)
    female_bmi_plot    = make_chart("Female", "BMI",    user)

    # Retrieve food logs with valid timestamps for calorie intake chart
    food_logs = FoodLog.query.filter(FoodLog.log_date_time.isnot(None)) \
                             .order_by(FoodLog.log_date_time.asc()) \
                             .all()

    calorie_chart = None
    if food_logs:
        # Extract time and calorie values
        times = [log.log_date_time.strftime("%H:%M") for log in food_logs]  # Convert to HH:MM format
        calories = [log.calories for log in food_logs]

        # Create a DataFrame for visualization
        df = pd.DataFrame({'Time': times, 'Calories': calories})

        # Plot line chart
        plt.figure(figsize=(8, 5))
        plt.plot(df['Time'], df['Calories'], marker='o', linestyle='-', color='b', label="Calories Intake")
        plt.xlabel('Time of Day')
        plt.ylabel('Calories')
        plt.title('Calories Intake Over Time')
        plt.xticks(rotation=45)
        plt.legend()
        plt.grid()

        # Convert plot to base64 for embedding in HTML
        img = io.BytesIO()
        plt.tight_layout()
        plt.savefig(img, format='png')
        plt.close()
        img.seek(0)
        calorie_chart = base64.b64encode(img.getvalue()).decode()

    return render_template(
        "dashboard.html",
        user=user,
        male_height_plot=male_height_plot,
        female_height_plot=female_height_plot,
        male_weight_plot=male_weight_plot,
        female_weight_plot=female_weight_plot,
        male_bmi_plot=male_bmi_plot,
        female_bmi_plot=female_bmi_plot,
        calorie_chart=calorie_chart  # Pass calorie chart to the template
    )



def make_chart(sex, measure, user=None):
    """
    Create a Matplotlib figure for the given sex ("Male"/"Female") and measure ("Height"/"Weight"/"BMI").
    Uses dummy data arrays for 3, 25, 50, 75, 97th percentiles from ages 0 to 20.
    If a 'user' is provided and user.gender matches 'sex', we plot a star for their data.
    """
    import matplotlib.pyplot as plt
    import io
    import base64
    import numpy as np
    
    # Generate some ages (0 to 20)
    ages = np.linspace(0, 20, 21)
    
    # Hardcoded percentile data for each measure
    if measure == "Height":
        base = 70 if sex == "Male" else 65
        top  = 180 if sex == "Male" else 170
        p3   = np.linspace(base - 5,  top - 20, 21)
        p25  = np.linspace(base,      top - 15, 21)
        p50  = np.linspace(base + 5,  top - 10, 21)
        p75  = np.linspace(base + 10, top - 5,  21)
        p97  = np.linspace(base + 15, top,      21)
    elif measure == "Weight":
        if sex == "Male":
            p3  = np.linspace(4,  50, 21)
            p25 = np.linspace(5,  60, 21)
            p50 = np.linspace(6,  70, 21)
            p75 = np.linspace(7,  80, 21)
            p97 = np.linspace(8,  90, 21)
        else:
            p3  = np.linspace(4,  45, 21)
            p25 = np.linspace(5,  50, 21)
            p50 = np.linspace(6,  55, 21)
            p75 = np.linspace(7,  65, 21)
            p97 = np.linspace(8,  75, 21)
    else:  # BMI
        if sex == "Male":
            p3  = np.linspace(13, 16, 21)
            p25 = np.linspace(14, 18, 21)
            p50 = np.linspace(15, 20, 21)
            p75 = np.linspace(17, 25, 21)
            p97 = np.linspace(20, 30, 21)
        else:
            p3  = np.linspace(13, 15, 21)
            p25 = np.linspace(14, 17, 21)
            p50 = np.linspace(15, 19, 21)
            p75 = np.linspace(17, 24, 21)
            p97 = np.linspace(20, 28, 21)
    
    # Create the plot
    fig, ax = plt.subplots(figsize=(5, 4), dpi=100)
    
    # Plot each percentile line
    ax.plot(ages, p3,  label="3rd",  linestyle="--")
    ax.plot(ages, p25, label="25th", linestyle="-.")
    ax.plot(ages, p50, label="50th", linestyle="-")
    ax.plot(ages, p75, label="75th", linestyle="--")
    ax.plot(ages, p97, label="97th", linestyle="-.")
    
    ax.set_title(f"{sex} {measure} Growth Chart")
    ax.set_xlabel("Age (years)")
    
    # Axis labels
    if measure == "Height":
        ax.set_ylabel("Height (cm)")
    elif measure == "Weight":
        ax.set_ylabel("Weight (kg)")
    else:
        ax.set_ylabel("BMI (kg/m²)")
    
    # ================ PLOT USER’S DATA AS A STAR ================
    if user is not None and user.gender == sex:
        # Only plot if user has an age, plus relevant data for measure
        if user.age is not None and 0 <= user.age <= 20:
            # Convert user’s data to chart scale
            if measure == "Height" and user.height:
                # user.height is in meters → convert to cm
                user_val = user.height * 100
            elif measure == "Weight" and user.weight:
                user_val = user.weight
            elif measure == "BMI" and user.bmi:
                user_val = user.bmi
            else:
                user_val = None
    
            # If we got a valid user_val, plot it
            if user_val is not None:
                ax.plot(
                    [user.age], [user_val],
                    marker='*', markersize=15, label="Your Data" # color="blue" if you prefer
                )
    # ============================================================
    
    ax.legend()
    
    # Convert plot to base64-encoded PNG
    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    base64_img = base64.b64encode(buf.getvalue()).decode("utf-8")
    
    return base64_img


@app.route('/basicinfo')
def basicinfo():
    # Require user to be logged in
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Retrieve the current user's record from the database
    user = User.query.filter_by(username=session['username']).first()
    if not user:
        flash("User not found. Please log in again.")
        return redirect(url_for('login'))
    
    # Pass user info to a new template called 'basic_info.html'
    return render_template('basicinfo.html', user=user)

@app.route('/foodlog')
def foodlog():
    # Retrieve only logs that have a valid log_date_time, ordered by newest first
    stored_food_logs = FoodLog.query.filter(FoodLog.log_date_time.isnot(None)) \
                                    .order_by(FoodLog.log_date_time.desc()) \
                                    .all()

    return render_template('foodlog.html', stored_food_logs=stored_food_logs)

@app.route('/medicationlog')
def medicationlog():
    if 'username' not in session:
        return redirect(url_for('login'))

    # Retrieve only the medication logs that have a valid log_date_time
    medications = MedicationInjection.query.filter(MedicationInjection.log_date_time.isnot(None)).all()

    return render_template('medicationlog.html', medications=medications)

if __name__ == '__main__':
    app.run(debug=True)
