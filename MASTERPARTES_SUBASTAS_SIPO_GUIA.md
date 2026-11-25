# Guía para construir la skill: masterpartes-subastas-sipo

> Documento de referencia escrito desde la sesión de cotización del 29–30 oct 2026.
> Úsalo para crear la skill final (SKILL.md) en otra sesión. Todo lo de abajo es lo que funciona hoy.

---

## 1. Contexto del negocio
- El usuario es dueño de **Master Partes** (Quito, Ecuador). Importa repuestos (vía Miami o Europa) y oferta en **subastas de aseguradoras** (SIPO / Cesvi Colombia, Audatex, Inpart).
- Cada subasta trae: aseguradora, VIN, marca/modelo/versión/año, placa, taller y una lista de piezas en español ("MASCARILLA", "STOP IZQUIERDO", "GUÍA PLÁSTICA PARACHOQUE"…). Casi nunca trae números de parte; si los trae (Audatex), pueden estar mal → verificar siempre por VIN.
- Trabajo de Claude: **número OEM correcto por VIN + precios** para que el usuario decida y oferte. Él oferta; Claude nunca envía nada.
- Tiers de cliente (parámetro `cliente` de quote_list): **Zurich = A**, **Latina = C**, **Atlántida / sin cliente = B**.
- Idioma: español, directo, tablas compactas. El usuario es experto; no explicar lo obvio.

## 2. Herramientas masterpartes (MCP en la laptop: `mcp__remote-devices__masterpartes__*`)
- **quote_parts**(parts=[{parte}], vin | brand, source auto|partsouq|auvika, incluir_alterno) → OEM MSRP/oferta + eBay genuino/alterno.
  - Con **VIN**: separa bien eBay genuino vs alterno, pero para VIN no-US devuelve OEM null (intenta PartSouq → cloudflare_403). Incluso 5J6 (Honda US) lo trató como no-US.
  - Con **brand** ("toyota", "honda", "nissan", "ford", "mazda"): trae OEM de la tienda US (toyotapartsdeal, hondapartsnow, nissanpartsdeal; Mazda está bloqueado por Cloudflare) pero mezcla genuino/alterno de eBay. → Correr ambas variantes cuando importe.
  - **Lotes de 2–4 partes** (timeout 60 s). Si hay timeout, reintentar en lotes más chicos (es solo lectura).
- **quote_list**(parts, cliente, vin/brand, source, precio auto|oem|ebay|alterno, freight_origin_eur) → costo puesto en Quito con margen del tier. Ofrecerlo al final; lotes 2–4.
- **ebay_por_descripcion**(piezas en inglés) → FOB aproximado sin número. NO usar year/make/model (HTTP 400, categoría 6028 no soporta fitment); poner "2018 Honda CR-V …" en el texto. También sirve para **descubrir números OEM en títulos** de anuncios.
- **buscar_numeros_vin** y source="auvika" dependen de workers en el Chrome del usuario que suelen estar caídos; no depender de ellos.
- eBay "genuino" < 40 % del OEM = casi seguro aftermarket/usado mal etiquetado → marcar ⚠. Revisar también envío absurdo (total con $300 de envío).

## 3. Dónde sacar números por VIN (en el Chrome del usuario, Claude in Chrome)
### PartSouq — `https://partsouq.com/en/search/all?q=<VIN>`
- Sirve para Toyota, Nissan, Mazda (no MM7 Tailandia), Honda (lista ambigua), japoneses de mercado general.
- Toyota: `/catalog/toyota/...`, diagramas por código (5253 parachoque trasero, 6761 compuerta, 6762 bisagras/amortiguadores compuerta, 7551 emblemas, 7552 molduras, 6451/6455 tapizados, 8111 stops). Extraer con `fetch` + DOMParser: `a.part-number-link` y el texto del padre (nombre, Variant, Spec).
- Nissan/Mazda: `/partcatalog/groups/...` (Laximo). Tomar links de categorías; para carrocería entrar a "Body, car glass" y sus subcategorías (Bumper, Radiator grille, Moldings, Doors…); luego diagramas. Números = links con texto `^[A-Z0-9]{8,13}$`. Las variables JS se pierden al navegar → redefinir.
- Precio/stock PartSouq: `fetch('/en/search/all?q=NUM')` desde una pestaña de partsouq y regex sobre "Search result for … Availability … Weight, kg … $ … Not Available". Secuencial, no paralelo.
- Las herramientas MCP NO pueden leer PartSouq (Cloudflare); solo vía Chrome.
- No reconoce: Mazda MM7 (Tailandia), X-Trail T33 2024, Peugeot.
- El output del JS se bloquea si contiene "=" / "&" (parece query string) → limpiar con regex antes de devolver.

