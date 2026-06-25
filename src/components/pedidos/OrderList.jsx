import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Trash2, Package, ChevronDown, ChevronRight, Calendar, Pencil } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

const getStatusText = (status) => {
  const statusMap = {
    adjudicado: "Adjudicado",
    comprado: "Comprado",
    transito: "Tránsito",
    en_bodega: "En Bodega",
    en_aduana: "En Aduana",
    enviado_cliente: "Enviado a Cliente",
    entregado: "Entregado",
  };
  return statusMap[status] || status;
};

const getStatusColor = (status) => {
  const colorMap = {
    adjudicado: "bg-slate-100 text-slate-700",
    comprado: "bg-blue-100 text-blue-700",
    transito: "bg-cyan-100 text-cyan-700",
    en_bodega: "bg-purple-100 text-purple-700",
    en_aduana: "bg-orange-100 text-orange-700",
    enviado_cliente: "bg-indigo-100 text-indigo-700",
    entregado: "bg-green-100 text-green-700",
  };
  return colorMap[status] || "bg-gray-100 text-gray-700";
};

const getDaysUntilDelivery = (deliveryDate) => {
  if (!deliveryDate) return null;
  const today = new Date();
  const delivery = new Date(deliveryDate);
  const diffTime = delivery - today;
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  return diffDays;
};

const getDeliveryColor = (days) => {
  if (days === null) return "bg-slate-100";
  if (days > 15) return "bg-green-100 border-green-300";
  if (days >= 5) return "bg-orange-100 border-orange-300";
  return "bg-purple-100 border-purple-300";
};

const getDeliveryTextColor = (days) => {
  if (days === null) return "text-slate-700";
  if (days > 15) return "text-green-700";
  if (days >= 5) return "text-orange-700";
  return "text-purple-700";
};

export default function OrderList({ orders, orderItems, isLoading, onEdit, onDelete, onSelect, selectedOrder }) {
  const [expandedOrders, setExpandedOrders] = useState({});

  const toggleExpand = (orderId) => {
    setExpandedOrders(prev => ({ ...prev, [orderId]: !prev[orderId] }));
  };

  const getOrderItems = (orderId) => orderItems.filter(item => item.pedido_id === orderId);

  const getEarliestDeliveryDate = (orderId) => {
    const items = getOrderItems(orderId);
    if (items.length === 0) return null;
    const dates = items.map(item => item.fecha_entrega_orden).filter(date => date).sort();
    return dates[0] || null;
  };

  const isOrderComplete = (orderId) => {
    const items = getOrderItems(orderId);
    return items.every(item => item.estado === 'entregado');
  };

  const activeOrders = orders.filter(order => !isOrderComplete(order.id));

  if (isLoading) {
    return (
      <Card className="border-none shadow-lg">
        <CardHeader className="border-b border-slate-100">
          <CardTitle>Pedidos en Curso</CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="p-4 border rounded-lg">
                <Skeleton className="h-6 w-48 mb-2" />
                <Skeleton className="h-4 w-full mb-2" />
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
        <CardTitle className="text-lg font-bold text-slate-900">Pedidos en Curso</CardTitle>
      </CardHeader>
      <CardContent className="p-6">
        {activeOrders.length === 0 ? (
          <div className="text-center py-12">
            <Package className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-600 mb-2">No hay pedidos activos</p>
          </div>
        ) : (
          <div className="space-y-3">
            {activeOrders.map((order) => {
              const items = getOrderItems(order.id);
              const earliestDelivery = getEarliestDeliveryDate(order.id);
              const daysUntilDelivery = getDaysUntilDelivery(earliestDelivery);
              const isExpanded = expandedOrders[order.id];
              const isSelected = selectedOrder?.id === order.id;
              return (
                <div key={order.id} className={`border-2 rounded-xl transition-all ${isSelected ? 'border-purple-500 shadow-md' : 'border-slate-200'} ${getDeliveryColor(daysUntilDelivery)}`}>
                  <div onClick={() => onSelect(order)} className="p-4 cursor-pointer">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="font-bold text-slate-900">{order.numero_pedido}</h3>
                          <Badge variant="outline" className="text-xs">{items.length} producto{items.length !== 1 ? 's' : ''}</Badge>
                        </div>
                        <p className="text-sm text-slate-600 mb-1">Cliente: {order.cliente}</p>
                        {earliestDelivery && (
                          <div className={`flex items-center gap-2 text-sm font-semibold ${getDeliveryTextColor(daysUntilDelivery)}`}>
                            <Calendar className="w-4 h-4" />
                            <span>Entrega: {new Date(earliestDelivery).toLocaleDateString('es-EC')} {daysUntilDelivery !== null && `(${daysUntilDelivery > 0 ? daysUntilDelivery + ' días' : 'Vencido'})`}</span>
                          </div>
                        )}
                      </div>
                      <div className="flex gap-2 ml-4">
                        <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); toggleExpand(order.id); }} className="text-slate-600">
                          {isExpanded ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
                        </Button>
                        <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); onEdit(order); }} className="text-slate-600 hover:text-blue-600">
                          <Pencil className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); onDelete(order.id); }} className="text-slate-600 hover:text-red-600">
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                  {isExpanded && (
                    <div className="px-4 pb-4 space-y-2 border-t">
                      {items.map((item) => (
                        <div key={item.id} className="mt-2 p-3 bg-white rounded-lg border">
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex-1">
                              <p className="font-semibold text-slate-900">{item.producto_nombre}</p>
                              <p className="text-xs text-slate-500">Cantidad: {item.cantidad}</p>
                            </div>
                            <Badge className={getStatusColor(item.estado)}>{getStatusText(item.estado)}</Badge>
                          </div>
                          <div className="grid grid-cols-2 gap-2 text-xs mt-2">
                            {item.fecha_compra && <div><span className="text-slate-500">Comprado:</span><span className="ml-1 font-medium">{new Date(item.fecha_compra).toLocaleDateString('es-EC')}</span></div>}
                            {item.tracking_number && <div><span className="text-slate-500">Tracking:</span><span className="ml-1 font-medium">{item.tracking_number}</span></div>}
                            {item.wr_bodega && <div><span className="text-slate-500">WR:</span><span className="ml-1 font-medium">{item.wr_bodega}</span></div>}
                            {item.awb && <div><span className="text-slate-500">AWB:</span><span className="ml-1 font-medium">{item.awb}</span></div>}
                            {item.numero_guia && <div><span className="text-slate-500">Guía:</span><span className="ml-1 font-medium">{item.numero_guia}</span></div>}
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
  );
}