import React from "react";
import { base44 } from "@/api/base44Client";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { createPageUrl } from "@/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Calculator, Package, FileText, TrendingUp, ShoppingCart, Truck, DollarSign } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function Dashboard() {
  const { data: products = [] } = useQuery({
    queryKey: ["products"],
    queryFn: () => base44.entities.Product.list(),
  });
  const { data: orders = [] } = useQuery({
    queryKey: ["orders"],
    queryFn: () => base44.entities.Order.list("-created_date"),
  });
  const { data: invoices = [] } = useQuery({
    queryKey: ["invoices"],
    queryFn: () => base44.entities.Invoice.list("-created_date"),
  });

  const ordersInTransit = orders.filter(o => !["delivered"].includes(o.estado_actual)).length;
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
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="border-none shadow-lg bg-gradient-to-br from-blue-500 to-blue-600 text-white overflow-hidden relative">
          <div className="absolute top-0 right-0 w-32 h-32 bg-white opacity-10 rounded-full -mr-16 -mt-16" />
          <CardHeader className="pb-3"><div className="flex items-center justify-between"><Calculator className="w-8 h-8" /><TrendingUp className="w-5 h-5 opacity-70" /></div></CardHeader>
          <CardContent><div className="text-3xl font-bold mb-1">{products.length}</div><p className="text-blue-100 text-sm">Productos en Catálogo</p></CardContent>
        </Card>
        <Card className="border-none shadow-lg bg-gradient-to-br from-purple-500 to-purple-600 text-white overflow-hidden relative">
          <div className="absolute top-0 right-0 w-32 h-32 bg-white opacity-10 rounded-full -mr-16 -mt-16" />
          <CardHeader className="pb-3"><div className="flex items-center justify-between"><Package className="w-8 h-8" /><Truck className="w-5 h-5 opacity-70" /></div></CardHeader>
          <CardContent><div className="text-3xl font-bold mb-1">{ordersInTransit}</div><p className="text-purple-100 text-sm">Pedidos en Tránsito</p></CardContent>
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
