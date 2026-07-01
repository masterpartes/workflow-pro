import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Package, ChevronDown, ChevronRight, Calendar, CheckSquare, Archive, AlertTriangle, Clock, CheckCircle2, Search, X, Trash2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

function ActionSelect({ orderId, onEdit, onArchive, onDelete }) {
  const [key, setKey] = useState(0);
  const handle = (v) => {
    if (v === "edit")    onEdit(orderId);
    if (v === "archive") onArchive(orderId);
    if (v === "delete")  onDelete(orderId);
    setKey(k => k + 1);
  };
  return (
    <Select key={key} onValueChange={handle}>
      <SelectTrigger className="w-36 h-8 text-xs" onClick={e => e.stopPropagation()}>
        <SelectValue placeholder="Acciones" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="edit">Editar</SelectItem>
        <SelectItem value="archive">Mover a Archivo</SelectItem>
        <SelectItem value="delete" className="text-red-600">Eliminar</SelectItem>
      </SelectContent>
    </Select>
  );
}

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

// ── SLA health logic (mirrors Dashboard.jsx) ─────────────────────────────────
// late = delivery date passed, urgent = ≤5 days, alert = ≤10 days, ok = >10 days
function getOrderHealth(order, items) {
  const activeItems = items.filter(i => i.estado !== 'entregado');
  if (activeItems.length === 0) return 'ok';

  const today = new Date(); today.setHours(0, 0, 0, 0);
  let minDaysLeft = Infinity;
  for (const item of activeItems) {
    if (item.fecha_entrega_orden) {
      const d = new Date(item.fecha_entrega_orden); d.setHours(0, 0, 0, 0);
      const left = Math.ceil((d - today) / 86400000);
      if (left < minDaysLeft) minDaysLeft = left;
    }
  }
  if (minDaysLeft < 0)   return 'late';
  if (minDaysLeft <= 5)  return 'urgent';
  if (minDaysLeft <= 10) return 'alert';
  return 'ok';
}

const HEALTH_CARD = {
  late:   'border-purple-400 bg-purple-50',
  urgent: 'border-orange-400 bg-orange-50',
  alert:  'border-yellow-300 bg-yellow-50',
  ok:     'border-green-300 bg-green-50',
};

const HEALTH_TEXT = {
  late:   'text-purple-700',
  urgent: 'text-orange-700',
  alert:  'text-yellow-700',
  ok:     'text-green-700',
};

