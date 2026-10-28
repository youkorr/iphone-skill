# Place Nette pour Pythonista 3
# Analyse le stockage et la photothèque de l'iPhone, puis supprime ce que tu choisis.
# Rien ne quitte l'iPhone. Les suppressions passent par « Supprimés récemment » (30 jours pour changer d'avis).

import base64
import datetime
import html
import json
import os
import shutil
import traceback
import urllib.parse

import photos
import ui
from objc_util import ObjCClass, ObjCInstance, create_objc_class, ns, nsurl, on_main_thread

VERSION = "1.1"
TOP_VIDEOS = 30
MAX_SCREEN_THUMBS = 60
MAX_DUP_GROUPS = 40
MAX_DUP_TILES = 6
THUMB_SIZE = (150, 150)
TOP_FILES = 40

# Apps qui ont leur propre outil de nettoyage. iOS interdit de le faire à leur place.
APPS = [
    ("WhatsApp", "whatsapp://", [
        "Onglet <strong>Réglages</strong> › <strong>Stockage et données</strong> › <strong>Gérer le stockage</strong>.",
        "Ouvre « Plus de 5 Mo » et les discussions les plus lourdes, sélectionne et supprime.",
        "Pour éviter les doublons : Réglages › Discussions › désactive <strong>Enregistrer dans Photos</strong>.",
        "Pour limiter : Stockage et données › Téléchargement automatique des médias › Wi-Fi ou Jamais."]),
    ("TikTok", "tiktok://", [
        "Onglet <strong>Profil</strong> › <strong>☰</strong> en haut à droite › <strong>Paramètres et confidentialité</strong>.",
        "<strong>Libérer de l'espace</strong> › <strong>Cache</strong> › Effacer.",
        "Dans le même écran, supprime les <strong>Téléchargements</strong> et brouillons inutiles."]),
    ("Instagram", "instagram://app", [
        "Instagram n'a pas de bouton pour vider son cache.",
        "Réglages › Général › Stockage iPhone › Instagram : si « Documents et données » dépasse 1 Go, supprime l'app puis réinstalle-la.",
        "Vérifie ton mot de passe avant."]),
    ("Snapchat", "snapchat://", [
        "Touche ton avatar › <strong>⚙️</strong> › <strong>Actions sur le compte</strong> › <strong>Vider le cache</strong>.",
        "Tes Souvenirs ne sont pas supprimés."]),
    ("Telegram", "tg://", [
        "<strong>Réglages</strong> › <strong>Données et stockage</strong> › <strong>Utilisation du stockage</strong> › <strong>Vider le cache</strong>.",
        "Règle <strong>Conserver les médias</strong> sur 1 semaine pour que ça ne revienne pas."]),
    ("Facebook", "fb://", [
        "Menu › Paramètres et confidentialité › <strong>Paramètres</strong> › <strong>Navigateur</strong> › Effacer les données de navigation.",
        "Si l'app pèse encore plus de 1 Go : supprime-la et réinstalle-la."]),
    ("Spotify", "spotify://", [
        "<strong>Accueil</strong> › ta photo › <strong>Paramètres et confidentialité</strong> › <strong>Stockage</strong> › <strong>Vider le cache</strong>.",
        "Dans le même écran, <strong>Supprimer tous les téléchargements</strong> si tu ne les écoutes plus."]),
    ("YouTube", "youtube://", [
        "Onglet <strong>Vous</strong> › <strong>Téléchargements</strong> : supprime les vidéos déjà vues."]),
    ("Netflix", "nflx://", [
        "Onglet <strong>Mon Netflix</strong> › <strong>Téléchargements</strong> : supprime les épisodes vus.",
        "Active <strong>Téléchargements intelligents</strong> pour qu'ils s'effacent tout seuls."]),
    ("Notes", "mobilenotes://", [
        "Dans la liste des dossiers, touche <strong>…</strong> › <strong>Afficher les pièces jointes</strong> : photos, vidéos et PDF des notes, à supprimer depuis la note.",
        "Vide ensuite le dossier <strong>Supprimées récemment</strong> des Notes."]),
    ("Messages", "", [
        "Réglages › Général › Stockage iPhone › Messages › <strong>Examiner les grandes pièces jointes</strong>.",
        "Réglages › Apps › Messages › <strong>Garder les messages</strong> › 1 an."]),
]


