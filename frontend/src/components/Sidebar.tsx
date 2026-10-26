export type RouteId = "overview" | "monitor" | "accuracy" | "history";

export const ROUTES: ReadonlyArray<{ id: RouteId; label: string }> = [
  { id: "overview", label: "Executive Overview" },
  { id: "monitor", label: "Forecast Monitor" },
  { id: "accuracy", label: "Accuracy Analytics" },
  { id: "history", label: "History & Data Quality" },
];

/** Hash links keep this a pure static site (no server rewrites needed on Vercel). */
export function Sidebar({ current }: { current: RouteId }) {
  return (
    <nav className="sidebar" aria-label="Dashboard sections">
      {ROUTES.map((r) => (
        <a key={r.id} className="sidebar__link" href={`#/${r.id}`} aria-current={r.id === current ? "page" : undefined}>
          {r.label}
        </a>
      ))}
      <p className="sidebar__note">
        This dashboard shows evidence only. It does not make purchasing decisions, and every figure is calculated by
        the analytics backend.
      </p>
    </nav>
  );
}
