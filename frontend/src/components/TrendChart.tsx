import {ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine} from 'recharts';
import type {HealthRecord} from '../services/api';
import {day, labels} from '../services/api';

export function TrendChart({record, metric, days = 30}: {record: HealthRecord; metric: string; days?: number}) {
  const cutoff = Date.now() - days * 86400000;
  const grouped = new Map<string, {values: number[]; date: string}>();
  for (const r of record.measurements.filter(r => r.metric === metric && r.quality === 'valid' && r.origin === 'simulated' && new Date(r.timestamp).getTime() >= cutoff)) {
    const key = r.timestamp.slice(0, 10);
    const entry = grouped.get(key) || {values: [], date: key};
    entry.values.push(r.value); grouped.set(key, entry);
  }
  const data = [...grouped.values()].sort((a,b)=>a.date.localeCompare(b.date)).map(r=>({date:r.date,value:Math.round(r.values.reduce((a,b)=>a+b,0)/r.values.length*10)/10}));
  const baseline = record.baselines.find(b=>b.metric===metric && b.origin === 'simulated');
  if (!data.length) return <div className="chart-empty">No valid synthetic measurements in this time window.</div>;
  return <div className="chart" role="img" aria-label={`${labels[metric]} daily mean chart across ${data.length} collection days. Latest ${data.at(-1)?.value} ${baseline?.unit || ''}; baseline ${baseline?.value}.`}><ResponsiveContainer width="100%" height="100%"><AreaChart data={data} margin={{top:18,right:12,bottom:5,left:-20}}><defs><linearGradient id={`fill-${metric}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#d2ed9c" stopOpacity={.19}/><stop offset="100%" stopColor="#d2ed9c" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#ffffff09" vertical={false}/><XAxis dataKey="date" tickFormatter={day} axisLine={false} tickLine={false} minTickGap={45} tick={{fill:'#7e8a8a',fontSize:11}} dy={10}/><YAxis domain={['auto','auto']} axisLine={false} tickLine={false} tick={{fill:'#7e8a8a',fontSize:11}}/><Tooltip labelFormatter={v=>day(String(v))} contentStyle={{background:'#182225',border:'1px solid #34413c',borderRadius:8,color:'#edf0e9'}} formatter={v=>[`${v} ${baseline?.unit || ''}`, 'Daily mean']}/>{baseline && <ReferenceLine y={baseline.value} stroke="#748375" strokeDasharray="5 5" label={{value:'BASELINE',position:'insideTopRight',fill:'#879787',fontSize:9}}/>}<Area isAnimationActive={false} type="monotone" dataKey="value" stroke="#d2ed9c" strokeWidth={2.5} fill={`url(#fill-${metric})`} activeDot={{r:5,stroke:'#0e1617',strokeWidth:3}}/></AreaChart></ResponsiveContainer></div>;
}
