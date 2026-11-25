-- 009_envio_clase.sql
-- Flete origen AVK (Vilnius -> Miami) por CLASE DE ENVIO, no por pieza.
-- Tarifa confirmada por el dueno 21-oct-2026: 6.33 EUR por kg volumetrico (divisor 5000).
-- Regla: en un mismo envio las piezas chicas viajan dentro de la caja grande
-- (caja de 720 EUR = parachoques + varias piezas, "el parachoques solo hubiera
-- costado lo mismo"). Las clases 'extra' NUNCA se estiman: se pide el volumen.

create table if not exists envio_clase (
  clase        text primary key,
  rango        int  not null,          -- 1 = la mas grande; manda en un envio mixto
  largo_cm     numeric,
  ancho_cm     numeric,
  alto_cm      numeric,
  vkg          numeric generated always as (largo_cm * ancho_cm * alto_cm / 5000.0) stored,
  pedir_volumen boolean not null default false,
  notas        text,
  updated_at   timestamptz not null default now()
);

insert into envio_clase (clase, rango, largo_cm, ancho_cm, alto_cm, pedir_volumen, notas) values
  ('extra',        0, null, null, null, true,  'Parabrisas, costados, tapizado de techo, protectores inferiores: pedir volumen al proveedor'),
  ('parachoques',  1, 170,  60,   50,   false, 'Dueno 21-oct-2026. Validado contra factura DHL 170x62x54 = 720 EUR'),
  ('mascarilla',   2, 130,  60,   30,   false, 'Dueno 21-oct-2026'),
  ('faro',         3,  70,  40,   30,   false, 'Dueno 21-oct-2026'),
  ('caja_pequena', 4,  40,  40,   40,   false, 'Modulos, cables, vinchas, etc. Dueno 21-oct-2026')
on conflict (clase) do update set rango = excluded.rango, largo_cm = excluded.largo_cm,
  ancho_cm = excluded.ancho_cm, alto_cm = excluded.alto_cm,
  pedir_volumen = excluded.pedir_volumen, notas = excluded.notas, updated_at = now();

insert into cost_params (key, value, unit, notes, source)
values ('avk_freight_eur_vkg', 6.33, 'EUR per volumetric kg (divisor 5000)',
        'Vilnius -> Miami. Se aplica al vkg de la clase mas grande del envio.',
        'Dueno 21-oct-2026; factura DHL 720 EUR / 113.8 vkg')
on conflict (key) do update set value = excluded.value, unit = excluded.unit,
  notes = excluded.notes, source = excluded.source;

-- Palabra clave (descripcion Audatex/Inpart, en mayusculas) -> clase.
-- PROPUESTA: revisar con el dueno antes de usar en cotizaciones.
create table if not exists envio_clase_palabra (
  palabra text primary key,
  clase   text not null references envio_clase(clase)
);

insert into envio_clase_palabra (palabra, clase) values
  ('PARABRISAS','extra'), ('VIDRIO','extra'), ('COSTADO','extra'), ('TAPIZADO','extra'),
  ('PROTECTOR INFERIOR','extra'), ('CAPOT','extra'), ('CAPO','extra'), ('PUERTA','extra'),
  ('COMPUERTA','extra'), ('TECHO','extra'),
  ('PARACHOQUE','parachoques'), ('PARACHOQUES','parachoques'), ('FASCIA','parachoques'),
  ('MASCARILLA','mascarilla'), ('PARRILLA','mascarilla'), ('GUARDAFANGO','mascarilla'),
  ('RADIADOR','mascarilla'), ('CONDENSADOR','mascarilla'), ('INTERCOOLER','mascarilla'),
  ('VIGA','mascarilla'), ('ALMA','mascarilla'), ('REFUERZO','mascarilla'),
  ('FARO','faro'), ('STOP','faro'), ('CALAVERA','faro'), ('NEBLINERO','faro'),
  ('ESPEJO','faro'), ('DEPOSITO','faro'), ('GUARDAPOLVO','faro'), ('DUCTO','faro'),
  ('MODULO','caja_pequena'), ('SENSOR','caja_pequena'), ('CABLE','caja_pequena'),
  ('VINCHA','caja_pequena'), ('CLIP','caja_pequena'), ('EMBLEMA','caja_pequena'),
  ('MANIJA','caja_pequena'), ('SOPORTE','caja_pequena'), ('BASE','caja_pequena'),
  ('CROMADO','caja_pequena'), ('MOLDURA','caja_pequena'), ('BOCEL','caja_pequena'),
  ('LUZ','caja_pequena'), ('ABSORBEDOR','caja_pequena'), ('REJILLA','caja_pequena')
on conflict (palabra) do update set clase = excluded.clase;
