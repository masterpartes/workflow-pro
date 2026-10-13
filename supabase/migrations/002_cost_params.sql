-- 002_cost_params.sql
-- Quito landed-cost engine parameters.
--
-- Every constant the cost engine uses lives here, never in code, so that
-- recalibration is an UPDATE rather than a deploy. See MASTER_PARTES_BUILD_BRIEF_v2.md §3.2.
--
-- Recalibrate quarterly from one recent refrendo (DAS) + one forwarder invoice.
-- Do NOT build an ingestion pipeline for customs declarations.

CREATE TABLE IF NOT EXISTS "cost_params" (
  key         text PRIMARY KEY,
  value       numeric     NOT NULL,
  unit        text,
  notes       text,
  source      text,                     -- the document this value was measured from
  updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Seed / refresh. Idempotent: re-running updates values without duplicating rows.
INSERT INTO "cost_params" (key, value, unit, notes, source) VALUES
  ('insurance_pct',                 1.0,    'percent of FOB',
   'Confirmed at 0.998% on a real declaration.',
   'DAS 0877-7841 06-sep-2026'),

  ('freight_declared_usd_kg',       1.4458, 'USD per kg',
   'What the forwarder declares to customs. Enters CIF only. Excel had a stale 4.00.',
   'DAS 0877-7841: flete 127.74 / 88.35 kg'),

  ('courier_usd_kg',                4.00,   'USD per kg',
   'ALL-IN Miami-Quito courier rate. No fuel surcharge, no x-ray. Excel had a stale 3.70.',
   'Panatlantic invoice 09-sep-2026'),

  ('nacionalizacion_usd_declaration', 30.00, 'USD per declaration',
   'Fixed per customs declaration. The courier may split the cargo into any number of guias; the total is always 30 + IVA.',
   'Panatlantic invoice 09-sep-2026: 3 guias x 10.00'),

  ('avg_kg_per_import',             35.0,   'kg',
   'Typical consolidated shipment, several times a week. Used to prorate nacionalizacion. A quote cannot know how the part will actually be consolidated, so this is deliberately an average.',
   'owner, 13-sep-2026'),

  ('iva_pct',                       15.0,   'percent',       'Ecuador IVA.',                      'DAS 0877-7841'),
  ('isd_pct',                       5.0,    'percent',       'Impuesto a la Salida de Divisas. Applies to FOB + origin freight ONLY. Miami-Quito is billed locally in Ecuador and carries no ISD.', 'owner, 13-sep-2026'),
  ('fodinfa_pct',                   0.5,    'percent of CIF','',                                  'DAS 0877-7841'),

  ('fx_max_age_hours',              72,     'hours',
   'Refuse to quote on an FX rate older than this. ECB does not publish at weekends, so 72h spans a normal Friday-to-Monday gap.',
   'design decision')
ON CONFLICT (key) DO UPDATE
  SET value      = EXCLUDED.value,
      unit       = EXCLUDED.unit,
      notes      = EXCLUDED.notes,
      source     = EXCLUDED.source,
      updated_at = now();

-- DELIBERATELY ABSENT, do not re-add:
--   fuel_pct  (2.7%)  and  xray_pct (1.7%)
-- Both are modelled in cotizacion_bulk.xlsm and appear on no forwarder invoice.
