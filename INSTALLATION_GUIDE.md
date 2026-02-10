# GUIDE D'INSTALLATION COMPLET - DUAL STORAGE + GRAFANA

## 📋 ÉTAPE 1: Installation d'InfluxDB

### 1.1 Installer InfluxDB sur Raspberry Pi

```bash
# Télécharger InfluxDB pour ARM (Raspberry Pi)
cd ~/Downloads
wget https://dl.influxdata.com/influxdb/releases/influxdb_1.8.10_armhf.deb

# Installer
sudo dpkg -i influxdb_1.8.10_armhf.deb

# Démarrer et activer au démarrage
sudo systemctl start influxdb
sudo systemctl enable influxdb

# Vérifier le statut
sudo systemctl status influxdb
```

### 1.2 Créer la base de données

```bash
# Accéder à l'interface CLI d'InfluxDB
influx

# Dans l'interface InfluxDB:
CREATE DATABASE surveillance
SHOW DATABASES
exit
```

## 📋 ÉTAPE 2: Installation des dépendances Python

```bash
# Installer le client InfluxDB Python
pip3 install influxdb

# Vérifier l'installation
python3 -c "from influxdb import InfluxDBClient; print('InfluxDB client OK')"
```

## 📋 ÉTAPE 3: Installation de Grafana

### 3.1 Installer Grafana

```bash
# Ajouter la clé GPG et le repository
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list

# Mettre à jour et installer
sudo apt-get update
sudo apt-get install -y grafana

# Démarrer et activer au démarrage
sudo systemctl start grafana-server
sudo systemctl enable grafana-server

# Vérifier le statut
sudo systemctl status grafana-server
```

### 3.2 Accéder à Grafana

1. Ouvrir le navigateur: `http://localhost:3000` ou `http://IP_DU_RPI:3000`
2. Login par défaut:
   - Username: `admin`
   - Password: `admin`
3. Changer le mot de passe à la première connexion

## 📋 ÉTAPE 4: Configurer InfluxDB dans Grafana

### 4.1 Ajouter la source de données

1. Dans Grafana, cliquer sur **Configuration** (⚙️) → **Data Sources**
2. Cliquer sur **Add data source**
3. Sélectionner **InfluxDB**
4. Configurer:
   - **Name**: `InfluxDB-Surveillance`
   - **Query Language**: `InfluxQL`
   - **URL**: `http://localhost:8086`
   - **Database**: `surveillance`
   - **User**: (laisser vide si pas de sécurité)
   - **Password**: (laisser vide si pas de sécurité)
5. Cliquer sur **Save & Test** → Vous devriez voir "Data source is working"

## 📋 ÉTAPE 5: Lancer le script Python

```bash
# Copier le nouveau script
cp surveillance_dual_storage.py ~/surveillance/

# Lancer le script
cd ~/surveillance/
python3 surveillance_dual_storage.py
```

**Vous devriez voir:**
```
✅ Base de données SQLite initialisée: surveillance.db
✅ Tables SQLite créées avec succès
✅ InfluxDB connecté: localhost:8086/surveillance
✅ DHT22 initialisé sur GPIO23
✅ PZEM-004T initialisé sur /dev/ttyUSB0
✅ Système DUAL STORAGE initialisé avec succès
   → SQLite: ACTIF
   → InfluxDB: ACTIF
```

## 📋 ÉTAPE 6: Créer les dashboards Grafana

### 6.1 Dashboard Environnement (DHT22)

#### Panel 1: Température en temps réel

1. Créer un nouveau dashboard: **Create** → **Dashboard** → **Add new panel**
2. Dans **Query**:
   ```
   FROM: environnement
   SELECT: field(temperature_C)
   GROUP BY: time($__interval)
   ```
3. **Visualization**: Time series
4. **Panel options**:
   - Title: `🌡️ Température`
   - Unit: `Celsius (°C)`
5. **Save**

#### Panel 2: Humidité en temps réel

1. **Add panel**
2. Dans **Query**:
   ```
   FROM: environnement
   SELECT: field(humidity_pct)
   GROUP BY: time($__interval)
   ```