# --- Mesures -----------------------------------------------------------------

def read_storage():
    """Capacité totale et espace disponible, comme dans Réglages › Stockage iPhone."""
    home = os.path.expanduser("~")
    total = free = None
    try:
        url = ObjCClass("NSURL").fileURLWithPath_(home)
        keys = ["NSURLVolumeTotalCapacityKey", "NSURLVolumeAvailableCapacityForImportantUsageKey"]
        vals = url.resourceValuesForKeys_error_(ns(keys), None)
        t = vals.objectForKey_(keys[0])
        f = vals.objectForKey_(keys[1])
        if t:
            total = int(t.longLongValue())
        if f:
            free = int(f.longLongValue())
    except Exception:
        pass
    if not total or free is None:
        du = shutil.disk_usage(home)
        total = total or du.total
        free = du.free if free is None else free
    return total, free


def resource_sizes(local_ids, progress):
    """Taille réelle de chaque élément de la photothèque, en octets (original, Live Photo comprise)."""
    PHAsset = ObjCClass("PHAsset")
    PHAssetResource = ObjCClass("PHAssetResource")
    sizes = {}
    result = PHAsset.fetchAssetsWithLocalIdentifiers_options_(ns(local_ids), None)
    n = int(result.count())
    for i in range(n):
        a = result.objectAtIndex_(i)
        total = 0
        try:
            res = PHAssetResource.assetResourcesForAsset_(a)
            for j in range(int(res.count())):
                v = res.objectAtIndex_(j).valueForKey_("fileSize")
                if v:
                    total += int(v.longLongValue())
        except Exception:
            total = 0
        sizes[str(a.localIdentifier())] = total
        if i % 250 == 0:
            progress("Mesure des fichiers", i, n)
    return sizes


def estimate_size(asset):
    """Estimation quand iOS ne donne pas la taille : environ 3 Mo par photo, 1,5 Mo par seconde de vidéo."""
    if asset.media_type == "video":
        return int((getattr(asset, "duration", 0) or 0) * 1.5e6)
    return 3_000_000


_thumbs = {}


def thumb(asset):
    if asset.local_id in _thumbs:
        return _thumbs[asset.local_id]
    _thumbs[asset.local_id] = _make_thumb(asset)
    return _thumbs[asset.local_id]


def _make_thumb(asset):
    try:
        img = asset.get_ui_image(size=THUMB_SIZE, crop=True)
        if img:
            return "data:image/png;base64," + base64.b64encode(img.to_png()).decode()
    except Exception:
        pass
    return ""


# --- Analyse -----------------------------------------------------------------

class Library:
    def __init__(self):
        self.by_id = {}
        self.items = []
        self.estimated = False

    def scan(self, progress):
        progress("Lecture de la photothèque", 0, 1)
        assets = photos.get_assets(media_type="image") + photos.get_assets(media_type="video")
        self.by_id = {a.local_id: a for a in assets}
        sizes = {}
        try:
            sizes = resource_sizes(list(self.by_id), progress)
        except Exception:
            sizes = {}
        self.items = []
        for a in assets:
            size = sizes.get(a.local_id) or 0
            date = a.creation_date
            if date is not None and date.tzinfo is not None:
                date = date.replace(tzinfo=None)
            if not size:
                size = estimate_size(a)
                self.estimated = True
            self.items.append({
                "id": a.local_id,
                "video": a.media_type == "video",
                "screen": "photo_screenshot" in (getattr(a, "media_subtypes", None) or []),
                "size": size,
                "w": a.pixel_width,
                "h": a.pixel_height,
                "date": date,
                "duration": getattr(a, "duration", 0) or 0,
            })

    def remove(self, ids):
        gone = set(ids)
        self.items = [it for it in self.items if it["id"] not in gone]
        for i in gone:
            self.by_id.pop(i, None)


