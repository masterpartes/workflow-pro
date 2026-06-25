import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { X, Save, Upload, Loader2 } from "lucide-react";
import { base44 } from "@/api/base44Client";

export default function InvoiceForm({ invoice, orders, onSubmit, onCancel, isLoading }) {
const [formData, setFormData] = useState(
invoice || {
numero_factura: `FAC-${Date.now()}`,
pedido_id: "",
pedido_numero: "",
cliente: "",
monto_total: 0,
estado: "pendiente",
fecha_emision: new Date().toISOString().split('T')[0],
fecha_vencimiento: "",
notas: "",
}
);
const [uploadingPdf, setUploadingPdf] = useState(false);
const [uploadingXml, setUploadingXml] = useState(false);

const handleSubmit = (e) => {
e.preventDefault();
onSubmit(formData);
};

const handleChange = (field, value) => {
setFormData((prev) => ({ ...prev, [field]: value }));
};

const handleOrderSelect = (orderId) => {
const order = orders.find(o => o.id === orderId);
if (order) {
handleChange("pedido_id", orderId);
handleChange("pedido_numero", order.numero_pedido);
handleChange("cliente", order.cliente);
handleChange("monto_total", (order.precio_venta || 0) * (order.cantidad || 1));
}
};

const handleFileUpload = async (file, type) => {
if (type === 'pdf') setUploadingPdf(true);
else setUploadingXml(true);

try {
const { file_url } = await base44.integrations.Core.UploadFile({ file });
handleChange(type === 'pdf' ? 'archivo_pdf' : 'archivo_xml', file_url);
} catch (error) {
console.error("Error uploading file:", error);
} finally {
if (type === 'pdf') setUploadingPdf(false);
else setUploadingXml(false);
}
};

return (
<Card className="border-none shadow-lg">
<CardHeader className="border-b border-slate-100">
<div className="flex items-center justify-between">
<CardTitle className="text-lg font-bold text-slate-900">
{invoice ? "Editar Factura" : "Nueva Factura"}
</CardTitle>
<Button variant="ghost" size="icon" onClick={onCancel}>
<X className="w-5 h-5" />
</Button>
</div>
</CardHeader>
<CardContent className="p-6">
<form onSubmit={handleSubmit} className="space-y-4">
<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
<div className="space-y-2">
<Label htmlFor="numero_factura">Número de Factura *</Label>
<Input
id="numero_factura"
value={formData.numero_factura}
onChange={(e) => handleChange("numero_factura", e.target.value)}
required
/>
</div>

<div className="space-y-2">
<Label htmlFor="pedido">Pedido *</Label>
<Select
value={formData.pedido_id}
onValueChange={handleOrderSelect}
required
>
<SelectTrigger>
<SelectValue placeholder="Seleccionar pedido" />
</SelectTrigger>
<SelectContent>
{orders.map((order) => (
<SelectItem key={order.id} value={order.id}>
{order.numero_pedido} - {order.cliente}
</SelectItem>
))}
</SelectContent>
</Select>
</div>

<div className="space-y-2">
<Label htmlFor="cliente">Cliente *</Label>
<Input
id="cliente"
value={formData.cliente}
onChange={(e) => handleChange("cliente", e.target.value)}
required
disabled={!!formData.pedido_id}
/>
</div>

<div className="space-y-2">
<Label htmlFor="monto_total">Monto Total ($) *</Label>
<Input
id="monto_total"
type="number"
step="0.01"
value={formData.monto_total}
onChange={(e) => handleChange("monto_total", parseFloat(e.target.value) || 0)}
required
/>
</div>

<div className="space-y-2">
<Label htmlFor="estado">Estado</Label>
<Select
value={formData.estado}
onValueChange={(value) => handleChange("estado", value)}
>
<SelectTrigger>
<SelectValue />
</SelectTrigger>
<SelectContent>
<SelectItem value="pendiente">Pendiente</SelectItem>
<SelectItem value="facturado">Facturado</SelectItem>
<SelectItem value="retencion">Retención</SelectItem>
<SelectItem value="pagado">Pagado</SelectItem>
</SelectContent>
</Select>
</div>

<div className="space-y-2">
<Label htmlFor="monto_retencion">Monto Retención ($)</Label>
<Input
id="monto_retencion"
type="number"
step="0.01"
value={formData.monto_retencion || 0}
onChange={(e) => handleChange("monto_retencion", parseFloat(e.target.value) || 0)}
/>
</div>

<div className="space-y-2">
<Label htmlFor="fecha_emision">Fecha de Emisión</Label>
<Input
id="fecha_emision"
type="date"
value={formData.fecha_emision}
onChange={(e) => handleChange("fecha_emision", e.target.value)}
/>
</div>

<div className="space-y-2">
<Label htmlFor="fecha_vencimiento">Fecha de Vencimiento</Label>
<Input
id="fecha_vencimiento"
type="date"
value={formData.fecha_vencimiento}
onChange={(e) => handleChange("fecha_vencimiento", e.target.value)}
/>
</div>

<div className="space-y-2">
<Label htmlFor="pdf">Archivo PDF</Label>
<div className="flex gap-2">
<Input
id="pdf"
type="file"
accept=".pdf"
onChange={(e) => handleFileUpload(e.target.files[0], 'pdf')}
disabled={uploadingPdf}
className="flex-1"
/>
{uploadingPdf && <Loader2 className="w-5 h-5 animate-spin text-blue-600" />}
</div>
{formData.archivo_pdf && (
<p className="text-xs text-green-600">✓ Archivo PDF cargado</p>
)}
</div>

<div className="space-y-2">
<Label htmlFor="xml">Archivo XML</Label>
<div className="flex gap-2">
<Input
id="xml"
type="file"
accept=".xml"
onChange={(e) => handleFileUpload(e.target.files[0], 'xml')}
disabled={uploadingXml}
className="flex-1"
/>
{uploadingXml && <Loader2 className="w-5 h-5 animate-spin text-blue-600" />}
</div>
{formData.archivo_xml && (
<p className="text-xs text-green-600">✓ Archivo XML cargado</p>
)}
</div>

<div className="space-y-2 md:col-span-2">
<Label htmlFor="notas">Notas</Label>
<Textarea
id="notas"
value={formData.notas}
onChange={(e) => handleChange("notas", e.target.value)}
placeholder="Notas adicionales"
rows={3}
/>
</div>
</div>

<div className="flex justify-end gap-3 pt-4">
<Button type="button" variant="outline" onClick={onCancel}>
Cancelar
</Button>
<Button
type="submit"
disabled={isLoading}
className="bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700"
>
<Save className="w-4 h-4 mr-2" />
{isLoading ? "Guardando..." : "Guardar"}
</Button>
</div>
</form>
</CardContent>
</Card>
);
}