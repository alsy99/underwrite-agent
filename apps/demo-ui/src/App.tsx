import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthGate } from "./components/AuthGate";
import { Layout } from "./components/Layout";
import { CaseDetail } from "./pages/CaseDetail";
import { Dashboard } from "./pages/Dashboard";
import { NewCase } from "./pages/NewCase";

const routerBasename =
  import.meta.env.BASE_URL === "/" ? undefined : import.meta.env.BASE_URL.replace(/\/$/, "");

export default function App() {
  return (
    <AuthGate>
    <BrowserRouter basename={routerBasename}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new" element={<NewCase />} />
          <Route path="/cases/:caseId" element={<CaseDetail />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
    </AuthGate>
  );
}
