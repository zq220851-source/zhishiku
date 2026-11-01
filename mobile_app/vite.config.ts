import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
const proxy = {'/v1/mobile':{target:'http://127.0.0.1:9011',ws:true}};
export default defineConfig({ plugins: [react()], server: {host:'127.0.0.1', port:5173,proxy}, preview:{proxy}, build:{outDir:'dist'} });