3. **Visualization**: Time series
4. **Panel options**:
   - Title: `💧 Humidité`
   - Unit: `Percent (0-100)`
5. **Save**

#### Panel 3: Point de rosée

1. **Add panel**
2. Dans **Query**:
   ```
   FROM: environnement
   SELECT: field(point_rosee)
   GROUP BY: time($__interval)
   ```
3. **Visualization**: Time series
4. **Panel options**:
   - Title: `💦 Point de rosée`
   - Unit: `Celsius (°C)`
5. **Save**

#### Panel 4: Valeurs actuelles (Gauges)

1. **Add panel**
2. Dans **Query A**:
   ```
   FROM: environnement
   SELECT: field(temperature_C)
   ```
3. Ajouter **Query B**:
   ```
   FROM: environnement
   SELECT: field(humidity_pct)
   ```
4. **Visualization**: Stat ou Gauge
5. **Panel options**:
   - Title: `📊 Valeurs actuelles`
6. **Save**

### 6.2 Dashboard Électrique (PZEM-004T)

#### Panel 1: Tension (Voltage)

1. **Add panel**
2. Dans **Query**:
   ```
   FROM: electrique
   SELECT: field(voltage_V)
   GROUP BY: time($__interval)
   ```
3. **Visualization**: Time series
4. **Panel options**:
   - Title: `⚡ Tension`
   - Unit: `Volt`
5. **Thresholds**:
   - Vert: 220-240V
   - Jaune: 210-220V ou 240-250V
   - Rouge: <210V ou >250V
6. **Save**

#### Panel 2: Courant (Current)

1. **Add panel**
2. Dans **Query**:
   ```
   FROM: electrique
   SELECT: field(current_A)
   GROUP BY: time($__interval)
   ```
3. **Visualization**: Time series
4. **Panel options**:
   - Title: `🔌 Courant`
   - Unit: `Ampere`
5. **Save**

#### Panel 3: Puissance (Power)

1. **Add panel**
2. Dans **Query**:
   ```
   FROM: electrique
   SELECT: field(power_W)
   GROUP BY: time($__interval)
   ```
3. **Visualization**: Time series
4. **Panel options**:
   - Title: `💡 Puissance`
   - Unit: `Watt`
5. **Save**

#### Panel 4: Énergie consommée (Energy)

1. **Add panel**
2. Dans **Query**:
   ```
   FROM: electrique
   SELECT: field(energy_Wh)
   GROUP BY: time($__interval)
   ```
3. **Visualization**: Stat
4. **Panel options**:
   - Title: `⚡ Énergie totale`
   - Unit: `Watt-hour`
5. **Calculation**: Last (pour voir la valeur totale)
6. **Save**

#### Panel 5: Fréquence

1. **Add panel**
2. Dans **Query**:
   ```
   FROM: electrique
   SELECT: field(frequency_Hz)
   GROUP BY: time($__interval)
   ```
3. **Visualization**: Time series
4. **Panel options**:
   - Title: `📊 Fréquence`
   - Unit: `Hertz`
5. **Thresholds**:
   - Vert: 49.5-50.5Hz
   - Jaune: 49-49.5Hz ou 50.5-51Hz
   - Rouge: <49Hz ou >51Hz
6. **Save**

#### Panel 6: Facteur de puissance

1. **Add panel**
2. Dans **Query**:
   ```
   FROM: electrique
   SELECT: field(power_factor)
   GROUP BY: time($__interval)
   ```
3. **Visualization**: Gauge
4. **Panel options**:
   - Title: `⚙️ Facteur de puissance`
   - Unit: `None`
   - Min: 0
   - Max: 1
5. **Thresholds**:
   - Vert: >0.9
   - Jaune: 0.7-0.9
   - Rouge: <0.7
6. **Save**

## 📋 ÉTAPE 7: Configuration avancée

### 7.1 Auto-refresh du dashboard

1. En haut à droite du dashboard, cliquer sur l'horloge
2. Sélectionner **Auto refresh**: `5s` ou `10s`
3. **Time range**: `Last 1 hour` ou `Last 6 hours`

