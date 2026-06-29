import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Box, Button, Typography, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, CircularProgress, Alert, FormControlLabel, Checkbox, Collapse, Slider } from '@mui/material';
import MatchingStats from './MatchingStats';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { ExpandMore, ExpandLess, TuneRounded, SearchOff, FilterAlt } from '@mui/icons-material';
import { API_BASE } from '../utils/apiConfig';
dayjs.extend(relativeTime);

interface Market {
  market: string;
  selection: string;
  line: string;
  pinnacle_nvp: string;
  betbck_odds: string;
  ev: string;
}

interface BuckeyeEvent {
  event_id: string;
  home_team: string;
  away_team: string;
  league: string;
  start_time: string;
  markets: Market[];
  total_ev: number;
  best_ev: number;
  last_updated: string;
}

const BuckeyeScraper: React.FC = () => {
  const [events, setEvents] = useState<BuckeyeEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [aceMarkets, setAceMarkets] = useState<any[]>([]);
  const [buckeyeMarkets, setBuckeyeMarkets] = useState<any[]>([]);
  const [stats, setStats] = useState({ pinnacleEvents: 0, betbckMatches: 0, matchRate: 0 });
  const [aceLastUpdate, setAceLastUpdate] = useState<string | null>(null);
  const [buckeyeLastUpdate, setBuckeyeLastUpdate] = useState<string | null>(null);
  const [eventIdsLastRun, setEventIdsLastRun] = useState<string | null>(() => localStorage.getItem('eventIdsLastRun'));
  const [sortBy, setSortBy] = useState<'ev' | 'start_time' | 'pinnacle_limit'>('ev');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [selectedSports, setSelectedSports] = useState<string[]>([]);
  const [showSportSelection, setShowSportSelection] = useState(false);
  const [wongTeasers, setWongTeasers] = useState<any | null>(null);
  const [wongExpanded, setWongExpanded] = useState(false);
  const [wongTeaserType, setWongTeaserType] = useState<'6pt' | '10pt'>('6pt');
  const [wongComboView, setWongComboView] = useState<'best' | 'grouped'>('grouped');
  const [combosExpanded, setCombosExpanded] = useState(false);
  const [parlays, setParlays] = useState<any | null>(null);
  const [parlaysExpanded, setParlaysExpanded] = useState(false);
  const [parlayLegFilter, setParlayLegFilter] = useState<'all' | 2 | 3 | 4>('all');
  const [parlayNext24h, setParlayNext24h] = useState(false);
  const [evNext24h, setEvNext24h] = useState(false);

  // EV range filter (display only)
  const EV_MAX_SLIDER = 20;
  const [minEv, setMinEv] = useState<number>(0);
  const [maxEv, setMaxEv] = useState<number>(EV_MAX_SLIDER);


  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const isPolling = useRef(false);
  const wsRef = useRef<WebSocket | null>(null);
  const runningAce = useRef(false);

  // Connect WebSocket on component mount + auto-run Get Event IDs if stale (>24h)
  useEffect(() => {
    connectWebSocket();

    const stored = localStorage.getItem('eventIdsLastRun');
    const stale = !stored || dayjs().diff(dayjs(stored), 'hour') >= 24;
    if (stale) {
      handleGetEventIds();
    }

    return () => {
      disconnectWebSocket();
      stopPolling();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const checkPipelineStatus = async () => {
    const isAceRun = runningAce.current; // snapshot before async — SSE may clear it mid-flight
    try {
      const statusUrl = isAceRun
        ? `${API_BASE}/ace/pipeline-status`
        : `${API_BASE}/api/pipeline-status`;
      const res = await fetch(statusUrl);
      const data = await res.json();
      if (data.status === 'success') {
        const running = data.data.running;
        const taskDone = data.data.task_done;
        setPipelineRunning(running);

        if (running) {
          console.log('[BuckeyeScraper] Pipeline is running...');
        } else if (taskDone) {
          console.log('[BuckeyeScraper] Pipeline completed!');
          setMessage('Pipeline completed successfully');
          if (isAceRun) {
            runningAce.current = false;
            fetchAceEvents();
          } else {
            fetchEvents();
          }
          stopPolling();
        }
      }
    } catch (err) {
      console.error('[BuckeyeScraper] Error checking pipeline status:', err);
    }
  };

  const startPolling = () => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    setPipelineRunning(true);
    // Check pipeline status every 2 seconds
    pollingRef.current = setInterval(() => {
      if (!isPolling.current && !loading) {
        isPolling.current = true;
        checkPipelineStatus().finally(() => { isPolling.current = false; });
      }
    }, 2000);
  };

  const stopPolling = () => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = null;
    setPipelineRunning(false);
  };

  const connectWebSocket = () => {
    if (wsRef.current) return;

    const es = new EventSource('/api/events/stream');
    (wsRef as any).current = es;

    es.onopen = () => {
      console.log('[BuckeyeScraper] SSE connected');
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'buckeye_update') {
          const { events, total_events, last_run, batch_completed, total_batches } = data.data;
          if (events && events.length > 0) {
            setBuckeyeMarkets(events);
            setBuckeyeLastUpdate(last_run);
            setMessage(`Streaming: ${batch_completed}/${total_batches} batches completed (${total_events} events)`);
          }
        } else if (data.type === 'buckeye_complete') {
          const { events, total_events, last_run, total_matched, teaser_results, parlay_results } = data.data;
          if (events && events.length > 0) {
            setBuckeyeMarkets(events);
            setBuckeyeLastUpdate(last_run);
            setMessage(`Buckeye done: ${total_matched} games matched, ${total_events} events found`);
          }
          if (teaser_results) {
            setWongTeasers(teaser_results);
          }
          if (parlay_results) {
            setParlays(parlay_results);
          }
          setPipelineRunning(false);
          stopPolling();
        } else if (data.type === 'ace_update') {
          const { events, total_events, last_run } = data.data;
          if (events && events.length > 0) {
            setAceMarkets(events);
            setAceLastUpdate(last_run);
            setMessage(`Ace: ${total_events} events found`);
          }
        } else if (data.type === 'ace_complete') {
          const { events, total_events, last_run, total_matched, parlay_results } = data.data;
          if (events && events.length > 0) {
            setAceMarkets(events);
            setAceLastUpdate(last_run);
            setMessage(`Ace done: ${total_matched} games matched, ${total_events} EV opportunities`);
          }
          if (parlay_results) {
            setParlays(parlay_results);
          }
          runningAce.current = false;
          setPipelineRunning(false);
          stopPolling();
        }
      } catch (err) {
        console.error('[BuckeyeScraper] Error parsing SSE message:', err);
      }
    };
    
    es.onerror = () => {
      console.warn('[BuckeyeScraper] SSE error - will auto-reconnect');
    };
  };

  const disconnectWebSocket = () => {
    if (wsRef.current) {
      (wsRef.current as any).close();
      wsRef.current = null;
    }
  };

  // Normalize start_time coming from different backends (Buckeye includes year, Ace is M/D HH:mm)
  const parseStartTime = (raw: any) => {
    if (!raw) return null;
    if (typeof raw === 'string') {
      // If it parses directly (likely includes year), use it
      const direct = dayjs(raw);
      if (direct.isValid()) return direct;
      // Ace style: "MM/DD HH:mm" (no year)
      const mdhm = raw.match(/^(\d{1,2})\/(\d{1,2})\s+(\d{1,2}):(\d{2})$/);
      if (mdhm) {
        const month = parseInt(mdhm[1], 10) - 1;
        const date = parseInt(mdhm[2], 10);
        const hour = parseInt(mdhm[3], 10);
        const minute = parseInt(mdhm[4], 10);
        const now = dayjs();
        return now.year(now.year()).month(month).date(date).hour(hour).minute(minute).second(0).millisecond(0);
      }
    }
    return null;
  };

  const fetchEvents = async () => {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      console.log('[BuckeyeScraper] Fetching results...');
      const res = await fetch(`${API_BASE}/buckeye/results`);
      const data = await res.json();
      console.log('[BuckeyeScraper] Results response:', data);
      if (data.status === 'success') {
        setBuckeyeLastUpdate(data.data.last_update || null);
        const allMarkets = (data.data.markets || []).slice(0, 150);
        setBuckeyeMarkets(allMarkets);
        if (data.data.teaser_results) {
          setWongTeasers(data.data.teaser_results);
        }
        if (data.data.parlay_results) {
          setParlays(data.data.parlay_results);
        }
      } else {
        setError(data.message || 'Failed to fetch results');
        setBuckeyeMarkets([]);
      }
    } catch (err) {
      console.error('[BuckeyeScraper] Error fetching results:', err);
      setError('Failed to fetch results');
      setBuckeyeMarkets([]);
    } finally {
      setLoading(false);
    }
  };

  const handleGetEventIds = async () => {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      console.log('[BuckeyeScraper] Getting event IDs...');
      const res = await fetch(`${API_BASE}/buckeye/get-event-ids`, { method: 'POST' });
      const data = await res.json();
      console.log('[BuckeyeScraper] Get Event IDs response:', data);
      if (data.status === 'success') {
        setMessage(data.message || 'Event IDs retrieved successfully');
        if (data.data && typeof data.data.event_count === 'number') {
          setStats(s => ({ ...s, pinnacleEvents: data.data.event_count }));
        }
        const now = new Date().toISOString();
        localStorage.setItem('eventIdsLastRun', now);
        setEventIdsLastRun(now);
      } else {
        setError(data.message || 'Failed to get event IDs');
      }
    } catch (err) {
      console.error('[BuckeyeScraper] Error getting event IDs:', err);
      setError('Failed to get event IDs');
    } finally {
      setLoading(false);
    }
  };

  const handleRunCalculations = async () => {
    // Immediately disable the button before any async work — prevents double-click
    if (pipelineRunning) return;
    setPipelineRunning(true);
    setLoading(true);
    setError(null);
    setMessage(null);
    setBuckeyeMarkets([]); // Clear Buckeye data
    setBuckeyeLastUpdate(null);
    setWongTeasers(null);        // Clear Wong Teaser results
    setParlays(null);            // Clear Parlay results
    setParlaysExpanded(false);   // Always start collapsed for new run
    setParlayNext24h(false);     // Reset 24h filter for new run
    setEvNext24h(false);         // Reset EV table 24h filter for new run
    setAceMarkets([]);    // Clear ACE results so only Buckeye shows
    setAceLastUpdate(null);
    try {
      const body = selectedSports.length > 0 ? { sport_filters: selectedSports } : {};

      // Auto-retry once on network errors (transient proxy drops in Replit)
      let res: Response | null = null;
      let lastNetworkErr: any = null;
      for (let attempt = 1; attempt <= 2; attempt++) {
        try {
          console.log(`[BuckeyeScraper] Starting streaming pipeline (attempt ${attempt})...`);
          res = await fetch(`${API_BASE}/api/run-streaming-pipeline`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          });
          lastNetworkErr = null;
          break;
        } catch (netErr) {
          lastNetworkErr = netErr;
          if (attempt < 2) {
            console.warn('[BuckeyeScraper] Network error on pipeline start, retrying in 2s...', netErr);
            await new Promise(r => setTimeout(r, 2000));
          }
        }
      }
      if (lastNetworkErr) throw lastNetworkErr;

      const data = await res!.json();
      console.log('[BuckeyeScraper] Streaming pipeline start response:', data);

      if (data.status === 'success') {
        setMessage(data.message || 'Streaming pipeline started - results will appear in real-time');
        connectWebSocket();
        startPolling();
      } else {
        // Backend rejected (e.g. already running) — restore button state
        setError(data.message || 'Failed to start streaming pipeline');
        setBuckeyeMarkets([]);
        setPipelineRunning(false);
      }
    } catch (err) {
      console.error('[BuckeyeScraper] Error starting streaming pipeline after retries:', err);
      setError('Connection to server failed — please tap Run EV Bets again');
      setBuckeyeMarkets([]);
      setPipelineRunning(false);
    } finally {
      setLoading(false);
    }
  };

  const handleRunAceCalculations = async () => {
    setLoading(true);
    setError(null);
    setMessage(null);
    setAceMarkets([]);
    setAceLastUpdate(null);
    setBuckeyeMarkets([]);
    setBuckeyeLastUpdate(null);
    setParlays(null);
    setWongTeasers(null);
    setParlaysExpanded(false);
    setParlayNext24h(false);
    setEvNext24h(false);
    // Don't start polling immediately - wait until calculations are actually running
    try {
      console.log('[BuckeyeScraper] Running Ace calculations...');
      const res = await fetch(`${API_BASE}/ace/run-calculations`, { method: 'POST' });
      const data = await res.json();
      console.log('[BuckeyeScraper] Ace calculations response:', data);
      
      // Handle the new response format with status field
      if (data.status === 'success') {
        setMessage(data.message || 'Ace calculations completed successfully');
        runningAce.current = true;
        startPolling(); // Start polling now that calculations are running
        // Don't fetch results immediately - let polling handle it
        // fetchAceEvents();
      } else if (data.status === 'partial_success') {
        setMessage(data.message || 'Ace calculations partially completed');
        startPolling(); // Start polling now that calculations are running
        // Don't fetch results immediately - let polling handle it
        // fetchAceEvents();
      } else if (data.status === 'error') {
        setError(data.message || data.error || 'Failed to run Ace calculations');
        setAceMarkets([]);
        stopPolling();
      } else {
        if (data.message) {
          setMessage(data.message);
        } else {
          setError('Failed to run Ace calculations - unexpected response format');
          setAceMarkets([]);
          stopPolling();
        }
      }
    } catch (err) {
      console.error('[BuckeyeScraper] Error running Ace calculations:', err);
      setError('Failed to run Ace calculations - network error');
      setAceMarkets([]);
      stopPolling();
    } finally {
      setLoading(false);
    }
  };

  const fetchAceEvents = async () => {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      console.log('[BuckeyeScraper] Fetching Ace results...');
      const res = await fetch(`${API_BASE}/ace/results`);
      const data = await res.json();
      console.log('[BuckeyeScraper] Ace results response:', data);
      
      // Handle the new response format with status field
      const setAce = (markets: any[], update: string | null) => {
        setAceMarkets(markets.slice(0, 150));
        setAceLastUpdate(update);
        stopPolling();
      };
      if (data.status === 'success') {
        setAce(data.markets || [], data.last_update || null);
      } else if (data.status === 'partial_success') {
        setAce(data.markets || [], data.last_update || null);
        setMessage(data.message || 'Partial results loaded');
      } else if (data.status === 'error') {
        setError(data.message || data.error || 'Failed to fetch Ace results');
        setAceMarkets([]);
        stopPolling();
      } else if (data.data && data.data.markets) {
        setAce(data.data.markets || [], data.data.last_update || null);
      } else {
        setError('Failed to fetch Ace results - unexpected response format');
        setAceMarkets([]);
        stopPolling();
      }
    } catch (err) {
      console.error('[BuckeyeScraper] Error fetching Ace results:', err);
      setError('Failed to fetch Ace results - network error');
      setAceMarkets([]);
      stopPolling();
    } finally {
      setLoading(false);
    }
  };

  const sports = [
    { key: 'nfl', label: 'NFL' },
    { key: 'ncaa_football', label: 'NCAA Football' },
    { key: 'nba', label: 'NBA' },
    { key: 'ncaa_basketball', label: 'NCAA Basketball' },
    { key: 'nhl', label: 'NHL' },
    { key: 'mlb', label: 'MLB' },
    { key: 'soccer', label: 'Soccer (All)' },
    { key: 'soccer_major', label: 'Soccer (Major Leagues)' }
  ];

  const toggleSport = (sportKey: string) => {
    setSelectedSports(prev => 
      prev.includes(sportKey) 
        ? prev.filter(s => s !== sportKey)
        : [...prev, sportKey]
    );
  };

  // Merged + sorted view of both pipelines' results
  const topMarkets = useMemo(() => {
    const combined = [...aceMarkets, ...buckeyeMarkets];
    return combined.sort((a: any, b: any) => {
      if (sortBy === 'ev') {
        const evA = parseFloat(a.ev?.replace('%', '') || '0');
        const evB = parseFloat(b.ev?.replace('%', '') || '0');
        return sortDir === 'desc' ? evB - evA : evA - evB;
      }
      if (sortBy === 'start_time') {
        const da = parseStartTime(a.start_time);
        const db = parseStartTime(b.start_time);
        return sortDir === 'desc'
          ? (db ? db.valueOf() : 0) - (da ? da.valueOf() : 0)
          : (da ? da.valueOf() : 0) - (db ? db.valueOf() : 0);
      }
      if (sortBy === 'pinnacle_limit') {
        const va = a.pinnacle_limit ?? -1;
        const vb = b.pinnacle_limit ?? -1;
        return sortDir === 'desc' ? vb - va : va - vb;
      }
      return 0;
    });
  }, [aceMarkets, buckeyeMarkets, sortBy, sortDir]);

  const evLabel = (v: number, isMax: boolean) =>
    isMax && v >= EV_MAX_SLIDER ? 'All' : `${v}%`;

  const filteredMarkets = topMarkets.filter(row => {
    const v = parseFloat(row.ev?.replace('%', '') || '0');
    const passMin = v >= minEv;
    const passMax = maxEv >= EV_MAX_SLIDER ? true : v <= maxEv;
    if (!passMin || !passMax) return false;
    if (evNext24h) {
      const start = parseStartTime(row.start_time);
      const isSoon = !!start && start.isAfter(dayjs()) && start.diff(dayjs(), 'hour') <= 24;
      if (!isSoon) return false;
    }
    return true;
  });

  const sliderSx = {
    color: 'rgba(255,255,255,0.5)',
    '& .MuiSlider-thumb': { width: 12, height: 12, bgcolor: '#F5F5F5', boxShadow: 'none', '&:hover': { boxShadow: '0 0 0 6px rgba(255,255,255,0.08)' } },
    '& .MuiSlider-rail': { bgcolor: 'rgba(255,255,255,0.1)' },
    '& .MuiSlider-track': { bgcolor: 'rgba(255,255,255,0.4)', border: 'none' },
    '& .MuiSlider-valueLabel': {
      bgcolor: '#1a1a1a',
      border: '1px solid rgba(255,255,255,0.12)',
      fontSize: '0.7rem',
      color: '#F5F5F5',
    },
  };

  return (
    <>
      <Box sx={{ display: 'flex', gap: 2, mb: 2, justifyContent: 'flex-start', flexWrap: 'wrap', alignItems: 'center' }}>
        <Button
          variant="outlined"
          size="small"
          sx={{
            color: '#9CA3AF',
            borderColor: 'rgba(255,255,255,0.1)',
            borderRadius: 1.5,
            fontWeight: 500,
            px: 2,
            py: 0.5,
            fontSize: '0.75rem',
            minWidth: 'auto',
            height: 32,
            textTransform: 'none',
            lineHeight: 1.2,
            bgcolor: 'rgba(255,255,255,0.04)',
            '&:hover': { bgcolor: 'rgba(255,255,255,0.07)', borderColor: 'rgba(255,255,255,0.2)', color: '#F5F5F5' },
          }}
          onClick={handleGetEventIds}
        >
          Get Event IDs
          {eventIdsLastRun && (
            <Box component="span" sx={{ ml: 0.75, fontSize: '0.65rem', color: '#666', fontWeight: 400 }}>
              ({dayjs(eventIdsLastRun).fromNow()})
            </Box>
          )}
        </Button>
        <Button
          variant="outlined"
          size="small"
          onClick={() => setShowSportSelection(!showSportSelection)}
          sx={{
            color: showSportSelection ? '#F5F5F5' : '#9CA3AF',
            borderColor: showSportSelection ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.1)',
            borderRadius: 1.5,
            fontWeight: 500,
            px: 2,
            py: 0.5,
            fontSize: '0.75rem',
            minWidth: 'auto',
            height: 32,
            textTransform: 'none',
            lineHeight: 1.2,
            bgcolor: showSportSelection ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.04)',
            '&:hover': { bgcolor: 'rgba(255,255,255,0.07)', borderColor: 'rgba(255,255,255,0.2)', color: '#F5F5F5' },
          }}
        >
          {showSportSelection ? <ExpandLess sx={{ fontSize: 16 }} /> : <ExpandMore sx={{ fontSize: 16 }} />} Select Sports
        </Button>
        <Button
          variant="outlined"
          size="small"
          disabled={pipelineRunning}
          sx={{
            color: pipelineRunning ? '#32D74B' : '#9CA3AF',
            borderColor: pipelineRunning ? 'rgba(50,215,75,0.3)' : 'rgba(255,255,255,0.1)',
            borderRadius: 1.5,
            fontWeight: 500,
            px: 2,
            py: 0.5,
            fontSize: '0.75rem',
            minWidth: 'auto',
            height: 32,
            textTransform: 'none',
            lineHeight: 1.2,
            bgcolor: pipelineRunning ? 'rgba(50,215,75,0.06)' : 'rgba(255,255,255,0.04)',
            '&:hover': { bgcolor: 'rgba(255,255,255,0.07)', borderColor: 'rgba(255,255,255,0.2)', color: '#F5F5F5' },
            '&.Mui-disabled': { color: '#32D74B', borderColor: 'rgba(50,215,75,0.3)', opacity: 1 },
          }}
          onClick={handleRunCalculations}
        >
          {pipelineRunning ? 'Running…' : `Buckeye${selectedSports.length > 0 ? ` (${selectedSports.length})` : ''}`}
        </Button>
        <Button
          variant="outlined"
          size="small"
          sx={{
            color: '#9CA3AF',
            borderColor: 'rgba(255,255,255,0.1)',
            borderRadius: 1.5,
            fontWeight: 500,
            px: 2,
            py: 0.5,
            fontSize: '0.75rem',
            minWidth: 'auto',
            height: 32,
            textTransform: 'none',
            lineHeight: 1.2,
            bgcolor: 'rgba(255,255,255,0.04)',
            '&:hover': { bgcolor: 'rgba(255,255,255,0.07)', borderColor: 'rgba(255,255,255,0.2)', color: '#F5F5F5' },
          }}
          onClick={handleRunAceCalculations}
        >
          Ace
        </Button>

        {/* Divider */}
        <Box sx={{ width: '1px', height: 24, bgcolor: 'rgba(255,255,255,0.12)', mx: 0.5 }} />

        {/* EV Filter — always inline, no toggle needed */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: 1.5, py: 0.5, border: '1px solid rgba(255,255,255,0.08)', borderRadius: 1.5, height: 32, minWidth: 240 }}>
          <TuneRounded sx={{ fontSize: '0.95rem', color: '#B0B0B0', flexShrink: 0 }} />
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0, flex: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography sx={{ fontSize: '0.7rem', color: '#777', width: 26, flexShrink: 0 }}>Min</Typography>
              <Slider
                value={minEv}
                onChange={(_, v) => setMinEv(v as number)}
                min={0} max={EV_MAX_SLIDER} step={0.5}
                valueLabelDisplay="auto"
                valueLabelFormat={v => evLabel(v, false)}
                sx={{ ...sliderSx, py: 0.5, my: 0 }}
              />
              <Typography sx={{ fontSize: '0.7rem', color: '#9CA3AF', width: 28, textAlign: 'right', flexShrink: 0 }}>
                {evLabel(minEv, false)}
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography sx={{ fontSize: '0.7rem', color: '#777', width: 26, flexShrink: 0 }}>Max</Typography>
              <Slider
                value={maxEv}
                onChange={(_, v) => setMaxEv(v as number)}
                min={0} max={EV_MAX_SLIDER} step={0.5}
                valueLabelDisplay="auto"
                valueLabelFormat={v => evLabel(v, true)}
                sx={{ ...sliderSx, py: 0.5, my: 0 }}
              />
              <Typography sx={{ fontSize: '0.7rem', color: '#9CA3AF', width: 28, textAlign: 'right', flexShrink: 0 }}>
                {evLabel(maxEv, true)}
              </Typography>
            </Box>
          </Box>
        </Box>

      </Box>
      <Collapse in={showSportSelection}>
        <Box sx={{ mb: 2, p: 2, bgcolor: 'rgba(26, 26, 26, 0.5)', borderRadius: 2, border: '1px solid rgba(255, 255, 255, 0.1)' }}>
          <Typography variant="body2" sx={{ color: '#B0B0B0', mb: 1.5, fontWeight: 500 }}>
            Select sports to scrape (leave empty for all sports):
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            {sports.map(sport => (
              <FormControlLabel
                key={sport.key}
                control={
                  <Checkbox
                    checked={selectedSports.includes(sport.key)}
                    onChange={() => toggleSport(sport.key)}
                    sx={{
                      color: '#2E7D32',
                      '&.Mui-checked': {
                        color: '#2E7D32',
                      },
                    }}
                  />
                }
                label={sport.label}
                sx={{
                  color: selectedSports.includes(sport.key) ? '#FFFFFF' : '#B0B0B0',
                  '& .MuiFormControlLabel-label': {
                    fontSize: '0.875rem',
                  },
                }}
              />
            ))}
          </Box>
          {selectedSports.length > 0 && (
            <Button
              size="small"
              onClick={() => setSelectedSports([])}
              sx={{
                mt: 1,
                color: '#B0B0B0',
                textTransform: 'none',
                fontSize: '0.75rem',
                '&:hover': {
                  color: '#FFFFFF',
                },
              }}
            >
              Clear Selection
            </Button>
          )}
        </Box>
      </Collapse>
      {(aceLastUpdate || buckeyeLastUpdate || topMarkets.length > 0) && (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1, ml: 0.5, flexWrap: 'wrap', gap: 0.5 }}>
          <Box sx={{ display: 'flex', gap: 2 }}>
            {aceLastUpdate && (
              <Typography variant="body2" sx={{ color: '#aaa', fontSize: '0.8rem' }}>
                Ace: {dayjs(aceLastUpdate).format('HH:mm:ss')} ({dayjs(aceLastUpdate).fromNow()})
              </Typography>
            )}
            {buckeyeLastUpdate && (
              <Typography variant="body2" sx={{ color: '#aaa', fontSize: '0.8rem' }}>
                Buckeye: {dayjs(buckeyeLastUpdate).format('HH:mm:ss')} ({dayjs(buckeyeLastUpdate).fromNow()})
              </Typography>
            )}
          </Box>
          {topMarkets.length > 0 && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {/* 24h toggle for EV table */}
              <Box
                onClick={() => setEvNext24h(v => !v)}
                sx={{
                  px: 1, py: 0.25,
                  fontSize: '0.7rem', fontWeight: evNext24h ? 700 : 400,
                  color: evNext24h ? '#FFB300' : '#555',
                  bgcolor: evNext24h ? 'rgba(255,179,0,0.1)' : 'transparent',
                  border: `1px solid ${evNext24h ? 'rgba(255,179,0,0.4)' : 'rgba(255,255,255,0.06)'}`,
                  borderRadius: 1,
                  cursor: 'pointer', userSelect: 'none',
                }}
              >
                ⏱ 24h
              </Box>
              <Typography variant="body2" sx={{ color: '#555', fontSize: '0.75rem' }}>
                Showing {filteredMarkets.length} of {topMarkets.length} bets
                {aceMarkets.length > 0 && buckeyeMarkets.length > 0 && (
                  <Box component="span" sx={{ color: '#555', ml: 0.5 }}>({aceMarkets.length} Ace + {buckeyeMarkets.length} Buckeye)</Box>
                )}
                {(minEv > 0 || maxEv < EV_MAX_SLIDER || evNext24h) && <Box component="span" sx={{ color: '#9CA3AF', ml: 0.5 }}>(filtered)</Box>}
              </Typography>
            </Box>
          )}
        </Box>
      )}
      {loading && <CircularProgress sx={{ mb: 2 }} />}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {message && <Alert severity="success" sx={{ mb: 2 }}>{message}</Alert>}
      {pipelineRunning && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Streaming pipeline is running... Results will appear in real-time as matches are found.
        </Alert>
      )}
      <TableContainer sx={{ 
        background: 'transparent', 
        borderRadius: 1.5, 
        border: '1px solid rgba(255,255,255,0.06)',
      }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{
              '& .MuiTableCell-root': {
                borderBottom: '1px solid rgba(255,255,255,0.06)',
                py: 1.5,
                bgcolor: 'rgba(255,255,255,0.02)',
              }
            }}>
              {([
                { label: 'Matchup', align: 'left' as const },
                { label: 'League', align: 'left' as const },
                { label: 'Bet', align: 'left' as const },
                { label: 'Book Odds', align: 'center' as const },
                { label: 'Pinnacle NVP', align: 'center' as const },
              ]).map(col => (
                <TableCell key={col.label} align={col.align} sx={{
                  color: '#6B7280',
                  fontWeight: 600,
                  fontSize: '0.6875rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.07em',
                }}>
                  {col.label}
                </TableCell>
              ))}
              <TableCell
                align="center"
                onClick={() => { setSortBy('ev'); setSortDir(d => (sortBy === 'ev' && d === 'desc' ? 'asc' : 'desc')); }}
                sx={{ color: sortBy === 'ev' ? '#F5F5F5' : '#6B7280', fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.07em', cursor: 'pointer', userSelect: 'none', '&:hover': { color: '#F5F5F5' } }}
                title="Sort by EV"
              >
                EV {sortBy === 'ev' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
              </TableCell>
              <TableCell
                onClick={() => { setSortBy('start_time'); setSortDir(d => (sortBy === 'start_time' && d === 'desc' ? 'asc' : 'desc')); }}
                sx={{ color: sortBy === 'start_time' ? '#F5F5F5' : '#6B7280', fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.07em', cursor: 'pointer', userSelect: 'none', '&:hover': { color: '#F5F5F5' } }}
                title="Sort by Start Time"
              >
                Start Time {sortBy === 'start_time' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
              </TableCell>
              <TableCell
                align="right"
                onClick={() => { setSortBy('pinnacle_limit'); setSortDir(d => (sortBy === 'pinnacle_limit' && d === 'desc' ? 'asc' : 'desc')); }}
                sx={{ color: sortBy === 'pinnacle_limit' ? '#F5F5F5' : '#6B7280', fontWeight: 600, fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.07em', whiteSpace: 'nowrap', cursor: 'pointer', userSelect: 'none', '&:hover': { color: '#F5F5F5' } }}
                title="Sort by Pin Limit"
              >
                Pin Limit {sortBy === 'pinnacle_limit' ? (sortDir === 'desc' ? '↓' : '↑') : ''}
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredMarkets.length === 0 && !loading && !error ? (
              <TableRow sx={{ '&:hover': { backgroundColor: 'transparent' } }}>
                <TableCell colSpan={8} sx={{ border: 'none', py: 5, px: 3 }}>
                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5 }}>
                    {topMarkets.length > 0
                      ? <FilterAlt sx={{ fontSize: 18, color: '#374151', mt: 0.15, flexShrink: 0, strokeWidth: 1.5 }} />
                      : <SearchOff sx={{ fontSize: 18, color: '#374151', mt: 0.15, flexShrink: 0, strokeWidth: 1.5 }} />
                    }
                    <Box>
                      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 500, color: '#6B7280', mb: 0.25 }}>
                        {topMarkets.length > 0 ? 'No bets match the active filters' : 'No markets loaded'}
                      </Typography>
                      <Typography sx={{ fontSize: '0.75rem', color: '#6B7280' }}>
                        {topMarkets.length > 0
                          ? <>EV range <span style={{ color: '#9CA3AF' }}>{minEv}%–{maxEv >= EV_MAX_SLIDER ? '∞' : `${maxEv}%`}</span>{evNext24h ? <>, next <span style={{ color: '#9CA3AF' }}>24 h</span> only</> : ''}. Widen the range or clear filters to see all {topMarkets.length} bets.</>
                          : <>Run <span style={{ color: '#9CA3AF' }}>Buckeye</span> or <span style={{ color: '#9CA3AF' }}>Ace</span> to populate the table.</>
                        }
                      </Typography>
                    </Box>
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              filteredMarkets.map((row, idx) => (
                <TableRow 
                  key={idx}
                  sx={{
                    '&:hover': { backgroundColor: 'rgba(255,255,255,0.03)' },
                    '& .MuiTableCell-root': {
                      borderBottom: '1px solid rgba(255,255,255,0.04)',
                      py: 1.25,
                      verticalAlign: 'middle',
                    }
                  }}
                >
                  <TableCell sx={{ color: '#F5F5F5', fontWeight: 500, fontSize: '0.875rem', fontFamily: '"Inter", "SF Pro Display", "Helvetica Neue", Arial, sans-serif' }}>
                    {row.matchup}
                  </TableCell>
                  <TableCell sx={{ color: '#9CA3AF', fontWeight: 400, fontSize: '0.8125rem', fontFamily: '"Inter", "SF Pro Display", "Helvetica Neue", Arial, sans-serif' }}>
                    {row.league}
                  </TableCell>
                  <TableCell sx={{ color: '#F5F5F5', fontWeight: 500, fontSize: '0.8125rem', fontFamily: '"Inter", "SF Pro Display", "Helvetica Neue", Arial, sans-serif' }}>
                    {row.bet}
                  </TableCell>
                  <TableCell align="center" sx={{ color: '#9CA3AF', fontSize: '0.8125rem', fontFamily: '"JetBrains Mono", "Fira Code", "Consolas", monospace', fontVariantNumeric: 'tabular-nums' }}>
                    {row.betbck_odds || row.ace_odds || 'N/A'}
                  </TableCell>
                  <TableCell align="center" sx={{ color: '#9CA3AF', fontSize: '0.8125rem', fontFamily: '"JetBrains Mono", "Fira Code", "Consolas", monospace', fontVariantNumeric: 'tabular-nums' }}>
                    {row.pinnacle_nvp}
                  </TableCell>
                  <TableCell align="center">
                    {parseFloat(row.ev) > 0 ? (
                      <span style={{ color: '#32D74B', fontWeight: 700, fontSize: '0.875rem', fontFamily: '"JetBrains Mono", "Fira Code", "Consolas", monospace', fontVariantNumeric: 'tabular-nums' }}>
                        {row.ev}
                      </span>
                    ) : (
                      <span style={{ color: '#4B5563', fontSize: '0.8125rem', fontFamily: '"JetBrains Mono", "Fira Code", "Consolas", monospace' }}>{row.ev}</span>
                    )}
                  </TableCell>
                  <TableCell align="left" sx={{ whiteSpace: 'nowrap', color: '#6B7280', fontSize: '0.8125rem', fontFamily: '"JetBrains Mono", "Fira Code", "Consolas", monospace', fontVariantNumeric: 'tabular-nums' }}>
                    {(() => {
                      const parsed = parseStartTime(row.start_time);
                      return parsed ? parsed.format('M/D/YY h:mm A') : (typeof row.start_time === 'string' ? row.start_time : '');
                    })()}
                    {(() => {
                      const start = parseStartTime(row.start_time);
                      const isSoon = !!start && start.isAfter(dayjs()) && start.diff(dayjs(), 'hour') <= 24;
                      return isSoon ? (
                        <Box component="span" sx={{ display: 'inline-block', ml: 1, width: 6, height: 6, bgcolor: '#F59E0B', borderRadius: '50%', verticalAlign: 'middle' }} />
                      ) : null;
                    })()}
                  </TableCell>
                  <TableCell align="right" sx={{ whiteSpace: 'nowrap', color: '#6B7280', fontSize: '0.8125rem', fontFamily: '"JetBrains Mono", "Fira Code", "Consolas", monospace', fontVariantNumeric: 'tabular-nums' }}>
                    {row.pinnacle_limit != null ? `${row.pinnacle_limit}` : ''}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* ── Wong Teaser Scanner ─────────────────────────────────────────── */}
      {wongTeasers && (
        <Box sx={{ mt: 3 }}>
          {/* Header row */}
          <Box
            onClick={() => setWongExpanded(e => !e)}
            sx={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              cursor: 'pointer', userSelect: 'none',
              px: 2, py: 1.25,
              bgcolor: 'rgba(26,26,26,0.9)',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: wongExpanded ? '8px 8px 0 0' : 2,
              '&:hover': { borderColor: 'rgba(255,255,255,0.12)' },
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Typography sx={{ color: '#9CA3AF', fontWeight: 600, fontSize: '0.875rem', letterSpacing: '0.01em' }}>
                Wong Teaser Scanner
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.75 }}>
                {wongTeasers.qualifying_legs_6pt > 0 && (
                  <Box sx={{ px: 1, py: 0.25, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 1, fontSize: '0.72rem', color: '#6B7280' }}>
                    {wongTeasers.qualifying_legs_6pt} × 6pt leg{wongTeasers.qualifying_legs_6pt !== 1 ? 's' : ''}
                  </Box>
                )}
                {wongTeasers.qualifying_legs_10pt > 0 && (
                  <Box sx={{ px: 1, py: 0.25, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 1, fontSize: '0.72rem', color: '#6B7280' }}>
                    {wongTeasers.qualifying_legs_10pt} × 10pt leg{wongTeasers.qualifying_legs_10pt !== 1 ? 's' : ''}
                  </Box>
                )}
                {wongTeasers.qualifying_legs_6pt === 0 && wongTeasers.qualifying_legs_10pt === 0 && (
                  <Box sx={{ px: 1, py: 0.25, fontSize: '0.72rem', color: '#555' }}>No qualifying legs this week</Box>
                )}
              </Box>
            </Box>
            {wongExpanded ? <ExpandLess sx={{ color: '#6B7280', fontSize: '1.1rem' }} /> : <ExpandMore sx={{ color: '#6B7280', fontSize: '1.1rem' }} />}
          </Box>

          <Collapse in={wongExpanded}>
            <Box sx={{ border: '1px solid rgba(255,255,255,0.06)', borderTop: 'none', borderRadius: '0 0 8px 8px', bgcolor: 'rgba(20,20,20,0.95)', p: 2 }}>

              {/* ── Type toggle ────────────────────────────────────────────── */}
              {(wongTeasers.qualifying_legs_6pt > 0 || wongTeasers.qualifying_legs_10pt > 0) && (
                <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                  {(['6pt', '10pt'] as const).map(t => (
                    <Button
                      key={t}
                      size="small"
                      onClick={() => setWongTeaserType(t)}
                      sx={{
                        fontSize: '0.78rem', textTransform: 'none', borderRadius: 1.5,
                        px: 2, py: 0.4,
                        color: wongTeaserType === t ? '#F5F5F5' : '#555',
                        border: `1px solid ${wongTeaserType === t ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.08)'}`,
                        bgcolor: wongTeaserType === t ? 'rgba(255,255,255,0.07)' : 'transparent',
                        '&:hover': { borderColor: 'rgba(255,255,255,0.2)', color: '#D1D5DB' },
                      }}
                    >
                      {t}
                    </Button>
                  ))}
                </Box>
              )}

              {/* ── Qualifying legs list ──────────────────────────────────── */}
              {wongTeaserType === '6pt' && wongTeasers.qualifying_legs_6pt === 0 && (
                <Typography sx={{ color: '#555', fontSize: '0.82rem', mb: 2, fontStyle: 'italic' }}>
                  No 6pt qualifying legs found in current slate (need NFL spreads between ±7.5–8.5 or ±1.5–2.5 with Pin limit ≥ 2,000).
                </Typography>
              )}
              {wongTeaserType === '10pt' && wongTeasers.qualifying_legs_10pt === 0 && (
                <Typography sx={{ color: '#555', fontSize: '0.82rem', mb: 2, fontStyle: 'italic' }}>
                  No 10pt qualifying legs found (need NFL road-team spreads at ±1.5/2/2.5 or ±9.5/10/10.5 with Pin limit ≥ 2,000).
                </Typography>
              )}

              {/* Legs grid */}
              {(() => {
                const rawLegs = wongTeaserType === '6pt'
                  ? (wongTeasers.legs_6pt || [])
                  : (wongTeasers.legs_10pt || []);
                if (rawLegs.length === 0) return null;
                // Sort: priority (road + low total) first, then by underlying Pinnacle EV desc
                const legs = [...rawLegs].sort((a: any, b: any) => {
                  const aPri = (a.is_road && a.low_total) ? 1 : 0;
                  const bPri = (b.is_road && b.low_total) ? 1 : 0;
                  if (bPri !== aPri) return bPri - aPri;
                  return (b.main_line_ev_pct ?? 0) - (a.main_line_ev_pct ?? 0);
                });
                return (
                  <Box sx={{ mb: 2.5 }}>
                    <Typography sx={{ fontSize: '0.74rem', color: '#666', mb: 1, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Qualifying Legs ({legs.length}) — ranked by priority then spread EV
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                      {legs.map((leg: any, i: number) => (
                        <Box key={i} sx={{
                          px: 1.5, py: 1,
                          bgcolor: '#151515',
                          border: '1px solid rgba(255,255,255,0.06)',
                          borderRadius: 1.5,
                          minWidth: 200,
                          flex: '0 1 auto',
                        }}>
                          <Box sx={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 1 }}>
                            <Typography sx={{ fontSize: '0.78rem', color: '#ddd', fontWeight: 600, lineHeight: 1.3 }}>
                              {leg.bet}
                            </Typography>
                            {leg.main_line_ev_pct != null && leg.main_line_ev_pct !== 0 && (
                              <Box sx={{ fontSize: '0.68rem', color: leg.main_line_ev_pct >= 0 ? '#32D74B' : '#aaa', fontFamily: 'monospace', fontWeight: 600, whiteSpace: 'nowrap' }}>
                                {leg.main_line_ev_pct >= 0 ? '+' : ''}{leg.main_line_ev_pct.toFixed(2)}% EV
                              </Box>
                            )}
                          </Box>
                          <Typography sx={{ fontSize: '0.7rem', color: '#777', lineHeight: 1.3 }}>
                            {leg.matchup}
                          </Typography>
                          <Box sx={{ display: 'flex', gap: 0.75, mt: 0.5, flexWrap: 'wrap', alignItems: 'center' }}>
                            <Box sx={{ fontSize: '0.68rem', color: '#F5F5F5', fontFamily: 'monospace' }}>
                              → teased to {leg.teased_line > 0 ? '+' : ''}{leg.teased_line}
                            </Box>
                            {leg.pin_nvp && (
                              <Box sx={{ fontSize: '0.68rem', color: '#888', fontFamily: 'monospace' }}>NVP {leg.pin_nvp}</Box>
                            )}
                          </Box>
                          <Box sx={{ display: 'flex', gap: 0.75, mt: 0.5, flexWrap: 'wrap', alignItems: 'center' }}>
                            {leg.is_road && <Box component="span" sx={{ fontSize: '0.65rem', color: '#9CA3AF' }}>Road</Box>}
                            {leg.is_road && (leg.low_total || leg.pin_limit >= 5000) && <Box component="span" sx={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.15)' }}>·</Box>}
                            {leg.low_total && <Box component="span" sx={{ fontSize: '0.65rem', color: '#9CA3AF' }}>O/U {leg.game_total}</Box>}
                            {leg.low_total && leg.pin_limit >= 5000 && <Box component="span" sx={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.15)' }}>·</Box>}
                            {leg.pin_limit >= 5000 && <Box component="span" sx={{ fontSize: '0.65rem', color: '#9CA3AF' }}>Lim {(leg.pin_limit/1000).toFixed(0)}k</Box>}
                          </Box>
                        </Box>
                      ))}
                    </Box>
                  </Box>
                );
              })()}

              {/* ── Combos ────────────────────────────────────────────────── */}
              {(() => {
                const combos: any[] = wongTeaserType === '6pt'
                  ? (wongTeasers.combos_6pt || [])
                  : (wongTeasers.combos_10pt || []);
                if (combos.length === 0) return null;

                const bySize: Record<number, any[]> = {};
                combos.forEach(c => { (bySize[c.n_teams] = bySize[c.n_teams] || []).push(c); });

                // Balanced "best picks": top 2 per size bucket (avoids 5-leggers monopolising the list)
                const bestPicks: any[] = [];
                Object.keys(bySize).sort((a, b) => Number(a) - Number(b)).forEach(n => {
                  const sorted = [...bySize[Number(n)]].sort((a, b) => (b.ev_blended_pct ?? b.ev_pct) - (a.ev_blended_pct ?? a.ev_pct));
                  bestPicks.push(...sorted.slice(0, 2));
                });

                const ComboCard = ({ combo, ci }: { combo: any; ci: number }) => (
                  <Box key={ci} sx={{
                    p: 1.5,
                    bgcolor: '#151515',
                    border: '1px solid rgba(255,255,255,0.06)',
                    borderRadius: 1.5,
                    minWidth: 220,
                    flex: '0 1 auto',
                    position: 'relative',
                  }}>
                    {combo.flagged && (
                      <Box sx={{ position: 'absolute', top: 6, right: 8, fontSize: '0.62rem', color: '#9CA3AF', fontWeight: 600, letterSpacing: '0.04em' }}>EDGE</Box>
                    )}
                    {combo.priority_score > 0 && (
                      <Box sx={{ position: 'absolute', top: combo.flagged ? 20 : 6, right: 8, fontSize: '0.62rem', color: '#6B7280' }}>
                        {'↑'.repeat(combo.priority_score)} pri
                      </Box>
                    )}
                    {combo.legs.map((leg: any, li: number) => (
                      <Box key={li} sx={{ mb: li < combo.legs.length - 1 ? 0.75 : 0 }}>
                        <Typography sx={{ fontSize: '0.76rem', color: '#ddd', fontWeight: 600, lineHeight: 1.2, pr: combo.flagged || combo.priority_score > 0 ? 4 : 0 }}>
                          {leg.bet}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 0.75, alignItems: 'center', flexWrap: 'wrap' }}>
                          <Typography sx={{ fontSize: '0.68rem', color: '#9CA3AF', fontFamily: 'monospace' }}>
                            → {leg.teased_line > 0 ? '+' : ''}{leg.teased_line}
                          </Typography>
                          {leg.is_road && <Box component="span" sx={{ fontSize: '0.62rem', color: '#6B7280' }}>road</Box>}
                          {leg.low_total && <Box component="span" sx={{ fontSize: '0.62rem', color: '#6B7280' }}>O/U {leg.game_total}</Box>}
                        </Box>
                      </Box>
                    ))}
                    <Box sx={{ mt: 1, pt: 0.75, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography sx={{ fontSize: '0.65rem', color: '#888', fontFamily: 'monospace' }}>
                          {combo.n_teams}T {combo.book_odds}
                        </Typography>
                        <Typography sx={{ fontSize: '0.7rem', color: '#32D74B', fontWeight: 700 }}>
                          +{combo.ev_hist_pct ?? combo.ev_blended_pct ?? combo.ev_pct}% EV
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography sx={{ fontSize: '0.62rem', color: '#666' }}>
                          Lim {(combo.min_pin_limit / 1000).toFixed(0)}k+
                        </Typography>
                        <Typography sx={{ fontSize: '0.62rem', color: '#888', fontFamily: 'monospace' }}>
                          {combo.combined_prob_hist_pct ?? combo.combined_prob_blended_pct}% to win
                        </Typography>
                      </Box>
                    </Box>
                  </Box>
                );

                return (
                  <Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: combosExpanded ? 1.5 : 0 }}>
                      <Box
                        sx={{ display: 'flex', alignItems: 'center', gap: 0.75, cursor: 'pointer', userSelect: 'none' }}
                        onClick={() => setCombosExpanded(v => !v)}
                      >
                        {combosExpanded
                          ? <ExpandLess sx={{ fontSize: '0.9rem', color: '#666' }} />
                          : <ExpandMore sx={{ fontSize: '0.9rem', color: '#666' }} />}
                        <Typography sx={{ fontSize: '0.74rem', color: '#666', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          Best Combinations ({combos.length} total)
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', gap: 0.75 }}>
                        {(['best', 'grouped'] as const).map(v => (
                          <Button key={v} size="small" onClick={() => setWongComboView(v)} sx={{
                            fontSize: '0.7rem', textTransform: 'none', borderRadius: 1.5, px: 1.5, py: 0.3,
                            color: wongComboView === v ? '#F5F5F5' : '#555',
                            border: `1px solid ${wongComboView === v ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.07)'}`,
                            bgcolor: wongComboView === v ? 'rgba(255,255,255,0.07)' : 'transparent',
                            '&:hover': { borderColor: 'rgba(255,255,255,0.2)', color: '#D1D5DB' },
                          }}>
                            {v === 'best' ? 'Best Picks' : 'By Size'}
                          </Button>
                        ))}
                      </Box>
                    </Box>

                    {combosExpanded && wongComboView === 'best' && (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                        {bestPicks.map((combo, ci) => <ComboCard key={ci} combo={combo} ci={ci} />)}
                      </Box>
                    )}

                    {combosExpanded && wongComboView === 'grouped' && Object.entries(bySize).sort(([a], [b]) => Number(a) - Number(b)).map(([n, grpCombos]) => (
                      <Box key={n} sx={{ mb: 2 }}>
                        <Typography sx={{ fontSize: '0.76rem', color: '#888', fontWeight: 600, mb: 1 }}>
                          {n}-Team {wongTeaserType} &nbsp;
                          <span style={{ color: '#9CA3AF', fontFamily: 'monospace' }}>{grpCombos[0].book_odds}</span>
                          &nbsp;· Break-even <span style={{ color: '#999' }}>{grpCombos[0].break_even_pct}%/leg</span>
                        </Typography>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                          {grpCombos.slice(0, 8).map((combo: any, ci: number) => (
                            <ComboCard key={ci} combo={combo} ci={ci} />
                          ))}
                        </Box>
                      </Box>
                    ))}
                  </Box>
                );
              })()}

              {/* Footer note */}
              <Typography sx={{ mt: 2, fontSize: '0.68rem', color: '#444', lineHeight: 1.6 }}>
                Historical win rates: 75.8%/leg (6pt, 2003+ data) · 83%/leg (10pt, road only, 3-team -120).
                Qualifiers cross key numbers 3 & 7 (6pt) or 3, 7 & 10 (10pt).
                <strong style={{ color: '#555' }}> EV</strong> = hist win rate (+ 1pp for O/U ≤49) raised to n_legs, × book payout − 1.
                "X% to win" = the actual probability all legs hit. Pin limit ≥ 2,000. Road + O/U ≤49 prioritized. One line per game.
              </Typography>
            </Box>
          </Collapse>
        </Box>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          PARLAYS
      ══════════════════════════════════════════════════════════════════ */}
      {parlays && (() => {
        // Two independent pools — switch entirely when 24h is active
        const parlayList: any[]  = parlayNext24h
          ? (parlays.parlays_24h || [])
          : (parlays.parlays    || []);
        const count24h: number = (parlays.parlays_24h || []).length;

        return (
        <Box sx={{ mt: 1.5 }}>
          {/* Header row */}
          <Box
            onClick={() => setParlaysExpanded(v => !v)}
            sx={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              px: 2, py: 1.25,
              bgcolor: 'rgba(26,26,26,0.9)',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: parlaysExpanded ? '8px 8px 0 0' : '8px',
              cursor: 'pointer', userSelect: 'none',
              '&:hover': { borderColor: 'rgba(255,255,255,0.12)' },
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Typography sx={{ color: '#9CA3AF', fontWeight: 600, fontSize: '0.875rem', letterSpacing: '0.01em' }}>
                Parlays
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.75, alignItems: 'center' }}>
                {([2, 3, 4] as const).map(n => {
                  const count = parlayList.filter((p: any) => p.n_legs === n).length;
                  return count > 0 ? (
                    <Box key={n} sx={{ px: 1, py: 0.25, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 1, fontSize: '0.72rem', color: '#6B7280' }}>
                      {n}-leg ×{count}
                    </Box>
                  ) : null;
                })}
                {parlays.eligible_legs != null && (
                  <Box sx={{ px: 1, py: 0.25, fontSize: '0.72rem', color: '#555' }}>
                    {parlays.eligible_legs} eligible legs
                  </Box>
                )}
                {/* 24h toggle */}
                <Box
                  onClick={(e) => { e.stopPropagation(); setParlayNext24h(v => !v); }}
                  sx={{
                    px: 1, py: 0.25,
                    fontSize: '0.7rem', fontWeight: parlayNext24h ? 600 : 400,
                    color: parlayNext24h ? '#D1D5DB' : '#555',
                    bgcolor: parlayNext24h ? 'rgba(255,255,255,0.08)' : 'transparent',
                    border: `1px solid ${parlayNext24h ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.06)'}`,
                    borderRadius: 1,
                    cursor: 'pointer', userSelect: 'none',
                  }}
                >
                  24h {parlayNext24h && count24h > 0 ? `(${count24h})` : ''}
                </Box>
              </Box>
            </Box>
            {parlaysExpanded
              ? <ExpandLess sx={{ color: '#6B7280', fontSize: '1.1rem' }} />
              : <ExpandMore sx={{ color: '#6B7280', fontSize: '1.1rem' }} />}
          </Box>

          <Collapse in={parlaysExpanded}>
            <Box sx={{ border: '1px solid rgba(255,255,255,0.06)', borderTop: 'none', borderRadius: '0 0 8px 8px', bgcolor: 'rgba(20,20,20,0.95)', p: 2 }}>

              {parlayList.length === 0 ? (
                <Typography sx={{ color: '#555', fontSize: '0.82rem', fontStyle: 'italic' }}>
                  {parlayNext24h
                    ? 'No qualifying parlays with games in the next 24 hours (need pin_limit ≥ 1,000, leg EV ≥ −1%, odds ≤ +150).'
                    : 'No qualifying parlays found (need pin_limit ≥ 1,000, leg EV ≥ −1%, odds ≤ +150).'}
                </Typography>
              ) : (
                <>
                  {/* Size filter tabs */}
                  <Box sx={{ display: 'flex', gap: 0.75, mb: 1.5, alignItems: 'center' }}>
                    {(['all', 2, 3, 4] as const).map(f => {
                      const label = f === 'all' ? 'All' : `${f}-leg`;
                      const count = f === 'all'
                        ? parlayList.length
                        : parlayList.filter((p: any) => p.n_legs === f).length;
                      const active = parlayLegFilter === f;
                      return count > 0 ? (
                        <Box
                          key={String(f)}
                          onClick={() => setParlayLegFilter(f)}
                          sx={{
                            px: 1.25, py: 0.3,
                            fontSize: '0.72rem', fontWeight: active ? 600 : 400,
                            color: active ? '#F5F5F5' : '#555',
                            bgcolor: active ? 'rgba(255,255,255,0.08)' : 'transparent',
                            border: `1px solid ${active ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.08)'}`,
                            borderRadius: 1,
                            cursor: 'pointer',
                            userSelect: 'none',
                          }}
                        >
                          {label} {count > 0 && <Box component="span" sx={{ opacity: 0.6 }}>({count})</Box>}
                        </Box>
                      ) : null;
                    })}
                    <Typography sx={{ ml: 'auto', fontSize: '0.7rem', color: '#444' }}>
                      {parlayNext24h
                        ? `${(parlays.total_combos_24h ?? 0).toLocaleString()} combos · ${parlays.eligible_legs_24h ?? 0} legs (24h)`
                        : `${(parlays.total_combos ?? 0).toLocaleString()} combos · ${parlays.eligible_legs ?? 0} legs`}
                    </Typography>
                  </Box>

                  {/* Parlay cards */}
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {parlayList
                      .filter((p: any) => parlayLegFilter === 'all' || p.n_legs === parlayLegFilter)
                      .map((parlay: any, pi: number) => (
                      <Box key={pi} sx={{
                        p: 1.5,
                        bgcolor: '#1A1A1A',
                        border: '1px solid rgba(255,255,255,0.06)',
                        borderRadius: 1.5,
                        minWidth: 230,
                        maxWidth: 310,
                        flex: '0 1 auto',
                        position: 'relative',
                      }}>
                        {parlay.same_sport && (
                          <Box sx={{ position: 'absolute', top: 6, right: 8, fontSize: '0.6rem', color: '#6B7280', fontWeight: 500, letterSpacing: '0.04em' }}>
                            ◇ SAME
                          </Box>
                        )}

                        {/* Legs */}
                        {(parlay.legs || []).map((leg: any, li: number) => (
                          <Box key={li} sx={{ mb: li < parlay.legs.length - 1 ? 0.9 : 0 }}>
                            {/* Bet name */}
                            <Typography sx={{ fontSize: '0.76rem', color: '#ddd', fontWeight: 600, lineHeight: 1.25, pr: parlay.same_sport ? 4 : 0 }}>
                              {leg.bet}
                            </Typography>
                            {/* Matchup context */}
                            {leg.matchup && leg.matchup.trim() && (
                              <Typography sx={{ fontSize: '0.61rem', color: '#aaa', lineHeight: 1.25, mb: 0.25 }}>
                                {leg.matchup}
                              </Typography>
                            )}
                            {/* Stats row */}
                            <Box sx={{ display: 'flex', gap: 0.6, alignItems: 'center', flexWrap: 'wrap' }}>
                              <Box component="span" sx={{ fontSize: '0.62rem', color: '#888', fontFamily: 'monospace' }}>
                                {leg.betbck_odds}
                              </Box>
                              {leg.league && (
                                <Box component="span" sx={{ fontSize: '0.6rem', color: '#6B7280' }}>
                                  {leg.league}
                                </Box>
                              )}
                              <Box component="span" sx={{ fontSize: '0.62rem', color: leg.ev_pct >= 0 ? '#32D74B' : '#aaa', fontFamily: 'monospace' }}>
                                {leg.ev_pct >= 0 ? '+' : ''}{leg.ev_pct}% EV
                              </Box>
                              <Box component="span" sx={{ fontSize: '0.6rem', color: '#555' }}>
                                Lim {(leg.pin_limit / 1000).toFixed(0)}k
                              </Box>
                            </Box>
                          </Box>
                        ))}

                        {/* Footer */}
                        <Box sx={{ mt: 1, pt: 0.75, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Typography sx={{ fontSize: '0.67rem', color: '#888', fontFamily: 'monospace', fontWeight: 600 }}>
                              {parlay.n_legs}L &nbsp;{parlay.parlay_odds}
                            </Typography>
                            <Typography sx={{ fontSize: '0.72rem', color: parlay.ev_blended_pct >= 0 ? '#32D74B' : '#aaa', fontWeight: 700 }}>
                              {parlay.ev_blended_pct >= 0 ? '+' : ''}{parlay.ev_blended_pct}% EV
                            </Typography>
                          </Box>
                          <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                            <Typography sx={{ fontSize: '0.62rem', color: '#555' }}>
                              win {parlay.win_prob_pct}%
                            </Typography>
                          </Box>
                        </Box>
                      </Box>
                    ))}
                  </Box>

                  {/* Footer note */}
                  <Typography sx={{ mt: 2, fontSize: '0.68rem', color: '#444', lineHeight: 1.6 }}>
                    Parlay EV = ∏(1 + leg_EV) − 1 · Parlay odds = product of BetBCK decimal odds · Top 10 per size shown.
                    Ranked highest EV to lowest · Pin limit ≥ 1,000 · Leg EV ≥ −1% · Odds ≤ +150 · Max 3 +money legs · One leg per game.
                  </Typography>
                </>
              )}
            </Box>
          </Collapse>
        </Box>
        );
      })()}
    </>
  );
};

export default BuckeyeScraper; 