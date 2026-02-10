# 🚀 QUICK START - DUAL STORAGE SYSTEM

## 📊 Comparaison: Ancien vs Nouveau système

| Fonctionnalité | Ancien (SQLite seul) | Nouveau (Dual Storage) |
|----------------|---------------------|------------------------|
| **Stockage local** | ✅ SQLite | ✅ SQLite (backup) |
| **Stockage time-series** | ❌ | ✅ InfluxDB |
| **Dashboard Grafana** | ⚠️ Difficile | ✅ Optimisé |
| **Performance dashboards** | ⚠️ Lente | ✅ Rapide |
| **Requêtes complexes** | ⚠️ Limitée | ✅ Puissante |
| **Rétention données** | ✅ Permanente | ✅ Configurable |
| **Robustesse** | ✅ Bonne | ✅ Excellente |
| **Grafana alertes** | ⚠️ Limitée | ✅ Native |

## 🎯 Avantages du Dual Storage

### ✅ Pourquoi c'est MIEUX:

1. **Redondance**: Si InfluxDB tombe, SQLite continue
2. **Performance**: InfluxDB est 10-100x plus rapide pour les time-series
3. **Grafana natif**: Intégration parfaite, pas de plugin tiers
4. **Requêtes avancées**: Agrégations, dérivées, downsampling
5. **Rétention configuré**: Garder 7 jours dans InfluxDB, tout dans SQLite
6. **Alertes**: Grafana peut déclencher des alertes nativement
7. **Scalabilité**: Facile d'ajouter d'autres visualisations

### 📈 Performance

```
Requête: Moyenne température sur 24h avec 43,200 points

SQLite:   ~2.5 secondes
InfluxDB: ~0.05 secondes (50x plus rapide!)
```

## ⚡ INSTALLATION EN 5 MINUTES

### Étape 1: Installer InfluxDB (2 min)

```bash
wget https://dl.influxdata.com/influxdb/releases/influxdb_1.8.10_armhf.deb
sudo dpkg -i influxdb_1.8.10_armhf.deb
sudo systemctl start influxdb
influx -execute 'CREATE DATABASE surveillance'
```

### Étape 2: Installer dépendances Python (30 sec)

```bash
pip3 install influxdb
```

### Étape 3: Installer Grafana (2 min)

```bash
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt-get update && sudo apt-get install -y grafana
sudo systemctl start grafana-server
```

### Étape 4: Lancer le nouveau script (10 sec)

```bash
python3 surveillance_dual_storage.py
```

### Étape 5: Configurer Grafana (30 sec)

1. Ouvrir `http://localhost:3000`
2. Login: `admin` / `admin`
3. Configuration → Data Sources → Add → InfluxDB
4. URL: `http://localhost:8086`, Database: `surveillance`
5. Import le dashboard: Upload `grafana_dashboard.json`

**TOTAL: ~5 minutes! 🎉**

## 🔍 Vérification rapide

### Test InfluxDB

```bash
# Vérifier que les données arrivent
influx -database surveillance -execute 'SELECT COUNT(*) FROM environnement'
influx -database surveillance -execute 'SELECT * FROM electrique LIMIT 3'
```

**Résultat attendu:**
```
name: environnement
time                count_temperature_C
----                -------------------
1970-01-01T00:00:00Z 150

name: electrique
time                 voltage_V current_A power_W
----                 --------- --------- -------
2026-02-10T14:30:00Z 230.5     1.234     284.5
2026-02-10T14:30:02Z 230.6     1.235     285.0
2026-02-10T14:30:04Z 230.4     1.236     284.8
```

### Test Grafana

1. Ouvrir le dashboard
2. Vous devriez voir des graphiques en temps réel
3. Les données se mettent à jour toutes les 10 secondes

## 📁 Structure des fichiers

```
~/surveillance/
├── surveillance_dual_storage.py    # Nouveau script (UTILISER CELUI-CI)
├── surveillance.db                  # Base SQLite (backup)
├── dashboard.html                   # Interface web Flask
├── grafana_dashboard.json          # Dashboard Grafana pré-configuré
├── INSTALLATION_GUIDE.md           # Guide complet
└── QUICK_START.md                  # Ce fichier
```

## 🎨 Dashboard Grafana - Aperçu

Le dashboard inclut:

### Section Environnement (DHT22)
- 🌡️ Température (time series avec seuils)
- 💧 Humidité (time series avec seuils)
- 💦 Point de rosée
- 📊 Valeurs actuelles (stat cards)

### Section Électrique (PZEM-004T)
- ⚡ Tension avec seuils (220V ± 10%)
- 🔌 Courant en temps réel
- 💡 Puissance active
- ⚡ Énergie totale accumulée
- 📊 Fréquence avec gauge (50Hz ± 0.5Hz)
- ⚙️ Facteur de puissance avec gauge
- 📈 Consommation horaire (bars)

