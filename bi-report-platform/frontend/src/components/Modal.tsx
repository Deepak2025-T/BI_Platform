import { useEffect, useId, useRef, type FormEvent, type ReactNode } from "react";

interface Props {
  title: string;
  onClose: () => void;
  /** Runs when the form is submitted (Enter or the submit button in the footer). */
  onSubmit?: () => void;
  /** Buttons along the bottom. */
  footer?: ReactNode;
  error?: string;
  size?: "sm" | "lg";
  children: ReactNode;
}

/**
 * A modal dialog built on <dialog>, so focus is trapped and Esc closes it.
 * Give the field that should get focus first a data-autofocus attribute.
 */
export default function Modal({ title, onClose, onSubmit, footer, error, size = "lg", children }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const d = dialog.current;
    d?.showModal();
    // showModal() focuses the first button (the close button); move focus to the intended field.
    d?.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    return () => d?.close();
  }, []);

  const submit = (e: FormEvent) => { e.preventDefault(); onSubmit?.(); };

  return (
    <dialog ref={dialog} className={"modal modal-" + size} aria-labelledby={titleId}
      onCancel={(e) => { e.preventDefault(); onClose(); }}>
      <form className="modal-inner" onSubmit={submit}>
        <div className="modal-head">
          <h2 id={titleId} className="h2">{title}</h2>
          <button type="button" className="icon-btn" aria-label="Close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">{children}</div>
        {error && <div className="alert alert-error" role="alert">{error}</div>}
        {footer && <div className="modal-foot">{footer}</div>}
      </form>
    </dialog>
  );
}
