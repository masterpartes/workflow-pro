import React, { useState } from "react";
import { base44 } from "@/api/base44Client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, Archive, Trash2 } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import OrderList from "../components/pedidos/OrderList";
import OrderForm from "../components/pedidos/OrderForm";
import OrderDetail from "../components/pedidos/OrderDetail";
import CompletedOrders from "../components/pedidos/CompletedOrders";

function ArchivedActionSelect({ orderId, onUnarchive, onDelete }) {
  const [key, setKey] = React.useState(0);
  const handle = (v) => {
    if (v === "unarchive") onUnarchive();
    if (v === "delete")    onDelete();
    setKey(k => k + 1);
  };
  return (
    <Select key={key} onValueChange={handle}>
      <SelectTrigger className="w-40 h-8 text-xs shrink-0">
        <SelectValue placeholder="Acciones" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="unarchive">Volver a En Curso</SelectItem>
        <SelectItem value="delete" className="text-red-600">Eliminar</SelectItem>
      </SelectContent>
    </Select>
  );
}

export default function Pedidos() {
  const [showForm, setShowForm] = useState(false);
  const [editingOrder, setEditingOrder] = useState(null);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const queryClient = useQueryClient();

  const { data: orders = [], isLoading } = useQuery({
    queryKey: ["orders"],
    queryFn: () => base44.entities.Order.list("-created_date"),
  });
  const { data: allOrderItems = [] } = useQuery({
    queryKey: ["orderItems"],
    queryFn: () => base44.entities.OrderItem.list(),
  });
  const { data: products = [] } = useQuery({
    queryKey: ["products"],
    queryFn: () => base44.entities.Product.list(),
  });

  const createOrderMutation = useMutation({
    mutationFn: (data) => base44.entities.Order.create(data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["orders"] }); },
  });
  const updateOrderMutation = useMutation({
    mutationFn: ({ id, data }) => base44.entities.Order.update(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["orders"] }); },
  });
  const createOrderItemsMutation = useMutation({
    mutationFn: (items) => base44.entities.OrderItem.bulkCreate(items),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orderItems"] });
      setShowForm(false);
      setEditingOrder(null);
    },
  });
  const updateOrderItemsMutation = useMutation({
    mutationFn: async ({ itemsToUpdate, itemsToCreate, itemsToDelete }) => {
      await Promise.all(itemsToUpdate.map(item => base44.entities.OrderItem.update(item.id, item)));
      if (itemsToCreate.length > 0) await base44.entities.OrderItem.bulkCreate(itemsToCreate);
      await Promise.all(itemsToDelete.map(id => base44.entities.OrderItem.delete(id)));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orderItems"] });
      setShowForm(false);
      setEditingOrder(null);
    },
  });
  const deleteOrderMutation = useMutation({
    mutationFn: async (orderId) => {
      const items = allOrderItems.filter(item => item.pedido_id === orderId);
      await Promise.all(items.map(item => base44.entities.OrderItem.delete(item.id)));
      await base44.entities.Order.delete(orderId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["orderItems"] });
      setSelectedOrder(null);
    },
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: async (ids) => {
      await Promise.all(ids.map(async (orderId) => {
        const items = allOrderItems.filter(item => item.pedido_id === orderId);
        await Promise.all(items.map(item => base44.entities.OrderItem.delete(item.id)));
        await base44.entities.Order.delete(orderId);
      }));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["orderItems"] });
      setSelectedIds(new Set());
      setSelectionMode(false);
      setSelectedOrder(null);
    },
  });

  const bulkArchiveMutation = useMutation({
    mutationFn: async (ids) => {
      await Promise.all(ids.map(id => base44.entities.Order.update(id, { archivado: true })));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      setSelectedIds(new Set());
      setSelectionMode(false);
      setSelectedOrder(null);
    },
  });

  const unarchiveMutation = useMutation({
    mutationFn: (id) => base44.entities.Order.update(id, { archivado: false }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["orders"] }),
  });

  // Reset all items back to 'adjudicado' so order leaves Completados → En Curso
  const reopenOrderMutation = useMutation({
    mutationFn: async (orderId) => {
      const items = allOrderItems.filter(i => i.pedido_id === orderId);
      await Promise.all(items.map(i => base44.entities.OrderItem.update(i.id, { estado: 'adjudicado' })));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["orderItems"] }),
  });

  const archiveOrderMutation = useMutation({
    mutationFn: (id) => base44.entities.Order.update(id, { archivado: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      setSelectedOrder(null);
    },
  });

  // Sanitize items before sending to Supabase:
  // - producto_id must be null (not "") when not linked to a product
  // - fecha_entrega_orden must be null (not "") when not set
  const sanitizeItems = (rawItems) => rawItems.map(item => ({
    ...item,
    producto_id: item.producto_id || null,
    fecha_entrega_orden: item.fecha_entrega_orden || null,
    estado: item.estado || 'adjudicado',
  }));

  const handleSubmit = async (orderData, items) => {
    if (editingOrder) {
      await updateOrderMutation.mutateAsync({ id: editingOrder.id, data: orderData });
      const existingItems = allOrderItems.filter(item => item.pedido_id === editingOrder.id);
      const itemsToUpdate = sanitizeItems(items.filter(item => item.id)).map(item => ({ ...item, pedido_id: editingOrder.id, pedido_numero: orderData.numero_pedido }));
      const itemsToCreate = sanitizeItems(items.filter(item => !item.id)).map(item => ({ ...item, pedido_id: editingOrder.id, pedido_numero: orderData.numero_pedido }));
      const itemsToDelete = existingItems.filter(existingItem => !items.find(item => item.id === existingItem.id)).map(item => item.id);
      await updateOrderItemsMutation.mutateAsync({ itemsToUpdate, itemsToCreate, itemsToDelete });
    } else {
      const order = await createOrderMutation.mutateAsync(orderData);
      const itemsWithOrderId = sanitizeItems(items).map(item => ({ ...item, pedido_id: order.id, pedido_numero: orderData.numero_pedido }));
      await createOrderItemsMutation.mutateAsync(itemsWithOrderId);
    }
  };

  const activeOrders = orders.filter(o => !o.archivado);
  const archivedOrders = orders.filter(o => o.archivado);

  const handleToggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };
  const handleSelectAll = (ids) => setSelectedIds(new Set(ids));
  const handleToggleSelectionMode = () => {
    setSelectionMode(prev => !prev);
    setSelectedIds(new Set());
  };
  const handleBulkDelete = () => {
    if (confirm(`¿Eliminar ${selectedIds.size} pedido${selectedIds.size !== 1 ? 's' : ''} y todos sus productos? Esta acción no se puede deshacer.`))
      bulkDeleteMutation.mutate([...selectedIds]);
  };
  const handleBulkArchive = () => {
    bulkArchiveMutation.mutate([...selectedIds]);
  };

  return (
    <div className="p-6 lg:p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Pedidos</h1>
          <p className="text-slate-600">Gestiona pedidos y rastrea el estado de cada producto</p>
        </div>
        <Button
          onClick={() => { setEditingOrder(null); setSelectedOrder(null); setShowForm(true); setSelectionMode(false); }}
          className="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 shadow-lg"
        >
          <Plus className="w-5 h-5 mr-2" />
          Nuevo Pedido
        </Button>
      </div>
      <Tabs defaultValue="active" className="w-full">
        <TabsList className="mb-6">
          <TabsTrigger value="active">Pedidos en Curso</TabsTrigger>
          <TabsTrigger value="completed">Pedidos Completados</TabsTrigger>
          <TabsTrigger value="archived" className="relative">
            Archivados
            {archivedOrders.length > 0 && (
              <Badge className="ml-2 bg-slate-500 text-white text-xs px-1.5 py-0">{archivedOrders.length}</Badge>
            )}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="active">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              {showForm ? (
                <OrderForm
                  order={editingOrder}
                  orderItems={editingOrder ? allOrderItems.filter(item => item.pedido_id === editingOrder.id) : null}
                  products={products}
                  onSubmit={handleSubmit}
                  onCancel={() => { setShowForm(false); setEditingOrder(null); }}
                  isLoading={createOrderMutation.isPending || createOrderItemsMutation.isPending || updateOrderMutation.isPending || updateOrderItemsMutation.isPending}
                />
              ) : (
                <OrderList
                  orders={activeOrders}
                  orderItems={allOrderItems}
                  isLoading={isLoading}
                  onEdit={(order) => { setEditingOrder(order); setSelectedOrder(null); setShowForm(true); }}
                  onDelete={(id) => { if (confirm("¿Estás seguro de eliminar este pedido y todos sus productos?")) deleteOrderMutation.mutate(id); }}
                  onArchive={(id) => archiveOrderMutation.mutate(id)}
                  onSelect={(order) => { setSelectedOrder(order); setShowForm(false); }}
                  selectedOrder={selectedOrder}
                  selectionMode={selectionMode}
                  selectedIds={selectedIds}
                  onToggleSelect={handleToggleSelect}
                  onSelectAll={handleSelectAll}
                  onBulkDelete={handleBulkDelete}
                  onBulkArchive={handleBulkArchive}
                  onToggleSelectionMode={handleToggleSelectionMode}
                />
              )}
            </div>
            <div>
              {selectedOrder && !selectionMode && (
                <OrderDetail
                  order={selectedOrder}
                  orderItems={allOrderItems.filter(item => item.pedido_id === selectedOrder.id)}
                />
              )}
            </div>
          </div>
        </TabsContent>
        <TabsContent value="completed">
          <CompletedOrders
            orders={activeOrders}
            orderItems={allOrderItems}
            onDelete={(id) => { if (confirm("¿Eliminar este pedido y todos sus productos?")) deleteOrderMutation.mutate(id); }}
            onArchive={(id) => archiveOrderMutation.mutate(id)}
            onReopen={(id) => reopenOrderMutation.mutate(id)}
          />
        </TabsContent>
        <TabsContent value="archived">
          <div className="space-y-3">
            {archivedOrders.length === 0 ? (
              <div className="text-center py-16">
                <Archive className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                <p className="text-slate-600">No hay pedidos archivados</p>
              </div>
            ) : (
              archivedOrders.map((order) => {
                const items = allOrderItems.filter(item => item.pedido_id === order.id);
                return (
                  <div key={order.id} className="border-2 border-slate-200 rounded-xl bg-slate-50 p-4 flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="font-bold text-slate-700">{order.numero_pedido}</h3>
                        <Badge variant="outline" className="text-xs text-slate-500">{items.length} producto{items.length !== 1 ? 's' : ''}</Badge>
                      </div>
                      <p className="text-sm text-slate-500">Cliente: {order.cliente}</p>
                    </div>
                    <ArchivedActionSelect
                      orderId={order.id}
                      onUnarchive={() => unarchiveMutation.mutate(order.id)}
                      onDelete={() => { if (confirm("¿Eliminar este pedido y todos sus productos?")) deleteOrderMutation.mutate(order.id); }}
                    />
                  </div>
                );
              })
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
