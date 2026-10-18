-- 008_catalog_jobs.sql
-- Cola de trabajos "buscar numeros de parte por VIN" (diseno handoff seccion 11).
--
-- Mismo patron que avk_job (006): el servidor MCP encola; un worker que corre
-- DENTRO de una pestana de partsouq.com abierta por el dueno (Chrome real, pasa
-- Cloudflare) toma el trabajo, navega VIN -> grupo -> diagrama, y escribe la
-- lista de piezas de los diagramas como TEXTO. El bot nunca toca el navegador.
--
-- El trabajo lleva SOLO un VIN validado (17 caracteres, sin I/O/Q) y las
-- descripciones tipeadas. El worker usa las descripciones unicamente para
-- elegir diagramas por palabras clave; nunca las mete en una URL.

CREATE TABLE IF NOT EXISTS "catalog_job" (
  id            bigserial PRIMARY KEY,
  vin           text        NOT NULL,
  descripciones jsonb       NOT NULL,                  -- ["faro derecho", "parachoque delantero", ...]
  status        text        NOT NULL DEFAULT 'pending', -- pending|working|done|error
  result        jsonb,                                  -- {vehiculo, diagramas:[{grupo,nombre,tags,aplica,piezas:[...]}], pedidos:[...]}
  error         text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS catalog_job_pending_idx
  ON "catalog_job" (status, created_at);

-- Latido del worker: para decir "no esta corriendo" en un segundo en vez de
-- esperar a un trabajo que nadie va a tomar.
CREATE TABLE IF NOT EXISTS "catalog_worker" (
  id         integer PRIMARY KEY DEFAULT 1,
  last_seen  timestamptz NOT NULL DEFAULT now(),
  note       text,
  CONSTRAINT catalog_worker_single_row CHECK (id = 1)
);
INSERT INTO "catalog_worker" (id, last_seen, note)
VALUES (1, now() - interval '1 day', 'sin arrancar')
ON CONFLICT (id) DO NOTHING;

-- Sin policy + GRANT, PostgREST devuelve CERO FILAS sin error (regla del §9).
ALTER TABLE "catalog_job"    ENABLE ROW LEVEL SECURITY;
ALTER TABLE "catalog_worker" ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "catalog_job anon rw" ON "catalog_job";
CREATE POLICY "catalog_job anon rw" ON "catalog_job"
  FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "catalog_worker anon rw" ON "catalog_worker";
CREATE POLICY "catalog_worker anon rw" ON "catalog_worker"
  FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE ON "catalog_job"    TO anon, authenticated;
GRANT USAGE, SELECT          ON SEQUENCE catalog_job_id_seq TO anon, authenticated;
GRANT SELECT, UPDATE         ON "catalog_worker" TO anon, authenticated;
