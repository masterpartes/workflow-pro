import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { X, Save } from "lucide-react";

export default function ProductForm({ product, onSubmit, onCancel, isLoading }) {
  const [formData, setFormData] = useState(product || {
    nombre: "", descripcion: "", clasificacion_arancelaria: "", arancel: 0,
    precio_referencial: 0, peso_unitario: 0, categoria: "", proveedor: "",
  });

  const handleSubmit = (e) => { e.preventDefault(); onSubmit(formData); };
  const handleChange = (field, value) => setFormData((prev) => ({ ...prev, [field]: value }));

  return (
    <Card className="border-none shadow-lg">
      <CardHeader className="border-b border-slate-100">
        <div className="flex items-center justify-between">
          <CardTitle>{product ? "Editar Producto" : "Nuevo Producto"}</CardTitle>
          <Button variant="ghost" size="icon" onClick={onCancel}><X className="w-5 h-5" /></Button>
        </div>
      </CardHeader>
      <CardContent className="p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2"><Label htmlFor="nombre">Nombre *</Label><Input id="nombre" value={formData.nombre} onChange={(e) => handleChange("nombre", e.target.value)} required placeholder="Ej: Laptop Dell XPS" /></div>
            <div className="space-y-2"><Label htmlFor="clasificacion">Clasificación Arancelaria *</Label><Input id="clasificacion" value={formData.clasificacion_arancelaria} onChange={(e) => handleChange("clasificacion_arancelaria", e.target.value)} required placeholder="Ej: 8471.30.00" /></div>
            <div className="space-y-2 md:col-span-2"><Label htmlFor="descripcion">Descripción</Label><Textarea id="descripcion" value={formData.descripcion} onChange={(e) => handleChange("descripcion", e.target.value)} rows={3} /></div>
            <div className="space-y-2"><Label htmlFor="arancel">Arancel (%)</Label><Input id="arancel" type="number" step="0.01" value={formData.arancel} onChange={(e) => handleChange("arancel", parseFloat(e.target.value) || 0)} /></div>
            <div className="space-y-2"><Label htmlFor="precio">Precio Referencial ($)</Label><Input id="precio" type="number" step="0.01" value={formData.precio_referencial} onChange={(e) => handleChange("precio_referencial", parseFloat(e.target.value) || 0)} /></div>
            <div className="space-y-2"><Label htmlFor="peso">Peso Unitario (kg)</Label><Input id="peso" type="number" step="0.01" value={formData.peso_unitario} onChange={(e) => handleChange("peso_unitario", parseFloat(e.target.value) || 0)} /></div>
            <div className="space-y-2"><Label htmlFor="categoria">Categoría</Label><Input id="categoria" value={formData.categoria} onChange={(e) => handleChange("categoria", e.target.value)} /></div>
            <div className="space-y-2 md:col-span-2"><Label htmlFor="proveedor">Proveedor</Label><Input id="proveedor" value={formData.proveedor} onChange={(e) => handleChange("proveedor", e.target.value)} /></div>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button type="button" variant="outline" onClick={onCancel}>Cancelar</Button>
            <Button type="submit" disabled={isLoading} className="bg-gradient-to-r from-blue-600 to-indigo-600">
              <Save className="w-4 h-4 mr-2" />{isLoading ? "Guardando..." : "Guardar"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}