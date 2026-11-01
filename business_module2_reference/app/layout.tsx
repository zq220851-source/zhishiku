import type { ReactNode } from 'react';
import './style.css';
import {VisualShell} from './components/VisualShell';
export const metadata = { title: '复盘与成长' };
export default function Layout({ children }: { children: ReactNode }) { return <html lang="zh-CN"><head><link rel="stylesheet" href="http://127.0.0.1:8892/visual/glass.css" /></head><body className="coach-ui module-2">{children}<VisualShell /></body></html>; }