def still_present(ids):
    """Identifiants encore présents dans la photothèque après une demande de suppression."""
    PHAsset = ObjCClass("PHAsset")
    result = PHAsset.fetchAssetsWithLocalIdentifiers_options_(ns(ids), None)
    return {str(result.objectAtIndex_(i).localIdentifier()) for i in range(int(result.count()))}


def scan_folder(path):
    """Fichiers les plus lourds d'un dossier choisi dans l'app Fichiers."""
    files, total, count = [], 0, 0
    for root, dirs, names in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for n in names:
            if n.startswith("."):
                continue
            fp = os.path.join(root, n)
            try:
                size = os.path.getsize(fp)
            except OSError:
                continue
            total += size
            count += 1
            files.append((size, os.path.relpath(fp, path)))
    files.sort(reverse=True)
    return {"name": os.path.basename(path.rstrip("/")) or path, "total": total, "count": count, "top": files[:TOP_FILES]}


# --- Mise en forme -----------------------------------------------------------

def fmt_size(b):
    if b >= 1e9:
        return ("%.1f Go" % (b / 1e9)).replace(".", ",")
    if b >= 1e6:
        return "%d Mo" % round(b / 1e6)
    return "%d Ko" % max(1, round(b / 1e3))


def fmt_num(n):
    return "{:,}".format(n).replace(",", " ")


