import { useEffect, useState } from "react";
import { DateRangeFilter } from "./components/DateRangeFilter";
import { Navbar } from "./components/Navbar";
import { ROUTES, Sidebar, type RouteId } from "./components/Sidebar";
import { FilterProvider } from "./context/FilterContext";
import { StatusProvider } from "./context/StatusContext";
import { AccuracyAnalyticsPage } from "./pages/AccuracyAnalytics";
import { ForecastHistoryPage } from "./pages/ForecastHistory";
import { ForecastMonitorPage } from "./pages/ForecastMonitor";
import { OverviewPage } from "./pages/Overview";

function routeFromHash(): RouteId {
  const id = window.location.hash.replace(/^#\/?/, "");
  return ROUTES.find((r) => r.id === id)?.id ?? "overview";
}

function useHashRoute(): RouteId {
  const [route, setRoute] = useState<RouteId>(routeFromHash);
  useEffect(() => {
    const onChange = () => setRoute(routeFromHash());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

function Page({ route }: { route: RouteId }) {
  switch (route) {
    case "overview":
      return <OverviewPage />;
    case "monitor":
      return <ForecastMonitorPage />;
    case "accuracy":
      return <AccuracyAnalyticsPage />;
    case "history":
      return <ForecastHistoryPage />;
  }
}

export default function App() {
  const route = useHashRoute();
  return (
    <StatusProvider>
      <FilterProvider>
        <div className="app">
          <Navbar />
          <div className="shell">
            <Sidebar current={route} />
            <main className="main" id="main">
              <DateRangeFilter />
              <Page route={route} />
            </main>
          </div>
        </div>
      </FilterProvider>
    </StatusProvider>
  );
}
