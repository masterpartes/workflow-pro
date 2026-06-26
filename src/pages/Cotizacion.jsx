import React, { useState } from "react";
import { base44 } from "@/api/base44Client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import PriceCalculator from "../components/cotizacion/PriceCalculator";
import ProductList from "../components/cotizacion/ProductList";

export default function Cotizacion() {
  const [selectedProduct, setSelectedProduct] = useState(null);
  const queryClient = useQueryClient();

  const { data: products = [], isLoading } = useQuery({
    queryKey: ["products"],
    queryFn: () => base44.entities.Product.list("-created_date"),
  });

  const { data: orders = [] } = useQuery({
    queryKey: ["orders"],
    queryFn: () => base44.entities.Order.list("-created_date"),
  });

  const { data: orderItems = [] } = useQuery({
    queryKey: ["orderItems"],
    queryFn: () => base44.entities.OrderItem.list(),
  });

  const createMutation = useMutation({
    mutationFn: (data) => base44.entities.Product.create(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: async (ids) => {
      await Promise.all(ids.map(id => base44.entities.Product.delete(id)));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      setSelectedProduct(null);
    },
  });

  return (
    <div className="p-6 lg:p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900 mb-2">Cotización</h1>
        <p className="text-slate-600">Catálogo de productos importados y calculadora de precios</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ProductList
            products={products}
            isLoading={isLoading}
            onDelete={(ids) => bulkDeleteMutation.mutate(ids)}
            onSelect={setSelectedProduct}
            selectedProduct={selectedProduct}
            onCreate={(data) => createMutation.mutateAsync(data)}
            isCreating={createMutation.isPending}
            orders={orders}
            orderItems={orderItems}
          />
        </div>
        <div>
          <PriceCalculator
            selectedProduct={selectedProduct}
            products={products}
            onProductSelect={setSelectedProduct}
          />
        </div>
      </div>
    </div>
  );
}
