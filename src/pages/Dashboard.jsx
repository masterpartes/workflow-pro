import React from "react";
import { base44 } from "@/api/base44Client";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { createPageUrl } from "@/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckSquare, Package, FileText, TrendingUp, ShoppingCart, Truck, DollarSign, AlertTriangle, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import TodoPanel from "@/components/dashboard/TodoPanel";
import { Tarea } from "@/api/entities";

// ── SLA thresholds ────────────────────────────────────────────────────────────
const SLA_PURCHASE        = 5;   // days since creation → must be purchased
const SLA_SHIPMENT        = 10;  // days since creation → must be shipped
const SLA_WAREHOUSE       = 20;  // days since creation → must be in warehouse
const SLA_DELIVERY_URGENT = 5;   // days remaining to delivery → urgent
const SLA_DELIVERY_ALERT  = 10;  // days remaining to delivery → alert

// Returns: 'late' | 'urgent' | 'alert' | 'ok'
function getOrderHealth(order, items) {
  const activeItems = items.filter(i => i.pedido_id === order.id && i.estado !== 'entregado');
  if (activeItems.length === 0) return 'ok';

  const today = new Date(); today.setHours(0, 0, 0, 0);
  const created = new Date(order.created_date); created.setHours(0, 0, 0, 0);
  const daysSince = Math.floor((today - created) / 86400000);

  // SLA process violations (highest priority)
  for (const item of activeItems) {
    const s = item.estado;
    if (s === 'adjudicado' && daysSince > SLA_PURCHASE)                                           return 'late';
    if (['adjudicado','comprado'].includes(s) && daysSince > SLA_SHIPMENT)                        return 'late';
    if (['adjudicado','comprado','transito','en_aduana'].includes(s) && daysSince > SLA_WAREHOUSE) return 'late';
  }

  // Delivery date proximity
  let minDaysLeft = Infinity;
  for (const item of activeItems) {
    if (item.fecha_entrega_orden) {
      const delivery = new Date(item.fecha_entrega_orden); delivery.setHours(0, 0, 0, 0);
      const daysLeft = Math.ceil((delivery - today) / 86400000);
      if (daysLeft < minDaysLeft) minDaysLeft = daysLeft;
    }
  }
  if (minDaysLeft <= SLA_DELIVERY_URGENT) return 'urgent';
  if (minDaysLeft <= SLA_DELIVERY_ALERT)  return 'alert';

  return 'ok';
}

