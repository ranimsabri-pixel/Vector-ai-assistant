"use client";

import { AlertTriangle, Loader2 } from "lucide-react";

import {
  isWidgetError,
  type BarLineData,
  type CorrelationMatrixData,
  type DashboardWidget,
  type DataTableData,
  type HeatmapData,
  type HistogramData,
  type KpiData,
  type PieData,
  type RadarData,
  type ScatterData,
  type WidgetData,
} from "@/lib/dashboards";
import { KpiWidget } from "@/components/widgets/kpi_widget";
import { BarLineChartWidget } from "@/components/widgets/bar_line_chart_widget";
import { PieChartWidget } from "@/components/widgets/pie_chart_widget";
import { DataTableWidget } from "@/components/widgets/data_table_widget";
import { RadarChartWidget } from "@/components/widgets/radar_chart_widget";
import { ScatterPlotWidget } from "@/components/widgets/scatter_plot_widget";
import { HeatmapWidget } from "@/components/widgets/heatmap_widget";
import { CorrelationMatrixWidget } from "@/components/widgets/correlation_matrix_widget";
import { HistogramWidget } from "@/components/widgets/histogram_widget";

export function WidgetRenderer({
  widget,
  data,
}: {
  widget: DashboardWidget;
  data: WidgetData | undefined;
}) {
  if (data === undefined) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground">
        <Loader2 size={20} className="animate-spin" />
      </div>
    );
  }

  if (isWidgetError(data)) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-2 text-center px-4">
        <AlertTriangle size={18} className="text-amber-500" />
        <p className="text-xs text-muted-foreground">{data.error}</p>
      </div>
    );
  }

  switch (widget.widget_type) {
    case "kpi":
      return <KpiWidget data={data as KpiData} />;
    case "bar_chart":
      return <BarLineChartWidget data={data as BarLineData} kind="bar_chart" />;
    case "line_chart":
      return <BarLineChartWidget data={data as BarLineData} kind="line_chart" />;
    case "pie_chart":
      return <PieChartWidget data={data as PieData} donut={false} />;
    case "donut_chart":
      return <PieChartWidget data={data as PieData} donut={true} />;
    case "data_table":
      return <DataTableWidget data={data as DataTableData} />;
    case "radar_chart":
      return <RadarChartWidget data={data as RadarData} />;
    case "scatter_plot":
      return <ScatterPlotWidget data={data as ScatterData} />;
    case "heatmap":
      return <HeatmapWidget data={data as HeatmapData} />;
    case "correlation_matrix":
      return <CorrelationMatrixWidget data={data as CorrelationMatrixData} />;
    case "histogram":
      return <HistogramWidget data={data as HistogramData} />;
    default:
      return (
        <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
          Type de widget non supporté
        </div>
      );
  }
}

// Widgets qui occupent 2 colonnes dans la grille (contenu plus large)
export function isWideWidget(widgetType: DashboardWidget["widget_type"]): boolean {
  return ["data_table", "heatmap", "correlation_matrix"].includes(widgetType);
}
