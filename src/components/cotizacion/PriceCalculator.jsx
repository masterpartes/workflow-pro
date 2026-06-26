import React, { useState, useEffect, useRef } from "react";
import { base44 } from "@/api/base44Client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Calculator, ChevronDown, ChevronRight, Search, Plus, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

// ─── Tariff Combobox ────────────────────────────────────────────────────────

function TariffCombobox({ tariffCodes, selectedTariff, onSelect, onCustom }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef(null);
  const dropdownRef = useRef(null);

  // Sync display value when tariff is selected from outside (e.g. catalog click)
  useEffect(() => {
    if (selectedTariff) {
      setQuery(selectedTariff.descripcion_referencial);
    }
  }, [selectedTariff]);

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target) &&
        inputRef.current && !inputRef.current.contains(e.target)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = query.trim().length === 0
    ? tariffCodes.slice(0, 20)
    : tariffCodes.filter(t =>
        t.descripcion_referencial.toLowerCase().includes(query.toLowerCase()) ||
        t.subpartida.toLowerCase().includes(query.toLowerCase())
      ).slice(0, 20);

  const handleInputChange = (e) => {
    setQuery(e.target.value);
    setOpen(true);
  };

  const handleSelect = (tariff) => {
    setQuery(tariff.descripcion_referencial);
    setOpen(false);
    onSelect(tariff);
  };

  const handleCustom = () => {
    setOpen(false);
    onCustom(query);
  };

  const handleFocus = () => {
    setOpen(true);
    if (query) setQuery("");
  };

  return (
    <div className="relative">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        <Input
          ref={inputRef}
          value={query}
          onChange={handleInputChange}
          onFocus={handleFocus}
          placeholder="Buscar clasificación arancelaria..."
          className="pl-9 font-medium"
        />
      </div>

      {open && (
        <div
          ref={dropdownRef}
          className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-xl max-h-72 overflow-y-auto"
        >
          {filtered.length > 0 ? (
            filtered.map((tariff) => (
              <button
                key={tariff.id}
                type="button"
                onClick={() => handleSelect(tariff)}
                className={`w-full text-left px-3 py-2.5 hover:bg-blue-50 border-b border-slate-100 last:border-0 transition-colors ${
                  selectedTariff?.id === tariff.id ? "bg-blue-50" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-medium text-slate-900 leading-tight">
                    {tariff.descripcion_referencial}
                    {tariff.es_personalizado && (
                      <Badge className="ml-2 text-xs bg-purple-100 text-purple-700 px-1 py-0">
                        Personalizado
                      </Badge>
                    )}
                  </span>
                  {selectedTariff?.id === tariff.id && (
                    <Check className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                  )}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">
                  {tariff.subpartida} · {tariff.arancel}% arancel
                </div>
              </button>
            ))
          ) : (
            <div className="px-3 py-2 text-sm text-slate-500">Sin resultados</div>
          )}

          {/* Always-visible custom option */}
          <button
            type="button"
            onClick={handleCustom}
            className="w-full text-left px-3 py-2.5 bg-purple-50 hover:bg-purple-100 border-t-2 border-purple-200 transition-colors flex items-center gap-2"
          >
            <Plus className="w-4 h-4 text-purple-600 shrink-0" />
            <div>
              <div className="text-sm font-medium text-purple-700">
                {query.trim() ? `Personalizado: "${query}"` : "Agregar clasificación personalizada"}
              </div>
              <div className="text-xs text-purple-500">Guardar en la lista para uso futuro</div>
            </div>
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Custom Entry Form ───────────────────────────────────────────────────────

function CustomTariffForm({ initialName, onSave, onCancel, isSaving }) {
  const [nombre, setNombre] = useState(initialName || "");
  const [subpartida, setSubpartida] = useState("");
  const [arancel, setArancel] = useState("");

  return (
    <div className="space-y-3 p-3 bg-purple-50 rounded-lg border border-purple-200">
      <p className="text-xs font-semibold text-purple-700 uppercase tracking-wide">
        Nueva clasificación personalizada
      </p>
      <div className="space-y-2">
        <Label className="text-xs text-slate-700">Descripción del producto</Label>
        <Input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="ej. SENSOR MAP MOTOR"
          className="text-sm"
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-2">
          <Label className="text-xs text-slate-700">Subpartida (opcional)</Label>
          <Input
            value={subpartida}
            onChange={(e) => setSubpartida(e.target.value)}
            placeholder="ej. 9026.20.00.00"
            className="text-sm font-mono"
          />
        </div>
        <div className="space-y-2">
          <Label className="text-xs text-slate-700">Arancel %</Label>
          <div className="relative">
            <Input
              type="number"
              step="1"
              min="0"
              max="100"
              value={arancel}
              onChange={(e) => setArancel(e.target.value)}
              placeholder="0"
              className="text-sm pr-8"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-slate-500">%</span>
          </div>
        </div>
      </div>
      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={() => onSave({ nombre, subpartida, arancel: parseFloat(arancel) || 0 })}
          disabled={!nombre.trim() || isSaving}
          className="bg-purple-600 hover:bg-purple-700 text-white flex-1"
        >
          {isSaving ? "Guardando..." : "Guardar y usar"}
        </Button>
        <Button size="sm" variant="outline" onClick={onCancel} className="flex-1">
          Cancelar
        </Button>
      </div>
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function PriceCalculator({ selectedProduct, products, onProductSelect }) {
  const [fob, setFob] = useState(0);
  const [peso, setPeso] = useState(0);
  const [margen, setMargen] = useState(20.0);
  const [arancelCalculo, setArancelCalculo] = useState(0);
  const [iva, setIva] = useState(15.0);
  const [isd, setIsd] = useState(5.0);
  const [showAduanaDetails, setShowAduanaDetails] = useState(false);
  const [showSiatiDetails, setShowSiatiDetails] = useState(false);

  // Tariff combobox state
  const [selectedTariff, setSelectedTariff] = useState(null);
  const [subpartida, setSubpartida] = useState("");
  const [showCustomForm, setShowCustomForm] = useState(false);
  const [customInitialName, setCustomInitialName] = useState("");

  const queryClient = useQueryClient();

  const { data: tariffCodes = [] } = useQuery({
    queryKey: ["tariffCodes"],
    queryFn: () => base44.entities.TariffCode.list("descripcion_referencial"),
    staleTime: 5 * 60 * 1000,
  });

  const saveTariffMutation = useMutation({
    mutationFn: (entry) => base44.entities.TariffCode.create(entry),
    onSuccess: (newEntry) => {
      queryClient.invalidateQueries({ queryKey: ["tariffCodes"] });
      // Auto-select the newly created entry
      setSelectedTariff(newEntry);
      setSubpartida(newEntry.subpartida || "");
      setArancelCalculo(newEntry.arancel || 0);
      setShowCustomForm(false);
    },
  });

  // When the catalog selects a product, pre-fill FOB + PESO and try to match tariff
  useEffect(() => {
    if (selectedProduct) {
      setFob(selectedProduct.precio_referencial || 0);
      setPeso(selectedProduct.peso_unitario || 0);
      // Try to match existing tariff by clasificacion_arancelaria
      if (tariffCodes.length > 0 && selectedProduct.clasificacion_arancelaria) {
        const match = tariffCodes.find(
          t => t.subpartida === selectedProduct.clasificacion_arancelaria
        );
        if (match) {
          setSelectedTariff(match);
          setSubpartida(match.subpartida);
          setArancelCalculo(match.arancel);
        } else {
          setSubpartida(selectedProduct.clasificacion_arancelaria || "");
          setArancelCalculo(selectedProduct.arancel || 0);
        }
      } else {
        setSubpartida(selectedProduct.clasificacion_arancelaria || "");
        setArancelCalculo(selectedProduct.arancel || 0);
      }
    }
  }, [selectedProduct, tariffCodes]);

  const handleTariffSelect = (tariff) => {
    setSelectedTariff(tariff);
    setSubpartida(tariff.subpartida);
    setArancelCalculo(tariff.arancel);
    setShowCustomForm(false);
  };

  const handleCustomClick = (initialName) => {
    setCustomInitialName(initialName);
    setShowCustomForm(true);
  };

  const handleSaveCustom = ({ nombre, subpartida: sp, arancel: ar }) => {
    saveTariffMutation.mutate({
      descripcion_referencial: nombre.trim().toUpperCase(),
      subpartida: sp.trim() || "XX.XX.XX.XX",
      arancel: ar,
      es_personalizado: true,
    });
  };

  // ── Calculations ──────────────────────────────────────────────────────────
  const insurance = 0.01 * fob;
  const freight = 1.57 * peso;
  const cif = fob + insurance + freight;
  const advalorem = cif * (arancelCalculo / 100);
  const fondinfa = 0.005 * cif;
  const ivaAduana = (iva / 100) * (cif + advalorem + fondinfa);
  const totalAduana = advalorem + fondinfa + ivaAduana;
  const salidaDivisas = fob * (isd / 100);
  const fleteSiati = 3.7 * peso * (1 + iva / 100);
  const fuelCourier = 0.027 * fleteSiati;
  const rayosX = 0.017 * fleteSiati;
  const tramite = (30 / 35) * peso * (1 + iva / 100);
  const totalSiati = fleteSiati + fuelCourier + rayosX + tramite;
  const precioUio = fob + salidaDivisas + totalAduana + totalSiati;
  const ganancia = (margen / 100) * precioUio;
  const creditoIvaAduana = ivaAduana;
  const precioOferta = precioUio + ganancia - creditoIvaAduana;

  const FieldRow = ({ label, value, bgColor = "bg-white", bold = false }) => (
    <div className={`grid grid-cols-2 gap-2 py-2 px-3 ${bgColor}`}>
      <span className={`text-sm ${bold ? "font-semibold" : "text-slate-700"}`}>{label}</span>
      <span className={`text-right ${bold ? "font-bold text-lg" : "font-semibold"}`}>
        $ {typeof value === "number" ? value.toFixed(2) : value}
      </span>
    </div>
  );

  const EditableField = ({ label, value, onChange, suffix = "", bgColor = "bg-green-50" }) => (
    <div className={`grid grid-cols-2 gap-2 py-2 px-3 items-center ${bgColor}`}>
      <Label className="text-sm font-medium text-slate-900">{label}</Label>
      <div className="relative">
        <Input
          type="number"
          step="0.01"
          value={value}
          onChange={(e) => onChange(e.target.value === "" ? 0 : parseFloat(e.target.value))}
          className="text-right font-semibold pr-12 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
        />
        {suffix && (
          <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm font-medium text-slate-600 pointer-events-none">
            {suffix}
          </span>
        )}
      </div>
    </div>
  );

  const hasSelection = selectedTariff || subpartida;

  return (
    <Card className="border-none shadow-lg">
      <CardHeader className="border-b border-slate-100 bg-gradient-to-r from-blue-50 to-indigo-50">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-lg flex items-center justify-center">
            <Calculator className="w-5 h-5 text-white" />
          </div>
          <CardTitle className="text-lg font-bold text-slate-900">Calculadora de Precios</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="p-4 space-y-3 bg-green-50 border-b-2 border-green-200">
          <div className="space-y-2">
            <Label className="text-sm font-semibold text-slate-900">PRODUCTO</Label>
            <TariffCombobox
              tariffCodes={tariffCodes}
              selectedTariff={selectedTariff}
              onSelect={handleTariffSelect}
              onCustom={handleCustomClick}
            />
          </div>

          {showCustomForm && (
            <CustomTariffForm
              initialName={customInitialName}
              onSave={handleSaveCustom}
              onCancel={() => setShowCustomForm(false)}
              isSaving={saveTariffMutation.isPending}
            />
          )}

          {hasSelection && !showCustomForm && (
            <>
              <div className="grid grid-cols-2 gap-2 py-2">
                <span className="text-sm font-medium text-slate-900">SUBPARTIDA</span>
                <span className="text-right font-semibold text-blue-700 font-mono text-sm">
                  {subpartida || "—"}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 py-2">
                <span className="text-sm font-medium text-slate-900">ARANCEL</span>
                <span className="text-right font-semibold text-slate-900">{arancelCalculo}%</span>
              </div>
            </>
          )}
        </div>

        {hasSelection && !showCustomForm ? (
          <>
            <div className="border-b-2 border-slate-200">
              <EditableField label="FOB" value={fob} onChange={setFob} suffix="$" />
              <EditableField label="PESO" value={peso} onChange={setPeso} suffix="KG" />
              <EditableField label="MARGEN" value={margen} onChange={setMargen} suffix="%" />
            </div>
            <div className="border-b-2 border-slate-200 bg-blue-50">
              <EditableField label="ARANCEL_CALCULO" value={arancelCalculo} onChange={setArancelCalculo} suffix="%" bgColor="bg-blue-50" />
              <EditableField label="IVA" value={iva} onChange={setIva} suffix="%" bgColor="bg-blue-50" />
              <EditableField label="ISD" value={isd} onChange={setIsd} suffix="%" bgColor="bg-blue-50" />
            </div>
            <div className="border-b-2 border-slate-300">
              <Button variant="ghost" onClick={() => setShowAduanaDetails(!showAduanaDetails)} className="w-full justify-between py-2 px-3 hover:bg-slate-50">
                <span className="text-sm font-semibold text-slate-900">DETALLES ADUANA</span>
                {showAduanaDetails ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
              </Button>
              {showAduanaDetails && (
                <div className="bg-slate-50">
                  <FieldRow label="INSURANCE" value={insurance} bgColor="bg-white" />
                  <FieldRow label="FREIGHT" value={freight} bgColor="bg-slate-50" />
                  <FieldRow label="CIF" value={cif} bgColor="bg-white" />
                  <FieldRow label="ADVALOREM" value={advalorem} bgColor="bg-slate-50" />
                  <FieldRow label="FONDINFA" value={fondinfa} bgColor="bg-white" />
                  <FieldRow label="IVA_ADUANA" value={ivaAduana} bgColor="bg-slate-50" />
                </div>
              )}
              <FieldRow label="TOTAL_ADUANA" value={totalAduana} bold bgColor="bg-slate-100" />
            </div>
            <div className="border-b-2 border-slate-300">
              <Button variant="ghost" onClick={() => setShowSiatiDetails(!showSiatiDetails)} className="w-full justify-between py-2 px-3 hover:bg-slate-50">
                <span className="text-sm font-semibold text-slate-900">DETALLES SIATI</span>
                {showSiatiDetails ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
              </Button>
              {showSiatiDetails && (
                <div className="bg-slate-50">
                  <FieldRow label="SALIDA_DIVISAS" value={salidaDivisas} bgColor="bg-white" />
                  <FieldRow label="FLETE_SIATI" value={fleteSiati} bgColor="bg-slate-50" />
                  <FieldRow label="FUEL_COURIER" value={fuelCourier} bgColor="bg-white" />
                  <FieldRow label="RAYOS_X" value={rayosX} bgColor="bg-slate-50" />
                  <FieldRow label="TRAMITE" value={tramite} bgColor="bg-white" />
                </div>
              )}
              <FieldRow label="TOTAL_SIATI" value={totalSiati} bold bgColor="bg-slate-100" />
            </div>
            <div className="border-b-2 border-amber-400">
              <FieldRow label="PRECIO_UIO" value={precioUio} bold bgColor="bg-amber-100" />
              <FieldRow label="GANANCIA" value={ganancia} bgColor="bg-white" />
              <FieldRow label="CREDITO_IVA_ADUANA" value={creditoIvaAduana} bgColor="bg-slate-50" />
            </div>
            <div className="bg-amber-200 border-b-2 border-amber-500">
              <FieldRow label="PRECIO_OFERTA" value={precioOferta} bold bgColor="bg-amber-200" />
            </div>
          </>
        ) : !showCustomForm ? (
          <div className="text-center py-12">
            <Calculator className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-600 text-sm">Busca un producto para calcular precios</p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
