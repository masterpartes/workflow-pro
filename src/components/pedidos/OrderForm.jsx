import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { X, Save, Plus, Trash2, ChevronDown, ChevronRight, Truck } from "lucide-react";

const STATUS_OPTIONS = [
  { value: "adjudicado",      label: "Adjudicado" },
  { value: "comprado",        label: "Comprado" },
  { value: "transito",        label: "Tránsito" },
  { value: "en_bodega",       label: "En Bodega" },
  { value: "en_aduana",       label: "En Aduana" },
  { value: "enviado_cliente", label: "Enviado a Cliente" },
  { value: "entregado",       label: "Entregado" },
];

const EMPTY_ITEM = {
  producto_id: null,
  producto_nombre: "",
  cantidad: 1,
  fecha_entrega_orden: "",
  precio_compra: 0,
  precio_venta: 0,
  estado: "adjudicado",
  // logistics
  fecha_compra: "",
  tracking_number: "",
  fecha_miami: "",
  wr_bodega: "",
  awb: "",
  fecha_aduana: "",
  numero_guia: "",
  fecha_entrega: "",
};

// Returns true if any logistics field has a value — auto-expand on edit
const hasLogisticsData = (item) =>
  !!(item.fecha_compra || item.tracking_number || item.fecha_miami ||
     item.wr_bodega || item.awb || item.fecha_aduana || item.numero_guia || item.fecha_entrega);

