import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { IntervalRecord } from "../types";
import { formatDateTime, formatMw, formatTick } from "../utils/format";
import { AXIS_STROKE, SERIES, activeIndexFromState } from "./chartStyles";
import { ChartLegend } from "./ChartLegend";
import { SignedValue } from "./SignedValue";

interface ChartPoint {
  /** Delivery time as epoch ms (numeric axis, so 46/48/50-interval days all plot correctly). */
  t: number;
  forecast_mw: number | null;
  actual_mw: number | null;
  record: IntervalRecord;
}

interface ForecastActualChartProps {
  intervals: IntervalRecord[];
  size?: "tall" | "compact";
  /** Called when the user clicks a point on the chart. */
  onSelect?: (record: IntervalRecord) => void;
  ariaLabel: string;
}

interface TipProps {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: ChartPoint }>;
}

function ForecastTooltip({ active, payload }: TipProps) {
  const point = active ? payload?.[0]?.payload : undefined;
  if (!point) return null;
  const r = point.record;
  return (
    <div className="tip" role="tooltip">
      <div className="tip__title">{formatDateTime(r.delivery_time)}</div>
      <dl>
        <dt>Forecast</dt>
        <dd>{formatMw(r.forecast_mw)}</dd>
        <dt>Actual</dt>
        <dd>{formatMw(r.actual_mw)}</dd>
        <dt>Error (forecast − actual)</dt>
        <dd>
          <SignedValue value={r.error_mw} showWord />
        </dd>
        <dt>Forecast published</dt>
        <dd>{formatDateTime(r.forecast_published_at)}</dd>
      </dl>
    </div>
  );
}

export function ForecastActualChart({ intervals, size = "tall", onSelect, ariaLabel }: ForecastActualChartProps) {
  const data = useMemo<ChartPoint[]>(
    () =>
      intervals
        .map((r) => ({ t: new Date(r.delivery_time).getTime(), forecast_mw: r.forecast_mw, actual_mw: r.actual_mw, record: r }))
        .filter((p) => Number.isFinite(p.t))
        .sort((a, b) => a.t - b.t),
    [intervals],
  );

  const compact = size === "compact";

  return (
    <div>
      <div className={`chart chart--${compact ? "compact" : "tall"}`} role="img" aria-label={ariaLabel}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 8, right: 16, bottom: 4, left: 0 }}
            onClick={(state: unknown) => {
              const i = activeIndexFromState(state);
              const p = i === null ? undefined : data[i];
              if (p && onSelect) onSelect(p.record);
            }}
          >
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              scale="time"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(v: number) => formatTick(v)}
              tickCount={compact ? 5 : 9}
              stroke={AXIS_STROKE}
              minTickGap={24}
            />
            <YAxis
              width={64}
              stroke={AXIS_STROKE}
              domain={[0, "auto"]}
              tickFormatter={(v: number) => v.toLocaleString("en-GB")}
              label={compact ? undefined : { value: "MW", angle: -90, position: "insideLeft", offset: 12 }}
            />
            <Tooltip content={<ForecastTooltip />} cursor={{ stroke: AXIS_STROKE }} />
            <Line
              type="monotone"
              dataKey={SERIES.forecast.key}
              name={SERIES.forecast.name}
              stroke={SERIES.forecast.stroke}
              strokeWidth={SERIES.forecast.strokeWidth}
              dot={false}
              activeDot={{ r: 5 }}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey={SERIES.actual.key}
              name={SERIES.actual.name}
              stroke={SERIES.actual.stroke}
              strokeWidth={SERIES.actual.strokeWidth}
              strokeDasharray={SERIES.actual.dash}
              dot={false}
              activeDot={{ r: 5 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <ChartLegend kind="forecast-actual" />
      <p className="chart-note">
        Gaps in a line are intervals where that value is unavailable - they are not zero. Times are shown in UK time.
        {onSelect ? " Click the chart or a table row to open an interval." : ""}
      </p>
    </div>
  );
}
