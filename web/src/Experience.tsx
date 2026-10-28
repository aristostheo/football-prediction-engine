import { lazy, Suspense } from "react";

const Dashboard = lazy(() => import("./touchline/Dashboard"));

// Retired URLs open the current app. Keep saved browser data and query/hash state.
if (["/classic", "/updated-mockup"].includes(window.location.pathname.replace(/\/+$/, ""))) {
  window.history.replaceState(null, "", `/${window.location.search}${window.location.hash}`);
}

export default function Experience() {
  return (
    <Suspense
      fallback={
        <div
          role="status"
          style={{
            padding: 32,
            fontFamily: "sans-serif",
            background: "#f4f2ec",
            color: "#252821",
            minHeight: "100vh",
          }}
        >
          Opening Match Forecast…
        </div>
      }
    >
      <Dashboard />
    </Suspense>
  );
}
