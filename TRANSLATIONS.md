# Gestion des traductions

ProxyTunnelAppLauncher utilise le système Qt Linguist (`.ts` → `.qm`).

- **`.ts`** — fichiers XML source, versionnés dans git, modifiés à la main
- **`.qm`** — binaires compilés, ignorés par git, générés par `build_translations.py`

---

## Ajouter ou supprimer du texte traduit (nouvelle fonctionnalité)

### 1. Envelopper les chaînes dans le code Python

**Dans une sous-classe de `QObject` (fenêtres, dialogues, widgets) :**

```python
self.tr("Texte à traduire")
# pour les chaînes avec variables :
self.tr("Élément {} introuvable").format(nom)
```

**Dans du code non-QObject (`forwarder.py`, fonctions utilitaires) :**

```python
from PyQt6.QtCore import QCoreApplication
QCoreApplication.translate("NomContexte", "Texte à traduire")
```

> Ne pas utiliser de f-strings avec `tr()`. Toujours `self.tr("template {}").format(var)`.

### 2. Régénérer le fichier `.ts`

```bash
venv/bin/pylupdate6 $(find ProxyTunnelAppLauncher -name "*.py") ProxyTunnelAppLauncher.py \
    -ts translations/en_US.ts
# Windows :
venv_win\Scripts\pylupdate6.exe ProxyTunnelAppLauncher\*.py ProxyTunnelAppLauncher\ui\*.py ... -ts translations\en_US.ts
```

`pylupdate6` :
- **Ajoute** les nouvelles chaînes détectées avec `<translation type="unfinished"/>`
- **Conserve** les traductions existantes
- **Marque** `type="obsolete"` les chaînes supprimées du code (ne les efface pas)

### 3. Remplir les traductions manquantes

Ouvrir `translations/en_US.ts` et compléter les `<translation type="unfinished">` :

```xml
<message>
    <source>Nouvelle chaîne</source>
    <translation type="unfinished"></translation>   <!-- avant -->
</message>

<message>
    <source>Nouvelle chaîne</source>
    <translation>New string</translation>            <!-- après -->
</message>
```

Supprimer les entrées `type="obsolete"` si la chaîne a vraiment été retirée.

### 4. Compiler et tester

```bash
python build_translations.py
python -c "
from PyQt6.QtWidgets import QApplication; import sys
app = QApplication(sys.argv)
from PyQt6.QtCore import QTranslator, QCoreApplication
t = QTranslator(); t.load('translations/en_US.qm'); app.installTranslator(t)
print(QCoreApplication.translate('MainWindow', 'Lancer'))  # doit afficher 'Launch'
"
```

### 5. Committer

```bash
git add translations/en_US.ts
git commit -m "i18n: update en_US translations"
```

Le `.qm` n'est **pas** commité (il est dans `.gitignore`). La CI le régénère.

---

## Ajouter une nouvelle langue

### 1. Créer le fichier `.ts`

Copier le fichier anglais comme base de travail :

```bash
cp translations/en_US.ts translations/fr_FR.ts
```

Puis remplacer chaque `<translation>…</translation>` par la traduction dans la nouvelle langue.

### 2. Mettre à jour `__main__.py`

Charger la locale active et la traduction correspondante :

```python
# ProxyTunnelAppLauncher/__main__.py
locale = settings.language or QLocale.system().name()   # ex: "fr_FR"
translator = QTranslator()
qm_path = os.path.join(os.path.dirname(__file__), "..", "translations", f"{locale}.qm")
if translator.load(qm_path):
    app.installTranslator(translator)
```

### 3. Compiler toutes les langues

```bash
python build_translations.py
# compile automatiquement tous les .ts présents dans translations/
```

### 4. Ajouter la langue dans les Paramètres (optionnel)

Dans `settings_dialog.py`, ajouter la langue au sélecteur afin que l'utilisateur puisse la choisir dans l'interface.

### 5. Committer

```bash
git add translations/fr_FR.ts
git commit -m "i18n: add French (fr_FR) translation"
```

---

## Architecture du compilateur (`build_translations.py`)

`build_translations.py` est un générateur `.qm` pur Python, utilisé quand `lrelease` n'est pas disponible (PyQt6 ≥ 6.5 ne le fournit plus).

Il implémente le format binaire Qt :
- **Magic bytes** 16 octets
- **Section Hashes** (tag `0x42`) — table triée de paires `(elfHash(source), offset_message)`
- **Section Messages** (tag `0x69`) — enregistrements contenant :
  - `Tag_Translation (0x03)` — chaîne traduite en UTF-16-BE
  - `Tag_Comment (0x08)` — désambiguïsation (vide si pas de commentaire)
  - `Tag_SourceText (0x06)` — chaîne source en UTF-8
  - `Tag_Context (0x07)` — nom de la classe en UTF-8
  - `Tag_End (0x01)`

Les traductions marquées `type="unfinished"` dans le `.ts` sont ignorées.

---

## Résumé des commandes

| Action | Commande |
|--------|----------|
| Extraire les chaînes du code | `pylupdate6 ... -ts translations/en_US.ts` |
| Compiler les `.ts` → `.qm` | `python build_translations.py` |
| Tester une traduction | voir section *Compiler et tester* ci-dessus |