### Partslink24 (el usuario inicia sesión; Claude NUNCA escribe credenciales)
- Marcas útiles: Renault, Peugeot/PSA, Ford Europa, VW, Nissan. **No incluye Mazda** en la suscripción.
- URLs: `/pl24-app/<marca>_parts/<VIN>/0/vehicle` y `/pl24-app/<marca>_parts/<VIN>/0/search?q=<texto>` (renault_parts, peugeot_parts…). Para Ford: `partslink24/user/brandMenu.do` → campo "Chassis number" → elegir Ford o Ford Commercial.
- Marca de agua "Demo" o pantalla de login = sesión cerrada → pedir al usuario que vuelva a entrar. La sesión se pierde fácil al saltar entre marcas o abrir otros sitios.
- La búsqueda de texto: usar el cuadro superior (triple click, escribir, Enter) y leer `document.body.innerText` entre "Search:" y "More hits". Hacer clic en un número abre su ilustración con la lista completa y restricciones.
- **Ford Europa**: el número de pedido es el **FINIS de 7 dígitos**; reportar también el de ingeniería (LV4B-…). Si el VIN no está, elegir modelo manual (ej. Kuga CTD 2020-) y filtrar por equipamiento.
- Renault: "No bill of materials" = no aplica al VIN; restricciones por equipamiento deciden variante. Peugeot: columna Remark dice Left/Right.
- Partslink decodifica el motor real (ej. 3008 que Audatex llama "1.6 GT" es DW10FD 2.0 diésel) → avisar discrepancias.

### Tiendas OEM US / gemelo US
- hondapartsnow, toyotapartsdeal, nissanpartsdeal (las usa quote_parts con brand).
- **parts.nissanusa.com**: diagramas por versión, ej. `/v-2025-nissan-rogue--sl--1-5l-l3-gas/body--bumper-and-components-rear`. Cloudflare pasa solo esperando ~8 s.
- Si el modelo no está en catálogos, usar el gemelo US y elegir versión por las fotos (X-Trail T33 = Rogue 2021+; Kuga = Escape). Lo pidió el usuario: "ir a la tienda OEM y elegir por descripción".

### AVK — avkparts.lt (europeos: Renault, PSA, Ford EU)
- Precios EUR sin IVA. Si el worker está caído, consultar directo en una pestaña logueada con `fetch('/search/NUM', {credentials:'include'})`.
- Parseo: elementos `[class*=column_price_no_tax]` → subir al contenedor que tenga `[class*=column_provider]`; texto en lituano ("d.d." = días); el **primer €** es sin IVA.
- Proveedores "RENAULT T/P/2/3/F" (y PSA) = genuinos; tomar el más barato.
- "Just a moment…" = desafío Cloudflare → el usuario debe resolverlo en la pestaña.

## 4. Leer subastas del correo
- Roundcube del usuario, carpeta `INBOX.SIPO`. Lista: `#messagelist tbody tr` (clase `flagged` = bandera roja; el id `rcmrow…` es el UID en base64).
- Cuerpo: `fetch(location.pathname+'?_task=mail&_action=show&_uid=UID&_mbox=INBOX.SIPO')`.
- "Cotizar hasta la primera con bandera roja" = desde la más reciente hasta antes de la primera marcada.
- Extraer: Empresa, Marca/Línea/Versión/Modelo, VIN, Placa, Consecutivo (Clave), Siniestro y piezas entre "Piezas a Subastar" y "Si desea" (quitar "CARROCERIA - ").
- Si un VIN ya se cotizó antes, decirlo y reutilizar.

