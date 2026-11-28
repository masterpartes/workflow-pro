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
| 2 | Agente de Santiago: carpeta `C:\MasterPartesBot\agente`, carril en el relay, cola, imagen cliente | código LISTO; **setup de laptop y prueba pendientes** |
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
- 28-nov: verificado: 0 líneas importadas; el agente nunca corrió (no hay `agente\historial`);
  bot sin uso desde 18-oct; workers AVK/catálogo sin latido desde 28/29-oct.

## Archivos clave
- `workflow-pro\supabase\migrations\010_lineas.sql`, `src\pages\Lineas.jsx`
- `workflow-pro\mcp_server\server.py` (tools), `tools\shared\presupuesto.py`
- `C:\MasterPartesBot\agente\` (CLAUDE.md, .claude\skills, settings), `relay\telegram_relay.py`
- `workflow-pro\INVENTARIO_2026-11-25.md` (qué fuentes existen y dónde)
- `PUBLICAR.bat` (push → Vercel; el push solo funciona desde la laptop)
