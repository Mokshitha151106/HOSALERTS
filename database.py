from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# Association table for many-to-many relationship between users and patients
user_patient = db.Table('user_patient',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('patient_id', db.Integer, db.ForeignKey('patients.id'), primary_key=True),
    db.Column('relationship', db.String(50)),
    db.Column('can_edit', db.Boolean, default=False),
    db.Column('can_view_vitals', db.Boolean, default=True),
    db.Column('can_view_meds', db.Boolean, default=True),
    db.Column('receive_alerts', db.Boolean, default=True),
    db.Column('assigned_at', db.DateTime, default=datetime.utcnow),
    extend_existing=True
)

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    user_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    patients = db.relationship('Patient', secondary=user_patient, 
                              backref=db.backref('assigned_users', lazy='dynamic'),
                              lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'user_type': self.user_type
        }
    
    def get_patients_with_details(self):
        """Get patients with relationship details"""
        results = db.session.query(Patient, user_patient).join(
            user_patient, Patient.id == user_patient.c.patient_id
        ).filter(user_patient.c.user_id == self.id).all()
        
        patients_with_details = []
        for patient, row in results:
            patient_dict = patient.to_dict()
            patient_dict.update({
                'relationship': row.relationship,
                'can_edit': row.can_edit,
                'can_view_vitals': row.can_view_vitals,
                'can_view_meds': row.can_view_meds,
                'receive_alerts': row.receive_alerts,
                'assigned_at': row.assigned_at.strftime('%Y-%m-%d %H:%M') if row.assigned_at else None
            })
            patients_with_details.append(patient_dict)
        
        return patients_with_details

class Patient(db.Model):
    __tablename__ = 'patients'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    room_number = db.Column(db.String(10))
    doctor_name = db.Column(db.String(100))
    admission_date = db.Column(db.DateTime, default=datetime.utcnow)
    diagnosis = db.Column(db.Text)
    allergies = db.Column(db.Text)
    
    vitals = db.relationship('VitalSign', backref='patient', lazy=True, cascade='all, delete-orphan')
    medicines = db.relationship('Medicine', backref='patient', lazy=True, cascade='all, delete-orphan')
    family_members = db.relationship('FamilyMember', backref='patient', lazy=True, cascade='all, delete-orphan')
    alerts = db.relationship('Alert', backref='patient', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'age': self.age,
            'gender': self.gender,
            'room_number': self.room_number,
            'doctor_name': self.doctor_name,
            'diagnosis': self.diagnosis,
            'allergies': self.allergies
        }

class VitalSign(db.Model):
    __tablename__ = 'vital_signs'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    heart_rate = db.Column(db.Integer)
    blood_pressure_systolic = db.Column(db.Integer)
    blood_pressure_diastolic = db.Column(db.Integer)
    temperature = db.Column(db.Float)
    oxygen_level = db.Column(db.Integer)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    recorded_by = db.Column(db.String(100))
    
    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'heart_rate': self.heart_rate,
            'blood_pressure': f"{self.blood_pressure_systolic}/{self.blood_pressure_diastolic}",
            'temperature': self.temperature,
            'oxygen_level': self.oxygen_level,
            'recorded_at': self.recorded_at.strftime('%H:%M'),
            'recorded_by': self.recorded_by
        }

class Medicine(db.Model):
    __tablename__ = 'medicines'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    dosage = db.Column(db.String(50))
    time = db.Column(db.String(5))
    instructions = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    last_given_time = db.Column(db.DateTime)
    last_given_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        patient = db.session.get(Patient, self.patient_id) if db.session else None
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'patient_name': patient.name if patient else None,
            'name': self.name,
            'dosage': self.dosage,
            'time': self.time,
            'instructions': self.instructions,
            'status': self.status,
            'last_given_time': self.last_given_time.strftime('%H:%M') if self.last_given_time else None,
            'last_given_by': self.last_given_by
        }

class FamilyMember(db.Model):
    __tablename__ = 'family_members'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    name = db.Column(db.String(100))
    relation = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'relation': self.relation,
            'phone': self.phone,
            'email': self.email
        }

class Alert(db.Model):
    __tablename__ = 'alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id'))
    message = db.Column(db.Text)
    alert_type = db.Column(db.String(20))
    severity = db.Column(db.String(20), default='normal')
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    acknowledged_at = db.Column(db.DateTime)
    acknowledged_by = db.Column(db.String(100))
    
    def to_dict(self):
        patient = db.session.get(Patient, self.patient_id) if db.session else None
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'patient_name': patient.name if patient else None,
            'room_number': patient.room_number if patient else None,
            'message': self.message,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'status': self.status,
            'created_at': self.created_at.strftime('%H:%M:%S'),
            'time_ago': self.get_time_ago()
        }
    
    def get_time_ago(self):
        diff = datetime.utcnow() - self.created_at
        seconds = diff.total_seconds()
        if seconds < 60:
            return 'just now'
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f'{minutes} minute{"s" if minutes > 1 else ""} ago'
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f'{hours} hour{"s" if hours > 1 else ""} ago'
        else:
            days = int(seconds / 86400)
            return f'{days} day{"s" if days > 1 else ""} ago'

class NurseChecklist(db.Model):
    __tablename__ = 'nurse_checklist'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    nurse_name = db.Column(db.String(100))
    task = db.Column(db.String(200))
    status = db.Column(db.String(20), default='pending')
    completed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
    def to_dict(self):
        patient = db.session.get(Patient, self.patient_id) if db.session else None
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'patient_name': patient.name if patient else None,
            'room_number': patient.room_number if patient else None,
            'nurse_name': self.nurse_name,
            'task': self.task,
            'status': self.status,
            'completed_at': self.completed_at.strftime('%H:%M') if self.completed_at else None,
            'notes': self.notes
        }

