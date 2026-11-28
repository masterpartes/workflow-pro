# PLAN MASTER PARTES — memoria de la construcción (fuente de verdad)

Leer ESTO primero en cada sesión. Actualizar la sección "Estado" al terminar cada paso.
Acordado con Alejandro el 25-nov-2026. Reemplaza los planes de los handoffs anteriores.

## Objetivo
Liberar a Alejandro (trabaja en oficina; Master Partes solo temprano y de noche):
1. Santiago cotiza solo mientras Alejandro no está, con el MISMO agente y método de Alejandro.
2. Un solo registro por parte reemplaza DESPACHO / PROVINCIAS / FACTURAS POR COBRAR.
3. Saber cuánto costó, cuánto se facturó y el margen bruto.

## Decisiones (no reabrir)
- Base: **Supabase**. Una fila por parte = `OrderItem` (+ cabecera `Order`). Vistas: `v_linea`,
  `v_por_despachar`, `v_llegadas`, `v_por_cobrar`, `v_alertas`, `v_margen_mes` (migración 010).
- Pantalla de trabajo: página **Líneas** del dashboard (grilla tipo Excel, pegar desde Excel).
- Importar solo lo pendiente y todo lo nuevo; no migrar historia.
- Vence = 20 días hábiles salvo que el pedido/aseguradora diga otra cosa.
- **Santiago lanza el agente completo** (skills + Chrome de Alejandro, Partslink24 incluido) desde
  Telegram. Entrada amplia: captura, JSON Inpart, chat Orgu, foto + VIN, texto. Sin formularios.
- SIPO: el agente lee las subastas del correo y aplica `reglas_subastas.json`; Santiago no carga datos.
- Salida para Santiago: costo puesto en Quito + sugerido, genuino y alterno, ⚠ en lo problemático.
  Tabla/imagen para el cliente cuando la pida (`render_presupuesto`).
- Alejandro: mismo formato de sus skills; él decide precio. Corridas mañana y noche las lanza él.
- IA solo donde hace falta; cada pedido de Santiago es una corrida nueva y corta (Sonnet), Pro.
- Adjudicación: llega por captura → las líneas cotizadas pasan a filas de pedido con precio adjudicado.
- Panatlantic: captura de la tabla de despacho + Word con las facturas de proveedor.
- Contabilidad: módulo aparte (otro agente); acá solo costo / facturado / margen y un export.
- Navegador: ventana de Chrome dedicada con pestañas fijadas (workers); el agente nunca las toca.
- Nunca: escribir contraseñas, resolver Cloudflare/CAPTCHA, enviar ofertas, pagar.

## Pasos
| # | Paso | Estado |
|---|---|---|
| 0 | Limpieza: commit, 009, retirar legado, rotar Inpart | parcial (010 hecho; 009 sin aplicar; legado y rotación pendientes) |
| 1 | Tabla única + página Líneas + vistas + import pendientes | código y base LISTOS; **import pendiente (Alejandro)** |
| 2 | Agente de Santiago (REDISEÑO 28-nov: pipeline + IA mínima, ver Estado): carpeta `C:\MasterPartesBot\agente`, carril en el relay, cola, imagen cliente | código LISTO; **setup de laptop y prueba pendientes** |
| 3 | Workers: userscript con AVK + PartSouq catálogo + PartSouq precio/stock/peso; latidos y alertas | código LISTO 28-nov (tools `catalogo_partsouq`, `precio_partsouq`; alertas en el relay); **falta instalar Tampermonkey + userscript y probar** |
| 4 | Guardar líneas de cotización (de Alejandro y de Santiago) + precio ofertado/adjudicado | pendiente |
| 5 | Adjudicación por captura → filas de pedido; despacho Panatlantic (tabla + Word facturas) | pendiente |
| 6 | Alertas a Santiago por Telegram (atrasados, problema, llegó sin destino) — sin IA | pendiente |
| 7 | Margen: export para el agente contable | pendiente (vista `v_margen_mes` ya existe) |
| 8 | Seguridad: login dashboard, service_role solo en MCP | pendiente |

