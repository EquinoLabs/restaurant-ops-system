import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { UserMe, OutletMembership } from '../../types/auth';
import { loginStaff, fetchCurrentUser } from '../../api/client';

interface AuthContextType {
  token: string | null;
  user: UserMe | null;
  loading: boolean;
  selectedOutlet: OutletMembership | null;
  setSelectedOutletId: (outletId: string) => void;
  login: (email: string, pass: string) => Promise<UserMe>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = 'roms_auth_token';

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<UserMe | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedOutletId, setSelectedOutletIdState] = useState<string | null>(null);

  useEffect(() => {
    async function loadUser() {
      if (!token) {
        setUser(null);
        setLoading(false);
        return;
      }
      try {
        const userProfile = await fetchCurrentUser(token);
        setUser(userProfile);
        if (userProfile.memberships.length > 0 && !selectedOutletId) {
          setSelectedOutletIdState(userProfile.memberships[0].outlet_id);
        }
      } catch (err) {
        console.error('Failed to validate auth token:', err);
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    }
    loadUser();
  }, [token]);

  const login = async (email: string, pass: string): Promise<UserMe> => {
    setLoading(true);
    try {
      const res = await loginStaff(email, pass);
      localStorage.setItem(TOKEN_KEY, res.access_token);
      setToken(res.access_token);
      const userProfile = await fetchCurrentUser(res.access_token);
      setUser(userProfile);
      if (userProfile.memberships.length > 0) {
        setSelectedOutletIdState(userProfile.memberships[0].outlet_id);
      }
      return userProfile;
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    setSelectedOutletIdState(null);
  };

  const setSelectedOutletId = (outletId: string) => {
    setSelectedOutletIdState(outletId);
  };

  const selectedOutlet =
    user?.memberships.find((m) => m.outlet_id === selectedOutletId) ||
    user?.memberships[0] ||
    null;

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        loading,
        selectedOutlet,
        setSelectedOutletId,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
