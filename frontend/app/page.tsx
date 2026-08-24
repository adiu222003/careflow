import { redirect } from "next/navigation";

/**
 * Root page redirects to login.
 * Authenticated users are redirected from login to their role-specific dashboard.
 */
export default function RootPage() {
  redirect("/login");
}
