import { useCallback, useEffect, useState } from 'react';

const TOKEN_KEY = 'aivideogpt_token';
const USER_KEY = 'aivideogpt_user';

export type AuthUser = {
  email: string;
  username?: string;
  verified?: boolean;
};

export function getStoredToken(): string | null {
  try {
    return typeof window === 'undefined' ? null : localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getStoredUser(): AuthUser | null {
  try {
    if (typeof window === 'undefined') return null;
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function setStoredAuth(token: string, user: AuthUser) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    window.dispatchEvent(new Event('aivideogpt:auth'));
  } catch {
    /* ignore */
  }
}

export function clearStoredAuth() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    window.dispatchEvent(new Event('aivideogpt:auth'));
  } catch {
    /* ignore */
  }
}

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(() => getStoredUser());
  const [token, setToken] = useState<string | null>(() => getStoredToken());

  useEffect(() => {
    const sync = () => {
      setUser(getStoredUser());
      setToken(getStoredToken());
    };
    window.addEventListener('storage', sync);
    window.addEventListener('aivideogpt:auth', sync);
    return () => {
      window.removeEventListener('storage', sync);
      window.removeEventListener('aivideogpt:auth', sync);
    };
  }, []);

  const login = useCallback((nextToken: string, nextUser: AuthUser) => {
    setStoredAuth(nextToken, nextUser);
    setToken(nextToken);
    setUser(nextUser);
  }, []);

  const logout = useCallback(() => {
    clearStoredAuth();
    setToken(null);
    setUser(null);
  }, []);

  return {
    user,
    token,
    isAuthenticated: Boolean(token),
    login,
    logout,
  };
}
