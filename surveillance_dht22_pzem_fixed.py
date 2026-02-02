"""
Système de Surveillance DHT22 + PZEM-004T
Version: 2.0 - Raspberry Pi 5
Affichage Terminal + Serveur Web + Base de données SQLite
"""

import sqlite3
import time
import json
import serial
from datetime import datetime, timedelta
from threading import Thread, Lock
from flask import Flask, jsonify, send_from_directory
import os
from collections import deque
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import math

# Import pour DHT22 sur Raspberry Pi 5
import board
import adafruit_dht

# Import pour PZEM-004T (communication ModBus RTU via USB/RS485)
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu


# ============================================================================
# MODÈLE DE DONNÉES
# ============================================================================

@dataclass
class MesureEnvironnement:
    """Mesure DHT22: température et humidité"""
    timestamp: str
    temperature_C: float
    humidity_pct: float
    point_rosee: float
    indice_chaleur: float


@dataclass
class MesureElectrique:
    """Mesure PZEM-004T: paramètres électriques"""
    timestamp: str
    voltage_V: float          # Volts
    current_A: float          # Ampères
    power_W: float            # Watts
    energy_Wh: float          # Wh
    frequency_Hz: float       # Hz
    power_factor: float       # 0-1
    alarm: int                # Alarme


# ============================================================================
# GESTIONNAIRE DE BASE DE DONNÉES
# ============================================================================

