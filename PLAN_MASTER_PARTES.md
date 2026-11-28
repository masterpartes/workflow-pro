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
| 3 | Workers: userscript con AVK + PartSouq catálogo + PartSouq precio/peso/envío; latidos y alertas | pendiente (workers caídos desde fin de oct) |
| 4 | Guardar líneas de cotización (de Alejandro y de Santiago) + precio ofertado/adjudicado | pendiente |
| 5 | Adjudicación por captura → filas de pedido; despacho Panatlantic (tabla + Word facturas) | pendiente |
| 6 | Alertas a Santiago por Telegram (atrasados, problema, llegó sin destino) — sin IA | pendiente |
| 7 | Margen: export para el agente contable | pendiente (vista `v_margen_mes` ya existe) |
| 8 | Seguridad: login dashboard, service_role solo en MCP | pendiente |

## Estado (actualizar)
- 25-nov: migración 010 aplicada; Líneas publicada (Vercel); `IMPORTAR_PENDIENTES.xlsx` en
  `workflow-pro\Claude outputs\` para revisar y pegar. `render_presupuesto` en el MCP.
  Relay con carril agente (`telegram_relay.py`, backup `.bak-2026-11-25`).
- 28-nov: verificado: 0 líneas importadas; el agente nunca corrió (no hay `agente\historial`);
  bot sin uso desde 18-oct; workers AVK/catálogo sin latido desde 28/29-oct.

## Archivos clave
- `workflow-pro\supabase\migrations\010_lineas.sql`, `src\pages\Lineas.jsx`
- `workflow-pro\mcp_server\server.py` (tools), `tools\shared\presupuesto.py`
- `C:\MasterPartesBot\agente\` (CLAUDE.md, .claude\skills, settings), `relay\telegram_relay.py`
- `workflow-pro\INVENTARIO_2026-11-25.md` (qué fuentes existen y dónde)
- `PUBLICAR.bat` (push → Vercel; el push solo funciona desde la laptop)
