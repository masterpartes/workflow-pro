import React, { useState } from "react";
import { base44 } from "@/api/base44Client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Plus, Filter } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import InvoiceList from "../components/facturacion/InvoiceList";
import InvoiceForm from "../components/facturacion/InvoiceForm";
import InvoiceDetails from "../components/facturacion/InvoiceDetails";

export default function Facturacion() {
  const [showForm, setShowForm] = useState(false);
  const [editingInvoice, setEditingInvoice] = useState(null);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [filterClient, setFilterClient] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterStartDate, setFilterStartDate] = useState("");
  const [filterEndDate, setFilterEndDate] = useState("");
  const queryClient = useQueryClient();

  const { data: allInvoices = [], isLoading } = useQuery({
    queryKey: ["invoices"],
    queryFn: () => base44.entities.Invoice.list("-created_date"),
  });

  const invoices = allInvoices.filter(invoice => {
    if (filterClient && !invoice.cliente.toLowerCase().includes(filterClient.toLowerCase())) return false;
    if (filterStatus !== "all" && invoice.estado !== filterStatus) return false;
    if (filterStartDate || filterEndDate) {
      const invoiceDate = new Date(invoice.fecha_emision || invoice.created_date);
      if (filterStartDate && invoiceDate < new Date(filterStartDate)) return false;
      if (filterEndDate && invoiceDate > new Date(filterEndDate)) return false;
    }
    return true;
  });

  const { data: orders = [] } = useQuery({
    queryKey: ["orders"],
    queryFn: () => base44.entities.Order.list(),
  });

  const createMutation = useMutation({
    mutationFn: (data) => base44.entities.Invoice.create(data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["invoices"] }); setShowForm(false); setEditingInvoice(null); },
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => base44.entities.Invoice.update(id, data),
    onSuccess: (_, { data }) => {
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
      setShowForm(false);
      setEditingInvoice(null);
      if (selectedInvoice) setSelectedInvoice({ ...selectedInvoice, ...data });
    },
  });
  const deleteMutation = useMutation({
    mutationFn: (id) => base44.entities.Invoice.delete(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["invoices"] }); setSelectedInvoice(null); },
  });

  const handleSubmit = (data) => {
    if (editingInvoice) updateMutation.mutate({ id: editingInvoice.id, data });
    else createMutation.mutate(data);
  };

  return (
    <div className="p-6 lg:p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Facturación</h1>
          <p className="text-slate-600">Administra tus facturas, retenciones y pagos</p>
        </div>
        <Button
          onClick={() => { setEditingInvoice(null); setShowForm(true); }}
          className="bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 shadow-lg"
        >
          <Plus className="w-5 h-5 mr-2" />
          Nueva Factura
        </Button>
      </div>
      {!showForm && (
        <Card className="border-none shadow-lg mb-6">
          <CardHeader className="border-b border-slate-100">
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-slate-600" />
              <CardTitle className="text-lg font-bold text-slate-900">Filtros</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label>Cliente</Label>
                <Input placeholder="Buscar por cliente" value={filterClient} onChange={(e) => setFilterClient(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Estado</Label>
                <Select value={filterStatus} onValueChange={setFilterStatus}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos</SelectItem>
                    <SelectItem value="pendiente">Pendiente</SelectItem>
                    <SelectItem value="facturado">Facturado</SelectItem>
                    <SelectItem value="retencion">Retención</SelectItem>
                    <SelectItem value="pagado">Pagado</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Fecha Desde</Label>
                <Input type="date" value={filterStartDate} onChange={(e) => setFilterStartDate(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Fecha Hasta</Label>
                <Input type="date" value={filterEndDate} onChange={(e) => setFilterEndDate(e.target.value)} />
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {showForm ? (
            <InvoiceForm
              invoice={editingInvoice}
              orders={orders}
              onSubmit={handleSubmit}
              onCancel={() => { setShowForm(false); setEditingInvoice(null); }}
              isLoading={createMutation.isPending || updateMutation.isPending}
            />
          ) : (
            <InvoiceList
              invoices={invoices}
              isLoading={isLoading}
              onEdit={(invoice) => { setEditingInvoice(invoice); setShowForm(true); }}
              onDelete={(id) => { if (confirm("¿Estás seguro de eliminar esta factura?")) deleteMutation.mutate(id); }}
              onSelect={setSelectedInvoice}
              selectedInvoice={selectedInvoice}
            />
          )}
        </div>
        <div>
          {selectedInvoice && (
            <InvoiceDetails
              invoice={selectedInvoice}
              onUpdate={(data) => { if (selectedInvoice) updateMutation.mutate({ id: selectedInvoice.id, data }); }}
              isUpdating={updateMutation.isPending}
            />
          )}
        </div>
      </div>
    </div>
  );
}
