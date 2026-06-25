import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { ArrowRight, Upload, ArrowLeft, Trash2 } from "lucide-react";
import { base44 } from "@/api/base44Client";
import { useMutation, useQueryClient } from "@tanstack/react-query";

const getStatusText = (status) => {
  const statusMap = {
    adjudicado: "Adjudicado", comprado: "Comprado", transito: "Tránsito",
    en_bodega: "En Bodega", en_aduana: "En Aduana", enviado_cliente: "Enviado a Cliente", entregado: "Entregado",
  };
  return statusMap[status] || status;
};

const getNextStatus = (current) => {
  const flow = { adjudicado: "comprado", comprado: "transito", transito: "en_bodega", en_bodega: "en_aduana", en_aduana: "enviado_cliente", enviado_cliente: "entregado" };
  return flow[current];
};

const getPreviousStatus = (current) => {
  const reverseFlow = { comprado: "adjudicado", transito: "comprado", en_bodega: "transito", en_aduana: "en_bodega", enviado_cliente: "en_aduana", entregado: "enviado_cliente" };
  return reverseFlow[current];
};

const getRequiredFields = (currentStatus, nextStatus) => {
  const requirements = {
    'adjudicado-comprado': [{ field: 'fecha_compra', label: 'Fecha de Compra', type: 'date' }],
    'comprado-transito': [{ field: 'tracking_number', label: 'Tracking Number', type: 'text' }, { field: 'fecha_miami', label: 'Fecha Miami', type: 'date' }],
    'transito-en_bodega': [{ field: 'wr_bodega', label: 'WR de Bodega', type: 'text' }, { field: 'fecha_miami', label: 'Actualizar Fecha Miami', type: 'date' }],
    'en_bodega-en_aduana': [{ field: 'awb', label: 'AWB', type: 'text' }, { field: 'fecha_aduana', label: 'Fecha Aduana', type: 'date' }],
    'en_aduana-enviado_cliente': [{ field: 'numero_guia', label: 'Número de Guía', type: 'text' }, { field: 'fecha_entrega', label: 'Fecha de Entrega', type: 'date' }],
    'enviado_cliente-entregado': [{ field: 'fecha_entrega', label: 'Actualizar Fecha Entrega', type: 'date' }, { field: 'prueba_entrega', label: 'Prueba de Entrega', type: 'file' }],
  };
  return requirements[`${currentStatus}-${nextStatus}`] || [];
};

