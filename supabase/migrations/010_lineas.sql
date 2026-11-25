-- ============================================================
-- 010_lineas.sql  ·  25-nov-2026
-- Una fila por parte (OrderItem) reemplaza DESPACHO, PROVINCIAS y
-- FACTURAS POR COBRAR. Order queda como cabecera (cliente, siniestro, VIN).
-- Las vistas dan cada planilla vieja como un filtro.
-- Idempotente. Correr en: Supabase -> SQL Editor -> New query -> Run
-- ============================================================

-- ── 1. Cabecera del pedido ───────────────────────────────────
ALTER TABLE "Order"
  ADD COLUMN IF NOT EXISTS clave      text,   -- SIPO / Audatex / Inpart id
  ADD COLUMN IF NOT EXISTS siniestro  text,
  ADD COLUMN IF NOT EXISTS vin        text,
  ADD COLUMN IF NOT EXISTS vehiculo   text,
  ADD COLUMN IF NOT EXISTS taller     text;

-- ── 2. La fila por parte ─────────────────────────────────────
ALTER TABLE "OrderItem"
  ADD COLUMN IF NOT EXISTS calidad          text,     -- genuino | alterno | usado
  ADD COLUMN IF NOT EXISTS proveedor        text,     -- eBay, AVK, PartSouq, fordpartsgiant...
  ADD COLUMN IF NOT EXISTS orden_proveedor  text,     -- n.º de orden / factura del proveedor
  ADD COLUMN IF NOT EXISTS valor_declarado  numeric,  -- columna VALOR del despacho (USD)
  ADD COLUMN IF NOT EXISTS subpartida       text,
  ADD COLUMN IF NOT EXISTS arancel_pct      numeric,  -- 0.15 = 15 %
  ADD COLUMN IF NOT EXISTS despacho         text,     -- ref. del despacho a Panatlantic (PNT-13093)
  ADD COLUMN IF NOT EXISTS fecha_despacho   date,
  ADD COLUMN IF NOT EXISTS destino          text,     -- MACHALA, GUAYAQUIL, ENTREGA LOCAL, PARA MI...
  ADD COLUMN IF NOT EXISTS instruccion      text,     -- qué hace Santiago al recibir
  ADD COLUMN IF NOT EXISTS problema         text,     -- no vacío = fila con problema (alerta)
  ADD COLUMN IF NOT EXISTS costo_real_usd   numeric,  -- landed real cuando se conoce
  ADD COLUMN IF NOT EXISTS factura_numero   text,
  ADD COLUMN IF NOT EXISTS fecha_factura    date,
  ADD COLUMN IF NOT EXISTS fecha_cobro      date,     -- vacío = por cobrar
  ADD COLUMN IF NOT EXISTS factura_prov_url text,     -- factura del proveedor (Word para aduana)
  ADD COLUMN IF NOT EXISTS notas            text;

-- Pegar filas rápido: sin pedido ni fecha límite obligatorios.
ALTER TABLE "OrderItem" ALTER COLUMN pedido_id           DROP NOT NULL;
ALTER TABLE "OrderItem" ALTER COLUMN fecha_entrega_orden DROP NOT NULL;
ALTER TABLE "OrderItem" ALTER COLUMN cantidad            SET DEFAULT 1;

-- Estados: se agregan despachado, en_quito y cancelado.
DO $$
DECLARE c text;
BEGIN
  FOR c IN SELECT conname FROM pg_constraint
           WHERE conrelid = '"OrderItem"'::regclass AND contype = 'c'
             AND pg_get_constraintdef(oid) ILIKE '%estado%'
  LOOP EXECUTE format('ALTER TABLE "OrderItem" DROP CONSTRAINT %I', c); END LOOP;
END $$;
ALTER TABLE "OrderItem" ADD CONSTRAINT "OrderItem_estado_check" CHECK (estado IN (
  'adjudicado','comprado','transito','en_bodega','despachado',
  'en_aduana','en_quito','enviado_cliente','entregado','cancelado'));

CREATE INDEX IF NOT EXISTS idx_item_estado   ON "OrderItem"(estado);
CREATE INDEX IF NOT EXISTS idx_item_tracking ON "OrderItem"(tracking_number);
CREATE INDEX IF NOT EXISTS idx_item_wr       ON "OrderItem"(wr_bodega);

-- ── 3. Días hábiles (lun-vie; feriados: pendiente) ────────────
CREATE OR REPLACE FUNCTION add_business_days(d date, n int) RETURNS date
LANGUAGE sql IMMUTABLE AS $$
  SELECT x::date FROM generate_series(d + 1, d + n * 2 + 14, interval '1 day') x
  WHERE extract(isodow FROM x) < 6
  ORDER BY x OFFSET greatest(n, 1) - 1 LIMIT 1
$$;

