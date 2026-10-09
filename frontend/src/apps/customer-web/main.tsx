import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { PublicMenuView } from '../../features/public-menu/PublicMenuView';
import { NotFoundView } from '../../features/public-menu/NotFoundView';
import '../../index.css';

export const CustomerWebApp: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/m/:publicSlug" element={<PublicMenuView />} />
        <Route
          path="*"
          element={
            <NotFoundView message="The page or link you opened does not exist. Please scan a valid restaurant QR code." />
          }
        />
      </Routes>
    </BrowserRouter>
  );
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <CustomerWebApp />
  </React.StrictMode>
);
