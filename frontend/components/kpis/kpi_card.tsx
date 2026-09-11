"use client";

import { type KPISpec, type KPIResult } from "@/lib/datasets";
import { KpiNumberCard } from "./kpi_number_card";
import { KpiBarChart } from "./kpi_bar_chart";
import { KpiLineChart } from "./kpi_line_chart";

interface KpiCardProps {
  spec: KPISpec;
  result: KPIResult;
}

export function KpiCard({ spec, result }: KpiCardProps) {
  switch (result.chart_type) {
    case "bar":
      return <KpiBarChart spec={spec} result={result} />;
    case "line":
      return <KpiLineChart spec={spec} result={result} />;
    case "number":
    default:
      return <KpiNumberCard spec={spec} result={result} />;
  }
}