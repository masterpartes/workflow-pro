import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Trash2, Package, ChevronDown, ChevronRight,
  Plus, CheckSquare, Search, X, Save
} from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

// ─── Inline New Product Form ────────────────────────────────────────────────

function NewProductForm({ onSubmit, onCancel, isLoading }) {
  const [form, setForm] = useState({
    nombre: "", descripcion: "",
    clasificacion_arancelaria: "", arancel: "",
    precio_referencial: "", peso_unitario: "",
  });
  const set = (field, val) => setForm(prev => ({ ...prev, [field]: val }));

  return (
    <div className="border-2 border-blue-200 rounded-xl bg-blue-50 p-4 space-y-3">
      <p className="text-sm font-semibold text-blue-700 uppercase tracking-wide">Nuevo Producto</p>
      <div className="grid grid-cols-2 gap-2">
        <div className="col-span-2 space-y-1">
          <Label className="text-xs">Número de Parte / Nombre *</Label>
          <Input value={form.nombre} onChange={e => set("nombre", e.target.value)}
            placeholder="ej. TECHO CORREDIZO BMW X5" className="text-sm" />
        </div>
        <div className="col-span-2 space-y-1">
          <Label className="text-xs">Descripción</Label>
          <Input value={form.descripcion} onChange={e => set("descripcion", e.target.value)}
            placeholder="Descripción del producto" className="text-sm" />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Clasificación</Label>
          <Input value={form.clasificacion_arancelaria} onChange={e => set("clasificacion_arancelaria", e.target.value)}
            placeholder="8708.29.90.90" className="text-sm font-mono" />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Arancel %</Label>
          <Input type="number" step="1" value={form.arancel} onChange={e => set("arancel", e.target.value)}
            placeholder="15" className="text-sm" />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Precio Ref. ($)</Label>
          <Input type="number" step="0.01" value={form.precio_referencial} onChange={e => set("precio_referencial", e.target.value)}
            placeholder="0.00" className="text-sm" />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Peso (kg)</Label>
          <Input type="number" step="0.01" value={form.peso_unitario} onChange={e => set("peso_unitario", e.target.value)}
            placeholder="0.00" className="text-sm" />
        </div>
      </div>
      <div className="flex gap-2 pt-1">
        <Button size="sm" disabled={!form.nombre.trim() || isLoading}
          onClick={() => onSubmit({
            ...form,
            arancel: parseFloat(form.arancel) || 0,
            precio_referencial: parseFloat(form.precio_referencial) || 0,
            peso_unitario: parseFloat(form.peso_unitario) || 0,
          })}
          className="bg-blue-600 hover:bg-blue-700 text-white flex-1">
          <Save className="w-3 h-3 mr-1" />
          {isLoading ? "Guardando..." : "Guardar"}
        </Button>
        <Button size="sm" variant="outline" onClick={onCancel} className="flex-1">
          <X className="w-3 h-3 mr-1" /> Cancelar
        </Button>
      </div>
    </div>
  );
}

// ─── Sales History Row ────────────────────────────────────────────────────────

