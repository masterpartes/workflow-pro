import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import { format } from "date-fns";

const orderStages = [
  { key: 'purchased', label: 'Comprado', dateField: 'fecha_compra' },
  { key: 'shipped', label: 'Enviado', dateField: 'fecha_envio', extraFields: ['tracking_internacional'] },
  { key: 'warehouse', label: 'En Bodega', dateField: 'fecha_llegada_bodega', extraFields: ['registro_bodega'] },
  { key: 'customs', label: 'En Aduana', dateField: 'fecha_llegada_aduana', extraFields: ['declaracion_aduanera'] },
  { key: 'local_warehouse', label: 'Bodega Local', dateField: 'fecha_entrega_bodega_local' },
  { key: 'shipped_to_client', label: 'Enviado a Cliente', dateField: 'fecha_envio_cliente', extraFields: ['tracking_cliente'] },
  { key: 'delivered', label: 'Entregado', dateField: 'fecha_entrega_cliente', extraFields: ['prueba_entrega'] },
];

export default function OrderTimeline({ order, onUpdate, isUpdating }) {
  const [editingStage, setEditingStage] = useState(null);
  const [formData, setFormData] = useState({});
  const currentStageIndex = orderStages.findIndex(s => s.key === order.estado_actual);

  const handleStageClick = (stage, index) => {
    if (index <= currentStageIndex + 1) {
      setEditingStage(stage.key);
      setFormData({
        [stage.dateField]: order[stage.dateField] || new Date().toISOString().split('T')[0],
        ...(stage.extraFields?.reduce((acc, field) => ({ ...acc, [field]: order[field] || '' }), {}) || {})
      });
    }
  };

  const handleUpdate = () => {
    onUpdate({ ...formData, estado_actual: editingStage });
    setEditingStage(null);
  };

  return (
    <Card className="border-none shadow-lg sticky top-6">
      <CardHeader className="border-b border-slate-100 bg-gradient-to-r from-purple-50 to-indigo-50">
        <CardTitle className="text-lg font-bold text-slate-900">Seguimiento de Pedido</CardTitle>
      </CardHeader>
      <CardContent className="p-6">
        <div className="space-y-1">
          {orderStages.map((stage, index) => {
            const isCompleted = index <= currentStageIndex;
            const isNext = index === currentStageIndex + 1;
            const isEditing = editingStage === stage.key;
            return (
              <div key={stage.key}>
                <div onClick={() => handleStageClick(stage, index)} className={`flex items-start gap-3 p-3 rounded-lg transition-all ${isNext ? 'cursor-pointer hover:bg-slate-50' : ''} ${isEditing ? 'bg-purple-50 border border-purple-200' : ''}`}>
                  <div className="flex flex-col items-center">
                    {isCompleted ? <CheckCircle2 className="w-6 h-6 text-green-600" /> : <Circle className={`w-6 h-6 ${isNext ? 'text-purple-600' : 'text-slate-300'}`} />}
                    {index < orderStages.length - 1 && <div className={`w-0.5 h-8 mt-1 ${isCompleted ? 'bg-green-600' : 'bg-slate-200'}`} />}
                  </div>
                  <div className="flex-1 pt-0.5">
                    <p className={`font-medium ${isCompleted ? 'text-slate-900' : 'text-slate-500'}`}>{stage.label}</p>
                    {order[stage.dateField] && <p className="text-xs text-slate-500 mt-1">{format(new Date(order[stage.dateField]), 'dd/MM/yyyy')}</p>}
                  </div>
                </div>
                {isEditing && (
                  <div className="ml-9 mt-2 p-4 bg-white border border-purple-200 rounded-lg space-y-3">
                    <div className="space-y-2">
                      <Label htmlFor={stage.dateField}>Fecha</Label>
                      <Input id={stage.dateField} type="date" value={formData[stage.dateField] || ''} onChange={(e) => setFormData({ ...formData, [stage.dateField]: e.target.value })} />
                    </div>
                    {stage.extraFields?.map(field => (
                      <div key={field} className="space-y-2">
                        <Label htmlFor={field}>{field.replace(/_/g, ' ')}</Label>
                        <Input id={field} value={formData[field] || ''} onChange={(e) => setFormData({ ...formData, [field]: e.target.value })} />
                      </div>
                    ))}
                    <div className="flex gap-2 pt-2">
                      <Button onClick={handleUpdate} disabled={isUpdating} size="sm" className="bg-purple-600 hover:bg-purple-700 flex-1">
                        {isUpdating ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Actualizar'}
                      </Button>
                      <Button onClick={() => setEditingStage(null)} variant="outline" size="sm">Cancelar</Button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}