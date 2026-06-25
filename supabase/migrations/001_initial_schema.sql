-- ============================================================
-- workflow-pro  —  Initial Supabase Schema
-- Run this in: Supabase Dashboard → SQL Editor → New query
-- ============================================================

-- ─────────────────────────────────────────
-- 1. PRODUCT
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS "Product" (
  id                       uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  created_date             timestamptz DEFAULT now(),
  updated_date             timestamptz DEFAULT now(),
  nombre                   text        NOT NULL,
  descripcion              text,
  clasificacion_arancelaria text        NOT NULL,
  arancel                  numeric,
  precio_referencial       numeric,
  peso_unitario            numeric,
  categoria                text,
  proveedor                text
);

-- ─────────────────────────────────────────
-- 2. ORDER
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS "Order" (
  id             uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  created_date   timestamptz DEFAULT now(),
  updated_date   timestamptz DEFAULT now(),
  numero_pedido  text        NOT NULL,
  cliente        text        NOT NULL,
  fecha_pedido   date,
  notas          text
);

-- ─────────────────────────────────────────
-- 3. ORDER ITEM
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS "OrderItem" (
  id                   uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  created_date         timestamptz DEFAULT now(),
  updated_date         timestamptz DEFAULT now(),
  pedido_id            text        NOT NULL,
  pedido_numero        text,
  producto_id          text,
  producto_nombre      text        NOT NULL,
  cantidad             numeric     NOT NULL,
  fecha_entrega_orden  date        NOT NULL,
  precio_compra        numeric,
  precio_venta         numeric,
  estado               text        DEFAULT 'adjudicado'
                         CHECK (estado IN (
                           'adjudicado','comprado','transito',
                           'en_bodega','en_aduana','enviado_cliente','entregado'
                         )),
  fecha_compra         date,
  tracking_number      text,
  fecha_miami          date,
  wr_bodega            text,
  awb                  text,
  fecha_aduana         date,
  numero_guia          text,
  fecha_entrega        date,
  prueba_entrega       text
);

-- ─────────────────────────────────────────
-- 4. INVOICE
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS "Invoice" (
  id                 uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  created_date       timestamptz DEFAULT now(),
  updated_date       timestamptz DEFAULT now(),
  numero_factura     text        NOT NULL,
  pedido_id          text,
  pedido_numero      text        NOT NULL,
  cliente            text        NOT NULL,
  monto_total        numeric     NOT NULL,
  estado             text        DEFAULT 'pendiente'
                       CHECK (estado IN ('pendiente','facturado','retencion','pagado')),
  fecha_emision      date,
  fecha_vencimiento  date,
  fecha_pago         date,
  archivo_pdf        text,
  archivo_xml        text,
  monto_retencion    numeric,
  notas              text
);

-- ─────────────────────────────────────────
-- 5. ROW LEVEL SECURITY
--    App runs in open-access mode (no login required).
--    Policies allow any anonymous request to read/write all tables.
-- ─────────────────────────────────────────
ALTER TABLE "Product"   ENABLE ROW LEVEL SECURITY;
ALTER TABLE "Order"     ENABLE ROW LEVEL SECURITY;
ALTER TABLE "OrderItem" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "Invoice"   ENABLE ROW LEVEL SECURITY;

-- Full access for the anon role (matches VITE_SUPABASE_ANON_KEY)
DO $$
DECLARE
  tbl text;
BEGIN
  FOREACH tbl IN ARRAY ARRAY['Product','Order','OrderItem','Invoice'] LOOP
    EXECUTE format(
      'CREATE POLICY "anon_all" ON "%s" FOR ALL TO anon USING (true) WITH CHECK (true)',
      tbl
    );
  END LOOP;
END$$;

-- ─────────────────────────────────────────
-- 6. STORAGE BUCKET  (for file uploads)
-- ─────────────────────────────────────────
-- Creates the "uploads" bucket used by UploadFile integration.
-- Public so that publicUrl() works without a signed URL.
INSERT INTO storage.buckets (id, name, public)
VALUES ('uploads', 'uploads', true)
ON CONFLICT (id) DO NOTHING;

-- Allow anonymous uploads and reads
CREATE POLICY "anon_upload" ON storage.objects
  FOR INSERT TO anon
  WITH CHECK (bucket_id = 'uploads');

CREATE POLICY "anon_read" ON storage.objects
  FOR SELECT TO anon
  USING (bucket_id = 'uploads');
