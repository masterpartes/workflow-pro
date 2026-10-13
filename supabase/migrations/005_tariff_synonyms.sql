-- 005_tariff_synonyms.sql
-- Agrega a descripcion_referencial los sustantivos que la aduana realmente
-- uso para cada subpartida, tomados de 1.548 items de DESPACHO MASTERPARTES.
-- Solo se incluyen sustantivos cuya subpartida dominante supera el 80% de los casos.
-- Idempotente: si el sustantivo ya esta, no se duplica.
-- El lector separa por '/' y toma el nucleo de cada tramo, asi que cada
-- sustantivo de la lista puede cobrar el bono de nucleo (ver tariff_lookup.py).

update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%PARACHOQUES%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / PARACHOQUES' end
where subpartida = '8708.10.00.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%VINCHA%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / VINCHA' end
where subpartida = '8708.10.00.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%ABSORBEDOR%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / ABSORBEDOR' end
where subpartida = '8708.10.00.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%VIGA%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / VIGA' end
where subpartida = '8708.10.00.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%VINCHAS%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / VINCHAS' end
where subpartida = '8708.10.00.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%FARO%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / FARO' end
where subpartida = '8512.20.10.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%NEBLINERO%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / NEBLINERO' end
where subpartida = '8512.20.10.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%REFLECTOR%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / REFLECTOR' end
where subpartida = '8512.20.10.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%GUARDAPOLVO%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / GUARDAPOLVO' end
where subpartida = '8708.29.20.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%GUARDAFANGO%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / GUARDAFANGO' end
where subpartida = '8708.29.20.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%BUCHE%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / BUCHE' end
where subpartida = '8708.29.20.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%DEFLECTOR%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / DEFLECTOR' end
where subpartida = '8708.29.20.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%PUERTA%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / PUERTA' end
where subpartida = '8708.29.20.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%MANIJA%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / MANIJA' end
where subpartida = '8708.29.20.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%REJILLA%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / REJILLA' end
where subpartida = '8708.29.30.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%MASCARILLA%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / MASCARILLA' end
where subpartida = '8708.29.30.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%EMBLEMA%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / EMBLEMA' end
where subpartida = '8708.29.30.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%RADIADOR%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / RADIADOR' end
where subpartida = '8708.91.00.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%CONDENSADOR%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / CONDENSADOR' end
where subpartida = '8708.91.00.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%VENTILADOR%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / VENTILADOR' end
where subpartida = '8708.91.00.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%AMORTIGUADOR%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / AMORTIGUADOR' end
where subpartida = '8708.80.20.10';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%AMORTIGUADORES%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / AMORTIGUADORES' end
where subpartida = '8708.80.20.10';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%BRAZO%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / BRAZO' end
where subpartida = '8708.99.33.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%TENSIONADOR%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / TENSIONADOR' end
where subpartida = '7315.12.00.90';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%ALTERNADOR%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / ALTERNADOR' end
where subpartida = '7315.12.00.90';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%POLEA%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / POLEA' end
where subpartida = '7315.12.00.90';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%ARO%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / ARO' end
where subpartida = '8714.92.10.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%TERMINAL%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / TERMINAL' end
where subpartida = '8708.80.10.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%ROTULA%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / ROTULA' end
where subpartida = '8708.80.10.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%RESERVORIO%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / RESERVORIO' end
where subpartida = '3923.30.99.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%TANQUE%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / TANQUE' end
where subpartida = '3923.30.99.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%ESPEJO%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / ESPEJO' end
where subpartida = '7009.10.00.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%COMPRESOR%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / COMPRESOR' end
where subpartida = '8414.80.10.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%PARABRISAS%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / PARABRISAS' end
where subpartida = '7007.11.00.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%PASTILLAS%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / PASTILLAS' end
where subpartida = '8708.30.10.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%CHAPA%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / CHAPA' end
where subpartida = '8301.20.00.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%HERRAMIENTA%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / HERRAMIENTA' end
where subpartida = '8206.00.00.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%RUEDAS%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / RUEDAS' end
where subpartida = '8708.70.10.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%TERMOSTATO%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / TERMOSTATO' end
where subpartida = '9032.10.00.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%CILINDRO%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / CILINDRO' end
where subpartida = '8412.21.00.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%BASES%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / BASES' end
where subpartida = '8708.99.29.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%RODAMIENTO%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / RODAMIENTO' end
where subpartida = '8482.10.00.00';
update "TariffCode" set descripcion_referencial = case
  when upper(coalesce(descripcion_referencial,'')) like '%DEPURADOR%' then descripcion_referencial
  else trim(both ' /' from coalesce(descripcion_referencial,'')) || ' / DEPURADOR' end
where subpartida = '8421.31.00.00';

select subpartida, arancel, descripcion_referencial from "TariffCode"
where subpartida in ('3923.30.99.00', '7007.11.00.00', '7009.10.00.00', '7315.12.00.90', '8206.00.00.00', '8301.20.00.00', '8412.21.00.00', '8414.80.10.00', '8421.31.00.00', '8482.10.00.00', '8512.20.10.00', '8708.10.00.00', '8708.29.20.00', '8708.29.30.00', '8708.30.10.00', '8708.70.10.00', '8708.80.10.00', '8708.80.20.10', '8708.91.00.00', '8708.99.29.00', '8708.99.33.00', '8714.92.10.00', '9032.10.00.00')
order by subpartida;