-- ── 4. Vista plana: una fila = una parte, con su cabecera ─────
CREATE OR REPLACE VIEW v_linea AS
SELECT
  i.*,
  o.numero_pedido, o.cliente, o.clave, o.siniestro, o.placa, o.vin, o.vehiculo,
  o.taller, o.fecha_pedido, coalesce(o.archivado, false) AS archivado,
  coalesce(i.fecha_entrega_orden,
           add_business_days(coalesce(o.fecha_pedido, i.created_date::date), 20)) AS vence,
  coalesce(i.costo_real_usd, i.est_landed_usd, i.precio_compra) AS costo_usd,
  (i.costo_real_usd IS NULL) AS costo_estimado,
  i.precio_venta * coalesce(i.cantidad, 1) AS venta_total,
  i.precio_venta * coalesce(i.cantidad, 1)
    - coalesce(i.costo_real_usd, i.est_landed_usd, i.precio_compra) * coalesce(i.cantidad, 1) AS margen_usd,
  (i.estado NOT IN ('entregado','cancelado')
   AND coalesce(i.fecha_entrega_orden,
        add_business_days(coalesce(o.fecha_pedido, i.created_date::date), 20)) < current_date) AS atrasado,
  c.plazo_pago_dias
FROM "OrderItem" i
LEFT JOIN "Order"  o ON o.id::text = i.pedido_id::text
LEFT JOIN LATERAL (
  SELECT plazo_pago_dias FROM "Client" c
  WHERE upper(o.cliente) LIKE '%' || upper(c.nombre) || '%'
  ORDER BY length(c.nombre) DESC LIMIT 1) c ON true;

-- ── 5. Las planillas viejas como vistas ───────────────────────
-- DESPACHO: en bodega Miami, todavía sin despacho a Panatlantic.
CREATE OR REPLACE VIEW v_por_despachar AS
SELECT id, wr_bodega, tracking_number, producto_nombre, valor_declarado, peso_kg,
       subpartida, arancel_pct, cliente, numero_pedido
FROM v_linea WHERE estado = 'en_bodega' AND despacho IS NULL;

-- PROVINCIAS: lo que llega (o llegó) a manos de Santiago y qué hacer.
CREATE OR REPLACE VIEW v_llegadas AS
SELECT id, estado, wr_bodega, tracking_number, producto_nombre, cliente, numero_pedido,
       placa, destino, instruccion, problema, despacho, vence
FROM v_linea WHERE estado IN ('despachado','en_aduana','en_quito');

-- FACTURAS POR COBRAR
CREATE OR REPLACE VIEW v_por_cobrar AS
SELECT cliente, factura_numero, fecha_factura,
       fecha_factura + coalesce(plazo_pago_dias, 30) AS cobro_esperado,
       sum(venta_total) AS monto_sin_iva,
       string_agg(producto_nombre, ', ') AS concepto
FROM v_linea
WHERE factura_numero IS NOT NULL AND fecha_cobro IS NULL
GROUP BY cliente, factura_numero, fecha_factura, plazo_pago_dias;

-- Alertas para Santiago y el dueño
CREATE OR REPLACE VIEW v_alertas AS
SELECT id, cliente, numero_pedido, producto_nombre, estado, vence,
       CASE WHEN problema IS NOT NULL THEN 'problema: ' || problema
            WHEN atrasado THEN 'atrasado (vencía ' || vence || ')'
            WHEN estado = 'en_quito' AND destino IS NULL THEN 'llegó sin destino'
       END AS alerta
FROM v_linea
WHERE NOT archivado AND (problema IS NOT NULL OR atrasado
                         OR (estado = 'en_quito' AND destino IS NULL));

-- Margen bruto por mes de factura
CREATE OR REPLACE VIEW v_margen_mes AS
SELECT date_trunc('month', fecha_factura)::date AS mes,
       count(*) AS partes,
       sum(venta_total) AS ventas_sin_iva,
       sum(costo_usd * coalesce(cantidad, 1)) AS costo,
       sum(margen_usd) AS margen_bruto,
       round(100 * sum(margen_usd) / nullif(sum(venta_total), 0), 1) AS margen_pct,
       bool_or(costo_estimado) AS incluye_estimados
FROM v_linea WHERE fecha_factura IS NOT NULL
GROUP BY 1 ORDER BY 1 DESC;

-- ── 6. Permisos (sin GRANT, PostgREST devuelve cero filas) ────
GRANT SELECT ON v_linea, v_por_despachar, v_llegadas, v_por_cobrar, v_alertas, v_margen_mes
  TO anon, authenticated;
GRANT EXECUTE ON FUNCTION add_business_days(date, int) TO anon, authenticated;
NOTIFY pgrst, 'reload schema';

-- ── 7. Verificación ──────────────────────────────────────────
SELECT add_business_days('2026-11-25', 20) AS vence_ejemplo,  -- debe dar 2026-12-23
       (SELECT count(*) FROM v_linea) AS lineas;
