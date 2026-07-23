import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import "./Dashboard.css";

const WINDOWS = [
  { value: "15m", label: "15 min" },
  { value: "1h", label: "1 hour" },
  { value: "6h", label: "6 hours" },
  { value: "24h", label: "24 hours" },
];

const COLOR = {
  seriesBlue: "#3987e5",
  seriesOrange: "#d95926",
  statusCritical: "#e66767",
  gridline: "#262a33",
  axis: "#3a3f4b",
  textPrimary: "#e6e6e6",
  textSecondary: "#c7c9cf",
  textMuted: "#7d8190",
};

const CHART_W = 800;
const CHART_H = 220;
const PAD = { top: 16, right: 16, bottom: 28, left: 40 };

function formatBucketLabel(iso) {
  const d = new Date(iso + "Z");
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function scaleY(value, maxValue) {
  const usable = CHART_H - PAD.top - PAD.bottom;
  if (maxValue <= 0) return CHART_H - PAD.bottom;
  return CHART_H - PAD.bottom - (value / maxValue) * usable;
}

function slotX(index, count) {
  const usable = CHART_W - PAD.left - PAD.right;
  const slotWidth = usable / Math.max(count, 1);
  return PAD.left + index * slotWidth + slotWidth / 2;
}

function slotWidthOf(count) {
  const usable = CHART_W - PAD.left - PAD.right;
  return usable / Math.max(count, 1);
}

function niceMax(value) {
  if (value <= 0) return 1;
  const magnitude = Math.pow(10, Math.floor(Math.log10(value)));
  const normalized = value / magnitude;
  const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return step * magnitude;
}

function GridAndAxis({ maxValue, formatTick }) {
  const ticks = [0, 0.5, 1].map((f) => f * maxValue);
  return (
    <g>
      {ticks.map((tick, i) => {
        const y = scaleY(tick, maxValue);
        return (
          <g key={i}>
            <line x1={PAD.left} x2={CHART_W - PAD.right} y1={y} y2={y} stroke={COLOR.gridline} strokeWidth={1} />
            <text x={PAD.left - 8} y={y + 4} fill={COLOR.textMuted} fontSize="11" textAnchor="end">
              {formatTick(tick)}
            </text>
          </g>
        );
      })}
      <line
        x1={PAD.left}
        x2={PAD.left}
        y1={PAD.top}
        y2={CHART_H - PAD.bottom}
        stroke={COLOR.axis}
        strokeWidth={1}
      />
      <line
        x1={PAD.left}
        x2={CHART_W - PAD.right}
        y1={CHART_H - PAD.bottom}
        y2={CHART_H - PAD.bottom}
        stroke={COLOR.axis}
        strokeWidth={1}
      />
    </g>
  );
}

function HoverLayer({ buckets, onHover, count }) {
  const slotW = slotWidthOf(count);
  return (
    <>
      {buckets.map((b, i) => (
        <rect
          key={i}
          x={PAD.left + i * slotW}
          y={PAD.top}
          width={slotW}
          height={CHART_H - PAD.top - PAD.bottom}
          fill="transparent"
          onMouseEnter={(e) => onHover({ index: i, clientX: e.clientX, clientY: e.clientY })}
          onMouseMove={(e) => onHover({ index: i, clientX: e.clientX, clientY: e.clientY })}
          onMouseLeave={() => onHover(null)}
        />
      ))}
    </>
  );
}

function Tooltip({ hover, children }) {
  if (!hover) return null;
  return (
    <div
      className="chart-tooltip"
      style={{ left: hover.clientX + 14, top: hover.clientY + 14 }}
    >
      {children}
    </div>
  );
}

function ThroughputChart({ data }) {
  const [hover, setHover] = useState(null);
  const maxValue = niceMax(Math.max(1, ...data.map((d) => d.requests)));
  const slotW = slotWidthOf(data.length);
  const barW = Math.max(slotW * 0.55, 2);

  return (
    <div className="chart-card">
      <div className="chart-title">Throughput</div>
      <div className="chart-subtitle">Requests per bucket</div>
      <svg viewBox={`0 0 ${CHART_W} ${CHART_H}`} className="chart-svg">
        <GridAndAxis maxValue={maxValue} formatTick={(v) => Math.round(v)} />
        {data.map((d, i) => {
          const x = slotX(i, data.length) - barW / 2;
          const y = scaleY(d.requests, maxValue);
          const h = CHART_H - PAD.bottom - y;
          return (
            <rect
              key={i}
              x={x}
              y={y}
              width={barW}
              height={Math.max(h, 0)}
              rx={2}
              fill={COLOR.seriesBlue}
              opacity={hover?.index === i ? 1 : 0.85}
            />
          );
        })}
        <HoverLayer buckets={data} count={data.length} onHover={setHover} />
      </svg>
      <Tooltip hover={hover}>
        {hover && (
          <>
            <div className="tooltip-label">{formatBucketLabel(data[hover.index].bucket)}</div>
            <div>{data[hover.index].requests} requests</div>
          </>
        )}
      </Tooltip>
    </div>
  );
}

function LatencyChart({ data }) {
  const [hover, setHover] = useState(null);
  const maxValue = niceMax(
    Math.max(1, ...data.map((d) => Math.max(d.avg_latency_ms || 0, d.p95_latency_ms || 0)))
  );

  function linePath(key) {
    return data
      .map((d, i) => `${i === 0 ? "M" : "L"} ${slotX(i, data.length)} ${scaleY(d[key] || 0, maxValue)}`)
      .join(" ");
  }

  return (
    <div className="chart-card">
      <div className="chart-title">Latency</div>
      <div className="chart-subtitle">Average vs p95, milliseconds</div>
      <div className="chart-legend">
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: COLOR.seriesBlue }} /> avg
        </span>
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: COLOR.seriesOrange }} /> p95
        </span>
      </div>
      <svg viewBox={`0 0 ${CHART_W} ${CHART_H}`} className="chart-svg">
        <GridAndAxis maxValue={maxValue} formatTick={(v) => `${Math.round(v)}ms`} />
        <path d={linePath("avg_latency_ms")} fill="none" stroke={COLOR.seriesBlue} strokeWidth={2} />
        <path d={linePath("p95_latency_ms")} fill="none" stroke={COLOR.seriesOrange} strokeWidth={2} />
        {hover && (
          <line
            x1={slotX(hover.index, data.length)}
            x2={slotX(hover.index, data.length)}
            y1={PAD.top}
            y2={CHART_H - PAD.bottom}
            stroke={COLOR.textMuted}
            strokeWidth={1}
            strokeDasharray="3,3"
          />
        )}
        <HoverLayer buckets={data} count={data.length} onHover={setHover} />
      </svg>
      <Tooltip hover={hover}>
        {hover && (
          <>
            <div className="tooltip-label">{formatBucketLabel(data[hover.index].bucket)}</div>
            <div>avg {Math.round(data[hover.index].avg_latency_ms || 0)}ms</div>
            <div>p95 {Math.round(data[hover.index].p95_latency_ms || 0)}ms</div>
          </>
        )}
      </Tooltip>
    </div>
  );
}

