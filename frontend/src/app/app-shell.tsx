import { useQuery } from "@tanstack/react-query";
import { Bell, Leaf, LogOut, Menu, Moon, Sun, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { navTrackA } from "@/app/nav-track-a";
import { navTrackB } from "@/app/nav-track-b";
import type { NavItem } from "@/app/nav-types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn, titleCase } from "@/lib/utils";

const NAV: NavItem[] = [...navTrackB, ...navTrackA];

function useTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("eco-theme", next ? "dark" : "light");
  }
  return { dark, toggle };
}

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth();
  const visible = NAV.filter(
    (item) => item.roles === null || user?.role === "admin" || item.roles.includes(user!.role),
  );
  const groups = [...new Set(visible.map((i) => i.group))];
  return (
    <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
      {groups.map((group) => (
        <div key={group}>
          <p className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-widest text-sidebar-foreground/50">
            {group}
          </p>
          {visible
            .filter((i) => i.group === group)
            .map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "mb-0.5 flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium text-sidebar-foreground/75 transition-colors hover:bg-white/10 hover:text-sidebar-foreground",
                    isActive && "bg-primary/90 text-white shadow-sm hover:bg-primary/90 hover:text-white",
                  )
                }
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {item.label}
              </NavLink>
            ))}
        </div>
      ))}
    </nav>
  );
}

export function AppShell() {
  const { user, logout } = useAuth();
  const { dark, toggle } = useTheme();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const { data: unread } = useQuery({
    queryKey: ["unread-count"],
    queryFn: () => api.get<{ unread: number }>("/notifications/me/unread-count"),
    refetchInterval: 30_000,
  });

  const sidebar = (
    <div className="flex h-full w-60 flex-col bg-sidebar">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-white">
          <Leaf className="h-4 w-4" />
        </div>
        <div>
          <p className="text-sm font-bold tracking-tight text-white">EcoSphere</p>
          <p className="text-[10px] uppercase tracking-widest text-sidebar-foreground/50">
            ESG Platform
          </p>
        </div>
      </div>
      <SidebarNav onNavigate={() => setMobileOpen(false)} />
      <div className="border-t border-white/10 p-3">
        <div className="flex items-center gap-2.5 rounded-md px-2 py-1.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/25 text-xs font-bold text-white">
            {user?.full_name
              .split(" ")
              .map((p) => p[0])
              .slice(0, 2)
              .join("")}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-white">{user?.full_name}</p>
            <p className="truncate text-[11px] text-sidebar-foreground/60">
              {titleCase(user?.role ?? "")}
            </p>
          </div>
          <button
            className="rounded-md p-1.5 text-sidebar-foreground/60 transition-colors hover:bg-white/10 hover:text-white"
            onClick={() => {
              logout();
              navigate("/login");
            }}
            title="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden lg:block">{sidebar}</aside>
      {/* Mobile sidebar */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 left-0 shadow-2xl">{sidebar}</div>
          <button
            className="absolute left-64 top-4 rounded-full bg-card p-2 shadow"
            onClick={() => setMobileOpen(false)}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col lg:pl-60">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b bg-background/85 px-4 backdrop-blur lg:px-8">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={() => setMobileOpen(true)}
            >
              <Menu />
            </Button>
            <p className="text-sm text-muted-foreground">
              {user?.department_name ? `${user.department_name} · ` : ""}
              FY Apr 2026 – Mar 2027 · Asia/Kolkata
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <Button variant="ghost" size="icon" onClick={toggle} title="Toggle theme">
              {dark ? <Sun /> : <Moon />}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="relative"
              onClick={() => navigate("/notifications")}
              title="Notifications"
            >
              <Bell />
              {(unread?.unread ?? 0) > 0 && (
                <Badge
                  variant="destructive"
                  className="absolute -right-1 -top-1 h-4 min-w-4 justify-center px-1 text-[10px]"
                >
                  {unread!.unread > 99 ? "99+" : unread!.unread}
                </Badge>
              )}
            </Button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 lg:px-8 animate-fade-up">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
