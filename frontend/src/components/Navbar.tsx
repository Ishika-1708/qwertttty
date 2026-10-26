import { SystemStatusPanel } from "./SystemStatusPanel";

export function Navbar() {
  return (
    <header className="navbar">
      <div className="navbar__brand">
        <span className="navbar__title">Wind Forecast Evaluation</span>
        <span className="navbar__subtitle">Forecast vs actual generation · evidence for purchasing decisions</span>
      </div>
      <SystemStatusPanel />
    </header>
  );
}
