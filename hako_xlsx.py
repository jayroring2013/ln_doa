'use client'

export const dynamic = 'force-dynamic'

import { useEffect, useMemo, useState, type ReactNode } from 'react'
import Link from 'next/link'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  BookOpen,
  Building2,
  CheckCircle2,
  Gauge,
  LayoutDashboard,
  ListFilter,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from 'lucide-react'
import supabase from '@/lib/supabaseClient'
import { useLocale } from '@/contexts/LocaleContext'

type Mode = 'dashboard' | 'watchlist'

type RawRankingRow = {
  id: number
  series_title: string | null
  series_id: string | null
  lidex_series_id: number | null
  series_code: string | null
  number_of_volumes: number | null
  average_price: number | null
  max_release_at: string | null
  average_view_count: number | null
  publisher: string | null
  original_volumes: number | null
  original_status: string | null
  evalution: string | null
  evaluation_basis: string | null
  ln_score: number | null
  trang_thai: string | null
  drop_percent: number | null
  drop_basis: string | null
  average_gap_months: number | null
  months_since_last_release: number | null
  completion_ratio: number | null
  publisher_activity: string | null
  publisher_releases_last_24m: number | null
  score_components: string | null
  drop_components: string | null
  cover_url: string | null
  cover_source_title: string | null
  updated_at: string | null
}

type LNRow = {
  raw_rank: number
  source_row_id: number
  series_key: string
  series_title: string
  series_id: string | null
  lidex_series_id: number | null
  series_code: string | null
  number_of_volumes: number
  average_price: number
  max_release_at: string | null
  average_view_count: number
  publisher: string | null
  original_volumes: number
  original_status: string | null
  evalution: string | null
  evaluation_basis: string | null
  ln_score: number
  trang_thai: string | null
  drop_percent: number
  drop_basis: string | null
  average_gap_months: number | null
  months_since_last_release: number | null
  completion_ratio: number | null
  publisher_activity: string | null
  publisher_releases_last_24m: number
  score_components: string | null
  drop_components: string | null
  cover_url: string | null
  cover_source_title: string | null

  release_pace_score: number
  catch_up_score: number
  demand_score: number
  publisher_support_score: number
  completion_safety_score: number
  momentum_score: number
}

type VolumeReleaseRow = {
  series_id: number
  publisher: string
  release_date: string
}

type PublisherAgg = {
  publisher: string
  releases24: number
  seriesCount: number
  avgScore: number
  avgDrop: number
  marketShare: number
}

type GrowthRow = {
  year: number
  volumes: number
}

type HeatmapRow = {
  publisher: string
  monthKey: string
  monthLabel: string
  count: number
}

function releaseYear(row: LNRow) {
  if (!row.max_release_at) return null
  const year = new Date(row.max_release_at).getFullYear()
  return Number.isFinite(year) ? year : null
}

function volumeReleaseYear(row: VolumeReleaseRow) {
  const year = new Date(row.release_date).getFullYear()
  return Number.isFinite(year) ? year : null
}

function availableReleaseYears(rows: Array<LNRow | VolumeReleaseRow>) {
  return Array.from(new Set(rows.map(row => 'release_date' in row ? volumeReleaseYear(row) : releaseYear(row)).filter((year): year is number => year !== null))).sort((a, b) => a - b)
}

function filterVolumeRowsByYears(rows: VolumeReleaseRow[], selectedYears: number[]) {
  if (selectedYears.length === 0) return rows
  const allowed = new Set(selectedYears)
  return rows.filter(row => {
    const year = volumeReleaseYear(row)
    return year !== null && allowed.has(year)
  })
}

function YearFilter({ years, selectedYears, setSelectedYears, vi }: { years: number[]; selectedYears: number[]; setSelectedYears: (years: number[]) => void; vi: boolean }) {
  const displayYears = [...years].sort((a, b) => b - a)
  const toggleYear = (year: number) => {
    setSelectedYears(selectedYears.includes(year) ? selectedYears.filter(y => y !== year) : [...selectedYears, year].sort((a, b) => a - b))
  }
  const label = selectedYears.length === 0
    ? (vi ? 'Tất cả năm' : 'All years')
    : selectedYears.length <= 2
      ? selectedYears.join(', ')
      : (vi ? `${selectedYears.length} năm` : `${selectedYears.length} years`)

  return (
    <details className="relative shrink-0">
      <summary
        className="list-none cursor-pointer select-none px-2.5 py-1.5 rounded-lg text-[10px] font-black min-w-[88px] text-center"
        style={{ background: selectedYears.length === 0 ? '#7c6af5' : 'var(--ln-control-bg)', color: selectedYears.length === 0 ? '#fff' : 'var(--foreground-secondary)', border: '1px solid var(--card-border)' }}
      >
        {label} ▾
      </summary>
      <div className="absolute right-0 top-8 z-[9999] w-[156px] rounded-lg p-2 shadow-xl space-y-1" style={{ background: 'var(--ln-panel-bg-strong)', border: '1px solid var(--card-border)' }}>
        <button type="button" onClick={() => setSelectedYears([])} className="w-full text-left px-2 py-1.5 rounded-md text-[10px] font-bold" style={{ color: selectedYears.length === 0 ? '#a78bfa' : 'var(--foreground-secondary)', background: selectedYears.length === 0 ? 'rgba(124,106,245,.16)' : 'transparent' }}>
          {vi ? 'Tất cả năm' : 'All years'}
        </button>
        <div className="overflow-y-auto overscroll-contain pr-1 space-y-1" style={{ maxHeight: 'min(70vh, 320px)', scrollbarGutter: 'stable' }}>
          {displayYears.map(year => (
            <label key={year} className="flex items-center gap-2 px-2 py-1.5 rounded-md text-[10px] font-bold cursor-pointer hover:bg-white/[0.04]" style={{ color: 'var(--foreground-secondary)' }}>
              <input type="checkbox" checked={selectedYears.includes(year)} onChange={() => toggleYear(year)} className="accent-violet-500" />
              {year}
            </label>
          ))}
        </div>
      </div>
    </details>
  )
}

const RELEASE_STATUS_ORDER: Record<string, number> = {
  'Đang phát hành': 0,
  'Lâu lắm rồi chưa có tập mới': 1,
  Drop: 2,
  'Đã bắt kịp bản gốc JP': 3,
  'Hoàn thành': 4,
}

const EVAL_ORDER = ['Completed', 'Good', 'Limping', 'Dead', 'Dropped']

const statusColors: Record<string, string> = {
  Completed: '#38bdf8',
  Good: '#22c55e',
  Limping: '#eab308',
  Dead: '#f97316',
  Dropped: '#ef4444',
}

function num(v: unknown, fallback = 0) {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}

function fmtNum(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return Number(value).toLocaleString('vi-VN', { maximumFractionDigits: digits })
}

