/* ===========================================================================
 * pl24_worker.js — worker de Partslink24 (28-nov-2026)
 *
 * Corre DENTRO de la pestaña de partslink24.com que abre MODO_REMOTO (#mpworker),
 * con la sesión del dueño ya iniciada. Mismo patrón que catalog_worker.js: toma
 * trabajos de catalog_job cuyo vin empieza con "PL24:", lee las páginas como las
 * ve el dueño (iframe mismo-origen, la app es JS) y devuelve TEXTO.
 *
 *   job.vin = "PL24:<VIN>", job.descripciones = {servicio: "skoda_parts",
 *            terminos: [{desc: "parabrisas", en: "windscreen"}, ...]}
 *
 * Por término: búsqueda del catálogo filtrada por VIN (/search?q=...) → hits
 * (número, descripción, MG, SG, ilustración). Para el grupo VW (servicio
 * skoda/vw/audi/seat) abre además la lámina (BOM) de la ilustración principal,
 * que trae todas las variantes con fechas y restricciones.
 *
 * Sesión: si la app muestra "Demo" o la pantalla de login, el latido lo dice
 * ("DEMO") y el relay avisa por Telegram. Cada 10 min recarga su propia pestaña
 * para que la sesión no expire (decisión del dueño, 28-nov).
 * =========================================================================== */
