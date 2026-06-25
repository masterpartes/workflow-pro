import React, { useState } from "react";
import { base44 } from "@/api/base44Client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import OrderList from "../components/pedidos/OrderList";
import OrderForm from "../components/pedidos/OrderForm";
import OrderDetail from "../components/pedidos/OrderDetail";
import CompletedOrders from "../components/pedidos/CompletedOrders";

export default function Pedidos() {
  const [showForm, setShowForm] = useState(false);
  const [editingOrder, setEditingOrder] = useState(null);
  const [selectedOrder, setSelectedOrder] = useState(null);
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

  const handleSubmit = async (orderData, items) => {
    if (editingOrder) {
      await updateOrderMutation.mutateAsync({ id: editingOrder.id, data: orderData });
      const existingItems = allOrderItems.filter(item => item.pedido_id === editingOrder.id);
      const itemsToUpdate = items.filter(item => item.id).map(item => ({ ...item, pedido_id: editingOrder.id, pedido_numero: orderData.numero_pedido }));
      const itemsToCreate = items.filter(item => !item.id).map(item => ({ ...item, pedido_id: editingOrder.id, pedido_numero: orderData.numero_pedido }));
      const itemsToDelete = existingItems.filter(existingItem => !items.find(item => item.id === existingItem.id)).map(item => item.id);
      await updateOrderItemsMutation.mutateAsync({ itemsToUpdate, itemsToCreate, itemsToDelete });
    } else {
      const order = await createOrderMutation.mutateAsync(orderData);
      const itemsWithOrderId = items.map(item => ({ ...item, pedido_id: order.id, pedido_numero: orderData.numero_pedido }));
      await createOrderItemsMutation.mutateAsync(itemsWithOrderId);
    }
  };

  return (
    <div className="p-6 lg:p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Pedidos</h1>
          <p className="text-slate-600">Gestiona pedidos y rastrea el estado de cada producto</p>
        </div>
        <Button
          onClick={() => { setEditingOrder(null); setSelectedOrder(null); setShowForm(true); }}
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
                  orders={orders}
                  orderItems={allOrderItems}
                  isLoading={isLoading}
                  onEdit={(order) => { setEditingOrder(order); setSelectedOrder(null); setShowForm(true); }}
                  onDelete={(id) => { if (confirm("¿Estás seguro de eliminar este pedido y todos sus productos?")) deleteOrderMutation.mutate(id); }}
                  onSelect={(order) => { setSelectedOrder(order); setShowForm(false); }}
                  selectedOrder={selectedOrder}
                />
              )}
            </div>
            <div>
              {selectedOrder && (
                <OrderDetail
                  order={selectedOrder}
                  orderItems={allOrderItems.filter(item => item.pedido_id === selectedOrder.id)}
                />
              )}
            </div>
          </div>
        </TabsContent>
        <TabsContent value="completed">
          <CompletedOrders orders={orders} orderItems={allOrderItems} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