export default function OrderDetail({ order, orderItems }) {
  const queryClient = useQueryClient();
  const [editingItem, setEditingItem] = useState(null);
  const [formData, setFormData] = useState({});
  const [uploading, setUploading] = useState(false);
  const [applyToAll, setApplyToAll] = useState(false);

  const updateItemMutation = useMutation({
    mutationFn: ({ id, data }) => base44.entities.OrderItem.update(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['orderItems'] }); setEditingItem(null); setFormData({}); setApplyToAll(false); },
  });

  const deleteItemMutation = useMutation({
    mutationFn: (id) => base44.entities.OrderItem.delete(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['orderItems'] }); },
  });

  const handleAdvanceStatus = (item) => {
    const nextStatus = getNextStatus(item.estado);
    if (!nextStatus) return;
    const requiredFields = getRequiredFields(item.estado, nextStatus);
    if (requiredFields.length > 0) {
      setEditingItem(item.id);
      const initialData = { estado: nextStatus };
      requiredFields.forEach(field => { initialData[field.field] = item[field.field] || ''; });
      setFormData(initialData);
    } else {
      updateItemMutation.mutate({ id: item.id, data: { estado: nextStatus } });
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    try {
      const { file_url } = await base44.integrations.Core.UploadFile({ file });
      setFormData(prev => ({ ...prev, prueba_entrega: file_url }));
    } catch (error) { alert('Error al subir archivo'); }
    setUploading(false);
  };

  const handleSubmitAdvance = async (itemId) => {
    if (applyToAll) {
      const currentItem = orderItems.find(item => item.id === itemId);
      const itemsToUpdate = orderItems.filter(item => item.estado === currentItem.estado);
      await Promise.all(itemsToUpdate.map(item => updateItemMutation.mutateAsync({ id: item.id, data: formData })));
    } else {
      updateItemMutation.mutate({ id: itemId, data: formData });
    }
  };

  const handleRevertStatus = (item) => {
    const prevStatus = getPreviousStatus(item.estado);
    if (prevStatus && confirm(`¿Retroceder a ${getStatusText(prevStatus)}?`)) {
      updateItemMutation.mutate({ id: item.id, data: { estado: prevStatus } });
    }
  };

  const handleDeleteItem = (itemId) => {
    if (orderItems.length === 1) { alert('No puedes eliminar el último producto del pedido'); return; }
    if (confirm('¿Estás seguro de eliminar este producto?')) { deleteItemMutation.mutate(itemId); }
  };

  return (
    <Card className="border-none shadow-lg sticky top-6">
      <CardHeader className="border-b border-slate-100 bg-gradient-to-r from-purple-50 to-indigo-50">
        <CardTitle className="text-lg font-bold text-slate-900">Detalle del Pedido</CardTitle>
      </CardHeader>
      <CardContent className="p-6 space-y-4">
        <div>
          <h3 className="font-bold text-xl text-slate-900 mb-1">{order.numero_pedido}</h3>
          <p className="text-sm text-slate-600">Cliente: {order.cliente}</p>
        </div>
        <div className="border-t pt-4">
          <h4 className="font-semibold text-slate-900 mb-3">Productos ({orderItems.length})</h4>
          <div className="space-y-3">
            {orderItems.map((item) => {
              const nextStatus = getNextStatus(item.estado);
              const isEditing = editingItem === item.id;
              const requiredFields = nextStatus ? getRequiredFields(item.estado, nextStatus) : [];
              return (
                <div key={item.id} className="p-3 border rounded-lg bg-slate-50">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="font-semibold text-slate-900 text-sm">{item.producto_nombre}</p>
                      <p className="text-xs text-slate-500">Cantidad: {item.cantidad}</p>
                    </div>
                    <Button variant="ghost" size="icon" onClick={() => handleDeleteItem(item.id)} className="h-6 w-6 text-red-600">
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </div>
                  <Badge className="mb-2" variant="outline">{getStatusText(item.estado)}</Badge>
                  {isEditing ? (
                    <div className="mt-3 space-y-3 border-t pt-3">
                      {requiredFields.map((field) => (
                        <div key={field.field} className="space-y-1">
                          <Label className="text-xs">{field.label}</Label>
                          {field.type === 'file' ? (
                            <div>
                              <Input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={handleFileUpload} disabled={uploading} />
                              {uploading && <p className="text-xs text-slate-500 mt-1">Subiendo...</p>}
                            </div>
                          ) : (
                            <Input type={field.type} value={formData[field.field] || ''} onChange={(e) => setFormData(prev => ({ ...prev, [field.field]: e.target.value }))} className="h-8 text-sm" />
                          )}
                        </div>
                      ))}
                      {orderItems.filter(i => i.estado === item.estado).length > 1 && (
                        <div className="flex items-center space-x-2 pt-2">
                          <Checkbox id="applyToAll" checked={applyToAll} onCheckedChange={setApplyToAll} />
                          <label htmlFor="applyToAll" className="text-xs text-slate-700 cursor-pointer">Aplicar a todos en estado {getStatusText(item.estado)}</label>
                        </div>
                      )}
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => handleSubmitAdvance(item.id)} disabled={updateItemMutation.isPending} className="flex-1 bg-gradient-to-r from-purple-600 to-indigo-600">Confirmar</Button>
                        <Button size="sm" variant="outline" onClick={() => { setEditingItem(null); setFormData({}); setApplyToAll(false); }} className="flex-1">Cancelar</Button>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2 mt-2">
                      {nextStatus && (
                        <Button size="sm" onClick={() => handleAdvanceStatus(item)} className="w-full bg-gradient-to-r from-purple-600 to-indigo-600">
                          <ArrowRight className="w-4 h-4 mr-2" />Avanzar a {getStatusText(nextStatus)}
                        </Button>
                      )}
                      {getPreviousStatus(item.estado) && (
                        <Button size="sm" variant="outline" onClick={() => handleRevertStatus(item)} className="w-full">
                          <ArrowLeft className="w-4 h-4 mr-2" />Retroceder a {getStatusText(getPreviousStatus(item.estado))}
                        </Button>
                      )}
                      {!nextStatus && <Badge className="w-full justify-center bg-green-100 text-green-700">Completado</Badge>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}