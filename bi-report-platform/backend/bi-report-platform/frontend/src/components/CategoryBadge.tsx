import type { CategoryRef } from "../api/types";

export default function CategoryBadge({ category }: { category: CategoryRef | null }) {
  if (!category) return <span className="cat-badge none">No category</span>;
  return (
    <span className="cat-badge">
      <span className="cat-dot" style={{ background: category.color }} aria-hidden="true" />
      {category.name}
    </span>
  );
}
