/* ===========================================================================
 * catalog_worker.js — worker de catalogo: VIN + descripciones -> piezas
 *
 * Corre DENTRO de una pestana de partsouq.com que abrio el dueno (Chrome real,
 * con la verificacion de Cloudflare ya resuelta a mano). Mismo patron que
 * avk_worker.js: el servidor MCP encola un trabajo en catalog_job, este worker
 * lo toma, navega el catalogo y escribe el resultado como TEXTO.
 *
 * Frontera (brief seccion 6): el bot de Telegram NO toca el navegador. Lo unico
 * que llega aca es un VIN validado y descripciones; las descripciones solo se
 * usan para elegir diagramas por palabras clave, jamas entran en una URL.
 *
 * La NAVEGACION es codigo; las DECISIONES las toma el mapa de palabras clave de
 * abajo. Si una descripcion no cae en el mapa, vuelve como "sin_mapa" con la
 * lista de grupos del catalogo, para que otro paso (IA chica sobre NOMBRES de
 * grupos, sin capturas) decida. El emparejado "faro derecho" <-> "HEADLIGHT RH"
 * lo hace el servidor, no este worker.
 *
 * Prototipo verificado el 18-oct-2026 contra el VIN del Montero
 * (MMBGUKS50PH001101): Body, car glass -> Headlamp -> 8301D438 HEADLIGHT (RH).
 * Solo se probo en catalogo Mitsubishi; otras marcas pueden tener otro arbol.
 *
 * Uso: python tools/build_catalog_worker.py  -> catalog_worker_bookmarklet.html
 * =========================================================================== */
