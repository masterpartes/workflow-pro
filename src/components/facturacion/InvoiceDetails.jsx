import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { FileText, Download, ExternalLink, Calendar, DollarSign } from "lucide-react";
import { format } from "date-fns";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function InvoiceDetails({ invoice, onUpdate, isUpdating }) {
const [editMode, setEditMode] = useState(false);
const [estado, setEstado] = useState(invoice.estado);
const [fechaPago, setFechaPago] = useState(invoice.fecha_pago || '');

const getStatusColor = (status) => {
const colorMap = {
pendiente: 'bg-gray-100 text-gray-800 border-gray-200',
facturado: 'bg-blue-100 text-blue-800 border-blue-200',
retencion: 'bg-amber-100 text-amber-800 border-amber-200',
pagado: 'bg-green-100 text-green-800 border-green-200'
};
return colorMap[status] || 'bg-gray-100 text-gray-800';
};

const handleSave = () => {
onUpdate({ estado, fecha_pago: fechaPago });
setEditMode(false);
};

return (
<Card className="border-none shadow-lg sticky top-6">
<CardHeader className="border-b border-slate-100 bg-gradient-to-r from-green-50 to-emerald-50">
<div className="flex items-center gap-3">
<div className="w-10 h-10 bg-gradient-to-br from-green-600 to-emerald-600 rounded-lg flex items-center justify-center">
<FileText className="w-5 h-5 text-white" />
</div>
<CardTitle className="text-lg font-bold text-slate-900">
Detalles de Factura
</CardTitle>
</div>
</CardHeader>
<CardContent className="p-6 space-y-6">
<div className="space-y-4">
<div className="flex items-center justify-between">
<h3 className="font-semibold text-slate-900 text-lg">{invoice.numero_factura}</h3>
<Badge className={`${getStatusColor(invoice.estado)} border`}>
{invoice.estado.toUpperCase()}
</Badge>
</div>

<div className="grid grid-cols-2 gap-4 p-4 bg-slate-50 rounded-lg">
<div>
<p className="text-xs text-slate-500 mb-1">Pedido</p>
<p className="font-medium text-slate-900">{invoice.pedido_numero}</p>
</div>
<div>
<p className="text-xs text-slate-500 mb-1">Cliente</p>
<p className="font-medium text-slate-900">{invoice.cliente}</p>
</div>
<div>
<p className="text-xs text-slate-500 mb-1">Emisión</p>
<div className="flex items-center gap-1">
<Calendar className="w-3 h-3 text-slate-400" />
<p className="font-medium text-slate-900 text-sm">
{invoice.fecha_emision ? format(new Date(invoice.fecha_emision), 'dd/MM/yyyy') : '-'}
</p>
</div>
</div>
{invoice.fecha_vencimiento && (
<div>
<p className="text-xs text-slate-500 mb-1">Vencimiento</p>
<p className="font-medium text-slate-900 text-sm">
{format(new Date(invoice.fecha_vencimiento), 'dd/MM/yyyy')}
</p>
</div>
)}
</div>

<div className="p-4 bg-gradient-to-br from-green-50 to-emerald-50 rounded-lg border border-green-100">
<div className="flex items-center gap-2 mb-2">
<DollarSign className="w-5 h-5 text-green-700" />
<p className="text-sm font-medium text-green-900">Monto Total</p>
</div>
<p className="text-3xl font-bold text-green-900">
${invoice.monto_total.toFixed(2)}
</p>
{invoice.monto_retencion > 0 && (
<p className="text-sm text-green-700 mt-2">
Retención: ${invoice.monto_retencion.toFixed(2)}
</p>
)}
</div>

{invoice.notas && (
<div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
<p className="text-xs text-blue-600 font-medium mb-2">NOTAS</p>
<p className="text-sm text-slate-700">{invoice.notas}</p>
</div>
)}

<div className="space-y-3">
<p className="text-xs font-semibold text-slate-500 uppercase">Documentos</p>
{invoice.archivo_pdf && (
<a
href={invoice.archivo_pdf}
target="_blank"
rel="noopener noreferrer"
className="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all group"
>
<div className="flex items-center gap-3">
<FileText className="w-5 h-5 text-red-500" />
<span className="text-sm font-medium text-slate-900">Factura PDF</span>
</div>
<ExternalLink className="w-4 h-4 text-slate-400 group-hover:text-blue-600" />
</a>
)}
{invoice.archivo_xml && (
<a
href={invoice.archivo_xml}
target="_blank"
rel="noopener noreferrer"
className="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all group"
>
<div className="flex items-center gap-3">
<FileText className="w-5 h-5 text-green-500" />
<span className="text-sm font-medium text-slate-900">Factura XML</span>
</div>
<ExternalLink className="w-4 h-4 text-slate-400 group-hover:text-blue-600" />
</a>
)}
{!invoice.archivo_pdf && !invoice.archivo_xml && (
<p className="text-sm text-slate-500 text-center py-4">No hay documentos adjuntos</p>
)}
</div>

<div className="pt-4 border-t border-slate-200">
<p className="text-xs font-semibold text-slate-500 uppercase mb-3">Actualizar Estado</p>
{!editMode ? (
<Button
onClick={() => setEditMode(true)}
variant="outline"
className="w-full"
>
Cambiar Estado
</Button>
) : (
<div className="space-y-3">
<div className="space-y-2">
<Label>Estado</Label>
<Select value={estado} onValueChange={setEstado}>
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
{estado === 'pagado' && (
<div className="space-y-2">
<Label>Fecha de Pago</Label>
<Input
type="date"
value={fechaPago}
onChange={(e) => setFechaPago(e.target.value)}
/>
</div>
)}
<div className="flex gap-2">
<Button
onClick={handleSave}
disabled={isUpdating}
className="flex-1 bg-green-600 hover:bg-green-700"
>
{isUpdating ? 'Guardando...' : 'Guardar'}
</Button>
<Button
onClick={() => {
setEditMode(false);
setEstado(invoice.estado);
setFechaPago(invoice.fecha_pago || '');
}}
variant="outline"
>
Cancelar
</Button>
</div>
</div>
)}
</div>
</div>
</CardContent>
</Card>
);
}