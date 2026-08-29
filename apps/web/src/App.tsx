import {
  Activity,
  BarChart3,
  Boxes,
  FileCheck2,
  LayoutDashboard,
  Menu,
  Network,
  ShieldCheck,
  X,
} from "lucide-react";
import { lazy, Suspense, useState } from "react";
import { LoadingState } from "./components/Shared";

const BenchmarkPage = lazy(() => import("./components/BenchmarkPage"));
const DashboardPage = lazy(() => import("./components/DashboardPage"));
const EvidenceGraphPage = lazy(() => import("./components/EvidenceGraphPage"));
const ReviewPage = lazy(() => import("./components/ReviewPage"));
const SettlementsPage = lazy(() => import("./components/SettlementsPage"));

export type Page = "dashboard" | "settlements" | "reviews" | "graph" | "benchmark";

const navigation: Array<{
  id: Page;
  label: string;
  icon: typeof LayoutDashboard;
}> = [
  { id: "dashboard", label: "Close command", icon: LayoutDashboard },
  { id: "settlements", label: "Settlements", icon: FileCheck2 },
  { id: "reviews", label: "Evidence review", icon: ShieldCheck },
  { id: "graph", label: "Lifecycle graph", icon: Network },
  { id: "benchmark", label: "Safety benchmark", icon: BarChart3 },
];

function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const navigate = (next: Page) => {
    setPage(next);
    setSidebarOpen(false);
  };

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">
            <Boxes size={20} />
          </div>
          <div>
            <div className="brand-name">ProofLedger</div>
            <div className="brand-tag">AI finance controller</div>
          </div>
          <button
            className="icon-button mobile-only"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>

        <div className="workspace-chip">
          <span className="pulse-dot" />
          <div>
            <strong>Demo workspace</strong>
            <small>Synthetic · INR · July 2026</small>
          </div>
        </div>

        <nav className="nav-list">
          <span className="nav-label">Controller workspace</span>
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={`nav-item ${page === item.id ? "active" : ""}`}
                onClick={() => navigate(item.id)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-foot">
          <div className="boundary-card">
            <ShieldCheck size={18} />
            <div>
              <strong>Bounded AI</strong>
              <p>AI explains. Controls approve.</p>
            </div>
          </div>
          <div className="author-line">Built by PARIDHIPAWAIYA</div>
        </div>
      </aside>

      <main className="main-shell">
        <header className="mobile-header">
          <button
            className="icon-button"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation"
          >
            <Menu size={20} />
          </button>
          <div className="brand-name">ProofLedger</div>
          <Activity size={18} />
        </header>
        <Suspense fallback={<LoadingState />}>
          {page === "dashboard" && <DashboardPage onNavigate={navigate} />}
          {page === "settlements" && <SettlementsPage />}
          {page === "reviews" && <ReviewPage />}
          {page === "graph" && <EvidenceGraphPage />}
          {page === "benchmark" && <BenchmarkPage />}
        </Suspense>
      </main>

      {sidebarOpen && (
        <button
          className="sidebar-scrim"
          onClick={() => setSidebarOpen(false)}
          aria-label="Close navigation"
        />
      )}
    </div>
  );
}

export default App;
