from flask import Flask, request, jsonify, session, render_template_string
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hosalert-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hosalert.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================== DATABASE MODELS ====================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer)
    room_number = db.Column(db.String(20))
    disease = db.Column(db.String(200))

class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'))
    name = db.Column(db.String(100))
    dosage = db.Column(db.String(50))
    time = db.Column(db.String(10))
    status = db.Column(db.String(20), default='pending')

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'))
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id'))
    message = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='active')

# ==================== HTML TEMPLATE WITH VOICE ====================

LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>HOSALERT - Login</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            width: 300px;
        }
        h2 { text-align: center; color: #333; }
        input {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        button {
            width: 100%;
            padding: 10px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        button:hover { background: #5a67d8; }
        .error { color: red; text-align: center; margin-top: 10px; }
        .voice-enabled {
            position: fixed;
            bottom: 10px;
            right: 10px;
            background: #28a745;
            color: white;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h2>🏥 HOSALERT</h2>
        <h3 style="text-align:center; color:#667eea;">Patient Medication Alert System</h3>
        <input type="text" id="username" placeholder="Username" value="nurse">
        <input type="password" id="password" placeholder="Password" value="nurse123">
        <button onclick="login()">Login</button>
        <div id="message"></div>
        <p style="text-align: center; margin-top: 20px; font-size: 12px;">Demo: nurse / nurse123</p>
    </div>
    <div class="voice-enabled">🔊 Voice Alerts Ready</div>
    <script>
        function speak(message) {
            if ('speechSynthesis' in window) {
                const utterance = new SpeechSynthesisUtterance(message);
                utterance.rate = 0.9;
                utterance.pitch = 1;
                window.speechSynthesis.cancel();
                window.speechSynthesis.speak(utterance);
            }
        }
        
        function login() {
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: username, password: password})
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    speak('Welcome to HOSALERT. Login successful.');
                    window.location.href = '/dashboard';
                } else {
                    document.getElementById('message').innerHTML = 
                        '<div class="error">Invalid credentials</div>';
                    speak('Login failed. Invalid credentials.');
                }
            });
        }
    </script>
