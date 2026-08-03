import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Box, Button, Typography, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, CircularProgress, Alert, Slider,
} from '@mui/material';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { TuneRounded, SearchOff } from '@mui/icons-material';
import { API_BASE } from '../utils/apiConfig';

dayjs.extend(relativeTime);

const FuturesScraper: React.FC = () => {
  const [markets, setMarkets]               = useState<any[]>([]);
  const [loading, setLoading]               = useState(false);
  const [error, setError]                   = useState<string | null>(null);
  const [message, setMessage]               = useState<string | null>(null);
  const [lastUpdate, setLastUpdate]         = useState<string | null>(null);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [eventIdsLastRun, setEventIdsLastRun] = useState<string | null>(
    () => localStorage.getItem('futuresEventIdsLastRun'),
  );
  const [sortBy, setSortBy]   = useState<'ev' | 'pinnacle_limit'>('ev');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const EV_MAX_SLIDER = 20;
  const [minEv, setMinEv] = useState(0);
  const [maxEv, setMaxEv] = useState(EV_MAX_SLIDER);

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
          const { events, last_run } = data.data;
          if (events?.length > 0) {
            setMarkets(events);
            setLastUpdate(last_run);
            setMessage(`Futures: ${events.length} opportunities so far`);
          }
        } else if (data.type === 'futures_complete') {
          const { events, last_run, total_matched } = data.data;
          if (events?.length > 0) {
            setMarkets(events);
            setLastUpdate(last_run);
          }
          setMessage(
            `Done: ${total_matched ?? 0} teams matched, ${events?.length ?? 0} EV opportunities`,
          );
          setPipelineRunning(false);
          stopPolling();
        }
      } catch {}
    };
    es.onerror = () => console.warn('[FuturesScraper] SSE error — will auto-reconnect');
  };

  const disconnectSSE = () => {
    sseRef.current?.close();
    sseRef.current = null;
  };

  // ── Polling ───────────────────────────────────────────────────────────────
  const checkStatus = async () => {
    try {
      const res  = await fetch(`${API_BASE}/api/futures-pipeline-status`);
      const data = await res.json();
      if (data.status === 'success') {
        const running = data.data.running;
        setPipelineRunning(running);
        if (!running && data.data.task_done) {
          await fetchResults();
          stopPolling();
        }
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

  const handleGetEventIds = async () => {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const res  = await fetch(`${API_BASE}/buckeye/get-futures-event-ids`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'success') {
        setMessage(data.message || 'Futures event IDs retrieved');
        const now = new Date().toISOString();
        localStorage.setItem('futuresEventIdsLastRun', now);
        setEventIdsLastRun(now);
      } else {
        setError(data.message || 'Failed to get futures event IDs');
      }
    } catch {
      setError('Failed to get futures event IDs');
    } finally {
      setLoading(false);
    }
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
      if (sortBy === 'ev') {
        const evA = parseFloat(a.ev?.replace('%', '') || '0');
        const evB = parseFloat(b.ev?.replace('%', '') || '0');
        return sortDir === 'desc' ? evB - evA : evA - evB;
      }
      if (sortBy === 'pinnacle_limit') {
        return sortDir === 'desc'
          ? (b.pinnacle_limit ?? -1) - (a.pinnacle_limit ?? -1)
          : (a.pinnacle_limit ?? -1) - (b.pinnacle_limit ?? -1);
      }
      return 0;
    });
  }, [markets, sortBy, sortDir]);

  const filteredMarkets = sortedMarkets.filter(row => {
    const v = parseFloat(row.ev?.replace('%', '') || '0');
    if (v < minEv) return false;
    if (maxEv < EV_MAX_SLIDER && v > maxEv) return false;
    return true;
  });

  const evLabel = (v: number, isMax: boolean) =>
    isMax && v >= EV_MAX_SLIDER ? 'All' : `${v}%`;

  // ── Shared styles ─────────────────────────────────────────────────────────
  const btnSx = {
    color: '#9CA3AF',
    borderColor: 'rgba(255,255,255,0.1)',
    borderRadius: '6px',
    fontWeight: 500,
    px: 2, py: 0.5,
    fontSize: '0.75rem',
    minWidth: 'auto',
    height: 32,
    textTransform: 'none' as const,
    lineHeight: 1.2,
    bgcolor: 'rgba(255,255,255,0.04)',
    '&:hover': { bgcolor: 'rgba(255,255,255,0.07)', borderColor: 'rgba(255,255,255,0.2)', color: '#F5F5F5' },
  };

  const sliderSx = {
    color: 'rgba(255,255,255,0.5)',
    '& .MuiSlider-thumb': { width: 12, height: 12, bgcolor: '#F5F5F5', boxShadow: 'none' },
    '& .MuiSlider-rail': { bgcolor: 'rgba(255,255,255,0.1)' },
    '& .MuiSlider-track': { bgcolor: 'rgba(255,255,255,0.4)', border: 'none' },
    '& .MuiSlider-valueLabel': {
      bgcolor: '#1a1a1a', border: '1px solid rgba(255,255,255,0.12)',
      fontSize: '0.7rem', color: '#F5F5F5',
    },
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      {/* Toolbar */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        <Button variant="outlined" size="small" sx={btnSx} onClick={handleGetEventIds}>
          Get Futures Event IDs
          {eventIdsLastRun && (
            <Box component="span" sx={{ ml: 0.75, fontSize: '0.65rem', color: '#666', fontWeight: 400 }}>
              ({dayjs(eventIdsLastRun).fromNow()})
            </Box>
          )}
        </Button>

        <Button
          variant="outlined"
          size="small"
          disabled={pipelineRunning}
          onClick={handleRunFutures}
          sx={{
            ...btnSx,
            color:       pipelineRunning ? '#32D74B' : '#9CA3AF',
            borderColor: pipelineRunning ? 'rgba(50,215,75,0.3)' : 'rgba(255,255,255,0.1)',
            bgcolor:     pipelineRunning ? 'rgba(50,215,75,0.06)' : 'rgba(255,255,255,0.04)',
            '&.Mui-disabled': {
              color: '#32D74B', borderColor: 'rgba(50,215,75,0.3)', opacity: 1, borderRadius: '6px',
            },
          }}
        >
          {pipelineRunning ? 'Running…' : 'Run Futures'}
        </Button>

        <Box sx={{ width: '1px', height: 24, bgcolor: 'rgba(255,255,255,0.12)', mx: 0.5 }} />

        {/* EV Range Filter */}
        <Box sx={{
          display: 'flex', alignItems: 'center', gap: 1.5,
          px: 1.5, py: 0.5,
          border: '1px solid rgba(255,255,255,0.08)', borderRadius: 1.5,
          height: 32, minWidth: 240,
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
              Showing {filteredMarkets.length} of {markets.length} futures
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
            Futures pipeline active… matching season win totals.
          </Typography>
        </Box>
      )}

      {/* EV Table */}
      <TableContainer sx={{
        background: 'transparent', borderRadius: 1.5,
        border: '1px solid rgba(255,255,255,0.06)',
      }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ '& .MuiTableCell-root': {
              borderBottom: '1px solid rgba(255,255,255,0.06)', py: 1.5,
              bgcolor: 'rgba(255,255,255,0.02)',
            }}}>
              {(['Team', 'League', 'Bet', 'Book Odds', 'Pinnacle NVP'] as const).map(label => (
                <TableCell key={label} align={['Book Odds', 'Pinnacle NVP'].includes(label) ? 'center' : 'left'}
                  sx={{ color: '#6B7280', fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                  {label}
                </TableCell>
              ))}
              <TableCell
                align="center"
                onClick={() => { setSortBy('ev'); setSortDir(d => sortBy === 'ev' && d === 'desc' ? 'asc' : 'desc'); }}
                sx={{ color: sortBy === 'ev' ? '#F5F5F5' : '#6B7280', fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.07em', cursor: 'pointer', userSelect: 'none', '&:hover': { color: '#F5F5F5' } }}
              >
                EV {sortBy === 'ev' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
              </TableCell>
              <TableCell
                align="right"
                onClick={() => { setSortBy('pinnacle_limit'); setSortDir(d => sortBy === 'pinnacle_limit' && d === 'desc' ? 'asc' : 'desc'); }}
                sx={{ color: sortBy === 'pinnacle_limit' ? '#F5F5F5' : '#6B7280', fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.07em', cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap', '&:hover': { color: '#F5F5F5' } }}
              >
                Pin Limit {sortBy === 'pinnacle_limit' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredMarkets.length === 0 && !loading ? (
              <TableRow sx={{ '&:hover': { backgroundColor: 'transparent' } }}>
                <TableCell colSpan={7} sx={{ border: 'none', py: 5, px: 3 }}>
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5 }}>
                    <SearchOff sx={{ fontSize: 18, color: '#374151', mt: 0.15, flexShrink: 0 }} />
                    <Box>
                      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 500, color: '#6B7280', mb: 0.25 }}>
                        {markets.length > 0 ? 'No futures match the active filters' : 'No futures loaded'}
                      </Typography>
                      <Typography sx={{ fontSize: '0.75rem', color: '#6B7280' }}>
                        {markets.length > 0
                          ? <>Widen the EV range to see all {markets.length} futures.</>
                          : <>Get Futures Event IDs, then click <span style={{ color: '#9CA3AF' }}>Run Futures</span> to see season win total EV.</>
                        }
                      </Typography>
                    </Box>
                  </Box>
                </TableCell>
              </TableRow>
            ) : filteredMarkets.map((row, idx) => (
              <TableRow
                key={idx}
                sx={{
                  '&:hover': { backgroundColor: 'rgba(255,255,255,0.03)' },
                  '& .MuiTableCell-root': { borderBottom: '1px solid rgba(255,255,255,0.04)', py: 1.25, verticalAlign: 'middle' },
                }}
              >
                <TableCell sx={{ color: '#E5E7EB', fontWeight: 400, fontSize: '0.875rem' }}>
                  {row.matchup}
                </TableCell>
                <TableCell sx={{ color: '#9CA3AF', fontSize: '0.8125rem' }}>
                  {row.league}
                </TableCell>
                <TableCell sx={{ color: '#E5E7EB', fontSize: '0.8125rem' }}>
                  {row.bet}
                </TableCell>
                <TableCell align="center" sx={{ color: '#D1D5DB', fontSize: '0.8125rem', fontFamily: '"JetBrains Mono","Fira Code","Consolas",monospace', fontVariantNumeric: 'tabular-nums' }}>
                  {row.betbck_odds || 'N/A'}
                </TableCell>
                <TableCell align="center" sx={{ color: '#D1D5DB', fontSize: '0.8125rem', fontFamily: '"JetBrains Mono","Fira Code","Consolas",monospace', fontVariantNumeric: 'tabular-nums' }}>
                  {row.pinnacle_nvp}
                </TableCell>
                <TableCell align="center">
                  {parseFloat(row.ev) > 0 ? (
                    <span style={{ color: '#32D74B', fontWeight: 500, fontSize: '0.875rem', fontFamily: 'monospace', fontVariantNumeric: 'tabular-nums' }}>
                      {row.ev}
                    </span>
                  ) : (
                    <span style={{ color: '#4B5563', fontSize: '0.8125rem', fontFamily: 'monospace' }}>{row.ev}</span>
                  )}
                </TableCell>
                <TableCell align="right" sx={{ color: '#6B7280', fontSize: '0.8125rem', fontFamily: '"JetBrains Mono","Fira Code","Consolas",monospace', fontVariantNumeric: 'tabular-nums' }}>
                  {row.pinnacle_limit != null ? `${row.pinnacle_limit}` : ''}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
};

export default FuturesScraper;
