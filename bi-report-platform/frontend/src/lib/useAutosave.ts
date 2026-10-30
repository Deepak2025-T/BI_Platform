import { useCallback, useEffect, useRef, useState } from "react";

export type SaveState = "saved" | "saving" | "error";

/**
 * Saves `value` `delay` ms after it last changed. Nothing is saved for the value it starts with (or
 * the first value once `enabled` turns on), so just opening an editor doesn't save. A change still
 * waiting when the editor closes is saved straight away, and the browser asks before the tab closes
 * with a change unsaved. `value` must keep its identity until it really changes (use useMemo).
 */
export function useAutosave<T>(value: T, save: (v: T) => Promise<unknown>, enabled = true, delay = 700): SaveState {
  const [state, setState] = useState<SaveState>("saved");
  const baseline = useRef<{ v: T } | null>(null);
  const pending = useRef<{ v: T } | null>(null);
  const saveRef = useRef(save);
  saveRef.current = save;

  const flush = useCallback(() => {
    const p = pending.current;
    if (!p) return;
    pending.current = null;
    saveRef.current(p.v)
      .then(() => setState(pending.current ? "saving" : "saved"))
      .catch(() => setState("error"));
  }, []);

  useEffect(() => {
    if (!enabled) return;
    if (!baseline.current) { baseline.current = { v: value }; return; }
    if (value === baseline.current.v && !pending.current) return; // e.g. React running the effect twice
    pending.current = { v: value };
    setState("saving");
    const t = window.setTimeout(flush, delay);
    return () => window.clearTimeout(t);
  }, [value, enabled, delay, flush]);

  // Leaving the page (another route) saves what's waiting; closing the tab asks first.
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (pending.current) { e.preventDefault(); e.returnValue = ""; }
    };
    window.addEventListener("beforeunload", warn);
    return () => { window.removeEventListener("beforeunload", warn); flush(); };
  }, [flush]);

  return state;
}