export default function Dashboard() {
  const { data: tareas = [] } = useQuery({
    queryKey: ["tareas"],
    queryFn: () => Tarea.list("fecha_vencimiento"),
  });
  const { data: orders = [], isLoading: ordersLoading } = useQuery({
    queryKey: ["orders"],
    queryFn: () => base44.entities.Order.list("-created_date"),
  });
  const { data: allOrderItems = [], isLoading: itemsLoading } = useQuery({
    queryKey: ["orderItems"],
    queryFn: () => base44.entities.OrderItem.list(),
  });
  const { data: invoices = [] } = useQuery({
    queryKey: ["invoices"],
    queryFn: () => base44.entities.Invoice.list("-created_date"),
  });

  // ── Tareas KPI ───────────────────────────────────────────────────────────────
  const tareasPendientes = tareas.filter(t => t.estado === "pendiente");
  const tareasAlejandro  = tareasPendientes.filter(t => t.asignado_a === "Alejandro").length;
  const tareasSantiago   = tareasPendientes.filter(t => t.asignado_a === "Santiago").length;
  const tareasAmbos      = tareasPendientes.filter(t => t.asignado_a === "Ambos").length;

  // ── Pedidos KPI — only computed once BOTH queries have resolved ──────────────
  const kpiReady = !ordersLoading && !itemsLoading;
  const isComplete = (orderId) => {
    const items = allOrderItems.filter(i => i.pedido_id === orderId);
    return items.length > 0 && items.every(i => i.estado === 'entregado');
  };
  const activeOrders  = kpiReady ? orders.filter(o => !o.archivado && !isComplete(o.id)) : [];
  const pedidosLate   = activeOrders.filter(o => getOrderHealth(o, allOrderItems) === 'late').length;
  const pedidosUrgent = activeOrders.filter(o => getOrderHealth(o, allOrderItems) === 'urgent').length;
  const pedidosAlert  = activeOrders.filter(o => getOrderHealth(o, allOrderItems) === 'alert').length;
  const pedidosOk     = activeOrders.filter(o => getOrderHealth(o, allOrderItems) === 'ok').length;

  // ── Invoices KPI ──────────────────────────────────────────────────────────────
  const pendingInvoices = invoices.filter(i => i.estado !== "pagado").length;
  const totalRevenue = invoices.filter(i => i.estado === "pagado").reduce((sum, i) => sum + (i.monto_total || 0), 0);

  const getOrderStatusText = (status) => {
    const statusMap = { purchased: "Comprado", shipped: "Enviado", warehouse: "En Bodega", customs: "En Aduana", local_warehouse: "Bodega Local", shipped_to_client: "Enviado a Cliente", delivered: "Entregado" };
    return statusMap[status] || status;
  };
  const getOrderStatusColor = (status) => {
    const colorMap = { purchased: "bg-blue-100 text-blue-800", shipped: "bg-purple-100 text-purple-800", warehouse: "bg-amber-100 text-amber-800", customs: "bg-orange-100 text-orange-800", local_warehouse: "bg-cyan-100 text-cyan-800", shipped_to_client: "bg-indigo-100 text-indigo-800", delivered: "bg-green-100 text-green-800" };
    return colorMap[status] || "bg-gray-100 text-gray-800";
  };
  const getInvoiceStatusColor = (status) => {
    const colorMap = { pendiente: "bg-gray-100 text-gray-800", facturado: "bg-blue-100 text-blue-800", retencion: "bg-amber-100 text-amber-800", pagado: "bg-green-100 text-green-800" };
    return colorMap[status] || "bg-gray-100 text-gray-800";
  };

  return (
    <div className="p-6 lg:p-8 space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 mb-2">Dashboard</h1>
        <p className="text-slate-600">Resumen general de tu operación de importación</p>
      </div>

      {/* ── KPI cards ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="border-none shadow-lg bg-gradient-to-br from-blue-500 to-blue-600 text-white overflow-hidden relative">
          <div className="absolute top-0 right-0 w-32 h-32 bg-white opacity-10 rounded-full -mr-16 -mt-16" />
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CheckSquare className="w-8 h-8" />
              <TrendingUp className="w-5 h-5 opacity-70" />
            </div>
            <p className="text-blue-100 text-sm mt-1">Tareas Pendientes</p>
          </CardHeader>
          <CardContent className="pt-0 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-blue-200 text-xs">Alejandro</span>
              <span className="text-2xl font-bold">{tareasAlejandro}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-blue-200 text-xs">Santiago</span>
              <span className="text-2xl font-bold">{tareasSantiago}</span>
            </div>
            <div className="flex items-center justify-between border-t border-blue-400/40 pt-1.5">
              <span className="text-blue-200 text-xs">Ambos</span>
              <span className="text-2xl font-bold">{tareasAmbos}</span>
            </div>
          </CardContent>
        </Card>
        <Card className="border-none shadow-lg bg-gradient-to-br from-purple-500 to-purple-600 text-white overflow-hidden relative">
          <div className="absolute top-0 right-0 w-32 h-32 bg-white opacity-10 rounded-full -mr-16 -mt-16" />
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <Truck className="w-8 h-8" />
              <Package className="w-5 h-5 opacity-70" />
            </div>
            <p className="text-purple-100 text-sm mt-1">Pedidos en Tránsito</p>
          </CardHeader>
          <CardContent className="pt-0 space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-red-200 text-xs flex items-center gap-1"><AlertTriangle className="w-3 h-3" />Atrasados</span>
              <span className="text-xl font-bold">{kpiReady ? pedidosLate : '—'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-orange-200 text-xs flex items-center gap-1"><Clock className="w-3 h-3" />Vencen &lt; 5 días</span>
              <span className="text-xl font-bold">{kpiReady ? pedidosUrgent : '—'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-yellow-200 text-xs flex items-center gap-1"><Clock className="w-3 h-3" />Vencen &lt; 10 días</span>
              <span className="text-xl font-bold">{kpiReady ? pedidosAlert : '—'}</span>
            </div>
            <div className="flex items-center justify-between border-t border-purple-400/40 pt-1">
              <span className="text-purple-200 text-xs">En Tiempo</span>
              <span className="text-xl font-bold">{kpiReady ? pedidosOk : '—'}</span>
            </div>
          </CardContent>
        </Card>
        <Card className="border-none shadow-lg bg-gradient-to-br from-amber-500 to-amber-600 text-white overflow-hidden relative">
          <div className="absolute top-0 right-0 w-32 h-32 bg-white opacity-10 rounded-full -mr-16 -mt-16" />
          <CardHeader className="pb-3"><div className="flex items-center justify-between"><FileText className="w-8 h-8" /><ShoppingCart className="w-5 h-5 opacity-70" /></div></CardHeader>
          <CardContent><div className="text-3xl font-bold mb-1">{pendingInvoices}</div><p className="text-amber-100 text-sm">Facturas Pendientes</p></CardContent>
        </Card>
        <Card className="border-none shadow-lg bg-gradient-to-br from-green-500 to-green-600 text-white overflow-hidden relative">
          <div className="absolute top-0 right-0 w-32 h-32 bg-white opacity-10 rounded-full -mr-16 -mt-16" />
          <CardHeader className="pb-3"><div className="flex items-center justify-between"><DollarSign className="w-8 h-8" /><TrendingUp className="w-5 h-5 opacity-70" /></div></CardHeader>
          <CardContent><div className="text-3xl font-bold mb-1">${totalRevenue.toFixed(2)}</div><p className="text-green-100 text-sm">Ingresos Cobrados</p></CardContent>
        </Card>
      </div>

      {/* ── To-do panel ── */}
      <TodoPanel />

      {/* ── Recent lists ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-none shadow-lg">
          <CardHeader className="border-b border-slate-100">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg font-bold text-slate-900">Pedidos Recientes</CardTitle>
              <Link to={createPageUrl("Pedidos")} className="text-sm text-blue-600 hover:text-blue-700 font-medium">Ver todos →</Link>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-slate-100">
              {orders.slice(0, 5).map((order) => (
                <div key={order.id} className="p-4 hover:bg-slate-50 transition-colors">
                  <div className="flex items-center justify-between mb-2">
                    <div className="font-semibold text-slate-900">{order.numero_pedido}</div>
                    <Badge className={getOrderStatusColor(order.estado_actual)}>{getOrderStatusText(order.estado_actual)}</Badge>
                  </div>
                  <div className="text-sm text-slate-600">{order.producto_nombre} • {order.cantidad} unidades</div>
                  <div className="text-xs text-slate-500 mt-1">Cliente: {order.cliente}</div>
                </div>
              ))}
              {orders.length === 0 && <div className="p-8 text-center text-slate-500">No hay pedidos registrados</div>}
            </div>
          </CardContent>
        </Card>
        <Card className="border-none shadow-lg">
          <CardHeader className="border-b border-slate-100">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg font-bold text-slate-900">Facturas Recientes</CardTitle>
              <Link to={createPageUrl("Facturacion")} className="text-sm text-blue-600 hover:text-blue-700 font-medium">Ver todas →</Link>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-slate-100">
              {invoices.slice(0, 5).map((invoice) => (
                <div key={invoice.id} className="p-4 hover:bg-slate-50 transition-colors">
                  <div className="flex items-center justify-between mb-2">
                    <div className="font-semibold text-slate-900">{invoice.numero_factura}</div>
                    <Badge className={getInvoiceStatusColor(invoice.estado)}>{invoice.estado.toUpperCase()}</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-slate-600">Pedido: {invoice.pedido_numero}</div>
                    <div className="font-semibold text-slate-900">${invoice.monto_total.toFixed(2)}</div>
                  </div>
                  <div className="text-xs text-slate-500 mt-1">Cliente: {invoice.cliente}</div>
                </div>
              ))}
              {invoices.length === 0 && <div className="p-8 text-center text-slate-500">No hay facturas registradas</div>}
            </div>
          </CardContent>
        </Card>
      </div>

    </div>
  );
}