### 7.2 Variables de dashboard (optionnel)

Pour filtrer par période:
1. **Dashboard settings** → **Variables**
2. **Add variable**:
   - Name: `interval`
   - Type: `Interval`
   - Values: `1s,5s,10s,30s,1m,5m`

### 7.3 Alertes (optionnel)

Exemple d'alerte pour température haute:

1. Dans le panel de température, cliquer sur **Alert**
2. **Create alert rule**
3. **Conditions**:
   ```
   WHEN avg() OF query(A, 5m, now) IS ABOVE 35
   ```
4. **Notifications**: Configurer email/Slack/Discord

## 📋 ÉTAPE 8: Vérification du système

### 8.1 Tester InfluxDB

```bash
# Se connecter à InfluxDB
influx

# Sélectionner la base
USE surveillance

# Voir les measurements
SHOW MEASUREMENTS

# Voir quelques données
SELECT * FROM environnement LIMIT 5
SELECT * FROM electrique LIMIT 5

# Compter les enregistrements
SELECT COUNT(*) FROM environnement
SELECT COUNT(*) FROM electrique

# Sortir
exit
```

### 8.2 Vérifier les logs

```bash
# Logs du script Python
# (s'il y a des erreurs, elles s'afficheront dans le terminal)

# Logs InfluxDB
sudo journalctl -u influxdb -f

# Logs Grafana
sudo journalctl -u grafana-server -f
```

## 🔧 TROUBLESHOOTING

### Problème: InfluxDB non accessible

```bash
# Vérifier le service
sudo systemctl status influxdb

# Redémarrer
sudo systemctl restart influxdb

# Vérifier le port
netstat -tulpn | grep 8086
```

### Problème: Grafana affiche "No data"

1. Vérifier que des données existent dans InfluxDB
2. Vérifier la configuration de la source de données
3. Vérifier la requête dans le panel
4. Vérifier le time range (augmenter à "Last 24 hours")

### Problème: Le script Python ne se connecte pas à InfluxDB

```bash
# Tester manuellement
python3 << EOF
from influxdb import InfluxDBClient
client = InfluxDBClient('localhost', 8086)
print(client.get_list_database())
EOF
```

## 📊 REQUÊTES UTILES POUR GRAFANA

### Requête agrégée (moyenne par minute)

```
SELECT mean("temperature_C") FROM "environnement" 
WHERE $timeFilter 
GROUP BY time(1m) fill(linear)
```

### Requête avec plusieurs champs

```
SELECT mean("voltage_V") AS "Tension",
       mean("current_A") AS "Courant",
       mean("power_W") AS "Puissance"
FROM "electrique"
WHERE $timeFilter
GROUP BY time($__interval) fill(linear)
```

### Requête de dérivée (pour calculer la consommation)

```
SELECT derivative(mean("energy_Wh"), 1h) AS "Consommation par heure"
FROM "electrique"
WHERE $timeFilter
GROUP BY time(1h) fill(linear)
```

## 🎯 RÉSULTAT FINAL

Vous aurez:

✅ **Stockage dual**:
   - SQLite: Backup local permanent
   - InfluxDB: Optimisé pour Grafana

✅ **Dashboard Grafana** avec:
   - Température en temps réel
   - Humidité
   - Tension / Courant / Puissance
   - Consommation électrique
   - Graphiques historiques
   - Alertes (optionnel)

✅ **Système robuste**:
   - Si InfluxDB tombe, SQLite continue
   - Statistiques de stockage visibles
   - Auto-recovery

## 📝 COMMANDES UTILES

```bash
# Démarrer le système
python3 surveillance_dual_storage.py

# Voir les données InfluxDB
influx -database surveillance -execute 'SELECT * FROM environnement LIMIT 10'

# Backup SQLite
cp surveillance.db surveillance_backup_$(date +%Y%m%d).db

# Exporter données InfluxDB
influx_inspect export -database surveillance -out backup.txt

# Monitoring en temps réel
watch -n 1 'influx -database surveillance -execute "SELECT LAST(*) FROM environnement"'
```
