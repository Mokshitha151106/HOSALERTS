from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import threading
import time
import socket
import json

# Import local modules
from database import db, Patient, VitalSign, Medicine, FamilyMember, Alert, NurseChecklist, User, user_patient, init_db
from voice_alert import VoiceAlertSystem

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hosalerts-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hosalerts.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize voice alert system
voice_system = VoiceAlertSystem()

# Voice Alert Manager for socket communication
class VoiceAlertManager:
    def __init__(self):
        self.voice_system = voice_system
        self.active_alerts = {}
        self.offline_alerts = []
    
    def trigger_alert(self, patient_name, medicine_name, room_number, message):
        alert_data = {
            'patient_name': patient_name,
            'medicine_name': medicine_name,
            'room_number': room_number,
            'message': message,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'type': 'alert'
        }
        # Play actual voice alert
        self.voice_system.play_alert(
            message,
            patient_name,
            medicine_name,
            room_number
        )
        socketio.emit('voice_alert', alert_data)
        return alert_data
    
    def trigger_escalation(self, patient_name, medicine_name, room_number, minutes_overdue):
        alert_data = {
            'patient_name': patient_name,
            'medicine_name': medicine_name,
            'room_number': room_number,
            'minutes_overdue': minutes_overdue,
            'type': 'escalation',
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }
        # Play escalation voice alert
        self.voice_system.play_escalation(
            patient_name,
            medicine_name,
            datetime.now().strftime('%H:%M'),
            minutes_overdue
        )
        socketio.emit('voice_alert_escalation', alert_data)
        return alert_data
    
    def store_offline_alert(self, alert_data):
        """Store alert for offline clients"""
        self.offline_alerts.append({
            **alert_data,
            'stored_at': datetime.now().isoformat()
        })
        # Keep only last 100 alerts
        if len(self.offline_alerts) > 100:
            self.offline_alerts = self.offline_alerts[-100:]
    
    def get_offline_alerts(self, since_timestamp=None):
        """Get offline alerts for syncing"""
        if since_timestamp:
            return [a for a in self.offline_alerts 
                   if a.get('stored_at', '') > since_timestamp]
        return self.offline_alerts
    
    def stop_alert(self):
        self.voice_system.stop_alert()

voice_manager = VoiceAlertManager()

# Background alert checker
def check_medication_alerts():
    while True:
        with app.app_context():
            current_time = datetime.now().strftime('%H:%M')
            
            # Check for due medications
            medicines = Medicine.query.filter_by(time=current_time, status='pending').all()
            
            for medicine in medicines:
                patient = db.session.get(Patient, medicine.patient_id)
                
                if patient:
                    # Check if alert already exists
                    existing = Alert.query.filter_by(
                        medicine_id=medicine.id,
                        status='active'
                    ).first()
                    
                    if not existing:
                        # Create alert
                        alert = Alert(
                            patient_id=patient.id,
                            medicine_id=medicine.id,
                            message=f"Medication due: {medicine.name} {medicine.dosage} for {patient.name}",
                            alert_type='medicine',
                            severity='high'
                        )
                        db.session.add(alert)
                        db.session.commit()
                        
                        # Trigger voice alert
                        voice_data = voice_manager.trigger_alert(
                            patient.name,
                            f"{medicine.name} {medicine.dosage}",
                            patient.room_number,
                            f"Time for {medicine.name}"
                        )
                        
                        # Store for offline clients
                        voice_manager.store_offline_alert(voice_data)
                        
                        socketio.emit('new_alert', alert.to_dict())
            
            # Check for overdue medications (10+ minutes)
            time_threshold = (datetime.now() - timedelta(minutes=10)).strftime('%H:%M')
            overdue = Medicine.query.filter(
                Medicine.time <= time_threshold,
                Medicine.status == 'pending'
            ).all()
            
            for medicine in overdue:
                patient = db.session.get(Patient, medicine.patient_id)
                
                if patient:
                    # Check if escalation already sent
                    existing = Alert.query.filter_by(
                        medicine_id=medicine.id,
                        alert_type='escalation',
                        status='active'
                    ).first()
                    
                    if not existing:
                        med_time = datetime.strptime(medicine.time, '%H:%M')
                        current = datetime.now()
                        minutes = (current.hour * 60 + current.minute) - (med_time.hour * 60 + med_time.minute)
                        
                        if minutes > 0:
                            alert = Alert(
                                patient_id=patient.id,
                                medicine_id=medicine.id,
                                message=f"URGENT: {medicine.name} overdue by {minutes} minutes for {patient.name}",
                                alert_type='escalation',
                                severity='critical'
                            )
                            db.session.add(alert)
                            db.session.commit()
                            
                            voice_data = voice_manager.trigger_escalation(
                                patient.name,
                                f"{medicine.name} {medicine.dosage}",
                                patient.room_number,
                                minutes
                            )
                            
                            voice_manager.store_offline_alert(voice_data)
                            
                            socketio.emit('new_alert', alert.to_dict())
        
        time.sleep(30)

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/test')
def test():
    return "App is working!"