## Estado (actualizar)
- 25-nov: migración 010 aplicada; Líneas publicada (Vercel); `IMPORTAR_PENDIENTES.xlsx` en
  `workflow-pro\Claude outputs\` para revisar y pegar. `render_presupuesto` en el MCP.
  Relay con carril agente (`telegram_relay.py`, backup `.bak-2026-11-25`).
- 28-nov: REVISADO y CONFIRMADO el diseño del paso 2: Telegram solo releva; toda la IA corre en la
  laptop (`claude -p --chrome`, login Pro, Chrome y cuentas de Alejandro, Partslink24 incluido) y la
  respuesta vuelve como tabla/imagen. Descartado: relay WhatsApp→app de escritorio (automatizar la app),
  cuenta propia para Santiago (no tiene accesos a proveedores), API key (apaga el control de Chrome).
  Ojo: desde jun-2026 las corridas `claude -p` usan un crédito aparte del plan (≈ cuota del plan) →
  medir con /uso y `agente\historial` la primera semana; carriles sin IA primero.
- 28-nov tarde: setup del agente: Pillow instalado; Claude Code re-logueado con Pro (estaba en
  "API Usage Billing"); `claude --chrome` conectado y probado (PartSouq por VIN, sin diálogos);
  tabla de fuentes por marca en `agente\CLAUDE.md`; Chrome "Always keep active" configurado.
  `MODO_REMOTO.bat` (abre ventana de trabajo, sin suspensión, arranca bot) y `MODO_NORMAL.bat`.
- 28-nov 17:10: PRIMERA CORRIDA REAL por Telegram OK: Montero MMBGUKS50PH001101 faro der →
  8301D438 correcto, ~2 min, 26 turnos, ≈0.62 USD equiv del crédito de automatización.
  Arreglos: 409 = plugin de Telegram de Channels cargado en cada `claude -p` → desactivado
  (enabledPlugins) en agente\ y en la raíz; faltaba permiso `quote_quito_cost` (costo con precio
  visto en el navegador) → agregado; salida en texto plano; MODO_REMOTO en una sola ventana +
  pestaña de Telegram. CLAVE DE COSTO: con workers vivos (paso 3) la búsqueda por VIN es 1
  llamada en vez de ~20 pasos de navegador → el paso 3 pasa a ser prioridad.
- 28-nov noche: paso 3 en código: worker PartSouq hace también precios (vin="PRECIO", sin migración);
  `catalogo_partsouq` devuelve diagramas crudos (el agente empareja, sin 2ª corrida de IA);
  userscript v2 solo arranca en pestañas `#mpworker` (las abre MODO_REMOTO) y no en iframes;
  relay avisa por Telegram si un worker pasa 3 min sin latido (relay_config "alertas" o el 1er usuario).
  Envío (shipping) de PartSouq NO incluido: requiere manipular el carrito; queda para después.
- 28-nov 17:45: workers vivos (Tampermonkey + userscript v3). PartSouq rediseñó el catálogo en
  nov → worker reescrito (VIN → entradas → vehículo → subgrupo → diagrama; probado: 3 piezas en 12 s).
  Costo por pedido: 0.62 → 0.47 → 0.30 USD (7 turnos, 30 s). Piso ≈ 0.25–0.30 por corrida (prompt de
  Claude Code + herramientas de Chrome se escriben en caché en cada corrida nueva; si hay otra
  corrida dentro de 1 h se reusa). Pedidos con varias piezas reparten ese piso.
- 28-nov 18:08: DECISIÓN DE COSTO (medido en la laptop). `claude -p` normal arrastra ~93.000 tokens
  de arranque (≈1.9 ¢ en Haiku solo por arrancar; el agente con Chrome ≈ 25–30 ¢ de piso). Con
  `--system-prompt "…" --tools "" --strict-mcp-config --disable-slash-commands --setting-sources local`
  desde una carpeta vacía (C:\MasterPartesBot\vacio): 626 tokens, 0.013 ¢. → REDISEÑO del carril de
  Santiago: PIPELINE en código (correo por IMAP, workers PartSouq + tascaparts/oempartsonline,
  quote_list, formato fijo) + 1–2 llamadas mínimas de IA (leer captura con imagen por stream-json;
  emparejar pieza↔diagrama). Objetivo ≈ 1 ¢ por pedido. El agente completo queda para Alejandro y
  como último recurso. Pendiente decisión de Alejandro: Partslink24 (europeos).
