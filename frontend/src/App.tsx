import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { Shell } from "./components/Shell";
import LandingPage from "./pages/Landing";
import DashboardPage from "./pages/Dashboard";
import ProfilesPage from "./pages/Profiles";
import HuntPage from "./pages/Hunt";
import {
  OpportunitiesPage,
  OpportunityDetailPage,
  SuppressedPage,
} from "./pages/Opportunities";
import KanbanPage from "./pages/Kanban";
import SourcesPage from "./pages/Sources";
import AboutPage from "./pages/About";
import SettingsPage from "./pages/Settings";

function RoutedApp() {
  const location = useLocation();

  useEffect(() => {
    document.documentElement.dataset.route = location.pathname;
  }, [location.pathname]);

  const isLanding = location.pathname === "/";

  const page = (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/profiles" element={<ProfilesPage />} />
      <Route path="/hunt" element={<HuntPage />} />
      <Route path="/opportunities" element={<OpportunitiesPage />} />
      <Route path="/opportunities/:id" element={<OpportunityDetailPage />} />
      <Route path="/suppressed" element={<SuppressedPage />} />
      <Route path="/applications" element={<KanbanPage />} />
      <Route path="/kanban" element={<KanbanPage />} />
      <Route path="/sources" element={<SourcesPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );

  if (isLanding) return page;
  return <Shell>{page}</Shell>;
}

export default function App() {
  return (
    <BrowserRouter>
      <RoutedApp />
    </BrowserRouter>
  );
}