class DatabaseManager:
    """Gestion de la base de données SQLite avec création automatique"""
    
    def __init__(self, db_path: str = "surveillance.db"):
        self.db_path = db_path
        self.lock = Lock()
        self._creer_tables()
        print(f"✅ Base de données initialisée: {db_path}")
    
    def _creer_tables(self):
        """Crée automatiquement toutes les tables nécessaires"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Table des mesures environnementales (DHT22)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mesures_environnement (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    temperature_C REAL,
                    humidity_pct REAL,
                    point_rosee REAL,
                    indice_chaleur REAL
                )
            """)
            
            # Table des mesures électriques (PZEM-004T)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mesures_electriques (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    voltage_V REAL,
                    current_A REAL,
                    power_W REAL,
                    energy_Wh REAL,
                    frequency_Hz REAL,
                    power_factor REAL,
                    alarm INTEGER
                )
            """)
            
            # Index pour performances
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_env_timestamp 
                ON mesures_environnement(timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_elec_timestamp 
                ON mesures_electriques(timestamp)
            """)
            
            conn.commit()
            print("✅ Tables créées avec succès")
    
    def inserer_mesure_environnement(self, mesure: MesureEnvironnement):
        """Insère une mesure environnementale"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO mesures_environnement 
                    (timestamp, temperature_C, humidity_pct, point_rosee, indice_chaleur)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    mesure.timestamp,
                    mesure.temperature_C,
                    mesure.humidity_pct,
                    mesure.point_rosee,
                    mesure.indice_chaleur
                ))
                conn.commit()
    
    def inserer_mesure_electrique(self, mesure: MesureElectrique):
        """Insère une mesure électrique"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO mesures_electriques 
                    (timestamp, voltage_V, current_A, power_W, energy_Wh, frequency_Hz, power_factor, alarm)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    mesure.timestamp,
                    mesure.voltage_V,
                    mesure.current_A,
                    mesure.power_W,
                    mesure.energy_Wh,
                    mesure.frequency_Hz,
                    mesure.power_factor,
                    mesure.alarm
                ))
                conn.commit()
    
    def obtenir_mesures_recentes(self, limite: int = 100) -> Dict:
        """Récupère les mesures récentes des deux capteurs"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Mesures environnement
            cursor.execute("""
                SELECT * FROM mesures_environnement 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limite,))
            columns_env = [desc[0] for desc in cursor.description]
            mesures_env = [dict(zip(columns_env, row)) for row in cursor.fetchall()]
            
            # Mesures électriques
            cursor.execute("""
                SELECT * FROM mesures_electriques 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limite,))
            columns_elec = [desc[0] for desc in cursor.description]
            mesures_elec = [dict(zip(columns_elec, row)) for row in cursor.fetchall()]
            
            return {
                'environnement': mesures_env,
                'electrique': mesures_elec
            }
    
    def obtenir_statistiques(self, heures: int = 24) -> Dict:
        """Calcule les statistiques sur une période"""
        temps_limite = (datetime.now() - timedelta(hours=heures)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Stats environnement
            cursor.execute("""
                SELECT 
                    COUNT(*) as nb_mesures,
                    AVG(temperature_C) as temp_moy,
                    MIN(temperature_C) as temp_min,
                    MAX(temperature_C) as temp_max,
                    AVG(humidity_pct) as hum_moy,
                    MIN(humidity_pct) as hum_min,
                    MAX(humidity_pct) as hum_max
                FROM mesures_environnement 
                WHERE timestamp > ?
            """, (temps_limite,))
            columns_env = [desc[0] for desc in cursor.description]
            stats_env = dict(zip(columns_env, cursor.fetchone() or []))
            
            # Stats électriques
            cursor.execute("""
                SELECT 
                    COUNT(*) as nb_mesures,
                    AVG(voltage_V) as tension_moy,
                    AVG(current_A) as courant_moy,
                    AVG(power_W) as puissance_moy,
                    MAX(power_W) as puissance_max,
                    SUM(energy_Wh) as energie_totale,
                    AVG(frequency_Hz) as freq_moy,
                    AVG(power_factor) as fp_moy
                FROM mesures_electriques 
                WHERE timestamp > ?
            """, (temps_limite,))
            columns_elec = [desc[0] for desc in cursor.description]
            stats_elec = dict(zip(columns_elec, cursor.fetchone() or []))
            
            return {
                'environnement': stats_env,
                'electrique': stats_elec
            }


# ============================================================================
# CAPTEUR DHT22
# ============================================================================

class DHT22Sensor:
    """Gestion du capteur DHT22 (température + humidité)"""
    
    def __init__(self, gpio_pin: int = 23):
        """
        Initialise le DHT22
        gpio_pin: numéro GPIO BCM (par défaut GPIO23 = pin physique 16)
        """
        self.gpio_pin = gpio_pin
        
        # Mapper le GPIO au pin board
        gpio_mapping = {
            23: board.D23,
            24: board.D24,
            4: board.D4,
            17: board.D17,
            27: board.D27,
            22: board.D22
        }
        
        if gpio_pin not in gpio_mapping:
            raise ValueError(f"GPIO {gpio_pin} non supporté. Utilisez: {list(gpio_mapping.keys())}")
        
        try:
            self.dht = adafruit_dht.DHT22(gpio_mapping[gpio_pin])
            print(f"✅ DHT22 initialisé sur GPIO{gpio_pin}")
        except Exception as e:
            print(f"❌ Erreur initialisation DHT22: {e}")
            self.dht = None
    
    def calculer_point_rosee(self, temp: float, hum: float) -> float:
        """Calcule le point de rosée (formule Magnus)"""
        try:
            a = 17.27
            b = 237.7
            alpha = ((a * temp) / (b + temp)) + math.log(hum / 100.0)
            point_rosee = (b * alpha) / (a - alpha)
            return round(point_rosee, 2)
        except:
            return 0.0
    
    def calculer_indice_chaleur(self, temp: float, hum: float) -> float:
        """Calcule l'indice de chaleur ressenti"""
        try:
            if temp < 27:
                return temp
            
            T = temp
            RH = hum
            
            HI = -8.78469475556 + \
                 1.61139411 * T + \
                 2.33854883889 * RH + \
                 -0.14611605 * T * RH + \
                 -0.012308094 * T * T + \
                 -0.0164248277778 * RH * RH + \
                 0.002211732 * T * T * RH + \
                 0.00072546 * T * RH * RH + \
                 -0.000003582 * T * T * RH * RH
            
            return round(HI, 2)
        except:
            return temp
    
    def lire_mesure(self) -> Optional[MesureEnvironnement]:
        """Lit une mesure du DHT22"""
        if not self.dht:
            return None
        
        try:
            temperature = self.dht.temperature
            humidite = self.dht.humidity
            
            if temperature is None or humidite is None:
                return None
            
            point_rosee = self.calculer_point_rosee(temperature, humidite)
            indice_chaleur = self.calculer_indice_chaleur(temperature, humidite)
            
            return MesureEnvironnement(
                timestamp=datetime.now().isoformat(),
                temperature_C=round(temperature, 2),
                humidity_pct=round(humidite, 2),
                point_rosee=point_rosee,
                indice_chaleur=indice_chaleur
            )
            
        except RuntimeError as e:
            # DHT22 est parfois bruyant, ignorer les erreurs occasionnelles
            return None
        except Exception as e:
            print(f"❌ Erreur lecture DHT22: {e}")
            return None
    
    def __del__(self):
        """Nettoyage"""
        if self.dht:
            try:
                self.dht.exit()
            except:
                pass


# ============================================================================
# CAPTEUR PZEM-004T
# ============================================================================

class PZEMSensor:
    """Gestion du capteur PZEM-004T (mesures électriques via ModBus RTU)"""
    
    def __init__(self, port: str = '/dev/ttyUSB0', slave_id: int = 1):
        """
        Initialise le PZEM-004T
        port: port série (USB/RS485)
        slave_id: adresse ModBus du PZEM (par défaut 1)
        """
        self.port = port
        self.slave_id = slave_id
        
        try:
            # Initialiser la connexion série
            self.ser = serial.Serial(
                port=port,
                baudrate=9600,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=1
            )
            
            # Créer le master ModBus RTU
            self.master = modbus_rtu.RtuMaster(self.ser)
            self.master.set_timeout(2.0)
            self.master.set_verbose(False)
            
            print(f"✅ PZEM-004T initialisé sur {port}")
            
        except Exception as e:
            print(f"❌ Erreur initialisation PZEM-004T: {e}")
            self.master = None
            self.ser = None
    
    def lire_mesure(self) -> Optional[MesureElectrique]:
        """Lit une mesure du PZEM-004T"""
        if not self.master:
            return None
        
        try:
            # Lire 10 registres à partir de l'adresse 0
            data = self.master.execute(self.slave_id, cst.READ_INPUT_REGISTERS, 0, 10)
            
            # Décoder les données selon le format PZEM-004T
            voltage = data[0] / 10.0
            current = (data[1] + (data[2] << 16)) / 1000.0
            power = (data[3] + (data[4] << 16)) / 10.0
            energy = data[5] + (data[6] << 16)  # En Wh
            frequency = data[7] / 10.0
            power_factor = data[8] / 100.0
            alarm = data[9]
            
            return MesureElectrique(
                timestamp=datetime.now().isoformat(),
                voltage_V=round(voltage, 2),
                current_A=round(current, 3),
                power_W=round(power, 2),
                energy_Wh=energy,
                frequency_Hz=round(frequency, 2),
                power_factor=round(power_factor, 2),
                alarm=alarm
            )
            
        except Exception as e:
            print(f"❌ Erreur lecture PZEM-004T: {e}")
            return None
    
    def __del__(self):
        """Fermeture de la connexion"""
        if self.master:
            try:
                self.master.close()
            except:
                pass


# ============================================================================
# SYSTÈME PRINCIPAL
# ============================================================================

class SystemeSurveillance:
    """Système principal de surveillance DHT22 + PZEM-004T"""
    
    def __init__(self, 
                 dht_gpio: int = 23,
                 pzem_port: str = '/dev/ttyUSB0',
                 db_path: str = "surveillance.db"):
        
        print("🔧 Initialisation du Système de Surveillance")
        print("=" * 70)
        
        # Composants
        self.db = DatabaseManager(db_path)
        self.dht22 = DHT22Sensor(gpio_pin=dht_gpio)
        self.pzem = PZEMSensor(port=pzem_port)
        
        # Configuration
        self.intervalle_mesure = 2  # secondes
        self.running = False
        
        # Dernières données pour l'interface web
        self.dernieres_mesures_env = deque(maxlen=100)
        self.dernieres_mesures_elec = deque(maxlen=100)
        self.lock = Lock()
        
        print("=" * 70)
        print("✅ Système initialisé avec succès\n")
    
    def cycle_mesure(self):
        """Exécute un cycle de mesure complet"""
        timestamp = datetime.now()
        
        # 1. Lire DHT22
        mesure_env = self.dht22.lire_mesure()
        if mesure_env:
            self.db.inserer_mesure_environnement(mesure_env)
            with self.lock:
                self.dernieres_mesures_env.append(asdict(mesure_env))
        
        # 2. Lire PZEM-004T
        mesure_elec = self.pzem.lire_mesure()
        if mesure_elec:
            self.db.inserer_mesure_electrique(mesure_elec)
            with self.lock:
                self.dernieres_mesures_elec.append(asdict(mesure_elec))
        
        # 3. Afficher dans le terminal
        self._afficher_terminal(mesure_env, mesure_elec)
    
    def _afficher_terminal(self, env: Optional[MesureEnvironnement], 
                          elec: Optional[MesureElectrique]):
        """Affiche les mesures dans le terminal"""
        heure = datetime.now().strftime('%H:%M:%S')
        
        print(f"\n{'=' * 70}")
        print(f"📊 [{heure}] MESURES EN TEMPS RÉEL")
        print(f"{'=' * 70}")
        
        # Environnement (DHT22)
        if env:
            print(f"\n🌡️  ENVIRONNEMENT (DHT22):")
            print(f"   ├─ Température      : {env.temperature_C:6.2f} °C")
            print(f"   ├─ Humidité         : {env.humidity_pct:6.2f} %")
            print(f"   ├─ Point de rosée   : {env.point_rosee:6.2f} °C")
            print(f"   └─ Indice chaleur   : {env.indice_chaleur:6.2f} °C")
        else:
            print(f"\n🌡️  ENVIRONNEMENT (DHT22): ❌ Erreur de lecture")
        
        # Électrique (PZEM-004T)
        if elec:
            print(f"\n⚡ ÉLECTRIQUE (PZEM-004T):")
            print(f"   ├─ Tension          : {elec.voltage_V:6.2f} V")
            print(f"   ├─ Courant          : {elec.current_A:6.3f} A")
            print(f"   ├─ Puissance        : {elec.power_W:6.2f} W")
            print(f"   ├─ Énergie          : {elec.energy_Wh:6.0f} Wh")
            print(f"   ├─ Fréquence        : {elec.frequency_Hz:6.2f} Hz")
            print(f"   ├─ Facteur puissance: {elec.power_factor:6.2f}")
            print(f"   └─ Alarme           : {elec.alarm}")
        else:
            print(f"\n⚡ ÉLECTRIQUE (PZEM-004T): ❌ Erreur de lecture")
        
        print(f"{'=' * 70}")
    
    def boucle_surveillance(self):
        """Boucle principale de surveillance"""
        print("\n🔍 Démarrage de la surveillance...")
        print("   Appuyez sur Ctrl+C pour arrêter\n")
        
        self.running = True
        
        try:
            while self.running:
                self.cycle_mesure()
                time.sleep(self.intervalle_mesure)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Arrêt demandé...")
        finally:
            self.arreter()
    
    def arreter(self):
        """Arrête proprement le système"""
        self.running = False
        print("✅ Système arrêté proprement")
    
    def obtenir_donnees_dashboard(self) -> Dict:
        """Retourne les données pour le dashboard web"""
        with self.lock:
            return {
                'mesures_environnement': list(self.dernieres_mesures_env),
                'mesures_electriques': list(self.dernieres_mesures_elec),
                'statistiques': self.db.obtenir_statistiques(heures=24),
                'timestamp': datetime.now().isoformat()
            }


# ============================================================================
# SERVEUR WEB
# ============================================================================

app = Flask(__name__)
systeme = None

# Chemin du fichier HTML
HTML_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def index():
    """Page principale"""
    return send_from_directory(HTML_DIR, 'dashboard.html')

@app.route('/api/donnees')
def api_donnees():
    """API: Données en temps réel"""
    if systeme:
        return jsonify(systeme.obtenir_donnees_dashboard())
    return jsonify({'error': 'Système non initialisé'}), 503

@app.route('/api/statistiques')
def api_statistiques():
    """API: Statistiques"""
    if systeme:
        return jsonify({
            'stats_24h': systeme.db.obtenir_statistiques(heures=24),
            'stats_7j': systeme.db.obtenir_statistiques(heures=24*7)
        })
    return jsonify({'error': 'Système non initialisé'}), 503


def demarrer_serveur_web(port=5000):
    """Démarre le serveur web Flask"""
    print(f"\n🌐 Serveur web démarré sur http://0.0.0.0:{port}")
    print(f"   Accédez au dashboard: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)


# ============================================================================
# POINT D'ENTRÉE PRINCIPAL
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print(" 🚀 SYSTÈME DE SURVEILLANCE DHT22 + PZEM-004T")
    print("="*70 + "\n")
    
    # Configuration
    DHT_GPIO_PIN = 23             # GPIO23 (BCM) = pin physique 16
    PZEM_PORT = '/dev/ttyUSB0'    # Port série du PZEM-004T
    WEB_PORT = 5000                # Port du serveur web
    
    # Créer le système
    systeme = SystemeSurveillance(
        dht_gpio=DHT_GPIO_PIN,
        pzem_port=PZEM_PORT
    )
    
    # Démarrer le serveur web dans un thread séparé
    thread_web = Thread(target=demarrer_serveur_web, args=(WEB_PORT,), daemon=True)
    thread_web.start()
    
    # Laisser le temps au serveur de démarrer
    time.sleep(2)
    
    # Lancer la surveillance
    systeme.boucle_surveillance()