# Serve static files
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

# ==================== NETWORK INFO ROUTE ====================
@app.route('/api/network-info', methods=['GET'])
def get_network_info():
    """Get network information for sharing"""
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        # Get local network IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 1))
            network_ip = s.getsockname()[0]
        except Exception:
            network_ip = '127.0.0.1'
        finally:
            s.close()
        
        return jsonify({
            'local': f'http://localhost:5000',
            'network': f'http://{network_ip}:5000',
            'hostname': hostname,
            'current': request.host_url
        })
    except Exception as e:
        return jsonify({'error': str(e)})

# ==================== OFFLINE SYNC ROUTE ====================
@app.route('/api/offline-sync', methods=['POST'])
def offline_sync():
    """Sync offline alerts when client comes back online"""
    try:
        data = request.json
        client_alerts = data.get('alerts', [])
        last_sync = data.get('last_sync')
        
        # Process any offline alerts from client
        for alert in client_alerts:
            # Store or process offline alerts
            print(f"Received offline alert: {alert}")
        
        # Return any missed alerts
        missed_alerts = voice_manager.get_offline_alerts(last_sync)
        
        return jsonify({
            'success': True,
            'synced': len(client_alerts),
            'missed_alerts': missed_alerts
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# User Management Routes
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        user_type = data.get('user_type')
        
        print(f"Login attempt - Username: {username}, Type: {user_type}")
        
        user = User.query.filter(
            User.username.ilike(username),
            User.user_type == user_type
        ).first()
        
        if user and user.password == password:
            session['user_id'] = user.id
            session['user_type'] = user.user_type
            session['username'] = user.username
            return jsonify({'success': True, 'user': user.to_dict()})
        
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    except Exception as e:
        print(f"Login error: {str(e)}")
        return jsonify({'success': False, 'message': 'Server error'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/current-user', methods=['GET'])
def get_current_user():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user:
            return jsonify(user.to_dict())
    return jsonify({'user': None})

# Patient Routes
@app.route('/api/my-patients', methods=['GET'])
def get_my_patients():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if user.user_type == 'nurse':
        patients = Patient.query.all()
        return jsonify([p.to_dict() for p in patients])
    else:
        patients = user.get_patients_with_details()
        return jsonify(patients)

@app.route('/api/patients/<int:patient_id>', methods=['GET'])
def get_patient(patient_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = db.session.get(User, session['user_id'])
    
    if user.user_type == 'nurse':
        patient = db.session.get(Patient, patient_id)
    else:
        patient = Patient.query.join(user_patient).filter(
            user_patient.c.user_id == user.id,
            Patient.id == patient_id
        ).first()
    
    return jsonify(patient.to_dict() if patient else {})

@app.route('/api/patients/<int:patient_id>/medicines', methods=['GET'])
def get_medicines(patient_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    medicines = Medicine.query.filter_by(patient_id=patient_id).order_by(Medicine.time).all()
    return jsonify([m.to_dict() for m in medicines])

@app.route('/api/patients/<int:patient_id>/vitals', methods=['GET'])
def get_vitals(patient_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    vitals = VitalSign.query.filter_by(patient_id=patient_id).order_by(VitalSign.recorded_at.desc()).limit(10).all()
    return jsonify([v.to_dict() for v in vitals])

@app.route('/api/medicines', methods=['POST'])
def add_medicine():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = db.session.get(User, session['user_id'])
    if user.user_type != 'nurse':
        return jsonify({'error': 'Only nurses can add medicines'}), 403
    
    data = request.json
    medicine = Medicine(
        patient_id=data['patient_id'],
        name=data['name'],
        dosage=data['dosage'],
        time=data['time'],
        instructions=data.get('instructions', ''),
        status='pending'
    )
    db.session.add(medicine)
    db.session.commit()
    socketio.emit('medicine_added', medicine.to_dict())
    return jsonify(medicine.to_dict()), 201

@app.route('/api/medicines/<int:medicine_id>/status', methods=['PUT'])
def update_medicine_status(medicine_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = db.session.get(User, session['user_id'])
    if user.user_type != 'nurse':
        return jsonify({'error': 'Only nurses can update medicine status'}), 403
    
    data = request.json
    medicine = db.session.get(Medicine, medicine_id)
    
    if medicine:
        medicine.status = data['status']
        if data['status'] == 'given':
            medicine.last_given_time = datetime.utcnow()
            medicine.last_given_by = user.name
            
            Alert.query.filter_by(medicine_id=medicine_id, status='active').update({
                'status': 'resolved',
                'acknowledged_at': datetime.utcnow(),
                'acknowledged_by': user.name
            })
        
        db.session.commit()
        socketio.emit('medicine_updated', medicine.to_dict())
        return jsonify(medicine.to_dict())
    return jsonify({'error': 'Medicine not found'}), 404

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = db.session.get(User, session['user_id'])
    
    if user.user_type == 'nurse':
        alerts = Alert.query.filter_by(status='active').order_by(Alert.created_at.desc()).limit(20).all()
    else:
        patient_ids = [row.patient_id for row in db.session.query(user_patient.c.patient_id).filter_by(user_id=user.id).all()]
        alerts = Alert.query.filter(
            Alert.patient_id.in_(patient_ids),
            Alert.status == 'active'
        ).order_by(Alert.created_at.desc()).limit(20).all()
    
    return jsonify([a.to_dict() for a in alerts])

@app.route('/api/alerts/<int:alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = db.session.get(User, session['user_id'])
    alert = db.session.get(Alert, alert_id)
    
    if alert:
        alert.status = 'acknowledged'
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = user.name
        db.session.commit()
        socketio.emit('alert_updated', alert.to_dict())
        voice_manager.stop_alert()
        return jsonify(alert.to_dict())
    return jsonify({'error': 'Alert not found'}), 404

@app.route('/api/patients/<int:patient_id>/family', methods=['GET'])
def get_family(patient_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    family = FamilyMember.query.filter_by(patient_id=patient_id).all()
    return jsonify([f.to_dict() for f in family])

@app.route('/api/checklist', methods=['GET'])
def get_checklist():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = db.session.get(User, session['user_id'])
    
    if user.user_type == 'nurse':
        checklist = NurseChecklist.query.filter_by(
            nurse_name=user.name, 
            status='pending'
        ).all()
        return jsonify([c.to_dict() for c in checklist])
    
    return jsonify({'error': 'Access denied'}), 403

@app.route('/api/checklist/<int:check_id>/complete', methods=['POST'])
def complete_checklist(check_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = db.session.get(User, session['user_id'])
    if user.user_type != 'nurse':
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.json
    item = db.session.get(NurseChecklist, check_id)
    if item and item.nurse_name == user.name:
        item.status = 'completed'
        item.completed_at = datetime.utcnow()
        item.notes = data.get('notes', '')
        db.session.commit()
        socketio.emit('checklist_updated', item.to_dict())
        return jsonify(item.to_dict())
    return jsonify({'error': 'Checklist item not found'}), 404

@app.route('/api/stats', methods=['GET'])
def get_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = db.session.get(User, session['user_id'])
    
    if user.user_type == 'nurse':
        total_patients = Patient.query.count()
        active_medicines = Medicine.query.filter_by(status='pending').count()
        active_alerts = Alert.query.filter_by(status='active').count()
        meds_today = Medicine.query.count()
    else:
        patient_ids = [row.patient_id for row in db.session.query(user_patient.c.patient_id).filter_by(user_id=user.id).all()]
        total_patients = len(patient_ids)
        active_medicines = Medicine.query.filter(
            Medicine.patient_id.in_(patient_ids),
            Medicine.status == 'pending'
        ).count()
        active_alerts = Alert.query.filter(
            Alert.patient_id.in_(patient_ids),
            Alert.status == 'active'
        ).count()
        meds_today = Medicine.query.filter(
            Medicine.patient_id.in_(patient_ids)
        ).count()
    
    return jsonify({
        'total_patients': total_patients,
        'active_medicines': active_medicines,
        'active_alerts': active_alerts,
        'meds_today': meds_today,
        'user_type': user.user_type,
        'user_name': user.name
    })

# SocketIO events
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('connected', {'data': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('request_offline_alerts')
def handle_offline_request(data):
    """Send missed alerts to reconnecting client"""
    last_sync = data.get('last_sync')
    missed = voice_manager.get_offline_alerts(last_sync)
    emit('offline_alerts', {'alerts': missed})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_db()
    
    alert_thread = threading.Thread(target=check_medication_alerts, daemon=True)
    alert_thread.start()
    
    print("=" * 50)
    print("Starting HOSALERTS server...")
    print("=" * 50)
    print("📍 Local URL: http://localhost:5000")
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 1))
        network_ip = s.getsockname()[0]
        s.close()
        print(f"📍 Network URL: http://{network_ip}:5000")
    except:
        pass
    
    print("=" * 50)
    print("✨ Features enabled:")
    print("   ✅ Voice Alerts with Beep Sounds")
    print("   ✅ Offline Alert Storage")
    print("   ✅ Auto-Sync when Online")
    print("   ✅ Vibration Support")
    print("=" * 50)
    print("\n🚀 For public access, run: ngrok http 5000\n")
    
    socketio.run(app, debug=True, port=5000)
