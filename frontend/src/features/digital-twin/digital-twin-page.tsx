import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CarFront,
  Factory,
  Gauge,
  House,
  IndianRupee,
  Leaf,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  TrendingDown,
} from "lucide-react";
import { useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { DigitalTwinResult, DigitalTwinScenario } from "@/lib/types";
import { cn, formatINR } from "@/lib/utils";

const DEFAULT_SCENARIO: DigitalTwinScenario = {
  current_esg_score: 72,
  fleet_electrification_pct: 50,
  remote_employee_pct: 30,
  remote_days_per_week: 2,
  supplier_switch_pct: 30,
  supplier_emissions_improvement_pct: 30,
  supplier_from: "Supplier A",
  supplier_to: "Supplier B",
  period: "fy",
};

const PRESETS: { name: string; caption: string; values: Partial<DigitalTwinScenario> }[] = [
  { name: "Balanced", caption: "EV + hybrid + supplier", values: DEFAULT_SCENARIO },
  {
    name: "Fleet-first",
    caption: "Accelerate transport",
    values: {
      fleet_electrification_pct: 75,
      remote_employee_pct: 15,
      remote_days_per_week: 1,
      supplier_switch_pct: 10,
      supplier_emissions_improvement_pct: 20,
    },
  },
  {
    name: "Workplace shift",
    caption: "Remote-first policy",
    values: {
      fleet_electrification_pct: 20,
      remote_employee_pct: 60,
      remote_days_per_week: 3,
      supplier_switch_pct: 10,
      supplier_emissions_improvement_pct: 15,
    },
  },
  {
    name: "Supply chain",
    caption: "Low-carbon sourcing",
    values: {
      fleet_electrification_pct: 10,
      remote_employee_pct: 10,
      remote_days_per_week: 1,
      supplier_switch_pct: 75,
      supplier_emissions_improvement_pct: 45,
    },
  },
];

function Lever({
  icon: Icon,
  label,
  value,
  min = 0,
  max = 100,
  step = 1,
  suffix = "%",
  hint,
  onChange,
}: {
  icon: typeof CarFront;
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  suffix?: string;
  hint: string;
  onChange: (value: number) => void;
}) {
  const fill = ((value - min) / (max - min)) * 100;
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.045] p-4 transition-colors hover:bg-white/[0.07]">
      <div className="flex items-start justify-between gap-4">
        <div className="flex gap-3">
          <div className="mt-0.5 grid h-9 w-9 place-items-center rounded-xl bg-emerald-300/10 text-emerald-300">
            <Icon className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-semibold text-white">{label}</p>
            <p className="mt-0.5 text-xs text-white/45">{hint}</p>
          </div>
        </div>
        <span className="shrink-0 text-xl font-bold tabular-nums text-emerald-300">
          {value}{suffix}
        </span>
      </div>
      <input
        aria-label={label}
        className="twin-range mt-4 w-full"
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        style={{ "--range-fill": `${fill}%` } as React.CSSProperties}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </div>
  );
}

function formatCarbon(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M kg`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}k kg`;
  return `${value.toFixed(0)} kg`;
}