def init_db():
    """Initialize database with sample data"""
    db.create_all()
    
    # Create patients if none exist
    if Patient.query.count() == 0:
        sample_names = [
            "John Doe", "Jane Smith", "Robert Johnson", "Maria Garcia", 
            "William Brown", "Patricia Miller", "Michael Davis", "Elizabeth Wilson",
            "James Anderson", "Margaret Martinez", "Charles Taylor", "Susan Thomas",
            "Joseph Harris", "Nancy Martin", "David Thompson", "Karen White",
            "Steven Rodriguez", "Lisa Lewis", "Kevin Lee", "Betty Walker",
            "George Hall", "Donna Young"
        ]
        
        rooms = [f"{i}0{i}" for i in range(1, 23)]
        doctors = ["Dr. Smith", "Dr. Johnson", "Dr. Williams", "Dr. Brown", "Dr. Davis"]
        
        for i, name in enumerate(sample_names):
            patient = Patient(
                name=name,
                age=50 + (i % 30),
                gender="Male" if i % 2 == 0 else "Female",
                room_number=rooms[i],
                doctor_name=doctors[i % len(doctors)],
                diagnosis=f"Condition {i+1}",
                allergies=f"Allergy {i+1}" if i % 3 == 0 else "None"
            )
            db.session.add(patient)
            db.session.flush()
            
            # Add vitals
            vital = VitalSign(
                patient_id=patient.id,
                heart_rate=70 + (i % 15),
                blood_pressure_systolic=110 + (i % 20),
                blood_pressure_diastolic=70 + (i % 15),
                temperature=98.4 + (i % 5) / 10,
                oxygen_level=95 + (i % 5),
                recorded_by="System"
            )
            db.session.add(vital)
            
            # Add medicines
            medicine_times = ["08:00", "12:00", "18:00", "21:00"]
            medicine_names = ["Aspirin", "Metformin", "Lisinopril", "Atorvastatin"]
            
            for j, med_name in enumerate(medicine_names[:3]):
                medicine = Medicine(
                    patient_id=patient.id,
                    name=med_name,
                    dosage=f"{50 + (j*25)}mg",
                    time=medicine_times[j],
                    instructions="Take with food" if j % 2 == 0 else "Take on empty stomach",
                    status="pending"
                )
                db.session.add(medicine)
            
            # Add family member
            family = FamilyMember(
                patient_id=patient.id,
                name=f"Family of {name}",
                relation="Family Member",
                phone=f"+1 (555) {100 + i}-{1000 + i}",
                email=f"family{i}@email.com"
            )
            db.session.add(family)
            
            # Add nurse checklist
            checklist = NurseChecklist(
                patient_id=patient.id,
                nurse_name="Nurse Admin",
                task=f"Morning check for {name}",
                status="pending"
            )
            db.session.add(checklist)
        
        db.session.commit()
        print("Sample patients created!")
    
    # Create users if none exist
    if User.query.count() == 0:
        # Create nurses
        nurses = [
            {"username": "nurse_smith", "password": "nurse123", "name": "Nurse Smith", "email": "smith@hospital.com", "phone": "555-0101"},
            {"username": "nurse_jones", "password": "nurse123", "name": "Nurse Jones", "email": "jones@hospital.com", "phone": "555-0102"},
            {"username": "nurse_admin", "password": "admin123", "name": "Head Nurse", "email": "admin@hospital.com", "phone": "555-0001"}
        ]
        
        for n in nurses:
            nurse = User(
                username=n["username"],
                password=n["password"],
                name=n["name"],
                email=n["email"],
                phone=n["phone"],
                user_type="nurse"
            )
            db.session.add(nurse)
            print(f"Added nurse: {n['username']} with password: {n['password']}")
        
        # Create family members
        families = [
            {"username": "john_son", "password": "family123", "name": "John Son", "email": "john@email.com", "phone": "555-1001", "patient": "John Doe", "relation": "son"},
            {"username": "jane_daughter", "password": "family123", "name": "Jane Daughter", "email": "jane@email.com", "phone": "555-1002", "patient": "Jane Smith", "relation": "daughter"},
            {"username": "robert_wife", "password": "family123", "name": "Robert Wife", "email": "robert@email.com", "phone": "555-1003", "patient": "Robert Johnson", "relation": "wife"},
            {"username": "maria_husband", "password": "family123", "name": "Maria Husband", "email": "maria@email.com", "phone": "555-1004", "patient": "Maria Garcia", "relation": "husband"}
        ]
        
        for f in families:
            family = User(
                username=f["username"],
                password=f["password"],
                name=f["name"],
                email=f["email"],
                phone=f["phone"],
                user_type="family"
            )
            db.session.add(family)
            db.session.flush()
            print(f"Added family: {f['username']} with password: {f['password']}")
            
            # Link to patient
            patient = Patient.query.filter_by(name=f["patient"]).first()
            if patient:
                stmt = user_patient.insert().values(
                    user_id=family.id,
                    patient_id=patient.id,
                    relationship=f["relation"],
                    can_edit=False,
                    can_view_vitals=True,
                    can_view_meds=True,
                    receive_alerts=True,
                    assigned_at=datetime.utcnow()
                )
                db.session.execute(stmt)
                print(f"Linked {f['username']} to patient {f['patient']}")
        
        db.session.commit()
        print("Sample users created successfully!")
