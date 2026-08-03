import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Box, Button, Typography, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Chip, Tooltip, ToggleButtonGroup, ToggleButton,
} from '@mui/material';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { SearchOff } from '@mui/icons-material';
import { API_BASE } from '../utils/apiConfig';

dayjs.extend(relativeTime);

interface FuturesRow {
  team:           string;
  sport:          string;   // 'NFL' | 'NCAAF'
  line:           number;
  direction:      string;   // 'Over' | 'Under'
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
  is_arb?:        boolean;
  arb_book?:      string;
  arb_opp_odds?:  string;
  arb_roi?:       number | null;
}

type SportFilter = 'ALL' | 'NFL' | 'NCAAF';

// ── helpers ──────────────────────────────────────────────────────────────────

const BOOKS = ['FD', 'DK', 'MGM'] as const;

/** Render 1–3 signal dots for a row. Green = that book confirms +EV, grey = available but not +EV, transparent = book doesn't have the line. */
function SignalDots({ row }: { row: FuturesRow }) {
  const bookKeys: Record<typeof BOOKS[number], string> = { FD: 'FD', DK: 'DK', MGM: 'MGM' };
  const oddsKeys: Record<typeof BOOKS[number], string> = { FD: row.fd_odds, DK: row.dk_odds, MGM: row.mgm_odds };

  return (
    <Box sx={{ display: 'flex', gap: '3px', alignItems: 'center' }}>
      {BOOKS.map(book => {
        const hasLine = oddsKeys[book] !== 'N/A' && oddsKeys[book];
        const evForBook = row.per_book_ev?.[bookKeys[book]];
        const isPositive = hasLine && evForBook !== undefined && evForBook > 0;
        const isPresent  = hasLine;

        return (
          <Tooltip
            key={book}
            title={!isPresent ? `${book}: no line` : `${book}: ${evForBook !== undefined ? (evForBook > 0 ? `+${evForBook.toFixed(1)}%` : `${evForBook.toFixed(1)}%`) : 'N/A'} EV`}
            placement="top"
            arrow
          >
            <Box
              sx={{
                width: 8, height: 8, borderRadius: '50%',
                bgcolor: !isPresent
                  ? 'rgba(255,255,255,0.06)'
                  : isPositive
                    ? '#32D74B'
                    : 'rgba(255,255,255,0.2)',
                border: !isPresent ? '1px solid rgba(255,255,255,0.08)' : 'none',
                flexShrink: 0,
                cursor: 'default',
              }}
            />
          </Tooltip>
        );
      })}
    </Box>
  );
}

/** Render an odds string; green-tinted if +EV for that book. */
function OddsCell({ odds, evFloat }: { odds: string; evFloat?: number }) {
  const na      = !odds || odds === 'N/A';
  const posEv   = !na && evFloat !== undefined && evFloat > 0;
  return (
    <span style={{
      fontFamily: '"JetBrains Mono","Fira Code",monospace',
      fontVariantNumeric: 'tabular-nums',
      fontSize: '0.8rem',
      color: na ? '#374151' : posEv ? '#4ADE80' : '#D1D5DB',
      fontWeight: posEv ? 600 : 400,
    }}>
      {na ? '—' : odds}
    </span>
  );
}

// ── component ─────────────────────────────────────────────────────────────────

