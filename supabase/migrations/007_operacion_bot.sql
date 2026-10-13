-- ============================================================
-- 007_operacion_bot.sql  ·  13-oct-2026
-- Base para que el bot opere workflow-pro (BRIEF_MASTER_PARTES_v3.md §6-§9).
-- Idempotente: se puede correr más de una vez.
-- Correr en: Supabase → SQL Editor → New query → Run
-- ============================================================

-- ── 1. Datos de prueba: archivar (no borrar) ──────────────────
-- Los 11 pedidos actuales son de prueba. Archivados desaparecen del
-- dashboard activo y se pueden recuperar desde "archivados".
UPDATE "Order" SET archivado = true
WHERE created_date < '2026-10-13' AND coalesce(archivado, false) = false;

-- ── 2. Tiers de clientes = los de CLAUDE.md (la versión vigente) ─
UPDATE "Client" SET tier='A', margen_min=15, margen_sugerido=20 WHERE upper(nombre) IN ('ZURICH','CHUBB');
UPDATE "Client" SET tier='B', margen_min=15, margen_sugerido=35 WHERE upper(nombre) IN ('ATLANTIDA','MAVESA','ORGU');
UPDATE "Client" SET tier='C', margen_min=25, margen_sugerido=50 WHERE upper(nombre) = 'LATINA';
UPDATE "Client" SET tier='D', margen_min=15, margen_sugerido=50 WHERE upper(nombre) = 'Q2';

INSERT INTO "Client" (nombre, tier, margen_min, margen_sugerido)
SELECT v.nombre, v.tier, v.mmin, v.msug
FROM (VALUES ('GENERALI','A',15,20), ('LIGABUE','A',15,20), ('MARITZA','A',15,20),
             ('ECOCAR','B',15,35)) AS v(nombre, tier, mmin, msug)
WHERE NOT EXISTS (SELECT 1 FROM "Client" c WHERE upper(c.nombre) = v.nombre);
-- EQUISUIZA, SPORTCAR, TIPAN, SERVICAR quedan como están (no figuran en CLAUDE.md).

-- ── 3. OrderItem: costo estimado al cotizar + datos para prorrateo ─
ALTER TABLE "OrderItem"
  ADD COLUMN IF NOT EXISTS numero_parte         text,
  ADD COLUMN IF NOT EXISTS peso_kg              numeric,
  ADD COLUMN IF NOT EXISTS embarque_id          uuid,
  ADD COLUMN IF NOT EXISTS est_fob_usd          numeric,
  ADD COLUMN IF NOT EXISTS est_flete_origen_usd numeric,
  ADD COLUMN IF NOT EXISTS est_courier_usd      numeric,  -- courier + nacionalización
  ADD COLUMN IF NOT EXISTS est_tributos_usd     numeric,  -- advalorem + fodinfa + iva aduana
  ADD COLUMN IF NOT EXISTS est_isd_usd          numeric,
  ADD COLUMN IF NOT EXISTS est_landed_usd       numeric;

-- ── 4. Embarque: una guía / un envío ──────────────────────────
CREATE TABLE IF NOT EXISTS "Embarque" (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  created_date  timestamptz DEFAULT now(),
  updated_date  timestamptz DEFAULT now(),
  awb           text,
  origen        text,          -- 'USA' | 'EU' | ...
  courier       text,
  fecha         date,
  notas         text
);

-- ── 5. Gasto: todo documento de costo ─────────────────────────
CREATE TABLE IF NOT EXISTS "Gasto" (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  created_date  timestamptz DEFAULT now(),
  updated_date  timestamptz DEFAULT now(),
  fecha         date        NOT NULL,
  proveedor     text,
  ruc           text,
  numero_doc    text,
  monto_usd     numeric     NOT NULL CHECK (monto_usd >= 0),
  iva_usd       numeric,
  categoria     text        NOT NULL CHECK (categoria IN (
                  'flete_origen','courier','aduana_declaracion',
                  'transporte_local','combustible','cliente','general')),
  embarque_id   uuid REFERENCES "Embarque"(id) ON DELETE SET NULL,
  pedido_id     uuid REFERENCES "Order"(id)    ON DELETE SET NULL,
  subido_por    text        NOT NULL,          -- 'Alejandro' | 'Santiago'
  estado        text        NOT NULL DEFAULT 'registrado'
                  CHECK (estado IN ('registrado','por_revisar','anulado')),
  archivo_url   text,                          -- ruta en bucket privado 'documentos'
  notas         text
);
CREATE INDEX IF NOT EXISTS idx_gasto_fecha  ON "Gasto"(fecha);
CREATE INDEX IF NOT EXISTS idx_gasto_estado ON "Gasto"(estado);