- 28-nov 18:40: Partslink24 worker (userscript v5, latido id=2, alerta DEMO, recarga c/10 min) devolvió
  6VA 845 011 K NVB en 16 s. Corrida por Telegram cortada: "5-hour limit / out of usage credits" (esta
  sesión de construcción en Opus consume la misma cuota). REFERENCIA DE CALIDAD (corrida de escritorio
  con skills, 30 acciones): parabrisas 6VA845011K NVB €229.74 AVK 13.95 kg; "caucho" = 6VA823723 €4.17
  ⚠ (vidrio pegado; adhesivo D 169 300 M2 + primer D 009 200 02); sin alterno en AVK; Caso Exprés.
  El pipeline tiene que llegar a esto. PRÓXIMO: pipeline (llamadas mínimas: leer captura, emparejar con
  texto de lámina) + AVK precio por número; sesiones de construcción cortas.
- 28-nov: verificado: 0 líneas importadas; el agente nunca corrió (no hay `agente\historial`);
  bot sin uso desde 18-oct; workers AVK/catálogo sin latido desde 28/29-oct.

## Archivos clave
- `workflow-pro\supabase\migrations\010_lineas.sql`, `src\pages\Lineas.jsx`
- `workflow-pro\mcp_server\server.py` (tools), `tools\shared\presupuesto.py`
- `C:\MasterPartesBot\agente\` (CLAUDE.md, .claude\skills, settings), `relay\telegram_relay.py`
- `workflow-pro\INVENTARIO_2026-11-25.md` (qué fuentes existen y dónde)
- `PUBLICAR.bat` (push → Vercel; el push solo funciona desde la laptop)


## PRÓXIMA SESIÓN — empezar acá (reescrito 28-nov 20:30)

**Objetivo:** carril remoto de Santiago alineado con el proceso de escritorio de Alejandro. NO tocar la
skill `masterpartes-cotizacion` ni el proceso de escritorio (Alejandro filtra SIPO, pasa el link de la
carpeta, el agente cotiza ~10 subastas en ~10 min: eso queda igual). Cualquier cambio a una skill = mostrar
el diff y esperar el OK. Escala real: 10+ subastas de 20+ piezas por día (100+ piezas).

**Diseño acordado:** motor en código (`C:\MasterPartesBot\relay\pipeline.py`) con la SUBASTA como unidad:
1 lectura del pedido (Haiku) → catálogo por VIN (worker) → 1 emparejado por subasta (Sonnet, solo el texto de
lámina relevante) → precios en lote (PartSouq / AVK bulk / eBay API en paralelo) → tabla. Las líneas con ⚠
(variantes, PR, pieza "más cercana" como el caucho del Skoda) pasan al agente completo con las skills. Nada se
descarta: lo difícil va por la vía lenta o "⚠ necesita a Alejandro".

**Hecho (28-nov, Sonnet/Opus):** `relay\ia_min.py` (llamada mínima, imagen por stream-json), `relay\pipeline.py`
(leer → ruteo WMI PartSouq/Partslink24 → emparejar con validación del número contra el texto → precios
PartSouq o AVK + eBay `ebay_service.search_part` en paralelo, regla eBay genuino < 40 % → ⚠ → costo Quito con
`quote_quito_cost` → tabla §3), `relay\test_pipeline.py` (simulado), `PROBAR_PIPELINE.bat` (Montero + Skoda,
o arrastrar una captura encima), carril en `telegram_relay.py` (`correr_pedido`, `/agente <pedido>` fuerza el
agente; backup `.bak-2026-11-28`). **Carril APAGADO**: se prende con `"pipeline": true` en `relay_config.json`.

**Medido en la laptop:** IA 0.1–0.8 ¢ por pedido corto (Skoda 3.8 ¢: demasiado texto de Partslink24 al
emparejar). Etapas: leer 2.5 s, emparejar 2–6 s, precios 4–13 s, catálogo 15–24 s… pero 127 s cuando la
pestaña del worker estuvo en segundo plano (Chrome frena timers de pestañas ocultas a ~1/min).
Montero OK (8301D438, reemplazo 26010W570P, sin stock; eBay genuino $430 rechazado por la regla del 40 %).
Skoda: número 6VA 845 011 K NVB OK; AVK no lo encuentra con NVB → arreglado (busca también 6VA845011K),
SIN PROBAR en la laptop; caucho sin número (correcto que vaya ⚠ al agente: en escritorio fue juicio, vidrio
pegado → 6VA823723 sello del panel frontal + adhesivo D 169 300 M2 + primer D 009 200 02).

**Pendiente, en este orden (probar cada uno con PROBAR_PIPELINE.bat antes del siguiente):**
1. **Chrome dedicado para los workers** (Alejandro DIJO QUE SÍ): `MODO_REMOTO.bat` abre un Chrome aparte con
   `--user-data-dir=C:\MasterPartesBot\chrome_trabajo --disable-background-timer-throttling
   --disable-renderer-backgrounding --disable-backgrounding-occluded-windows` y las pestañas `#mpworker`.
   Alejandro inicia sesión UNA vez en ese perfil (Partslink24, AVK, correo, Telegram web) e instala ahí
   Tampermonkey + `masterpartes_worker.user.js` (y la extensión de Claude in Chrome si el agente la usa ahí;
   verificar que `claude --chrome` se conecte a ese perfil, si no, decidir con él). Correr el .bat dos
   veces con 10 min de diferencia: catálogo Skoda debe quedar < 30 s las dos.
