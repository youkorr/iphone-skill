#!/usr/bin/env bash
# Assemble index.html (version installable) à partir de src/app.html.
set -euo pipefail
cd "$(dirname "$0")"
{
  cat <<'HEAD'
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Libère le stockage de ton iPhone et donne-lui une seconde vie.">
<meta name="theme-color" content="#0A7A61">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Place Nette">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icons/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="icons/icon-180.png">
</head>
<body>
HEAD
  cat src/app.html
  cat <<'TAIL'
<script>
if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () { navigator.serviceWorker.register("sw.js").catch(function () {}); });
}
</script>
</body>
</html>
TAIL
} > index.html
echo "index.html généré"
