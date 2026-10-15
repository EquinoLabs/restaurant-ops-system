import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { PublicMenuView } from './features/public-menu/PublicMenuView';
import { NotFoundView } from '@roms/ui';

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

export default CustomerWebApp;
