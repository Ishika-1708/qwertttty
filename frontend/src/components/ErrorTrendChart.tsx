import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatCount, formatMw, formatPct } from "../utils/format";
import { AXIS_STROKE, ERROR_BAR_FILL } from "./chartStyles";
import { ChartLegend } from "./ChartLegend";
import { SignedValue } from "./SignedValue";

/** One aggregated figure, exactly as returned by the backend, with its sample count. */
export interface TrendDatum {
  key: string;
  label: string;
  value: number | null;
  sampleCount: number;
  coveragePct?: number | null;
}

/**
 * magnitude - MAE / RMSE, never negative, in MW
 * signed    - MBE / bias; bars rise above or fall below zero
 * count     - how many intervals fall in a bin (distribution)
 */
export type TrendMode = "magnitude" | "signed" | "count";

interface ErrorTrendChartProps {
  data: TrendDatum[];
  mode: TrendMode;
  /** What the bars represent, used in the legend and the accessible label. */
  seriesLabel: string;
  yLabel: string;
  xLabel?: string;
  ariaLabel: string;
}

interface TipProps {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: TrendDatum }>;
}

function makeTooltip(mode: TrendMode, seriesLabel: string) {
  return function TrendTooltip({ active, payload }: TipProps) {
    const d = active ? payload?.[0]?.payload : undefined;
    if (!d) return null;
    return (
      <div className="tip" role="tooltip">
        <div className="tip__title">{d.label}</div>
        <dl>
          <dt>{seriesLabel}</dt>
          <dd>
            {mode === "signed" ? (
              <SignedValue value={d.value} showWord />
            ) : mode === "count" ? (
              `${formatCount(d.value)} intervals`
            ) : (
              formatMw(d.value)
            )}
          </dd>
          {mode !== "count" && (
            <>
              <dt>Sample count (n)</dt>
              <dd>{formatCount(d.sampleCount)} intervals</dd>
            </>
          )}
          {d.coveragePct !== undefined && (
            <>
              <dt>Coverage</dt>
              <dd>{formatPct(d.coveragePct)}</dd>
            </>
          )}
        </dl>
      </div>
    );
  };
}

export function ErrorTrendChart({ data, mode, seriesLabel, yLabel, xLabel, ariaLabel }: ErrorTrendChartProps) {
  const Tip = useMemo(() => makeTooltip(mode, seriesLabel), [mode, seriesLabel]);
  return (
    <div>
      <div className="chart chart--mid" role="img" aria-label={ariaLabel}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 16, bottom: xLabel ? 22 : 4, left: 0 }} barCategoryGap="22%">
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="label"
              stroke={AXIS_STROKE}
              interval="preserveStartEnd"
              minTickGap={14}
              label={xLabel ? { value: xLabel, position: "insideBottom", offset: -14 } : undefined}
            />
            <YAxis
              width={64}
              stroke={AXIS_STROKE}
              tickFormatter={(v: number) => v.toLocaleString("en-GB")}
              label={{ value: yLabel, angle: -90, position: "insideLeft", offset: 12 }}
            />
            <Tooltip content={<Tip />} cursor={{ fill: "var(--wash)" }} />
            {mode === "signed" && <ReferenceLine y={0} stroke="var(--ink-2)" strokeWidth={1.5} />}
            <Bar dataKey="value" name={seriesLabel} fill={ERROR_BAR_FILL} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ChartLegend kind="bar" barLabel={seriesLabel} />
      {mode === "signed" ? (
        <p className="chart-note">
          Bars above the zero line (▲): forecasts were higher than actual generation. Bars below (▼): forecasts were lower.
          Days with no value are left blank, not drawn as zero.
        </p>
      ) : (
        <p className="chart-note">Intervals with no value are left blank, not drawn as zero.</p>
      )}
    </div>
  );
}
