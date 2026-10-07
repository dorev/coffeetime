// Rafraîchit le widget chaque minute à partir de /status.json.
(function () {
  var btn = document.querySelector("[data-status-url]");
  if (!btn) return;
  function refresh() {
    fetch(btn.getAttribute("data-status-url"), { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) {
        if (!s) return;
        btn.className = btn.className.replace(/status-\w+/, "status-" + s.status);
        btn.querySelector('[data-field="label"]').textContent = s.label;
        btn.querySelector('[data-field="action"]').textContent = s.action + " →";
      })
      .catch(function () {});
  }
  setInterval(refresh, 60000);
})();
