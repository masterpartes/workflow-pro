import { supabase } from './base44Client';

const notImplemented = (name) => async (...args) => {
  throw new Error(`${name} integration not available in self-hosted version`);
};

export const UploadFile = async ({ file }) => {
  const fileName = `${Date.now()}-${file.name}`;
  const { data, error } = await supabase.storage
    .from('uploads')
    .upload(fileName, file, { upsert: true });
  if (error) throw error;
  const { data: { publicUrl } } = supabase.storage.from('uploads').getPubl