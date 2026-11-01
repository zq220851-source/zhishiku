import type { CapacitorConfig } from '@capacitor/cli';
// Edit appId before public distribution. HTTPS API URL is a Vite build variable,
// not a Capacitor server.url: packaged assets remain local to the App.
const config: CapacitorConfig = {
  appId: 'cn.medrep.coach',
  appName: 'MedRep Coach',
  webDir: 'dist'
};
export default config;
