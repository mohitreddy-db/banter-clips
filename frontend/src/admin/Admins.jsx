import { useState } from "react";
import { api } from "../lib/api.js";
import { Badge, Card, LoadingOrError, PageHead, T, useFetch } from "./ui.jsx";

/** Admin access — console-managed admins on top of the ADMIN_EMAILS bootstrap. */
export default function AdminAdmins() {
  const { data, error, loading, reload } = useFetch(() => api.adminAdmins(), []);
  const [email, setEmail] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [removing, setRemoving] = useState("");

  const run = async (fn, done = "") => {
    setBusy(true);
    setMsg("");
    try {
      await fn();
      setMsg(done);
      setEmail("");
      setReason("");
      setRemoving("");
      reload();
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  const input = { padding: "9px 12px", fontSize: 13, borderRadius: 9, border: `1px solid ${T.border}`, background: T.panel, color: T.text, boxSizing: "border-box" };

  return (
    <>
      <PageHead
        title="Admins"
        sub="Who can open this console. New admins sign in with their normal account — access applies within ~30 seconds."
      />
      <LoadingOrError loading={loading} error={error} reload={reload} />
      {data && (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.4fr) minmax(280px, 1fr)", gap: 16 }} className="admin-two-col">
          <Card title="Current admins" sub={data.note}>
            {data.admins.length === 0 && (
              <div style={{ fontSize: 12.5, color: T.muted2 }}>
                No admins configured — set ADMIN_EMAILS on the server for the bootstrap admin.
              </div>
            )}
            {data.admins.map((a) => (
              <div key={a.email} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 0", borderBottom: `1px solid ${T.border}55`, flexWrap: "wrap" }}>
                <span style={{ width: 30, height: 30, borderRadius: "50%", background: T.purple, display: "grid", placeItems: "center", fontSize: 12, fontWeight: 700, color: "#fff", flexShrink: 0 }}>
                  {a.email[0].toUpperCase()}
                </span>
                <span style={{ fontSize: 13, fontWeight: 600, color: T.text, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {a.email}
                  {a.email === data.you && <span style={{ color: T.muted2, fontWeight: 500 }}> (you)</span>}
                </span>
                <span style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
                  {a.source === "env"
                    ? <Badge color={T.muted}>ENV · PINNED</Badge>
                    : <Badge color={T.cyan}>CONSOLE</Badge>}
                  {a.source === "console" && a.email !== data.you && (
                    removing === a.email ? (
                      <button className="ghost-btn" style={{ padding: "5px 12px", fontSize: 11.5, color: "#fff", background: T.error, border: "none" }}
                              disabled={busy || !reason.trim()}
                              title={!reason.trim() ? "Enter a reason below first" : undefined}
                              onClick={() => run(() => api.adminRemoveAdmin(a.email, reason), `${a.email} removed.`)}>
                        Confirm remove
                      </button>
                    ) : (
                      <button className="ghost-btn" style={{ padding: "5px 12px", fontSize: 11.5, color: T.error }}
                              disabled={busy} onClick={() => { setRemoving(a.email); setMsg(""); }}>
                        Remove
                      </button>
                    )
                  )}
                </span>
              </div>
            ))}
          </Card>

          <Card title="Add an admin" sub="they get full console access — every action they take is audited">
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@example.com" style={input} />
              <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (required — feeds the audit log)" style={input} />
              <button className="grad-btn" style={{ padding: "10px 16px", fontSize: 13 }}
                      disabled={busy || !email.trim() || !reason.trim()}
                      onClick={() => run(() => api.adminAddAdmin(email, reason), `${email.trim().toLowerCase()} added.`)}>
                {busy ? "…" : "+ Add admin"}
              </button>
              {removing && (
                <div style={{ fontSize: 11.5, color: T.amber }}>
                  Removing <b>{removing}</b> — the reason field above is used for the audit entry.
                </div>
              )}
              {msg && <div style={{ fontSize: 12.5, color: msg.endsWith("added.") || msg.endsWith("removed.") ? T.green : T.error }}>{msg}</div>}
              <div style={{ fontSize: 11, color: T.muted2 }}>
                Safety rails: you can't remove yourself, and admins pinned by the server's
                ADMIN_EMAILS can only be changed in the server config.
              </div>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