export default function OrderForm({ order, orderItems, products, onSubmit, onCancel, isLoading }) {
  const [orderData, setOrderData] = useState(order || {
    numero_pedido: "",
    cliente: "",
    fecha_pedido: new Date().toISOString().split('T')[0],
    notas: "",
  });

  const initialItems = orderItems?.length > 0
    ? orderItems.map(i => ({ ...EMPTY_ITEM, ...i }))
    : [{ ...EMPTY_ITEM }];

  const [items, setItems] = useState(initialItems);

  // Which items have logistics expanded
  const [expandedLogistics, setExpandedLogistics] = useState(() => {
    const map = {};
    initialItems.forEach((item, i) => { if (hasLogisticsData(item)) map[i] = true; });
    return map;
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(orderData, items);
  };

  const handleOrderChange = (field, value) =>
    setOrderData(prev => ({ ...prev, [field]: value }));

  const handleItemChange = (index, field, value) => {
    const next = [...items];
    next[index] = { ...next[index], [field]: value };
    setItems(next);
  };

  const addItem = () => {
    setItems([...items, { ...EMPTY_ITEM }]);
  };

  const removeItem = (index) => {
    setItems(items.filter((_, i) => i !== index));
    setExpandedLogistics(prev => {
      const next = {};
      Object.entries(prev).forEach(([k, v]) => {
        const ki = parseInt(k);
        if (ki < index) next[ki] = v;
        else if (ki > index) next[ki - 1] = v;
      });
      return next;
    });
  };

  const toggleLogistics = (index) =>
    setExpandedLogistics(prev => ({ ...prev, [index]: !prev[index] }));

  return (
    <Card className="border-none shadow-lg">
      <CardHeader className="border-b border-slate-100">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-bold text-slate-900">
            {order ? "Editar Pedido" : "Nuevo Pedido"}
          </CardTitle>
          <Button variant="ghost" size="icon" onClick={onCancel}>
            <X className="w-5 h-5" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-6">
        <form onSubmit={handleSubmit} className="space-y-6">

          {/* ── Order header ── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="numero_pedido">Número de Pedido *</Label>
              <Input
                id="numero_pedido"
                value={orderData.numero_pedido}
                onChange={e => handleOrderChange("numero_pedido", e.target.value)}
                required
                placeholder="PED-001"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cliente">Cliente *</Label>
              <Input
                id="cliente"
                value={orderData.cliente}
                onChange={e => handleOrderChange("cliente", e.target.value)}
                required
                placeholder="Nombre del cliente"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fecha_pedido">Fecha del Pedido</Label>
              <Input
                id="fecha_pedido"
                type="date"
                value={orderData.fecha_pedido}
                onChange={e => handleOrderChange("fecha_pedido", e.target.value)}
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="notas">Notas</Label>
              <Textarea
                id="notas"
                value={orderData.notas || ""}
                onChange={e => handleOrderChange("notas", e.target.value)}
                placeholder="Notas adicionales"
                rows={2}
              />
            </div>
          </div>

          {/* ── Items ── */}
          <div className="border-t pt-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-slate-900">Productos del Pedido</h3>
              <Button type="button" onClick={addItem} variant="outline" size="sm">
                <Plus className="w-4 h-4 mr-2" />Agregar Producto
              </Button>
            </div>

            <div className="space-y-4">
              {items.map((item, index) => (
                <div key={index} className="border rounded-lg bg-slate-50 overflow-hidden">

                  {/* Item header */}
                  <div className="flex items-center justify-between px-4 py-3 bg-slate-100 border-b">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-slate-700">Producto {index + 1}</span>
                      {item.estado && item.estado !== "adjudicado" && (
                        <Badge variant="outline" className="text-xs">{STATUS_OPTIONS.find(s => s.value === item.estado)?.label}</Badge>
                      )}
                    </div>
                    {items.length > 1 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => removeItem(index)}
                        className="h-6 w-6 text-red-600"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    )}
                  </div>

                  <div className="p-4 space-y-4">
                    {/* Basic fields */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div className="space-y-2 md:col-span-2">
                        <Label>Producto *</Label>
                        <Input
                          placeholder="Nombre del producto"
                          value={item.producto_nombre || ""}
                          onChange={e => handleItemChange(index, 'producto_nombre', e.target.value)}
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Cantidad *</Label>
                        <Input
                          type="number"
                          min="1"
                          value={item.cantidad}
                          onChange={e => handleItemChange(index, 'cantidad', parseInt(e.target.value) || 1)}
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Fecha Entrega Estimada *</Label>
                        <Input
                          type="date"
                          value={item.fecha_entrega_orden || ""}
                          onChange={e => handleItemChange(index, 'fecha_entrega_orden', e.target.value)}
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Precio de Compra</Label>
                        <Input
                          type="number"
                          step="0.01"
                          value={item.precio_compra ?? 0}
                          onChange={e => handleItemChange(index, 'precio_compra', parseFloat(e.target.value) || 0)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Precio de Venta</Label>
                        <Input
                          type="number"
                          step="0.01"
                          value={item.precio_venta ?? 0}
                          onChange={e => handleItemChange(index, 'precio_venta', parseFloat(e.target.value) || 0)}
                        />
                      </div>
                    </div>

                    {/* Logistics toggle */}
                    <button
                      type="button"
                      onClick={() => toggleLogistics(index)}
                      className="flex items-center gap-2 text-sm font-medium text-purple-700 hover:text-purple-900 transition-colors"
                    >
                      <Truck className="w-4 h-4" />
                      Logística / Tracking
                      {expandedLogistics[index]
                        ? <ChevronDown className="w-4 h-4" />
                        : <ChevronRight className="w-4 h-4" />}
                    </button>

                    {/* Logistics fields */}
                    {expandedLogistics[index] && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-3 border-t border-slate-200">

                        <div className="space-y-2 md:col-span-2">
                          <Label>Estado</Label>
                          <Select
                            value={item.estado || "adjudicado"}
                            onValueChange={v => handleItemChange(index, 'estado', v)}
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {STATUS_OPTIONS.map(s => (
                                <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>

                        <div className="space-y-2">
                          <Label>Fecha de Compra</Label>
                          <Input
                            type="date"
                            value={item.fecha_compra || ""}
                            onChange={e => handleItemChange(index, 'fecha_compra', e.target.value)}
                          />
                        </div>

                        <div className="space-y-2">
                          <Label>Tracking Number</Label>
                          <Input
                            placeholder="ej. 1Z999AA10123456784"
                            value={item.tracking_number || ""}
                            onChange={e => handleItemChange(index, 'tracking_number', e.target.value)}
                          />
                        </div>

                        <div className="space-y-2">
                          <Label>Fecha Miami</Label>
                          <Input
                            type="date"
                            value={item.fecha_miami || ""}
                            onChange={e => handleItemChange(index, 'fecha_miami', e.target.value)}
                          />
                        </div>

                        <div className="space-y-2">
                          <Label>WR Bodega</Label>
                          <Input
                            placeholder="Warehouse receipt"
                            value={item.wr_bodega || ""}
                            onChange={e => handleItemChange(index, 'wr_bodega', e.target.value)}
                          />
                        </div>

                        <div className="space-y-2">
                          <Label>AWB</Label>
                          <Input
                            placeholder="Air waybill"
                            value={item.awb || ""}
                            onChange={e => handleItemChange(index, 'awb', e.target.value)}
                          />
                        </div>

                        <div className="space-y-2">
                          <Label>Fecha Aduana</Label>
                          <Input
                            type="date"
                            value={item.fecha_aduana || ""}
                            onChange={e => handleItemChange(index, 'fecha_aduana', e.target.value)}
                          />
                        </div>

                        <div className="space-y-2">
                          <Label>Número de Guía</Label>
                          <Input
                            placeholder="Guía de entrega"
                            value={item.numero_guia || ""}
                            onChange={e => handleItemChange(index, 'numero_guia', e.target.value)}
                          />
                        </div>

                        <div className="space-y-2">
                          <Label>Fecha de Entrega Real</Label>
                          <Input
                            type="date"
                            value={item.fecha_entrega || ""}
                            onChange={e => handleItemChange(index, 'fecha_entrega', e.target.value)}
                          />
                        </div>

                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button type="button" variant="outline" onClick={onCancel}>Cancelar</Button>
            <Button
              type="submit"
              disabled={isLoading}
              className="bg-gradient-to-r from-purple-600 to-indigo-600"
            >
              <Save className="w-4 h-4 mr-2" />
              {isLoading ? "Guardando..." : "Guardar Pedido"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
