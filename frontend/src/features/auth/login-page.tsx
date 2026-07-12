import { Leaf } from "lucide-react";
import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";

const DEMO_ACCOUNTS = [
  { label: "Employee", email: "employee@ecosphere.in" },
  { label: "Dept Head", email: "head@ecosphere.in" },
  { label: "ESG Manager", email: "esg@ecosphere.in" },
  { label: "Admin", email: "admin@ecosphere.in" },
];

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function submit(e?: React.FormEvent, overrideEmail?: string) {
    e?.preventDefault();
    setBusy(true);
    try {
      await login(overrideEmail ?? email, overrideEmail ? "Demo@123" : password);
      navigate((location.state as { from?: string } | null)?.from ?? "/", { replace: true });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen">
      {/* Brand panel */}
      <div className="relative hidden w-1/2 flex-col justify-between overflow-hidden bg-sidebar p-10 lg:flex">
        <div className="absolute -right-32 -top-32 h-96 w-96 rounded-full bg-primary/20 blur-3xl" />
        <div className="absolute -bottom-40 -left-24 h-96 w-96 rounded-full bg-emerald-400/10 blur-3xl" />
        <div className="relative flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-white">
            <Leaf className="h-5 w-5" />
          </div>
          <span className="text-lg font-bold tracking-tight text-white">EcoSphere</span>
        </div>
        <div className="relative">
          <h1 className="max-w-md text-4xl font-bold leading-tight tracking-tight text-white">
            Measure, engage and govern your ESG impact.
          </h1>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-sidebar-foreground/70">
            Carbon tracking with auditable calculations, CSR and challenge engagement with XP
            rewards, policy governance and transparent ESG scoring — in one place.
          </p>
        </div>
        <p className="relative text-xs text-sidebar-foreground/50">
          Fiscal year April–March · INR · Asia/Kolkata
        </p>
      </div>

      {/* Form panel */}
      <div className="flex flex-1 items-center justify-center bg-background p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-white">
              <Leaf className="h-5 w-5" />
            </div>
            <h1 className="text-xl font-bold">EcoSphere</h1>
          </div>
          <h2 className="text-2xl font-bold tracking-tight">Welcome back</h2>
          <p className="mb-6 mt-1 text-sm text-muted-foreground">
            Sign in with your work account
          </p>
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                required
                placeholder="you@ecosphere.in"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                required
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          <Card className="mt-8 border-dashed">
            <CardContent className="p-4">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Demo accounts · password Demo@123
              </p>
              <div className="grid grid-cols-2 gap-2">
                {DEMO_ACCOUNTS.map((acc) => (
                  <Button
                    key={acc.email}
                    variant="outline"
                    size="sm"
                    disabled={busy}
                    onClick={() => void submit(undefined, acc.email)}
                  >
                    {acc.label}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
