# ProxyTunnelAppLauncher

Lance n'importe quelle application via un tunnel SOCKS5, pour les logiciels qui ne disposent pas d'option proxy native (RDP, SSH, VNC, etc.).

## Principe

Chaque commande est configurée avec :
- une **cible** (IP distante + port)
- un **proxy SOCKS5** (profil nommé réutilisable)
- une **commande** à exécuter, avec les placeholders `{bind_ip}` et `{bind_port}`

Au lancement d'une commande, l'application :
1. Alloue automatiquement un **port local aléatoire** dans la plage configurée
2. Crée un **tunnel TCP** : `127.0.0.1:<port_auto>` → `cible_distante` via le proxy SOCKS5
3. Résout les placeholders et **exécute la commande**
4. **Détruit le tunnel** automatiquement quand le processus se termine

**Exemple RDP :**
```
Cible    : 192.168.0.201 : 3389
Proxy    : Mon-Bastion-SSH (127.0.0.1:2222)
Commande : mstsc /v:{bind_ip}:{bind_port}

→ Tunnel créé  : 127.0.0.1:24731 → 192.168.0.201:3389 via 127.0.0.1:2222
→ Commande lancée : mstsc /v:127.0.0.1:24731
```

**Exemple SSH (mode console) :**
```
Cible    : 10.0.0.5 : 22
Proxy    : Mon-Bastion-SSH (127.0.0.1:2222)
Commande : ssh user@{bind_ip} -p {bind_port}  [✓ Console interactive]

→ Tunnel créé  : 127.0.0.1:27854 → 10.0.0.5:22 via 127.0.0.1:2222
→ SSH s'ouvre dans sa propre fenêtre console
```

---

## Confiance limitée dans le build ?

Les binaires Windows, Linux et macOS sont compilés automatiquement par GitHub Actions à partir de ce dépôt public — le workflow est visible dans [`.github/workflows/build-release.yml`](.github/workflows/build-release.yml).

Si vous préférez ne pas exécuter un binaire pré-compilé, vous pouvez lancer l'application directement depuis les sources Python :

```bash
git clone https://github.com/Altaramis/ProxyTunnelAppLauncher.git
cd ProxyTunnelAppLauncher

# 1. Créer le venv et installer les dépendances (une seule fois)
python -m venv venv
# Windows :    venv\Scripts\pip install -r requirements.txt
# Linux/macOS : venv/bin/pip install -r requirements.txt

# 2a. Lancer avec activation du venv
# Windows :    venv\Scripts\activate
# Linux/macOS : source venv/bin/activate
python ProxyTunnelAppLauncher.py

# 2b. Lancer sans activation (appel direct)
# Windows :    venv\Scripts\python ProxyTunnelAppLauncher.py
# Linux/macOS : venv/bin/python ProxyTunnelAppLauncher.py
```

Le code est sous licence GPL v3+ — vous pouvez l'auditer, le modifier et le redistribuer librement.

---

## Installation

```bash
# 1. Créer le venv et installer les dépendances (une seule fois)
python -m venv venv
# Windows :    venv\Scripts\pip install -r requirements.txt
# Linux/macOS : venv/bin/pip install -r requirements.txt

# 2a. Lancer avec activation du venv
# Windows :    venv\Scripts\activate
# Linux/macOS : source venv/bin/activate
python ProxyTunnelAppLauncher.py

# 2b. Lancer sans activation (appel direct)
# Windows :    venv\Scripts\python ProxyTunnelAppLauncher.py
# Linux/macOS : venv/bin/python ProxyTunnelAppLauncher.py
```

**Dépendances :**
- Python 3.10+
- PyQt6 >= 6.6.0
- PySocks >= 1.7.1

---

## macOS — Premier lancement

L'application n'est pas signée avec un certificat Apple payant. macOS bloque son exécution au premier lancement.

**Méthode 1 — Réglages Système (sans Terminal)**

1. Tenter d'ouvrir `ProxyTunnelAppLauncher` (le lancement est bloqué)
2. Ouvrir **Réglages Système → Confidentialité et sécurité**
3. Faire défiler vers le bas → un message *"ProxyTunnelAppLauncher a été bloqué"* apparaît
4. Cliquer **"Autoriser quand même"**
5. Rouvrir l'application → confirmer avec **"Ouvrir quand même"**

**Méthode 2 — Terminal**

```bash
xattr -dr com.apple.quarantine /chemin/vers/ProxyTunnelAppLauncher
```
Puis double-cliquer normalement.

---

## Lancement

```bash
# Via le lanceur direct
python ProxyTunnelAppLauncher.py

# Via le module Python
python -m ProxyTunnelAppLauncher
```

---

## Interface

### Fenêtre principale

Le tableau central liste toutes les commandes configurées avec les colonnes :

| Colonne | Description |
|---------|-------------|
| **Nom** | Label de la commande |
| **Statut** | En cours / Arrêté, port local alloué affiché si actif |
| **Cible** | `host:port` distant |
| **Proxy** | Profil proxy associé (en rouge si introuvable) |
| **Actions** | Boutons Lancer / Tuer / Modifier |

**Double-clic** sur une commande arrêtée pour la lancer directement.  
**Clic droit** pour accéder à : Lancer, Tuer, Modifier, Dupliquer, Supprimer.

### Barre de boutons

| Bouton | Fonction |
|--------|----------|
| **Ajouter** | Créer une nouvelle commande |
| **Tout arrêter** | Arrêter tous les tunnels actifs |
| **Exporter** | Sauvegarder la configuration dans un fichier JSON |
| **Importer** | Charger une configuration avec gestion des conflits |
| **Variables** | Gérer les variables globales réutilisables |
| **Proxies** | Gérer les profils proxy SOCKS5 |
| **Paramètres** | Configurer la plage de ports et le journal |
| **Journal** | Ouvrir la fenêtre de logs |