</body>
</html>
'''

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>HOSALERT - Dashboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f4f4f4;
        }
        .header {
            background: #667eea;
            color: white;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .container {
            display: flex;
            gap: 20px;
        }
        .sidebar {
            width: 280px;
            background: white;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .main {
            flex: 1;
            background: white;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .patient-card {
            background: #f9f9f9;
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
            cursor: pointer;
            transition: background 0.3s;
        }
        .patient-card:hover { background: #e9e9e9; }
        .selected-patient {
            background: #667eea;
            color: white;
        }
        .selected-patient:hover { background: #5a67d8; }
        .alert {
            background: #ff4757;
            color: white;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            animation: pulse 0.5s infinite alternate;
        }
        @keyframes pulse {
            from { transform: scale(1); }
            to { transform: scale(1.02); }
        }
        button {
            background: #28a745;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 5px;
            cursor: pointer;
        }
        button:hover { background: #218838; }
        .medicine {
            background: #f0f0f0;
            padding: 10px;
            margin: 8px 0;
            border-radius: 5px;
            display: flex;
            justify-content: space-between;
        }
        h3 { margin: 0 0 15px 0; color: #333; }
        .stats {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: #667eea;
            color: white;
            padding: 15px;
            border-radius: 5px;
            flex: 1;
            text-align: center;
        }
        .logout {
            color: white;
            text-decoration: none;
            background: rgba(255,255,255,0.2);
            padding: 8px 15px;
            border-radius: 5px;
        }
        .voice-control {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .voice-toggle {
            background: #ff9800;
            padding: 8px 15px;
            border-radius: 5px;
            cursor: pointer;
        }
        .voice-status {
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h2>🏥 HOSALERT - Patient Medication Alert System</h2>
        <div class="voice-control">
            <div class="voice-toggle" onclick="toggleVoice()">
                🔊 Voice: <span id="voiceStatus">ON</span>
            </div>
            <a href="/logout" class="logout">Logout</a>
        </div>
    </div>
    
    <div class="stats" id="stats">
        <div class="stat-card">👨‍⚕️ Patients: <span id="patientCount">0</span></div>
        <div class="stat-card">💊 Medicines: <span id="medicineCount">0</span></div>
        <div class="stat-card">🔔 Alerts: <span id="alertCount">0</span></div>
    </div>
    
    <div class="container">
        <div class="sidebar">
            <h3>👨‍⚕️ Patients</h3>
            <div id="patientsList"></div>
        </div>
        
        <div class="main">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3>🔔 Active Alerts</h3>
                <div class="voice-status">🔊 New alerts will be spoken aloud</div>
            </div>
            <div id="alertsList"></div>
            
            <h3>💊 Medicines Schedule</h3>
            <div id="medicinesList"></div>
        </div>
    </div>
    
    <script>
        let currentPatientId = null;
        let voiceEnabled = true;
        let lastAlertIds = new Set();
        
        function speak(message) {
            if (!voiceEnabled) return;
            if ('speechSynthesis' in window) {
                const utterance = new SpeechSynthesisUtterance(message);
                utterance.rate = 0.9;
                utterance.pitch = 1;
                window.speechSynthesis.cancel();
                window.speechSynthesis.speak(utterance);
            }
        }
        
        function toggleVoice() {
            voiceEnabled = !voiceEnabled;
            document.getElementById('voiceStatus').innerText = voiceEnabled ? 'ON' : 'OFF';
            speak(voiceEnabled ? 'Voice alerts enabled' : 'Voice alerts disabled');
        }
        
        function loadPatients() {
            fetch('/api/patients')
                .then(res => res.json())
                .then(patients => {
                    const container = document.getElementById('patientsList');
                    document.getElementById('patientCount').innerText = patients.length;
                    container.innerHTML = patients.map(p => `
                        <div class="patient-card" onclick="selectPatient(${p.id})">
                            <strong>${p.name}</strong><br>
                            Room ${p.room_number} | Age ${p.age}
                        </div>
                    `).join('');
                    if(patients.length > 0 && !currentPatientId) selectPatient(patients[0].id);
                });
        }
        
        function selectPatient(id) {
            currentPatientId = id;
            document.querySelectorAll('.patient-card').forEach(card => {
                card.classList.remove('selected-patient');
            });
            event.target.closest('.patient-card').classList.add('selected-patient');
            loadMedicines(id);
            speak(`Selected patient ${id}`);
        }
        
        function loadMedicines(patientId) {
            fetch(`/api/medicines/${patientId}`)
                .then(res => res.json())
                .then(medicines => {
                    const container = document.getElementById('medicinesList');
                    document.getElementById('medicineCount').innerText = medicines.length;
                    container.innerHTML = medicines.map(m => `
                        <div class="medicine">
                            <span><strong>${m.name}</strong> - ${m.dosage}</span>
                            <span>⏰ ${m.time}</span>
                            <span style="color: ${m.status === 'pending' ? 'orange' : 'green'}">
                                ${m.status}
                            </span>
                        </div>
                    `).join('');
                });
        }
        
        function loadAlerts() {
            fetch('/api/alerts')
                .then(res => res.json())
                .then(alerts => {
                    const container = document.getElementById('alertsList');
                    document.getElementById('alertCount').innerText = alerts.length;
                    
                    // Check for new alerts and speak them
                    alerts.forEach(alert => {
                        if (!lastAlertIds.has(alert.id)) {
                            lastAlertIds.add(alert.id);
                            const alertMessage = `Alert for ${alert.patient_name}: ${alert.message}`;
                            speak(alertMessage);
                        }
                    });
                    
                    container.innerHTML = alerts.map(a => `
                        <div class="alert">
                            <span>🔔 <strong>${a.patient_name}</strong>: ${a.message}</span>
                            <button onclick="acknowledgeAlert(${a.id})">Acknowledge</button>
                        </div>
                    `).join('');
                    
                    // Keep only last 50 alert IDs
                    if (lastAlertIds.size > 50) {
                        const ids = Array.from(lastAlertIds);
                        lastAlertIds = new Set(ids.slice(-50));
                    }
                });
        }
        
        function acknowledgeAlert(alertId) {
            fetch(`/api/alerts/${alertId}/acknowledge`, {method: 'POST'})
                .then(() => {
                    speak('Alert acknowledged');
                    loadAlerts();
                });
        }
        
        // Auto-refresh every 10 seconds
        setInterval(() => {
            loadAlerts();
            loadPatients();
        }, 10000);
        
        // Speak welcome message
        window.onload = () => {
            speak('Welcome to HOSALERT dashboard. Monitoring patient medications.');
            loadPatients();
            loadAlerts();
        };
        
        loadPatients();
        loadAlerts();
    </script>
</body>
</html>
'''

