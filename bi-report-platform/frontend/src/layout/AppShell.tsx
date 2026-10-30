import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import Icon from "../components/Icon";

export default function AppShell() {
  const { user, isManager, logout } = useAuth();
  const navigate = useNavigate();
  const navClass = ({ isActive }: { isActive: boolean }) => "nav-btn" + (isActive ? " active" : "");

  return (
    <div className="shell">
      <nav className="sidebar" aria-label="Main">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true"><span /><span /><span /></div>
          <div>
            <div className="brand-name">BI Reports</div>
            <div className="brand-sub">Ask your data</div>
          </div>
        </div>

        <NavLink to="/" end className={navClass}><Icon name="home" />Ask a question</NavLink>
        <NavLink to="/chat" className={navClass}><Icon name="chat" />Chat with data</NavLink>
        <NavLink to="/build-chart" className={navClass}><Icon name="grid" />Build a chart</NavLink>
        <NavLink to="/reports" className={navClass}><Icon name="reports" />Reports</NavLink>
        <NavLink to="/templates" className={navClass}><Icon name="template" />Templates</NavLink>

        {isManager && (
          <>
            <div className="nav-group">Manage</div>
            <NavLink to="/manage/users" className={navClass}><Icon name="users" />Users and access</NavLink>
            <NavLink to="/manage/connections" className={navClass}><Icon name="database" />Connections</NavLink>
            <NavLink to="/manage/ai-models" className={navClass}><Icon name="spark" />AI models</NavLink>
            <NavLink to="/manage/settings" className={navClass}><Icon name="settings" />Usage and settings</NavLink>
          </>
        )}

        <div className="sidebar-foot">
          <div className="who">
            <div className="who-name">{user?.full_name}</div>
            <div className="who-role">{isManager ? "Manager" : "User"}, {user?.email}</div>
          </div>
          <button className="nav-btn" onClick={() => { logout(); navigate("/login"); }}>
            <Icon name="logout" />Sign out
          </button>
        </div>
      </nav>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
