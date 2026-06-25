// src/api/base44Client.js
import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// Generic entity helper — matches Base44 API shape
export function createEntity(tableName) {
  return {
    async list(orderBy = '-created_date', filters = {}) {
      let query = supabase.from(tableName).select('*');
      for (const [col, val] of Object.entries(filters)) {
        query = query.eq(col, val);
      }
      const ascending = !orderBy.startsWith('-');
      const col = orderBy.replace(/^-/, '');
      const { data, error } = await query.order(col, { ascending });
      if (error) throw error;
      return data;
    },
    async get(id) {
      const { data, error } = await supabase.from(tableName).select('*').eq('id', id).single();
      if (error) throw error;
      return data;
    },
    async create(record) {
      const { data, error } = await supabase.from(tableName).insert(record).select().single();
      if (error) throw error;
      return data;
    },
    async update(id, updates) {
      const { data, error } = await supabase
        .from(tableName)
        .update({ ...updates, updated_date: new Date().toISOString() })
        .eq('id', id)
        .select()
        .single();
      if (error) throw error;
      return data;
    },
    async delete(id) {
      const { error } = await supabase.from(tableName).delete().eq('id', id);
      if (error) throw error;
    },
    async bulkCreate(records) {
      const { data, error } = await supabase.from(tableName).insert(records).select();
      if (error) throw error;
      return data;
    },
  };
}

// File upload via Supabase Storage
const uploadFile = async ({ file }) => {
  const fileName = `${Date.now()}-${file.name}`;
  const { error } = await supabase.storage.from('uploads').upload(fileName, file, { upsert: true });
  if (error) throw error;
  const { data: { publicUrl } } = supabase.storage.from('uploads').getPublicUrl(fileName);
  return { file_url: publicUrl };
};

export const UploadedFile = { upload: uploadFile };

// Compat shim: base44.entities.X mirrors the createEntity API
import { Product, Order, OrderItem, Invoice } from './entities';
export const base44 = {
  entities: { Product, Order, OrderItem, Invoice },
  storage: { upload: uploadFile },
};
