import { lazy, Suspense } from "react";

// The mockup never mounts the live dashboard's data-fetching effects. CSS is
// imported with each experience, so the two visual directions stay isolated.
const App = lazy(() => import("./App"));
const UpdatedMockup = lazy(() => import("./mockup/UpdatedMockup"));

export default function Experience() {
  const preview =
    window.location.pathname.replace(/\/+$/, "") === "/updated-mockup";
  return (
    <Suspense
      fallback={
        <div
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
      {preview ? <UpdatedMockup /> : <App />}
    </Suspense>
  );
}
