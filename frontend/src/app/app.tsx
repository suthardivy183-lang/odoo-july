import { Navigate, Outlet, useLocation, useRoutes } from "react-router-dom";

import { AppShell } from "@/app/app-shell";
import { routesTrackA } from "@/app/routes-track-a";
import { routesTrackB } from "@/app/routes-track-b";
import { EmptyState } from "@/components/app/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { LoginPage } from "@/features/auth/login-page";
import { useAuth } from "@/lib/auth";

function Protected() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="w-72 space-y-3">
          <Skeleton className="h-8 w-1/2" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

export function App() {
  return useRoutes([
    { path: "/login", element: <LoginPage /> },
    {
      element: <Protected />,
      children: [
        {
          path: "/",
          element: <AppShell />,
          children: [
            ...routesTrackB,
            ...routesTrackA,
            {
              path: "*",
              element: (
                <EmptyState
                  title="Page not found"
                  description="This page does not exist or has not been built yet."
                />
              ),
            },
          ],
        },
      ],
    },
  ]);
}