function fmtDate(value: string | null | undefined) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('vi-VN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

function fmtScore(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return Number(value).toFixed(1)
}

function pctValue(raw: number | null | undefined) {
  const x = Number(raw || 0)
  return x <= 1 ? Math.round(x * 100) : Math.round(x)
}

function fmtPercent(raw: number | null | undefined) {
  return `${pctValue(raw)}%`
}

function evalLabel(s?: string | null, vi = true) {
  const viMap = { Completed: 'Hoàn thành', Good: 'Tốt', Limping: 'Cầm chừng', Dead: 'Gần chết', Dropped: 'Đã drop' } as Record<string, string>
  const enMap = { Completed: 'Completed', Good: 'Good', Limping: 'Limping', Dead: 'Inactive', Dropped: 'Dropped' } as Record<string, string>
  return (vi ? viMap : enMap)[s || ''] || s || '—'
}

function releaseStatusLabel(status: string, vi = true) {
  if (vi) return status
  return ({
    'Đang phát hành': 'Active',
    'Lâu lắm rồi chưa có tập mới': 'Long inactive',
    Drop: 'Dropped',
    'Đã bắt kịp bản gốc JP': 'Caught up to JP',
    'Hoàn thành': 'Completed',
  } as Record<string, string>)[status] || status
}

function releaseStatus(row: LNRow) {
  return row.trang_thai || (
    row.evalution === 'Completed'
      ? 'Hoàn thành'
      : row.evalution === 'Dead'
        ? 'Lâu lắm rồi chưa có tập mới'
        : row.evalution === 'Dropped'
          ? 'Drop'
          : 'Đang phát hành'
  )
}

function releaseStatusPriority(row: LNRow) {
  return RELEASE_STATUS_ORDER[releaseStatus(row)] ?? 99
}

function releaseStatusStyle(row: LNRow) {
  const rs = releaseStatus(row)
  if (rs === 'Hoàn thành') return { color: '#7dd3fc', bg: 'rgba(56,189,248,.12)', border: 'rgba(56,189,248,.22)' }
  if (rs === 'Drop') return { color: '#fca5a5', bg: 'rgba(239,68,68,.12)', border: 'rgba(239,68,68,.22)' }
  if (rs === 'Lâu lắm rồi chưa có tập mới') return { color: '#fb923c', bg: 'rgba(249,115,22,.12)', border: 'rgba(249,115,22,.22)' }
  if (rs === 'Đã bắt kịp bản gốc JP') return { color: '#a78bfa', bg: 'rgba(124,106,245,.15)', border: 'rgba(124,106,245,.28)' }
  return { color: '#4ade80', bg: 'rgba(34,197,94,.12)', border: 'rgba(34,197,94,.22)' }
}

function scoreColor(score: number) {
  if (score >= 8) return '#22c55e'
  if (score >= 6) return '#38bdf8'
  if (score >= 4) return '#eab308'
  return '#ef4444'
}

function dropColor(drop: number) {
  const p = pctValue(drop)
  if (p <= 25) return '#22c55e'
  if (p <= 55) return '#eab308'
  return '#ef4444'
}

function proxyImg(url: string | null) {
  if (!url) return null
  try {
    const h = new URL(url).hostname
    if (!h.includes('supabase') && !h.includes('localhost') && !url.startsWith('/')) {
      return `/api/image-proxy?url=${encodeURIComponent(url)}`
    }
  } catch {}
  return url
}

function detailHref(row: LNRow | null) {
  if (!row) return '/browse'
  if (row.lidex_series_id) return `/content/${row.lidex_series_id}`
  return `/browse?search=${encodeURIComponent(row.series_title)}`
}

function clamp10(v: number) {
  return Math.max(0, Math.min(10, Number.isFinite(v) ? v : 0))
}

function releasePaceScore(avgGap: number | null, monthsSince: number | null) {
  let gap = 5
  if (avgGap != null) {
    if (avgGap <= 4) gap = 9.5
    else if (avgGap <= 6) gap = 8.5
    else if (avgGap <= 12) gap = 6.5
    else if (avgGap <= 18) gap = 4.5
    else if (avgGap <= 24) gap = 3
    else gap = 1.5
  }

  let recency = 5
  if (monthsSince != null) {
    if (monthsSince <= 6) recency = 9
    else if (monthsSince <= 12) recency = 7
    else if (monthsSince <= 18) recency = 5
    else if (monthsSince <= 24) recency = 3
    else if (monthsSince <= 36) recency = 1.8
    else recency = 1
  }

  return Number((gap * 0.6 + recency * 0.4).toFixed(1))
}

function catchUpScore(row: RawRankingRow) {
  if (row.completion_ratio != null) {
    const r = num(row.completion_ratio)
    return clamp10((r > 1 ? r / 100 : r) * 10)
  }
  const jp = num(row.original_volumes)
  if (jp > 0) return clamp10(num(row.number_of_volumes) / jp * 10)
  return 5
}

function percentileFn(values: number[]) {
  const sorted = values.filter(v => Number.isFinite(v)).sort((a, b) => a - b)
  return (value: number) => {
    if (sorted.length <= 1) return 5
    const idx = sorted.findIndex(v => v >= value)
    const rank = idx < 0 ? sorted.length - 1 : idx
    return Number(((rank / (sorted.length - 1)) * 10).toFixed(1))
  }
}

function publisherSupport(activity: string | null, releases24: number) {
  const base = ({ Active: 8, Moderate: 6.5, Low: 4.5, Inactive: 2 } as Record<string, number>)[activity || ''] ?? 5
  return Number(clamp10(base + Math.min(releases24 / 50 * 2, 2)).toFixed(1))
}

function safetyScore(evalution: string | null, drop: number) {
  if (evalution === 'Completed') return 10
  const p = pctValue(drop) / 100
  return Number(clamp10((1 - p) * 10).toFixed(1))
}

function momentumScore(activity: string | null, releases24: number, monthsSince: number | null) {
  const base = ({ Active: 7.5, Moderate: 6, Low: 4, Inactive: 2 } as Record<string, number>)[activity || ''] ?? 5
  const releaseScore = clamp10(releases24 / 40 * 10)
  let freshness = 5
  if (monthsSince != null) {
    if (monthsSince <= 6) freshness = 8.5
    else if (monthsSince <= 12) freshness = 6.5
    else if (monthsSince <= 18) freshness = 4.5
    else freshness = 2
  }
  return Number((base * 0.45 + releaseScore * 0.35 + freshness * 0.2).toFixed(1))
}

function mapRows(raw: RawRankingRow[]) {
  const demand = percentileFn(raw.map(r => num(r.average_view_count)))
  return raw.map((r, i): LNRow => {
    const monthsSince = r.months_since_last_release == null ? null : num(r.months_since_last_release)
    const avgGap = r.average_gap_months == null ? null : num(r.average_gap_months)
    const releases24 = num(r.publisher_releases_last_24m)
    const drop = num(r.drop_percent)
    return {
      raw_rank: i + 1,
      source_row_id: r.id,
      series_key: `${r.lidex_series_id || r.series_id || r.id}|${r.series_code || ''}`,
      series_title: r.series_title || 'Untitled',
      series_id: r.series_id,
      lidex_series_id: r.lidex_series_id == null ? null : num(r.lidex_series_id),
      series_code: r.series_code,
      number_of_volumes: num(r.number_of_volumes),
      average_price: num(r.average_price),
      max_release_at: r.max_release_at ? String(r.max_release_at).slice(0, 10) : null,
      average_view_count: num(r.average_view_count),
      publisher: r.publisher,
      original_volumes: num(r.original_volumes),
      original_status: r.original_status,
      evalution: r.evalution,
      evaluation_basis: r.evaluation_basis,
      ln_score: num(r.ln_score),
      trang_thai: r.trang_thai,
      drop_percent: drop,
      drop_basis: r.drop_basis,
      average_gap_months: avgGap,
      months_since_last_release: monthsSince,
      completion_ratio: r.completion_ratio == null ? null : num(r.completion_ratio),
      publisher_activity: r.publisher_activity,
      publisher_releases_last_24m: releases24,
      score_components: r.score_components,
      drop_components: r.drop_components,
      cover_url: r.cover_url,
      cover_source_title: r.cover_source_title,
      release_pace_score: releasePaceScore(avgGap, monthsSince),
      catch_up_score: catchUpScore(r),
      demand_score: demand(num(r.average_view_count)),
      publisher_support_score: publisherSupport(r.publisher_activity, releases24),
      completion_safety_score: safetyScore(r.evalution, drop),
      momentum_score: momentumScore(r.publisher_activity, releases24, monthsSince),
    }
  })
}

async function hydrateRowsWithCanonicalSeries(rows: LNRow[]): Promise<LNRow[]> {
  const ids = Array.from(new Set(rows.map(row => row.lidex_series_id).filter((id): id is number => Boolean(id))))
  if (ids.length === 0) return rows

  const canonical = new Map<number, { title?: string | null; cover_url?: string | null; publisher?: string | null }>()
  const batchSize = 200

  for (let i = 0; i < ids.length; i += batchSize) {
    const chunk = ids.slice(i, i + batchSize)
    const { data, error } = await supabase
      .from('series')
      .select('id, title, cover_url, publisher')
      .in('id', chunk)

    if (error) {
      console.warn('[Dashboard] canonical series fetch failed:', error.message)
      continue
    }

    for (const series of data || []) {
      canonical.set(Number((series as any).id), {
        title: (series as any).title,
        cover_url: (series as any).cover_url,
        publisher: (series as any).publisher,
      })
    }
  }

  return rows.map(row => {
    const meta = row.lidex_series_id ? canonical.get(row.lidex_series_id) : null
    if (!meta) return row
    return {
      ...row,
      // Keep the evaluated ranking title unless it is missing, but use canonical cover/publisher as fallback.
      series_title: row.series_title || meta.title || row.series_title,
      cover_url: row.cover_url || meta.cover_url || row.cover_url,
      publisher: row.publisher || meta.publisher || row.publisher,
    }
  })
}

function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-xl ${className}`}
      style={{
        background: 'var(--ln-card-bg)',
        border: '1px solid var(--card-border)',
        boxShadow: 'var(--ln-card-shadow)',
      }}
    >
      {children}
    </div>
  )
}

function KpiStrip({ rows, vi }: { rows: LNRow[]; vi: boolean }) {
  const avgScore = rows.length ? rows.reduce((s, r) => s + r.ln_score, 0) / rows.length : 0
  const avgDrop = rows.length ? rows.reduce((s, r) => s + pctValue(r.drop_percent), 0) / rows.length : 0
  const active = rows.filter(r => ['Đang phát hành', 'Đã bắt kịp bản gốc JP', 'Lâu lắm rồi chưa có tập mới'].includes(releaseStatus(r))).length
  const completed = rows.filter(r => r.evalution === 'Completed' || releaseStatus(r) === 'Hoàn thành').length
  const activePublishers = new Set(rows.filter(r => r.publisher_activity === 'Active').map(r => r.publisher).filter(Boolean)).size
  const linked = rows.filter(r => Boolean(r.lidex_series_id)).length

  const items = [
    { label: vi ? 'Đã cấp phép' : 'Licensed', value: rows.length.toLocaleString('vi-VN'), icon: BookOpen, color: '#818cf8' },
    { label: vi ? 'Liên kết ID' : 'Linked IDs', value: `${linked}/${rows.length}`, icon: ShieldCheck, color: linked === rows.length ? '#22c55e' : '#f97316' },
    { label: vi ? 'Đang hoạt động' : 'Active', value: active.toLocaleString('vi-VN'), icon: Activity, color: '#22c55e' },
    { label: vi ? 'Hoàn thành' : 'Completed', value: completed.toLocaleString('vi-VN'), icon: CheckCircle2, color: '#38bdf8' },
    { label: vi ? 'Điểm TB' : 'Avg Score', value: avgScore.toFixed(1), icon: Gauge, color: '#eab308' },
    { label: vi ? 'Drop TB' : 'Avg Drop', value: `${avgDrop.toFixed(1)}%`, icon: AlertTriangle, color: '#fb7185' },
    { label: vi ? 'Nhà PH hoạt động' : 'Active Pubs', value: activePublishers.toLocaleString('vi-VN'), icon: Building2, color: '#a78bfa' },
  ]

  return (
    <Card className="p-2.5">
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-7 gap-2">
        {items.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-lg px-3 py-2.5 relative overflow-hidden" style={{ background: 'var(--ln-panel-bg)', border: '1px solid var(--card-border)' }}>
            <div className="absolute right-0 top-0 w-16 h-16 rounded-full blur-2xl" style={{ background: `${color}22` }} />
            <div className="relative flex items-start justify-between gap-2">
              <div>
                <p className="text-[9px] font-black uppercase tracking-[.15em]" style={{ color: 'var(--foreground-muted)' }}>{label}</p>
                <p className="text-xl font-black mt-1 leading-none" style={{ color: 'var(--foreground)' }}>{value}</p>
              </div>
              <Icon className="w-4 h-4" style={{ color }} />
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

function ModeSwitch({ mode, setMode, vi }: { mode: Mode; setMode: (m: Mode) => void; vi: boolean }) {
  return (
    <div className="flex items-center gap-1 p-1 rounded-xl" style={{ background: 'var(--ln-panel-bg-strong)', border: '1px solid var(--card-border)' }}>
      <button
        onClick={() => setMode('dashboard')}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all"
        style={mode === 'dashboard' ? { background: '#7c6af5', color: '#fff' } : { color: 'var(--foreground-secondary)' }}
      >
        <LayoutDashboard className="w-3.5 h-3.5" />
        {vi ? 'Bảng điều khiển' : 'Dashboard'}
      </button>
      <button
        onClick={() => setMode('watchlist')}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all"
        style={mode === 'watchlist' ? { background: '#22c55e', color: '#03150a' } : { color: 'var(--foreground-secondary)' }}
      >
        <ListFilter className="w-3.5 h-3.5" />
        {vi ? 'Watchlist LN' : 'LN Watchlist'}
      </button>
    </div>
  )
}

function ScatterPlot({ rows, selectedKey, onSelect, vi }: { rows: LNRow[]; selectedKey: string | null; onSelect: (row: LNRow) => void; vi: boolean }) {
  const plotRows = rows.filter(r => r.evalution !== 'Completed')
  return (
    <Card className="p-3.5">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div>
          <p className="text-xs font-black uppercase tracking-wide" style={{ color: 'var(--foreground)' }}>{vi ? 'Điểm LN vs Rủi ro Drop' : 'LN Score vs Drop Risk'}</p>
          <p className="text-[11px]" style={{ color: 'var(--foreground-muted)' }}>{vi ? 'Ẩn các series đã hoàn thành để tập trung vào rủi ro hiện tại.' : 'Completed novels are hidden to focus on current market risk.'}</p>
        </div>
        <div className="hidden sm:flex flex-wrap gap-2">
          {['Good', 'Limping', 'Dead', 'Dropped'].map(s => (
            <span key={s} className="text-[10px] font-bold flex items-center gap-1" style={{ color: 'var(--foreground-secondary)' }}>
              <span className="w-2 h-2 rounded-full" style={{ background: statusColors[s] }} />
              {evalLabel(s, vi)}
            </span>
          ))}
        </div>
      </div>

      <div className="relative h-[300px] sm:h-[350px] rounded-lg overflow-hidden" style={{ background: 'var(--ln-chart-bg)', border: '1px solid var(--card-border)' }}>
        <div className="absolute inset-0 opacity-50 pointer-events-none">
          <div className="absolute left-0 top-0 w-1/2 h-1/2" style={{ background: 'linear-gradient(135deg, rgba(239,68,68,.08), transparent)' }} />
          <div className="absolute right-0 bottom-0 w-1/2 h-1/2" style={{ background: 'linear-gradient(315deg, rgba(34,197,94,.08), transparent)' }} />
        </div>

        <div className="absolute inset-7 sm:inset-8">
          {[0, 25, 50, 75, 100].map(v => (
            <div key={`y-${v}`} className="absolute left-0 right-0 border-t border-dashed" style={{ top: `${100 - v}%`, borderColor: 'rgba(136,146,170,.16)' }}>
              <span className="absolute -left-1 -translate-x-full -top-2 text-[9px]" style={{ color: 'var(--foreground-muted)' }}>{v}%</span>
            </div>
          ))}
          {[0, 2, 4, 6, 8, 10].map(v => (
            <div key={`x-${v}`} className="absolute top-0 bottom-0 border-l border-dashed" style={{ left: `${v * 10}%`, borderColor: 'rgba(136,146,170,.10)' }}>
              <span className="absolute -bottom-4 -translate-x-1/2 text-[9px]" style={{ color: 'var(--foreground-muted)' }}>{v}</span>
            </div>
          ))}

          <span className="absolute left-2 top-2 text-[10px] font-black uppercase" style={{ color: '#ef4444' }}>{vi ? 'Rủi ro cao' : 'High Risk'}</span>
          <span className="absolute right-2 top-2 text-[10px] font-black uppercase" style={{ color: '#eab308' }}>{vi ? 'Phổ biến nhưng rủi ro' : 'Popular Risk'}</span>
          <span className="absolute left-2 bottom-2 text-[10px] font-black uppercase" style={{ color: '#a78bfa' }}>{vi ? 'Đình trệ' : 'Stalled'}</span>
          <span className="absolute right-2 bottom-2 text-[10px] font-black uppercase" style={{ color: '#22c55e' }}>{vi ? 'Khỏe mạnh' : 'Healthy'}</span>

          {plotRows.map(row => {
            const x = Math.max(0, Math.min(100, row.ln_score * 10))
            const y = 100 - Math.max(0, Math.min(100, pctValue(row.drop_percent)))
            const active = row.series_key === selectedKey
            const color = statusColors[row.evalution || ''] || scoreColor(row.ln_score)
            const dotSize = active ? 16 : Math.max(7, Math.min(12, 6 + row.demand_score * 0.6))
            return (
              <button
                key={row.series_key}
                onClick={() => onSelect(row)}
                title={`${row.series_title}\nLN ${row.ln_score.toFixed(1)} · Drop ${fmtPercent(row.drop_percent)}`}
                className="absolute rounded-full transition-all hover:scale-150"
                style={{
                  left: `${x}%`,
                  top: `${y}%`,
                  width: dotSize,
                  height: dotSize,
                  background: color,
                  border: active ? '2px solid #fff' : '1px solid rgba(255,255,255,.35)',
                  boxShadow: active ? `0 0 0 8px ${color}26, 0 0 26px ${color}` : `0 0 12px ${color}66`,
                  transform: 'translate(-50%, -50%)',
                }}
              />
            )
          })}
        </div>

        <div className="absolute left-4 bottom-2 text-[10px]" style={{ color: 'var(--foreground-muted)' }}>LN Score →</div>
        <div className="absolute left-2 top-1/2 -rotate-90 text-[10px]" style={{ color: 'var(--foreground-muted)' }}>{vi ? 'Khả năng drop' : 'Drop Probability'}</div>
      </div>
    </Card>
  )
}

function RadarChart({ row, vi }: { row: LNRow | null; vi: boolean }) {
  const axes = row ? [
    [vi ? 'Nhịp phát hành' : 'Release Pace', row.release_pace_score, vi ? 'Khoảng cách trung bình + độ mới của tập gần nhất' : 'Average gap + latest release recency'],
    [vi ? 'Bắt kịp' : 'Catch-up', row.catch_up_score, vi ? 'Tiến độ bản Việt so với số tập gốc' : 'VN volumes compared with original volumes'],
    [vi ? 'Nhu cầu' : 'Demand', row.demand_score, vi ? 'Percentile lượt xem trung bình' : 'Average view count percentile'],
    [vi ? 'Nhà PH' : 'Publisher', row.publisher_support_score, vi ? 'Hoạt động nhà phát hành + số tập 24 tháng' : 'Publisher activity + 24M release output'],
    [vi ? 'An toàn' : 'Safety', row.completion_safety_score, vi ? 'Nghịch đảo của khả năng drop' : 'Inverse of drop probability'],
    [vi ? 'Đà phát hành' : 'Momentum', row.momentum_score, vi ? 'Hỗ trợ nhà phát hành + độ mới phát hành' : 'Publisher support + recent release recency'],
  ] as const : []

  const size = 210
  const cx = size / 2
  const cy = size / 2
  const maxR = 68
  const points = axes.map(([, value], i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / axes.length
    const r = clamp10(value) / 10 * maxR
    return `${cx + Math.cos(angle) * r},${cy + Math.sin(angle) * r}`
  }).join(' ')
  const grids = [0.33, 0.66, 1].map(level => axes.map(([,], i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / axes.length
    const r = level * maxR
    return `${cx + Math.cos(angle) * r},${cy + Math.sin(angle) * r}`
  }).join(' '))

  if (!row) {
    return (
      <Card className="p-4 h-full flex items-center justify-center text-sm">
        <span style={{ color: 'var(--foreground-muted)' }}>{vi ? 'Chọn một series' : 'Select a series'}</span>
      </Card>
    )
  }

  const rsStyle = releaseStatusStyle(row)

  return (
    <Card className="p-3.5 h-full">
      <div className="flex gap-3">
        {row.cover_url ? (
          <img src={proxyImg(row.cover_url) || ''} alt="" className="w-[78px] h-[112px] sm:w-[88px] sm:h-[126px] object-cover rounded-lg shadow-lg shrink-0" />
        ) : (
          <div className="w-[78px] h-[112px] sm:w-[88px] sm:h-[126px] rounded-lg shrink-0" style={{ background: 'rgba(124,106,245,.14)' }} />
        )}
        <div className="min-w-0 flex-1">
          <h2 className="text-base sm:text-lg font-black leading-snug line-clamp-3" style={{ color: 'var(--foreground)' }}>{row.series_title}</h2>
          <div className="flex items-center justify-between gap-3 mt-1 text-[11px] font-semibold" style={{ color: 'var(--foreground-muted)' }}>
            <span>{vi ? 'Số tập' : 'Volumes'}: <span style={{ color: 'var(--foreground-secondary)' }}>{fmtNum(row.number_of_volumes, 0)}</span></span>
            <span className="text-right">{vi ? 'Mới nhất' : 'Latest'}: <span style={{ color: 'var(--foreground-secondary)' }}>{fmtDate(row.max_release_at)}</span></span>
          </div>
          <div className="flex flex-wrap gap-1.5 mt-2">
            <span className="rounded-full px-2 py-0.5 text-[10px] font-black" style={{ color: rsStyle.color, background: rsStyle.bg, border: `1px solid ${rsStyle.border}` }}>{releaseStatusLabel(releaseStatus(row), vi)}</span>
            <span className="rounded-full px-2 py-0.5 text-[10px] font-black" style={{ color: 'var(--foreground-muted)', background: 'var(--ln-muted-bg)' }}>{row.publisher || '—'}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 mt-3">
        <div className="rounded-lg px-2.5 py-2 flex items-center justify-between gap-2" style={{ background: 'rgba(34,197,94,.10)' }}>
          <p className="text-[9px] uppercase font-black" style={{ color: 'var(--foreground-muted)' }}>LN Score</p>
          <p className="text-lg font-black leading-none" style={{ color: scoreColor(row.ln_score) }}>{fmtScore(row.ln_score)}</p>
        </div>
        <div className="rounded-lg px-2.5 py-2 flex items-center justify-between gap-2" style={{ background: 'rgba(239,68,68,.10)' }}>
          <p className="text-[9px] uppercase font-black" style={{ color: 'var(--foreground-muted)' }}>Drop</p>
          <p className="text-lg font-black leading-none" style={{ color: dropColor(row.drop_percent) }}>{fmtPercent(row.drop_percent)}</p>
        </div>
        <Link href={detailHref(row)} className="rounded-lg px-2.5 py-2 flex items-center justify-center gap-1 text-xs font-black transition-all hover:scale-[1.02]" style={{ background: 'rgba(124,106,245,.18)', color: '#c4b5fd', border: '1px solid rgba(124,106,245,.28)' }}>
          Open
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-[210px_1fr] xl:grid-cols-[210px_1fr] gap-2 mt-2 items-center">
        <div className="flex justify-start">
          <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="max-w-full">
            {grids.map((g, i) => <polygon key={i} points={g} fill="none" stroke="rgba(136,146,170,.18)" />)}
            {axes.map(([label], i) => {
              const angle = -Math.PI / 2 + (i * 2 * Math.PI) / axes.length
              const x = cx + Math.cos(angle) * (maxR + 20)
              const y = cy + Math.sin(angle) * (maxR + 20)
              return (
                <g key={label}>
                  <line x1={cx} y1={cy} x2={cx + Math.cos(angle) * maxR} y2={cy + Math.sin(angle) * maxR} stroke="rgba(136,146,170,.14)" />
                  <text x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontSize="8.5" fill="rgba(232,236,244,.72)">{label}</text>
                </g>
              )
            })}
            <polygon points={points} fill="rgba(124,106,245,.34)" stroke="#a78bfa" strokeWidth="2" />
            {points.split(' ').map((p, i) => {
              const [x, y] = p.split(',').map(Number)
              return <circle key={i} cx={x} cy={y} r="3" fill="#c4b5fd" />
            })}
          </svg>
        </div>

        <div className="grid grid-cols-2 xl:grid-cols-1 gap-1.5">
          {axes.map(([label, value, source]) => (
            <div key={label} title={source} className="rounded-lg px-2 py-1.5" style={{ background: 'var(--ln-panel-bg)', border: '1px solid var(--card-border)' }}>
              <p className="text-[9px] uppercase font-black" style={{ color: 'var(--foreground-muted)' }}>{label}</p>
              <p className="text-xs font-black" style={{ color: '#c4b5fd' }}>{fmtScore(value)}</p>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}

function buildPublishers(rows: LNRow[], volumeRows?: VolumeReleaseRow[]) {
  const groups = new Map<string, LNRow[]>()
  for (const row of rows) {
    const key = row.publisher || 'Unknown'
    groups.set(key, [...(groups.get(key) || []), row])
  }
  const volumeCounts = new Map<string, number>()
  for (const row of volumeRows || []) {
    const key = row.publisher || 'Unknown'
    volumeCounts.set(key, (volumeCounts.get(key) || 0) + 1)
    if (!groups.has(key)) groups.set(key, [])
  }
  const totalReleases = Array.from(volumeCounts.values()).reduce((sum, count) => sum + count, 0) || 1
  return Array.from(groups.entries()).map(([publisher, items]): PublisherAgg => {
    const releases24 = volumeRows ? (volumeCounts.get(publisher) || 0) : Math.max(...items.map(i => i.publisher_releases_last_24m), 0)
    return {
      publisher,
      releases24,
      seriesCount: items.length,
      avgScore: items.length ? items.reduce((s, i) => s + i.ln_score, 0) / items.length : 0,
      avgDrop: items.length ? items.reduce((s, i) => s + pctValue(i.drop_percent), 0) / items.length : 0,
      marketShare: releases24 / totalReleases * 100,
    }
  }).sort((a, b) => b.releases24 - a.releases24 || b.seriesCount - a.seriesCount)
}

function PublisherLeaderboard({ rows, volumeRows, vi }: { rows: LNRow[]; volumeRows: VolumeReleaseRow[]; vi: boolean }) {
  const [selectedYears, setSelectedYears] = useState<number[]>([])
  const years = availableReleaseYears(volumeRows)
  const filteredVolumes = filterVolumeRowsByYears(volumeRows, selectedYears)
  const publishers = buildPublishers(rows, filteredVolumes).filter(p => p.releases24 > 0).slice(0, 6)
  const max = Math.max(...publishers.map(p => p.releases24), 1)

  return (
    <Card className="p-3 h-[226px] overflow-visible">
      <div className="flex items-center justify-between mb-2">
        <div>
          <p className="text-[11px] font-black uppercase tracking-wide" style={{ color: 'var(--foreground)' }}>{vi ? 'Nhà phát hành hoạt động nhiều nhất' : 'Most Active Publishers'}</p>
          <p className="text-[10px]" style={{ color: 'var(--foreground-muted)' }}>{vi ? 'Sản lượng phát hành, điểm LN và độ an toàn.' : 'Release output, score, and safety proxy.'}</p>
        </div>
        <div className="flex items-center gap-2 min-w-0">
          <YearFilter years={years} selectedYears={selectedYears} setSelectedYears={setSelectedYears} vi={vi} />
          <Building2 className="w-4 h-4 shrink-0" style={{ color: '#38bdf8' }} />
        </div>
      </div>

      <div className="grid grid-cols-[1.05fr_0.9fr_0.55fr_0.6fr] gap-2 px-1 pb-1 text-[9px] font-black uppercase tracking-wide" style={{ color: 'var(--foreground-muted)' }}>
        <span>{vi ? 'Nhà PH' : 'Publisher'}</span>
        <span>{vi ? 'Tập' : 'Releases'}</span>
        <span className="text-right">{vi ? 'Điểm' : 'Score'}</span>
        <span className="text-right">{vi ? 'An toàn' : 'Safe'}</span>
      </div>

      <div className="space-y-1.5">
        {publishers.map((p, i) => {
          const width = (p.releases24 / max) * 100
          const completionProxy = Math.max(0, Math.min(100, 100 - p.avgDrop))
          return (
            <div key={p.publisher} className="grid grid-cols-[1.05fr_0.9fr_0.55fr_0.6fr] gap-2 items-center">
              <div className="flex items-center gap-2 min-w-0">
                <span className="w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-black shrink-0" style={{ background: 'rgba(56,189,248,.16)', color: '#38bdf8' }}>{i + 1}</span>
                <span className="font-bold truncate text-[11px]" style={{ color: 'var(--foreground)' }}>{p.publisher}</span>
              </div>

              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <div className="h-2 rounded-full overflow-hidden flex-1" style={{ background: 'var(--ln-track-bg)' }}>
                    <div className="h-full rounded-full" style={{ width: `${width}%`, background: 'linear-gradient(90deg,#7c6af5,#38bdf8)' }} />
                  </div>
                  <span className="text-[10px] tabular-nums shrink-0" style={{ color: 'var(--foreground-secondary)' }}>{p.releases24}</span>
                </div>
              </div>

              <div className="text-right text-[11px] font-bold tabular-nums" style={{ color: 'var(--foreground-secondary)' }}>
                {p.avgScore.toFixed(2)}
              </div>

              <div className="text-right text-[11px] font-bold tabular-nums" style={{ color: 'var(--foreground-secondary)' }}>
                {completionProxy.toFixed(0)}%
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}

function buildGrowth(rows: VolumeReleaseRow[]) {
  const map = new Map<number, GrowthRow>()
  for (const row of rows) {
    const year = volumeReleaseYear(row)
    if (year === null) continue
    const prev = map.get(year) || { year, volumes: 0 }
    prev.volumes += 1
    map.set(year, prev)
  }
  return Array.from(map.values()).sort((a, b) => a.year - b.year)
}

function GrowthChart({ volumeRows, vi }: { volumeRows: VolumeReleaseRow[]; vi: boolean }) {
  const data = buildGrowth(volumeRows)
  const w = 520
  const h = 148
  const padL = 42
  const padR = 18
  const padT = 12
  const padB = 24
  const maxY = Math.max(...data.map(d => d.volumes), 1)
  const yTicks = [1, .75, .5, .25, 0].map(ratio => Math.round(maxY * ratio))
  const points = data.map((d, i) => {
    const x = padL + i / Math.max(1, data.length - 1) * (w - padL - padR)
    const y = h - padB - d.volumes / maxY * (h - padT - padB)
    return { x, y, d }
  })
  const line = points.map(p => `${p.x},${p.y}`).join(' ')

  return (
    <Card className="p-3 h-[226px] overflow-visible">
      <div className="flex items-center justify-between mb-1.5">
        <div>
          <p className="text-[11px] font-black uppercase tracking-wide" style={{ color: 'var(--foreground)' }}>{vi ? 'Tăng trưởng thị trường LN Việt Nam' : 'Vietnamese LN Market Growth'}</p>
          <p className="text-[10px]" style={{ color: 'var(--foreground-muted)' }}>{vi ? 'Đếm số tập thật từ bảng volumes theo năm phát hành.' : 'Counts real volume rows from volumes by release year.'}</p>
        </div>
        <TrendingUp className="w-4 h-4" style={{ color: '#22c55e' }} />
      </div>

      <div className="flex items-center gap-4 mb-1 text-[10px]" style={{ color: 'var(--foreground-secondary)' }}>
        <span className="inline-flex items-center gap-1"><span className="w-3 h-0.5 rounded-full" style={{ background: '#22c55e' }} /> {vi ? 'Tổng tập' : 'Volumes'}</span>
      </div>

      <div className="overflow-x-auto overflow-y-hidden">
        <svg viewBox={`0 0 ${w} ${h}`} className="h-[166px]" style={{ width: '100%', minWidth: `${Math.max(520, data.length * 42)}px` }}>
          {yTicks.map((tick, i) => {
            const y = padT + i / Math.max(1, yTicks.length - 1) * (h - padT - padB)
            return (
              <g key={`${tick}-${i}`}>
                <line x1={padL} x2={w - padR} y1={y} y2={y} stroke="rgba(136,146,170,.14)" strokeDasharray="5 5" />
                <text x={padL - 8} y={y + 3} textAnchor="end" fontSize="8.5" fill="rgba(147,164,193,.85)">{tick}</text>
              </g>
            )
          })}
          <polyline points={line} fill="none" stroke="#22c55e" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          {points.map(p => (
            <g key={p.d.year}>
              <title>{`${p.d.year}: ${p.d.volumes.toLocaleString('vi-VN')} ${vi ? 'tập' : 'volumes'}`}</title>
              <circle cx={p.x} cy={p.y} r="3" fill="#bbf7d0" stroke="#22c55e" strokeWidth="1.6" />
              <text x={p.x} y={h - 5} textAnchor="middle" fontSize="8.5" fill="rgba(232,236,244,.55)">{p.d.year}</text>
            </g>
          ))}
        </svg>
      </div>
    </Card>
  )
}

function buildHeatmap(rows: VolumeReleaseRow[]) {
  const map = new Map<string, HeatmapRow>()
  for (const row of rows) {
    const d = new Date(row.release_date)
    if (Number.isNaN(d.getTime())) continue
    const monthKey = String(d.getMonth()).padStart(2, '0')
    const monthLabel = d.toLocaleString('en-US', { month: 'short' })
    const publisher = row.publisher || 'Unknown'
    const key = `${publisher}|${monthKey}`
    const prev = map.get(key) || { publisher, monthKey, monthLabel, count: 0 }
    prev.count += 1
    map.set(key, prev)
  }
  return Array.from(map.values()).sort((a, b) => a.monthKey.localeCompare(b.monthKey) || a.publisher.localeCompare(b.publisher))
}

function Heatmap({ rows, volumeRows, vi }: { rows: LNRow[]; volumeRows: VolumeReleaseRow[]; vi: boolean }) {
  const [selectedYears, setSelectedYears] = useState<number[]>([])
  const years = availableReleaseYears(volumeRows)
  const filteredVolumes = filterVolumeRowsByYears(volumeRows, selectedYears)
  const data = buildHeatmap(filteredVolumes)
  const publishers = buildPublishers(rows, filteredVolumes).filter(p => p.releases24 > 0).slice(0, 6).map(p => p.publisher)
  const months = Array.from({ length: 12 }, (_, month) => [
    String(month).padStart(2, '0'),
    new Date(2020, month, 1).toLocaleString('en-US', { month: 'short' }),
  ] as const)
  const monthGrid = '74px repeat(12, 1fr)'
  const max = Math.max(...data.map(d => d.count), 1)
  const lookup = new Map(data.map(d => [`${d.publisher}|${d.monthKey}`, d.count]))

  return (
    <Card className="p-3 h-[226px] overflow-visible">
      <div className="flex items-center justify-between mb-2">
        <div>
          <p className="text-[11px] font-black uppercase tracking-wide" style={{ color: 'var(--foreground)' }}>{vi ? 'Hoạt động phát hành theo nhà PH' : 'Publisher Release Activity'}</p>
          <p className="text-[10px]" style={{ color: 'var(--foreground-muted)' }}>{vi ? 'Đếm số tập thật từ volumes theo tháng và năm đã chọn.' : 'Counts real volume rows from volumes by selected month/year.'}</p>
        </div>
        <div className="flex items-center gap-2 min-w-0">
          <YearFilter years={years} selectedYears={selectedYears} setSelectedYears={setSelectedYears} vi={vi} />
          <BarChart3 className="w-4 h-4 shrink-0" style={{ color: '#ec4899' }} />
        </div>
      </div>

      <div className="overflow-x-auto">
        <div style={{ minWidth: `${Math.max(350, 74 + 12 * 34)}px` }}>
          <div className="grid gap-1 mb-1" style={{ gridTemplateColumns: monthGrid }}>
            <div />
            {months.map(([key, label]) => (
              <div key={key} className="text-[8px] text-center" style={{ color: 'var(--foreground-muted)' }}>{label}</div>
            ))}
          </div>

          <div className="space-y-1">
            {publishers.map(pub => (
              <div key={pub} className="grid gap-1 items-center" style={{ gridTemplateColumns: monthGrid }}>
                <div className="text-[10px] truncate pr-1 font-semibold" style={{ color: 'var(--foreground-secondary)' }}>{pub}</div>
                {months.map(([key]) => {
                  const v = lookup.get(`${pub}|${key}`) || 0
                  const alpha = v === 0 ? .08 : .18 + v / max * .76
                  return <div key={key} title={`${pub}: ${v.toLocaleString('vi-VN')} ${vi ? 'tập' : 'volumes'}`} className="h-5 rounded-sm" style={{ background: `rgba(124,106,245,${alpha})`, border: '1px solid rgba(255,255,255,.04)' }} />
                })}
              </div>
            ))}
          </div>

          <div className="flex items-center gap-2 mt-2 pl-[74px]">
            <span className="text-[9px]" style={{ color: 'var(--foreground-muted)' }}>0</span>
            <div className="h-2 flex-1 rounded-full" style={{ background: 'linear-gradient(90deg,rgba(124,106,245,.18),#3b82f6,#22c5b8)' }} />
            <span className="text-[9px]" style={{ color: 'var(--foreground-muted)' }}>{max}+</span>
          </div>
        </div>
      </div>
    </Card>
  )
}

function scoreTooltip(row: LNRow) {
  const parts = String(row.score_components || row.evaluation_basis || '').split('\n').filter(Boolean)
  return [
    `Điểm LN: ${row.ln_score.toFixed(1)}/10`,
    `Tập mới nhất: ${row.months_since_last_release == null ? 'không rõ' : '~' + row.months_since_last_release.toFixed(1) + ' tháng trước'}`,
    `Nhịp ra tập TB: ${row.average_gap_months == null ? 'chưa đủ dữ liệu' : '~' + row.average_gap_months.toFixed(1) + ' tháng/tập'}`,
    `Nhà phát hành: ${row.publisher || '—'} (${row.publisher_activity || 'không rõ'})`,
    '',
    'Thành phần điểm:',
    ...(parts.length ? parts : ['Không có breakdown chi tiết.']),
  ].join('\n')
}

function dropTooltip(row: LNRow) {
  const parts = String(row.drop_components || row.drop_basis || '').split('\n').filter(Boolean)
  return [
    `Khả năng drop: ${fmtPercent(row.drop_percent)}`,
    `Điểm LN liên quan: ${row.ln_score.toFixed(1)}/10`,
    `Khung đánh giá: ${evalLabel(row.evalution)}`,
    '',
    'Thành phần rủi ro:',
    ...(parts.length ? parts : ['Không có breakdown chi tiết.']),
  ].join('\n')
}

async function loadNovelVolumeReleases(dashboardRows: LNRow[]): Promise<VolumeReleaseRow[]> {
  const publisherBySeries = new Map<number, string>()
  let seriesIds = Array.from(new Set(dashboardRows.map(row => {
    if (!row.lidex_series_id) return null
    publisherBySeries.set(row.lidex_series_id, row.publisher || 'Unknown')
    return row.lidex_series_id
  }).filter((id): id is number => Boolean(id))))

  if (seriesIds.length === 0) {
    const { data: seriesData, error: seriesError } = await supabase
      .from('series')
      .select('id, publisher')
      .eq('item_type', 'novel')
      .not('genres', 'cs', '{"Hentai"}')

    if (seriesError || !seriesData) {
      console.warn('[Dashboard] novel series fetch failed:', seriesError?.message)
      return []
    }

    seriesIds = seriesData.map((series: any) => {
      const id = Number(series.id)
      publisherBySeries.set(id, series.publisher || 'Unknown')
      return id
    }).filter(Boolean)
  }

  const releases: VolumeReleaseRow[] = []
  const batchSize = 200
  for (let i = 0; i < seriesIds.length; i += batchSize) {
    const chunk = seriesIds.slice(i, i + batchSize)
    const { data: volumeData, error: volumeError } = await supabase
      .from('volumes')
      .select('series_id, release_date, is_special')
      .in('series_id', chunk)
      .not('release_date', 'is', null)
      .limit(10000)

    if (volumeError) {
      console.warn('[Dashboard] volume fetch failed:', volumeError.message)
      continue
    }

    for (const volume of volumeData || []) {
      const special = (volume as any).is_special
      if (special === true || String(special).toLowerCase() === 'true') continue
      const seriesId = Number((volume as any).series_id)
      releases.push({
        series_id: seriesId,
        publisher: publisherBySeries.get(seriesId) || 'Unknown',
        release_date: String((volume as any).release_date).slice(0, 10),
      })
    }
  }

  return releases
}

function LNWatchlist({ rows, onSelect, vi }: { rows: LNRow[]; onSelect: (row: LNRow) => void; vi: boolean }) {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [publisher, setPublisher] = useState('')
  const [releaseStatusFilter, setReleaseStatusFilter] = useState('')
  const [sortBy, setSortBy] = useState('scoreRelease')
  const [filtersOpen, setFiltersOpen] = useState(false)

  const statuses = useMemo(() => Array.from(new Set(rows.map(d => d.evalution).filter((v): v is string => Boolean(v))))
    .sort((a, b) => EVAL_ORDER.indexOf(a) - EVAL_ORDER.indexOf(b)), [rows])
  const publishers = useMemo(() => Array.from(new Set(rows.map(d => d.publisher).filter((v): v is string => Boolean(v)))).sort(), [rows])

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim()
    const base = rows.filter(r => {
      const rs = releaseStatus(r)
      const blob = `${r.series_title} ${r.publisher} ${r.series_code} ${r.evalution} ${rs}`.toLowerCase()
      return (
        (!q || blob.includes(q)) &&
        (!status || r.evalution === status) &&
        (!publisher || r.publisher === publisher) &&
        (!releaseStatusFilter || rs === releaseStatusFilter)
      )
    })

    const withReleaseStatusPriority = (comparator: (a: LNRow, b: LNRow) => number) => (a: LNRow, b: LNRow) => {
      if (!releaseStatusFilter) {
        const statusDiff = releaseStatusPriority(a) - releaseStatusPriority(b)
        if (statusDiff !== 0) return statusDiff
      }
      return comparator(a, b)
    }

    const latest = (a: LNRow, b: LNRow) => String(b.max_release_at || '').localeCompare(String(a.max_release_at || ''))
    const sorters: Record<string, (a: LNRow, b: LNRow) => number> = {
      rank: withReleaseStatusPriority((a, b) => a.raw_rank - b.raw_rank),
      scoreRelease: withReleaseStatusPriority((a, b) => (b.ln_score - a.ln_score) || latest(a, b)),
      scoreDesc: withReleaseStatusPriority((a, b) => b.ln_score - a.ln_score),
      scoreAsc: withReleaseStatusPriority((a, b) => a.ln_score - b.ln_score),
      releaseDesc: withReleaseStatusPriority(latest),
      viewsDesc: withReleaseStatusPriority((a, b) => b.average_view_count - a.average_view_count),
      volumesDesc: withReleaseStatusPriority((a, b) => b.number_of_volumes - a.number_of_volumes),
      dropRiskDesc: withReleaseStatusPriority((a, b) => pctValue(b.drop_percent) - pctValue(a.drop_percent)),
      releaseStatus: (a, b) => (releaseStatusPriority(a) - releaseStatusPriority(b)) || (b.ln_score - a.ln_score) || latest(a, b),
    }

    return [...base].sort(sorters[sortBy] || sorters.scoreRelease)
  }, [rows, search, status, publisher, releaseStatusFilter, sortBy])

  const avg = filtered.length ? filtered.reduce((s, r) => s + r.ln_score, 0) / filtered.length : 0
  const good = filtered.filter(r => ['Good', 'Completed'].includes(r.evalution || '')).length
  const risky = filtered.filter(r => ['Dead', 'Dropped'].includes(r.evalution || '')).length
  const completed = filtered.filter(r => r.evalution === 'Completed').length
  const activeFilterCount = [status, publisher, releaseStatusFilter].filter(Boolean).length

  const stats = [
    [vi ? 'Series hiển thị' : 'Visible Series', filtered.length],
    [vi ? 'Điểm TB' : 'Avg Score', avg.toFixed(1)],
    [vi ? 'Tốt/Hoàn thành' : 'Good/Completed', good],
    [vi ? 'Gần chết/Đã drop' : 'Inactive/Dropped', risky],
    [vi ? 'Hoàn thành' : 'Completed', completed],
  ]

  return (
    <div className="space-y-3">
      <header className="text-center">
        <p className="text-[10px] font-black uppercase tracking-[.15em] mb-2 inline-flex items-center justify-center gap-2" style={{ color: '#7c6af5' }}>
          <span className="w-5 h-0.5 rounded-full" style={{ background: '#7c6af5' }} />
          {vi ? 'Vietnamese Light Novel DOA' : 'Vietnamese Light Novel DOA'}
        </p>
        <h2 className="text-xl sm:text-3xl font-black tracking-tight" style={{ color: 'var(--foreground)' }}>{vi ? 'Bảng xếp hạng Light Novel Việt Nam Ded or Alive' : 'Vietnamese Light Novel Ded or Alive Ranking'}</h2>
        <p className="text-xs mt-2 max-w-3xl mx-auto" style={{ color: 'var(--foreground-muted)' }}>{vi ? 'Xếp hạng theo Điểm LN, ngày phát hành gần nhất, tình trạng phát hành tại Việt Nam và khả năng bị drop.' : 'Ranked by LN Score, latest release date, Vietnamese release status, and drop risk.'}</p>
      </header>

      <div className="flex sm:grid sm:grid-cols-5 gap-2 overflow-x-auto pb-1">
        {stats.map(([label, value]) => (
          <div key={label} className="min-w-[106px] rounded-xl p-3 relative overflow-hidden" style={{ background: 'var(--ln-panel-bg-strong)', border: '1px solid var(--card-border)' }}>
            <div className="absolute top-0 left-0 right-0 h-0.5" style={{ background: 'rgba(124,106,245,.60)' }} />
            <p className="text-[8.5px] font-black uppercase tracking-[.12em]" style={{ color: 'var(--foreground-muted)' }}>{label}</p>
            <p className="text-xl font-black mt-1" style={{ color: 'var(--foreground)' }}>{String(value)}</p>
          </div>
        ))}
      </div>

      <div className="sticky top-0 z-20 rounded-xl p-3 backdrop-blur-xl" style={{ background: 'var(--ln-panel-bg-strong)', border: '1px solid var(--card-border)' }}>
        <div className="flex flex-wrap gap-2 items-center">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: 'var(--foreground-muted)' }} />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder={vi ? 'Tìm tên truyện, nhà phát hành, mã series...' : 'Search title, publisher, series code...'}
              className="w-full pl-8 pr-3 py-2 rounded-lg text-xs outline-none"
              style={{ background: 'var(--ln-control-bg)', color: 'var(--foreground)', border: '1px solid var(--card-border)' }}
            />
          </div>

          <button
            onClick={() => setFiltersOpen(v => !v)}
            className="md:hidden flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-black"
            style={{
              background: 'var(--ln-control-bg)',
              color: activeFilterCount ? '#7c6af5' : 'var(--foreground-muted)',
              border: `1px solid ${activeFilterCount ? 'rgba(124,106,245,.6)' : 'var(--card-border)'}`,
            }}
          >
            <ListFilter className="w-3.5 h-3.5" />
            {vi ? 'Lọc' : 'Filters'}
            {activeFilterCount > 0 && <span className="rounded-full px-1.5 text-[10px]" style={{ background: '#7c6af5', color: '#fff' }}>{activeFilterCount}</span>}
          </button>

          <div className={`${filtersOpen ? 'flex' : 'hidden'} md:flex flex-col md:flex-row gap-2 w-full md:w-auto`}>
            <select value={status} onChange={e => setStatus(e.target.value)} className="px-3 py-2 rounded-lg text-xs font-semibold outline-none min-w-[140px]" style={{ background: 'var(--ln-control-bg)', color: 'var(--foreground)', border: '1px solid var(--card-border)' }}>
              <option value="">{vi ? 'Tất cả đánh giá' : 'All evaluations'}</option>
              {statuses.map(s => <option key={s} value={s}>{evalLabel(s, vi)}</option>)}
            </select>
            <select value={publisher} onChange={e => setPublisher(e.target.value)} className="px-3 py-2 rounded-lg text-xs font-semibold outline-none min-w-[150px]" style={{ background: 'var(--ln-control-bg)', color: 'var(--foreground)', border: '1px solid var(--card-border)' }}>
              <option value="">{vi ? 'Tất cả nhà phát hành' : 'All publishers'}</option>
              {publishers.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
            <select value={releaseStatusFilter} onChange={e => setReleaseStatusFilter(e.target.value)} className="px-3 py-2 rounded-lg text-xs font-semibold outline-none min-w-[150px]" style={{ background: 'var(--ln-control-bg)', color: 'var(--foreground)', border: '1px solid var(--card-border)' }}>
              <option value="">{vi ? 'Tất cả trạng thái' : 'All statuses'}</option>
              <option value="Đang phát hành">{releaseStatusLabel('Đang phát hành', vi)}</option>
              <option value="Lâu lắm rồi chưa có tập mới">{releaseStatusLabel('Lâu lắm rồi chưa có tập mới', vi)}</option>
              <option value="Đã bắt kịp bản gốc JP">{releaseStatusLabel('Đã bắt kịp bản gốc JP', vi)}</option>
              <option value="Drop">{releaseStatusLabel('Drop', vi)}</option>
              <option value="Hoàn thành">{releaseStatusLabel('Hoàn thành', vi)}</option>
            </select>
            <select value={sortBy} onChange={e => setSortBy(e.target.value)} className="px-3 py-2 rounded-lg text-xs font-semibold outline-none min-w-[150px]" style={{ background: 'var(--ln-control-bg)', color: 'var(--foreground)', border: '1px solid var(--card-border)' }}>
              <option value="scoreRelease">{vi ? 'Điểm LN → Ngày ra' : 'LN Score → Release date'}</option>
              <option value="rank">{vi ? 'Xếp hạng gốc' : 'Original rank'}</option>
              <option value="scoreDesc">{vi ? 'Điểm cao → thấp' : 'Score high → low'}</option>
              <option value="scoreAsc">{vi ? 'Điểm thấp → cao' : 'Score low → high'}</option>
              <option value="releaseDesc">{vi ? 'Phát hành mới nhất' : 'Latest release'}</option>
              <option value="viewsDesc">{vi ? 'Lượt xem TB' : 'Average views'}</option>
              <option value="volumesDesc">{vi ? 'Số tập VN' : 'VN volumes'}</option>
              <option value="dropRiskDesc">{vi ? 'Drop cao → thấp' : 'Drop high → low'}</option>
            </select>
          </div>
        </div>
      </div>

      <div className="rounded-xl overflow-hidden" style={{ background: 'var(--ln-panel-bg-strong)', border: '1px solid var(--card-border)' }}>
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full min-w-[1120px] text-[12px] border-collapse">
            <thead style={{ background: 'var(--ln-control-bg)' }}>
              <tr style={{ color: 'var(--foreground-muted)', borderBottom: '1px solid rgba(136,146,170,.18)' }}>
                {(vi
                  ? ['Hạng', 'Series', 'Số tập', 'Ngày phát hành gần nhất', 'Nhà PH', 'Trạng thái', 'Điểm đánh giá', 'Khả năng drop', 'Đánh giá']
                  : ['Rank', 'Series', 'Volumes', 'Latest release', 'Publisher', 'Status', 'LN Score', 'Drop risk', 'Evaluation']
                ).map((h, i) => (
                  <th key={h} className={`${i === 0 ? 'text-center' : 'text-left'} font-black uppercase tracking-widest py-2.5 px-3 whitespace-nowrap`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={9} className="text-center py-10" style={{ color: 'var(--foreground-muted)' }}>{vi ? 'Không có series nào phù hợp với bộ lọc.' : 'No series match the current filters.'}</td></tr>
              ) : filtered.map((row, idx) => {
                const scoreBar = Math.max(0, Math.min(100, row.ln_score * 10))
                const riskBar = Math.max(0, Math.min(100, pctValue(row.drop_percent)))
                const rankBg = idx === 0 ? 'linear-gradient(135deg,#f6d860,#e8a800)' : idx === 1 ? 'linear-gradient(135deg,#d8dde8,#a5afc0)' : idx === 2 ? 'linear-gradient(135deg,#e8a86e,#c47730)' : 'var(--ln-muted-bg)'
                const rankColor = idx <= 2 ? '#161616' : 'var(--foreground-muted)'
                const rsStyle = releaseStatusStyle(row)
                const evalColor = statusColors[row.evalution || ''] || '#94a3b8'
                return (
                  <tr key={row.series_key} style={{ borderBottom: '1px solid var(--ln-row-border)' }}>
                    <td className="py-2.5 px-3 text-center"><span className="inline-flex items-center justify-center min-w-[34px] h-[34px] rounded-lg font-black text-[11px]" style={{ background: rankBg, color: rankColor }}>#{idx + 1}</span></td>
                    <td className="py-2.5 px-3">
                      <div className="flex items-center gap-3 min-w-[300px]">
                        {row.cover_url ? <img src={proxyImg(row.cover_url) || ''} alt="" className="w-[64px] h-[90px] object-cover rounded-lg shrink-0 shadow-lg" /> : <div className="w-[64px] h-[90px] rounded-lg shrink-0" style={{ background: 'rgba(124,106,245,.14)' }} />}
                        <div className="min-w-0">
                          <p className="font-black leading-snug line-clamp-2 max-w-[340px]" style={{ color: 'var(--foreground)' }}>{row.series_title}</p>
                          <p className="text-[10px] mt-1 font-semibold" style={{ color: 'var(--foreground-muted)' }}>ID {row.lidex_series_id || row.series_id || '—'} · {row.series_code || '—'}</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 tabular-nums" style={{ color: 'var(--foreground-secondary)' }}>{fmtNum(row.number_of_volumes, 0)}</td>
                    <td className="py-2.5 px-3 tabular-nums" style={{ color: 'var(--foreground-secondary)' }}>{fmtDate(row.max_release_at)}</td>
                    <td className="py-2.5 px-3" style={{ color: 'var(--foreground-secondary)' }}>{row.publisher || '—'}</td>
                    <td className="py-2.5 px-3"><span className="inline-flex rounded-full px-2.5 py-1 text-[10px] font-black whitespace-nowrap" style={{ color: rsStyle.color, background: rsStyle.bg, border: `1px solid ${rsStyle.border}` }}>{releaseStatusLabel(releaseStatus(row), vi)}</span></td>
                    <td className="py-2.5 px-3">
                      <div title={scoreTooltip(row)} className="cursor-help">
                        <p className="text-lg font-black leading-none" style={{ color: scoreColor(row.ln_score) }}>{row.ln_score.toFixed(1)}</p>
                        <div className="w-[68px] h-1 rounded-full mt-1 overflow-hidden" style={{ background: 'var(--ln-track-bg)' }}><div className="h-full rounded-full" style={{ width: `${scoreBar}%`, background: 'linear-gradient(90deg,#ef4444 0%,#eab308 50%,#22c55e 100%)' }} /></div>
                      </div>
                    </td>
                    <td className="py-2.5 px-3">
                      <div title={dropTooltip(row)} className="cursor-help">
                        <p className="text-sm font-black leading-none" style={{ color: dropColor(row.drop_percent) }}>{fmtPercent(row.drop_percent)}</p>
                        <div className="w-[68px] h-1 rounded-full mt-1 overflow-hidden" style={{ background: 'var(--ln-track-bg)' }}><div className="h-full rounded-full" style={{ width: `${riskBar}%`, background: 'linear-gradient(90deg,#22c55e 0%,#eab308 40%,#ef4444 80%)' }} /></div>
                      </div>
                    </td>
                    <td className="py-2.5 px-3"><span className="inline-flex rounded-full px-2.5 py-1 text-[10px] font-black whitespace-nowrap" style={{ color: evalColor, background: `${evalColor}20`, border: `1px solid ${evalColor}40` }}>{evalLabel(row.evalution, vi)}</span></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <div className="md:hidden">
          {filtered.map((row, idx) => {
            const scoreBar = Math.max(0, Math.min(100, row.ln_score * 10))
            const riskBar = Math.max(0, Math.min(100, pctValue(row.drop_percent)))
            const rsStyle = releaseStatusStyle(row)
            const evalColor = statusColors[row.evalution || ''] || '#94a3b8'
            const rankBg = idx === 0 ? 'linear-gradient(135deg,#f6d860,#e8a800)' : idx === 1 ? 'linear-gradient(135deg,#d8dde8,#a5afc0)' : idx === 2 ? 'linear-gradient(135deg,#e8a86e,#c47730)' : 'var(--ln-muted-bg)'
            return (
              <div key={row.series_key} className="p-3" style={{ borderBottom: '1px solid var(--ln-row-border)' }}>
                <div className="flex gap-3">
                  <div className="w-8 shrink-0 pt-1"><span className="inline-flex items-center justify-center w-8 h-8 rounded-lg font-black text-[10px]" style={{ background: rankBg, color: idx <= 2 ? '#161616' : 'var(--foreground-muted)' }}>#{idx + 1}</span></div>
                  {row.cover_url ? <img src={proxyImg(row.cover_url) || ''} alt="" className="w-[104px] h-[148px] object-cover rounded-lg shrink-0 shadow-lg" /> : <div className="w-[104px] h-[148px] rounded-lg shrink-0" style={{ background: 'rgba(124,106,245,.14)' }} />}
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-black leading-snug line-clamp-4" style={{ color: 'var(--foreground)' }}>{row.series_title}</p>
                    <p className="text-[10px] mt-1 font-semibold" style={{ color: 'var(--foreground-muted)' }}>ID {row.lidex_series_id || row.series_id || '—'} · {row.series_code || '—'}</p>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      <span className="text-[10px] font-bold px-2 py-1 rounded-md" style={{ color: 'var(--foreground-muted)', background: 'var(--ln-muted-bg)' }}>{row.publisher || '—'}</span>
                      <span className="text-[10px] font-bold px-2 py-1 rounded-md" style={{ color: 'var(--foreground-muted)', background: 'var(--ln-muted-bg)' }}>{fmtDate(row.max_release_at)}</span>
                    </div>
                  </div>
                </div>

                <div className="pl-11 mt-2 flex flex-wrap gap-1.5">
                  <span className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5" style={{ background: 'var(--ln-control-bg)', border: '1px solid var(--card-border)' }}>
                    <span className="text-[9px] font-black uppercase" style={{ color: 'var(--foreground-muted)' }}>{vi ? 'Điểm' : 'Score'}</span>
                    <strong className="text-xs font-black" style={{ color: scoreColor(row.ln_score) }}>{row.ln_score.toFixed(1)}</strong>
                    <span className="w-10 h-1 rounded-full overflow-hidden" style={{ background: 'var(--ln-track-bg)' }}><span className="block h-full rounded-full" style={{ width: `${scoreBar}%`, background: 'linear-gradient(90deg,#ef4444 0%,#eab308 50%,#22c55e 100%)' }} /></span>
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5" style={{ background: 'var(--ln-control-bg)', border: '1px solid var(--card-border)' }}>
                    <span className="text-[9px] font-black uppercase" style={{ color: 'var(--foreground-muted)' }}>Drop</span>
                    <strong className="text-xs font-black" style={{ color: dropColor(row.drop_percent) }}>{fmtPercent(row.drop_percent)}</strong>
                    <span className="w-10 h-1 rounded-full overflow-hidden" style={{ background: 'var(--ln-track-bg)' }}><span className="block h-full rounded-full" style={{ width: `${riskBar}%`, background: 'linear-gradient(90deg,#22c55e 0%,#eab308 40%,#ef4444 80%)' }} /></span>
                  </span>
                  <span className="inline-flex rounded-lg px-2.5 py-1.5 text-[10px] font-black" style={{ color: evalColor, background: `${evalColor}20`, border: `1px solid ${evalColor}40` }}>{evalLabel(row.evalution, vi)}</span>
                  <span className="inline-flex rounded-lg px-2.5 py-1.5 text-[10px] font-black" style={{ color: rsStyle.color, background: rsStyle.bg, border: `1px solid ${rsStyle.border}` }}>{releaseStatusLabel(releaseStatus(row), vi)}</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { locale } = useLocale()
  const vi = locale === 'vi'
  const [mode, setMode] = useState<Mode>('dashboard')
  const [rows, setRows] = useState<LNRow[]>([])
  const [volumeRows, setVolumeRows] = useState<VolumeReleaseRow[]>([])
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)

    const { data, error } = await supabase
      .from('ln_series_ranking')
      .select('*')
      .order('ln_score', { ascending: false })
      .order('max_release_at', { ascending: false })

    if (error) {
      setError(error.message)
      setLoading(false)
      return
    }

    const mapped = mapRows((data || []) as RawRankingRow[])
    const hydrated = await hydrateRowsWithCanonicalSeries(mapped)
    const volumeReleases = await loadNovelVolumeReleases(hydrated)
    setRows(hydrated)
    setVolumeRows(volumeReleases)
    setSelectedKey((hydrated.find(r => r.evalution === 'Good') || hydrated[0])?.series_key || null)
    setLoading(false)
  }

  useEffect(() => {
    load()
  }, [])

  const selected = useMemo(() => rows.find(r => r.series_key === selectedKey) || rows[0] || null, [rows, selectedKey])

  return (
    <div className="min-h-screen relative overflow-hidden" style={{ background: 'var(--background)' }}>
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute -top-40 left-20 w-96 h-96 rounded-full blur-3xl" style={{ background: 'rgba(124,106,245,.10)' }} />
        <div className="absolute top-48 right-0 w-96 h-96 rounded-full blur-3xl" style={{ background: 'rgba(236,72,153,.07)' }} />
      </div>

      <div className="relative max-w-[1440px] mx-auto px-3 sm:px-4 lg:px-6 py-4 sm:py-5">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3 mb-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-lg px-2.5 py-1 mb-2" style={{ background: 'rgba(124,106,245,.12)', border: '1px solid rgba(124,106,245,.22)' }}>
              <Sparkles className="w-3 h-3" style={{ color: '#a78bfa' }} />
              <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: '#a78bfa' }}>
                {vi ? 'Thị trường Light Novel Việt Nam' : 'Vietnamese Light Novel Market'}
              </span>
            </div>
            <h1 className="text-2xl sm:text-4xl font-black tracking-tight" style={{ color: 'var(--foreground)' }}>LN Market Analytics</h1>
            <p className="text-xs sm:text-sm mt-1.5 max-w-2xl" style={{ color: 'var(--foreground-secondary)' }}>
              {vi ? 'ln_series_ranking cho điểm/rủi ro; series + volumes cho liên kết và hoạt động phát hành.' : 'ln_series_ranking powers score/risk; series + volumes power links and release activity.'}
            </p>
          </div>

          <div className="flex items-center gap-2 self-start">
            <ModeSwitch mode={mode} setMode={setMode} vi={vi} />
            <button onClick={load} className="p-1.5 rounded-lg transition-all hover:scale-110" style={{ background: 'var(--glass-bg)', border: '1px solid var(--card-border)' }} title={vi ? 'Làm mới' : 'Refresh'}>
              <RefreshCw className="w-4 h-4" style={{ color: 'var(--foreground-secondary)' }} />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="h-[60vh] flex items-center justify-center">
            <div className="flex items-center gap-3 text-sm" style={{ color: 'var(--foreground-secondary)' }}>
              <Loader2 className="w-5 h-5 animate-spin" />
              {vi ? 'Đang tải phân tích thị trường LN...' : 'Loading LN market analytics...'}
            </div>
          </div>
        ) : error ? (
          <Card className="p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 mt-0.5" style={{ color: '#f59e0b' }} />
              <div>
                <p className="font-bold" style={{ color: 'var(--foreground)' }}>{vi ? 'Không tải được dữ liệu dashboard' : 'Dashboard data failed to load'}</p>
                <p className="text-sm mt-1" style={{ color: 'var(--foreground-secondary)' }}>{error}</p>
              </div>
            </div>
          </Card>
        ) : mode === 'watchlist' ? (
          <LNWatchlist rows={rows} vi={vi} onSelect={(row) => { setSelectedKey(row.series_key); setMode('dashboard'); window.scrollTo({ top: 0, behavior: 'smooth' }) }} />
        ) : (
          <div className="space-y-4">
            <KpiStrip rows={rows} vi={vi} />

            <div className="grid grid-cols-1 xl:grid-cols-[1.7fr_0.9fr] gap-4">
              <ScatterPlot rows={rows} selectedKey={selectedKey} vi={vi} onSelect={row => setSelectedKey(row.series_key)} />
              <RadarChart row={selected} vi={vi} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <PublisherLeaderboard rows={rows} volumeRows={volumeRows} vi={vi} />
              <GrowthChart volumeRows={volumeRows} vi={vi} />
              <Heatmap rows={rows} volumeRows={volumeRows} vi={vi} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
