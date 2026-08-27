import { api } from "../lib/api.js";
import { Card, LoadingOrError, PageHead, T, useFetch } from "./ui.jsx";

/**
 * Credits — deliberately a placeholder. The credit system (PRICING.md) is not
 * integrated yet; this page owns the spot so the ledger, grant actions and
 * issued/consumed KPIs land here without touching the rest of the console.
 */
export default function AdminCredits() {
  const { data, error, loading, reload } = useFetch(() => api.adminCredits(), []);

  return (
    <>
      <PageHead title="Credits" sub="One wallet per user · 1 credit = $0.01 face value — once the credit system ships." />
      <LoadingOrError loading={loading} error={error} reload={reload} />
      {data && !data.enabled && (
        <>
          <div className="panel" style={{ padding: "16px 20px", border: "1px solid rgba(225,158,60,.5)", borderRadius: 14 }}>
            <div style={{ fontSize: 13.5, fontWeight: 700, color: T.amber, marginBottom: 6 }}>
              ⚑ Credit system not live yet
            </div>
            <div style={{ fontSize: 12.5, color: T.muted, lineHeight: 1.6 }}>
              {data.note} When the ledger ships, this page gains: issued / consumed / purchased / expired KPIs,
              the per-user ledger (consumed · purchased · granted · reserved · released · expired),
              and the <b style={{ color: T.text }}>grant credits</b> action. The backend placeholder is
              <code style={{ color: T.cyan }}> GET /admin/credits</code> — everything else in the console
              reports provider dollars and does not assume credits exist.
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16 }}>
            <Card title="Launch price list (PRICING.md §4)" sub="read-only — prices are code constants for MVP">
              <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse", color: T.text }}>
                <thead>
                  <tr>
                    {["LENGTH", "720P", "1080P"].map((h) => (
                      <th key={h} style={{ textAlign: "left", fontSize: 9.5, letterSpacing: ".08em", color: T.muted2, padding: "6px 8px", borderBottom: `1px solid ${T.border}` }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(data.price_list.video).map(([len, res]) => (
                    <tr key={len}>
                      <td style={{ padding: "8px", color: T.muted }}>{len}</td>
                      <td style={{ padding: "8px", fontWeight: 700 }}>{res["720p"].toLocaleString()} cr</td>
                      <td style={{ padding: "8px", fontWeight: 700 }}>{res["1080p"].toLocaleString()} cr</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ fontSize: 12, color: T.muted, marginTop: 12 }}>
                ✨ Enhance take: <b style={{ color: T.text }}>{data.price_list.extras.enhance_take} cr</b> ·
                captions / publish / retry: <b style={{ color: T.text }}>0</b> ·
                1 credit = ${data.price_list.face_value_usd}
              </div>
            </Card>

            <Card title="What lands here when credits ship" sub="kept open by design">
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: T.muted, lineHeight: 2 }}>
                <li>Issued vs consumed vs purchased vs expired KPIs</li>
                <li>Ledger table with reserve-on-start / release-on-failure rows (PRICING rule 3)</li>
                <li>Grant credits (reason required → audit log) · mark comped (1,100/mo, no billing)</li>
                <li>Per-clip credit receipts with line items on All Videos</li>
                <li>Gross margin switches from MRR-basis to consumed-credits basis</li>
              </ul>
            </Card>
          </div>
        </>
      )}
    </>
  );
}
