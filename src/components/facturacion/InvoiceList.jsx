import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Pencil, Trash2, FileText } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { format } from "date-fns";

export default function InvoiceList({ invoices, isLoading, onEdit, onDelete, onSelect, selectedInvoice }) {
const getStatusColor = (status) => {
const colorMap = {
pendiente: 'bg-gray-100 text-gray-800 border-gray-200',
facturado: 'bg-blue-100 text-blue-800 border-blue-200',
retencion: 'bg-amber-100 text-amber-800 border-amber-200',
pagado: 'bg-green-100 text-green-800 border-green-200'
};
return colorMap[status] || 'bg-gray-100 text-gray-800';
};

if (isLoading) {
return (
<Card className="border-none shadow-lg">
<CardHeader className="border-b border-slate-100">
<CardTitle>Lista de Facturas</CardTitle>
</CardHeader>
<CardContent className="p-6">
<div className="space-y-4">
{[1, 2, 3].map((i) => (
<div key={i} className="p-4 border rounded-lg">
<Skeleton className="h-6 w-48 mb-2" />
<Skeleton className="h-4 w-full mb-2" />
<Skeleton className="h-4 w-32" />
</div>
))}
</div>
</CardContent>
</Card>
);
}

return (
<Card className="border-none shadow-lg">
<CardHeader className="border-b border-slate-100">
<CardTitle className="text-lg font-bold text-slate-900">Lista de Facturas</CardTitle>
</CardHeader>
<CardContent className="p-6">
{invoices.length === 0 ? (
<div className="text-center py-12">
<FileText className="w-16 h-16 text-slate-300 mx-auto mb-4" />
<p className="text-slate-600 mb-2">No hay facturas registradas</p>
<p className="text-sm text-slate-500">Comienza creando tu primera factura</p>
</div>
) : (
<div className="space-y-3">
{invoices.map((invoice) => (
<div
key={invoice.id}
onClick={() => onSelect(invoice)}
className={`p-4 border rounded-xl transition-all cursor-pointer hover:shadow-md ${
selectedInvoice?.id === invoice.id
? 'border-green-500 bg-green-50'
: 'border-slate-200 hover:border-slate-300'
}`}
>
<div className="flex items-start justify-between mb-3">
<div className="flex-1">
<div className="flex items-center gap-3 mb-2">
<h3 className="font-semibold text-slate-900">{invoice.numero_factura}</h3>
<Badge className={`${getStatusColor(invoice.estado)} border`}>
{invoice.estado.toUpperCase()}
</Badge>
</div>
<p className="text-sm text-slate-600 mb-1">
Pedido: {invoice.pedido_numero}
</p>
<p className="text-xs text-slate-500">Cliente: {invoice.cliente}</p>
</div>
<div className="flex gap-2 ml-4">
<Button
variant="ghost"
size="icon"
onClick={(e) => {
e.stopPropagation();
onEdit(invoice);
}}
className="text-slate-600 hover:text-blue-600"
>
<Pencil className="w-4 h-4" />
</Button>
<Button
variant="ghost"
size="icon"
onClick={(e) => {
e.stopPropagation();
onDelete(invoice.id);
}}
className="text-slate-600 hover:text-red-600"
>
<Trash2 className="w-4 h-4" />
</Button>
</div>
</div>

<div className="flex items-center justify-between pt-3 border-t border-slate-100">
<div className="text-xs text-slate-500">
{invoice.fecha_emision && `Emitida: ${format(new Date(invoice.fecha_emision), 'dd/MM/yyyy')}`}
</div>
<div className="text-lg font-bold text-slate-900">
${invoice.monto_total.toFixed(2)}
</div>
</div>
</div>
))}
</div>
)}
</CardContent>
</Card>
);
}