import { createContext, useContext, useEffect, useState } from 'react';
import { identifyUser, resetPostHog } from '../analytics';

interface User {
  id: number;
  email: string;
  name: string;
  avatar_url: string | null;
  profile_id: string;  // always set from first login
  onboarded: boolean;  // true once profile_yaml is persisted (CV uploaded + profile saved)
  is_admin?: boolean;
  // Impersonation fields (present when an admin is viewing as another user)
  is_impersonating?: boolean;
  real_user_id?: number;
  real_user_name?: string;
}

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  stopImpersonating: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  logout: async () => {},
  refreshUser: async () => {},
  stopImpersonating: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchUser = () =>
    fetch('/api/auth/me')
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        setUser(data);
        if (data) identifyUser(data.id, data.email, data.name);
      });

  useEffect(() => {
    fetchUser().finally(() => setIsLoading(false));
  }, []);

  const logout = async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    setUser(null);
    resetPostHog();
  };

  const refreshUser = async () => {
    await fetchUser();
  };

  const stopImpersonating = async () => {
    await fetch('/api/admin/impersonate', { method: 'DELETE' });
    await fetchUser();
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, isAuthenticated: !!user, logout, refreshUser, stopImpersonating }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