2. **Verificar AVK en la laptop**: Skoda debe dar parabrisas €229.74. Revisar clasificación genuino/alterno
   (corrida anterior dio €300.87 "genuino" y €229.74 "alterno"; escritorio: €229.74 genuino, sin alterno):
   mirar las ofertas en `avk_job` (Supabase, id ≥ 245: provider, calidad) y corregir `tools/avk_worker.js`.
   OJO: el shell de la VM no llega a Supabase; usar la tool MCP `db_select` o la laptop.
3. **AVK bulk en el worker**: hoy una página por número. Copiar el método de `avk_bookmarklets.html`
   (modal "Bulk parts search": textarea con un número por línea → botón search → resultados en
   `.bulk_single_item` / `.single_bulk_code` / `.item` `.column_provider` `.column_price_no_tax`). En la
   pestaña de AVK (Cloudflare pasado) mirar con Claude in Chrome qué request hace el bulk (read_network_requests)
   para hacerlo por fetch; si no, manejar el modal desde el worker. Genuino/alterno en bulk = por código de
   proveedor (lista GENUINO del worker: VAG, PSA, BMW…), validar contra una búsqueda individual.
   `avk_live.lookup_avk` mandar UN job con todos los números.
4. **Catálogo por subasta**: una lectura por VIN para todas las piezas; láminas compartidas una sola vez;
   al emparejar mandar solo las láminas relevantes (recortar texto → baja el 3.8 ¢). Partslink24 es una sola
   sesión: secuencial.
5. **Prueba de 20 piezas**: Alejandro elige una subasta ya cotizada en escritorio (con su resultado) →
   correrla por el pipeline y comparar línea por línea (número, precio, ⚠). Medir tiempo y costo.
6. **Vía ⚠ al agente**: las líneas ⚠ del pipeline van a `correr_agente` con el contexto ya resuelto (VIN,
   vehículo, números hallados, solo las piezas ⚠), respuesta fusionada en una tabla.
7. Después: worker tascaparts / oempartsonline (Ford US, Honda, GM, Mopar) y prender el carril
   (`"pipeline": true`). SIPO por IMAP queda para Santiago únicamente (no para el escritorio).

**Mañas del entorno:** `device_commit_files` a veces tarda en verse en la VM: verificar con grep. Git en la VM
deja `.lock`: moverlos a `.git/stale-*` (borrar no está permitido sin pedir permiso). La VM no hace push:
`PUBLICAR.bat`. Workers: `python tools/build_userscript.py` y reimportar en Tampermonkey (subir `@version`).
409 en el bot = otra instancia: terminar python.exe / claude.exe. El shell de la VM no llega a Supabase.
Sesiones de construcción cortas (misma cuota del plan).