const FuturesScraper: React.FC = () => {
  const [markets, setMarkets]                     = useState<FuturesRow[]>([]);
  const [loading, setLoading]                     = useState(false);
  const [message, setMessage]                     = useState<string | null>(null);
  const [lastUpdate, setLastUpdate]               = useState<string | null>(null);
  const [pipelineRunning, setPipelineRunning]     = useState(false);
  const [sportFilter, setSportFilter]             = useState<SportFilter>('ALL');
  const [showOnlyPositive, setShowOnlyPositive]   = useState(false);
  const [minSignal, setMinSignal]                 = useState(0);

  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const isPolling  = useRef(false);
  const sseRef     = useRef<EventSource | null>(null);

  useEffect(() => { connectSSE(); fetchResults(); return () => { disconnectSSE(); stopPolling(); }; }, []); // eslint-disable-line

  // ── SSE ────────────────────────────────────────────────────────────────────
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

  // ── Polling ────────────────────────────────────────────────────────────────
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

  // ── API ─────────────────────────────────────────────────────────────────────
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
    setPipelineRunning(true); setLoading(true); setMessage(null); setMarkets([]);
    try {
      const res  = await fetch(`${API_BASE}/api/run-futures-pipeline`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'success') { connectSSE(); startPolling(); }
      else { setPipelineRunning(false); }
    } catch { setPipelineRunning(false); }
    finally { setLoading(false); }
  };

  // ── Filter / sort ───────────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    return markets.filter(r => {
      if (r.is_arb) return true; // arbs always shown
      if (sportFilter !== 'ALL' && r.sport !== sportFilter) return false;
      if (showOnlyPositive && r.ev_float <= 0) return false;
      if (r.signal_count < minSignal) return false;
      return true;
    });
  }, [markets, sportFilter, showOnlyPositive, minSignal]);

  // ── Counts ──────────────────────────────────────────────────────────────────
  const arbCount   = markets.filter(r => r.is_arb).length;
  const posEvCount = markets.filter(r => !r.is_arb && r.ev_float > 0).length;
  const nflCount   = markets.filter(r => r.sport === 'NFL').length;
  const ncaafCount = markets.filter(r => r.sport === 'NCAAF').length;
  const multi      = markets.filter(r => !r.is_arb && r.signal_count >= 2).length;

  // ── Style helpers ───────────────────────────────────────────────────────────
  const hdr = {
    color: '#6B7280', fontWeight: 600, fontSize: '0.625rem',
    textTransform: 'uppercase' as const, letterSpacing: '0.08em', py: 1.25,
    borderBottom: '1px solid rgba(255,255,255,0.07)',
    bgcolor: 'rgba(0,0,0,0.25)',
  };

  const cell = {
    borderBottom: '1px solid rgba(255,255,255,0.04)',
    py: 1, verticalAlign: 'middle',
  };

  const mono = {
    fontFamily: '"JetBrains Mono","Fira Code",monospace',
    fontVariantNumeric: 'tabular-nums' as const,
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <>
      {/* ── Toolbar ─────────────────────────────────────────────────── */}
      <Box sx={{ display: 'flex', gap: 1.5, mb: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        {/* Run button */}
        <Button
          variant="outlined" size="small" disabled={pipelineRunning || loading}
          onClick={handleRun}
          sx={{
            color: pipelineRunning ? '#32D74B' : '#9CA3AF',
            borderColor: pipelineRunning ? 'rgba(50,215,75,0.35)' : 'rgba(255,255,255,0.1)',
            bgcolor: pipelineRunning ? 'rgba(50,215,75,0.06)' : 'rgba(255,255,255,0.04)',
            borderRadius: '6px', fontWeight: 500, px: 2, fontSize: '0.75rem',
            height: 30, textTransform: 'none', minWidth: 'auto',
            '&:hover': { bgcolor: 'rgba(255,255,255,0.07)', borderColor: 'rgba(255,255,255,0.2)', color: '#F5F5F5' },
            '&.Mui-disabled': { color: pipelineRunning ? '#32D74B' : undefined, borderColor: pipelineRunning ? 'rgba(50,215,75,0.35)' : undefined, opacity: 1 },
          }}
        >
          {pipelineRunning ? '● Running…' : 'Run Pipeline'}
        </Button>

        {/* Divider */}
        <Box sx={{ width: 1, height: 20, bgcolor: 'rgba(255,255,255,0.1)' }} />

        {/* Sport filter */}
        <ToggleButtonGroup
          value={sportFilter} exclusive size="small"
          onChange={(_, v) => v && setSportFilter(v)}
          sx={{
            height: 30,
            '& .MuiToggleButton-root': {
              border: '1px solid rgba(255,255,255,0.1)',
              color: '#6B7280', fontSize: '0.7rem', fontWeight: 600,
              px: 1.25, py: 0, textTransform: 'none', lineHeight: 1,
              '&.Mui-selected': { bgcolor: 'rgba(255,255,255,0.1)', color: '#F5F5F5', borderColor: 'rgba(255,255,255,0.2)' },
              '&:hover': { bgcolor: 'rgba(255,255,255,0.06)' },
            },
          }}
        >
          <ToggleButton value="ALL">All {markets.length > 0 ? `(${markets.length})` : ''}</ToggleButton>
          <ToggleButton value="NFL">NFL {nflCount > 0 ? `(${nflCount})` : ''}</ToggleButton>
          <ToggleButton value="NCAAF">NCAAF {ncaafCount > 0 ? `(${ncaafCount})` : ''}</ToggleButton>
        </ToggleButtonGroup>

        {/* Signal filter */}
        <Box sx={{ display: 'flex', gap: 0.75 }}>
          {[0, 1, 2, 3].map(n => (
            <Button
              key={n} size="small"
              onClick={() => setMinSignal(prev => prev === n ? 0 : n)}
              sx={{
                minWidth: 0, px: 1.25, height: 30,
                fontSize: '0.7rem', fontWeight: 600,
                borderRadius: '6px', textTransform: 'none',
                border: '1px solid',
                color: minSignal === n ? '#F5F5F5' : '#6B7280',
                borderColor: minSignal === n ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.08)',
                bgcolor: minSignal === n ? 'rgba(255,255,255,0.1)' : 'transparent',
                '&:hover': { bgcolor: 'rgba(255,255,255,0.07)' },
              }}
            >
              {n === 0 ? 'All signals' : `${n}+ books`}
            </Button>
          ))}
        </Box>

        {/* +EV only toggle */}
        <Button
          size="small"
          onClick={() => setShowOnlyPositive(v => !v)}
          sx={{
            minWidth: 0, px: 1.25, height: 30,
            fontSize: '0.7rem', fontWeight: 600,
            borderRadius: '6px', textTransform: 'none',
            border: '1px solid',
            color: showOnlyPositive ? '#32D74B' : '#6B7280',
            borderColor: showOnlyPositive ? 'rgba(50,215,75,0.35)' : 'rgba(255,255,255,0.08)',
            bgcolor: showOnlyPositive ? 'rgba(50,215,75,0.06)' : 'transparent',
            '&:hover': { bgcolor: 'rgba(255,255,255,0.07)' },
          }}
        >
          +EV only
        </Button>
      </Box>

      {/* ── Stats bar ───────────────────────────────────────────────── */}
      {markets.length > 0 && (
        <Box sx={{ display: 'flex', gap: 1, mb: 1.5, alignItems: 'center', flexWrap: 'wrap' }}>
          {arbCount > 0 && (
            <Chip label={`${arbCount} ARB`} size="small" sx={{
              height: 20, fontSize: '0.65rem', fontWeight: 700,
              bgcolor: 'rgba(251,191,36,0.15)', color: '#FBB724',
              border: '1px solid rgba(251,191,36,0.3)', borderRadius: '4px',
              '& .MuiChip-label': { px: 1 },
            }} />
          )}
          {posEvCount > 0 && (
            <Chip label={`${posEvCount} +EV`} size="small" sx={{
              height: 20, fontSize: '0.65rem', fontWeight: 700,
              bgcolor: 'rgba(50,215,75,0.1)', color: '#32D74B',
              border: '1px solid rgba(50,215,75,0.22)', borderRadius: '4px',
              '& .MuiChip-label': { px: 1 },
            }} />
          )}
          {multi > 0 && (
            <Chip label={`${multi} multi-book`} size="small" sx={{
              height: 20, fontSize: '0.65rem', fontWeight: 700,
              bgcolor: 'rgba(96,165,250,0.1)', color: '#60A5FA',
              border: '1px solid rgba(96,165,250,0.22)', borderRadius: '4px',
              '& .MuiChip-label': { px: 1 },
            }} />
          )}
          <Box sx={{ flex: 1 }} />
          {lastUpdate && (
            <Typography sx={{ color: '#4B5563', fontSize: '0.7rem' }}>
              {dayjs(lastUpdate).format('h:mm a')} · {dayjs(lastUpdate).fromNow()}
            </Typography>
          )}
          <Typography sx={{ color: '#374151', fontSize: '0.7rem' }}>
            {filtered.length} of {markets.length} shown
          </Typography>
        </Box>
      )}

      {/* ── Live status ─────────────────────────────────────────────── */}
      {pipelineRunning && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
          <Box sx={{
            '@keyframes fp': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.2 } },
            width: 6, height: 6, borderRadius: '50%', bgcolor: '#32D74B',
            animation: 'fp 1.4s ease-in-out infinite', flexShrink: 0,
          }} />
          <Typography sx={{ color: '#6B7280', fontSize: '0.75rem' }}>
            {message || 'Scraping BetBCK · FanDuel · DraftKings · BetMGM…'}
          </Typography>
        </Box>
      )}
      {!pipelineRunning && message && markets.length > 0 && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1.5 }}>
          <Box component="span" sx={{ color: '#32D74B', fontSize: '0.75rem' }}>✓</Box>
          <Typography sx={{ color: '#4B5563', fontSize: '0.75rem' }}>{message}</Typography>
        </Box>
      )}

      {/* ── Table ───────────────────────────────────────────────────── */}
      <TableContainer sx={{ background: 'transparent', borderRadius: 1.5, border: '1px solid rgba(255,255,255,0.06)' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              {/* Signal */}
              <TableCell sx={{ ...hdr, width: 52, pl: 1.5 }}>
                <Tooltip title="Dots show per-book EV: green = +EV vs that book, grey = line available, hollow = no line" placement="top" arrow>
                  <span style={{ cursor: 'help' }}>Signal</span>
                </Tooltip>
              </TableCell>
              <TableCell sx={{ ...hdr, width: 52 }}>Sport</TableCell>
              <TableCell sx={hdr}>Team</TableCell>
              <TableCell sx={hdr}>Bet</TableCell>
              <TableCell align="center" sx={{ ...hdr, width: 70 }}>
                <Tooltip title="BetBCK — the book you're betting with" placement="top" arrow>
                  <span style={{ cursor: 'help' }}>BetBCK</span>
                </Tooltip>
              </TableCell>
              <TableCell align="center" sx={{ ...hdr, width: 62 }}>FD</TableCell>
              <TableCell align="center" sx={{ ...hdr, width: 62 }}>DK</TableCell>
              <TableCell align="center" sx={{ ...hdr, width: 62 }}>MGM</TableCell>
              <TableCell align="center" sx={{ ...hdr, width: 66 }}>
                <Tooltip title="Consensus fair price — average of deviggged reference books" placement="top" arrow>
                  <span style={{ cursor: 'help' }}>Fair</span>
                </Tooltip>
              </TableCell>
              <TableCell align="center" sx={{ ...hdr, width: 72, color: '#9CA3AF' }}>EV%</TableCell>
              <TableCell align="right" sx={{ ...hdr, pr: 1.5, width: 88 }}>Note</TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            {filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={11} sx={{ border: 'none', py: 6, px: 3 }}>
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5 }}>
                    <SearchOff sx={{ fontSize: 18, color: '#374151', mt: 0.15, flexShrink: 0 }} />
                    <Box>
                      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 500, color: '#6B7280', mb: 0.3 }}>
                        {markets.length > 0 ? 'No bets match the active filters' : 'No futures loaded'}
                      </Typography>
                      <Typography sx={{ fontSize: '0.75rem', color: '#4B5563' }}>
                        {markets.length > 0
                          ? 'Clear the signal / sport / +EV filters to see more.'
                          : <>Click <span style={{ color: '#9CA3AF' }}>Run Pipeline</span> to scrape win totals from BetBCK, FanDuel, DraftKings, and BetMGM.</>
                        }
                      </Typography>
                    </Box>
                  </Box>
                </TableCell>
              </TableRow>
            ) : filtered.map((row, idx) => {
              const isArb = row.is_arb === true;
              const evVal = row.ev_float ?? 0;
              const evPos = evVal > 0;

              // EV color by magnitude
              const evColor = evVal === 0 ? '#374151'
                : evVal >= 8 ? '#4ADE80'
                : evVal >= 4 ? '#86EFAC'
                : evVal >= 0 ? '#BBF7D0'
                : '#EF4444';

              return (
                <TableRow
                  key={idx}
                  sx={{
                    ...(isArb ? { bgcolor: 'rgba(251,191,36,0.025)' } : {}),
                    '&:hover': { bgcolor: isArb ? 'rgba(251,191,36,0.05)' : 'rgba(255,255,255,0.025)' },
                    ...(isArb ? { borderLeft: '2px solid rgba(251,191,36,0.45)' } : {}),
                  }}
                >
                  {/* Signal dots */}
                  <TableCell sx={{ ...cell, pl: 1.5, pr: 0.5 }}>
                    <SignalDots row={row} />
                  </TableCell>

                  {/* Sport tag */}
                  <TableCell sx={cell}>
                    <Box
                      component="span"
                      sx={{
                        display: 'inline-block',
                        fontSize: '0.6rem', fontWeight: 700,
                        letterSpacing: '0.06em',
                        px: 0.75, py: 0.25, borderRadius: '3px',
                        ...(row.sport === 'NFL'
                          ? { bgcolor: 'rgba(96,165,250,0.12)', color: '#60A5FA' }
                          : { bgcolor: 'rgba(251,146,60,0.12)', color: '#FB923C' }),
                      }}
                    >
                      {row.sport || '?'}
                    </Box>
                  </TableCell>

                  {/* Team */}
                  <TableCell sx={{ ...cell, maxWidth: 160, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    <Typography sx={{ fontSize: '0.875rem', color: '#E5E7EB', fontWeight: 500 }}>
                      {row.team}
                    </Typography>
                  </TableCell>

                  {/* Bet: Over/Under + line */}
                  <TableCell sx={{ ...cell, whiteSpace: 'nowrap' }}>
                    <Box component="span" sx={{
                      fontSize: '0.8rem', fontWeight: 600,
                      color: row.direction === 'Over' ? '#60A5FA' : '#F87171',
                      mr: 0.5,
                    }}>
                      {row.direction}
                    </Box>
                    <Box component="span" sx={{ fontSize: '0.8rem', color: '#9CA3AF', ...mono }}>
                      {row.line}
                    </Box>
                  </TableCell>

                  {/* BetBCK odds — this is the bet you're placing */}
                  <TableCell align="center" sx={cell}>
                    <Box component="span" sx={{
                      ...mono, fontSize: '0.8125rem',
                      fontWeight: 600, color: '#E5E7EB',
                    }}>
                      {row.betbck_odds}
                    </Box>
                  </TableCell>

                  {/* FD */}
                  <TableCell align="center" sx={cell}>
                    <OddsCell odds={row.fd_odds} evFloat={row.per_book_ev?.FD} />
                  </TableCell>

                  {/* DK */}
                  <TableCell align="center" sx={cell}>
                    <OddsCell odds={row.dk_odds} evFloat={row.per_book_ev?.DK} />
                  </TableCell>

                  {/* MGM */}
                  <TableCell align="center" sx={cell}>
                    <OddsCell odds={row.mgm_odds} evFloat={row.per_book_ev?.MGM} />
                  </TableCell>

                  {/* Consensus fair */}
                  <TableCell align="center" sx={cell}>
                    <Box component="span" sx={{ ...mono, fontSize: '0.775rem', color: '#6B7280' }}>
                      {row.consensus_fair}
                    </Box>
                  </TableCell>

                  {/* EV% — scaled color */}
                  <TableCell align="center" sx={cell}>
                    <Box component="span" sx={{
                      ...mono,
                      fontSize: evVal >= 6 ? '0.9375rem' : evVal >= 3 ? '0.875rem' : '0.8125rem',
                      fontWeight: evVal >= 3 ? 700 : evPos ? 600 : 400,
                      color: evColor,
                    }}>
                      {row.ev}
                    </Box>
                  </TableCell>

                  {/* Note: ARB or signal label */}
                  <TableCell align="right" sx={{ ...cell, pr: 1.5 }}>
                    {isArb ? (
                      <Tooltip
                        title={`Arb vs ${row.arb_book} ${row.arb_opp_odds} · guaranteed +${row.arb_roi?.toFixed(1) ?? '?'}% on balanced stakes`}
                        placement="left" arrow
                      >
                        <Chip
                          label={`ARB +${row.arb_roi?.toFixed(1) ?? '?'}%`}
                          size="small"
                          sx={{
                            height: 20, fontSize: '0.65rem', fontWeight: 700, cursor: 'help',
                            bgcolor: 'rgba(251,191,36,0.18)', color: '#FBB724',
                            border: '1px solid rgba(251,191,36,0.4)', borderRadius: '4px',
                            '& .MuiChip-label': { px: 0.75 },
                          }}
                        />
                      </Tooltip>
                    ) : row.signal_count >= 2 ? (
                      <Tooltip title={`+EV confirmed by ${row.signal_count} independent books: ${row.sharp_books}`} placement="left" arrow>
                        <Chip
                          label={`${row.signal_count} books`}
                          size="small"
                          sx={{
                            height: 20, fontSize: '0.65rem', fontWeight: 700, cursor: 'help',
                            bgcolor: 'rgba(96,165,250,0.12)', color: '#60A5FA',
                            border: '1px solid rgba(96,165,250,0.25)', borderRadius: '4px',
                            '& .MuiChip-label': { px: 0.75 },
                          }}
                        />
                      </Tooltip>
                    ) : row.sharp_books ? (
                      <Box component="span" sx={{ fontSize: '0.65rem', color: '#374151', fontWeight: 500 }}>
                        {row.sharp_books}
                      </Box>
                    ) : null}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
};

export default FuturesScraper;