function SalesHistory({ productName, orderItems, orders }) {
  const sales = orderItems
    .filter(item => item.producto_nombre === productName)
    .map(item => {
      const order = orders.find(o => o.id === item.pedido_id);
      return {
        id: item.id,
        pedido: item.pedido_numero || order?.numero_pedido || "—",
        cliente: order?.cliente || "—",
        fecha: order?.fecha_pedido || order?.created_date,
        cantidad: item.cantidad,
        precio_compra: item.precio_compra,
        precio_venta: item.precio_venta,
        estado: item.estado,
      };
    })
    .sort((a, b) => new Date(b.fecha) - new Date(a.fecha));

  if (sales.length === 0) {
    return <p className="text-xs text-slate-400 italic px-1 py-2">Sin ventas registradas</p>;
  }

  return (
    <div className="mt-2 overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-slate-200">
            <th className="text-left py-1 px-2 text-slate-500 font-medium">Pedido</th>
            <th className="text-left py-1 px-2 text-slate-500 font-medium">Cliente</th>
            <th className="text-left py-1 px-2 text-slate-500 font-medium">Fecha</th>
            <th className="text-right py-1 px-2 text-slate-500 font-medium">Cant.</th>
            <th className="text-right py-1 px-2 text-slate-500 font-medium">P. Compra</th>
            <th className="text-right py-1 px-2 text-slate-500 font-medium">P. Venta</th>
          </tr>
        </thead>
        <tbody>
          {sales.map(s => (
            <tr key={s.id} className="border-b border-slate-100 last:border-0">
              <td className="py-1 px-2 font-mono text-slate-700">{s.pedido}</td>
              <td className="py-1 px-2 text-slate-700">{s.cliente}</td>
              <td className="py-1 px-2 text-slate-500">
                {s.fecha ? new Date(s.fecha).toLocaleDateString("es-EC") : "—"}
              </td>
              <td className="py-1 px-2 text-right text-slate-700">{s.cantidad}</td>
              <td className="py-1 px-2 text-right text-slate-700">
                {s.precio_compra ? `$${Number(s.precio_compra).toFixed(2)}` : "—"}
              </td>
              <td className="py-1 px-2 text-right font-semibold text-blue-700">
                {s.precio_venta ? `$${Number(s.precio_venta).toFixed(2)}` : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function ProductList({
  products, isLoading, onDelete, onSelect, selectedProduct,
  onCreate, isCreating,
  orderItems = [], orders = [],
}) {
  const [expanded, setExpanded] = useState({});
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [selectionMode, setSelectionMode] = useState(false);
  const [showNewForm, setShowNewForm] = useState(false);
  const [search, setSearch] = useState("");

  const toggleExpand = id => setExpanded(prev => ({ ...prev, [id]: !prev[id] }));

  const toggleSelect = id => setSelectedIds(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  const handleSelectAll = checked => {
    setSelectedIds(checked ? new Set(filtered.map(p => p.id)) : new Set());
  };

  const handleBulkDelete = () => {
    if (confirm(`¿Eliminar ${selectedIds.size} producto${selectedIds.size !== 1 ? "s" : ""}? Esta acción no se puede deshacer.`)) {
      onDelete([...selectedIds]);
      setSelectedIds(new Set());
      setSelectionMode(false);
    }
  };

  const filtered = products.filter(p =>
    !search ||
    p.nombre?.toLowerCase().includes(search.toLowerCase()) ||
    p.clasificacion_arancelaria?.toLowerCase().includes(search.toLowerCase()) ||
    p.descripcion?.toLowerCase().includes(search.toLowerCase())
  );

  const allSelected = filtered.length > 0 && filtered.every(p => selectedIds.has(p.id));

  if (isLoading) {
    return (
      <Card className="border-none shadow-lg">
        <CardHeader><CardTitle>Catálogo de Productos</CardTitle></CardHeader>
        <CardContent className="p-6">
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="p-3 border rounded-lg space-y-2">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-3 w-full" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-none shadow-lg">
      <CardHeader className="border-b border-slate-100 pb-3">
        <div className="flex items-center justify-between mb-3">
          <CardTitle className="text-lg font-bold text-slate-900">
            Catálogo de Productos
            <span className="ml-2 text-sm font-normal text-slate-400">({products.length})</span>
          </CardTitle>
          <div className="flex gap-2">
            <Button
              variant={selectionMode ? "default" : "outline"}
              size="sm"
              onClick={() => { setSelectionMode(p => !p); setSelectedIds(new Set()); setShowNewForm(false); }}
              className={selectionMode ? "bg-purple-600 hover:bg-purple-700 text-white" : ""}
            >
              <CheckSquare className="w-4 h-4 mr-1" />
              {selectionMode ? "Cancelar" : "Seleccionar"}
            </Button>
            {!selectionMode && (
              <Button size="sm" onClick={() => setShowNewForm(p => !p)}
                className="bg-blue-600 hover:bg-blue-700 text-white">
                <Plus className="w-4 h-4 mr-1" />
                Nuevo
              </Button>
            )}
          </div>
        </div>

        {/* Search */}
        {!selectionMode && (
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
            <Input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Buscar producto..." className="pl-8 h-8 text-sm" />
          </div>
        )}

        {/* Bulk action bar */}
        {selectionMode && selectedIds.size > 0 && (
          <div className="flex items-center gap-3 p-2 bg-purple-50 rounded-lg border border-purple-200 mt-2">
            <Checkbox checked={allSelected} onCheckedChange={handleSelectAll} className="h-4 w-4" />
            <span className="text-sm font-semibold text-purple-700 flex-1">
              {selectedIds.size} seleccionado{selectedIds.size !== 1 ? "s" : ""}
            </span>
            <Button size="sm" onClick={handleBulkDelete}
              className="bg-red-600 hover:bg-red-700 text-white">
              <Trash2 className="w-3.5 h-3.5 mr-1" /> Eliminar
            </Button>
          </div>
        )}
        {selectionMode && selectedIds.size === 0 && (
          <div className="flex items-center gap-3 p-2 bg-slate-50 rounded-lg border border-slate-200 mt-2">
            <Checkbox checked={false} onCheckedChange={handleSelectAll} className="h-4 w-4" />
            <span className="text-sm text-slate-500">Selecciona productos para eliminar</span>
          </div>
        )}
      </CardHeader>

      <CardContent className="p-4 space-y-2 max-h-[calc(100vh-280px)] overflow-y-auto">
        {/* Inline new product form */}
        {showNewForm && !selectionMode && (
          <NewProductForm
            onSubmit={async (data) => { await onCreate(data); setShowNewForm(false); }}
            onCancel={() => setShowNewForm(false)}
            isLoading={isCreating}
          />
        )}

        {filtered.length === 0 && !showNewForm ? (
          <div className="text-center py-12">
            <Package className="w-14 h-14 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500 text-sm">
              {search ? "Sin resultados para la búsqueda" : "No hay productos en el catálogo"}
            </p>
          </div>
        ) : (
          filtered.map(product => {
            const isChecked = selectedIds.has(product.id);
            const isSelected = selectedProduct?.id === product.id;
            const isExpanded = expanded[product.id];
            const salesCount = orderItems.filter(i => i.producto_nombre === product.nombre).length;

            return (
              <div key={product.id}
                className={`rounded-xl border-2 transition-all ${
                  isChecked ? "border-purple-400 bg-purple-50"
                  : isSelected ? "border-blue-400 bg-blue-50"
                  : "border-slate-200 hover:border-slate-300 bg-white"
                }`}>
                {/* Main row */}
                <div
                  className="p-3 cursor-pointer"
                  onClick={() => selectionMode ? toggleSelect(product.id) : onSelect(product)}
                >
                  <div className="flex items-start gap-2">
                    {selectionMode && (
                      <Checkbox
                        checked={isChecked}
                        onCheckedChange={() => toggleSelect(product.id)}
                        onClick={e => e.stopPropagation()}
                        className="h-4 w-4 mt-0.5 shrink-0"
                      />
                    )}
                    <div className="flex-1 min-w-0">
                      {/* Name row */}
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-semibold text-slate-900 text-sm truncate">{product.nombre}</p>
                        {!selectionMode && (
                          <Button variant="ghost" size="icon"
                            className="h-6 w-6 text-slate-400 hover:text-red-500 shrink-0"
                            onClick={e => { e.stopPropagation(); if (confirm("¿Eliminar este producto?")) onDelete([product.id]); }}>
                            <Trash2 className="w-3.5 h-3.5" />
                          </Button>
                        )}
                      </div>

                      {/* Description */}
                      {product.descripcion && (
                        <p className="text-xs text-slate-500 truncate mt-0.5">{product.descripcion}</p>
                      )}

                      {/* Stat chips */}
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {product.clasificacion_arancelaria && (
                          <Badge variant="outline" className="text-xs font-mono px-1.5 py-0">
                            {product.clasificacion_arancelaria}
                          </Badge>
                        )}
                        {product.arancel != null && (
                          <Badge className="text-xs bg-orange-100 text-orange-700 px-1.5 py-0">
                            {product.arancel}%
                          </Badge>
                        )}
                        {product.precio_referencial != null && product.precio_referencial > 0 && (
                          <Badge className="text-xs bg-green-100 text-green-700 px-1.5 py-0">
                            ${Number(product.precio_referencial).toFixed(2)}
                          </Badge>
                        )}
                        {product.peso_unitario != null && product.peso_unitario > 0 && (
                          <Badge className="text-xs bg-slate-100 text-slate-600 px-1.5 py-0">
                            {product.peso_unitario} kg
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Sales history toggle */}
                  {!selectionMode && (
                    <button
                      type="button"
                      onClick={e => { e.stopPropagation(); toggleExpand(product.id); }}
                      className="mt-2 flex items-center gap-1 text-xs text-slate-500 hover:text-blue-600 transition-colors"
                    >
                      {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                      {salesCount > 0
                        ? `${salesCount} venta${salesCount !== 1 ? "s" : ""} registrada${salesCount !== 1 ? "s" : ""}`
                        : "Sin ventas"}
                    </button>
                  )}
                </div>

                {/* Expanded sales history */}
                {isExpanded && !selectionMode && (
                  <div className="px-3 pb-3 border-t border-slate-100">
                    <SalesHistory
                      productName={product.nombre}
                      orderItems={orderItems}
                      orders={orders}
                    />
                  </div>
                )}
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