function ErrorsChart({ data }) {
  const [hover, setHover] = useState(null);
  const maxValue = niceMax(Math.max(1, ...data.map((d) => d.errors)));
  const slotW = slotWidthOf(data.length);
  const barW = Math.max(slotW * 0.55, 2);
  const hasErrors = data.some((d) => d.errors > 0);

  return (
    <div className="chart-card">
      <div className="chart-title">
        <span className="status-dot critical" /> Errors
      </div>
      <div className="chart-subtitle">Failed inference calls per bucket</div>
      <svg viewBox={`0 0 ${CHART_W} ${CHART_H}`} className="chart-svg">
        <GridAndAxis maxValue={maxValue} formatTick={(v) => Math.round(v)} />
        {data.map((d, i) => {
          const x = slotX(i, data.length) - barW / 2;
          const y = scaleY(d.errors, maxValue);
          const h = CHART_H - PAD.bottom - y;
          return (
            <rect
              key={i}
              x={x}
              y={y}
              width={barW}
              height={Math.max(h, 0)}
              rx={2}
              fill={COLOR.statusCritical}
              opacity={hover?.index === i ? 1 : 0.85}
            />
          );
        })}
        <HoverLayer buckets={data} count={data.length} onHover={setHover} />
      </svg>
      {!hasErrors && <div className="chart-empty-note">No errors in this window.</div>}
      <Tooltip hover={hover}>
        {hover && (
          <>
            <div className="tooltip-label">{formatBucketLabel(data[hover.index].bucket)}</div>
            <div>{data[hover.index].errors} errors</div>
          </>
        )}
      </Tooltip>
    </div>
  );
}

function StatTile({ label, value, tone }) {
  return (
    <div className="stat-tile">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${tone || ""}`}>{value}</div>
    </div>
  );
}

export default function Dashboard() {
  const [window_, setWindow] = useState("1h");
  const [summary, setSummary] = useState(null);
  const [timeseries, setTimeseries] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([api.getMetricsSummary(window_), api.getMetricsTimeseries(window_)])
      .then(([s, t]) => {
        if (cancelled) return;
        setSummary(s);
        setTimeseries(t);
      })
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false));

    const interval = setInterval(() => {
      Promise.all([api.getMetricsSummary(window_), api.getMetricsTimeseries(window_)])
        .then(([s, t]) => {
          if (cancelled) return;
          setSummary(s);
          setTimeseries(t);
        })
        .catch(() => {});
    }, 15000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [window_]);

  const errorRatePct = useMemo(
    () => (summary ? `${(summary.error_rate * 100).toFixed(1)}%` : "—"),
    [summary]
  );

  return (
    <div className="dashboard thin-scroll">
      <div className="dashboard-header">
        <h2>Inference metrics</h2>
        <div className="window-select">
          {WINDOWS.map((w) => (
            <button
              key={w.value}
              className={`window-btn ${window_ === w.value ? "active" : ""}`}
              onClick={() => setWindow(w.value)}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {!error && summary && (
        <div className="stat-tiles">
          <StatTile label="Total requests" value={summary.total_requests} />
          <StatTile
            label="Error rate"
            value={errorRatePct}
            tone={summary.error_rate > 0.05 ? "critical" : undefined}
          />
          <StatTile label="Avg latency" value={summary.avg_latency_ms ? `${Math.round(summary.avg_latency_ms)}ms` : "—"} />
          <StatTile label="P95 latency" value={summary.p95_latency_ms ? `${Math.round(summary.p95_latency_ms)}ms` : "—"} />
          <StatTile label="Total tokens" value={summary.total_tokens.toLocaleString()} />
        </div>
      )}

      {!error && !loading && timeseries.length === 0 && (
        <div className="chart-empty-note">
          No inference logs in this window yet — send a few chat messages first.
        </div>
      )}

      {!error && timeseries.length > 0 && (
        <div className="chart-grid">
          <ThroughputChart data={timeseries} />
          <LatencyChart data={timeseries} />
          <ErrorsChart data={timeseries} />
        </div>
      )}
    </div>
  );
}
