"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { User } from "@/types";

export default function Navbar() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("careflow_user");
      if (stored) {
        try {
          setUser(JSON.parse(stored));
        } catch {}
      }
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("careflow_token");
    localStorage.removeItem("careflow_user");
    router.push("/login");
  };

  const dashboardUrl = user?.role ? `/${user.role.toLowerCase()}/dashboard` : "/";

  return (
    <nav className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <div className="flex-shrink-0 flex items-center">
            <Link href={dashboardUrl} className="text-xl font-bold text-indigo-600 tracking-tight">
              CareFlow
            </Link>
          </div>
          <div className="flex items-center space-x-4">
            {user ? (
              <>
                <span className="text-sm text-gray-700 hidden sm:inline-block">
                  {user.full_name} ({user.role})
                </span>
                <button
                  onClick={handleLogout}
                  className="text-sm font-medium text-gray-500 hover:text-gray-700"
                >
                  Logout
                </button>
              </>
            ) : (
              <Link href="/login" className="text-sm font-medium text-indigo-600 hover:text-indigo-500">
                Login
              </Link>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