### Fonctionnalités
- ✅ Auto-refresh: 10 secondes
- ✅ Time range: Dernières 6 heures
- ✅ Thresholds colorés (vert/jaune/rouge)
- ✅ Tooltips interactifs
- ✅ Zoom et pan sur les graphiques
- ✅ Export des données

## 🔧 Configuration personnalisée

### Changer l'intervalle de mesure

Dans `surveillance_dual_storage.py`:
```python
self.intervalle_mesure = 5  # Changer de 2 à 5 secondes
```

### Configurer la rétention InfluxDB

```bash
influx
USE surveillance
CREATE RETENTION POLICY "30_days" ON "surveillance" DURATION 30d REPLICATION 1 DEFAULT
```

Cela garde les données 30 jours dans InfluxDB (SQLite garde tout).

### Ajouter des alertes Grafana

1. Ouvrir un panel
2. Cliquer sur **Alert**
3. **Create alert rule**
4. Exemple: Température > 35°C
   ```
   WHEN avg() OF query(A, 5m, now) IS ABOVE 35
   THEN send notification to "Email" OR "Telegram"
   ```

## 📊 Requêtes utiles InfluxDB

### Moyenne horaire

```sql
SELECT mean("temperature_C") 
FROM "environnement" 
WHERE time > now() - 24h 
GROUP BY time(1h)
```

### Consommation électrique par heure

```sql
SELECT derivative(mean("energy_Wh"), 1h) 
FROM "electrique" 
WHERE time > now() - 24h 
GROUP BY time(1h)
```

### Puissance maximale

```sql
SELECT max("power_W") 
FROM "electrique" 
WHERE time > now() - 7d 
GROUP BY time(1d)
```

## 🎯 Prochaines étapes recommandées

### 1. Backup automatique (recommandé)

```bash
# Créer un script de backup
cat > ~/backup_surveillance.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
# Backup SQLite
cp ~/surveillance/surveillance.db ~/backups/surveillance_$DATE.db
# Backup InfluxDB
influx_inspect export -database surveillance -out ~/backups/influx_$DATE.txt
# Nettoyer les vieux backups (>30 jours)
find ~/backups -name "*.db" -mtime +30 -delete
EOF

chmod +x ~/backup_surveillance.sh

# Ajouter au crontab (tous les jours à 3h du matin)
crontab -e
# Ajouter: 0 3 * * * /home/pi/backup_surveillance.sh
```

### 2. Service systemd (démarrage automatique)

```bash
# Créer le service
sudo nano /etc/systemd/system/surveillance.service
```

Contenu:
```ini
[Unit]
Description=Surveillance DHT22 + PZEM-004T
After=network.target influxdb.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/surveillance
ExecStart=/usr/bin/python3 /home/pi/surveillance/surveillance_dual_storage.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activer:
```bash
sudo systemctl daemon-reload
sudo systemctl enable surveillance.service
sudo systemctl start surveillance.service
sudo systemctl status surveillance.service
```

### 3. Accès distant (optionnel)

```bash
# Ouvrir Grafana sur le réseau local
sudo ufw allow 3000/tcp

# Configurer un nom de domaine local avec mDNS
sudo apt-get install avahi-daemon
# Accès via: http://raspberrypi.local:3000
```

### 4. Notifications Telegram/Discord (avancé)

Grafana supporte nativement:
- Email
- Telegram
- Discord
- Slack
- Webhooks

Configuration dans Grafana → Alerting → Contact points

## 🐛 Troubleshooting rapide

| Problème | Solution |
|----------|----------|
| "InfluxDB non disponible" | `sudo systemctl restart influxdb` |
| Grafana "No data" | Vérifier time range (Last 24h) |
| Script Python crash | Vérifier GPIO et USB connections |
| Dashboard vide | Attendre 1-2 minutes pour les données |
| Erreur permission | `sudo chmod 666 /dev/ttyUSB0` |

## ✅ Checklist de vérification

- [ ] InfluxDB fonctionne: `sudo systemctl status influxdb`
- [ ] Grafana fonctionne: `sudo systemctl status grafana-server`
- [ ] Script Python lit DHT22: Voir température dans terminal
- [ ] Script Python lit PZEM: Voir voltage dans terminal
- [ ] Données dans InfluxDB: `influx -execute 'SELECT COUNT(*) FROM surveillance.autogen.environnement'`
- [ ] Dashboard Grafana affiche les données
- [ ] Auto-refresh activé (horloge en haut à droite)
- [ ] Stats de stockage OK: SQLite ✅ et InfluxDB ✅ dans terminal

## 🎉 C'est terminé!

Vous avez maintenant un système professionnel de monitoring IoT avec:
- ✅ Dual storage robuste
- ✅ Dashboard Grafana en temps réel
- ✅ Backup automatique
- ✅ Haute performance
- ✅ Extensible et maintenable

**Profitez de votre nouveau système!** 🚀
