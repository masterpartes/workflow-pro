import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { X, Save, Plus, Trash2 } from "lucide-react";

export default function OrderForm({ order, orderItems, products, onSubmit, onCancel, isLoading }) {
  const [orderData, setOrderData] = useState(order || {
    numero_pedido: "",
    cliente: "",
    fecha_pedido: new Date().toISOString().split('T')[0],
    notas: "",
  });

  const [items, setItems] = useState(orderItems?.length > 0 ? orderItems : [{
    producto_id: "",
    producto_nombre: "",
    cantidad: 1,
    fecha_entrega_orden: "",
    precio_compra: 0,
    precio_venta: 0,
  }]);

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(orderData, items);
  };

  const handleOrderChange = (field, value) => {
    setOrderData(prev => ({ ...prev, [field]: value }));
  };

  const handleItemChange = (index, field, value) => {
    const newItems = [...items];
    newItems[index] = { ...newItems[index], [field]: value };
    setItems(newItems);
  };

  const addItem = () => {
    setItems([...items, {
      producto_id: "",
      producto_nombre: "",
      cantidad: 1,
      fecha_entrega_orden: "",
      precio_compra: 0,
      precio_venta: 0,
    }]);
  };

  const removeItem = (index) => {
    setItems(items.filter((_, i) => i !== index));
  };

  return (
    <Card className="border-none shadow-lg">
      <CardHeader className="border-b border-slate-100">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-bold text-slate-900">{order ? "Editar Pedido" : "Nuevo Pedido"}</CardTitle>
          <Button variant="ghost" size="icon" onClick={onCancel}>
            <X className="w-5 h-5" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="numero_pedido">Número de Pedido *</Label>
              <Input id="numero_pedido" value={orderData.numero_pedido} onChange={(e) => handleOrderChange("numero_pedido", e.target.value)} required placeholder="PED-001" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cliente">Cliente *</Label>
              <Input id="cliente" value={orderData.cliente} onChange={(e) => handleOrderChange("cliente", e.target.value)} required placeholder="Nombre del cliente" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fecha_pedido">Fecha del Pedido</Label>
              <Input id="fecha_pedido" type="date" value={orderData.fecha_pedido} onChange={(e) => handleOrderChange("fecha_pedido", e.target.value)} />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label htmlFor="notas">Notas</Label>
              <Textarea id="notas" value={orderData.notas} onChange={(e) => handleOrderChange("notas", e.target.value)} placeholder="Notas adicionales" rows={2} />
            </div>
          </div>
          <div className="border-t pt-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-slate-900">Productos del Pedido</h3>
              <Button type="button" onClick={addItem} variant="outline" size="sm">
                <Plus className="w-4 h-4 mr-2" />Agregar Producto
              </Button>
            </div>
            <div className="space-y-4">
              {items.map((item, index) => (
                <div key={index} className="p-4 border rounded-lg bg-slate-50 space-y-3">
                  <div className="flex items-start justify-between">
                    <span className="text-sm font-medium text-slate-700">Producto {index + 1}</span>
                    {items.length > 1 && (
                      <Button type="button" variant="ghost" size="icon" onClick={() => removeItem(index)} className="h-6 w-6 text-red-600">
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="space-y-2 md:col-span-2">
                      <Label>Producto *</Label>
                      <Input placeholder="Nombre del producto" value={item.producto_nombre} onChange={(e) => handleItemChange(index, 'producto_nombre', e.target.value)} required />
                    </div>
                    <div className="space-y-2">
                      <Label>Cantidad *</Label>
                      <Input type="number" min="1" value={item.cantidad} onChange={(e) => handleItemChange(index, 'cantidad', parseInt(e.target.value) || 1)} required />
                    </div>
                    <div className="space-y-2">
                      <Label>Fecha Entrega Orden *</Label>
                      <Input type="date" value={item.fecha_entrega_orden} onChange={(e) => handleItemChange(index, 'fecha_entrega_orden', e.target.value)} required />
                    </div>
                    <div className="space-y-2">
                      <Label>Precio de Compra</Label>
                      <Input type="number" step="0.01" value={item.precio_compra} onChange={(e) => handleItemChange(index, 'precio_compra', parseFloat(e.target.value) || 0)} />
                    </div>
                    <div className="space-y-2">
                      <Label>Precio de Venta</Label>
                      <Input type="number" step="0.01" value={item.precio_venta} onChange={(e) => handleItemChange(index, 'precio_venta', parseFloat(e.target.value) || 0)} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button type="button" variant="outline" onClick={onCancel}>Cancelar</Button>
            <Button type="submit" disabled={isLoading} className="bg-gradient-to-r from-purple-600 to-indigo-600">
              <Save className="w-4 h-4 mr-2" />{isLoading ? "Guardando..." : "Guardar Pedido"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}