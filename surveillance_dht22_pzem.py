"""
Système de Surveillance DHT22 + PZEM-004T
Version: 1.0 - Raspberry Pi 4
Affichage Terminal + Serveur Web + Base de données SQLite
"""

import sqlite3
import time
import json
from datetime import datetime, timedelta
from threading import Thread, Lock
from flask import Flask, jsonify, send_from_directory
import os
from collections import deque
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import math

# Import pour DHT22 sur Raspberry Pi 4
try:
    import board
    import adafruit_dht
    DHT_DISPONIBLE = True
    print("✅ Bibliothèque adafruit-circuitpython-dht chargée")
except ImportError:
    print("⚠️  adafruit-circuitpython-dht non installé - Mode simulation DHT22")
    DHT_DISPONIBLE = False

# Import pour PZEM-004T (communication ModBus RTU via USB/RS485)
try:
    from pymodbus.client import ModbusSerialClient
    PZEM_DISPONIBLE = True
    print("✅ Bibliothèque pymodbus chargée")
except ImportError:
    print("⚠️  pymodbus non installé - Mode simulation PZEM-004T")
    PZEM_DISPONIBLE = False


# ============================================================================
# MODÈLE DE DONNÉES
# ============================================================================

@dataclass
class MesureEnvironnement:
    """Mesure DHT22: température et humidité"""
    timestamp: str
    temperature: float
    humidite: float
    point_rosee: float
    indice_chaleur: float


