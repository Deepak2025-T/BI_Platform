import { Navigate, Route, Routes } from "react-router-dom";
import RequireAuth from "./auth/RequireAuth";
import AppShell from "./layout/AppShell";
import AIModels from "./pages/AIModels";
import AskFlow from "./pages/AskFlow";
import BuildDashboard from "./pages/BuildDashboard";
import Chat from "./pages/Chat";
import Connections from "./pages/Connections";
import Home from "./pages/Home";
import Login from "./pages/Login";
import MyReports from "./pages/MyReports";
import ReportEditor from "./pages/ReportEditor";
import ReportViewer from "./pages/ReportViewer";
import Settings from "./pages/Settings";
import Templates from "./pages/Templates";
import VisualBuilder from "./pages/VisualBuilder";
import Users from "./pages/Users";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      {/* Everything below needs a signed-in user */}
      <Route element={<RequireAuth><AppShell /></RequireAuth>}>
        <Route index element={<Home />} />
        <Route path="ask" element={<AskFlow />} />
        <Route path="chat" element={<Chat />} />
        <Route path="chat/:id" element={<Chat />} />
        <Route path="build" element={<BuildDashboard />} />
        <Route path="reports" element={<MyReports />} />
        <Route path="reports/:id" element={<ReportViewer />} />
        <Route path="reports/:id/edit" element={<ReportEditor />} />
        <Route path="templates" element={<Templates />} />
        <Route path="build-chart" element={<VisualBuilder />} />

        {/* Manager-only pages */}
        <Route path="manage/users" element={<RequireAuth role="manager"><Users /></RequireAuth>} />
        <Route path="manage/ai-models" element={<RequireAuth role="manager"><AIModels /></RequireAuth>} />
        <Route path="manage/connections" element={<RequireAuth role="manager"><Connections /></RequireAuth>} />
        <Route path="manage/settings" element={<RequireAuth role="manager"><Settings /></RequireAuth>} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