## 5. Traducción de nombres (Audatex → catálogo)
- Mascarilla = radiator grille. Niquelado mascarilla = moldura cromada (Nissan T32: MOULDING-FRONT BUMPER 62072-4BA0A).
- Stop = lámpara trasera en carrocería. Luz/faro en compuerta, luz reversa tapa baúl = lámpara de tapa (trunk/back door lamp). Reflectivo parachoque = reflex reflector (en Arkana es el neblinero trasero).
- Guía parachoque = retainer/bracket lateral. Vincha = clip/soporte pequeño (no cotizar clips sueltos salvo que pidan).
- Extensión plástica guardafango = moldura de arco (fender flare/wheel arch). OJO: en Honda "protector, wheel arch" es el **forro interior**, no la moldura.
- Guardapolvo plástico = splash shield (puede ser escudo pequeño o forro completo; aclarar).
- Mesa = lower control arm. Terminal = outer tie rod end. Brazo axial / barra dirección = inner tie rod. Link = stabilizer link. Torre amortiguador = strut mount (+ rodamiento). Manzana = hub (en CX-5 incluye rodamiento → no cotizar rodamiento aparte). Fijación mangueta a mesa = perno estándar.
- Deflector de radiador = air guide. Cobertor sup. radiadores = radiator core upper cover/seal.
- Tapa remolque = tow hook cap/flap. Emblema/monograma = emblem/monogram/name plate.
- Lados por marca: Mazda 700=RH 900=LH, 300=RH 350=LH, 021=RH 031=LH, 550X=RH 560X=LH; Toyota 81551=RH 81561=LH; Ford número impar suele ser LH. Confirmar siempre con (R)/(L) del catálogo.
- Partes en color (parachoques Mazda, tapas de remolque) a veces no tienen número en PartSouq → marcar "sin número".
- Arkana: el parachoque posterior son dos mitades (850169973R RH / 850176695R LH) = mismas que "punteras" → no duplicar.

## 6. Flete y costo
- Miami → Quito: lo calcula quote_list (cost_params en Supabase).
- AVK (Vilnius → Miami): **€6.33 por kg volumétrico**, divisor 5000, **cada parte se cotiza como si fuera la única del pedido**.
  - Parachoque 170×60×50 = 102 vkg = €645.66
  - Mascarilla 130×60×30 = 46.8 vkg = €296.24
  - Faro 70×40×30 = 16.8 vkg = €106.34
  - Caja pequeña 40×40×40 = 12.8 vkg = €81.02 (módulos, cables, vinchas, sensores, emblemas)
  - Extra voluminoso (parabrisas, costados, tapizados de techo, protectores inferiores) → pedir volumen al usuario.
- Migración propuesta `supabase/migrations/009_envio_clase.sql` (tabla envio_clase + mapa de palabras) existe en workflow-pro pero NO está aplicada.

## 7. Flujo estándar por subasta
1. Decodificar el VIN en el catálogo (motor/versión reales); avisar si contradice a Audatex.
2. Números por VIN: PartSouq → Partslink → tienda OEM / gemelo US. Nunca inventar; lo dudoso con ⚠.
3. Precios: quote_parts (brand para OEM US, VIN para separar eBay), PartSouq vía Chrome como referencia OEM para no-US, AVK para europeos.
4. Entregar por subasta una tabla:
   **Pieza | Número | OEM (oferta / MSRP, o PartSouq ref + stock) | eBay genuino | Alterno**
   Debajo, pocas viñetas: ⚠ sospechosos, piezas sin número, duplicados, qué falta y qué se necesita del usuario (login, Cloudflare, equipamiento).
5. Ofrecer el siguiente paso: quote_list puesto en Quito con el tier del cliente.

## 8. Preferencias y correcciones del usuario
- Precios con **masterpartes** ("Masterpartes usa la API de eBay"); no búsquedas manuales ni imágenes de presupuesto.
- Empezar de inmediato; preguntar solo lo que bloquea (login, volumen de extra voluminosos, equipamiento cuando hay variantes — ej. espejos Ford: ¿punto ciego? ¿plegado eléctrico?).
- Ford Europa = FINIS de 7 dígitos.
- Sin catálogo → tienda OEM y elegir por descripción y fotos del vehículo.
- Precios siempre como FOB (US$ o € sin IVA) salvo que se haya corrido quote_list; decirlo.
- Cerrar pestañas propias al terminar; no disparar diálogos del navegador; nunca escribir contraseñas.

## 9. Archivos útiles (laptop, `C:\Users\Juan Guerra\Desktop\workflow-pro`)
- `avk_worker_bookmarklet.html` — worker AVK (marcador en avkparts.lt).
- `tools/avk_worker.js`, `tools/shared/quito_cost.py`, `mcp_server/server.py` — lógica de cotización.
- `supabase/migrations/009_envio_clase.sql` — tabla de clases de envío (pendiente de aplicar), igual que la 008 (worker de catálogo).
