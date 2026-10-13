# HANDOFF — 13/14-oct-2026 (para arrancar una conversación NUEVA)

Fuente de verdad del diseño: `BRIEF_MASTER_PARTES_v3.md`. Esto es solo el estado.

## Hecho y probado contra la base real
- Git al día (había un `.git/HEAD.lock` del 17-jul que bloqueaba todos los commits). Falta `git push origin HEAD:backup-2026-10-13` desde PowerShell del dueño.
- Migración `007_operacion_bot.sql` aplicada: Embarque, Gasto, bot_log, costos estimados en OrderItem, bucket privado `documentos`, tiers de Client = CLAUDE.md, 11 pedidos de prueba archivados.
- Tools MCP nuevas: `inspect_db`, `db_select`, `find_orders`, `record_delivery`, `record_expense`, `undo_last`, `quote_list`, `quote_detail`, `create_order`.
- `quote_list`: cotiza la lista en UNA llamada y devuelve la tabla armada (≤42 col). Sin cliente → tier B; números Ford reconocidos solos; peso/arancel faltantes → supuesto conservador marcado ⚠. Probado en vivo (ORGU Ford Escape: 94/138/186 · 176/215/290 · 301/375/507).
- `create_order` ("vendido 1, 3") probado en vivo con deshacer.
- Skill `master-partes-operador` propuesta para el dueño en la app del teléfono.

## Decisiones de esta sesión
- Santiago por Telegram (permisos limitados, siempre usuario=Santiago). El dueño opera desde la app de Claude.
- Cada cotización se trata como NUEVA: nada de sesión larga (el costo crecía mensaje a mensaje hasta el límite).
- Telegram, no WhatsApp.

## En curso — retomar acá
1. **Relay** `C:\MasterPartesBot\relay\telegram_relay.py` (escrito, SIN probar en Windows). `INICIAR_BOT.bat` ahora lo arranca; el viejo quedó como `INICIAR_BOT_CHANNELS_viejo.bat`. Cada mensaje = `claude -p` nuevo (Sonnet) con solo la vuelta anterior. `/ping`, `/uso`, `/nuevo` sin IA. Log en `relay\uso.csv`.
2. **Carril sin IA (propuesto, falta el OK del dueño):** lista tipeada "PARTE descripción" (+ cliente) y correcciones ("cliente zurich", "peso cubo 4", "m=40") resueltas por el relay llamando `quote_list` directo → costo cero. Fotos / texto libre / "sí" → Claude.
3. Verificar que Claude Code en la laptop esté con la SUSCRIPCIÓN (el bot mostraba "API Usage Billing"). Si persiste: variable `ANTHROPIC_API_KEY` en Windows.
4. Decisión pendiente: avisar en la tabla cuando el precio sugerido supera el MSRP (pasó en 2 de 3 partes de la prueba).

## Pendientes heredados
- Rotar contraseña Inpart y token del bot.
- Login en el dashboard (anon key con escritura total, pública en Vercel).
- Tools: compras/avanzar etapa, embarques + prorrateo por peso, ventas (XML SRI), página Márgenes, digest matinal.
- Quotation/QuotationItem de Supabase sin usar (las cotizaciones viven en `workflow-pro\data\cotizaciones\*.json`).