# ==================== ROUTES ====================

@app.route('/')
def index():
    if 'user_id' in session:
        return render_template_string(DASHBOARD_HTML)
    return render_template_string(LOGIN_HTML)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return render_template_string(LOGIN_HTML)
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data['username'], password=data['password']).first()
    if user:
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        return jsonify({'success': True, 'role': user.role})
    return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/api/patients')
def get_patients():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    patients = Patient.query.all()
    return jsonify([{'id': p.id, 'name': p.name, 'age': p.age, 'room_number': p.room_number, 'disease': p.disease} for p in patients])

@app.route('/api/medicines/<int:patient_id>')
def get_medicines(patient_id):
    medicines = Medicine.query.filter_by(patient_id=patient_id).all()
    return jsonify([{'id': m.id, 'name': m.name, 'dosage': m.dosage, 'time': m.time, 'status': m.status} for m in medicines])

@app.route('/api/alerts')
def get_alerts():
    alerts = Alert.query.filter_by(status='active').order_by(Alert.created_at.desc()).limit(20).all()
    result = []
    for a in alerts:
        patient = Patient.query.get(a.patient_id)
        result.append({'id': a.id, 'patient_name': patient.name if patient else 'Unknown', 'message': a.message, 'time': a.created_at.strftime('%H:%M:%S')})
    return jsonify(result)

@app.route('/api/alerts/<int:alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    alert = Alert.query.get(alert_id)
    if alert:
        alert.status = 'acknowledged'
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/logout')
def logout():
    session.clear()
    return render_template_string(LOGIN_HTML)

# ==================== CREATE SAMPLE DATA ====================

def create_sample_data():
    with app.app_context():
        if not User.query.filter_by(username='nurse').first():
            nurse = User(username='nurse', password='nurse123', role='nurse', name='Head Nurse')
            db.session.add(nurse)
            db.session.commit()
            
            patient1 = Patient(name='Rajesh Kumar', age=65, room_number='101', disease='Hypertension')
            patient2 = Patient(name='Sumanth Reddy', age=45, room_number='102', disease='Diabetes')
            patient3 = Patient(name='Lakshmi Devi', age=58, room_number='103', disease='Blood Pressure')
            db.session.add_all([patient1, patient2, patient3])
            db.session.commit()
            
            medicine1 = Medicine(patient_id=1, name='Amlodipine', dosage='5mg', time='09:00', status='pending')
            medicine2 = Medicine(patient_id=2, name='Metformin', dosage='500mg', time='20:00', status='pending')
            medicine3 = Medicine(patient_id=3, name='Losartan', dosage='50mg', time='14:00', status='pending')
            medicine4 = Medicine(patient_id=1, name='Aspirin', dosage='75mg', time='21:00', status='pending')
            db.session.add_all([medicine1, medicine2, medicine3, medicine4])
            db.session.commit()
            
            alert1 = Alert(patient_id=1, medicine_id=1, message='Medication due: Amlodipine 5mg for Rajesh Kumar')
            alert2 = Alert(patient_id=2, medicine_id=2, message='Medication due: Metformin 500mg for Sumanth Reddy')
            alert3 = Alert(patient_id=3, medicine_id=3, message='Medication due: Losartan 50mg for Lakshmi Devi')
            db.session.add_all([alert1, alert2, alert3])
            db.session.commit()
            print("Sample data created successfully!")

# ==================== RUN APP ====================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_sample_data()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