@dataclass
class MesureElectrique:
    """Mesure PZEM-004T: paramètres électriques"""
    timestamp: str
    tension: float          # Volts
    courant: float          # Ampères
    puissance: float        # Watts
    energie: float          # kWh
    frequence: float        # Hz
    facteur_puissance: float  # 0-1


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
                    temperature REAL,
                    humidite REAL,
                    point_rosee REAL,
                    indice_chaleur REAL
                )
            """)
            
            # Table des mesures électriques (PZEM-004T)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mesures_electriques (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    tension REAL,
                    courant REAL,
                    puissance REAL,
                    energie REAL,
                    frequence REAL,
                    facteur_puissance REAL
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
                    (timestamp, temperature, humidite, point_rosee, indice_chaleur)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    mesure.timestamp,
                    mesure.temperature,
                    mesure.humidite,
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
                    (timestamp, tension, courant, puissance, energie, frequence, facteur_puissance)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    mesure.timestamp,
                    mesure.tension,
                    mesure.courant,
                    mesure.puissance,
                    mesure.energie,
                    mesure.frequence,
                    mesure.facteur_puissance
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
                    AVG(temperature) as temp_moy,
                    MIN(temperature) as temp_min,
                    MAX(temperature) as temp_max,
                    AVG(humidite) as hum_moy,
                    MIN(humidite) as hum_min,
                    MAX(humidite) as hum_max
                FROM mesures_environnement 
                WHERE timestamp > ?
            """, (temps_limite,))
            columns_env = [desc[0] for desc in cursor.description]
            stats_env = dict(zip(columns_env, cursor.fetchone() or []))
            
            # Stats électriques
            cursor.execute("""
                SELECT 
                    COUNT(*) as nb_mesures,
                    AVG(tension) as tension_moy,
                    AVG(courant) as courant_moy,
                    AVG(puissance) as puissance_moy,
                    MAX(puissance) as puissance_max,
                    SUM(energie) as energie_totale,
                    AVG(frequence) as freq_moy,
                    AVG(facteur_puissance) as fp_moy
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
    """Gestion du capteur DHT22"""
    
    def __init__(self, gpio_pin: int = 4):
        self.gpio_pin = gpio_pin
        self.dht_device = None
        self.mode_simulation = not DHT_DISPONIBLE
        
        if DHT_DISPONIBLE:
            try:
                self.dht_device = adafruit_dht.DHT22(getattr(board, f'D{gpio_pin}'))
                print(f"✅ DHT22 initialisé sur GPIO{gpio_pin}")
            except Exception as e:
                print(f"⚠️  Erreur initialisation DHT22: {e}")
                self.mode_simulation = True
        
        if self.mode_simulation:
            print("⚠️  Mode simulation DHT22 activé")
            self.sim_temp = 22.0
            self.sim_hum = 50.0
    
    @staticmethod
    def _calculer_point_rosee(temp: float, hum: float) -> float:
        """Calcule le point de rosée"""
        a, b = 17.27, 237.7
        alpha = ((a * temp) / (b + temp)) + math.log(hum / 100.0)
        return (b * alpha) / (a - alpha)
    
    @staticmethod
    def _calculer_indice_chaleur(temp: float, hum: float) -> float:
        """Calcule l'indice de chaleur (ressenti)"""
        if temp < 27:
            return temp
        
        T, H = temp, hum
        ic = (-8.78469475556 + 1.61139411*T + 2.33854883889*H 
              - 0.14611605*T*H - 0.012308094*T*T 
              - 0.0164248277778*H*H + 0.002211732*T*T*H 
              + 0.00072546*T*H*H - 0.000003582*T*T*H*H)
        return ic
    
    def lire_mesure(self) -> Optional[MesureEnvironnement]:
        """Lit une mesure du DHT22"""
        try:
            if self.mode_simulation:
                # Simulation
                import random
                self.sim_temp += random.uniform(-0.5, 0.5)
                self.sim_hum += random.uniform(-2, 2)
                self.sim_temp = max(-10, min(50, self.sim_temp))
                self.sim_hum = max(0, min(100, self.sim_hum))
                temp, hum = self.sim_temp, self.sim_hum
            else:
                # Lecture réelle
                temp = self.dht_device.temperature
                hum = self.dht_device.humidity
                
                if temp is None or hum is None:
                    return None
            
            # Calculs dérivés
            point_rosee = self._calculer_point_rosee(temp, hum)
            indice_chaleur = self._calculer_indice_chaleur(temp, hum)
            
            return MesureEnvironnement(
                timestamp=datetime.now().isoformat(),
                temperature=round(temp, 2),
                humidite=round(hum, 2),
                point_rosee=round(point_rosee, 2),
                indice_chaleur=round(indice_chaleur, 2)
            )
            
        except Exception as e:
            print(f"❌ Erreur lecture DHT22: {e}")
            return None


# ============================================================================
# CAPTEUR PZEM-004T
# ============================================================================

class PZEMSensor:
    """Gestion du capteur PZEM-004T via ModBus RTU"""
    
    def __init__(self, port: str = '/dev/ttyUSB0', slave_id: int = 1):
        self.port = port
        self.slave_id = slave_id
        self.client = None
        self.mode_simulation = not PZEM_DISPONIBLE
        
        if PZEM_DISPONIBLE:
            try:
                self.client = ModbusSerialClient(
                    port=port,
                    baudrate=9600,
                    bytesize=8,
                    parity='N',
                    stopbits=1,
                    timeout=1
                )
                if self.client.connect():
                    print(f"✅ PZEM-004T initialisé sur {port}")
                else:
                    print(f"⚠️  Impossible de se connecter au PZEM-004T sur {port}")
                    self.mode_simulation = True
            except Exception as e:
                print(f"⚠️  Erreur initialisation PZEM-004T: {e}")
                self.mode_simulation = True
        
        if self.mode_simulation:
            print("⚠️  Mode simulation PZEM-004T activé")
            self.sim_tension = 230.0
            self.sim_courant = 1.5
            self.sim_energie = 0.0
    
    def lire_mesure(self) -> Optional[MesureElectrique]:
        """Lit une mesure du PZEM-004T"""
        try:
            if self.mode_simulation:
                # Simulation
                import random
                self.sim_tension += random.uniform(-2, 2)
                self.sim_courant += random.uniform(-0.1, 0.1)
                self.sim_tension = max(200, min(250, self.sim_tension))
                self.sim_courant = max(0, min(10, self.sim_courant))
                
                tension = self.sim_tension
                courant = self.sim_courant
                puissance = tension * courant
                self.sim_energie += puissance / 3600000  # Conversion W -> kWh
                energie = self.sim_energie
                frequence = 50.0 + random.uniform(-0.5, 0.5)
                facteur_puissance = 0.95 + random.uniform(-0.05, 0.05)
                
            else:
                # Lecture réelle via ModBus
                # Registres PZEM-004T:
                # 0x0000: Tension (V) - 1 registre / 10
                # 0x0001: Courant (A) - 2 registres / 1000
                # 0x0003: Puissance (W) - 2 registres / 10
                # 0x0005: Énergie (kWh) - 2 registres / 1000
                # 0x0007: Fréquence (Hz) - 1 registre / 10
                # 0x0008: Facteur de puissance - 1 registre / 100
                
                result = self.client.read_input_registers(0x0000, 10, slave=self.slave_id)
                
                if result.isError():
                    return None
                
                regs = result.registers
                tension = regs[0] / 10.0
                courant = ((regs[1] << 16) | regs[2]) / 1000.0
                puissance = ((regs[3] << 16) | regs[4]) / 10.0
                energie = ((regs[5] << 16) | regs[6]) / 1000.0
                frequence = regs[7] / 10.0
                facteur_puissance = regs[8] / 100.0
            
            return MesureElectrique(
                timestamp=datetime.now().isoformat(),
                tension=round(tension, 2),
                courant=round(courant, 3),
                puissance=round(puissance, 2),
                energie=round(energie, 3),
                frequence=round(frequence, 2),
                facteur_puissance=round(facteur_puissance, 2)
            )
            
        except Exception as e:
            print(f"❌ Erreur lecture PZEM-004T: {e}")
            return None
    
    def __del__(self):
        """Fermeture de la connexion"""
        if self.client and not self.mode_simulation:
            try:
                self.client.close()
            except:
                pass


# ============================================================================
# SYSTÈME PRINCIPAL
# ============================================================================

class SystemeSurveillance:
    """Système principal de surveillance DHT22 + PZEM-004T"""
    
    def __init__(self, 
                 dht_gpio: int = 4,
                 pzem_port: str = '/dev/ttyUSB0',
                 db_path: str = "surveillance.db"):
        
        print("🔧 Initialisation du Système de Surveillance")
        print("=" * 70)
        
        # Composants
        self.db = DatabaseManager(db_path)
        self.dht22 = DHT22Sensor(gpio_pin=dht_gpio)
        self.pzem = PZEMSensor(port=pzem_port)
        
        # Configuration
        self.intervalle_mesure = 3  # secondes
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
            print(f"   ├─ Température      : {env.temperature:6.2f} °C")
            print(f"   ├─ Humidité         : {env.humidite:6.2f} %")
            print(f"   ├─ Point de rosée   : {env.point_rosee:6.2f} °C")
            print(f"   └─ Indice chaleur   : {env.indice_chaleur:6.2f} °C")
        else:
            print(f"\n🌡️  ENVIRONNEMENT (DHT22): ❌ Erreur de lecture")
        
        # Électrique (PZEM-004T)
        if elec:
            print(f"\n⚡ ÉLECTRIQUE (PZEM-004T):")
            print(f"   ├─ Tension          : {elec.tension:6.2f} V")
            print(f"   ├─ Courant          : {elec.courant:6.3f} A")
            print(f"   ├─ Puissance        : {elec.puissance:6.2f} W")
            print(f"   ├─ Énergie          : {elec.energie:6.3f} kWh")
            print(f"   ├─ Fréquence        : {elec.frequence:6.2f} Hz")
            print(f"   └─ Facteur puissance: {elec.facteur_puissance:6.2f}")
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
    DHT_GPIO_PIN = 4              # GPIO4 (pin 7)
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
