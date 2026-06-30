-- ============================================================
--  Panel de Tareas — Migración Supabase
--  Ejecutar en: Supabase Dashboard → SQL Editor → Run
-- ============================================================

CREATE TABLE IF NOT EXISTS "Tarea" (
  id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  titulo           TEXT NOT NULL,
  descripcion      TEXT,
  entregable_tipo  TEXT DEFAULT 'texto',     -- 'texto' | 'archivo' | 'foto'
  entregable_url   TEXT,                     -- URL pública (Supabase Storage)
  entregable_texto TEXT,                     -- Texto libre como entregable
  fecha_vencimiento DATE NOT NULL,
  asignado_a       TEXT DEFAULT 'Ambos',     -- 'Santiago' | 'Alejandro' | 'Ambos'
  creado_por       TEXT,
  estado           TEXT DEFAULT 'pendiente', -- 'pendiente' | 'completado' | 'archivado'
  completado_en    TIMESTAMPTZ,
  created_date     TIMESTAMPTZ DEFAULT NOW(),
  updated_date     TIMESTAMPTZ DEFAULT NOW()
);

-- Índices útiles
CREATE INDEX IF NOT EXISTS idx_tarea_estado ON "Tarea"(estado);
CREATE INDEX IF NOT EXISTS idx_tarea_fecha  ON "Tarea"(fecha_vencimiento);

-- Trigger para updated_date automático
CREATE OR REPLACE FUNCTION update_updated_date()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_date = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tarea_updated_date ON "Tarea";
CREATE TRIGGER tarea_updated_date
  BEFORE UPDATE ON "Tarea"
  FOR EACH ROW EXECUTE FUNCTION update_updated_date();

-- RLS: permitir todas las operaciones (ajustar según auth de tu proyecto)
ALTER TABLE "Tarea" ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "allow_all_tarea" ON "Tarea";
CREATE POLICY "allow_all_tarea" ON "Tarea"
  FOR ALL USING (true) WITH CHECK (true);
