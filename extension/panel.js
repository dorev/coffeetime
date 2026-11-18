// Panneau de l'extension Twitch « Accès TRN ».
// Twitch fournit un jeton signé indiquant le rôle de la personne (broadcaster, moderator, viewer).
// Le serveur vérifie ce jeton : le bouton de demande ne fonctionne que pour le streamer et les mods.
(function () {
  var base = window.TRN_BASE_URL;
  var auth = null;
  var $ = function (id) { return document.getElementById(id); };

  function api(path, options) {
    options = options || {};
    // « ngrok-skip-browser-warning » : évite la page d'avertissement de ngrok pendant les tests (sans effet ailleurs).
    options.headers = Object.assign(
      { Authorization: "Bearer " + auth.token, "ngrok-skip-browser-warning": "1" }, options.headers || {});
    return fetch(base + path, options).then(function (r) { return r.json(); });
  }

  function render(info) {
    var app = $("app");
    app.className = "status-" + info.status;
    $("status-label").textContent = info.label;
    $("headline").textContent = info.headline;
    $("help-link").href = base + "/go?src=extension";
    if (info.message) { $("team-message").textContent = info.message; $("team-message").hidden = false; }
    else { $("team-message").hidden = true; }
    $("mod-zone").hidden = !info.can_request;
  }

  function refresh() {
    if (!auth) return;
    api("/ext/info").then(render).catch(function () {});
  }

  $("send").addEventListener("click", function () {
    var btn = $("send");
    btn.disabled = true;
    api("/ext/demande", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: $("message").value })
    }).then(function (res) {
      var box = $("result");
      box.textContent = res.text || "Erreur : " + (res.error || "inconnue");
      box.className = "note " + (res.outcome === "envoyee" ? "ok" : "warn");
      box.hidden = false;
      if (res.outcome === "envoyee") $("message").value = "";
    }).catch(function () {
      $("result").textContent = "Le service ne répond pas. Réessaie dans un instant.";
      $("result").hidden = false;
    }).finally(function () { btn.disabled = false; });
  });

  window.Twitch.ext.onAuthorized(function (a) {
    auth = a;
    refresh();
  });
  setInterval(refresh, 60000);
})();
