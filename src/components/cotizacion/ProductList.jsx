import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Pencil, Trash2, Package } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

export default function ProductList({ products, isLoading, onEdit, onDelete, onSelect, selectedProduct }) {
  if (isLoading) {
    return (
      <Card className="border-none shadow-lg">
        <CardHeader><CardTitle>Catálogo de Productos</CardTitle></CardHeader>
        <CardContent className="p-6"><div className="space-y-4">{[1,2,3].map(i => <div key={i} className="p-4 border rounded-lg"><Skeleton className="h-6 w-48 mb-2" /><Skeleton className="h-4 w-full" /></div>)}</div></CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-none shadow-lg">
      <CardHeader className="border-b border-slate-100">
        <CardTitle className="text-lg font-bold text-slate-900">Catálogo de Productos</CardTitle>
      </CardHeader>
      <CardContent className="p-6">
        {products.length === 0 ? (
          <div className="text-center py-12"><Package className="w-16 h-16 text-slate-300 mx-auto mb-4" /><p className="text-slate-600">No hay productos registrados</p></div>
        ) : (
          <div className="space-y-3">
            {products.map((product) => (
              <div key={product.id} onClick={() => onSelect(product)} className={`p-4 border rounded-xl transition-all cursor-pointer hover:shadow-md ${selectedProduct?.id === product.id ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:border-slate-300'}`}>
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <h3 className="font-semibold text-slate-900 mb-1">{product.nombre}</h3>
                    {product.descripcion && <p className="text-sm text-slate-600 mb-2">{product.descripcion}</p>}
                  </div>
                  <div className="flex gap-2 ml-4">
                    <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); onEdit(product); }} className="text-slate-600 hover:text-blue-600"><Pencil className="w-4 h-4" /></Button>
                    <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); onDelete(product.id); }} className="text-slate-600 hover:text-red-600"><Trash2 className="w-4 h-4" /></Button>
                  </div>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div><p className="text-xs text-slate-500 mb-1">Clasificación</p><Badge variant="outline" className="text-xs font-mono">{product.clasificacion_arancelaria}</Badge></div>
                  <div><p className="text-xs text-slate-500 mb-1">Arancel</p><p className="text-sm font-semibold text-slate-900">{product.arancel}%</p></div>
                  <div><p className="text-xs text-slate-500 mb-1">Precio Ref.</p><p className="text-sm font-semibold text-slate-900">${product.precio_referencial?.toFixed(2) || '0.00'}</p></div>
                  {product.peso_unitario && <div><p className="text-xs text-slate-500 mb-1">Peso</p><p className="text-sm font-semibold text-slate-900">{product.peso_unitario} kg</p></div>}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}