import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Box, Button, Typography, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Chip, Tooltip, Collapse, Slider,
} from '@mui/material';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { SearchOff, ExpandMore, ExpandLess } from '@mui/icons-material';
import { API_BASE } from '../utils/apiConfig';

dayjs.extend(relativeTime);

// ── Types ─────────────────────────────────────────────────────────────────────

interface BookOdds { over: string; under: string; }

interface FuturesRow {
  team:           string;
  sport:          string;
  line:           number;
  direction:      string;
  betbck_odds:    string;
  fd_odds:        string;
  dk_odds:        string;
  mgm_odds:       string;
  consensus_fair: string;
  ev:             string;
  ev_float:       number;
  sharp_books:    string;
  signal_count:   number;
  per_book_ev:    Record<string, number>;
  all_book_odds?: Record<string, BookOdds>;
  is_arb?:        boolean;
  arb_book?:      string;
  arb_opp_odds?:  string;
  arb_roi?:       number | null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const BOOKS = ['FD', 'DK', 'MGM'] as const;

const mono = {
  fontFamily: '"JetBrains Mono","Fira Code",monospace',
  fontVariantNumeric: 'tabular-nums' as const,
};

function fmtOdds(o?: string) {
  if (!o || o === 'N/A') return '—';
  return o;
}

function OddsCell({ odds, evFloat }: { odds: string; evFloat?: number }) {
  const na    = !odds || odds === 'N/A';
  const posEv = !na && evFloat !== undefined && evFloat > 0;
  return (
    <span style={{
      ...mono,
      fontSize: '0.8rem',
      color:  na ? '#374151' : posEv ? '#4ADE80' : '#D1D5DB',
      fontWeight: posEv ? 600 : 400,
    }}>
      {na ? '—' : odds}
    </span>
  );
}

/** Three 8-px signal dots: green = +EV for that book, grey = line exists, hollow = no line */
function SignalDots({ row }: { row: FuturesRow }) {
  const oddsOf: Record<typeof BOOKS[number], string> = {
    FD: row.fd_odds, DK: row.dk_odds, MGM: row.mgm_odds,
  };
  return (
    <Box sx={{ display: 'flex', gap: '3px', alignItems: 'center' }}>
      {BOOKS.map(book => {
        const hasLine = oddsOf[book] && oddsOf[book] !== 'N/A';
        const evVal   = row.per_book_ev?.[book];
        const isPos   = hasLine && evVal !== undefined && evVal > 0;
        return (
          <Tooltip
            key={book}
            title={!hasLine ? `${book}: no line`
              : evVal !== undefined ? `${book}: ${evVal > 0 ? '+' : ''}${evVal.toFixed(1)}% EV`
              : `${book}: line available`}
            placement="top" arrow
          >
            <Box sx={{
              width: 8, height: 8, borderRadius: '50%', flexShrink: 0, cursor: 'default',
              bgcolor: !hasLine ? 'rgba(255,255,255,0.06)'
                : isPos ? '#32D74B' : 'rgba(255,255,255,0.2)',
              border: !hasLine ? '1px solid rgba(255,255,255,0.08)' : 'none',
            }} />
          </Tooltip>
        );
      })}
    </Box>
  );
}

/** Expanded row: shows Over/Under for all 4 books at a glance */
function ExpandPanel({ row }: { row: FuturesRow }) {
  const abo = row.all_book_odds ?? {};
  const books: { key: string; label: string }[] = [
    { key: 'Buckeye', label: 'Buckeye' },
    { key: 'FD',      label: 'FanDuel' },
    { key: 'DK',      label: 'DraftKings' },
    { key: 'MGM',     label: 'BetMGM' },
  ];

  return (
    <Box sx={{
      display: 'flex', gap: 2, px: 2, py: 1.5, flexWrap: 'wrap',
      bgcolor: 'rgba(255,255,255,0.02)',
      borderTop: '1px solid rgba(255,255,255,0.05)',
    }}>
      <Box sx={{ display: 'flex', alignItems: 'center', mr: 1 }}>
        <Typography sx={{ color: '#4B5563', fontSize: '0.7rem', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          {row.team} · {row.direction === 'Over' ? 'O' : 'U'} {row.line} · All book odds
        </Typography>
      </Box>
      {books.map(({ key, label }) => {
        const sides = abo[key];
        const hasAny = sides && (sides.over !== 'N/A' || sides.under !== 'N/A');
        return (
          <Box key={key} sx={{
            display: 'flex', flexDirection: 'column', gap: 0.25,
            minWidth: 80,
            opacity: hasAny ? 1 : 0.35,
          }}>
            <Typography sx={{ color: '#6B7280', fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              {label}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.1 }}>
                <Typography sx={{ color: '#374151', fontSize: '0.6rem' }}>Over</Typography>
                <Typography sx={{ ...mono, fontSize: '0.8125rem', color: '#E5E7EB', fontWeight: 500 }}>
                  {fmtOdds(sides?.over)}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.1 }}>
                <Typography sx={{ color: '#374151', fontSize: '0.6rem' }}>Under</Typography>
                <Typography sx={{ ...mono, fontSize: '0.8125rem', color: '#E5E7EB', fontWeight: 500 }}>
                  {fmtOdds(sides?.under)}
                </Typography>
              </Box>
            </Box>
          </Box>
        );
      })}
      {row.is_arb && row.arb_roi != null && (
        <Box sx={{ ml: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', justifyContent: 'center', gap: 0.25 }}>
          <Typography sx={{ color: '#FBB724', fontSize: '0.7rem', fontWeight: 700 }}>
            Arb vs {row.arb_book}: {row.arb_opp_odds}
          </Typography>
          <Typography sx={{ color: '#92400E', fontSize: '0.7rem' }}>
            Guaranteed +{row.arb_roi.toFixed(2)}% on balanced stakes
          </Typography>
        </Box>
      )}
    </Box>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

const FuturesScraper: React.FC = () => {
  const [markets, setMarkets]                   = useState<FuturesRow[]>([]);
  const [loading, setLoading]                   = useState(false);
  const [message, setMessage]                   = useState<string | null>(null);
  const [lastUpdate, setLastUpdate]             = useState<string | null>(null);
  const [pipelineRunning, setPipelineRunning]   = useState(false);
  const [expandedIdx, setExpandedIdx]           = useState<number | null>(null);

  // Filters
  const [sportFilter, setSportFilter]           = useState<'ALL'|'NFL'|'NCAAF'>('ALL');
  const [showOnlyPositive, setShowOnlyPositive] = useState(false);
  const [minSignal, setMinSignal]               = useState(0);
  const [evRange, setEvRange]                   = useState<[number, number]>([-30, 30]);
  const [showAll, setShowAll]                   = useState(false);

  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const isPolling  = useRef(false);
  const sseRef     = useRef<EventSource | null>(null);

  useEffect(() => { connectSSE(); fetchResults(); return () => { disconnectSSE(); stopPolling(); }; }, []); // eslint-disable-line

  // ── SSE ──────────────────────────────────────────────────────────────────
  const connectSSE = () => {
    if (sseRef.current) return;
    const es = new EventSource('/api/events/stream');
    sseRef.current = es;
    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'futures_update') {
          const { events, last_run, message: msg } = data.data;
          if (events?.length > 0) { setMarkets(events); setLastUpdate(last_run); }
          if (msg) setMessage(msg);
        } else if (data.type === 'futures_complete') {
          const { events, last_run, message: msg } = data.data;
          if (events?.length > 0) { setMarkets(events); setLastUpdate(last_run); }
          if (msg) setMessage(msg);
          setPipelineRunning(false); stopPolling();
        } else if (data.type === 'futures_error') {
          setPipelineRunning(false); stopPolling();
        }
      } catch {}
    };
    es.onerror = () => {};
  };
  const disconnectSSE = () => { sseRef.current?.close(); sseRef.current = null; };

  // ── Polling ───────────────────────────────────────────────────────────────
  const checkStatus = async () => {
    try {
      const res  = await fetch(`${API_BASE}/api/futures-pipeline-status`);
      const data = await res.json();
      if (data.status === 'success' && !data.data.running && data.data.task_done) {
        await fetchResults(); stopPolling();
      }
    } catch {}
  };
  const startPolling = () => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    setPipelineRunning(true);
    pollingRef.current = setInterval(() => {
      if (!isPolling.current) { isPolling.current = true; checkStatus().finally(() => { isPolling.current = false; }); }
    }, 2000);
  };
  const stopPolling = () => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = null; setPipelineRunning(false);
  };

