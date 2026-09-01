import { Routes, Route, Navigate } from "react-router-dom";
import Landing from "./pages/Landing.jsx";
import SignIn from "./pages/SignIn.jsx";
import ResetPassword from "./pages/ResetPassword.jsx";
import Onboarding from "./pages/Onboarding.jsx";
import AppShell from "./components/AppShell.jsx";
import Studio from "./pages/Studio.jsx";
import Prompts from "./pages/Prompts.jsx";
import Clips from "./pages/Clips.jsx";
import Account from "./pages/Account.jsx";
import Pricing from "./pages/Pricing.jsx";
import { Privacy, Terms } from "./pages/Legal.jsx";
import { ShowcaseIndex, ShowcaseClip } from "./pages/Showcase.jsx";
import AdminCatalog from "./pages/AdminCatalog.jsx";
import AdminShell from "./admin/AdminShell.jsx";
import AdminDashboard from "./admin/Dashboard.jsx";
import AdminUsers from "./admin/Users.jsx";
import AdminVideos from "./admin/Videos.jsx";
import AdminJobs from "./admin/Jobs.jsx";
import AdminCosts from "./admin/Costs.jsx";
import AdminRevenue from "./admin/Revenue.jsx";
import AdminCredits from "./admin/Credits.jsx";
import AdminPublishing from "./admin/Publishing.jsx";
import AdminAudit from "./admin/Audit.jsx";
import AdminAdmins from "./admin/Admins.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/signin" element={<SignIn />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/privacy" element={<Privacy />} />
      <Route path="/terms" element={<Terms />} />
      <Route path="/onboarding" element={<Onboarding />} />
      {/* Public on purpose: pricing is the highest-intent search query a SaaS
          gets, and inside the AppShell gate a crawler only ever saw a redirect
          to /signin. The page itself puts the app chrome back for signed-in
          users (AppShell children mode). */}
      <Route path="/pricing" element={<Pricing />} />
      {/* Public clip pages — /showcase, not /clips, which is the gated user
          library. One URL per clip so each carries its own VideoObject. */}
      <Route path="/showcase" element={<ShowcaseIndex />} />
      <Route path="/showcase/:slug" element={<ShowcaseClip />} />
      <Route element={<AppShell />}>
        <Route path="/studio" element={<Studio />} />
        <Route path="/prompts" element={<Prompts />} />
        <Route path="/clips" element={<Clips />} />
        <Route path="/account" element={<Account />} />
      </Route>
      {/* Admin console — its own shell + grouped sidebar (ADMIN.md §2). */}
      <Route path="/admin" element={<AdminShell />}>
        <Route index element={<AdminDashboard />} />
        <Route path="users" element={<AdminUsers />} />
        <Route path="videos" element={<AdminVideos />} />
        <Route path="jobs" element={<AdminJobs />} />
        <Route path="costs" element={<AdminCosts />} />
        <Route path="revenue" element={<AdminRevenue />} />
        <Route path="credits" element={<AdminCredits />} />
        <Route path="publishing" element={<AdminPublishing />} />
        <Route path="catalog" element={<AdminCatalog />} />
        <Route path="admins" element={<AdminAdmins />} />
        <Route path="audit" element={<AdminAudit />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
