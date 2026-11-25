// Lineas.jsx — una fila por parte, editable como una planilla.
// Reemplaza DESPACHO, PROVINCIAS y FACTURAS POR COBRAR (migración 010).
// Teclado: flechas, Shift+flechas (selección), Enter/F2 editar, Tab, Esc,
// Supr (borrar), Ctrl+Enter (aplicar a toda la selección), Ctrl+C / Ctrl+V
// (pegar desde Excel; lo que pasa del final crea filas nuevas).
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { supabase } from "@/api/base44Client";

const ESTADOS = ["adjudicado", "comprado", "transito", "en_bodega", "despachado",
  "en_aduana", "en_quito", "enviado_cliente", "entregado", "cancelado"];

// src: "item" = OrderItem, "order" = Order (cabecera), "ro" = calculado
const COLS = [
  { k: "cliente", l: "Cliente", w: 110, src: "order" },
  { k: "placa", l: "Placa", w: 80, src: "order" },
  { k: "siniestro", l: "Siniestro", w: 90, src: "order" },
  { k: "vehiculo", l: "Vehículo", w: 130, src: "order" },
  { k: "producto_nombre", l: "Pieza", w: 200, src: "item" },
  { k: "numero_parte", l: "N.º parte", w: 120, src: "item" },
  { k: "calidad", l: "Calidad", w: 70, src: "item" },
  { k: "cantidad", l: "Cant", w: 45, src: "item", t: "num" },
  { k: "estado", l: "Estado", w: 105, src: "item", t: "estado" },
  { k: "vence", l: "Vence", w: 85, src: "ro", t: "date" },
  { k: "proveedor", l: "Proveedor", w: 90, src: "item" },
  { k: "precio_compra", l: "Compra", w: 70, src: "item", t: "num" },
  { k: "tracking_number", l: "Tracking", w: 150, src: "item" },
  { k: "wr_bodega", l: "WR", w: 95, src: "item" },
  { k: "valor_declarado", l: "Valor", w: 65, src: "item", t: "num" },
  { k: "peso_kg", l: "Peso", w: 55, src: "item", t: "num" },
  { k: "subpartida", l: "Subpartida", w: 105, src: "item" },
  { k: "arancel_pct", l: "Aranc.", w: 55, src: "item", t: "num" },
  { k: "despacho", l: "Despacho", w: 85, src: "item" },
  { k: "destino", l: "Destino", w: 130, src: "item" },
  { k: "instruccion", l: "Instrucción", w: 180, src: "item" },
  { k: "problema", l: "Problema", w: 150, src: "item" },
  { k: "precio_venta", l: "Venta", w: 70, src: "item", t: "num" },
  { k: "costo_usd", l: "Costo", w: 65, src: "ro", t: "num" },
  { k: "margen_usd", l: "Margen", w: 65, src: "ro", t: "num" },
  { k: "factura_numero", l: "Factura", w: 75, src: "item" },
  { k: "fecha_factura", l: "F. factura", w: 90, src: "item", t: "date" },
  { k: "fecha_cobro", l: "Cobrado", w: 90, src: "item", t: "date" },
  { k: "fecha_entrega_orden", l: "Límite", w: 90, src: "item", t: "date" },
  { k: "notas", l: "Notas", w: 160, src: "item" },
];