  // ── API ───────────────────────────────────────────────────────────────────
  const fetchResults = async () => {
    try {
      const res  = await fetch(`${API_BASE}/buckeye/futures-results`);
      const data = await res.json();
      if (data.status === 'success') {
        setLastUpdate(data.data.last_update || null);
        setMarkets(data.data.markets || []);
      }
    } catch {}
  };

  const handleRun = async () => {
    if (pipelineRunning) return;
    setPipelineRunning(true); setLoading(true); setMessage(null); setMarkets([]); setExpandedIdx(null);
    try {
      const res  = await fetch(`${API_BASE}/api/run-futures-pipeline`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'success') { connectSSE(); startPolling(); }
      else { setPipelineRunning(false); }
    } catch { setPipelineRunning(false); }
    finally { setLoading(false); }
  };

  // ── Derived counts ────────────────────────────────────────────────────────
  const arbCount   = markets.filter(r => r.is_arb).length;
  const posEvCount = markets.filter(r => !r.is_arb && r.ev_float > 0).length;
  const nflCount   = markets.filter(r => r.sport === 'NFL').length;
  const ncaafCount = markets.filter(r => r.sport === 'NCAAF').length;

  const evMin = useMemo(() => Math.floor(Math.min(0, ...markets.map(r => r.ev_float))), [markets]);
  const evMax = useMemo(() => Math.ceil(Math.max(0, ...markets.map(r => r.ev_float))),  [markets]);

