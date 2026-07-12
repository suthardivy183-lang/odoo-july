import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Coins,
  TrendingUp,
  Leaf,
  DollarSign,
  Target,
  BarChart4,
  Activity,
  Download,
  Plus,
  AlertTriangle,
} from "lucide-react";
import { useState, useEffect } from "react";
import { toast } from "sonner";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

import { PageHeader } from "@/components/app/page-header";
import { StatCard } from "@/components/app/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, getToken } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function CarbonAccountingPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState("dashboard");

  // Dialog states
  const [pricingOpen, setPricingOpen] = useState(false);
  const [budgetOpen, setBudgetOpen] = useState(false);

  // Form states
  const [pricePerTon, setPricePerTon] = useState("");
  const [currency, setCurrency] = useState("INR");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [pricingMethod, setPricingMethod] = useState("fixed_internal");

  const [budgetDept, setBudgetDept] = useState("");
  const [budgetFiscalYear, setBudgetFiscalYear] = useState("2026-2027");
  const [budgetPeriodType, setBudgetPeriodType] = useState("annual");
  const [budgetPeriodValue, setBudgetPeriodValue] = useState("");
  const [budgetedTons, setBudgetedTons] = useState("");
  const [budgetStartDate, setBudgetStartDate] = useState("");
  const [budgetEndDate, setBudgetEndDate] = useState("");

  // Report states
  const [reportType, setReportType] = useState("monthly_cost");
  const [reportFormat, setReportFormat] = useState("pdf");

  // Simulation states
  const [dieselReduction, setDieselReduction] = useState(0);
  const [fleetEv, setFleetEv] = useState(0);
  const [solarReplacement, setSolarReplacement] = useState(0);

  // Queries
  const { data: dashboard, isLoading: dashboardLoading } = useQuery({
    queryKey: ["carbon-dashboard"],
    queryFn: () => api.get<any>("/carbon/accounting/dashboard"),
  });

  const { data: pricingRules, isLoading: pricingLoading } = useQuery({
    queryKey: ["pricing-rules"],
    queryFn: () => api.get<any>("/carbon/pricing-rules"),
  });

  const { data: budgets, isLoading: budgetsLoading } = useQuery({
    queryKey: ["carbon-budgets"],
    queryFn: () => api.get<any>("/carbon/budgets"),
  });

  const { data: departments } = useQuery({
    queryKey: ["departments-list"],
    queryFn: () => api.get<any>("/departments"),
  });

  const { data: simulation, mutate: runSimulation } = useMutation({
    mutationKey: ["simulate-scenarios"],
    mutationFn: (body: any) => api.post<any>("/carbon/accounting/simulate", body),
  });

  // Run initial simulation
  useEffect(() => {
    runSimulation({
      diesel_reduction_pct: dieselReduction,
      fleet_ev_pct: fleetEv,
      solar_replacement_pct: solarReplacement,
    });
  }, [dieselReduction, fleetEv, solarReplacement]);

  // Mutations
  const createPricing = useMutation({
    mutationFn: (body: any) => api.post("/carbon/pricing-rules", body),
    onSuccess: () => {
      toast.success("Pricing rule configured successfully!");
      setPricingOpen(false);
      void qc.invalidateQueries({ queryKey: ["pricing-rules"] });
      void qc.invalidateQueries({ queryKey: ["carbon-dashboard"] });
    },
    onError: (e) => toast.error(e.message),
  });

  const activatePricing = useMutation({
    mutationFn: (id: number) => api.patch(`/carbon/pricing-rules/${id}/activate`),
    onSuccess: () => {
      toast.success("Pricing rule activated!");
      void qc.invalidateQueries({ queryKey: ["pricing-rules"] });
      void qc.invalidateQueries({ queryKey: ["carbon-dashboard"] });
    },
    onError: (e) => toast.error(e.message),
  });

  const createBudget = useMutation({
    mutationFn: (body: any) => api.post("/carbon/budgets", body),
    onSuccess: () => {
      toast.success("Carbon budget configured successfully!");
      setBudgetOpen(false);
      void qc.invalidateQueries({ queryKey: ["carbon-budgets"] });
    },
    onError: (e) => toast.error(e.message),
  });

  const handleDownload = async () => {
    try {
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) headers.Authorization = `Bearer ${token}`;
      const response = await fetch(
        `/api/v1/carbon/accounting/reports?report_type=${reportType}&file_format=${reportFormat}`,
        { headers }
      );
      if (!response.ok) throw new Error("Download failed");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${reportType}.${reportFormat === "excel" ? "xlsx" : reportFormat}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      toast.success("Report downloaded successfully!");
    } catch (e) {
      toast.error("Failed to download report");
    }
  };

  const handleCreatePricing = (e: React.FormEvent) => {
    e.preventDefault();
    createPricing.mutate({
      price_per_ton: parseFloat(pricePerTon),
      currency,
      effective_date: effectiveDate,
      pricing_method: pricingMethod,
      is_active: true,
    });
  };

  const handleCreateBudget = (e: React.FormEvent) => {
    e.preventDefault();
    createBudget.mutate({
      department_id: parseInt(budgetDept),
      fiscal_year: budgetFiscalYear,
      period_type: budgetPeriodType,
      period_value: budgetPeriodType === "quarterly" ? budgetPeriodValue : null,
      budgeted_co2e_tons: parseFloat(budgetedTons),
      start_date: budgetStartDate,
      end_date: budgetEndDate,
    });
  };

  const getFormatLabel = (method: string) => {
    if (method === "fixed_internal") return "Fixed Internal Price";
    if (method === "govt_tax") return "Government Carbon Tax";
    return "Market Carbon Credit Price";
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Carbon Cost Accounting"
        description="Convert greenhouse gas emissions into financial environmental liabilities and monitor budgets."
      />

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="dashboard">Financial Dashboard</TabsTrigger>
          <TabsTrigger value="pricing">Carbon Pricing Configuration</TabsTrigger>
          <TabsTrigger value="budgets">Department Budgets</TabsTrigger>
          <TabsTrigger value="simulation">Scenario Simulator</TabsTrigger>
          <TabsTrigger value="reports">Download Financial Reports</TabsTrigger>
        </TabsList>

        {/* DASHBOARD TAB */}
        <TabsContent value="dashboard" className="space-y-4">
          {dashboardLoading || !dashboard ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-24" />
              ))}
            </div>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard
                  label="Total Carbon Liability"
                  value={`₹${dashboard.total_liability.toLocaleString()}`}
                  icon={Coins}
                  hint="Calculated in real-time"
                  tone="danger"
                />
                <StatCard
                  label="Total Emitted Carbon"
                  value={`${dashboard.total_emissions_tons} Tons`}
                  icon={Leaf}
                  hint="Calculated in real-time"
                />
                <StatCard
                  label="Cost Per Employee"
                  value={`₹${dashboard.cost_per_employee.toLocaleString()}`}
                  icon={DollarSign}
                  tone="warning"
                />
                <StatCard
                  label="Cost Per Product"
                  value={`₹${dashboard.cost_per_product.toLocaleString()}`}
                  icon={Target}
                  tone="success"
                />
              </div>

              <div className="grid gap-4 lg:grid-cols-5">
                <Card className="lg:col-span-3">
                  <CardHeader>
                    <CardTitle>Monthly Carbon Cost Trend (₹)</CardTitle>
                  </CardHeader>
                  <CardContent className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={dashboard.monthly_trend}>
                        <defs>
                          <linearGradient id="colorLiability" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#dc2626" stopOpacity={0.2} />
                            <stop offset="95%" stopColor="#dc2626" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
                        <XAxis dataKey="month" fontSize={11} />
                        <YAxis fontSize={11} />
                        <Tooltip />
                        <Area
                          type="monotone"
                          dataKey="liability"
                          name="Liability (₹)"
                          stroke="#dc2626"
                          fillOpacity={1}
                          fill="url(#colorLiability)"
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                <Card className="lg:col-span-2">
                  <CardHeader>
                    <CardTitle>Top Emission Sources</CardTitle>
                  </CardHeader>
                  <CardContent className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={dashboard.top_emission_sources} layout="vertical">
                        <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
                        <XAxis type="number" fontSize={11} />
                        <YAxis dataKey="source" type="category" width={80} fontSize={11} />
                        <Tooltip />
                        <Bar dataKey="emissions_tons" name="Emissions (Tons)" fill="#16a34a" radius={[0, 3, 3, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Highest Cost Departments</CardTitle>
                </CardHeader>
                <CardContent className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dashboard.highest_cost_departments}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
                      <XAxis dataKey="name" fontSize={11} />
                      <YAxis fontSize={11} />
                      <Tooltip />
                      <Bar dataKey="liability" name="Liability (₹)" fill="#dc2626" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* PRICING TAB */}
        <TabsContent value="pricing" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Carbon Pricing Version History</CardTitle>
                <p className="text-sm text-muted-foreground">
                  View and manage carbon pricing rules. Only one pricing rule can be active at a time.
                </p>
              </div>
              {(user?.role === "admin" || user?.role === "esg_manager") && (
                <Button onClick={() => setPricingOpen(true)} className="flex items-center gap-1.5">
                  <Plus className="h-4 w-4" /> Configure Carbon Price
                </Button>
              )}
            </CardHeader>
            <CardContent>
              {pricingLoading || !pricingRules ? (
                <Skeleton className="h-40 w-full" />
              ) : (
                <div className="relative w-full overflow-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50 font-medium">
                        <th className="p-3">Version</th>
                        <th className="p-3">Pricing Method</th>
                        <th className="p-3">Price Per Ton</th>
                        <th className="p-3">Effective Date</th>
                        <th className="p-3">Status</th>
                        <th className="p-3">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pricingRules.items.map((rule: any) => (
                        <tr key={rule.id} className="border-b transition-colors hover:bg-muted/50">
                          <td className="p-3 font-semibold">v{rule.version}</td>
                          <td className="p-3">{getFormatLabel(rule.pricing_method)}</td>
                          <td className="p-3">
                            {rule.currency} {rule.price_per_ton.toLocaleString()}
                          </td>
                          <td className="p-3">{new Date(rule.effective_date).toLocaleDateString()}</td>
                          <td className="p-3">
                            {rule.is_active ? (
                              <Badge className="bg-emerald-600 hover:bg-emerald-600">Active</Badge>
                            ) : (
                              <Badge variant="secondary">Inactive</Badge>
                            )}
                          </td>
                          <td className="p-3">
                            {!rule.is_active && (user?.role === "admin" || user?.role === "esg_manager") && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => activatePricing.mutate(rule.id)}
                              >
                                Activate
                              </Button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* BUDGETS TAB */}
        <TabsContent value="budgets" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Department Carbon Budgets</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Track actual department emissions and estimated liabilities against budgeted tons.
                </p>
              </div>
              {user?.role === "admin" && (
                <Button onClick={() => setBudgetOpen(true)} className="flex items-center gap-1.5">
                  <Plus className="h-4 w-4" /> Define Budget
                </Button>
              )}
            </CardHeader>
            <CardContent>
              {budgetsLoading || !budgets ? (
                <Skeleton className="h-40 w-full" />
              ) : (
                <div className="relative w-full overflow-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50 font-medium">
                        <th className="p-3">Department</th>
                        <th className="p-3">Fiscal Year</th>
                        <th className="p-3">Period</th>
                        <th className="p-3">Budget</th>
                        <th className="p-3">Actual Emissions</th>
                        <th className="p-3">Utilization</th>
                        <th className="p-3">Estimated Liability</th>
                      </tr>
                    </thead>
                    <tbody>
                      {budgets.items.map((b: any) => {
                        const isOver = b.budget_utilization_pct > 100;
                        return (
                          <tr key={b.id} className="border-b transition-colors hover:bg-muted/50">
                            <td className="p-3 font-semibold">{b.department_name}</td>
                            <td className="p-3">{b.fiscal_year}</td>
                            <td className="p-3 font-medium">
                              {b.period_type === "annual" ? (
                                <Badge variant="outline">Annual</Badge>
                              ) : (
                                <Badge variant="secondary" className="bg-sky-500/10 text-sky-600 hover:bg-sky-500/10">
                                  {b.period_value}
                                </Badge>
                              )}
                            </td>
                            <td className="p-3">{b.budgeted_co2e_tons} Tons</td>
                            <td className="p-3">{b.actual_co2e_tons.toFixed(2)} Tons</td>
                            <td className="p-3 min-w-44">
                              <div className="flex items-center gap-2">
                                <Progress value={Math.min(b.budget_utilization_pct, 100)} className="h-2 w-28" />
                                <span className={isOver ? "font-bold text-red-600" : "font-medium text-muted-foreground"}>
                                  {b.budget_utilization_pct}%
                                </span>
                                {isOver && <AlertTriangle className="h-4 w-4 text-red-600" />}
                              </div>
                            </td>
                            <td className="p-3 font-semibold text-red-600">
                              ₹{b.estimated_liability.toLocaleString()}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* SIMULATION TAB */}
        <TabsContent value="simulation" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-5">
            <Card className="md:col-span-2">
              <CardHeader>
                <CardTitle>Simulation Inputs</CardTitle>
                <p className="text-sm text-muted-foreground">Adjust operational decisions to preview financial impact.</p>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="font-semibold">Decrease Diesel Usage</Label>
                    <span className="text-sm font-bold text-primary">{dieselReduction}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={dieselReduction}
                    onChange={(e) => setDieselReduction(parseInt(e.target.value))}
                    className="w-full accent-primary"
                  />
                  <p className="text-xs text-muted-foreground">Applies reduction to stationary & heating diesel.</p>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="font-semibold">Fleet Electrification (EV %)</Label>
                    <span className="text-sm font-bold text-primary">{fleetEv}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={fleetEv}
                    onChange={(e) => setFleetEv(parseInt(e.target.value))}
                    className="w-full accent-primary"
                  />
                  <p className="text-xs text-muted-foreground">Assumes EVs reduce target vehicle emissions by 85%.</p>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="font-semibold">Replace Grid with Solar Energy</Label>
                    <span className="text-sm font-bold text-primary">{solarReplacement}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={solarReplacement}
                    onChange={(e) => setSolarReplacement(parseInt(e.target.value))}
                    className="w-full accent-primary"
                  />
                  <p className="text-xs text-muted-foreground">Applies clean offset to Scope 2 grid electricity.</p>
                </div>
              </CardContent>
            </Card>

            <Card className="md:col-span-3">
              <CardHeader>
                <CardTitle>Estimated Financial & ESG Savings</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {!simulation ? (
                  <Skeleton className="h-40 w-full" />
                ) : (
                  <>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="rounded-xl border bg-emerald-500/5 p-4 flex items-center gap-3">
                        <div className="h-10 w-10 shrink-0 flex items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600">
                          <Leaf className="h-5 w-5" />
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground uppercase font-bold">Carbon Reduction</p>
                          <p className="text-lg font-bold">{simulation.carbon_reduction_tons} Tons</p>
                          <p className="text-xs font-semibold text-emerald-600">-{simulation.carbon_reduction_pct}% of baseline</p>
                        </div>
                      </div>

                      <div className="rounded-xl border bg-primary/5 p-4 flex items-center gap-3">
                        <div className="h-10 w-10 shrink-0 flex items-center justify-center rounded-lg bg-primary/10 text-primary">
                          <Coins className="h-5 w-5" />
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground uppercase font-bold">Financial Savings</p>
                          <p className="text-lg font-bold">₹{simulation.financial_savings.toLocaleString()}</p>
                          <p className="text-xs font-semibold text-primary">Direct liability reduction</p>
                        </div>
                      </div>

                      <div className="rounded-xl border bg-sky-500/5 p-4 flex items-center gap-3">
                        <div className="h-10 w-10 shrink-0 flex items-center justify-center rounded-lg bg-sky-500/10 text-sky-600">
                          <TrendingUp className="h-5 w-5" />
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground uppercase font-bold">ESG Score Improvement</p>
                          <p className="text-lg font-bold">+{simulation.esg_score_improvement} Points</p>
                          <p className="text-xs font-semibold text-sky-600">Estimated environmental pillar shift</p>
                        </div>
                      </div>

                      <div className="rounded-xl border bg-red-500/5 p-4 flex items-center gap-3">
                        <div className="h-10 w-10 shrink-0 flex items-center justify-center rounded-lg bg-red-500/10 text-red-600">
                          <Activity className="h-5 w-5" />
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground uppercase font-bold">New Liability Projection</p>
                          <p className="text-lg font-bold">₹{simulation.new_carbon_liability.toLocaleString()}</p>
                          <p className="text-xs font-semibold text-red-600">Remaining liability</p>
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* REPORTS TAB */}
        <TabsContent value="reports" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Download Carbon Liability & Financial Exposure Reports</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6 max-w-md">
              <div className="space-y-2">
                <Label>Select Report Type</Label>
                <Select value={reportType} onChange={(e) => setReportType(e.target.value)}>
                  <option value="monthly_cost">Monthly Carbon Cost Report</option>
                  <option value="department_liability">Department Carbon Liability Report</option>
                  <option value="budget_utilization">Carbon Budget Utilization Report</option>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Select Export Format</Label>
                <Select value={reportFormat} onChange={(e) => setReportFormat(e.target.value)}>
                  <option value="pdf">Adobe PDF (.pdf)</option>
                  <option value="excel">Microsoft Excel (.xlsx)</option>
                  <option value="csv">Comma Separated Values (.csv)</option>
                </Select>
              </div>

              <Button onClick={handleDownload} className="flex items-center gap-2">
                <Download className="h-4 w-4" /> Download Report
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Pricing Rule Config Dialog */}
      <Dialog open={pricingOpen} onOpenChange={setPricingOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Configure Carbon Price</DialogTitle>
            <DialogDescription>Define carbon pricing metric for calculating financial liability.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreatePricing} className="space-y-4 pt-2">
            <div className="space-y-2">
              <Label>Price Per Ton (INR)</Label>
              <Input
                type="number"
                step="0.01"
                placeholder="e.g. 3500.00"
                value={pricePerTon}
                onChange={(e) => setPricePerTon(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <Label>Currency</Label>
              <Input value={currency} onChange={(e) => setCurrency(e.target.value)} required />
            </div>

            <div className="space-y-2">
              <Label>Effective Date</Label>
              <Input type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} required />
            </div>

            <div className="space-y-2">
              <Label>Pricing Method</Label>
              <Select value={pricingMethod} onChange={(e) => setPricingMethod(e.target.value)}>
                <option value="fixed_internal">Fixed Internal Price</option>
                <option value="govt_tax">Government Carbon Tax</option>
                <option value="market_credit">Market Carbon Credit Price</option>
              </Select>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setPricingOpen(false)}>
                Cancel
              </Button>
              <Button type="submit">Configure & Activate</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Budget Config Dialog */}
      <Dialog open={budgetOpen} onOpenChange={setBudgetOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Configure Department Carbon Budget</DialogTitle>
            <DialogDescription>Define budgeted carbon tons for the department.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreateBudget} className="space-y-4 pt-2">
            <div className="space-y-2">
              <Label>Select Department</Label>
              <Select value={budgetDept} onChange={(e) => setBudgetDept(e.target.value)} required>
                <option value="">-- Choose Department --</option>
                {departments?.items?.map((d: any) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>Fiscal Year</Label>
                <Input
                  placeholder="e.g. 2026-2027"
                  value={budgetFiscalYear}
                  onChange={(e) => setBudgetFiscalYear(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label>Budget Type</Label>
                <Select value={budgetPeriodType} onChange={(e) => setBudgetPeriodType(e.target.value)}>
                  <option value="annual">Annual</option>
                  <option value="quarterly">Quarterly</option>
                </Select>
              </div>
            </div>

            {budgetPeriodType === "quarterly" && (
              <div className="space-y-2">
                <Label>Select Quarter</Label>
                <Select value={budgetPeriodValue} onChange={(e) => setBudgetPeriodValue(e.target.value)} required>
                  <option value="">-- Choose Quarter --</option>
                  <option value="Q1">Q1 (Apr - Jun)</option>
                  <option value="Q2">Q2 (Jul - Sep)</option>
                  <option value="Q3">Q3 (Oct - Dec)</option>
                  <option value="Q4">Q4 (Jan - Mar)</option>
                </Select>
              </div>
            )}

            <div className="space-y-2">
              <Label>Budgeted CO₂ Limit (Tons)</Label>
              <Input
                type="number"
                step="0.01"
                placeholder="e.g. 100.0"
                value={budgetedTons}
                onChange={(e) => setBudgetedTons(e.target.value)}
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>Start Date</Label>
                <Input
                  type="date"
                  value={budgetStartDate}
                  onChange={(e) => setBudgetStartDate(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label>End Date</Label>
                <Input
                  type="date"
                  value={budgetEndDate}
                  onChange={(e) => setBudgetEndDate(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setBudgetOpen(false)}>
                Cancel
              </Button>
              <Button type="submit">Define Budget</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
