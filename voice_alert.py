from gtts import gTTS
import pygame
import os
import tempfile
import time

class VoiceAlertSystem:
    def __init__(self):
        try:
            pygame.mixer.init()
            self.playing = False
            self.current_alert = None
            print("Voice Alert System initialized")
        except Exception as e:
            print(f"Error initializing pygame: {e}")
            self.playing = False
        
    def generate_speech(self, text, lang='en'):
        """Generate speech from text"""
        try:
            tts = gTTS(text=text, lang=lang, slow=False)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            tts.save(temp_file.name)
            return temp_file.name
        except Exception as e:
            print(f"Error generating speech: {e}")
            return None
    
    def play_alert(self, text, patient_name, medicine_name, room_number):
        """Play voice alert"""
        try:
            alert_text = f"Attention! {text}. Patient {patient_name} in room {room_number} needs {medicine_name}. Please respond immediately."
            print(f"Playing alert: {alert_text}")
            
            audio_file = self.generate_speech(alert_text)
            
            if audio_file:
                pygame.mixer.music.load(audio_file)
                pygame.mixer.music.play()
                self.playing = True
                
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                
                pygame.mixer.music.unload()
                try:
                    os.unlink(audio_file)
                except:
                    pass
                self.playing = False
                
            return True
        except Exception as e:
            print(f"Error playing alert: {e}")
            return False
    
    def play_escalation(self, patient_name, medicine_name, time_str, minutes_overdue):
        """Play escalation alert"""
        try:
            alert_text = f"Emergency! {patient_name} is {minutes_overdue} minutes overdue for {medicine_name}. All nurses please respond to room immediately."
            print(f"Playing escalation: {alert_text}")
            
            audio_file = self.generate_speech(alert_text)
            
            if audio_file:
                for i in range(3):
                    pygame.mixer.music.load(audio_file)
                    pygame.mixer.music.play()
                    self.playing = True
                    
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                    
                    if i < 2:
                        time.sleep(2)
                
                pygame.mixer.music.unload()
                try:
                    os.unlink(audio_file)
                except:
                    pass
                self.playing = False
                
            return True
        except Exception as e:
            print(f"Error playing escalation: {e}")
            return False
    
    def stop_alert(self):
        """Stop currently playing alert"""
        try:
            if self.playing:
                pygame.mixer.music.stop()
                self.playing = False
        except Exception as e:
            print(f"Error stopping alert: {e}")
