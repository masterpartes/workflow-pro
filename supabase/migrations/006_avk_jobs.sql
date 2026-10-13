-- 006_avk_jobs.sql
-- Cola de trabajos para consultar precios AVK en vivo.
--
-- Por que existe una cola y no una llamada directa: avkparts.lt esta detras de
-- Cloudflare y solo deja pasar al Chrome real del dueno. Ningun cliente
-- automatico (Playwright, el panel de Claude, httpx) obtiene `cf_clearance`.
-- Ver MASTER_PARTES_BUILD_BRIEF_v2.md seccion 5.
--
-- El flujo es: el servidor MCP inserta filas aqui; un worker que corre DENTRO
-- de una pestana de avkparts.lt que el dueno abrio hace el fetch mismo-origen
-- con sus cookies y escribe el resultado. El bot de Telegram nunca toca el
-- navegador: ver seccion 6 del brief, esa frontera no se mueve.

CREATE TABLE IF NOT EXISTS "avk_job" (
  id          bigserial PRIMARY KEY,
  oe          text        NOT NULL,
  status      text        NOT NULL DEFAULT 'pending',  -- pending|working|done|error
  result      jsonb,                                   -- [{provider, price_eur, price_gross_eur, lead, calidad}]
  error       text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS avk_job_pending_idx
  ON "avk_job" (status, created_at);

-- Latido del worker. Sirve para una cosa concreta: que el servidor MCP pueda
-- decir "el worker no esta corriendo" en vez de esperar 90 segundos a un
-- trabajo que nadie va a tomar.
CREATE TABLE IF NOT EXISTS "avk_worker" (
  id         integer PRIMARY KEY DEFAULT 1,
  last_seen  timestamptz NOT NULL DEFAULT now(),
  note       text,
  CONSTRAINT avk_worker_single_row CHECK (id = 1)
);
INSERT INTO "avk_worker" (id, last_seen, note)
VALUES (1, now() - interval '1 day', 'sin arrancar')
ON CONFLICT (id) DO NOTHING;

-- Sin policy, PostgREST devuelve CERO FILAS en vez de un error, y el worker
-- se queda mirando una cola que siempre parece vacia. Paso exactamente eso con
-- cost_params el 20-sep-2026.
ALTER TABLE "avk_job"    ENABLE ROW LEVEL SECURITY;
ALTER TABLE "avk_worker" ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "avk_job anon rw" ON "avk_job";
CREATE POLICY "avk_job anon rw" ON "avk_job"
  FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "avk_worker anon rw" ON "avk_worker";
CREATE POLICY "avk_worker anon rw" ON "avk_worker"
  FOR ALL TO anon, authenticated USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE ON "avk_job"    TO anon, authenticated;
GRANT USAGE, SELECT          ON SEQUENCE avk_job_id_seq TO anon, authenticated;
GRANT SELECT, UPDATE         ON "avk_worker" TO anon, authenticated;