const abierta = (r) => !["entregado", "cancelado"].includes(r.estado) || !r.factura_numero || !r.fecha_cobro;
const VISTAS = [
  { id: "abiertas", l: "Abiertas", f: abierta, cols: null },
  { id: "alertas", l: "Alertas", f: (r) => r.problema || r.atrasado || (r.estado === "en_quito" && !r.destino),
    cols: ["cliente", "placa", "producto_nombre", "estado", "vence", "tracking_number", "destino", "problema", "notas"] },
  { id: "despachar", l: "Por despachar", f: (r) => r.estado === "en_bodega" && !r.despacho,
    cols: ["wr_bodega", "tracking_number", "producto_nombre", "valor_declarado", "peso_kg", "subpartida", "arancel_pct", "despacho", "cliente"] },
  { id: "llegadas", l: "Llegadas (Santiago)", f: (r) => ["despachado", "en_aduana", "en_quito"].includes(r.estado),
    cols: ["wr_bodega", "tracking_number", "producto_nombre", "cliente", "placa", "estado", "destino", "instruccion", "problema"] },
  { id: "facturar", l: "Por facturar", f: (r) => ["enviado_cliente", "entregado"].includes(r.estado) && !r.factura_numero,
    cols: ["cliente", "placa", "siniestro", "producto_nombre", "cantidad", "precio_venta", "costo_usd", "margen_usd", "factura_numero", "fecha_factura"] },
  { id: "cobrar", l: "Por cobrar", f: (r) => r.factura_numero && !r.fecha_cobro,
    cols: ["cliente", "factura_numero", "fecha_factura", "producto_nombre", "precio_venta", "fecha_cobro", "notas"] },
  { id: "todas", l: "Todas", f: () => true, cols: null },
];

function coerce(t, v) {
  if (v === undefined || v === null) return null;
  const s = String(v).trim();
  if (s === "") return null;
  if (t === "num") {
    let t2 = s.replace(/[$€\s]/g, "");
    t2 = /,\d{1,2}$/.test(t2) ? t2.replace(/\./g, "").replace(",", ".")   // 1.234,50 / 0,15
                              : t2.replace(/,/g, "");                      // 1,234.50
    const n = Number(t2);
    return Number.isFinite(n) ? n : null;
  }
  if (t === "date") {
    let m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (m) return `${m[1]}-${m[2].padStart(2, "0")}-${m[3].padStart(2, "0")}`;
    m = s.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$/);            // dd/mm/aaaa
    if (m) { const y = m[3].length === 2 ? "20" + m[3] : m[3];
      return `${y}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}`; }
    if (/^hoy$/i.test(s)) return new Date().toISOString().slice(0, 10);
    return null;
  }
  if (t === "estado") {
    const k = s.toLowerCase().replace(/\s+/g, "_");
    return ESTADOS.find((e) => e === k || e.startsWith(k)) || null;
  }
  return s;
}

const show = (t, v) => (v === null || v === undefined ? "" :
  t === "num" ? (Math.round(Number(v) * 100) / 100).toString() : String(v));