  // ── Filter ────────────────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    let rows = markets.filter(r => {
      if (r.is_arb) return showAll ? true : true; // arbs always included
      if (sportFilter !== 'ALL' && r.sport !== sportFilter) return false;
      if (showOnlyPositive && r.ev_float <= 0) return false;
      if (r.signal_count < minSignal) return false;
      if (r.ev_float < evRange[0] || r.ev_float > evRange[1]) return false;
      return true;
    });
    if (!showAll) rows = rows.filter(r => r.is_arb || r.ev_float > 0);
    return rows;
  }, [markets, sportFilter, showOnlyPositive, minSignal, evRange, showAll]);

  // ── Shared styles ──────────────────────────────────────────────────────────
  const hdr = {
    color: '#6B7280', fontWeight: 600, fontSize: '0.625rem',
    textTransform: 'uppercase' as const, letterSpacing: '0.08em', py: 1.25,
    borderBottom: '1px solid rgba(255,255,255,0.07)',
    bgcolor: 'rgba(0,0,0,0.3)',
  };
  const cell = { borderBottom: '1px solid rgba(255,255,255,0.04)', py: 0.875, verticalAlign: 'middle' };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      {/* ── Top toolbar (matches screenshot) ─────────────────────── */}
      <Box sx={{ display: 'flex', gap: 1, mb: 1.5, alignItems: 'center', flexWrap: 'wrap' }}>
        <Button
          variant="outlined" size="small" disabled={pipelineRunning || loading}
          onClick={handleRun}
          sx={{
            color: pipelineRunning ? '#32D74B' : '#9CA3AF',
            borderColor: pipelineRunning ? 'rgba(50,215,75,0.35)' : 'rgba(255,255,255,0.12)',
            bgcolor: pipelineRunning ? 'rgba(50,215,75,0.06)' : 'rgba(255,255,255,0.04)',
            borderRadius: '6px', fontWeight: 600, px: 2, fontSize: '0.75rem',
            height: 28, textTransform: 'none', minWidth: 'auto',
            '&:hover': { bgcolor: 'rgba(255,255,255,0.07)', borderColor: 'rgba(255,255,255,0.2)', color: '#F5F5F5' },
            '&.Mui-disabled': { color: pipelineRunning ? '#32D74B' : undefined, borderColor: pipelineRunning ? 'rgba(50,215,75,0.35)' : undefined, opacity: 1 },
          }}
        >
          {pipelineRunning ? '● Running…' : 'Run Futures'}
        </Button>

        {/* ARB / +EV count badges */}
        {arbCount > 0 && (
          <Chip label={`${arbCount} ARB`} size="small" onClick={() => { setSportFilter('ALL'); setShowAll(false); setShowOnlyPositive(false); setMinSignal(0); }} sx={{
            height: 24, fontSize: '0.7rem', fontWeight: 700, cursor: 'pointer',
            bgcolor: 'rgba(251,191,36,0.15)', color: '#FBB724',
            border: '1px solid rgba(251,191,36,0.3)', borderRadius: '5px',
            '& .MuiChip-label': { px: 1 },
          }} />
        )}
        {posEvCount > 0 && (
          <Chip label={`${posEvCount} +EV`} size="small" onClick={() => setShowOnlyPositive(v => !v)} sx={{
            height: 24, fontSize: '0.7rem', fontWeight: 700, cursor: 'pointer',
            bgcolor: showOnlyPositive ? 'rgba(50,215,75,0.18)' : 'rgba(50,215,75,0.08)',
            color: '#32D74B',
            border: `1px solid ${showOnlyPositive ? 'rgba(50,215,75,0.45)' : 'rgba(50,215,75,0.2)'}`,
            borderRadius: '5px', '& .MuiChip-label': { px: 1 },
          }} />
        )}

        {/* EV range slider */}
        {markets.length > 0 && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 160 }}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.2, width: 140 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography sx={{ color: '#6B7280', fontSize: '0.6rem' }}>EV Min</Typography>
                <Typography sx={{ color: '#6B7280', fontSize: '0.6rem' }}>Max</Typography>
              </Box>
              <Slider
                size="small" value={evRange}
                min={evMin} max={evMax} step={0.5}
                onChange={(_, v) => setEvRange(v as [number, number])}
                sx={{
                  color: '#4B5563', py: 0.5, height: 2,
                  '& .MuiSlider-thumb': { width: 10, height: 10 },
                  '& .MuiSlider-rail': { opacity: 0.3 },
                }}
              />
            </Box>
          </Box>
        )}

        {/* Show All toggle */}
        <Button size="small" onClick={() => setShowAll(v => !v)} sx={{
          minWidth: 0, px: 1.5, height: 28,
          fontSize: '0.7rem', fontWeight: 600, borderRadius: '6px',
          textTransform: 'none', border: '1px solid',
          color: showAll ? '#F5F5F5' : '#6B7280',
          borderColor: showAll ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.08)',
          bgcolor: showAll ? 'rgba(255,255,255,0.1)' : 'transparent',
          '&:hover': { bgcolor: 'rgba(255,255,255,0.07)' },
        }}>
          Show All
        </Button>

        <Box sx={{ flex: 1 }} />

        {lastUpdate && (
          <Typography sx={{ color: '#374151', fontSize: '0.7rem' }}>
            Last run: {dayjs(lastUpdate).format('H:mm:ss')} ({dayjs(lastUpdate).fromNow()})
          </Typography>
        )}
        {markets.length > 0 && (
          <Typography sx={{ color: '#374151', fontSize: '0.7rem' }}>
            Showing {filtered.length} of {markets.length} bets
          </Typography>
        )}
      </Box>

      {/* ── Pipeline data-source line ─────────────────────────────── */}
      {markets.length > 0 && !pipelineRunning && (
        <Box sx={{ display: 'flex', gap: 0.75, mb: 1.25, alignItems: 'center', flexWrap: 'wrap' }}>
          <Typography sx={{ color: '#374151', fontSize: '0.72rem' }}>✓</Typography>
          <Typography sx={{ color: '#4B5563', fontSize: '0.72rem' }}>
            Buckeye: {Math.round(markets.length / 2)} teams
            {' | '}FD: {markets.filter(r => r.fd_odds && r.fd_odds !== 'N/A').length > 0 ? `${Math.round(markets.filter(r => r.fd_odds && r.fd_odds !== 'N/A').length / 2)}` : 0}
            {' | '}DK: {Math.round(markets.filter(r => r.dk_odds && r.dk_odds !== 'N/A').length / 2)}
            {' | '}MGM: {Math.round(markets.filter(r => r.mgm_odds && r.mgm_odds !== 'N/A').length / 2)}
            {' | '}+EV: {posEvCount}
          </Typography>
        </Box>
      )}

      {/* ── Live progress ─────────────────────────────────────────── */}
      {pipelineRunning && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.25 }}>
          <Box sx={{
            '@keyframes fp': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.2 } },
            width: 6, height: 6, borderRadius: '50%', bgcolor: '#32D74B', flexShrink: 0,
            animation: 'fp 1.4s ease-in-out infinite',
          }} />
          <Typography sx={{ color: '#6B7280', fontSize: '0.75rem' }}>
            {message || 'Scraping Buckeye · FanDuel · DraftKings · BetMGM…'}
          </Typography>
        </Box>
      )}

      {/* ── Sport / signal / +EV filter bar ──────────────────────── */}
      <Box sx={{ display: 'flex', gap: 0.75, mb: 1.5, alignItems: 'center', flexWrap: 'wrap' }}>
        {(['ALL', 'NFL', 'NCAAF'] as const).map(s => (
          <Button key={s} size="small" onClick={() => setSportFilter(s)} sx={{
            minWidth: 0, px: 1.25, height: 26,
            fontSize: '0.7rem', fontWeight: 600,
            borderRadius: '5px', textTransform: 'none', border: '1px solid',
            color: sportFilter === s ? '#F5F5F5' : '#6B7280',
            borderColor: sportFilter === s ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.08)',
            bgcolor: sportFilter === s ? 'rgba(255,255,255,0.1)' : 'transparent',
            '&:hover': { bgcolor: 'rgba(255,255,255,0.07)' },
          }}>
            {s}{s === 'NFL' && nflCount > 0 ? ` (${nflCount})` : s === 'NCAAF' && ncaafCount > 0 ? ` (${ncaafCount})` : s === 'ALL' && markets.length > 0 ? ` (${markets.length})` : ''}
          </Button>
        ))}

        <Box sx={{ width: 1, height: 18, bgcolor: 'rgba(255,255,255,0.07)', mx: 0.25 }} />

        {[0, 1, 2, 3].map(n => (
          <Button key={n} size="small" onClick={() => setMinSignal(prev => prev === n ? 0 : n)} sx={{
            minWidth: 0, px: 1.25, height: 26,
            fontSize: '0.7rem', fontWeight: 600,
            borderRadius: '5px', textTransform: 'none', border: '1px solid',
            color: minSignal === n ? '#F5F5F5' : '#6B7280',
            borderColor: minSignal === n ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.08)',
            bgcolor: minSignal === n ? 'rgba(255,255,255,0.1)' : 'transparent',
            '&:hover': { bgcolor: 'rgba(255,255,255,0.07)' },
          }}>
            {n === 0 ? 'All signals' : `${n}+ books`}
          </Button>
        ))}

        <Box sx={{ width: 1, height: 18, bgcolor: 'rgba(255,255,255,0.07)', mx: 0.25 }} />

        <Button size="small" onClick={() => setShowOnlyPositive(v => !v)} sx={{
          minWidth: 0, px: 1.25, height: 26,
          fontSize: '0.7rem', fontWeight: 600,
          borderRadius: '5px', textTransform: 'none', border: '1px solid',
          color: showOnlyPositive ? '#32D74B' : '#6B7280',
          borderColor: showOnlyPositive ? 'rgba(50,215,75,0.35)' : 'rgba(255,255,255,0.08)',
          bgcolor: showOnlyPositive ? 'rgba(50,215,75,0.06)' : 'transparent',
          '&:hover': { bgcolor: 'rgba(255,255,255,0.07)' },
        }}>
          +EV only
        </Button>
      </Box>

      {/* ── Table ─────────────────────────────────────────────────── */}
      <TableContainer sx={{ background: 'transparent', borderRadius: 1.5, border: '1px solid rgba(255,255,255,0.07)' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ ...hdr, width: 36, pl: 1 }} />
              {/* Signal */}
              <TableCell sx={{ ...hdr, width: 48, pl: 0.5 }}>
                <Tooltip title="Green dot = +EV vs that book. FD · DK · MGM" placement="top" arrow>
                  <span style={{ cursor: 'help' }}>Sig</span>
                </Tooltip>
              </TableCell>
              <TableCell sx={{ ...hdr, width: 46 }}>Sport</TableCell>
              <TableCell sx={hdr}>Team</TableCell>
              <TableCell sx={hdr}>Bet</TableCell>
              <TableCell align="center" sx={{ ...hdr, width: 72 }}>
                <Tooltip title="Buckeye (BetBCK) — the book you're placing the bet with" placement="top" arrow>
                  <span style={{ cursor: 'help' }}>Buckeye</span>
                </Tooltip>
              </TableCell>
              <TableCell align="center" sx={{ ...hdr, width: 60 }}>FanDuel</TableCell>
              <TableCell align="center" sx={{ ...hdr, width: 60 }}>DraftKings</TableCell>
              <TableCell align="center" sx={{ ...hdr, width: 60 }}>BetMGM</TableCell>
              <TableCell align="center" sx={{ ...hdr, width: 62 }}>
                <Tooltip title="Consensus fair price — averaged devigged reference books" placement="top" arrow>
                  <span style={{ cursor: 'help' }}>Fair</span>
                </Tooltip>
              </TableCell>
              <TableCell align="center" sx={{ ...hdr, width: 68, color: '#9CA3AF' }}>EV%</TableCell>
              <TableCell align="right"  sx={{ ...hdr, width: 96, pr: 1.5 }}>Info</TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            {filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={12} sx={{ border: 'none', py: 6, px: 3 }}>
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5 }}>
                    <SearchOff sx={{ fontSize: 18, color: '#374151', mt: 0.15, flexShrink: 0 }} />
                    <Box>
                      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 500, color: '#6B7280', mb: 0.3 }}>
                        {markets.length > 0 ? 'No bets match the active filters' : 'No futures loaded'}
                      </Typography>
                      <Typography sx={{ fontSize: '0.75rem', color: '#4B5563' }}>
                        {markets.length > 0
                          ? 'Try "Show All" or clear the signal / sport filters to see more.'
                          : <>Click <span style={{ color: '#9CA3AF' }}>Run Futures</span> to scrape win totals from Buckeye, FanDuel, DraftKings, and BetMGM.</>}
                      </Typography>
                    </Box>
                  </Box>
                </TableCell>
              </TableRow>
            ) : filtered.map((row, idx) => {
              const isArb    = row.is_arb === true;
              const ev       = row.ev_float ?? 0;
              const isExpanded = expandedIdx === idx;

              const evColor = ev >= 8 ? '#4ADE80' : ev >= 4 ? '#86EFAC' : ev >= 0 ? '#BBF7D0' : ev >= -3 ? '#9CA3AF' : '#EF4444';
              const evSize  = ev >= 6 ? '0.9375rem' : ev >= 3 ? '0.875rem' : '0.8rem';
              const evWeight = ev >= 3 ? 700 : ev > 0 ? 600 : 400;

              return (
                <React.Fragment key={idx}>
                  <TableRow
                    onClick={() => setExpandedIdx(isExpanded ? null : idx)}
                    sx={{
                      cursor: 'pointer',
                      ...(isArb ? { bgcolor: 'rgba(251,191,36,0.025)' } : {}),
                      ...(isExpanded ? { bgcolor: 'rgba(255,255,255,0.03)' } : {}),
                      '&:hover': { bgcolor: isArb ? 'rgba(251,191,36,0.05)' : 'rgba(255,255,255,0.03)' },
                      ...(isArb ? { borderLeft: '2px solid rgba(251,191,36,0.4)' } : {}),
                    }}
                  >
                    {/* Expand chevron */}
                    <TableCell sx={{ ...cell, pl: 1, pr: 0, width: 36 }}>
                      {isExpanded
                        ? <ExpandLess sx={{ fontSize: 14, color: '#4B5563' }} />
                        : <ExpandMore sx={{ fontSize: 14, color: '#2D3748' }} />
                      }
                    </TableCell>

                    {/* Signal dots */}
                    <TableCell sx={{ ...cell, pl: 0.5, pr: 0.5 }}>
                      <SignalDots row={row} />
                    </TableCell>

                    {/* Sport tag */}
                    <TableCell sx={cell}>
                      <Box component="span" sx={{
                        display: 'inline-block',
                        fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.05em',
                        px: 0.75, py: 0.2, borderRadius: '3px',
                        ...(row.sport === 'NFL'
                          ? { bgcolor: 'rgba(96,165,250,0.12)', color: '#60A5FA' }
                          : { bgcolor: 'rgba(251,146,60,0.1)', color: '#FB923C' }),
                      }}>
                        {row.sport || '?'}
                      </Box>
                    </TableCell>

                    {/* Team */}
                    <TableCell sx={{ ...cell, maxWidth: 150, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
                      <Typography sx={{ fontSize: '0.875rem', color: '#E5E7EB', fontWeight: 500 }}>
                        {row.team}
                      </Typography>
                    </TableCell>

                    {/* Bet */}
                    <TableCell sx={{ ...cell, whiteSpace: 'nowrap' }}>
                      <Box component="span" sx={{
                        fontSize: '0.8rem', fontWeight: 600, mr: 0.5,
                        color: row.direction === 'Over' ? '#60A5FA' : '#F87171',
                      }}>
                        {row.direction}
                      </Box>
                      <Box component="span" sx={{ fontSize: '0.8rem', color: '#9CA3AF', ...mono }}>
                        {row.line}
                      </Box>
                    </TableCell>

                    {/* Buckeye odds */}
                    <TableCell align="center" sx={cell}>
                      <Box component="span" sx={{ ...mono, fontSize: '0.8125rem', fontWeight: 600, color: '#E5E7EB' }}>
                        {row.betbck_odds}
                      </Box>
                    </TableCell>

                    {/* Reference book odds — green when +EV */}
                    <TableCell align="center" sx={cell}>
                      <OddsCell odds={row.fd_odds}  evFloat={row.per_book_ev?.FD} />
                    </TableCell>
                    <TableCell align="center" sx={cell}>
                      <OddsCell odds={row.dk_odds}  evFloat={row.per_book_ev?.DK} />
                    </TableCell>
                    <TableCell align="center" sx={cell}>
                      <OddsCell odds={row.mgm_odds} evFloat={row.per_book_ev?.MGM} />
                    </TableCell>

                    {/* Fair */}
                    <TableCell align="center" sx={cell}>
                      <Box component="span" sx={{ ...mono, fontSize: '0.775rem', color: '#6B7280' }}>
                        {row.consensus_fair}
                      </Box>
                    </TableCell>

                    {/* EV% — scaled by magnitude */}
                    <TableCell align="center" sx={cell}>
                      <Box component="span" sx={{ ...mono, fontSize: evSize, fontWeight: evWeight, color: evColor }}>
                        {row.ev}
                      </Box>
                    </TableCell>

                    {/* Info badge */}
                    <TableCell align="right" sx={{ ...cell, pr: 1.5 }}>
                      {isArb ? (
                        <Tooltip
                          title={`Hedge: ${row.arb_book} ${row.arb_opp_odds} — lock in +${row.arb_roi?.toFixed(1) ?? '?'}% guaranteed`}
                          placement="left" arrow
                        >
                          <Chip
                            label={`ARB +${row.arb_roi?.toFixed(1) ?? '?'}%`}
                            size="small"
                            sx={{
                              height: 20, fontSize: '0.65rem', fontWeight: 700, cursor: 'pointer',
                              bgcolor: 'rgba(251,191,36,0.15)', color: '#FBB724',
                              border: '1px solid rgba(251,191,36,0.35)', borderRadius: '4px',
                              '& .MuiChip-label': { px: 0.75 },
                            }}
                          />
                        </Tooltip>
                      ) : row.signal_count >= 2 ? (
                        <Tooltip
                          title={`+EV confirmed by ${row.signal_count} books: ${row.sharp_books}`}
                          placement="left" arrow
                        >
                          <Chip
                            label={row.sharp_books}
                            size="small"
                            sx={{
                              height: 20, fontSize: '0.65rem', fontWeight: 700, cursor: 'pointer',
                              bgcolor: 'rgba(96,165,250,0.1)', color: '#60A5FA',
                              border: '1px solid rgba(96,165,250,0.2)', borderRadius: '4px',
                              '& .MuiChip-label': { px: 0.75 },
                            }}
                          />
                        </Tooltip>
                      ) : row.sharp_books ? (
                        <Box component="span" sx={{ fontSize: '0.68rem', color: '#374151', fontWeight: 500 }}>
                          {row.sharp_books}
                        </Box>
                      ) : null}
                    </TableCell>
                  </TableRow>

                  {/* ── Expand panel ───────────────────────────────── */}
                  <TableRow sx={{ '& > td': { p: 0, border: 'none' } }}>
                    <TableCell colSpan={12}>
                      <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                        <ExpandPanel row={row} />
                      </Collapse>
                    </TableCell>
                  </TableRow>
                </React.Fragment>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
};

export default FuturesScraper;
