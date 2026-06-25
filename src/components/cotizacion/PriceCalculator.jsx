import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Calculator, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function PriceCalculator({ selectedProduct, products, onProductSelect }) {
  const [fob, setFob] = useState(0);
  const [peso, setPeso] = useState(0);
  const [margen, setMargen] = useState(20.0);
  const [arancelCalculo, setArancelCalculo] = useState(0);
  const [iva, setIva] = useState(15.0);
  const [isd, setIsd] = useState(5.0);
  const [showAduanaDetails, setShowAduanaDetails] = useState(false);
  const [showSiatiDetails, setShowSiatiDetails] = useState(false);

  useEffect(() => {
    if (selectedProduct) {
      setFob(selectedProduct.precio_referencial || 0);
      setPeso(selectedProduct.peso_unitario || 0);
      setArancelCalculo(selectedProduct.arancel || 0);
    }
  }, [selectedProduct]);

  const handleProductSelect = (productId) => {
    const product = products.find(p => p.id === productId);
    if (product) onProductSelect(product);
  };

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
      <span className={`text-sm ${bold ? 'font-semibold' : 'text-slate-700'}`}>{label}</span>
      <span className={`text-right ${bold ? 'font-bold text-lg' : 'font-semibold'}`}>$ {typeof value === 'number' ? value.toFixed(2) : value}</span>
    </div>
  );

  const EditableField = ({ label, value, onChange, suffix = "", bgColor = "bg-green-50" }) => (
    <div className={`grid grid-cols-2 gap-2 py-2 px-3 items-center ${bgColor}`}>
      <Label className="text-sm font-medium text-slate-900">{label}</Label>
      <div className="relative">
        <Input type="number" step="0.01" value={value} onChange={(e) => onChange(e.target.value === '' ? 0 : parseFloat(e.target.value))} className="text-right font-semibold pr-12 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none" />
        {suffix && <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm font-medium text-slate-600 pointer-events-none">{suffix}</span>}
      </div>
    </div>
  );

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
        {products && products.length > 0 ? (
          <>
            <div className="p-4 space-y-3 bg-green-50 border-b-2 border-green-200">
              <div className="space-y-2">
                <Label className="text-sm font-semibold text-slate-900">PRODUCTO</Label>
                <Select value={selectedProduct?.id || ''} onValueChange={handleProductSelect}>
                  <SelectTrigger><SelectValue placeholder="Escoge un producto" /></SelectTrigger>
                  <SelectContent>
                    {products.map((product) => (
                      <SelectItem key={product.id} value={product.id}>{product.nombre}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {selectedProduct && (
                <>
                  <div className="grid grid-cols-2 gap-2 py-2">
                    <span className="text-sm font-medium text-slate-900">SUBPARTIDA</span>
                    <span className="text-right font-semibold text-blue-700">{selectedProduct.clasificacion_arancelaria}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 py-2">
                    <span className="text-sm font-medium text-slate-900">ARANCEL</span>
                    <span className="text-right font-semibold text-slate-900">{selectedProduct.arancel}%</span>
                  </div>
                </>
              )}
            </div>
            {selectedProduct ? (
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
            ) : (
              <div className="text-center py-12"><Calculator className="w-12 h-12 text-slate-300 mx-auto mb-3" /><p className="text-slate-600 text-sm">Selecciona un producto del menú para calcular precios</p></div>
            )}
          </>
        ) : (
          <div className="text-center py-12 px-4"><Calculator className="w-12 h-12 text-slate-300 mx-auto mb-3" /><p className="text-slate-600 text-sm mb-2">No hay productos disponibles</p></div>
        )}
      </CardContent>
    </Card>
  );
}