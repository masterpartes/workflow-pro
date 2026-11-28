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


## PRÓXIMA SESIÓN — empezar acá (escrito 28-nov 19:50)

**Objetivo:** pipeline del carril de Santiago a ~1 ¢ por pedido, con la calidad de la corrida de escritorio
(ver Estado 28-nov 18:40). El agente completo (`claude -p --chrome`) queda solo como último recurso.

**Piezas a construir (en este orden, probando cada una):**
1. `relay/ia_min.py` — `llamar(prompt, imagen=None, modelo="haiku")`: `claude -p` desde
   `C:\MasterPartesBot\vacio` con `--system-prompt <corto> --tools "" --strict-mcp-config
   --disable-slash-commands --setting-sources local --output-format json`; imagen vía
   `--input-format stream-json` (mensaje user con bloque image base64). Medido: 626 tokens de arranque.
2. `leer_pedido(texto|imagen)` → JSON estricto {vin, marca, cliente, clave, cierre, caso_expres,
   piezas:[{texto, cant, numero?, en}]} (`en` = término de catálogo en inglés). SIPO por IMAP sin IA
   después (paso 6).
3. Ruteo por VIN (WMI): PartSouq (`catalog_live.catalogo_crudo`), Partslink24 (`partslink_crudo`),
   EE.UU. (paso 5). Workers ya existen y andan (userscript v5).
4. `emparejar(pieza, texto_diagramas)` (Sonnet, sin herramientas) → {numero, confianza, nota ⚠};
   validar que el número exista en el texto leído. Precios: `precios_partsouq`, AVK
   (`avk_live.lookup_avk`, devuelve € y peso), `quote_list`/`quote_quito_cost`; tabla con formato fijo
   (CLAUDE.md del agente §3) armada en código. Integrar en `telegram_relay.py` como carril 3a;
   el agente completo pasa a `/agente <pedido>`.
5. Worker tascaparts / oempartsonline (mismo patrón; plataforma RevolutionParts) para Ford US, Honda,
   GM, Mopar, BMW/VW US.
6. SIPO por IMAP + `reglas_subastas.json` → "subastas" sin IA para leer.

**Pruebas de referencia:** Montero MMBGUKS50PH001101 faro derecho → 8301D438 (PSQ $1423.73 sin stock,
reemplazo 26010W570P). Skoda TMBEC4PJ7S4006022 parabrisas → 6VA845011K NVB (AVK €229.74, 13.95 kg),
"caucho" → 6VA823723 ⚠.

**Mañas del entorno:** `device_commit_files` a veces tarda en verse en la VM: verificar con grep antes de
construir/commitear. Git en la VM deja `.lock`: moverlos a `.git/stale-*`. La VM no puede hacer push:
`PUBLICAR.bat`. Los workers se actualizan reconstruyendo (`python tools/build_userscript.py`) y
reimportando en Tampermonkey (subir `@version`). 409 en el bot = otra instancia: terminar python.exe /
claude.exe. Sesiones de construcción en Sonnet y cortas (la cuota es la misma del plan Pro).
