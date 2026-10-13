/* ===========================================================================
 * avk_worker.js — worker de precios AVK
 *
 * Corre DENTRO de una pestana de avkparts.lt que abrio el dueno. Esa es toda
 * la idea: el fetch sale del mismo navegador, con las mismas cookies y la
 * misma huella que el dueno navegando a mano, asi que Cloudflare no lo
 * distingue de una busqueda normal. Cualquier cliente de afuera (Playwright,
 * el panel de Claude, httpx) se come el desafio. Ver brief seccion 5.
 *
 * El bot de Telegram NO llega hasta aca. El servidor MCP encola un numero de
 * parte; este worker solo ve ese numero. Ver brief seccion 6.
 *
 * Uso: se arma con  python tools/build_avk_worker.py  (mete URL y anon key
 * desde .env) y queda un bookmarklet en avk_worker_bookmarklet.html.
 * =========================================================================== */
(function () {
  var SUPABASE_URL = "__SUPABASE_URL__";
  var ANON_KEY     = "__SUPABASE_ANON_KEY__";

  var POLL_MS      = 5000;   // Chrome frena los timers de pestanas de fondo a
                             // ~1/minuto. Con la pestana visible son 5 s.
  var LOTE         = 5;      // trabajos por vuelta
  var PAUSA_MS     = 700;    // entre busquedas, para no parecer un bot

  if (!/avkparts/.test(location.hostname)) {
    alert("Este worker corre en una pestana de avkparts.lt.");
    return;
  }
  if (window.__avkWorker) {
    window.__avkWorker.stop();
    return;                  // segundo clic = apagar
  }

  // Codigos de grupo de fabricante = pieza original. Los independientes (TYC,
  // DEPOT, AYFAR...) son alternos. Sin esto AVK entero se clasifica mal:
  // "PSA E" no dice "OEM" por ningun lado pero es Peugeot-Citroen original.
  var GENUINO = ["PSA", "FCA", "VAG", "BMW", "MERCEDES", "VOLVO", "JLR", "OPEL",
                 "FORD", "TOYOTA", "NISSAN", "HONDA", "HYUNDAI", "KIA", "RENAULT"];

  var head = {
    "apikey":        ANON_KEY,
    "Authorization": "Bearer " + ANON_KEY,
    "Content-Type":  "application/json",
    "Accept":        "application/json"
  };

  function rest(path, opts) {
    opts = opts || {};
    opts.headers = head;
    // credentials omit: la llamada a Supabase no debe arrastrar cookies de AVK.
    opts.credentials = "omit";
    return fetch(SUPABASE_URL + "/rest/v1/" + path, opts);
  }

  function calidadPorNombre(provider) {
    var p = (provider || "").toUpperCase();
    for (var i = 0; i < GENUINO.length; i++) {
      if (p.indexOf(GENUINO[i]) === 0) return "genuino";
    }
    return "alterno";
  }

  function parsear(html) {
    var doc = new DOMParser().parseFromString(html, "text/html");
    if (/just a moment|security verification/i.test(doc.title || "")) {
      return { challenge: true };
    }

    // Peso real de la pieza: AVK lo pone en "More info: ... | 0.05 kg".
    // Vale oro: para una parte europea reemplaza la estimacion estadistica
    // por el dato del proveedor.
    var mp = (doc.body ? doc.body.textContent : "").match(/\|\s*([\d]+[.,]?[\d]*)\s*kg/i);
    var peso = mp ? parseFloat(mp[1].replace(",", ".")) : null;

    // La pagina separa en dos bloques: arriba los proveedores originales,
    // y bajo "Original part analogues and related parts" los alternos.
    // Clasificar por seccion es mucho mas fiable que adivinar por el nombre
    // del proveedor: "PSA E" es original y no lo dice por ningun lado.
    var corte = null;
    var hs = doc.querySelectorAll("h1,h2,h3,h4,h5,div,p,span");
    for (var i = 0; i < hs.length; i++) {
      // El corte tiene que ser el TITULO, no un contenedor que envuelva las
      // tablas: si envuelve, compareDocumentPosition dice "contenido por" y
      // todas las filas quedarian marcadas como alternas.
      if (/analogues?\s+and\s+related|analogues/i.test(hs[i].textContent || "") &&
          (hs[i].textContent || "").length < 120 &&
          !hs[i].querySelector("table")) { corte = hs[i]; break; }
    }
    function esAlterno(fila) {
      if (!corte) return null;
      return !!(corte.compareDocumentPosition(fila) & Node.DOCUMENT_POSITION_FOLLOWING);
    }

    function num(t) {
      if (!t) return null;
      var m = t.match(/€?\s*([\d]{1,3}(?:,[\d]{3})*(?:\.[\d]+)?|[\d]+(?:\.[\d]+)?)/);
      if (!m) return null;
      // "€81.85" no es 8185: la coma separa miles, el punto es decimal.
      return parseFloat(m[1].replace(/,/g, ""));
    }

    var ofertas = [];

    // --- Camino 1: tabla de verdad, mapeando por el ENCABEZADO -------------
    // Los indices de columna se leen de los titulos ("Supplier", "Price
    // excluding VAT"...), no se cuentan a mano: si AVK agrega una columna,
    // esto sigue funcionando.
    Array.prototype.forEach.call(doc.querySelectorAll("table"), function (tb) {
      var idx = null;
      Array.prototype.forEach.call(tb.querySelectorAll("tr"), function (tr) {
        var celdas = tr.querySelectorAll("th,td");
        if (!celdas.length) return;
        var textos = Array.prototype.map.call(celdas, function (c) {
          return (c.textContent || "").trim();
        });

        if (!idx) {
          var cand = {};
          textos.forEach(function (t, i) {
            if (/supplier/i.test(t))              cand.prov = i;
            else if (/^code/i.test(t))            cand.code = i;
            else if (/delivery/i.test(t))         cand.lead = i;
            else if (/excluding\s*vat/i.test(t))  cand.neto = i;
            else if (/with\s*vat/i.test(t))       cand.con  = i;
          });
          if (cand.prov != null && cand.neto != null) { idx = cand; return; }
        }
        if (!idx) return;

        var neto = num(textos[idx.neto]);
        if (neto == null) return;                       // fila sin precio
        var prov = (textos[idx.prov] || "").trim();
        if (!prov) return;
        ofertas.push({
          provider:        prov,
          code:            idx.code != null ? textos[idx.code] : null,
          price_eur:       neto,
          price_gross_eur: idx.con  != null ? num(textos[idx.con]) : null,
          lead:            idx.lead != null ? textos[idx.lead].replace(/\s+/g, " ") : null,
          calidad:         esAlterno(tr) === true ? "alterno"
                         : esAlterno(tr) === false ? "genuino"
                         : calidadPorNombre(prov)
        });
      });
    });

    // --- Camino 2: la estructura div de la busqueda masiva -----------------
    if (!ofertas.length) {
      doc.querySelectorAll(".item").forEach(function (item) {
        var pe = item.querySelector(".column_provider");
        var neto = num(item.querySelector(".column_price_no_tax")
                    ? item.querySelector(".column_price_no_tax").textContent : "");
        var con  = num(item.querySelector(".column_price_with_tax")
                    ? item.querySelector(".column_price_with_tax").textContent : "");
        if (neto == null && con == null) return;
        var prov = pe ? pe.textContent.trim() : "";
        var lead = (item.textContent.match(/(\d+\s*-\s*\d+\s*d\.?\s*d\.?|\d+\s*-\s*\d+\s*days)/i) || [])[1] || null;
        ofertas.push({
          provider:        prov,
          code:            null,
          price_eur:       neto,
          price_gross_eur: con,
          lead:            lead ? lead.replace(/\s+/g, " ") : null,
          calidad:         esAlterno(item) === true ? "alterno"
                         : esAlterno(item) === false ? "genuino"
                         : calidadPorNombre(prov)
        });
      });
    }

    return { ofertas: ofertas, peso_kg: peso };
  }

  function buscar(oe) {
    // El OE ya viene saneado del lado del servidor, pero encodeURIComponent
    // igual: lo que entra en una URL no se construye a confianza.
    return fetch("/search/" + encodeURIComponent(oe), { credentials: "include" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.text();
      })
      .then(parsear);
  }

  function marcar(id, patch) {
    return rest("avk_job?id=eq." + id, {
      method: "PATCH",
      body: JSON.stringify(Object.assign({ updated_at: new Date().toISOString() }, patch))
    });
  }

  var vivo = true, hechos = 0, fallos = 0;

  function latido(nota) {
    return rest("avk_worker?id=eq.1", {
      method: "PATCH",
      body: JSON.stringify({ last_seen: new Date().toISOString(), note: nota || null })
    }).catch(function () {});
  }

  function vuelta() {
    if (!vivo) return;
    latido(hechos + " ok / " + fallos + " err");
    rest("avk_job?status=eq.pending&order=created_at.asc&limit=" + LOTE)
      .then(function (r) { return r.json(); })
      .then(function (jobs) {
        if (!jobs || !jobs.length) return;
        return jobs.reduce(function (cadena, job) {
          return cadena.then(function () {
            if (!vivo) return;
            return marcar(job.id, { status: "working" })
              .then(function () { return buscar(job.oe); })
              .then(function (res) {
                if (res.challenge) {
                  fallos++;
                  pintar("Cloudflare pidio verificacion — abri la pestana y resolvela");
                  return marcar(job.id, { status: "error", error: "cloudflare_challenge" });
                }
                hechos++;
                return marcar(job.id, { status: "done", result: res.ofertas });
              })
              .catch(function (e) {
                fallos++;
                return marcar(job.id, { status: "error", error: String(e).slice(0, 200) });
              })
              .then(function () {
                return new Promise(function (ok) { setTimeout(ok, PAUSA_MS); });
              });
          });
        }, Promise.resolve());
      })
      .catch(function (e) { pintar("error de cola: " + e); })
      .then(function () { setTimeout(vuelta, POLL_MS); });
  }

  // Cartelito, para que se vea de un vistazo que sigue vivo.
  var caja = document.createElement("div");
  caja.style.cssText = "position:fixed;bottom:14px;right:14px;z-index:2147483647;" +
    "background:#1b5e20;color:#fff;font:12px/1.5 system-ui,sans-serif;padding:8px 12px;" +
    "border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.35);cursor:pointer";
  caja.title = "Clic para apagar el worker AVK";
  document.body.appendChild(caja);
  function pintar(msg) {
    caja.textContent = "AVK worker · " + hechos + " ok · " + fallos + " err" +
                       (msg ? " · " + msg : "");
  }
  caja.onclick = function () { window.__avkWorker.stop(); };

  window.__avkWorker = {
    stop: function () {
      vivo = false;
      latido("apagado");
      caja.remove();
      delete window.__avkWorker;
    }
  };

  pintar("arrancando");
  vuelta();
})();
