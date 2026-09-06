"use client";

import { createContext, useContext, useEffect, useState } from "react";
import type { Scope } from "./types";

type ScopeContextValue = { scope: Scope; setScope: (value: Scope) => void };
const ScopeContext = createContext<ScopeContextValue | null>(null);
const DEFAULT_SCOPE: Scope = { role: "MOSPI" };
const STORAGE_KEY = "tracex-kavach-scope";

function readStoredScope(): Scope {
  const saved = window.localStorage.getItem(STORAGE_KEY);
  if (!saved) return DEFAULT_SCOPE;
  try {
    const parsed = JSON.parse(saved) as Scope;
    return ["MOSPI", "STATE", "DISTRICT", "IA", "MP"].includes(parsed.role) ? parsed : DEFAULT_SCOPE;
  } catch { return DEFAULT_SCOPE; }
}

export function ScopeProvider({ children }: { children: React.ReactNode }) {
  const [scope, setScopeState] = useState<Scope>(DEFAULT_SCOPE);
  useEffect(() => {
    const restore = window.setTimeout(() => setScopeState(readStoredScope()), 0);
    const syncFromOtherTab = () => setScopeState(readStoredScope());
    window.addEventListener("storage", syncFromOtherTab);
    return () => {
      window.clearTimeout(restore);
      window.removeEventListener("storage", syncFromOtherTab);
    };
  }, []);
  const setScope = (value: Scope) => {
    setScopeState(value); window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  };
  return <ScopeContext.Provider value={{ scope, setScope }}>{children}</ScopeContext.Provider>;
}

export function useScope() {
  const value = useContext(ScopeContext);
  if (!value) throw new Error("ScopeProvider is missing");
  return value;
}
