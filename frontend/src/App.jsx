import { Routes, Route, Navigate } from "react-router-dom";
import Landing from "./pages/Landing.jsx";
import SignIn from "./pages/SignIn.jsx";
import ResetPassword from "./pages/ResetPassword.jsx";
import Onboarding from "./pages/Onboarding.jsx";
import AppShell from "./components/AppShell.jsx";
import Studio from "./pages/Studio.jsx";
import Clips from "./pages/Clips.jsx";
import Account from "./pages/Account.jsx";
import Pricing from "./pages/Pricing.jsx";
import { Privacy, Terms } from "./pages/Legal.jsx";
import AdminCatalog from "./pages/AdminCatalog.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/signin" element={<SignIn />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/privacy" element={<Privacy />} />
      <Route path="/terms" element={<Terms />} />
      <Route path="/onboarding" element={<Onboarding />} />
      <Route element={<AppShell />}>
        <Route path="/studio" element={<Studio />} />
        <Route path="/clips" element={<Clips />} />
        <Route path="/account" element={<Account />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/admin" element={<AdminCatalog />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