def fmt_duration(s):
    s = int(round(s))
    return "%d:%02d" % (s // 60, s % 60) if s < 3600 else "%d h %02d" % (s // 3600, (s % 3600) // 60)


def fmt_date(d):
    return d.strftime("%d/%m/%Y") if d else ""


def marketing_capacity(total):
    """iOS affiche 128 Go même si le volume fait 119 Go une fois formaté."""
    for c in (16, 32, 64, 128, 256, 512, 1024, 2048):
        if total <= c * 1e9:
            return c
    return round(total / 1e9)


CSS = """
:root {
  --bg: #F1F5F4; --surface: #FFFFFF; --ink: #12201C; --muted: #586A65; --line: #D8E2DF;
  --accent: #0A7A61; --accent-ink: #FFFFFF; --accent-soft: #DCEFE9; --warn: #A86A0C; --crit: #B93A12;
  --c-photos: #DE9A12; --c-videos: #D2457A; --c-other: #3A6AD4;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0C1311; --surface: #141D1A; --ink: #E3ECE9; --muted: #92A39E; --line: #24302C;
    --accent: #45D2AC; --accent-ink: #052119; --accent-soft: #123A2F; --warn: #E6A63B; --crit: #F07A52;
    --c-photos: #F0B232; --c-videos: #EC6B9A; --c-other: #5C8BF0;
    color-scheme: dark;
  }
}
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.45 -apple-system, system-ui, sans-serif; }
.wrap { padding: 18px 16px 120px; display: grid; gap: 22px; max-width: 640px; margin: 0 auto; }
h1 { font-size: 1.9rem; line-height: 1.1; margin: 0; letter-spacing: -0.02em; }
h2 { font-size: 1.3rem; margin: 0; }
p { margin: 0; }
.muted { color: var(--muted); } .small { font-size: 0.875rem; }
.num { font-variant-numeric: tabular-nums; font-weight: 600; }
.eyebrow { font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); font-weight: 600; }
.card { background: var(--surface); border-radius: 14px; padding: 16px; display: grid; gap: 12px; }
.big { font-size: 3rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1; }
.bar { display: flex; height: 18px; border-radius: 6px; overflow: hidden; background: var(--line); }
.bar span { height: 100%; }
.bar span + span { border-left: 2px solid var(--surface); }
.legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 0.82rem; color: var(--muted); }
.legend i { display: inline-block; width: 9px; height: 9px; border-radius: 3px; margin-right: 6px; }
.stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.stats div { background: var(--bg); border-radius: 10px; padding: 10px 12px; display: grid; gap: 2px; }
.stats .num { font-size: 1.15rem; }
.grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
.tile { position: relative; border-radius: 10px; overflow: hidden; background: var(--line); aspect-ratio: 1; border: 3px solid transparent; }
.tile img { width: 100%; height: 100%; object-fit: cover; display: block; }
.tile .meta { position: absolute; left: 0; right: 0; bottom: 0; padding: 14px 6px 4px; font-size: 0.72rem; font-weight: 600; color: #fff;
  background: linear-gradient(transparent, rgba(0,0,0,.7)); display: flex; justify-content: space-between; gap: 4px; }
.tile .tick { position: absolute; top: 6px; right: 6px; width: 24px; height: 24px; border-radius: 50%; border: 2px solid #fff;
  background: rgba(0,0,0,.25); display: grid; place-items: center; }
.tile.on { border-color: var(--accent); }
.tile.on .tick { background: var(--accent); border-color: var(--accent); }
.tile.on .tick::after { content: ""; width: 6px; height: 11px; border: solid var(--accent-ink); border-width: 0 2.5px 2.5px 0; transform: translateY(-1px) rotate(45deg); }
.row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
button { font: 600 0.92rem -apple-system, system-ui, sans-serif; border-radius: 10px; padding: 9px 14px; border: 1px solid var(--line);
  background: transparent; color: var(--accent); }
.group { display: grid; gap: 6px; padding-top: 10px; border-top: 1px solid var(--line); }
.notice { background: var(--accent-soft); border-radius: 12px; padding: 12px 14px; font-size: 0.92rem; }
.warn { color: var(--warn); }
.dock { position: fixed; left: 0; right: 0; bottom: 0; padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
  background: var(--surface); border-top: 1px solid var(--line); display: flex; gap: 12px; align-items: center; justify-content: space-between; }
.dock button { background: var(--accent); color: var(--accent-ink); border: 0; padding: 12px 18px; font-size: 1rem; }
.dock button:disabled { opacity: .4; }
details.app { border-top: 1px solid var(--line); padding-top: 10px; }
details.app summary { font-weight: 600; cursor: pointer; }
details.app ol { margin: 8px 0; padding-left: 1.3em; display: grid; gap: 6px; font-size: 0.92rem; }
.files { display: grid; gap: 2px; }
.file { display: flex; justify-content: space-between; gap: 12px; padding: 7px 0; border-bottom: 1px solid var(--line); font-size: 0.88rem; }
.file span:first-child { min-width: 0; overflow-wrap: anywhere; }
.file .num { white-space: nowrap; }
.progress { height: 6px; border-radius: 3px; background: var(--line); overflow: hidden; }
.progress span { display: block; height: 100%; width: 0; background: var(--accent); transition: width .3s; }
"""

JS = """
var sel = new Set();
function upd() {
  var n = 0, b = 0;
  sel.forEach(function (id) { n++; b += SIZES[id] || 0; });
  document.querySelectorAll('.tile').forEach(function (t) { t.classList.toggle('on', sel.has(t.dataset.id)); });
  document.getElementById('sel-count').textContent = n ? n + ' sélectionné' + (n > 1 ? 's' : '') + ' · ' + fmtSize(b) : 'Rien de sélectionné';
  document.getElementById('del').disabled = !n;
}
function fmtSize(b) {
  if (b >= 1e9) return (b / 1e9).toFixed(1).replace('.', ',') + ' Go';
  if (b >= 1e6) return Math.round(b / 1e6) + ' Mo';
  return Math.max(1, Math.round(b / 1e3)) + ' Ko';
}
function tog(el) { var id = el.dataset.id; sel.has(id) ? sel.delete(id) : sel.add(id); upd(); }
function pick(key) { (GROUPS[key] || []).forEach(function (id) { sel.add(id); }); upd(); }
function clearSel() { sel.clear(); upd(); }
function go(u) { location.href = 'placenette://open?u=' + encodeURIComponent(u); }
function del() {
  if (!sel.size) return;
  location.href = 'placenette://delete?ids=' + encodeURIComponent(JSON.stringify(Array.from(sel)));
}
"""


def page(body, script=""):
    return ("<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1, viewport-fit=cover'>"
            "<style>" + CSS + "</style></head><body>" + body +
            "<script>" + script + "</script></body></html>")


def loading_page():
    return page(
        "<div class='wrap'><p class='eyebrow'>Place Nette</p><h1>Analyse de ton iPhone…</h1>"
        "<p class='muted' id='step'>Lecture de la photothèque</p>"
        "<div class='progress'><span id='bar'></span></div>"
        "<p class='small muted'>Avec beaucoup de photos, compte une à deux minutes. Rien ne quitte l'iPhone.</p></div>",
        "function setProgress(step, p) { document.getElementById('step').textContent = step;"
        " document.getElementById('bar').style.width = Math.round(p * 100) + '%'; }")


def message_page(title, text):
    return page("<div class='wrap'><p class='eyebrow'>Place Nette</p><h1>" + html.escape(title) + "</h1>"
                "<p>" + text + "</p></div>")


def tile(item, asset, label_right):
    left = fmt_size(item["size"])
    src = thumb(asset)
    return ("<div class='tile' data-id='" + html.escape(item["id"], quote=True) + "' onclick='tog(this)'>"
            + ("<img src='" + src + "' alt=''>" if src else "") +
            "<span class='tick'></span>"
            "<span class='meta'><span>" + left + "</span><span>" + html.escape(label_right) + "</span></span></div>")


def apps_section():
    out = ["<div class='card'><h2>Nettoyer WhatsApp, TikTok et les autres</h2>"
           "<p class='small muted'>iOS interdit à toute app de toucher aux données des autres. Mais la plupart ont leur propre "
           "bouton de nettoyage, bien caché. Vérifie d'abord lesquelles pèsent le plus : "
           "Réglages › Général › Stockage iPhone.</p>"
           "<div class='row'><button onclick=\"go('App-prefs:General&path=STORAGE_MGMT')\">Ouvrir Stockage iPhone</button></div>"]
    for name, scheme, steps in APPS:
        out.append("<details class='app'><summary>" + name + "</summary><ol>" +
                   "".join("<li>" + st + "</li>" for st in steps) + "</ol>" +
                   ("<button onclick=\"go('" + scheme + "')\">Ouvrir " + name + "</button>" if scheme else "") +
                   "</details>")
    out.append("</div>")
    return "".join(out)


def folder_section(folder):
    out = ["<div class='card'><h2>App Fichiers</h2>"]
    if not folder:
        out.append("<p class='small muted'>Téléchargements et documents ne sont pas dans Photos. Choisis un dossier, par exemple "
                   "<em>Sur mon iPhone</em> ou <em>Téléchargements</em>, pour voir ses fichiers les plus lourds.</p>")
    elif folder.get("error"):
        out.append("<p class='small warn'>" + html.escape(folder["error"]) + "</p>")
    else:
        out.append("<p class='small muted'><strong>" + html.escape(folder["name"]) + "</strong> : " + fmt_num(folder["count"]) +
                   " fichiers, " + fmt_size(folder["total"]) + ". Les plus lourds :</p><div class='files'>")
        for size, rel in folder["top"]:
            out.append("<div class='file'><span>" + html.escape(rel) + "</span><span class='num'>" + fmt_size(size) + "</span></div>")
        out.append("</div><p class='small muted'>Pour supprimer : ouvre l'app Fichiers, appuie longuement sur le fichier › Supprimer, "
                   "puis vide <em>Suppressions récentes</em>.</p>")
    out.append("<div class='row'><button onclick=\"location.href='placenette://folder'\">" +
               ("Analyser un autre dossier" if folder and not folder.get("error") else "Choisir un dossier") + "</button>"
               "<button onclick=\"go('shareddocuments://')\">Ouvrir Fichiers</button></div></div>")
    return "".join(out)


def report_page(lib, total, free, notice="", folder=None):
    items = lib.items
    cap = marketing_capacity(total)
    used = max(0, total - free)
    vids = [it for it in items if it["video"]]
    imgs = [it for it in items if not it["video"]]
    screens = sorted([it for it in imgs if it["screen"]], key=lambda it: it["date"] or datetime.datetime.min)
    size_v = sum(it["size"] for it in vids)
    size_i = sum(it["size"] for it in imgs)
    size_s = sum(it["size"] for it in screens)
    lib_total = size_v + size_i

    # Doublons probables : mêmes dimensions et même taille au octet près
    buckets = {}
    for it in imgs:
        if it["size"] and not lib.estimated:
            buckets.setdefault((it["w"], it["h"], it["size"]), []).append(it)
    dups = [sorted(g, key=lambda it: it["date"] or datetime.datetime.min) for g in buckets.values() if len(g) > 1]
    dups.sort(key=lambda g: -g[0]["size"] * (len(g) - 1))
    dup_copies = [it for g in dups for it in g[1:]]

    now = datetime.datetime.now()
    old_screens = [it for it in screens if it["date"] and (now - it["date"]).days > 30]

    sizes = {it["id"]: it["size"] for it in items}
    groups = {
        "screens-all": [it["id"] for it in screens],
        "screens-old": [it["id"] for it in old_screens],
        "dups": [it["id"] for it in dup_copies],
    }

    def pct(b):
        return "%.2f%%" % (100.0 * b / total) if total else "0%"

    other = max(0, used - lib_total)
    out = ["<div class='wrap'>"]
    if notice:
        out.append("<div class='notice'>" + notice + "</div>")
    out.append(
        "<div class='card'><p class='eyebrow'>Stockage</p>"
        "<div class='row' style='align-items:baseline'><span class='big num'>" + fmt_size(free).replace(" Go", "") +
        "</span><span class='muted'>" + (" Go" if free >= 1e9 else "") + " libres sur " + str(cap) + " Go</span></div>"
        "<div class='bar'><span style='width:" + pct(min(size_i, used)) + ";background:var(--c-photos)'></span>"
        "<span style='width:" + pct(min(size_v, used)) + ";background:var(--c-videos)'></span>"
        "<span style='width:" + pct(other) + ";background:var(--c-other)'></span></div>"
        "<div class='legend'><span><i style='background:var(--c-photos)'></i>Photos " + fmt_size(size_i) + "</span>"
        "<span><i style='background:var(--c-videos)'></i>Vidéos " + fmt_size(size_v) + "</span>"
        "<span><i style='background:var(--c-other)'></i>Apps, iOS et le reste " + fmt_size(other) + "</span></div>"
        + ("<p class='small warn'>Tailles estimées : iOS n'a pas donné la taille exacte des fichiers.</p>" if lib.estimated else "") +
        "</div>")

    out.append(
        "<div class='stats'>"
        "<div><span class='eyebrow'>Photos</span><span class='num'>" + fmt_num(len(imgs)) + "</span></div>"
        "<div><span class='eyebrow'>Vidéos</span><span class='num'>" + fmt_num(len(vids)) + "</span></div>"
        "<div><span class='eyebrow'>Captures d'écran</span><span class='num'>" + fmt_num(len(screens)) + "</span></div>"
        "<div><span class='eyebrow'>Doublons probables</span><span class='num'>" + fmt_num(len(dup_copies)) + "</span></div>"
        "</div>")
    out.append(apps_section())
    out.append(folder_section(folder))

    # Vidéos les plus lourdes
    top = sorted(vids, key=lambda it: -it["size"])[:TOP_VIDEOS]
    if top:
        out.append("<div class='card'><h2>Les vidéos les plus lourdes</h2>"
                   "<p class='small muted'>Les " + str(len(top)) + " plus grosses pèsent " +
                   fmt_size(sum(it["size"] for it in top)) + ". Touche une vidéo pour la sélectionner.</p><div class='grid'>")
        for it in top:
            out.append(tile(it, lib.by_id[it["id"]], fmt_duration(it["duration"])))
        out.append("</div></div>")

    # Captures d'écran
    if screens:
        shown = screens[:MAX_SCREEN_THUMBS]
        out.append("<div class='card'><h2>Captures d'écran</h2>"
                   "<p class='small muted'>" + fmt_num(len(screens)) + " captures, " + fmt_size(size_s) + " au total, dont " +
                   fmt_num(len(old_screens)) + " de plus de 30 jours.</p>"
                   "<div class='row'><button onclick=\"pick('screens-old')\">Plus de 30 jours</button>"
                   "<button onclick=\"pick('screens-all')\">Toutes</button></div>"
                   + ("<p class='small muted'>Aperçu des " + str(len(shown)) + " plus anciennes.</p>" if len(screens) > len(shown) else "") +
                   "<div class='grid'>")
        for it in shown:
            out.append(tile(it, lib.by_id[it["id"]], fmt_date(it["date"])))
        out.append("</div></div>")

    # Doublons
    if dups:
        out.append("<div class='card'><h2>Doublons probables</h2>"
                   "<p class='small muted'>Photos identiques au octet près. La plus ancienne de chaque groupe est gardée ; "
                   "le bouton sélectionne les copies (" + fmt_num(len(dup_copies)) + ", " +
                   fmt_size(sum(it["size"] for it in dup_copies)) + ").</p>"
                   "<div class='row'><button onclick=\"pick('dups')\">Sélectionner les copies</button></div>")
        for g in dups[:MAX_DUP_GROUPS]:
            out.append("<div class='group'><p class='small muted'>" + str(len(g)) + " exemplaires</p><div class='grid'>")
            for k, it in enumerate(g[:MAX_DUP_TILES]):
                out.append(tile(it, lib.by_id[it["id"]], "original" if k == 0 else "copie"))
            out.append("</div></div>")
        out.append("</div>")

    out.append(
        "<div class='card'><h2>Ce que Place Nette ne peut pas faire</h2>"
        "<p class='small muted'>Aucune app ne peut vider les Données système ni les caches des autres apps : seul iOS les gère. "
        "Redémarrer l'iPhone et installer la dernière mise à jour d'iOS aide à les faire baisser.</p></div>")
    out.append("<p class='small muted' style='text-align:center'>Place Nette " + VERSION + " · rien ne quitte ton iPhone</p>")
    out.append("</div>")
    out.append("<div class='dock'><span class='small' id='sel-count'>Rien de sélectionné</span>"
               "<button id='del' onclick='del()' disabled>Supprimer</button></div>")

    script = ("var SIZES = " + json.dumps(sizes) + "; var GROUPS = " + json.dumps(groups) + ";" + JS + "upd();")
    return page("".join(out), script)


# --- Application -------------------------------------------------------------

class App:
    def __init__(self):
        self.lib = Library()
        self.folder = None
        self.wv = ui.WebView(name="Place Nette")
        self.wv.delegate = self
        self.wv.load_html(loading_page())
        self.wv.present("fullscreen")
        self.run_scan()

    @on_main_thread
    def show(self, html_text):
        self.wv.load_html(html_text)

    @on_main_thread
    def progress(self, step, i, n):
        self.wv.eval_js("setProgress(%s, %f)" % (json.dumps(step), (i / n) if n else 0))

    @ui.in_background
    def run_scan(self):
        try:
            if not photos.is_authorized():
                photos.get_assets()  # déclenche la demande d'accès
            self.lib.scan(self.progress)
            self.progress("Préparation des aperçus", 1, 1)
            self.refresh()
        except Exception:
            if not photos.is_authorized():
                self.show(message_page("Accès aux photos refusé",
                                       "Autorise l'accès complet : Réglages › Apps › Pythonista › Photos › Accès complet, puis relance Place Nette."))
            else:
                self.show(message_page("Quelque chose a bloqué",
                                       "Envoie une capture de cet écran pour que le problème soit corrigé.<br><pre style='white-space:pre-wrap;font-size:12px'>" +
                                       html.escape(traceback.format_exc()) + "</pre>"))

    @ui.in_background
    def delete(self, ids):
        assets = [self.lib.by_id[i] for i in ids if i in self.lib.by_id]
        if not assets:
            return
        try:
            photos.batch_delete(assets)  # iOS affiche sa propre confirmation
        except Exception:
            pass
        remaining = still_present(ids)
        deleted = [i for i in ids if i not in remaining]
        freed = sum(it["size"] for it in self.lib.items if it["id"] in set(deleted))
        self.lib.remove(deleted)
        if deleted:
            notice = ("<strong>" + fmt_num(len(deleted)) + " élément" + ("s" if len(deleted) > 1 else "") +
                      " supprimé" + ("s" if len(deleted) > 1 else "") + ", " + fmt_size(freed) + ".</strong> "
                      "Ils restent 30 jours dans <em>Supprimés récemment</em>. Pour libérer la place tout de suite : "
                      "Photos › Albums › Supprimés récemment › Sélectionner › Tout supprimer.")
        else:
            notice = "Rien n'a été supprimé."
        self.refresh(notice)

    def refresh(self, notice=""):
        total, free = read_storage()
        self.show(report_page(self.lib, total, free, notice, self.folder))

    @on_main_thread
    def open_url(self, u):
        app = ObjCClass("UIApplication").sharedApplication()
        app.openURL_options_completionHandler_(nsurl(u), ns({}), None)

    @on_main_thread
    def pick_folder(self):
        UTType = ObjCClass("UTType")
        picker = ObjCClass("UIDocumentPickerViewController").alloc().initForOpeningContentTypes_(
            ns([UTType.typeWithIdentifier_("public.folder")]))
        picker.setDelegate_(_picker_delegate(self))
        root = ObjCClass("UIApplication").sharedApplication().keyWindow().rootViewController()
        while root.presentedViewController():
            root = root.presentedViewController()
        root.presentViewController_animated_completion_(picker, True, None)

    @ui.in_background
    def folder_picked(self, url):
        try:
            url.startAccessingSecurityScopedResource()
            try:
                self.folder = scan_folder(str(url.path()))
            finally:
                url.stopAccessingSecurityScopedResource()
        except Exception as e:
            self.folder = {"error": "Impossible de lire ce dossier (" + str(e) + "). iOS ne l'autorise peut-être pas."}
        self.refresh()

    # Délégué du WebView : les boutons de la page appellent placenette://…
    def webview_should_start_load(self, webview, url, nav_type):
        if url.startswith("placenette://delete"):
            query = urllib.parse.urlparse(url).query
            raw = urllib.parse.parse_qs(query).get("ids", ["[]"])[0]
            try:
                ids = json.loads(raw)
            except ValueError:
                ids = []
            self.delete(ids)
            return False
        if url.startswith("placenette://open"):
            target = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("u", [""])[0]
            if target:
                self.open_url(target)
            return False
        if url.startswith("placenette://folder"):
            try:
                self.pick_folder()
            except Exception as e:
                self.folder = {"error": "Le choix de dossier n'est pas disponible (" + str(e) + ")."}
                self.refresh()
            return False
        return True


# Délégué du sélecteur de dossier (UIDocumentPickerViewController)
_picker_app = [None]


def documentPicker_didPickDocumentsAtURLs_(_self, _cmd, _picker, _urls):
    urls = ObjCInstance(_urls)
    if _picker_app[0] is not None and urls.count():
        _picker_app[0].folder_picked(urls.objectAtIndex_(0))


def documentPickerWasCancelled_(_self, _cmd, _picker):
    pass


_PickerDelegate = None


def _picker_delegate(app):
    global _PickerDelegate
    _picker_app[0] = app
    if _PickerDelegate is None:
        try:
            # Pythonista garde les classes Objective-C d'un lancement à l'autre
            _PickerDelegate = ObjCClass("PlaceNettePickerDelegate")
        except ValueError:
            _PickerDelegate = None
    if _PickerDelegate is None:
        _PickerDelegate = create_objc_class(
            "PlaceNettePickerDelegate",
            methods=[documentPicker_didPickDocumentsAtURLs_, documentPickerWasCancelled_],
            protocols=["UIDocumentPickerDelegate"])
    app._delegate = _PickerDelegate.new()  # garder une référence tant que le sélecteur est ouvert
    return app._delegate


if __name__ == "__main__":
    App()
