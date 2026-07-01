import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { ArrowRight, Upload, ArrowLeft, Trash2, Pencil, Plus, X } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
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

const STATUS_OPTIONS = [
  { value: "adjudicado",      label: "Adjudicado" },
  { value: "comprado",        label: "Comprado" },
  { value: "transito",        label: "Tránsito" },
  { value: "en_bodega",       label: "En Bodega" },
  { value: "en_aduana",       label: "En Aduana" },
  { value: "enviado_cliente", label: "Enviado a Cliente" },
  { value: "entregado",       label: "Entregado" },
];

export default function OrderDetail({ order, orderItems, onEdit, onClose }) {
  const queryClient = useQueryClient();
  const [editingItem, setEditingItem] = useState(null);
  const [formData, setFormData] = useState({});
  const [uploading, setUploading] = useState(false);
  const [applyToAll, setApplyToAll] = useState(false);

  // Inline add-product state
  const [addingProduct, setAddingProduct] = useState(false);
  const [newProduct, setNewProduct] = useState({ producto_nombre: "", cantidad: 1, fecha_entrega_orden: "", estado: "adjudicado", precio_compra: 0, precio_venta: 0 });

  const updateItemMutation = useMutation({
    mutationFn: ({ id, data }) => base44.entities.OrderItem.update(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['orderItems'] }); setEditingItem(null); setFormData({}); setApplyToAll(false); },
  });

  const deleteItemMutation = useMutation({
    mutationFn: (id) => base44.entities.OrderItem.delete(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['orderItems'] }); },
  });

  const createItemMutation = useMutation({
    mutationFn: (item) => base44.entities.OrderItem.create(item),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orderItems'] });
      setAddingProduct(false);
      setNewProduct({ producto_nombre: "", cantidad: 1, fecha_entrega_orden: "", estado: "adjudicado", precio_compra: 0, precio_venta: 0 });
    },
  });

  const handleAddProduct = () => {
    if (!newProduct.producto_nombre.trim()) return;
    createItemMutation.mutate({
      pedido_id: order.id,
      pedido_numero: order.numero_pedido,
      producto_id: null,
      producto_nombre: newProduct.producto_nombre.trim(),
      cantidad: newProduct.cantidad || 1,
      fecha_entrega_orden: newProduct.fecha_entrega_orden || null,
      precio_compra: newProduct.precio_compra || null,
      precio_venta: newProduct.precio_venta || null,
      estado: newProduct.estado || "adjudicado",
    });
  };

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
    <Card className="border-none shadow-lg">
      <CardHeader className="border-b border-slate-100 bg-gradient-to-r from-purple-50 to-indigo-50">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-bold text-slate-900">Detalle del Pedido</CardTitle>
          <div className="flex items-center gap-2">
            {onEdit && (
              <Button size="sm" variant="outline" onClick={onEdit} className="border-purple-300 text-purple-700 hover:bg-purple-50">
                <Pencil className="w-3 h-3 mr-1" />Editar
              </Button>
            )}
            {onClose && (
              <Button size="sm" variant="ghost" onClick={onClose} className="text-slate-500 hover:text-slate-900 h-8 w-8 p-0">
                <X className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-6 space-y-4">
        <div>
          <h3 className="font-bold text-xl text-slate-900 mb-1">{order.numero_pedido}</h3>
          <p className="text-sm text-slate-600">Cliente: {order.cliente}</p>
        </div>
        <div className="border-t pt-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-semibold text-slate-900">Productos ({orderItems.length})</h4>
            {!addingProduct && (
              <Button size="sm" variant="outline" onClick={() => setAddingProduct(true)} className="h-7 text-xs border-purple-300 text-purple-700 hover:bg-purple-50">
                <Plus className="w-3 h-3 mr-1" />Agregar
              </Button>
            )}
          </div>
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
          {/* Inline add product form */}
          {addingProduct && (
            <div className="mt-3 p-3 border-2 border-dashed border-purple-300 rounded-lg bg-purple-50 space-y-2">
              <p className="text-xs font-semibold text-purple-700">Nuevo producto</p>
              <Input
                placeholder="Nombre del producto *"
                value={newProduct.producto_nombre}
                onChange={e => setNewProduct(p => ({ ...p, producto_nombre: e.target.value }))}
                className="h-8 text-sm"
              />
              <div className="grid grid-cols-2 gap-2">
                <Input
                  type="number" min="1" placeholder="Cantidad"
                  value={newProduct.cantidad}
                  onChange={e => setNewProduct(p => ({ ...p, cantidad: parseInt(e.target.value) || 1 }))}
                  className="h-8 text-sm"
                />
                <Input
                  type="date" placeholder="Fecha entrega"
                  value={newProduct.fecha_entrega_orden}
                  onChange={e => setNewProduct(p => ({ ...p, fecha_entrega_orden: e.target.value }))}
                  className="h-8 text-sm"
                />
                <Input
                  type="number" step="0.01" placeholder="Precio compra"
                  value={newProduct.precio_compra || ""}
                  onChange={e => setNewProduct(p => ({ ...p, precio_compra: parseFloat(e.target.value) || 0 }))}
                  className="h-8 text-sm"
                />
                <Input
                  type="number" step="0.01" placeholder="Precio venta"
                  value={newProduct.precio_venta || ""}
                  onChange={e => setNewProduct(p => ({ ...p, precio_venta: parseFloat(e.target.value) || 0 }))}
                  className="h-8 text-sm"
                />
              </div>
              <Select value={newProduct.estado} onValueChange={v => setNewProduct(p => ({ ...p, estado: v }))}>
                <SelectTrigger className="h-8 text-sm"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map(s => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
                </SelectContent>
              </Select>
              <div className="flex gap-2 pt-1">
                <Button
                  size="sm" onClick={handleAddProduct}
                  disabled={createItemMutation.isPending || !newProduct.producto_nombre.trim()}
                  className="flex-1 bg-gradient-to-r from-purple-600 to-indigo-600 text-white"
                >
                  {createItemMutation.isPending ? "Guardando…" : "Agregar"}
                </Button>
                <Button size="sm" variant="outline" onClick={() => setAddingProduct(false)} className="flex-1">
                  Cancelar
                </Button>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}