(function () {
  var SUPABASE_URL = "__SUPABASE_URL__";
  var ANON_KEY     = "__SUPABASE_ANON_KEY__";
  var POLL_MS = 5000, ESPERA_MS = 20000, RECARGA_MS = 10 * 60 * 1000, LATIDO_ID = 2;
  var VIN_RE = /^[A-HJ-NPR-Z0-9]{17}$/;
  var SERV_RE = /^[a-z]+_parts$/;
  var VWAG = { skoda_parts: 1, vw_parts: 1, audi_parts: 1, seat_parts: 1, cupra_parts: 1 };

  if (!/partslink24/.test(location.hostname)) return;
  if (window.__pl24Worker) { window.__pl24Worker.stop(); return; }

  function txt(s) { return String(s || "").replace(/\r/g, "").replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim(); }
  function esperar(ms) { return new Promise(function (ok) { setTimeout(ok, ms); }); }
  function sinSesion(t) { return /\bDemo\b|Become a partslink24 user|Log ?in to partslink24|Anmelden/i.test(t || ""); }

  function leer(url, listo) {          // carga en iframe oculto y espera a que el texto cumpla `listo`
    return new Promise(function (ok, mal) {
      var f = document.createElement("iframe");
      f.style.cssText = "position:fixed;left:-3000px;top:0;width:1200px;height:900px;";
      f.src = url;
      var t0 = Date.now();
      var iv = setInterval(function () {
        var t = "";
        try { t = f.contentDocument && f.contentDocument.body ? f.contentDocument.body.innerText : ""; } catch (e) {}
        if (sinSesion(t)) { clearInterval(iv); f.remove(); mal(new Error("pl24_sin_sesion")); return; }
        if (listo(t) || Date.now() - t0 > ESPERA_MS) {
          clearInterval(iv); f.remove();
          if (listo(t)) ok(t); else mal(new Error("pl24_timeout"));
        }
      }, 400);
      document.body.appendChild(f);
    });
  }

  function hits(t) {                    // bloques "Part no. / Description / MG / SG / Illustration"
    var i = t.indexOf("Search:"); if (i < 0) return [];
    var cuerpo = t.slice(i), fin = cuerpo.indexOf("\nMain group"); if (fin > 0) cuerpo = cuerpo.slice(0, fin);
    return cuerpo.split(/\nPart no\.\n/).slice(1).map(function (b) {
      var m = b.match(/^([^\n]+)\nDescription\n([\s\S]*?)\nMG\n(\w+)\nSG\n(\w+)(?:\nIllustration\n([^\n]+))?/);
      return m ? { numero: m[1].trim(), descripcion: m[2].replace(/\s+/g, " ").trim(),
                   mg: m[3], sg: m[4], ilustracion: (m[5] || "").trim() } : null;
    }).filter(Boolean).slice(0, 15);
  }

  function urlLamina(servicio, vin, ilu, mg) {
    var j = { path: "/p5vwag/extern/bom/vin?illustration=" + ilu + "&illustrationNormalized=" +
                    ilu.replace(/\D/g, "") + "&lang=en&maingroup=" + mg + "&serviceName=" + servicio + "&vin=" + vin,
              wid: "bomlist" };
    return "/pl24-app/" + servicio + "/" + vin + "/" + btoa(JSON.stringify(j));
  }

  async function procesar(job) {
    var vin = String(job.vin || "").replace(/^PL24:/, "").toUpperCase();
    var d = job.descripciones || {};
    var servicio = String(d.servicio || "");
    if (!VIN_RE.test(vin)) throw new Error("vin_invalido");
    if (!SERV_RE.test(servicio)) throw new Error("servicio_invalido");
    var terminos = (d.terminos || []).slice(0, 12);
    var base = "/pl24-app/" + servicio + "/" + vin + "/0/";
    var vehiculo = await leer(base + "vehicle", function (t) { return /Vehicle data/.test(t) && /Main group/.test(t); });
    var iv = vehiculo.indexOf("Vehicle data"), fv = vehiculo.indexOf("Main group");
    var out = { fuente: "Partslink24", vin: vin, servicio: servicio,
                vehiculo: txt(vehiculo.slice(iv, fv)).slice(0, 900), piezas: [] };
    var laminasLeidas = {};
    for (var k = 0; k < terminos.length; k++) {
      var tq = String(terminos[k].en || terminos[k].desc || "").replace(/[^\w\s,\-]/g, " ").trim().slice(0, 60);
      pintar("buscando " + tq);
      var res = { desc: terminos[k].desc || tq, busqueda: tq, hits: [], laminas: [] };
      if (tq) {
        var t = await leer(base + "search?q=" + encodeURIComponent(tq) + "&lang=en&desktop=true",
                           function (x) { return /Search:/.test(x) && (/Part no\./.test(x) || /No hits|no results/i.test(x)); });
        res.hits = hits(t);
        if (VWAG[servicio]) {
          // láminas de los hits que más se parecen al término (no las primeras de la lista)
          var pal = tq.toLowerCase().split(/[\s,]+/).filter(function (w) { return w.length > 2; });
          var puntuar = function (h) {
            var d = h.descripcion.toLowerCase(), sc = 0;
            pal.forEach(function (w, i) { if (d.indexOf(w) >= 0) sc += (d.indexOf(w) < 15 ? 3 : 1) * (i === 0 ? 2 : 1); });
            ["cleaner", "cleaning", "solution", "washer", "pump", "wiper", "holder", "housing", "hose",
             "contact", "grease", "adhesive", "clip", "screw", "bolt", "bracket", "grommet"].forEach(function (w) {
              if (d.indexOf(w) >= 0 && tq.toLowerCase().indexOf(w) < 0) sc -= 3;
            });
            return sc;
          };
          var ilus = [];
          res.hits.slice().sort(function (a, b) { return puntuar(b) - puntuar(a); }).forEach(function (h) {
            if (puntuar(h) > 0 && h.ilustracion && ilus.indexOf(h.ilustracion + "|" + h.mg) < 0)
              ilus.push(h.ilustracion + "|" + h.mg);
          });
          for (var u = 0; u < Math.min(ilus.length, 2); u++) {
            var p = ilus[u].split("|");
            if (!laminasLeidas[ilus[u]]) {
              var tl = await leer(urlLamina(servicio, vin, p[0], p[1]), function (x) {
                var i = x.indexOf("Pos.");      // listo cuando ya hay filas con números de parte
                return i >= 0 && /\b[0-9A-Z]{3} [0-9]{3} [0-9]{3}/.test(x.slice(i));
              });
              var i0 = tl.indexOf(p[0]);
              laminasLeidas[ilus[u]] = txt(tl.slice(i0 >= 0 ? i0 : 0)).slice(0, 4000);
            }
            res.laminas.push({ ilustracion: p[0], texto: laminasLeidas[ilus[u]] });
          }
        }
      }
      out.piezas.push(res);
    }
    return out;
  }

  /* ------------------------------- cola --------------------------------- */
  var head = { "apikey": ANON_KEY, "Authorization": "Bearer " + ANON_KEY,
               "Content-Type": "application/json", "Accept": "application/json" };
  function rest(path, opts) {
    opts = opts || {}; opts.headers = head; opts.credentials = "omit";
    return fetch(SUPABASE_URL + "/rest/v1/" + path, opts);
  }
  function marcar(id, patch) {
    return rest("catalog_job?id=eq." + id, { method: "PATCH",
      body: JSON.stringify(Object.assign({ updated_at: new Date().toISOString() }, patch)) });
  }
  var vivo = true, hechos = 0, fallos = 0, ocupado = false, estadoSesion = "ok", t0 = Date.now();
  function latido() {
    return rest("catalog_worker?id=eq." + LATIDO_ID, { method: "PATCH",
      body: JSON.stringify({ last_seen: new Date().toISOString(),
                             note: (estadoSesion === "ok" ? "" : "DEMO · ") + hechos + " ok / " + fallos + " err" }) })
      .catch(function () {});
  }
  function revisarSesion() {
    estadoSesion = sinSesion(document.body ? document.body.innerText : "") ? "demo" : "ok";
    if (estadoSesion !== "ok") pintar("SESIÓN CERRADA: iniciá sesión en esta pestaña");
  }

  function vuelta() {
    if (!vivo) return;
    revisarSesion();
    latido();
    if (!ocupado && Date.now() - t0 > RECARGA_MS) { location.reload(); return; }   // mantiene la sesión
    if (ocupado || estadoSesion !== "ok") { setTimeout(vuelta, POLL_MS); return; }
    rest("catalog_job?status=eq.pending&vin=like.PL24*&order=created_at.asc&limit=1")
      .then(function (r) { return r.json(); })
      .then(function (jobs) {
        if (!jobs || !jobs.length) return;
        var job = jobs[0];
        ocupado = true;
        return marcar(job.id, { status: "working" })
          .then(function () { return procesar(job); })
          .then(function (res) { hechos++; return marcar(job.id, { status: "done", result: res }); })
          .catch(function (e) {
            fallos++;
            var msg = String(e && e.message || e).slice(0, 200);
            if (msg === "pl24_sin_sesion") estadoSesion = "demo";
            return marcar(job.id, { status: "error", error: msg });
          })
          .then(function () { ocupado = false; pintar(""); });
      })
      .catch(function (e) { pintar("error de cola: " + e); })
      .then(function () { setTimeout(vuelta, POLL_MS); });
  }

  var caja = document.createElement("div");
  caja.style.cssText = "position:fixed;bottom:14px;right:14px;z-index:2147483647;background:#6a1b9a;color:#fff;" +
    "font:12px/1.5 system-ui,sans-serif;padding:8px 12px;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.35);cursor:pointer";
  caja.title = "Clic para apagar el worker de Partslink24";
  function pintar(msg) {
    caja.textContent = "Partslink24 worker · " + hechos + " ok · " + fallos + " err" + (msg ? " · " + msg : "");
  }
  caja.onclick = function () { window.__pl24Worker.stop(); };
  window.__pl24Worker = { stop: function () { vivo = false; caja.remove(); delete window.__pl24Worker; } };
  function montar() { if (document.body) { document.body.appendChild(caja); pintar("arrancando"); vuelta(); } else setTimeout(montar, 500); }
  setTimeout(montar, 3000);          // la app de Partslink24 tarda en dibujar
})();