export default function Lineas() {
  const [rows, setRows] = useState([]);
  const [vista, setVista] = useState("abiertas");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState({ r: 0, c: 0, r2: 0, c2: 0 });
  const [edit, setEdit] = useState(null);            // {value, r, c}
  const editRef = useRef(null);                      // evita guardar dos veces (Enter + blur)
  const empezar = (value, r = sel.r, c = sel.c) => { editRef.current = { r, c }; setEdit({ value, r, c }); };
  const cancelar = () => { editRef.current = null; setEdit(null); box.current?.focus(); };
  const [msg, setMsg] = useState("");
  const box = useRef(null);

  const cargar = useCallback(async () => {
    const { data, error } = await supabase.from("v_linea").select("*")
      .eq("archivado", false).order("created_date", { ascending: true }).limit(5000);
    if (error) { setMsg("Error al cargar: " + error.message); return; }
    setRows(data || []);
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const v = VISTAS.find((x) => x.id === vista);
  const cols = useMemo(() => (v.cols ? v.cols.map((k) => COLS.find((c) => c.k === k)) : COLS), [v]);
  const vis = useMemo(() => {
    const qq = q.trim().toLowerCase();
    return rows.filter(v.f).filter((r) => !qq || cols.some((c) => String(r[c.k] ?? "").toLowerCase().includes(qq)));
  }, [rows, v, q, cols]);

  const rect = { r1: Math.min(sel.r, sel.r2), r2: Math.max(sel.r, sel.r2),
                 c1: Math.min(sel.c, sel.c2), c2: Math.max(sel.c, sel.c2) };
  const enSel = (r, c) => r >= rect.r1 && r <= rect.r2 && c >= rect.c1 && c <= rect.c2;

  // ── escritura ──────────────────────────────────────────────
  async function pedidoPara(row, cambiosOrder) {
    if (row.pedido_id) return row.pedido_id;
    const cliente = cambiosOrder.cliente || row.cliente || "SIN CLIENTE";
    const placa = cambiosOrder.placa || row.placa || "";
    let qy = supabase.from("Order").select("id").eq("cliente", cliente)
      .or("archivado.is.null,archivado.eq.false");
    qy = placa ? qy.eq("placa", placa) : qy.is("placa", null);
    const { data: ya } = await qy.limit(1);
    if (ya && ya.length) return ya[0].id;
    const { data, error } = await supabase.from("Order").insert({
      numero_pedido: `${cliente} ${placa}`.trim(), cliente, placa: placa || null,
      fecha_pedido: new Date().toISOString().slice(0, 10), archivado: false }).select("id").single();
    if (error) throw error;
    return data.id;
  }

  async function guardar(cambios) {          // [{row, key, value}] row=null => fila nueva
    const porFila = new Map();
    for (const ch of cambios) {
      const col = COLS.find((c) => c.k === ch.key);
      if (!col || col.src === "ro") continue;
      const id = ch.row ? ch.row.id : `nueva-${ch.nueva}`;
      if (!porFila.has(id)) porFila.set(id, { row: ch.row, item: {}, order: {} });
      porFila.get(id)[col.src][ch.key] = coerce(col.t, ch.value);
    }
    setRows((prev) => prev.map((r) => {
      const p = porFila.get(r.id); return p ? { ...r, ...p.item, ...p.order } : r; }));
    let n = 0;
    try {
      for (const [, p] of porFila) {
        const row = p.row || { cantidad: 1 };
        if (!p.row) {
          const pid = (Object.keys(p.order).length) ? await pedidoPara(row, p.order) : null;
          const { error } = await supabase.from("OrderItem").insert({
            producto_nombre: p.item.producto_nombre || "(sin nombre)", estado: "adjudicado",
            cantidad: 1, ...p.item, pedido_id: pid });
          if (error) throw error;
        } else {
          if (Object.keys(p.item).length) {
            const { error } = await supabase.from("OrderItem")
              .update({ ...p.item, updated_date: new Date().toISOString() }).eq("id", row.id);
            if (error) throw error;
          }
          if (Object.keys(p.order).length) {
            if (row.pedido_id) {
              const { error } = await supabase.from("Order").update(p.order).eq("id", row.pedido_id);
              if (error) throw error;
            } else {
              const pid = await pedidoPara(row, p.order);
              await supabase.from("Order").update(p.order).eq("id", pid);
              await supabase.from("OrderItem").update({ pedido_id: pid }).eq("id", row.id);
            }
          }
        }
        n++;
      }
      setMsg(`${n} fila(s) guardadas`);
    } catch (e) { setMsg("Error al guardar: " + (e.message || e)); }
    cargar();
  }

  // ── teclado y portapapeles ─────────────────────────────────
  const mover = (dr, dc, extender) => setSel((s) => {
    const r = Math.max(0, Math.min(vis.length, (extender ? s.r2 : s.r) + dr));
    const c = Math.max(0, Math.min(cols.length - 1, (extender ? s.c2 : s.c) + dc));
    return extender ? { ...s, r2: r, c2: c } : { r, c, r2: r, c2: c };
  });

  function commit(valor, aTodo, dr = 1, dc = 0) {
    const pos = editRef.current;
    if (!pos) return;                                  // ya guardado
    editRef.current = null;
    const cambios = [];
    if (aTodo) {
      for (let r = rect.r1; r <= rect.r2; r++) for (let c = rect.c1; c <= rect.c2; c++)
        if (vis[r]) cambios.push({ row: vis[r], key: cols[c].k, value: valor });
    } else if (vis[pos.r]) cambios.push({ row: vis[pos.r], key: cols[pos.c].k, value: valor });
    else if (String(valor ?? "").trim()) cambios.push({ row: null, nueva: pos.r, key: cols[pos.c].k, value: valor });
    setEdit(null);
    if (cambios.length) guardar(cambios);
    if (dr || dc) mover(dr, dc, false);
    box.current?.focus();
  }

  function onKey(e) {
    if (edit) return;                                  // el input maneja sus teclas
    const k = e.key;
    if (k.startsWith("Arrow")) {
      e.preventDefault();
      mover(k === "ArrowDown" ? 1 : k === "ArrowUp" ? -1 : 0,
            k === "ArrowRight" ? 1 : k === "ArrowLeft" ? -1 : 0, e.shiftKey);
    } else if (k === "Tab") { e.preventDefault(); mover(0, e.shiftKey ? -1 : 1, false); }
    else if (k === "Enter" || k === "F2") {
      e.preventDefault();
      if (cols[sel.c]?.src !== "ro") empezar(show(cols[sel.c].t, vis[sel.r]?.[cols[sel.c].k]));
    } else if (k === "Delete" || k === "Backspace") {
      e.preventDefault();
      const cambios = [];
      for (let r = rect.r1; r <= rect.r2; r++) for (let c = rect.c1; c <= rect.c2; c++)
        if (vis[r]) cambios.push({ row: vis[r], key: cols[c].k, value: null });
      if (cambios.length) guardar(cambios);
    } else if (k.length === 1 && !e.ctrlKey && !e.metaKey && cols[sel.c]?.src !== "ro") {
      empezar(k); e.preventDefault();
    }
  }

  function onCopy(e) {
    const txt = [];
    for (let r = rect.r1; r <= rect.r2; r++) {
      const fila = [];
      for (let c = rect.c1; c <= rect.c2; c++) fila.push(show(cols[c].t, vis[r]?.[cols[c].k]));
      txt.push(fila.join("\t"));
    }
    e.clipboardData.setData("text/plain", txt.join("\n")); e.preventDefault();
  }

  function onPaste(e) {
    if (edit) return;
    e.preventDefault();
    const filas = e.clipboardData.getData("text/plain").replace(/\r/g, "").replace(/\n$/, "")
      .split("\n").map((l) => l.split("\t"));
    const cambios = [];
    filas.forEach((f, i) => f.forEach((val, j) => {
      const c = sel.c + j; if (c >= cols.length) return;
      const r = sel.r + i;
      if (r < vis.length) cambios.push({ row: vis[r], key: cols[c].k, value: val });
      else cambios.push({ row: null, nueva: r, key: cols[c].k, value: val });
    }));
    guardar(cambios);
  }

  function copiarVista() {
    const txt = [cols.map((c) => c.l).join("\t"),
      ...vis.map((r) => cols.map((c) => show(c.t, r[c.k])).join("\t"))].join("\n");
    navigator.clipboard.writeText(txt).then(() => setMsg(`${vis.length} filas copiadas (pegar en Excel)`));
  }

  // suma de la selección, como la barra de estado de Excel
  let suma = 0, nums = 0;
  for (let r = rect.r1; r <= rect.r2; r++) for (let c = rect.c1; c <= rect.c2; c++) {
    const x = vis[r]?.[cols[c]?.k]; if (typeof x === "number") { suma += x; nums++; } }

  return (
    <div className="p-3 flex flex-col gap-2 h-[calc(100vh-24px)]">
      <div className="flex flex-wrap items-center gap-1">
        {VISTAS.map((x) => (
          <button key={x.id} onClick={() => { setVista(x.id); setSel({ r: 0, c: 0, r2: 0, c2: 0 }); }}
            className={`px-3 py-1 rounded text-sm border ${vista === x.id ? "bg-slate-800 text-white" : "bg-white"}`}>
            {x.l} <span className="opacity-60">{rows.filter(x.f).length}</span>
          </button>))}
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar…"
          className="ml-2 px-2 py-1 border rounded text-sm w-48" />
        <button onClick={copiarVista} className="px-3 py-1 rounded text-sm border bg-white">Copiar vista</button>
        <button onClick={() => { setSel({ r: vis.length, c: 0, r2: vis.length, c2: 0 }); box.current?.focus(); }}
          className="px-3 py-1 rounded text-sm border bg-white">+ Pegar filas nuevas</button>
        <span className="text-xs text-slate-500 ml-auto">
          {nums > 1 ? `Suma ${Math.round(suma * 100) / 100} · ` : ""}{msg}
        </span>
      </div>

      <div ref={box} tabIndex={0} onKeyDown={onKey} onCopy={onCopy} onPaste={onPaste}
        className="flex-1 overflow-auto border rounded bg-white outline-none text-[12px]">
        <table className="border-collapse table-fixed">
          <thead className="sticky top-0 z-10 bg-slate-100">
            <tr>
              <th className="w-8 border px-1 text-slate-400">#</th>
              {cols.map((c) => <th key={c.k} style={{ width: c.w, minWidth: c.w }}
                className="border px-1 text-left font-medium">{c.l}</th>)}
            </tr>
          </thead>
          <tbody>
            {[...vis, null].map((row, r) => (
              <tr key={row ? row.id : "nueva"}
                className={!row ? "" : row.problema ? "bg-orange-50" : row.atrasado ? "bg-red-50" : ""}>
                <td className="border px-1 text-slate-400 text-right">{row ? r + 1 : "+"}</td>
                {cols.map((c, ci) => {
                  const activo = sel.r === r && sel.c === ci;
                  const editando = edit && edit.r === r && edit.c === ci;
                  return (
                    <td key={c.k}
                      onMouseDown={(e) => { if (editando) return;
                        setSel((s) => e.shiftKey ? { ...s, r2: r, c2: ci } : { r, c: ci, r2: r, c2: ci }); }}
                      onDoubleClick={() => c.src !== "ro" && empezar(show(c.t, row?.[c.k]), r, ci)}
                      className={`border px-1 truncate ${c.t === "num" ? "text-right" : ""}
                        ${c.src === "ro" ? "text-slate-500" : ""}
                        ${enSel(r, ci) ? "bg-blue-100" : ""} ${activo ? "outline outline-2 outline-blue-600" : ""}`}>
                      {editando ? (
                        c.t === "estado" ? (
                          <select autoFocus value={coerce("estado", edit.value) || ""} className="w-full"
                            onChange={(e) => commit(e.target.value, true)}
                            onBlur={() => cancelar()}
                            onKeyDown={(e) => e.key === "Escape" && cancelar()}>
                            <option value="" />
                            {ESTADOS.map((x) => <option key={x} value={x}>{x}</option>)}
                          </select>
                        ) : (
                          <input autoFocus value={edit.value} className="w-full outline-none"
                            onChange={(e) => { const value = e.target.value; setEdit((x) => ({ ...x, value })); }}
                            onBlur={() => commit(edit.value, false, 0, 0)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") { e.preventDefault(); commit(edit.value, e.ctrlKey || e.metaKey); }
                              else if (e.key === "Tab") { e.preventDefault(); commit(edit.value, false, 0, e.shiftKey ? -1 : 1); }
                              else if (e.key === "Escape") cancelar();
                            }} />)
                      ) : row ? show(c.t, row[c.k]) : ""}
                    </td>);
                })}
              </tr>))}
          </tbody>
        </table>
      </div>
      <div className="text-[11px] text-slate-500">
        Enter editar · Ctrl+Enter aplica a toda la selección · Shift+flechas selecciona · Ctrl+V pega desde Excel
        (debajo de la última fila crea filas nuevas) · fechas dd/mm/aaaa o "hoy" · naranja = problema · rojo = atrasado
      </div>
    </div>
  );
}
