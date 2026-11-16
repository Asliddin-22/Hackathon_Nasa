import {ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine} from 'recharts';
import type {HealthRecord} from '../services/api';
import {day, labels} from '../services/api';

// Cumulative daily metrics are summarised by their daily total, others by mean.
const DAILY_TOTAL = new Set(['steps']);
const ORIGIN_NAMES: Record<string, string> = {simulated: 'Simulated', manual: 'Manual entry', device: 'Verified device', imported: 'Imported'};

export function TrendChart({record, metric, days = 30, origin = 'simulated'}: {record: HealthRecord; metric: string; days?: number; origin?: string}) {
  const cutoff = Date.now() - days * 86400000;
  const rows = record.measurements.filter(r => r.metric === metric && r.quality === 'valid' && (origin === 'all' || r.origin === origin) && new Date(r.timestamp).getTime() >= cutoff);
  const grouped = new Map<string, Record<string, number[]>>();
  for (const r of rows) {
    const key = r.timestamp.slice(0, 10);
    const entry = grouped.get(key) || {};
    (entry[r.origin] ||= []).push(r.value);
    grouped.set(key, entry);
  }
  const origins = [...new Set(rows.map(r => r.origin))].sort((a, b) => (a === 'simulated' ? -1 : b === 'simulated' ? 1 : a.localeCompare(b)));
  const summarise = (values: number[]) => Math.round((DAILY_TOTAL.has(metric) ? Math.max(...values) : values.reduce((a, b) => a + b, 0) / values.length) * 10) / 10;
  const data = [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([date, byOrigin]) => ({date, ...Object.fromEntries(Object.entries(byOrigin).map(([o, v]) => [o, summarise(v)]))})) as ({date: string} & Record<string, number>)[];
  const baseline = record.baselines.find(b => b.metric === metric && b.origin === 'simulated');
  const unit = baseline?.unit || rows[0]?.unit || '';
  if (!data.length) return <div className="chart-empty">No valid {origin === 'all' ? '' : `${(ORIGIN_NAMES[origin] || origin).toLowerCase()} `}measurements in this time window.</div>;
  const latest = data.at(-1)!;
  const showBaseline = baseline && origins.includes('simulated');
  return <div className="chart" role="img" aria-label={`${labels[metric]} daily ${DAILY_TOTAL.has(metric) ? 'total' : 'mean'} chart across ${data.length} collection days. Latest ${origins.map(o => `${ORIGIN_NAMES[o] || o} ${latest[o] ?? 'none'}`).join(', ')} ${unit}${showBaseline ? `; synthetic baseline ${baseline!.value}` : ''}.`}>
    <ResponsiveContainer width="100%" height="100%"><ComposedChart data={data} margin={{top: 18, right: 12, bottom: 5, left: -20}}>
      <defs><linearGradient id={`fill-${metric}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#d2ed9c" stopOpacity={.19}/><stop offset="100%" stopColor="#d2ed9c" stopOpacity={0}/></linearGradient></defs>
      <CartesianGrid stroke="#ffffff09" vertical={false}/>
      <XAxis dataKey="date" tickFormatter={day} axisLine={false} tickLine={false} minTickGap={45} tick={{fill: '#7e8a8a', fontSize: 11}} dy={10}/>
      <YAxis domain={['auto', 'auto']} axisLine={false} tickLine={false} tick={{fill: '#7e8a8a', fontSize: 11}}/>
      <Tooltip labelFormatter={v => day(String(v))} contentStyle={{background: '#182225', border: '1px solid #34413c', borderRadius: 8, color: '#edf0e9'}} formatter={(v, name) => [`${v} ${unit}`, `${ORIGIN_NAMES[String(name)] || name} · daily ${DAILY_TOTAL.has(metric) ? 'total' : 'mean'}`]}/>
      {showBaseline && <ReferenceLine y={baseline!.value} stroke="#748375" strokeDasharray="5 5" label={{value: 'BASELINE', position: 'insideTopRight', fill: '#879787', fontSize: 9}}/>}
      {origins.includes('simulated') && <Area isAnimationActive={false} type="monotone" dataKey="simulated" stroke="#d2ed9c" strokeWidth={2.5} fill={`url(#fill-${metric})`} connectNulls activeDot={{r: 5, stroke: '#0e1617', strokeWidth: 3}}/>}
      {origins.filter(o => o !== 'simulated').map(o => <Line key={o} isAnimationActive={false} type="monotone" dataKey={o} stroke={o === 'manual' ? '#e0b581' : '#8fd3e8'} strokeWidth={2} connectNulls dot={{r: 3.5, fill: o === 'manual' ? '#e0b581' : '#8fd3e8', strokeWidth: 0}}/>)}
    </ComposedChart></ResponsiveContainer>
  </div>;
}