-- ── 6. bot_log: auditoría de cada escritura + deshacer ────────
CREATE TABLE IF NOT EXISTS "bot_log" (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  created_date  timestamptz DEFAULT now(),
  usuario       text        NOT NULL,
  tool          text        NOT NULL,
  tabla         text        NOT NULL,
  fila_id       uuid,
  antes         jsonb,
  despues       jsonb,
  deshecho      boolean     DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_bot_log_usuario ON "bot_log"(usuario, created_date DESC);

-- ── 7. updated_date automático ────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_date() RETURNS TRIGGER AS $$
BEGIN NEW.updated_date = NOW(); RETURN NEW; END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS embarque_updated_date ON "Embarque";
CREATE TRIGGER embarque_updated_date BEFORE UPDATE ON "Embarque"
  FOR EACH ROW EXECUTE FUNCTION update_updated_date();
DROP TRIGGER IF EXISTS gasto_updated_date ON "Gasto";
CREATE TRIGGER gasto_updated_date BEFORE UPDATE ON "Gasto"
  FOR EACH ROW EXECUTE FUNCTION update_updated_date();

-- ── 8. RLS + GRANT (sin policy PostgREST devuelve CERO filas, no error) ─
-- Mismo modelo abierto que el resto de las tablas por ahora.
-- PENDIENTE (brief §3.5): login en el dashboard + service_role en el MCP.
ALTER TABLE "Embarque" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "Gasto"    ENABLE ROW LEVEL SECURITY;
ALTER TABLE "bot_log"  ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_all" ON "Embarque";
CREATE POLICY "anon_all" ON "Embarque" FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "anon_all" ON "Gasto";
CREATE POLICY "anon_all" ON "Gasto"    FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);
-- bot_log: se puede leer e insertar, no editar ni borrar (es la auditoría)
DROP POLICY IF EXISTS "bot_log_read"   ON "bot_log";
DROP POLICY IF EXISTS "bot_log_insert" ON "bot_log";
DROP POLICY IF EXISTS "bot_log_undo"   ON "bot_log";
CREATE POLICY "bot_log_read"   ON "bot_log" FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "bot_log_insert" ON "bot_log" FOR INSERT TO anon, authenticated WITH CHECK (true);
CREATE POLICY "bot_log_undo"   ON "bot_log" FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON "Embarque" TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON "Gasto"    TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE         ON "bot_log"  TO anon, authenticated;

-- ── 9. Bucket privado para recibos y facturas ─────────────────
-- Las fotos de entrega siguen en 'uploads' (el dashboard las enlaza directo).
-- Recibos y facturas van acá: no tienen URL pública.
INSERT INTO storage.buckets (id, name, public)
VALUES ('documentos', 'documentos', false)
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "documentos_insert" ON storage.objects;
DROP POLICY IF EXISTS "documentos_read"   ON storage.objects;
CREATE POLICY "documentos_insert" ON storage.objects FOR INSERT TO anon, authenticated
  WITH CHECK (bucket_id = 'documentos');
CREATE POLICY "documentos_read"   ON storage.objects FOR SELECT TO anon, authenticated
  USING (bucket_id = 'documentos');

-- ── 10. Verificación: debe devolver 3 filas ───────────────────
SELECT 'Embarque' AS tabla, count(*) FROM "Embarque"
UNION ALL SELECT 'Gasto', count(*) FROM "Gasto"
UNION ALL SELECT 'bot_log', count(*) FROM "bot_log";
