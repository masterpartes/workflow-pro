import React, { useState, useMemo, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Tarea } from "@/api/entities";
import { UploadFile } from "@/api/integrations";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  AlertTriangle, Plus, CheckCircle2, Archive, RotateCcw,
  Trash2, CheckSquare, X, Upload, Calendar, User, Paperclip,
  Clock, Square,
} from "lucide-react";

// ── Helpers ────────────────────────────────────────────────────────────────────

function today0() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

function parseDate(str) {
  // str is "YYYY-MM-DD"
  const [y, m, d] = str.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function urgency(tarea) {
  if (tarea.estado === "completado") return "done";
  if (tarea.estado === "archivado")  return "archived";
  const hoy  = today0();
  const venc = parseDate(tarea.fecha_vencimiento);
  const diff = Math.round((venc - hoy) / 86400000); // days
  if (diff < 0)  return "vencida";
  if (diff === 0) return "hoy";
  if (diff <= 2)  return "pronto";
  return "ok";
}

const URGENCY_STYLES = {
  vencida:  { card: "border-red-300 bg-red-50",    badge: "bg-red-100 text-red-800 border-red-200",     label: "VENCIDA" },
  hoy:      { card: "border-amber-300 bg-amber-50", badge: "bg-amber-100 text-amber-800 border-amber-200", label: "VENCE HOY" },
  pronto:   { card: "border-yellow-300 bg-yellow-50", badge: "bg-yellow-100 text-yellow-800 border-yellow-200", label: "PRÓXIMA" },
  ok:       { card: "border-slate-200 bg-white",   badge: "bg-slate-100 text-slate-600 border-slate-200", label: "" },
  done:     { card: "border-green-200 bg-green-50", badge: "bg-green-100 text-green-800 border-green-200", label: "COMPLETADA" },
  archived: { card: "border-slate-200 bg-slate-50", badge: "bg-slate-100 text-slate-500 border-slate-200", label: "" },
};

function formatDate(str) {
  if (!str) return "";
  const [y, m, d] = str.split("-");
  return `${d}/${m}/${y}`;
}

const USERS = ["Santiago", "Alejandro", "Ambos"];

// ── Empty form ────────────────────────────────────────────────────────────────
const emptyForm = () => ({
  titulo: "",
  descripcion: "",
  entregable_tipo: "texto",
  entregable_url: "",
  entregable_texto: "",
  fecha_vencimiento: "",
  asignado_a: "Ambos",
  creado_por: "Alejandro",
});

// ═══════════════════════════════════════════════════════════════════════════════
export default function TodoPanel() {
  const qc = useQueryClient();
  const fileRef = useRef(null);

  const [activeTab,     setActiveTab]     = useState("pendientes");
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds,   setSelectedIds]   = useState(new Set());
  const [showDialog,    setShowDialog]    = useState(false);
  const [form,          setForm]          = useState(emptyForm());
  const [uploading,     setUploading]     = useState(false);
  const [saving,        setSaving]        = useState(false);

  // ── Data ────────────────────────────────────────────────────────────────────
  const { data: allTareas = [], isLoading } = useQuery({
    queryKey: ["tareas"],
    queryFn: () => Tarea.list("fecha_vencimiento"),
  });

  const activas    = useMemo(() => allTareas.filter(t => t.estado !== "archivado"), [allTareas]);
  const archivadas = useMemo(() => allTareas.filter(t => t.estado === "archivado"), [allTareas]);
  const vencidas   = useMemo(() => activas.filter(t => urgency(t) === "vencida"),   [activas]);

  // ── Mutations ───────────────────────────────────────────────────────────────
  const invalidate = () => qc.invalidateQueries({ queryKey: ["tareas"] });

  const mutUpdate = useMutation({
    mutationFn: ({ id, updates }) => Tarea.update(id, updates),
    onSuccess: invalidate,
  });

  const mutDelete = useMutation({
    mutationFn: (id) => Tarea.delete(id),
    onSuccess: invalidate,
  });

  const mutCreate = useMutation({
    mutationFn: (data) => Tarea.create(data),
    onSuccess: () => { invalidate(); setShowDialog(false); setForm(emptyForm()); },
  });

  // ── Selection helpers ───────────────────────────────────────────────────────
  function toggleSelect(id) {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }
  function clearSelection() { setSelectedIds(new Set()); setSelectionMode(false); }

  async function bulkUpdate(updates) {
    await Promise.all([...selectedIds].map(id => Tarea.update(id, updates)));
    invalidate();
    clearSelection();
  }

  // ── File upload ─────────────────────────────────────────────────────────────
  async function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const { file_url } = await UploadFile({ file });
      setForm(f => ({ ...f, entregable_url: file_url }));
    } catch (err) {
      console.error(err);
    } finally {
      setUploading(false);
    }
  }

  // ── Save ────────────────────────────────────────────────────────────────────
  async function handleSave() {
    if (!form.titulo.trim() || !form.fecha_vencimiento) return;
    setSaving(true);
    try {
      await mutCreate.mutateAsync({
        ...form,
        estado: "pendiente",
        created_date: new Date().toISOString(),
      });
    } finally {
      setSaving(false);
    }
  }

  // ── Single-task actions ─────────────────────────────────────────────────────
  function markDone(t) {
    mutUpdate.mutate({ id: t.id, updates: { estado: "completado", completado_en: new Date().toISOString() } });
  }
  function markPending(t) {
    mutUpdate.mutate({ id: t.id, updates: { estado: "pendiente", completado_en: null } });
  }
  function archiveOne(t) {
    mutUpdate.mutate({ id: t.id, updates: { estado: "archivado" } });
  }
  function unarchiveOne(t) {
    mutUpdate.mutate({ id: t.id, updates: { estado: t.completado_en ? "completado" : "pendiente" } });
  }
  function deleteOne(t) {
    if (window.confirm(`¿Eliminar la tarea "${t.titulo}"?`)) mutDelete.mutate(t.id);
  }

  // ── Task card ───────────────────────────────────────────────────────────────
  function TaskCard({ tarea, isArchived = false }) {
    const u   = urgency(tarea);
    const sty = URGENCY_STYLES[u];
    const checked = selectedIds.has(tarea.id);

    return (
      <div className={`relative rounded-xl border-2 p-4 transition-all ${sty.card} ${checked ? "ring-2 ring-blue-400" : ""}`}>
        {/* Selection checkbox */}
        {selectionMode && (
          <div className="absolute top-3 left-3">
            <Checkbox
              checked={checked}
              onCheckedChange={() => toggleSelect(tarea.id)}
              className="w-5 h-5"
            />
          </div>
        )}

        <div className={`flex items-start gap-3 ${selectionMode ? "pl-7" : ""}`}>
          {/* Main content */}
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <span className="font-semibold text-slate-900 text-sm">{tarea.titulo}</span>
              {sty.label && (
                <Badge variant="outline" className={`text-[10px] font-bold tracking-wide px-1.5 py-0 ${sty.badge}`}>
                  {sty.label}
                </Badge>
              )}
            </div>

            {tarea.descripcion && (
              <p className="text-xs text-slate-600 mb-2 line-clamp-2">{tarea.descripcion}</p>
            )}

            <div className="flex flex-wrap gap-3 text-xs text-slate-500">
              <span className="flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                {formatDate(tarea.fecha_vencimiento)}
              </span>
              <span className="flex items-center gap-1">
                <User className="w-3 h-3" />
                {tarea.asignado_a}
              </span>
              {tarea.creado_por && (
                <span className="text-slate-400">por {tarea.creado_por}</span>
              )}
            </div>

            {/* Entregable */}
            {tarea.entregable_tipo === "texto" && tarea.entregable_texto && (
              <div className="mt-2 text-xs bg-white/70 rounded-lg p-2 border border-slate-200 text-slate-600">
                <span className="font-medium text-slate-700 block mb-0.5">Entregable:</span>
                {tarea.entregable_texto}
              </div>
            )}
            {(tarea.entregable_tipo === "archivo" || tarea.entregable_tipo === "foto") && tarea.entregable_url && (
              <div className="mt-2">
                {tarea.entregable_tipo === "foto"
                  ? <img src={tarea.entregable_url} alt="entregable" className="max-h-28 rounded-lg object-contain border border-slate-200" />
                  : <a href={tarea.entregable_url} target="_blank" rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline">
                      <Paperclip className="w-3 h-3" /> Ver archivo adjunto
                    </a>
                }
              </div>
            )}
          </div>

          {/* Action buttons */}
          {!selectionMode && (
            <div className="flex flex-col gap-1 shrink-0">
              {!isArchived && (
                <>
                  {tarea.estado !== "completado"
                    ? <Button size="sm" variant="outline" onClick={() => markDone(tarea)}
                        className="h-7 text-xs text-green-700 border-green-300 hover:bg-green-50 px-2">
                        <CheckCircle2 className="w-3 h-3 mr-1" /> Hecho
                      </Button>
                    : <Button size="sm" variant="outline" onClick={() => markPending(tarea)}
                        className="h-7 text-xs text-slate-600 border-slate-300 hover:bg-slate-50 px-2">
                        <Clock className="w-3 h-3 mr-1" /> Reabrir
                      </Button>
                  }
                  <Button size="sm" variant="outline" onClick={() => archiveOne(tarea)}
                    className="h-7 text-xs text-slate-600 border-slate-300 hover:bg-slate-50 px-2">
                    <Archive className="w-3 h-3 mr-1" /> Archivar
                  </Button>
                </>
              )}
              {isArchived && (
                <Button size="sm" variant="outline" onClick={() => unarchiveOne(tarea)}
                  className="h-7 text-xs text-blue-700 border-blue-300 hover:bg-blue-50 px-2">
                  <RotateCcw className="w-3 h-3 mr-1" /> Recuperar
                </Button>
              )}
              <Button size="sm" variant="ghost" onClick={() => deleteOne(tarea)}
                className="h-7 text-xs text-red-500 hover:text-red-700 hover:bg-red-50 px-2">
                <Trash2 className="w-3 h-3" />
              </Button>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Tab toolbar (select / bulk actions) ────────────────────────────────────
  function TabToolbar({ list, isArchived }) {
    const count = [...selectedIds].filter(id => list.some(t => t.id === id)).length;
    return (
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-slate-500">{list.length} tarea{list.length !== 1 ? "s" : ""}</span>
        <div className="flex items-center gap-2">
          {selectionMode && count > 0 && (
            <Button size="sm" variant="outline"
              onClick={() => bulkUpdate(isArchived
                ? { estado: "pendiente" }
                : { estado: "archivado" }
              )}
              className={`h-7 text-xs px-2 ${isArchived
                ? "text-blue-700 border-blue-300 hover:bg-blue-50"
                : "text-slate-700 border-slate-300 hover:bg-slate-50"}`}>
              {isArchived
                ? <><RotateCcw className="w-3 h-3 mr-1" />Recuperar {count}</>
                : <><Archive className="w-3 h-3 mr-1" />Archivar {count}</>}
            </Button>
          )}
          <Button size="sm" variant={selectionMode ? "default" : "outline"}
            onClick={() => { setSelectionMode(s => !s); setSelectedIds(new Set()); }}
            className="h-7 text-xs px-2">
            {selectionMode
              ? <><X className="w-3 h-3 mr-1" />Cancelar</>
              : <><CheckSquare className="w-3 h-3 mr-1" />Seleccionar</>}
          </Button>
        </div>
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <>
      <Card className="border-none shadow-lg">
        <CardHeader className="border-b border-slate-100 pb-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-slate-600" />
              Panel de Tareas
            </CardTitle>
            <Button size="sm" onClick={() => setShowDialog(true)}
              className="bg-slate-900 hover:bg-slate-700 text-white h-8 px-3 text-xs">
              <Plus className="w-3.5 h-3.5 mr-1" /> Nueva tarea
            </Button>
          </div>
        </CardHeader>

        <CardContent className="pt-4 pb-2">
          {/* ── Warning banner ── */}
          {vencidas.length > 0 && (
            <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3">
              <div className="flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-red-600 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-red-800 mb-1">
                    {vencidas.length} tarea{vencidas.length !== 1 ? "s" : ""} vencida{vencidas.length !== 1 ? "s" : ""}
                  </p>
                  <ul className="space-y-0.5">
                    {vencidas.map(t => (
                      <li key={t.id} className="text-xs text-red-700 flex items-center gap-1.5">
                        <span className="w-1 h-1 rounded-full bg-red-400 shrink-0" />
                        <span className="font-medium">{t.titulo}</span>
                        <span className="text-red-500">— venció el {formatDate(t.fecha_vencimiento)}</span>
                        <span className="text-red-400">({t.asignado_a})</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* ── Tabs ── */}
          <Tabs value={activeTab} onValueChange={(v) => { setActiveTab(v); clearSelection(); }}>
            <TabsList className="mb-4 bg-slate-100">
              <TabsTrigger value="pendientes" className="text-xs">
                Pendientes
                {activas.length > 0 && (
                  <span className="ml-1.5 bg-slate-700 text-white text-[10px] rounded-full px-1.5 py-0.5 leading-none">
                    {activas.length}
                  </span>
                )}
              </TabsTrigger>
              <TabsTrigger value="archivadas" className="text-xs">
                Archivadas
                {archivadas.length > 0 && (
                  <span className="ml-1.5 bg-slate-400 text-white text-[10px] rounded-full px-1.5 py-0.5 leading-none">
                    {archivadas.length}
                  </span>
                )}
              </TabsTrigger>
            </TabsList>

            {/* Pendientes */}
            <TabsContent value="pendientes" className="mt-0">
              {isLoading ? (
                <div className="py-10 text-center text-slate-400 text-sm">Cargando tareas...</div>
              ) : activas.length === 0 ? (
                <div className="py-10 text-center text-slate-400">
                  <CheckCircle2 className="w-10 h-10 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No hay tareas pendientes</p>
                </div>
              ) : (
                <>
                  <TabToolbar list={activas} isArchived={false} />
                  <div className="space-y-3">
                    {activas.map(t => <TaskCard key={t.id} tarea={t} isArchived={false} />)}
                  </div>
                </>
              )}
            </TabsContent>

            {/* Archivadas */}
            <TabsContent value="archivadas" className="mt-0">
              {archivadas.length === 0 ? (
                <div className="py-10 text-center text-slate-400">
                  <Archive className="w-10 h-10 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No hay tareas archivadas</p>
                </div>
              ) : (
                <>
                  <TabToolbar list={archivadas} isArchived={true} />
                  <div className="space-y-3">
                    {archivadas.map(t => <TaskCard key={t.id} tarea={t} isArchived={true} />)}
                  </div>
                </>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* ── Add task dialog ── */}
      <Dialog open={showDialog} onOpenChange={(o) => { if (!o) { setShowDialog(false); setForm(emptyForm()); } }}>
        <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-base font-bold">Nueva Tarea</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Título */}
            <div className="space-y-1.5">
              <Label htmlFor="titulo" className="text-xs font-semibold text-slate-700">Título *</Label>
              <Input id="titulo" placeholder="¿Qué hay que hacer?" value={form.titulo}
                onChange={e => setForm(f => ({ ...f, titulo: e.target.value }))}
                className="text-sm" />
            </div>

            {/* Descripción */}
            <div className="space-y-1.5">
              <Label htmlFor="descripcion" className="text-xs font-semibold text-slate-700">Descripción</Label>
              <Textarea id="descripcion" placeholder="Detalla los requisitos..." value={form.descripcion}
                onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))}
                rows={3} className="text-sm resize-none" />
            </div>

            {/* Asignado + Creado por */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold text-slate-700">Asignado a</Label>
                <Select value={form.asignado_a} onValueChange={v => setForm(f => ({ ...f, asignado_a: v }))}>
                  <SelectTrigger className="text-sm h-9"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {USERS.map(u => <SelectItem key={u} value={u} className="text-sm">{u}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold text-slate-700">Creado por</Label>
                <Select value={form.creado_por} onValueChange={v => setForm(f => ({ ...f, creado_por: v }))}>
                  <SelectTrigger className="text-sm h-9"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {["Santiago", "Alejandro"].map(u => <SelectItem key={u} value={u} className="text-sm">{u}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Fecha vencimiento */}
            <div className="space-y-1.5">
              <Label htmlFor="fecha" className="text-xs font-semibold text-slate-700">Fecha de entrega *</Label>
              <Input id="fecha" type="date" value={form.fecha_vencimiento}
                onChange={e => setForm(f => ({ ...f, fecha_vencimiento: e.target.value }))}
                className="text-sm" />
            </div>

            {/* Entregable */}
            <div className="space-y-2">
              <Label className="text-xs font-semibold text-slate-700">Entregable</Label>
              <Select value={form.entregable_tipo} onValueChange={v => setForm(f => ({ ...f, entregable_tipo: v, entregable_url: "", entregable_texto: "" }))}>
                <SelectTrigger className="text-sm h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="texto"   className="text-sm">Texto</SelectItem>
                  <SelectItem value="archivo" className="text-sm">Archivo</SelectItem>
                  <SelectItem value="foto"    className="text-sm">Foto</SelectItem>
                </SelectContent>
              </Select>

              {form.entregable_tipo === "texto" && (
                <Textarea placeholder="Describe el entregable esperado..." value={form.entregable_texto}
                  onChange={e => setForm(f => ({ ...f, entregable_texto: e.target.value }))}
                  rows={2} className="text-sm resize-none" />
              )}

              {(form.entregable_tipo === "archivo" || form.entregable_tipo === "foto") && (
                <div>
                  <input type="file" ref={fileRef} className="hidden"
                    accept={form.entregable_tipo === "foto" ? "image/*" : "*/*"}
                    onChange={handleFileChange} />
                  {form.entregable_url ? (
                    <div className="flex items-center gap-2 text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg p-2">
                      <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                      <span className="truncate flex-1">Archivo adjunto</span>
                      <button onClick={() => setForm(f => ({ ...f, entregable_url: "" }))}
                        className="text-slate-400 hover:text-red-500">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ) : (
                    <Button type="button" variant="outline" size="sm"
                      onClick={() => fileRef.current?.click()}
                      disabled={uploading}
                      className="w-full text-xs h-9 border-dashed">
                      {uploading
                        ? "Subiendo..."
                        : <><Upload className="w-3.5 h-3.5 mr-1.5" />
                          {form.entregable_tipo === "foto" ? "Seleccionar foto" : "Seleccionar archivo"}</>}
                    </Button>
                  )}
                </div>
              )}
            </div>
          </div>

          <DialogFooter className="gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => { setShowDialog(false); setForm(emptyForm()); }}>
              Cancelar
            </Button>
            <Button size="sm" onClick={handleSave}
              disabled={!form.titulo.trim() || !form.fecha_vencimiento || saving}
              className="bg-slate-900 hover:bg-slate-700 text-white">
              {saving ? "Guardando..." : "Crear tarea"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