function HealthBadge({ health }) {
  const map = {
    late:   { label: 'Atrasado',      cls: 'bg-purple-100 text-purple-700 border-purple-300', Icon: AlertTriangle },
    urgent: { label: 'Vence < 5 días', cls: 'bg-orange-100 text-orange-700 border-orange-300', Icon: AlertTriangle },
    alert:  { label: 'Vence < 10 días',cls: 'bg-yellow-100 text-yellow-700 border-yellow-300', Icon: Clock },
    ok:     { label: 'En Tiempo',      cls: 'bg-green-100  text-green-700  border-green-300',  Icon: CheckCircle2 },
  };
  const { label, cls, Icon } = map[health] || map.ok;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full border ${cls}`}>
      <Icon className="w-3 h-3" />{label}
    </span>
  );
}

const getDaysUntilDelivery = (deliveryDate) => {
  if (!deliveryDate) return null;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const delivery = new Date(deliveryDate); delivery.setHours(0, 0, 0, 0);
  return Math.ceil((delivery - today) / 86400000);
};

const HEALTH_FILTERS = [
  { value: 'all',    label: 'Todos' },
  { value: 'late',   label: 'Atrasados' },
  { value: 'urgent', label: 'Vence < 5d' },
  { value: 'alert',  label: 'Vence < 10d' },
  { value: 'ok',     label: 'En Tiempo' },
];

export default function OrderList({ orders, orderItems, isLoading, onEdit, onDelete, onArchive, onSelect, selectedOrder, selectedIds = new Set(), onToggleSelect, onSelectAll, onBulkDelete, onBulkArchive, selectionMode, onToggleSelectionMode }) {
  const [expandedOrders, setExpandedOrders] = useState({});
  const [search, setSearch] = useState('');
  const [healthFilter, setHealthFilter] = useState('all');

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

  const allActive = orders.filter(order => !isOrderComplete(order.id));

  // Apply search (placa, numero_pedido, cliente) + health filter
  const activeOrders = allActive.filter(order => {
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      const hit = (order.placa || '').toLowerCase().includes(q)
        || (order.numero_pedido || '').toLowerCase().includes(q)
        || (order.cliente || '').toLowerCase().includes(q);
      if (!hit) return false;
    }
    if (healthFilter !== 'all') {
      const items = getOrderItems(order.id);
      if (getOrderHealth(order, items) !== healthFilter) return false;
    }
    return true;
  });

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

  const allActiveIds = activeOrders.map(o => o.id);
  const allSelected = allActiveIds.length > 0 && allActiveIds.every(id => selectedIds.has(id));
  const someSelected = selectedIds.size > 0;

  return (
    <Card className="border-none shadow-lg">
      <CardHeader className="border-b border-slate-100 space-y-3">
        {/* Title row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {selectionMode && (
              <Checkbox
                checked={allSelected}
                onCheckedChange={(checked) => onSelectAll(checked ? allActiveIds : [])}
                className="h-5 w-5"
              />
            )}
            <CardTitle className="text-lg font-bold text-slate-900">
              Pedidos en Curso
              {(search || healthFilter !== 'all') && (
                <span className="ml-2 text-sm font-normal text-slate-500">({activeOrders.length} resultado{activeOrders.length !== 1 ? 's' : ''})</span>
              )}
            </CardTitle>
          </div>
          <Button
            variant={selectionMode ? "default" : "outline"}
            size="sm"
            onClick={onToggleSelectionMode}
            className={selectionMode ? "bg-purple-600 hover:bg-purple-700 text-white" : ""}
          >
            <CheckSquare className="w-4 h-4 mr-2" />
            {selectionMode ? "Cancelar" : "Seleccionar"}
          </Button>
        </div>

        {/* Search + health filter row */}
        {!selectionMode && (
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                placeholder="Buscar por PLACA, número o cliente…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="pl-9 h-9 text-sm"
              />
              {search && (
                <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700">
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
            <div className="flex gap-1 flex-wrap">
              {HEALTH_FILTERS.map(f => (
                <button
                  key={f.value}
                  onClick={() => setHealthFilter(f.value)}
                  className={`px-3 py-1 rounded-full text-xs font-semibold border transition-colors ${
                    healthFilter === f.value
                      ? 'bg-purple-600 text-white border-purple-600'
                      : 'bg-white text-slate-600 border-slate-300 hover:border-purple-400 hover:text-purple-600'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {selectionMode && someSelected && (
          <div className="mt-3 flex items-center gap-3 p-3 bg-purple-50 rounded-lg border border-purple-200">
            <span className="text-sm font-semibold text-purple-700 flex-1">
              {selectedIds.size} pedido{selectedIds.size !== 1 ? 's' : ''} seleccionado{selectedIds.size !== 1 ? 's' : ''}
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={onBulkArchive}
              className="border-slate-400 hover:bg-slate-100 text-slate-700"
            >
              <Archive className="w-4 h-4 mr-1" />
              Archivar
            </Button>
            <Button
              size="sm"
              onClick={onBulkDelete}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              <Trash2 className="w-4 h-4 mr-1" />
              Eliminar
            </Button>
          </div>
        )}
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
              const health = getOrderHealth(order, items);
              const isExpanded = expandedOrders[order.id];
              const isSelected = selectedOrder?.id === order.id;
              const isChecked = selectedIds.has(order.id);
              const cardClass = isChecked
                ? 'border-purple-500 bg-purple-50'
                : isSelected
                  ? `border-purple-500 shadow-md ${HEALTH_CARD[health]}`
                  : HEALTH_CARD[health];
              return (
                <div key={order.id} className={`border-2 rounded-xl transition-all ${cardClass}`}>
                  <div onClick={() => selectionMode ? onToggleSelect(order.id) : onSelect(order)} className="p-4 cursor-pointer">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-start gap-3 flex-1">
                        {selectionMode && (
                          <Checkbox
                            checked={isChecked}
                            onCheckedChange={() => onToggleSelect(order.id)}
                            onClick={(e) => e.stopPropagation()}
                            className="h-5 w-5 mt-1 shrink-0"
                          />
                        )}
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2 flex-wrap">
                            <h3 className="font-bold text-slate-900">{order.numero_pedido}</h3>
                            {order.placa && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded bg-slate-800 text-white text-xs font-mono tracking-widest">{order.placa}</span>
                            )}
                            <Badge variant="outline" className="text-xs">{items.length} producto{items.length !== 1 ? 's' : ''}</Badge>
                            <HealthBadge health={health} />
                          </div>
                          <p className="text-sm text-slate-600 mb-1">Cliente: {order.cliente}</p>
                          {earliestDelivery && (
                            <div className={`flex items-center gap-2 text-sm font-semibold ${HEALTH_TEXT[health]}`}>
                              <Calendar className="w-4 h-4" />
                              <span>Entrega: {new Date(earliestDelivery).toLocaleDateString('es-EC')} {daysUntilDelivery !== null && `(${daysUntilDelivery > 0 ? daysUntilDelivery + ' días' : 'Vencido'})`}</span>
                            </div>
                          )}
                        </div>
                      </div>
                      {!selectionMode && (
                        <div className="flex items-center gap-2 ml-4">
                          <ActionSelect
                            orderId={order.id}
                            onEdit={() => onEdit(order)}
                            onArchive={onArchive}
                            onDelete={onDelete}
                          />
                          <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); toggleExpand(order.id); }} className="text-slate-600">
                            {isExpanded ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                  {!selectionMode && isExpanded && (
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