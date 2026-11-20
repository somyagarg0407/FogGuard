import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { Dashboard } from './pages/Dashboard';
import { TrafficManagement } from './pages/TrafficManagement';
import { Analytics } from './pages/Analytics';
import { DetectionHistory } from './pages/DetectionHistory';
import { DeviceStatus } from './pages/DeviceStatus';
import { Settings } from './pages/Settings';
import { useWebSocket } from './hooks/useWebSocket';

function AppContent() {
  useWebSocket();

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header />
        <main className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/traffic" element={<TrafficManagement />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/history" element={<DetectionHistory />} />
            <Route path="/devices" element={<DeviceStatus />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;