Un sélecteur de **thème** (Système / Clair / Sombre) est disponible en bas à droite.

---

## Configuration d'une commande

| Champ | Description |
|-------|-------------|
| **Nom** | Label unique affiché dans le tableau |
| **IP distante** | Hôte cible distant |
| **Port distant** | Port cible distant |
| **Proxy SOCKS5** | Profil proxy à utiliser (optionnel) |
| **Commande** | Template avec placeholders (voir ci-dessous) |
| **Console interactive** | Ouvre la commande dans sa propre fenêtre console — utile pour SSH, telnet |

### Placeholders disponibles dans la commande

| Placeholder | Valeur |
|-------------|--------|
| `{bind_ip}` | IP locale du tunnel (`127.0.0.1`) |
| `{bind_port}` | Port local alloué automatiquement |
| `{nom_variable}` | Toute variable globale définie dans **Variables** |

L'éditeur propose des **boutons d'insertion rapide** et un **aperçu résolu** en temps réel.

---

## Profils proxy SOCKS5

Chaque profil contient :
- **Nom** — identifiant réutilisable dans les commandes
- **Host / Port** — adresse du serveur SOCKS5
- **Utilisateur / Mot de passe** — authentification optionnelle
- **Bouton "Tester"** — vérifie la connectivité TCP vers le proxy en temps réel

Les profils sont partagés entre toutes les commandes. Un **renommage** de profil se répercute automatiquement sur toutes les commandes qui l'utilisent.

---

## Variables globales

Les variables permettent de factoriser des valeurs communes utilisées dans les templates de commandes.

Variables par défaut :

| Variable | Valeur |
|----------|--------|
| `{localhost}` | `127.0.0.1` |
| `{ssh_port}` | `22` |
| `{rdp_port}` | `3389` |

Les variables peuvent être imbriquées (résolution jusqu'à 5 passes).

---

## Paramètres

### Plage de ports locaux
Plage dans laquelle les ports locaux sont alloués **aléatoirement** à chaque tunnel.  
Par défaut : `20000 – 30000`.

### Journal fichier
Active l'écriture des logs dans un fichier rotatif (`ProxyTunnelAppLauncher.log` par défaut).  
Configurable : taille max (Mo) et nombre de fichiers de rotation.

---

## Import / Export

L'export sauvegarde l'intégralité des proxies et commandes dans un fichier JSON.

L'import détecte automatiquement les conflits :
- **Nouveau** → sera ajouté
- **Identique** → ignoré (déjà à jour)
- **Conflit** → choix par ligne : Écraser ou Ignorer

---

## Fichiers de configuration

Les fichiers sont créés automatiquement dans le **répertoire de travail** au premier lancement.

### `configs.json`
Stocke les profils proxy et les commandes.

```json
{
  "port_range": [20000, 30000],
  "proxies": [
    {
      "name": "Mon-Bastion",
      "host": "127.0.0.1",
      "port": 2222,
      "user": null,
      "password": null
    }
  ],
  "commands": [
    {
      "name": "Serveur RDP",
      "target_host": "192.168.0.201",
      "target_port": 3389,
      "proxy": "Mon-Bastion",
      "command": "mstsc /v:{bind_ip}:{bind_port}",
      "order": 0,
      "console": false
    }
  ]
}
```

### `settings.json`
Stocke les préférences et variables globales.

```json
{
  "theme": "Système",
  "log_file_enabled": false,
  "log_file_path": "ProxyTunnelAppLauncher.log",
  "log_file_max_mb": 5,
  "log_file_backup_count": 3,
  "variables": {
    "localhost": "127.0.0.1",
    "ssh_port": "22",
    "rdp_port": "3389"
  }
}
```

> ⚠️ Ces fichiers peuvent contenir des adresses et mots de passe. Ils sont exclus du dépôt git par `.gitignore`.

---

## Compilation en exécutable (Nuitka)

```batch
pip install --upgrade wheel setuptools nuitka

.\venv_win\Scripts\python.exe -m nuitka --onefile --remove-output --standalone ^
  --enable-plugin=pyqt6 --windows-console-mode=disable ^
  --windows-icon-from-ico=logo.ico ^
  --include-data-files=logo.ico=logo.ico ^
  ProxyTunnelAppLauncher.py
```

Produit un fichier `ProxyTunnelAppLauncher.exe` autonome.  
`configs.json` et `settings.json` sont lus dans le **répertoire courant** à l'exécution, non inclus dans l'exe.

---

## Structure du projet

```
ProxyTunnelAppLauncher/
    __main__.py              # Point d'entrée (python -m ProxyTunnelAppLauncher)
    models.py                # ProxyProfile, CommandEntry, AppConfig, AppSettings
    forwarder.py             # SimpleForwarder — tunnel TCP via SOCKS5
    tunnel_manager.py        # TunnelManager — cycle de vie des tunnels et processus
    config_io.py             # Lecture / écriture de configs.json
    settings_io.py           # Lecture / écriture de settings.json
    ui/
        main_window.py       # Fenêtre principale
        command_tree.py      # Widget tableau des commandes
        tree_delegate.py     # Rendu visuel du tableau
        log_window.py        # Fenêtre journal
        dialogs/
            command_dialog.py    # Créer / modifier une commande
            proxy_dialog.py      # Gérer les profils proxy
            variables_dialog.py  # Gérer les variables globales
            settings_dialog.py   # Paramètres (ports, logs, thème)
            import_dialog.py     # Import avec gestion des conflits
ProxyTunnelAppLauncher.py    # Lanceur direct
requirements.txt
```
