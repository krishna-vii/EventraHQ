import { Suspense } from "react";
import AccountPage from "../../components/account";
export default function Page() {
  return <Suspense fallback={<main className="container page-intro"><h1>Your workspace</h1><p role="status">Loading your workspace…</p></main>}><AccountPage /></Suspense>;
}
