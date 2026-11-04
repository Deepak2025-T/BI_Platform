import { useEffect, useState, type FormEvent } from "react";
import { errorMessage } from "../api/client";
import { usersApi } from "../api/endpoints";
import type { Role, User } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";

export default function Users() {
  const { user: me } = useAuth();
  const toast = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [form, setForm] = useState({ full_name: "", email: "", password: "", role: "user" as Role });
  const [formError, setFormError] = useState("");
  const [resetFor, setResetFor] = useState<number | null>(null);
  const [newPw, setNewPw] = useState("");

  useEffect(() => { usersApi.list().then(setUsers).catch((e) => toast(errorMessage(e))); }, [toast]);

  const replace = (u: User) => setUsers((list) => list.map((x) => (x.id === u.id ? u : x)));

  async function create(e: FormEvent) {
    e.preventDefault();
    setFormError("");
    try {
      const u = await usersApi.create(form);
      setUsers((l) => [...l, u]);
      setForm({ full_name: "", email: "", password: "", role: "user" });
      toast(`Added ${u.full_name}. Share the password with them securely.`);
    } catch (err) { setFormError(errorMessage(err)); }
  }

  async function update(u: User, body: Parameters<typeof usersApi.update>[1], msg: string) {
    try { replace(await usersApi.update(u.id, body)); toast(msg); }
    catch (err) { toast(errorMessage(err)); }
  }

  return (
    <div className="page">
      <div className="stack-lg" style={{ maxWidth: 1100 }}>
        <div>
          <h1 className="h1">Users and access</h1>
          <p className="muted">Users can ask questions, build reports and see published reports. Managers can also edit any report, manage users and change settings.</p>
        </div>

        <form className="card stack" onSubmit={create} aria-labelledby="add-h">
          <h2 id="add-h" className="h2">Add a person</h2>
          {formError && <div className="alert alert-error" role="alert">{formError}</div>}
          <div className="form-grid">
            <label className="field"><span>Full name</span><input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></label>
            <label className="field"><span>Work email</span><input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
            <label className="field"><span>Temporary password (8+ characters)</span><input type="text" required minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
            <label className="field"><span>Access</span>
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
                <option value="user">User</option><option value="manager">Manager</option>
              </select>
            </label>
          </div>
          <button className="btn btn-primary self-start" type="submit">Add person</button>
        </form>

        <div className="card flush table-scroll">
          <table className="table">
            <thead><tr><th scope="col">Name</th><th scope="col">Access</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {users.map((u) => {
                const self = u.id === me?.id;
                return (
                  <tr key={u.id}>
                    <td><div className="strong">{u.full_name}{self && " (you)"}</div><div className="muted small">{u.email}</div></td>
                    <td>
                      <label className="sr-only" htmlFor={`role-${u.id}`}>Access for {u.full_name}</label>
                      <select id={`role-${u.id}`} value={u.role} disabled={self}
                        onChange={(e) => update(u, { role: e.target.value as Role }, `${u.full_name} is now a ${e.target.value}`)}>
                        <option value="user">User</option><option value="manager">Manager</option>
                      </select>
                    </td>
                    <td><span className={"badge " + (u.is_active ? "badge-ok" : "badge-off")}>{u.is_active ? "Active" : "Disabled"}</span></td>
                    <td className="r">
                      {resetFor === u.id ? (
                        <span className="row-wrap end">
                          <label className="sr-only" htmlFor={`pw-${u.id}`}>New password</label>
                          <input id={`pw-${u.id}`} placeholder="New password" value={newPw} onChange={(e) => setNewPw(e.target.value)} />
                          <button className="btn btn-primary btn-sm" disabled={newPw.length < 8}
                            onClick={() => { update(u, { password: newPw }, "Password changed"); setResetFor(null); setNewPw(""); }}>Save</button>
                          <button className="btn btn-ghost btn-sm" onClick={() => setResetFor(null)}>Cancel</button>
                        </span>
                      ) : (
                        <span className="row-wrap end">
                          <button className="btn btn-ghost btn-sm" onClick={() => setResetFor(u.id)}>Reset password</button>
                          {!self && (
                            <button className="btn btn-ghost btn-sm" onClick={() => update(u, { is_active: !u.is_active }, u.is_active ? "Access removed" : "Access restored")}>
                              {u.is_active ? "Disable" : "Enable"}
                            </button>
                          )}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
