/**
 * Webhook Google Apps Script : ajoute les événements du service Accès TRN dans la feuille.
 *
 * Installation (5 minutes) : voir README.md dans ce dossier.
 * Le service envoie : { "secret": "...", "rows": [[at, type, channel, source, actor, message, trn_status, detail], ...] }
 */
var HEADERS = ["Horodatage (UTC)", "Événement", "Chaîne", "Source", "Personne", "Message", "Statut TRN", "Détail"];

function doPost(e) {
  var props = PropertiesService.getScriptProperties();
  var expected = props.getProperty("WEBHOOK_SECRET");
  var body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (err) {
    return reply({ ok: false, error: "json" });
  }
  if (!expected || body.secret !== expected) {
    return reply({ ok: false, error: "secret" });
  }
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Événements")
      || SpreadsheetApp.getActiveSpreadsheet().insertSheet("Événements");
    if (sheet.getLastRow() === 0) {
      sheet.appendRow(HEADERS);
      sheet.setFrozenRows(1);
    }
    var rows = (body.rows || []).map(function (r) { return r.map(function (v) { return v === null ? "" : String(v); }); });
    if (rows.length) {
      sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, HEADERS.length).setValues(rows);
    }
    return reply({ ok: true, added: rows.length });
  } finally {
    lock.releaseLock();
  }
}

function reply(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
