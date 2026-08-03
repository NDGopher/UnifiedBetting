import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Box, Button, Typography, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, CircularProgress, Alert, Slider, Chip, Tooltip,
} from '@mui/material';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { TuneRounded, SearchOff } from '@mui/icons-material';
import { API_BASE } from '../utils/apiConfig';

dayjs.extend(relativeTime);

interface FuturesRow {
  team:           string;
  line:           number;
  direction:      string;   // "Over" | "Under"
  betbck_odds:    string;
  fd_odds:        string;
  dk_odds:        string;
  mgm_odds:       string;
  consensus_fair: string;
  ev:             string;
  ev_float:       number;
  sharp_books:    string;
  is_arb?:        boolean;
  arb_book?:      string;
  arb_opp_odds?:  string;
  arb_roi?:       number | null;
}

const FuturesScraper: React.FC = () => {
  const [markets, setMarkets]               = useState<FuturesRow[]>([]);
  const [loading, setLoading]               = useState(false);
  const [error, setError]                   = useState<string | null>(null);
  const [message, setMessage]               = useState<string | null>(null);
  const [lastUpdate, setLastUpdate]         = useState<string | null>(null);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const EV_MAX_SLIDER = 20;
  const [minEv, setMinEv] = useState(0);
  const [maxEv, setMaxEv] = useState(EV_MAX_SLIDER);
  const [showAllEv, setShowAllEv] = useState(false);

  const pollingRef  = useRef<NodeJS.Timeout | null>(null);
  const isPolling   = useRef(false);
  const sseRef      = useRef<EventSource | null>(null);

  useEffect(() => {
    connectSSE();
    fetchResults();
    return () => {
      disconnectSSE();
      stopPolling();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
          setPipelineRunning(false);
          stopPolling();
        } else if (data.type === 'futures_error') {
          setError(data.data?.message || 'Futures pipeline error');
          setPipelineRunning(false);
          stopPolling();
        }
      } catch {}
    };
    es.onerror = () => console.warn('[FuturesScraper] SSE error');
  };

  const disconnectSSE = () => { sseRef.current?.close(); sseRef.current = null; };

  // ── Polling ───────────────────────────────────────────────────────────────
  const checkStatus = async () => {
    try {
      const res  = await fetch(`${API_BASE}/api/futures-pipeline-status`);
      const data = await res.json();
      if (data.status === 'success') {
        const running = data.data.running;
        setPipelineRunning(running);
        if (!running && data.data.task_done) { await fetchResults(); stopPolling(); }
      }
    } catch {}
  };

  const startPolling = () => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    setPipelineRunning(true);
    pollingRef.current = setInterval(() => {
      if (!isPolling.current) {
        isPolling.current = true;
        checkStatus().finally(() => { isPolling.current = false; });
      }
    }, 2000);
  };

  const stopPolling = () => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = null;
    setPipelineRunning(false);
  };

  // ── API calls ─────────────────────────────────────────────────────────────
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

  const handleRunFutures = async () => {
    if (pipelineRunning) return;
    setPipelineRunning(true);
    setLoading(true);
    setError(null);
    setMessage(null);
    setMarkets([]);
    setLastUpdate(null);
    try {
      const res  = await fetch(`${API_BASE}/api/run-futures-pipeline`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'success') {
        setMessage('Futures pipeline started…');
        connectSSE();
        startPolling();
      } else {
        setError(data.message || 'Failed to start futures pipeline');
        setPipelineRunning(false);
      }
    } catch {
      setError('Connection failed — try again');
      setPipelineRunning(false);
    } finally {
      setLoading(false);
    }
  };

  // ── Sort / filter ─────────────────────────────────────────────────────────
  const sortedMarkets = useMemo(() => {
    return [...markets].sort((a, b) => {
      // Arb always floats to top regardless of sort direction
      if (a.is_arb && !b.is_arb) return -1;
      if (!a.is_arb && b.is_arb) return 1;
      return sortDir === 'desc' ? b.ev_float - a.ev_float : a.ev_float - b.ev_float;
    });
  }, [markets, sortDir]);

  const filteredMarkets = useMemo(() => sortedMarkets.filter(row => {
    if (row.is_arb) return true;         // arbs always visible
    if (showAllEv) return true;
    const v = row.ev_float ?? 0;
    if (v < minEv) return false;
    if (maxEv < EV_MAX_SLIDER && v > maxEv) return false;
    return true;
  }), [sortedMarkets, minEv, maxEv, showAllEv]);

  const evLabel = (v: number, isMax: boolean) =>
    isMax && v >= EV_MAX_SLIDER ? 'All' : `${v}%`;

  const arbCount  = markets.filter(r => r.is_arb).length;
  const posEvCount = markets.filter(r => !r.is_arb && (r.ev_float ?? 0) > 0).length;

  // ── Styles ────────────────────────────────────────────────────────────────
  const btnSx = {
    color: '#9CA3AF', borderColor: 'rgba(255,255,255,0.1)', borderRadius: '6px',
    fontWeight: 500, px: 2, py: 0.5, fontSize: '0.75rem', minWidth: 'auto',
    height: 32, textTransform: 'none' as const, lineHeight: 1.2,
    bgcolor: 'rgba(255,255,255,0.04)',
    '&:hover': { bgcolor: 'rgba(255,255,255,0.07)', borderColor: 'rgba(255,255,255,0.2)', color: '#F5F5F5' },
  };

  const sliderSx = {
    color: 'rgba(255,255,255,0.5)',
    '& .MuiSlider-thumb': { width: 12, height: 12, bgcolor: '#F5F5F5', boxShadow: 'none' },
    '& .MuiSlider-rail': { bgcolor: 'rgba(255,255,255,0.1)' },
    '& .MuiSlider-track': { bgcolor: 'rgba(255,255,255,0.4)', border: 'none' },
    '& .MuiSlider-valueLabel': { bgcolor: '#1a1a1a', border: '1px solid rgba(255,255,255,0.12)', fontSize: '0.7rem', color: '#F5F5F5' },
  };

  const monoSx = {
    fontFamily: '"JetBrains Mono","Fira Code","Consolas",monospace',
    fontVariantNumeric: 'tabular-nums' as const,
    fontSize: '0.8125rem',
  };

  const hdrSx = {
    color: '#6B7280', fontWeight: 600, fontSize: '0.6875rem',
    textTransform: 'uppercase' as const, letterSpacing: '0.07em',
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      {/* Toolbar */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        <Button
          variant="outlined" size="small" disabled={pipelineRunning}
          onClick={handleRunFutures}
          sx={{
            ...btnSx,
            color:       pipelineRunning ? '#32D74B' : '#9CA3AF',
            borderColor: pipelineRunning ? 'rgba(50,215,75,0.3)' : 'rgba(255,255,255,0.1)',
            bgcolor:     pipelineRunning ? 'rgba(50,215,75,0.06)' : 'rgba(255,255,255,0.04)',
            '&.Mui-disabled': { color: '#32D74B', borderColor: 'rgba(50,215,75,0.3)', opacity: 1, borderRadius: '6px' },
          }}
        >
          {pipelineRunning ? 'Running…' : 'Run Futures'}
        </Button>

        {/* Summary badges */}
        {markets.length > 0 && (
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            {arbCount > 0 && (
              <Chip
                label={`${arbCount} ARB`}
                size="small"
                sx={{
                  height: 22, fontSize: '0.7rem', fontWeight: 700,
                  bgcolor: 'rgba(251,191,36,0.15)', color: '#FBB724',
                  border: '1px solid rgba(251,191,36,0.35)', borderRadius: '5px',
                  '& .MuiChip-label': { px: 1 },
                }}
              />
            )}
            {posEvCount > 0 && (
              <Chip
                label={`${posEvCount} +EV`}
                size="small"
                sx={{
                  height: 22, fontSize: '0.7rem', fontWeight: 700,
                  bgcolor: 'rgba(50,215,75,0.1)', color: '#32D74B',
                  border: '1px solid rgba(50,215,75,0.25)', borderRadius: '5px',
                  '& .MuiChip-label': { px: 1 },
                }}
              />
            )}
          </Box>
        )}

        <Box sx={{ width: '1px', height: 24, bgcolor: 'rgba(255,255,255,0.12)', mx: 0.5 }} />

        {/* EV Range Filter */}
        {!showAllEv && (
          <Box sx={{
            display: 'flex', alignItems: 'center', gap: 1.5,
            px: 1.5, py: 0.5, border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 1.5, height: 32, minWidth: 240,
          }}>
            <TuneRounded sx={{ fontSize: '0.95rem', color: '#B0B0B0', flexShrink: 0 }} />
            <Box sx={{ flex: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography sx={{ fontSize: '0.7rem', color: '#777', width: 26, flexShrink: 0 }}>Min</Typography>
                <Slider value={minEv} onChange={(_, v) => setMinEv(v as number)}
                  min={0} max={EV_MAX_SLIDER} step={0.5}
                  valueLabelDisplay="auto" valueLabelFormat={v => evLabel(v, false)}
                  sx={{ ...sliderSx, py: 0.5, my: 0 }} />
                <Typography sx={{ fontSize: '0.7rem', color: '#9CA3AF', width: 28, textAlign: 'right', flexShrink: 0 }}>
                  {evLabel(minEv, false)}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography sx={{ fontSize: '0.7rem', color: '#777', width: 26, flexShrink: 0 }}>Max</Typography>
                <Slider value={maxEv} onChange={(_, v) => setMaxEv(v as number)}
                  min={0} max={EV_MAX_SLIDER} step={0.5}
                  valueLabelDisplay="auto" valueLabelFormat={v => evLabel(v, true)}
                  sx={{ ...sliderSx, py: 0.5, my: 0 }} />
                <Typography sx={{ fontSize: '0.7rem', color: '#9CA3AF', width: 28, textAlign: 'right', flexShrink: 0 }}>
                  {evLabel(maxEv, true)}
                </Typography>
              </Box>
            </Box>
          </Box>
        )}

        <Button variant="outlined" size="small" onClick={() => setShowAllEv(v => !v)}
          sx={{ ...btnSx, ...(showAllEv ? { color: '#F5F5F5', borderColor: 'rgba(255,255,255,0.25)' } : {}) }}>
          {showAllEv ? 'Filter EV' : 'Show All'}
        </Button>
      </Box>

      {/* Meta row */}
      {(lastUpdate || markets.length > 0) && (
        <Box sx={{ mb: 1, ml: 0.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          {lastUpdate && (
            <Typography variant="body2" sx={{ color: '#aaa', fontSize: '0.8rem' }}>
              Last run: {dayjs(lastUpdate).format('HH:mm:ss')} ({dayjs(lastUpdate).fromNow()})
            </Typography>
          )}
          {markets.length > 0 && (
            <Typography variant="body2" sx={{ color: '#555', fontSize: '0.75rem' }}>
              Showing {filteredMarkets.length} of {markets.length} bets
            </Typography>
          )}
        </Box>
      )}

      {loading && <CircularProgress size={20} sx={{ mb: 2 }} />}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {message && !pipelineRunning && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1.5 }}>
          <Box component="span" sx={{ color: '#32D74B', fontSize: '0.75rem', lineHeight: 1 }}>✓</Box>
          <Typography sx={{ color: '#9CA3AF', fontSize: '0.75rem' }}>{message}</Typography>
        </Box>
      )}
      {pipelineRunning && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
          <Box sx={{
            '@keyframes futures-pulse': { '0%, 100%': { opacity: 1 }, '50%': { opacity: 0.15 } },
            width: 6, height: 6, borderRadius: '50%', bgcolor: '#32D74B',
            animation: 'futures-pulse 1.5s ease-in-out infinite', flexShrink: 0,
          }} />
          <Typography sx={{ color: '#9CA3AF', fontSize: '0.75rem' }}>
            {message || 'Futures pipeline running — scraping BetBCK + FanDuel + DraftKings + BetMGM…'}
          </Typography>
        </Box>
      )}

      {/* EV Table */}
      <TableContainer sx={{ background: 'transparent', borderRadius: 1.5, border: '1px solid rgba(255,255,255,0.06)' }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ '& .MuiTableCell-root': {
              borderBottom: '1px solid rgba(255,255,255,0.06)', py: 1.5,
              bgcolor: 'rgba(255,255,255,0.02)',
            }}}>
              <TableCell sx={hdrSx}>Team</TableCell>
              <TableCell sx={hdrSx}>Bet</TableCell>
              <TableCell align="center" sx={hdrSx}>BetBCK</TableCell>
              <TableCell align="center" sx={hdrSx}>FanDuel</TableCell>
              <TableCell align="center" sx={hdrSx}>DraftKings</TableCell>
              <TableCell align="center" sx={hdrSx}>BetMGM</TableCell>
              <TableCell align="center" sx={hdrSx}>Fair</TableCell>
              <TableCell
                align="center"
                onClick={() => setSortDir(d => d === 'desc' ? 'asc' : 'desc')}
                sx={{ ...hdrSx, color: '#F5F5F5', cursor: 'pointer', userSelect: 'none', '&:hover': { color: '#fff' } }}
              >
                EV {sortDir === 'desc' ? '↓' : '↑'}
              </TableCell>
              {/* Arb / Ref combined */}
              <TableCell align="right" sx={hdrSx}>Info</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredMarkets.length === 0 && !loading ? (
              <TableRow sx={{ '&:hover': { backgroundColor: 'transparent' } }}>
                <TableCell colSpan={9} sx={{ border: 'none', py: 5, px: 3 }}>
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5 }}>
                    <SearchOff sx={{ fontSize: 18, color: '#374151', mt: 0.15, flexShrink: 0 }} />
                    <Box>
                      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 500, color: '#6B7280', mb: 0.25 }}>
                        {markets.length > 0 ? 'No futures match the active filters' : 'No futures loaded'}
                      </Typography>
                      <Typography sx={{ fontSize: '0.75rem', color: '#6B7280' }}>
                        {markets.length > 0
                          ? <>Widen the EV range or click <b style={{ color: '#9CA3AF' }}>Show All</b> to see all {markets.length} bets.</>
                          : <>Click <span style={{ color: '#9CA3AF' }}>Run Futures</span> to scrape BetBCK, FanDuel, and DraftKings win totals.</>
                        }
                      </Typography>
                    </Box>
                  </Box>
                </TableCell>
              </TableRow>
            ) : filteredMarkets.map((row, idx) => {
              const evVal  = row.ev_float ?? 0;
              const evPos  = evVal > 0;
              const isArb  = row.is_arb === true;

              return (
                <TableRow
                  key={idx}
                  sx={{
                    // Arb rows get a faint amber left border
                    ...(isArb ? {
                      borderLeft: '2px solid rgba(251,191,36,0.5)',
                      bgcolor: 'rgba(251,191,36,0.03)',
                    } : {}),
                    '&:hover': { backgroundColor: isArb ? 'rgba(251,191,36,0.06)' : 'rgba(255,255,255,0.03)' },
                    '& .MuiTableCell-root': { borderBottom: '1px solid rgba(255,255,255,0.04)', py: 1.25, verticalAlign: 'middle' },
                  }}
                >
                  {/* Team */}
                  <TableCell sx={{ color: '#E5E7EB', fontSize: '0.875rem', maxWidth: 180, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {row.team}
                  </TableCell>

                  {/* Bet: "Over 6.5" */}
                  <TableCell sx={{ color: '#D1D5DB', fontSize: '0.8125rem', whiteSpace: 'nowrap' }}>
                    <Box component="span" sx={{ color: row.direction === 'Over' ? '#60A5FA' : '#F87171', fontWeight: 500 }}>
                      {row.direction}
                    </Box>
                    {' '}{row.line}
                  </TableCell>

                  {/* BetBCK odds */}
                  <TableCell align="center" sx={{ color: '#D1D5DB', ...monoSx }}>
                    {row.betbck_odds}
                  </TableCell>

                  {/* FanDuel odds */}
                  <TableCell align="center" sx={{ color: row.fd_odds === 'N/A' ? '#374151' : '#D1D5DB', ...monoSx }}>
                    {row.fd_odds}
                  </TableCell>

                  {/* DraftKings odds */}
                  <TableCell align="center" sx={{ color: row.dk_odds === 'N/A' ? '#374151' : '#D1D5DB', ...monoSx }}>
                    {row.dk_odds}
                  </TableCell>

                  {/* BetMGM odds */}
                  <TableCell align="center" sx={{ color: row.mgm_odds === 'N/A' ? '#374151' : '#D1D5DB', ...monoSx }}>
                    {row.mgm_odds ?? 'N/A'}
                  </TableCell>

                  {/* Consensus fair */}
                  <TableCell align="center" sx={{ color: '#9CA3AF', ...monoSx }}>
                    {row.consensus_fair}
                  </TableCell>

                  {/* EV% */}
                  <TableCell align="center">
                    <span style={{
                      color: evVal === 0 ? '#4B5563' : evPos ? '#32D74B' : '#EF4444',
                      fontWeight: isArb ? 700 : evPos ? 600 : 400,
                      fontSize: (evPos || isArb) ? '0.9rem' : '0.8125rem',
                      fontFamily: 'monospace',
                      fontVariantNumeric: 'tabular-nums',
                    }}>
                      {row.ev}
                    </span>
                  </TableCell>

                  {/* Info: arb badge or sharp-books ref */}
                  <TableCell align="right">
                    {isArb ? (
                      <Tooltip
                        title={`Arb vs ${row.arb_book} ${row.arb_opp_odds} — guaranteed ${row.arb_roi != null ? `+${row.arb_roi.toFixed(1)}%` : 'profit'} on balanced stakes`}
                        placement="left"
                        arrow
                      >
                        <Chip
                          label={`ARB ${row.arb_roi != null ? `+${row.arb_roi.toFixed(1)}%` : ''}`}
                          size="small"
                          sx={{
                            height: 20, fontSize: '0.65rem', fontWeight: 700, cursor: 'help',
                            bgcolor: 'rgba(251,191,36,0.18)', color: '#FBB724',
                            border: '1px solid rgba(251,191,36,0.4)', borderRadius: '4px',
                            '& .MuiChip-label': { px: 0.75 },
                          }}
                        />
                      </Tooltip>
                    ) : (
                      row.sharp_books && (
                        <Chip
                          label={row.sharp_books}
                          size="small"
                          sx={{
                            height: 18, fontSize: '0.6rem', fontWeight: 600,
                            bgcolor: 'rgba(255,255,255,0.06)', color: '#6B7280',
                            borderRadius: '4px', '& .MuiChip-label': { px: 0.75 },
                          }}
                        />
                      )
                    )}
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
