import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { categoriesApi } from "../api/endpoints";
import type { Category, Report } from "../api/types";
import CategoryPicker from "./CategoryPicker";
import Modal from "./Modal";

interface Props {
  report: Pick<Report, "title" | "status" | "category">;
  onClose: () => void;
  /** Saves and publishes the report in the chosen category. */
  onPublish: (categoryId: number | null) => Promise<void>;
}

export default function PublishDialog({ report, onClose, onPublish }: Props) {
  const [categories, setCategories] = useState<Category[] | null>(null);
  const [categoryId, setCategoryId] = useState<number | null>(report.category?.id ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const republish = report.status === "published";

  useEffect(() => {
    categoriesApi.list().then(setCategories).catch((e) => { setError(errorMessage(e)); setCategories([]); });
  }, []);

  async function publish() {
    setBusy(true);
    setError("");
    try {
      await onPublish(categoryId);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <Modal size="sm" title={republish ? "Update published report" : "Publish report"} onClose={onClose} onSubmit={publish}
      error={error}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={busy || categories === null}>
            {busy ? "Publishing…" : republish ? "Update" : "Publish"}
          </button>
        </>
      }>
      <div className="stack">
        <p className="muted">
          <span className="strong" style={{ color: "var(--fg)" }}>{report.title}</span> will be visible to everyone in your
          organisation. Put it in a category so people can find it on the Reports page.
        </p>
        {categories === null ? <p className="muted">Loading categories…</p> : (
          <CategoryPicker categories={categories} value={categoryId} onChange={setCategoryId}
            onCreated={(c) => setCategories((list) => [...(list ?? []), c].sort((a, b) => a.name.localeCompare(b.name)))} />
        )}
      </div>
    </Modal>
  );
}