(function () {
  var SUPABASE_URL = "__SUPABASE_URL__";
  var ANON_KEY     = "__SUPABASE_ANON_KEY__";

  var POLL_MS        = 5000;
  var PAUSA_MS       = 400;    // entre cargas de pagina, para no parecer un bot
  var MAX_DIAG_DESC  = 3;      // diagramas por descripcion
  var MAX_GRUPOS_DESC = 3;     // grupos que se recorren por descripcion
  var MAX_PAGINAS    = 6;      // paginas de diagramas por grupo
  var ESPERA_CARGA_MS = 25000;

  var VIN_RE = /^[A-HJ-NPR-Z0-9]{17}$/;

  /* ---- Mapa de palabras clave: espanol -> terminos del catalogo (ingles) ----
   * es:     regex sobre la descripcion (minusculas, sin tildes)
   * en:     terminos que se buscan en nombre y etiquetas de los diagramas
   * grupos: regex sobre el NOMBRE del grupo donde buscar primero            */
  var MAPA = [
    { es: /\b(faro|farol|foco)s?\b(?!.*(trasero|posterior))|luz delantera|headlamp/, en: ["headlamp", "headlight"], grupos: /body|electrical|lamp|light/i },
    { es: /(luz|faro|farol|stop|calavera|lampara).*(trasero|trasera|posterior)|(trasero|trasera|posterior).*(luz|faro|farol|stop)|calavera|stop\b/, en: ["rear exterior lamp", "rear combination", "tail", "stop light"], grupos: /body|electrical|lamp|light/i },
    { es: /(parachoque|paragolpe|bomper|bumper|defensa).*(trasero|trasera|posterior)|(trasero|trasera|posterior).*(parachoque|paragolpe|bomper|bumper|defensa)/, en: ["rear bumper"], grupos: /body/i },
    { es: /parachoque|paragolpe|bomper|bumper|defensa|cara de parachoque/, en: ["front bumper", "bumper"], grupos: /body/i },
    { es: /\bcapo\b|capot|hood/, en: ["hood"], grupos: /body/i },
    { es: /guardafango|guardabarro|guardalodo|aleta|fender/, en: ["fender", "front panel", "side panel"], grupos: /body/i },
    { es: /rejilla|parrilla|persiana|grille/, en: ["radiator grille", "grille"], grupos: /body/i },
    { es: /espejo|retrovisor/, en: ["rear view mirror", "mirror"], grupos: /body/i },
    { es: /limpiaparabrisas|limpia parabrisas|wiper|plumilla/, en: ["wiper"], grupos: /body|electrical/i },
    { es: /parabrisas|vidrio|luna|cristal/, en: ["windshield", "glass", "window"], grupos: /body/i },
    { es: /porton|baul|tapa trasera|compuerta|tailgate/, en: ["tailgate", "trunk"], grupos: /body/i },
    { es: /puerta|door/, en: ["door"], grupos: /body/i },
    { es: /moldura|cromad|emblema|insignia|ornamento|garnish/, en: ["ornament", "emblem", "garnish", "molding"], grupos: /body/i },
    { es: /radiador/, en: ["radiator", "cooling"], grupos: /cooling|engine|body/i },
    { es: /condensador/, en: ["condenser"], grupos: /heating|a\/c|air/i },
    { es: /amortiguador|resorte|suspension|brazo|rotula|terminal/, en: ["shock", "suspension", "arm", "spring"], grupos: /suspension|chassis|steering/i },
    { es: /freno|pastilla|disco|brake/, en: ["brake"], grupos: /brake/i }
  ];

  if (!/partsouq/.test(location.hostname) && !window.__CATALOG_TEST__) {
    alert("Este worker corre en una pestana de partsouq.com.");
    return;
  }
  if (window.__catalogWorker && !window.__CATALOG_TEST__) {
    window.__catalogWorker.stop();
    return;                  // segundo clic = apagar
  }

  function norm(s) {
    return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }
  function txt(el) { return el ? (el.textContent || "").replace(/\s+/g, " ").trim() : ""; }
  function esperar(ms) { return new Promise(function (ok) { setTimeout(ok, ms); }); }
  function desafio(doc) {
    return /just a moment|security verification|attention required/i.test((doc && doc.title) || "");
  }

  /* ------------------------------ parsers ------------------------------- */

  function parseGrupos(doc, base) {
    var vistos = {}, out = [];
    Array.prototype.forEach.call(doc.querySelectorAll("a[href*='groupId=']"), function (a) {
      var u = new URL(a.getAttribute("href"), base);
      if (u.searchParams.get("schemaId") || /\/diagram\//.test(u.pathname)) return;
      if (u.searchParams.get("page") != null) return;           // "Next"
      var id = u.searchParams.get("groupId"), nombre = txt(a);
      if (!id || !nombre || vistos[id] || /^login$|^register$/i.test(nombre)) return;
      vistos[id] = 1;
      out.push({ id: id, nombre: nombre });
    });
    return out;
  }

  function parseTarjetas(doc, base) {
    return Array.prototype.map.call(
      doc.querySelectorAll("a.part-catalog-diagram-card__link"), function (a) {
        return {
          nombre: txt(a.querySelector("h3")),
          tags: Array.prototype.map.call(
            a.querySelectorAll(".part-catalog-diagram-card__tags span"), txt),
          aplica: txt(a.querySelector(".part-catalog-diagram-card__body p")),
          url: new URL(a.getAttribute("href"), base).toString()
        };
      });
  }

  function siguiente(doc, base) {
    var n = Array.prototype.filter.call(doc.querySelectorAll("a"), function (a) {
      return txt(a) === "Next" && /page=\d/.test(a.getAttribute("href") || "");
    })[0];
    return n ? new URL(n.getAttribute("href"), base).toString() : null;
  }

  function parsePiezas(doc) {
    return Array.prototype.map.call(doc.querySelectorAll(".part-catalog-part-row"), function (r) {
      var badges = Array.prototype.map.call(
        r.querySelectorAll(".part-catalog-part-row__badge"), txt);
      function campo(re) {
        var b = badges.filter(function (x) { return re.test(x); })[0];
        return b ? b.replace(re, "").trim() : null;
      }
      var numEl = r.querySelector(".part-catalog-part-row__number");
      return {
        numero: numEl ? (numEl.getAttribute("data-part-number") || txt(numEl)) : null,
        descripcion: txt(r.querySelector(".part-catalog-part-row__summary strong")),
        callout: r.getAttribute("data-callout") || null,
        cantidad: campo(/^QTY:\s*/i),
        aplicabilidad: campo(/^APPLICABILITY:\s*/i),
        reemplazo: campo(/^REPLACEMENT:\s*/i),
        especificacion: (function () {
          var a = campo(/^APPLICABILITY:\s*/i) || "";
          var m = a.match(/SPECIFICATION:\s*(.*)$/i);
          return m ? m[1] : null;
        })()
      };
    }).filter(function (p) { return p.numero; });
  }

  function parseVehiculo(doc, finalUrl) {
    var t = doc.querySelector("table.part-catalog-vehicle-details");
    var u = new URL(finalUrl);
    var v = { catalogo: u.searchParams.get("catalogId"), titulo: txt(doc.querySelector("h1")) };
    if (t) {
      Array.prototype.forEach.call(t.querySelectorAll("td[data-label]"), function (td) {
        var k = td.getAttribute("data-label");
        if (k === "Region") v.region = txt(td);
        else if (k === "Year") v.anio = txt(td);
        else if (k === "Model") v.modelo = txt(td);
        else if (k === "Model code") v.codigo = txt(td);
      });
      v.detalles = Array.prototype.map.call(
        t.querySelectorAll(".part-catalog-vehicle-detail-badges span"), txt);
    }
    return v;
  }

  /* --------------------- carga de paginas (fetch o iframe) -------------- */

  function viaFetch(url) {
    return fetch(url, { credentials: "include" }).then(function (r) {
      return r.text().then(function (html) {
        var doc = new DOMParser().parseFromString(html, "text/html");
        if (r.status === 403 || desafio(doc)) return null;
        return { doc: doc, url: r.url || url };
      });
    }).catch(function () { return null; });
  }

  function viaIframe(url) {
    return new Promise(function (ok) {
      var f = document.createElement("iframe");
      f.style.cssText = "position:fixed;left:-3000px;top:0;width:1000px;height:800px;";
      f.src = url;
      var t0 = Date.now();
      var iv = setInterval(function () {
        var d = null;
        try { d = f.contentDocument; } catch (e) {}
        var listo = d && d.readyState === "complete" && !desafio(d) &&
                    d.querySelector(".part-catalog-browser, .part-catalog-page");
        if (listo || Date.now() - t0 > ESPERA_CARGA_MS) {
          clearInterval(iv);
          var res = listo ? { doc: d, url: f.contentWindow.location.href } : null;
          // El DOM del iframe se copia antes de destruirlo.
          if (res) {
            res.doc = new DOMParser().parseFromString(d.documentElement.outerHTML, "text/html");
          }
          f.remove();
          ok(res);
        }
      }, 300);
      document.body.appendChild(f);
    });
  }

  function cargar(url) {
    return viaFetch(url).then(function (r) {
      return r || viaIframe(url);
    }).then(function (r) {
      if (!r) throw new Error("cloudflare_challenge");
      return esperar(PAUSA_MS).then(function () { return r; });
    });
  }

  /* ------------------------------ decisiones ----------------------------- */

  function mapear(desc) {
    var d = norm(desc);
    for (var i = 0; i < MAPA.length; i++) {
      if (MAPA[i].es.test(d)) return MAPA[i];
    }
    return null;
  }

  function puntaje(tarjeta, terminos) {
    var s = 0, hay = norm(tarjeta.nombre + " " + tarjeta.tags.join(" "));
    terminos.forEach(function (t, i) {
      if (hay.indexOf(t) >= 0) s += (terminos.length - i) * 2 + (norm(tarjeta.nombre).indexOf(t) >= 0 ? 3 : 0);
    });
    return s;
  }

  async function tarjetasDeGrupo(base, grupo, cache) {
    if (cache[grupo.id]) return cache[grupo.id];
    var todas = [], u = new URL(base);
    u.searchParams.set("groupId", grupo.id);
    u.searchParams.set("page", "0");
    var url = u.toString();
    for (var p = 0; p < MAX_PAGINAS && url; p++) {
      var r = await cargar(url);
      Array.prototype.push.apply(todas, parseTarjetas(r.doc, r.url).map(function (t) {
        t.grupo = grupo.nombre; return t;
      }));
      url = siguiente(r.doc, r.url);
    }
    cache[grupo.id] = todas;
    return todas;
  }

  async function procesar(job) {
    var vin = String(job.vin || "").toUpperCase();
    if (!VIN_RE.test(vin)) throw new Error("vin_invalido");
    var descs = (job.descripciones || []).map(function (d) {
      return typeof d === "string" ? d : String(d.texto || "");
    }).filter(Boolean);
    if (!descs.length) throw new Error("sin_descripciones");

    var r0 = await cargar("/en/search/all?q=" + encodeURIComponent(vin));
    var grupos = parseGrupos(r0.doc, r0.url);
    if (!grupos.length) return procesarNuevo(vin, descs);     // catalogo rediseñado (nov-2026)
    var vehiculo = parseVehiculo(r0.doc, r0.url);

    var cacheGrupos = {}, diagramas = [], idxPorUrl = {}, pedidos = [];
    for (var i = 0; i < descs.length; i++) {
      var m = mapear(descs[i]);
      if (!m) { pedidos.push({ descripcion: descs[i], estado: "sin_mapa", diagramas: [] }); continue; }
      var candidatos = [];
      var gs = grupos.filter(function (g) { return m.grupos.test(g.nombre); }).slice(0, MAX_GRUPOS_DESC);
      for (var k = 0; k < gs.length; k++) {
        var ts = await tarjetasDeGrupo(r0.url, gs[k], cacheGrupos);
        ts.forEach(function (t) { candidatos.push({ t: t, s: puntaje(t, m.en) }); });
      }
      candidatos = candidatos.filter(function (c) { return c.s > 0; })
        .sort(function (a, b) { return b.s - a.s; }).slice(0, MAX_DIAG_DESC);
      if (!candidatos.length) { pedidos.push({ descripcion: descs[i], estado: "sin_diagrama", diagramas: [] }); continue; }
      var idxs = [];
      for (var c = 0; c < candidatos.length; c++) {
        var t = candidatos[c].t;
        if (idxPorUrl[t.url] == null) {
          var rd = await cargar(t.url);
          idxPorUrl[t.url] = diagramas.length;
          diagramas.push({ grupo: t.grupo, nombre: t.nombre, tags: t.tags,
                           aplica: t.aplica, piezas: parsePiezas(rd.doc) });
        }
        idxs.push(idxPorUrl[t.url]);
      }
      pedidos.push({ descripcion: descs[i], estado: "ok", diagramas: idxs });
    }
    return { fuente: "PartSouq", vin: vin, vehiculo: vehiculo, diagramas: diagramas,
             pedidos: pedidos,
             grupos: pedidos.some(function (p) { return p.estado === "sin_mapa"; })
               ? grupos.map(function (g) { return g.nombre; }) : undefined };
  }

  /* ------------- precios: numero de parte -> precio, stock, peso -------------
   * Trabajo tipo "precio" (28-nov-2026): job.numeros = ["8301D438", ...].
   * Lee la pagina de busqueda de cada numero (fetch mismo-origen; si Cloudflare,
   * iframe) y devuelve por numero: ofertas [{nombre, precio, stock, peso_kg, marca,
   * origen}], la mas barata con stock y la mas barata en general. */
  var NUM_RE = /^[A-Z0-9-]{4,20}$/;
  // marca de la oferta = fabricante del vehiculo -> genuino; cualquier otra (SANKEI, DEPO...) -> alterno
  var FABRICANTES = /^(toyota|lexus|nissan|infiniti|mitsubishi|mazda|honda|acura|hyundai|kia|subaru|suzuki|isuzu|daihatsu|ford|gm|chevrolet|mopar|chrysler|jeep|volkswagen|vw|audi|bmw|mini|mercedes|mercedes-benz|porsche|volvo|land rover|jaguar|peugeot|citroen|renault|genesis|ssangyong)\b/i;
  function parsePrecios(doc, numero) {
    var limpio = numero.replace(/[^A-Z0-9]/g, "");
    return Array.prototype.map.call(doc.querySelectorAll(".search-product-card"), function (c) {
      var campos = {};
      Array.prototype.forEach.call(c.querySelectorAll(".search-product-card-info-item"), function (it) {
        var k = txt(it.querySelector(".search-product-card-info-label")).toLowerCase();
        if (k) campos[k] = txt(it.querySelector(".search-product-card-info-value"));
      });
      var pm = txt(c.querySelector(".search-product-price")).replace(/,/g, "").match(/([\d.]+)\s*\$/);
      var peso = null;
      Object.keys(campos).forEach(function (k) {
        if (/weight/.test(k)) { var w = parseFloat(campos[k]); if (w > 0) peso = w; }
      });
      var stock = parseInt(campos["availability"], 10);
      return {
        nombre: txt(c.querySelector("h1, h2, h3, h4")),
        numero: (campos["part number"] || "").replace(/[^A-Z0-9]/gi, "").toUpperCase(),
        precio: pm ? parseFloat(pm[1]) : null,
        stock: isNaN(stock) ? null : stock,
        peso_kg: peso,
        marca: campos["make"] || null,
        origen: campos["made in"] || null
      };
    }).filter(function (o) { return o.precio != null && (!o.numero || o.numero === limpio); });
  }

  async function procesarPrecios(job) {
    var nums = (job.numeros || []).map(function (n) {
      return String(n || "").toUpperCase().replace(/\s+/g, "");
    }).filter(function (n) { return NUM_RE.test(n); }).slice(0, 25);
    if (!nums.length) throw new Error("sin_numeros");
    var out = [];
    for (var i = 0; i < nums.length; i++) {
      try { pintar("precio " + (i + 1) + "/" + nums.length + " " + nums[i]); } catch (e) {}
      var r = await cargarBusqueda("/en/search/all?q=" + encodeURIComponent(nums[i].replace(/-/g, "")));
      var ofertas = parsePrecios(r.doc, nums[i]).sort(function (a, b) { return a.precio - b.precio; });
      ofertas.forEach(function (o) { o.genuino = FABRICANTES.test(o.marca || ""); });
      var elegir = function (lista) {       // la mas barata con stock; si ninguna tiene, la mas barata
        return lista.filter(function (o) { return o.stock > 0; })[0] || lista[0] || null;
      };
      out.push({ numero: nums[i], encontrado: ofertas.length > 0,
                 genuino: elegir(ofertas.filter(function (o) { return o.genuino; })),
                 alterno: elegir(ofertas.filter(function (o) { return !o.genuino; })),
                 ofertas: ofertas.slice(0, 6) });
    }
    return { fuente: "PartSouq", tipo: "precio", moneda: "USD", resultados: out };
  }

  function cargarBusqueda(url) {      // la busqueda no tiene .part-catalog-*: otra condicion de "listo"
    return viaFetch(url).then(function (r) {
      if (r) return r;
      return new Promise(function (ok) {
        var f = document.createElement("iframe");
        f.style.cssText = "position:fixed;left:-3000px;top:0;width:1000px;height:800px;";
        f.src = url;
        var t0 = Date.now();
        var iv = setInterval(function () {
          var d = null;
          try { d = f.contentDocument; } catch (e) {}
          var listo = d && d.readyState === "complete" && !desafio(d) &&
                      (d.querySelector(".search-product-card") || /search result/i.test(d.title || ""));
          if (listo || Date.now() - t0 > ESPERA_CARGA_MS) {
            clearInterval(iv);
            var res = listo ? { doc: new DOMParser().parseFromString(d.documentElement.outerHTML, "text/html"),
                                url: url } : null;
            f.remove(); ok(res);
          }
        }, 300);
        document.body.appendChild(f);
      });
    }).then(function (r) {
      if (!r) throw new Error("cloudflare_challenge");
      return esperar(PAUSA_MS).then(function () { return r; });
    });
  }

  /* ------------- catalogo nuevo de PartSouq (rediseño nov-2026) -------------
   * VIN -> /en/search/all?q=VIN: tabla con filas tr[data-catalogs-row-link] (una por catalogo)
   *     -> /catalogs/<marca>/vehicle/vin/<vin>/<id>/ : links a TODOS los subgrupos
   *        ("BODY - RADIATOR GRILLE,HEADLAMP BEZEL (1)") + tabla .catalogs-details-table
   *     -> subgrupo: tarjetas a.catalogs-unit-card ("54010 CHASSIS ELECTRICAL - HEADLAMP")
   *     -> diagrama: tr.catalogs-part con a.catalogs-part-number[data-part-fields] (JSON). */
  var MAX_SUBGRUPOS = 3, MAX_UNIDADES = 2;

  function absoluto(href, base) { try { return new URL(href, base).pathname; } catch (e) { return null; } }

  function entradasVin(doc, base) {
    return Array.prototype.map.call(doc.querySelectorAll("tr[data-catalogs-row-link]"), function (tr) {
      var celda = function (k) { return txt(tr.querySelector('td[data-label="' + k + '"]')); };
      return { url: absoluto(tr.getAttribute("data-catalogs-row-link"), base),
               marca: celda("Brand"), region: celda("Region"), modelo: celda("Model"), detalle: celda("Details") };
    }).filter(function (e) { return e.url; });
  }

  function vehiculoNuevo(doc) {
    var v = { titulo: txt(doc.querySelector("h1")) };
    Array.prototype.forEach.call(doc.querySelectorAll(".catalogs-details-table tr"), function (tr) {
      var k = txt(tr.querySelector("th")), val = txt(tr.querySelector("td"));
      if (k && val && k !== "Detail") v[k] = val.slice(0, 400);
    });
    return v;
  }

  function subgrupos(doc, basePath) {
    var vistos = {};
    return Array.prototype.map.call(doc.querySelectorAll('a[href^="' + basePath + '"]'), function (a) {
      var u = a.getAttribute("href"), resto = u.slice(basePath.length).split("/").filter(Boolean);
      if (resto.length !== 2 || vistos[u]) return null;          // grupo/subgrupo/
      vistos[u] = 1;
      return { url: u, nombre: txt(a).replace(/\s*\(\d+\)\s*$/, "") };
    }).filter(Boolean);
  }

  function unidades(doc) {
    return Array.prototype.map.call(doc.querySelectorAll("a.catalogs-unit-card"), function (a) {
      return { url: a.getAttribute("href"), nombre: txt(a) };
    });
  }

  function piezasNuevas(doc) {
    return Array.prototype.map.call(doc.querySelectorAll("a.catalogs-part-number[data-part-number]"), function (a) {
      var campos = {};
      try { JSON.parse(a.getAttribute("data-part-fields") || "[]").forEach(function (f) { campos[f.key] = f.value; }); }
      catch (e) {}
      var nota = [campos.note, campos.producedFrom && ("desde " + campos.producedFrom),
                  campos.producedTo && ("hasta " + campos.producedTo)].filter(Boolean).join(" ");
      return { numero: a.getAttribute("data-part-number"), descripcion: campos.name || "",
               cantidad: campos.qty || null, aplicabilidad: nota || null,
               reemplazo: (campos.replacements && typeof campos.replacements === "string") ? campos.replacements : null,
               callout: a.getAttribute("data-pnc") || null };
    });
  }

  function puntajeNombre(nombre, m) {
    var n = norm(nombre), s = 0;
    m.en.forEach(function (t, i) { if (n.indexOf(t) >= 0) s += (m.en.length - i) * 2; });
    var grupo = nombre.split(" - ")[0] || "";
    if (s > 0 && m.grupos.test(grupo)) s += 1;
    return s;
  }

  async function procesarNuevo(vin, descs) {
    var r0 = await cargarBusqueda("/en/search/all?q=" + encodeURIComponent(vin));
    var entradas = entradasVin(r0.doc, location.origin + "/");
    if (!entradas.length) throw new Error("vin_sin_catalogo");
    var rv = await cargarBusqueda(entradas[0].url);            // la /select/... redirige al vehiculo
    var basePath = new URL(rv.url, location.origin).pathname;
    if (!/\/vehicle\//.test(basePath)) {                     // fetch sin url final: armarla
      basePath = entradas[0].url.replace("/select/", "/vehicle/").replace(/\/vin\/([^/]+)\/([^/]+)\/.*$/, "/vin/$1/$2/")
        .replace(/\/select\/[^/]+\/vin\//, "/vin/");
    }
    var subs = subgrupos(rv.doc, basePath);
    if (!subs.length) throw new Error("vin_sin_catalogo");
    var vehiculo = vehiculoNuevo(rv.doc);
    vehiculo.otras_entradas = entradas.slice(1).map(function (e) { return e.modelo; });

    var diagramas = [], idxPorUrl = {}, pedidos = [];
    for (var i = 0; i < descs.length; i++) {
      var m = mapear(descs[i]);
      if (!m) { pedidos.push({ descripcion: descs[i], estado: "sin_mapa", diagramas: [] }); continue; }
      var cand = subs.map(function (sg) { return { sg: sg, s: puntajeNombre(sg.nombre, m) }; })
        .filter(function (c) { return c.s > 0; }).sort(function (a, b) { return b.s - a.s; })
        .slice(0, MAX_SUBGRUPOS);
      if (!cand.length) { pedidos.push({ descripcion: descs[i], estado: "sin_diagrama", diagramas: [] }); continue; }
      var idxs = [];
      for (var c = 0; c < cand.length; c++) {
        var rs = await cargarBusqueda(cand[c].sg.url);
        var us = unidades(rs.doc).slice(0, MAX_UNIDADES);
        for (var u = 0; u < us.length; u++) {
          if (idxPorUrl[us[u].url] == null) {
            var rd = await cargarBusqueda(us[u].url);
            idxPorUrl[us[u].url] = diagramas.length;
            diagramas.push({ grupo: cand[c].sg.nombre, nombre: us[u].nombre, piezas: piezasNuevas(rd.doc) });
          }
          idxs.push(idxPorUrl[us[u].url]);
        }
      }
      pedidos.push({ descripcion: descs[i], estado: idxs.length ? "ok" : "sin_diagrama", diagramas: idxs });
    }
    return { fuente: "PartSouq", vin: vin, vehiculo: vehiculo, diagramas: diagramas, pedidos: pedidos,
             grupos: pedidos.some(function (p) { return p.estado !== "ok"; })
               ? subs.map(function (g) { return g.nombre; }) : undefined };
  }

  /* ---- Gancho de prueba: expone parsers sin arrancar la cola ---- */
  if (window.__CATALOG_TEST__) {
    window.__catalogParsers = { parseGrupos: parseGrupos, parseTarjetas: parseTarjetas,
      parsePiezas: parsePiezas, parseVehiculo: parseVehiculo, siguiente: siguiente,
      parsePrecios: parsePrecios, procesarPrecios: procesarPrecios, procesarNuevo: procesarNuevo,
      entradasVin: entradasVin, subgrupos: subgrupos, unidades: unidades, piezasNuevas: piezasNuevas,
      mapear: mapear, puntaje: puntaje, procesar: procesar };
    return;
  }

  /* ------------------------------- cola --------------------------------- */

  var head = { "apikey": ANON_KEY, "Authorization": "Bearer " + ANON_KEY,
               "Content-Type": "application/json", "Accept": "application/json" };

  function rest(path, opts) {
    opts = opts || {};
    opts.headers = head;
    opts.credentials = "omit";           // no arrastrar cookies de PartSouq a Supabase
    return fetch(SUPABASE_URL + "/rest/v1/" + path, opts);
  }
  function marcar(id, patch) {
    return rest("catalog_job?id=eq." + id, { method: "PATCH",
      body: JSON.stringify(Object.assign({ updated_at: new Date().toISOString() }, patch)) });
  }
  var vivo = true, hechos = 0, fallos = 0, ocupado = false;
  function latido(nota) {
    return rest("catalog_worker?id=eq.1", { method: "PATCH",
      body: JSON.stringify({ last_seen: new Date().toISOString(), note: nota || null }) })
      .catch(function () {});
  }

  function vuelta() {
    if (!vivo) return;
    latido(hechos + " ok / " + fallos + " err");
    if (ocupado) { setTimeout(vuelta, POLL_MS); return; }
    rest("catalog_job?status=eq.pending&order=created_at.asc&limit=1")
      .then(function (r) { return r.json(); })
      .then(function (jobs) {
        if (!jobs || !jobs.length) return;
        var job = jobs[0];
        ocupado = true;
        // Trabajo de precios: vin = "PRECIO" y descripciones = {numeros: [...]} (sin migracion nueva)
        var esPrecio = job.vin === "PRECIO";
        pintar(esPrecio ? "precios" : "buscando " + job.vin);
        return marcar(job.id, { status: "working" })
          .then(function () {
            return esPrecio ? procesarPrecios({ numeros: (job.descripciones || {}).numeros }) : procesar(job);
          })
          .then(function (res) { hechos++; return marcar(job.id, { status: "done", result: res }); })
          .catch(function (e) {
            fallos++;
            var msg = String(e && e.message || e).slice(0, 200);
            if (msg === "cloudflare_challenge") pintar("Cloudflare pidio verificacion: resolvela en esta pestana");
            return marcar(job.id, { status: "error", error: msg });
          })
          .then(function () { ocupado = false; pintar(""); });
      })
      .catch(function (e) { pintar("error de cola: " + e); })
      .then(function () { setTimeout(vuelta, POLL_MS); });
  }

  var caja = document.createElement("div");
  caja.style.cssText = "position:fixed;bottom:14px;right:14px;z-index:2147483647;" +
    "background:#0d47a1;color:#fff;font:12px/1.5 system-ui,sans-serif;padding:8px 12px;" +
    "border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.35);cursor:pointer";
  caja.title = "Clic para apagar el worker de catalogo";
  document.body.appendChild(caja);
  function pintar(msg) {
    caja.textContent = "Catalogo worker · " + hechos + " ok · " + fallos + " err" + (msg ? " · " + msg : "");
  }
  caja.onclick = function () { window.__catalogWorker.stop(); };
  window.__catalogWorker = { stop: function () {
    vivo = false; latido("apagado"); caja.remove(); delete window.__catalogWorker; } };

  pintar("arrancando");
  vuelta();
})();