export function DigitalTwinPage() {
  const [draft, setDraft] = useState<DigitalTwinScenario>(DEFAULT_SCENARIO);
  const [submitted, setSubmitted] = useState({ scenario: DEFAULT_SCENARIO, version: 0 });
  const { data, isFetching, error } = useQuery({
    queryKey: ["digital-twin", submitted.version],
    queryFn: () => api.post<DigitalTwinResult>("/scores/simulate", submitted.scenario),
  });

  const update = <K extends keyof DigitalTwinScenario>(key: K, value: DigitalTwinScenario[K]) =>
    setDraft((current) => ({ ...current, [key]: value }));

  const runScenario = () =>
    setSubmitted((current) => ({ scenario: { ...draft }, version: current.version + 1 }));

  return (
    <div className="twin-page -mx-4 -my-6 min-h-[calc(100vh-3.5rem)] px-4 py-7 lg:-mx-8 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <header className="mb-6 flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
          <div>
            <div className="mb-3 flex items-center gap-2">
              <Badge className="border border-emerald-300/20 bg-emerald-300/10 text-emerald-200 hover:bg-emerald-300/10">
                <Sparkles className="mr-1 h-3 w-3" /> Decision intelligence
              </Badge>
              <span className="text-xs text-white/40">FY scenario model · India</span>
            </div>
            <h1 className="max-w-3xl text-3xl font-semibold tracking-[-0.04em] text-white sm:text-5xl">
              Test the future before <span className="text-emerald-300">funding it.</span>
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-white/55 sm:text-base">
              Move operational levers and see the carbon, ESG score, and financial impact before
              committing capital.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-4 py-2 text-xs text-white/55">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300 opacity-50" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-300" />
            </span>
            {data?.data_source === "live_ledger"
              ? "Live carbon ledger connected"
              : data?.data_source === "planning_baseline"
                ? "Annual planning baseline active"
                : "Demo baseline active"}
          </div>
        </header>

        <div className="grid gap-5 lg:grid-cols-[0.82fr_1.18fr]">
          <section className="rounded-[1.75rem] border border-white/10 bg-[#0d1916]/90 p-4 shadow-2xl shadow-black/20 sm:p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-300/70">Scenario levers</p>
                <h2 className="mt-1 text-lg font-semibold text-white">Build an intervention</h2>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="text-white/50 hover:bg-white/10 hover:text-white"
                onClick={() => setDraft(DEFAULT_SCENARIO)}
              >
                <RotateCcw /> Reset
              </Button>
            </div>

            <div className="mb-4 grid grid-cols-2 gap-2">
              {PRESETS.map((preset) => (
                <button
                  key={preset.name}
                  className="rounded-xl border border-white/10 bg-black/10 px-3 py-2 text-left transition-all hover:-translate-y-0.5 hover:border-emerald-300/30 hover:bg-emerald-300/[0.06]"
                  onClick={() => setDraft((current) => ({ ...current, ...preset.values }))}
                >
                  <span className="block text-xs font-semibold text-white">{preset.name}</span>
                  <span className="block text-[10px] text-white/40">{preset.caption}</span>
                </button>
              ))}
            </div>

            <div className="space-y-3">
              <Lever
                icon={CarFront}
                label="Replace diesel fleet with EVs"
                hint="Share of fleet transitioned"
                value={draft.fleet_electrification_pct}
                onChange={(value) => update("fleet_electrification_pct", value)}
              />
              <Lever
                icon={House}
                label="Hybrid work adoption"
                hint={`${draft.remote_days_per_week} remote day(s) per week`}
                value={draft.remote_employee_pct}
                onChange={(value) => update("remote_employee_pct", value)}
              />
              <Lever
                icon={Gauge}
                label="Remote days per week"
                hint="Applied to participating employees"
                value={draft.remote_days_per_week}
                min={0}
                max={5}
                step={1}
                suffix=" days"
                onChange={(value) => update("remote_days_per_week", value)}
              />
              <Lever
                icon={Factory}
                label="Switch supplier volume"
                hint={`${draft.supplier_from} → ${draft.supplier_to}`}
                value={draft.supplier_switch_pct}
                onChange={(value) => update("supplier_switch_pct", value)}
              />
              <Lever
                icon={Leaf}
                label="Replacement supplier advantage"
                hint="Modeled emissions improvement"
                value={draft.supplier_emissions_improvement_pct}
                onChange={(value) => update("supplier_emissions_improvement_pct", value)}
              />
            </div>

            <div className="mt-3 grid grid-cols-2 gap-2">
              <Input
                aria-label="Current supplier"
                className="border-white/10 bg-white/5 text-white placeholder:text-white/30"
                value={draft.supplier_from}
                onChange={(event) => update("supplier_from", event.target.value)}
              />
              <Input
                aria-label="Replacement supplier"
                className="border-white/10 bg-white/5 text-white placeholder:text-white/30"
                value={draft.supplier_to}
                onChange={(event) => update("supplier_to", event.target.value)}
              />
            </div>

            <Button
              size="lg"
              className="mt-4 w-full bg-emerald-300 font-semibold text-emerald-950 shadow-lg shadow-emerald-500/10 hover:bg-emerald-200"
              disabled={isFetching || !draft.supplier_from.trim() || !draft.supplier_to.trim()}
              onClick={runScenario}
            >
              {isFetching ? "Running digital twin…" : "Run this scenario"}
              {!isFetching && <ArrowRight />}
            </Button>
          </section>

          <section className={cn("space-y-5 transition-opacity", isFetching && "opacity-60")}>
            {error && (
              <div className="rounded-2xl border border-red-400/20 bg-red-400/10 p-4 text-sm text-red-100">
                {error instanceof Error ? error.message : "The scenario could not be calculated."}
              </div>
            )}

            <div className="twin-result relative overflow-hidden rounded-[1.75rem] border border-emerald-200/15 p-6 sm:p-8">
              <div className="relative z-10">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-950/55">Projected ESG score</p>
                    <p className="mt-1 text-sm text-emerald-950/70">After full scenario adoption</p>
                  </div>
                  <div className="rounded-full border border-emerald-950/10 bg-white/35 px-3 py-1 text-xs font-semibold text-emerald-950">
                    +{data?.score_uplift ?? "—"} points
                  </div>
                </div>

                <div className="mt-7 flex items-end gap-4 sm:gap-7">
                  <div>
                    <p className="text-xs uppercase tracking-wider text-emerald-950/45">Current</p>
                    <p className="text-4xl font-semibold tracking-[-0.05em] text-emerald-950/50 sm:text-6xl">
                      {data?.current_esg_score ?? "—"}
                    </p>
                  </div>
                  <ArrowRight className="mb-3 h-8 w-8 text-emerald-900/35 sm:mb-5" />
                  <div>
                    <p className="text-xs uppercase tracking-wider text-emerald-950/60">Scenario</p>
                    <p className="text-6xl font-bold tracking-[-0.07em] text-emerald-950 sm:text-8xl">
                      {data?.scenario_esg_score ?? "—"}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-white/[0.055] p-5">
                <div className="flex items-center justify-between">
                  <div className="grid h-10 w-10 place-items-center rounded-xl bg-cyan-300/10 text-cyan-300">
                    <TrendingDown />
                  </div>
                  <span className="text-xs text-white/40">annualized</span>
                </div>
                <p className="mt-5 text-3xl font-semibold tracking-tight text-white">
                  {data?.carbon_reduction_pct ?? "—"}%
                </p>
                <p className="mt-1 text-sm text-white/45">Carbon reduction</p>
                <p className="mt-3 text-xs text-cyan-200/70">
                  {data ? `${formatCarbon(data.carbon_reduction_kg)} avoided` : "Waiting for scenario"}
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.055] p-5">
                <div className="flex items-center justify-between">
                  <div className="grid h-10 w-10 place-items-center rounded-xl bg-amber-300/10 text-amber-300">
                    <IndianRupee />
                  </div>
                  <span className="text-xs text-white/40">estimated</span>
                </div>
                <p className="mt-5 text-3xl font-semibold tracking-tight text-white">
                  {data ? `₹${data.annual_savings_lakh}L` : "—"}
                </p>
                <p className="mt-1 text-sm text-white/45">Annual savings</p>
                <p className="mt-3 text-xs text-amber-200/70">
                  {data ? formatINR(data.annual_savings_inr) : "Waiting for scenario"}
                </p>
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-white">Five-year carbon trajectory</p>
                  <p className="text-xs text-white/40">Phased adoption of the selected interventions</p>
                </div>
                <Leaf className="h-5 w-5 text-emerald-300" />
              </div>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data?.projection ?? []} margin={{ left: -12, right: 8, top: 12 }}>
                    <defs>
                      <linearGradient id="twinScenario" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6ee7b7" stopOpacity={0.34} />
                        <stop offset="95%" stopColor="#6ee7b7" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(255,255,255,.08)" vertical={false} />
                    <XAxis dataKey="year" tick={{ fill: "rgba(255,255,255,.45)", fontSize: 11 }} tickLine={false} axisLine={false} />
                    <YAxis tickFormatter={(value) => `${Math.round(value / 1000)}k`} tick={{ fill: "rgba(255,255,255,.35)", fontSize: 10 }} tickLine={false} axisLine={false} />
                    <Tooltip formatter={(value: number) => formatCarbon(value)} contentStyle={{ background: "#10231d", border: "1px solid rgba(255,255,255,.12)", borderRadius: 12, color: "white" }} />
                    <Area type="monotone" dataKey="current_carbon_kg" name="Current path" stroke="rgba(255,255,255,.3)" fill="transparent" strokeDasharray="5 5" />
                    <Area type="monotone" dataKey="scenario_carbon_kg" name="Scenario path" stroke="#6ee7b7" strokeWidth={3} fill="url(#twinScenario)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>
        </div>

        {data && (
          <section className="mt-5 grid gap-5 lg:grid-cols-[1.25fr_.75fr]">
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/40">Impact attribution</p>
              <div className="mt-4 divide-y divide-white/10">
                {data.breakdown.map((item) => (
                  <div key={item.key} className="grid gap-3 py-4 sm:grid-cols-[1fr_auto] sm:items-center">
                    <div>
                      <p className="text-sm font-semibold text-white">{item.label}</p>
                      <p className="mt-1 max-w-xl text-xs leading-relaxed text-white/40">{item.assumption}</p>
                    </div>
                    <div className="text-left sm:text-right">
                      <p className="text-lg font-semibold text-emerald-300">−{formatCarbon(item.reduction_kg)}</p>
                      <p className="text-xs text-white/35">{item.reduction_pct_of_total}% of total</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5">
              <div className="flex items-center gap-2 text-white">
                <ShieldCheck className="h-5 w-5 text-emerald-300" />
                <p className="text-sm font-semibold">Model transparency</p>
              </div>
              <ul className="mt-4 space-y-3">
                {data.methodology.map((item) => (
                  <li key={item} className="flex gap-2 text-xs leading-relaxed text-white/45">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-300/70" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
