import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Calendar, Package, ChevronDown, ChevronRight } from "lucide-react";

function ActionSelect({ orderId, onDelete, onArchive, onReopen }) {
  const [key, setKey] = useState(0);
  const handle = (v) => {
    if (v === "delete")  onDelete(orderId);
    if (v === "archive") onArchive(orderId);
    if (v === "reopen")  onReopen(orderId);
    setKey(k => k + 1);
  };
  return (
    <Select key={key} onValueChange={handle}>
      <SelectTrigger className="w-40 h-8 text-xs" onClick={e => e.stopPropagation()}>
        <SelectValue placeholder="Acciones" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="reopen">Volver a En Curso</SelectItem>
        <SelectItem value="archive">Mover a Archivo</SelectItem>
        <SelectItem value="delete" className="text-red-600">Eliminar</SelectItem>
      </SelectContent>
    </Select>
  );
}

export default function CompletedOrders({ orders, orderItems, onDelete, onArchive, onReopen }) {
  const [filterClient, setFilterClient] = useState("");
  const [filterStartDate, setFilterStartDate] = useState("");
  const [filterEndDate, setFilterEndDate] = useState("");
  const [expandedOrders, setExpandedOrders] = useState({});

  const toggleExpand = (orderId) => setExpandedOrders(prev => ({ ...prev, [orderId]: !prev[orderId] }));
  const getOrderItems = (orderId) => orderItems.filter(item => item.pedido_id === orderId);

  const isOrderComplete = (orderId) => {
    const items = getOrderItems(orderId);
    return items.length > 0 && items.every(item => item.estado === 'entregado');
  };

  const completedOrders = orders.filter(order => {
    if (!isOrderComplete(order.id)) return false;
    if (filterClient && !order.cliente.toLowerCase().includes(filterClient.toLowerCase())) return false;
    if (filterStartDate || filterEndDate) {
      const orderDate = new Date(order.fecha_pedido || order.created_date);
      if (filterStartDate && orderDate < new Date(filterStartDate)) return false;
      if (filterEndDate && orderDate > new Date(filterEndDate)) return false;
    }
    return true;
  }).sort((a, b) => new Date(b.created_date) - new Date(a.created_date));

  const getStatusText = (status) => {
    const statusMap = { adjudicado: "Adjudicado", comprado: "Comprado", transito: "Tránsito", en_bodega: "En Bodega", en_aduana: "En Aduana", enviado_cliente: "Enviado a Cliente", entregado: "Entregado" };
    return statusMap[status] || status;
  };

  return (
    <div className="space-y-6">
      <Card className="border-none shadow-lg">
        <CardHeader className="border-b border-slate-100"><CardTitle>Filtros</CardTitle></CardHeader>
        <CardContent className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2"><Label>Cliente</Label><Input placeholder="Buscar por cliente" value={filterClient} onChange={(e) => setFilterClient(e.target.value)} /></div>
            <div className="space-y-2"><Label>Fecha Desde</Label><Input type="date" value={filterStartDate} onChange={(e) => setFilterStartDate(e.target.value)} /></div>
            <div className="space-y-2"><Label>Fecha Hasta</Label><Input type="date" value={filterEndDate} onChange={(e) => setFilterEndDate(e.target.value)} /></div>
          </div>
        </CardContent>
      </Card>
      <Card className="border-none shadow-lg">
        <CardHeader className="border-b border-slate-100">
          <CardTitle>Pedidos Completados ({completedOrders.length})</CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          {completedOrders.length === 0 ? (
            <div className="text-center py-12"><Package className="w-16 h-16 text-slate-300 mx-auto mb-4" /><p className="text-slate-600">No hay pedidos completados</p></div>
          ) : (
            <div className="space-y-3">
              {completedOrders.map((order) => {
                const items = getOrderItems(order.id);
                const isExpanded = expandedOrders[order.id];
                return (
                  <div key={order.id} className="border-2 rounded-xl border-green-200 bg-green-50">
                    <div className="p-4">
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <h3 className="font-bold text-slate-900">{order.numero_pedido}</h3>
                            <Badge className="bg-green-100 text-green-700">Completado</Badge>
                            <Badge variant="outline" className="text-xs">{items.length} producto{items.length !== 1 ? 's' : ''}</Badge>
                          </div>
                          <p className="text-sm text-slate-600">Cliente: {order.cliente}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <ActionSelect orderId={order.id} onDelete={onDelete} onArchive={onArchive} onReopen={onReopen} />
                          <Button variant="ghost" size="icon" onClick={() => toggleExpand(order.id)}>
                            {isExpanded ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
                          </Button>
                        </div>
                      </div>
                    </div>
                    {isExpanded && (
                      <div className="px-4 pb-4 space-y-2 border-t">
                        {items.map((item) => (
                          <div key={item.id} className="mt-2 p-3 bg-white rounded-lg border">
                            <div className="flex items-start justify-between mb-2">
                              <div><p className="font-semibold text-slate-900">{item.producto_nombre}</p><p className="text-xs text-slate-500">Cantidad: {item.cantidad}</p></div>
                              <Badge className="bg-green-100 text-green-700">{getStatusText(item.estado)}</Badge>
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-xs mt-2">
                              {item.fecha_entrega && <div><span className="text-slate-500">Entregado:</span><span className="ml-1 font-medium">{new Date(item.fecha_entrega).toLocaleDateString('es-EC')}</span></div>}
                              {item.tracking_number && <div><span className="text-slate-500">Tracking:</span><span className="ml-1 font-medium">{item.tracking_number}</span></div>}
                              {item.prueba_entrega && <div className="col-span-2"><a href={item.prueba_entrega} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Ver prueba de entrega</a></div>}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}