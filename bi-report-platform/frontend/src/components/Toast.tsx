import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

export interface ToastAction {
  label: string;
  onClick: () => void;
}

const ToastContext = createContext<(msg: string, action?: ToastAction) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<{ msg: string; action?: ToastAction } | null>(null);
  const timer = useRef<number>();
  const show = useCallback((msg: string, action?: ToastAction) => {
    window.clearTimeout(timer.current);
    setToast({ msg, action });
    timer.current = window.setTimeout(() => setToast(null), action ? 7000 : 2800); // time to press Undo
  }, []);
  return (
    <ToastContext.Provider value={show}>
      {children}
      {toast && (
        <div role="status" className="toast">
          {toast.msg}
          {toast.action && (
            <button type="button" className="toast-action" onClick={() => { toast.action!.onClick(); setToast(null); }}>
              {toast.action.label}
            </button>
          )}
        </div>
      )}
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
