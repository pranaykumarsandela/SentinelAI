import React, { createContext, useContext, useState, useEffect } from 'react';
import { AuthUser, UserRole } from '../types';

interface AuthContextType {
  user: AuthUser;
  login: (role: UserRole, name?: string, email?: string) => void;
  logout: () => void;
  switchRole: (role: UserRole) => void;
  hasPermission: (requiredRole: UserRole) => boolean;
}

const DEFAULT_USER: AuthUser = {
  id: 'usr_sec_admin_01',
  name: 'Security Admin',
  email: 'admin@sentinel.internal',
  role: 'admin',
};

const ROLE_HIERARCHY: Record<UserRole, number> = {
  viewer: 1,
  analyst: 2,
  supervisor: 3,
  admin: 4,
};

const AuthContext = createContext<AuthContextType>({
  user: DEFAULT_USER,
  login: () => {},
  logout: () => {},
  switchRole: () => {},
  hasPermission: () => true,
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser>(() => {
    try {
      const stored = localStorage.getItem('sentinel_auth_user');
      return stored ? JSON.parse(stored) : DEFAULT_USER;
    } catch {
      return DEFAULT_USER;
    }
  });

  useEffect(() => {
    localStorage.setItem('sentinel_auth_user', JSON.stringify(user));
  }, [user]);

  const login = (role: UserRole, name?: string, email?: string) => {
    const defaultNames: Record<UserRole, { name: string; email: string }> = {
      admin: { name: 'Security Admin', email: 'admin@sentinel.internal' },
      supervisor: { name: 'Operations Supervisor', email: 'supervisor@sentinel.internal' },
      analyst: { name: 'Threat Analyst', email: 'analyst@sentinel.internal' },
      viewer: { name: 'Audit Viewer', email: 'viewer@sentinel.internal' },
    };

    const info = defaultNames[role];
    setUser({
      id: `usr_${role}_${Date.now().toString(36)}`,
      name: name || info.name,
      email: email || info.email,
      role,
    });
  };

  const logout = () => {
    login('viewer');
  };

  const switchRole = (role: UserRole) => {
    login(role);
  };

  const hasPermission = (requiredRole: UserRole): boolean => {
    return (ROLE_HIERARCHY[user.role] ?? 0) >= (ROLE_HIERARCHY[requiredRole] ?? 0);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, switchRole, hasPermission }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
