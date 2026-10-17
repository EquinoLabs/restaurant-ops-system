import React from 'react';
import ReactDOM from 'react-dom/client';
import { PlatformAdminApp } from './App';
import { AppErrorBoundary } from './components/errors/AppErrorBoundary';
import '@roms/ui/index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppErrorBoundary>
      <PlatformAdminApp />
    </AppErrorBoundary>
  </React.StrictMode>
);
