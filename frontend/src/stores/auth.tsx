import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { authApi, authEvents, ApiError } from "@/api";
import {
  fromTokenResponse,
  getSession,
  setSession,
  subscribe,
  type Session,
} from "@/api/tokenStore";
import type { User } from "@/api/types";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthCtx {
  status: AuthStatus;
  user: User | null;
  error: string | null;
  isAdmin: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>(() => (getSession() ? "loading" : "anonymous"));
  const [user, setUser] = useState<User | null>(() => getSession()?.user ?? null);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  // Validate a persisted session on boot.
  useEffect(() => {
    if (!getSession()) return;
    let cancelled = false;
    authApi
      .me()
      .then((me) => {
        if (cancelled) return;
        const s = getSession();
        if (s) setSession({ ...s, user: me });
        setUser(me);
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) return;
        setSession(null);
        setUser(null);
        setStatus("anonymous");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // React to session drops from the API layer (failed refresh) and other tabs.
  useEffect(() => {
    const onExpired = () => {
      if (!mounted.current) return;
      setUser(null);
      setStatus("anonymous");
      setError("Your session has expired. Please sign in again.");
    };
    authEvents.addEventListener("expired", onExpired);
    const unsub = subscribe((s: Session | null) => {
      if (!mounted.current) return;
      if (!s) {
        setUser(null);
        setStatus("anonymous");
      } else {
        setUser(s.user);
        setStatus("authenticated");
      }
    });
    return () => {
      authEvents.removeEventListener("expired", onExpired);
      unsub();
    };
  }, []);

  const login = useCallback(async (identifier: string, password: string) => {
    setError(null);
    try {
      const res = await authApi.login(identifier, password);
      setSession(fromTokenResponse(res));
      setUser(res.user);
      setStatus("authenticated");
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.status === 401
            ? "Incorrect email/username or password."
            : err.message
          : "Unable to sign in right now.";
      setError(message);
      throw err;
    }
  }, []);

  const register = useCallback(
    async (email: string, username: string, password: string) => {
      setError(null);
      try {
        const res = await authApi.register(email, username, password);
        setSession(fromTokenResponse(res));
        setUser(res.user);
        setStatus("authenticated");
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.status === 409
              ? "That email or username is already registered."
              : err.message
            : "Unable to create the account right now.";
        setError(message);
        throw err;
      }
    },
    [],
  );

  const logout = useCallback(async () => {
    const s = getSession();
    if (s?.refresh_token) {
      try {
        await authApi.logout(s.refresh_token);
      } catch {
        /* best effort */
      }
    }
    setSession(null);
    setUser(null);
    setStatus("anonymous");
    setError(null);
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const value = useMemo<AuthCtx>(
    () => ({
      status,
      user,
      error,
      isAdmin: user?.role === "admin",
      login,
      register,
      logout,
      clearError,
    }),
    [status, user, error, login, register, logout, clearError],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
