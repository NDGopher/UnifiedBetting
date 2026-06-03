import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Box, Button, Typography, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, CircularProgress, Alert, FormControlLabel, Checkbox, Collapse, Slider } from '@mui/material';
import MatchingStats from './MatchingStats';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { Analytics, ExpandMore, ExpandLess, TuneRounded } from '@mui/icons-material';
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
  const [wongComboView, setWongComboView] = useState<'top8' | 'grouped'>('top8');
  const [combosExpanded, setCombosExpanded] = useState(false);
  const [parlays, setParlays] = useState<any | null>(null);
  const [parlaysExpanded, setParlaysExpanded] = useState(false);
  const [parlayLegFilter, setParlayLegFilter] = useState<'all' | 2 | 3 | 4>('all');

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
          const { events, total_events, last_run, total_matched } = data.data;
          if (events && events.length > 0) {
            setAceMarkets(events);
            setAceLastUpdate(last_run);
            setMessage(`Ace done: ${total_matched} games matched, ${total_events} EV opportunities`);
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
    setAceMarkets([]);    // Clear ACE results so only Buckeye shows
    setAceLastUpdate(null);
    try {
      console.log('[BuckeyeScraper] Starting streaming Buckeye pipeline...');
      const body = selectedSports.length > 0 ? { sport_filters: selectedSports } : {};
      const res = await fetch(`${API_BASE}/api/run-streaming-pipeline`, { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      console.log('[BuckeyeScraper] Streaming pipeline start response:', data);
      
      if (data.status === 'success') {
        setMessage(data.message || 'Streaming pipeline started - results will appear in real-time');
        console.log('[BuckeyeScraper] Streaming pipeline started successfully - watching for real-time updates...');
        
        // Connect WebSocket for real-time updates
        connectWebSocket();
        
        // Start polling for results while pipeline runs (fallback)
        startPolling();
      } else {
        // Backend rejected (e.g. already running) — restore button state
        setError(data.message || 'Failed to start streaming pipeline');
        setBuckeyeMarkets([]);
        setPipelineRunning(false);
      }
    } catch (err) {
      console.error('[BuckeyeScraper] Error starting streaming pipeline:', err);
      setError('Failed to start streaming pipeline');
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
    setAceMarkets([]); // Clear ACE data
    setAceLastUpdate(null);
    setBuckeyeMarkets([]);  // Clear Buckeye results so only ACE shows
    setBuckeyeLastUpdate(null);
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
    return passMin && passMax;
  });

  const sliderSx = {
    color: '#2E7D32',
    '& .MuiSlider-thumb': { width: 14, height: 14, bgcolor: '#2E7D32' },
    '& .MuiSlider-rail': { bgcolor: 'rgba(255,255,255,0.15)' },
    '& .MuiSlider-track': { bgcolor: '#2E7D32', border: 'none' },
    '& .MuiSlider-valueLabel': {
      bgcolor: '#1a1a1a',
      border: '1px solid rgba(46,125,50,0.5)',
      fontSize: '0.75rem',
      color: '#2E7D32',
    },
  };

  return (
    <>
      <Box sx={{ display: 'flex', gap: 2, mb: 2, justifyContent: 'flex-start', flexWrap: 'wrap', alignItems: 'center' }}>
        <Button
          variant="outlined"
          size="small"
          sx={{
            color: '#2E7D32',
            borderColor: '#2E7D32',
            borderRadius: 2,
            fontWeight: 500,
            px: 2,
            py: 0.5,
            fontSize: '0.875rem',
            minWidth: 'auto',
            height: 36,
            textTransform: 'none',
            lineHeight: 1.2,
            '&:hover': {
              bgcolor: 'rgba(46, 125, 50, 0.1)',
              borderColor: '#2E7D32',
            },
          }}
          onClick={handleGetEventIds}
        >
          Get Event IDs
          {eventIdsLastRun && (
            <Box component="span" sx={{ ml: 0.75, fontSize: '0.7rem', color: 'rgba(46,125,50,0.7)', fontWeight: 400 }}>
              ({dayjs(eventIdsLastRun).fromNow()})
            </Box>
          )}
        </Button>
        <Button
          variant="outlined"
          size="small"
          onClick={() => setShowSportSelection(!showSportSelection)}
          sx={{
            color: showSportSelection ? '#2E7D32' : '#B0B0B0',
            borderColor: showSportSelection ? '#2E7D32' : 'rgba(255, 255, 255, 0.2)',
            borderRadius: 2,
            fontWeight: 500,
            px: 2,
            py: 0.5,
            fontSize: '0.875rem',
            minWidth: 'auto',
            height: 36,
            textTransform: 'none',
            lineHeight: 1.2,
            '&:hover': {
              bgcolor: 'rgba(46, 125, 50, 0.1)',
              borderColor: '#2E7D32',
            },
          }}
        >
          {showSportSelection ? <ExpandLess /> : <ExpandMore />} Select Sports
        </Button>
        <Button
          variant="outlined"
          size="small"
          disabled={pipelineRunning}
          sx={{
            color: pipelineRunning ? '#2E7D32' : (selectedSports.length > 0 ? '#2E7D32' : '#B0B0B0'),
            borderColor: pipelineRunning ? '#2E7D32' : (selectedSports.length > 0 ? '#2E7D32' : 'rgba(255, 255, 255, 0.2)'),
            borderRadius: 2,
            fontWeight: 500,
            px: 2,
            py: 0.5,
            fontSize: '0.875rem',
            minWidth: 'auto',
            height: 36,
            textTransform: 'none',
            lineHeight: 1.2,
            '&:hover': {
              bgcolor: pipelineRunning ? 'rgba(46, 125, 50, 0.1)' : (selectedSports.length > 0 ? 'rgba(46, 125, 50, 0.1)' : 'rgba(255, 255, 255, 0.05)'),
              borderColor: pipelineRunning ? '#2E7D32' : (selectedSports.length > 0 ? '#2E7D32' : 'rgba(255, 255, 255, 0.3)'),
            },
          }}
          onClick={handleRunCalculations}
        >
          {pipelineRunning ? 'Running...' : `Buckeye${selectedSports.length > 0 ? ` (${selectedSports.length})` : ''}`}
        </Button>
        <Button
          variant="outlined"
          size="small"
          sx={{
            color: '#B0B0B0',
            borderColor: 'rgba(255, 255, 255, 0.2)',
            borderRadius: 2,
            fontWeight: 500,
            px: 2,
            py: 0.5,
            fontSize: '0.875rem',
            minWidth: 'auto',
            height: 36,
            textTransform: 'none',
            lineHeight: 1.2,
            '&:hover': {
              bgcolor: 'rgba(255, 255, 255, 0.05)',
              borderColor: 'rgba(255, 255, 255, 0.3)',
            },
          }}
          onClick={handleRunAceCalculations}
        >
          Ace
        </Button>

        {/* Divider */}
        <Box sx={{ width: '1px', height: 24, bgcolor: 'rgba(255,255,255,0.12)', mx: 0.5 }} />

        {/* EV Filter — always inline, no toggle needed */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: 1.5, py: 0.5, border: '1px solid rgba(255,255,255,0.12)', borderRadius: 2, height: 36, minWidth: 260 }}>
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
              <Typography sx={{ fontSize: '0.7rem', color: '#2E7D32', width: 28, textAlign: 'right', flexShrink: 0 }}>
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
              <Typography sx={{ fontSize: '0.7rem', color: maxEv >= EV_MAX_SLIDER ? '#777' : '#2E7D32', width: 28, textAlign: 'right', flexShrink: 0 }}>
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
            <Typography variant="body2" sx={{ color: '#555', fontSize: '0.75rem' }}>
              Showing {filteredMarkets.length} of {topMarkets.length} bets
              {aceMarkets.length > 0 && buckeyeMarkets.length > 0 && (
                <Box component="span" sx={{ color: '#555', ml: 0.5 }}>({aceMarkets.length} Ace + {buckeyeMarkets.length} Buckeye)</Box>
              )}
              {(minEv > 0 || maxEv < EV_MAX_SLIDER) && <Box component="span" sx={{ color: '#2E7D32', ml: 0.5 }}>(filtered)</Box>}
            </Typography>
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
        background: 'rgba(26, 26, 26, 0.8)', 
        borderRadius: 2, 
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        backdropFilter: 'blur(20px)'
      }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{
              '& .MuiTableCell-root': {
                borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                py: 2
              }
            }}>
              <TableCell sx={{ 
                color: '#B0B0B0', 
                fontWeight: 600, 
                fontSize: '0.875rem' 
              }}>
                Matchup
              </TableCell>
              <TableCell sx={{ 
                color: '#B0B0B0', 
                fontWeight: 600, 
                fontSize: '0.875rem' 
              }}>
                League
              </TableCell>
              <TableCell sx={{ 
                color: '#B0B0B0', 
                fontWeight: 600, 
                fontSize: '0.875rem' 
              }}>
                Bet
              </TableCell>
              <TableCell align="center" sx={{ 
                color: '#B0B0B0', 
                fontWeight: 600, 
                fontSize: '0.875rem' 
              }}>
                Book Odds
              </TableCell>
              <TableCell align="center" sx={{ 
                color: '#B0B0B0', 
                fontWeight: 600, 
                fontSize: '0.875rem' 
              }}>
                Pinnacle NVP
              </TableCell>
              <TableCell
                align="center"
                onClick={() => {
                  setSortBy('ev');
                  setSortDir(d => (sortBy === 'ev' && d === 'desc' ? 'asc' : 'desc'));
                }}
                sx={{ 
                  color: '#B0B0B0', 
                  fontWeight: 600, 
                  fontSize: '0.875rem', 
                  cursor: 'pointer', 
                  userSelect: 'none',
                  '&:hover': {
                    color: '#2E7D32'
                  }
                }}
                title="Sort by EV"
              >
                EV
              </TableCell>
              <TableCell
                onClick={() => {
                  setSortBy('start_time');
                  setSortDir(d => (sortBy === 'start_time' && d === 'desc' ? 'asc' : 'desc'));
                }}
                sx={{ 
                  color: '#B0B0B0', 
                  fontWeight: 600, 
                  fontSize: '0.875rem', 
                  cursor: 'pointer', 
                  userSelect: 'none',
                  '&:hover': {
                    color: '#2E7D32'
                  }
                }}
                title="Sort by Start Time"
              >
                Start Time
              </TableCell>
              <TableCell
                align="right"
                onClick={() => {
                  setSortBy('pinnacle_limit');
                  setSortDir(d => (sortBy === 'pinnacle_limit' && d === 'desc' ? 'asc' : 'desc'));
                }}
                sx={{ 
                  color: '#B0B0B0', 
                  fontWeight: 600, 
                  fontSize: '0.875rem', 
                  whiteSpace: 'nowrap', 
                  cursor: 'pointer', 
                  userSelect: 'none',
                  '&:hover': {
                    color: '#2E7D32'
                  }
                }}
                title="Sort by Pin Limit"
              >
                Pin Limit
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredMarkets.length === 0 && !loading && !error ? (
              <TableRow>
                <TableCell colSpan={8} align="center" sx={{ 
                  color: '#9E9E9E', 
                  fontStyle: 'italic',
                  py: 4,
                  fontSize: '0.875rem'
                }}>
                  {topMarkets.length > 0
                    ? `No bets match the current EV filter (${minEv}%–${maxEv >= EV_MAX_SLIDER ? '∞' : `${maxEv}%`}). Try widening the range.`
                    : 'No valid markets found. Click RUN CALCULATIONS to populate or check backend filters.'}
                </TableCell>
              </TableRow>
            ) : (
              filteredMarkets.map((row, idx) => (
                <TableRow 
                  key={idx}
                  sx={{
                    '&:hover': {
                      backgroundColor: 'rgba(46, 125, 50, 0.06)'
                    },
                    '& .MuiTableCell-root': {
                      borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
                      py: 1.5
                    }
                  }}
                >
                  <TableCell sx={{ color: '#FFFFFF', fontWeight: 500, fontSize: '0.875rem' }}>
                    {row.matchup}
                  </TableCell>
                  <TableCell sx={{ color: '#FFFFFF', fontWeight: 500, fontSize: '0.875rem' }}>
                    {row.league}
                  </TableCell>
                  <TableCell sx={{ color: '#FFFFFF', fontWeight: 500, fontSize: '0.875rem' }}>
                    {row.bet}
                  </TableCell>
                  <TableCell align="center" sx={{ color: '#B0B0B0', fontSize: '0.875rem' }}>
                    {row.betbck_odds || row.ace_odds || 'N/A'}
                  </TableCell>
                  <TableCell align="center" sx={{ color: '#B0B0B0', fontSize: '0.875rem' }}>
                    {row.pinnacle_nvp}
                  </TableCell>
                  <TableCell align="center">
                    {parseFloat(row.ev) > 0 ? (
                      <Box sx={{
                        display: 'inline-block',
                        px: 1.5,
                        py: 0.5,
                        border: '2px solid #2E7D32',
                        borderRadius: 1.5,
                        color: '#2E7D32',
                        fontWeight: 700,
                        fontSize: '0.875rem',
                        bgcolor: 'rgba(46, 125, 50, 0.1)',
                      }}>
                        {row.ev}
                      </Box>
                    ) : (
                      <span style={{ color: '#9E9E9E', fontSize: '0.875rem' }}>{row.ev}</span>
                    )}
                  </TableCell>
                  <TableCell align="left" sx={{ whiteSpace: 'nowrap' }}>
                    {(() => {
                      const parsed = parseStartTime(row.start_time);
                      return parsed ? parsed.format('M/D/YYYY [at] h:mm A') : (typeof row.start_time === 'string' ? row.start_time : '');
                    })()}
                    {(() => {
                      const start = parseStartTime(row.start_time);
                      const isSoon = !!start && start.isAfter(dayjs()) && start.diff(dayjs(), 'hour') <= 24;
                      return isSoon ? (
                        <Box component="span" sx={{ display: 'inline-block', ml: 1, width: 8, height: 8, bgcolor: '#FFD54F', borderRadius: '50%' }} />
                      ) : null;
                    })()}
                  </TableCell>
                  <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
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
              border: '1px solid rgba(255,165,0,0.25)',
              borderRadius: wongExpanded ? '8px 8px 0 0' : 2,
              '&:hover': { borderColor: 'rgba(255,165,0,0.5)' },
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Analytics sx={{ fontSize: '1rem', color: '#FFA500' }} />
              <Typography sx={{ color: '#FFA500', fontWeight: 600, fontSize: '0.9rem' }}>
                Wong Teaser Scanner
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.75 }}>
                {wongTeasers.qualifying_legs_6pt > 0 && (
                  <Box sx={{ px: 1, py: 0.25, bgcolor: 'rgba(255,165,0,0.15)', border: '1px solid rgba(255,165,0,0.3)', borderRadius: 1, fontSize: '0.72rem', color: '#FFA500' }}>
                    {wongTeasers.qualifying_legs_6pt} × 6pt leg{wongTeasers.qualifying_legs_6pt !== 1 ? 's' : ''}
                  </Box>
                )}
                {wongTeasers.qualifying_legs_10pt > 0 && (
                  <Box sx={{ px: 1, py: 0.25, bgcolor: 'rgba(255,200,0,0.12)', border: '1px solid rgba(255,200,0,0.3)', borderRadius: 1, fontSize: '0.72rem', color: '#FFD700' }}>
                    {wongTeasers.qualifying_legs_10pt} × 10pt leg{wongTeasers.qualifying_legs_10pt !== 1 ? 's' : ''}
                  </Box>
                )}
                {wongTeasers.qualifying_legs_6pt === 0 && wongTeasers.qualifying_legs_10pt === 0 && (
                  <Box sx={{ px: 1, py: 0.25, fontSize: '0.72rem', color: '#666' }}>No qualifying legs this week</Box>
                )}
              </Box>
            </Box>
            {wongExpanded ? <ExpandLess sx={{ color: '#FFA500', fontSize: '1.1rem' }} /> : <ExpandMore sx={{ color: '#FFA500', fontSize: '1.1rem' }} />}
          </Box>

          <Collapse in={wongExpanded}>
            <Box sx={{ border: '1px solid rgba(255,165,0,0.25)', borderTop: 'none', borderRadius: '0 0 8px 8px', bgcolor: 'rgba(20,20,20,0.95)', p: 2 }}>

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
                        color: wongTeaserType === t ? '#FFA500' : '#666',
                        border: `1px solid ${wongTeaserType === t ? 'rgba(255,165,0,0.5)' : 'rgba(255,255,255,0.08)'}`,
                        bgcolor: wongTeaserType === t ? 'rgba(255,165,0,0.08)' : 'transparent',
                        '&:hover': { borderColor: 'rgba(255,165,0,0.4)', color: '#FFA500' },
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
                const legs = wongTeaserType === '6pt'
                  ? (wongTeasers.legs_6pt || [])
                  : (wongTeasers.legs_10pt || []);
                if (legs.length === 0) return null;
                return (
                  <Box sx={{ mb: 2.5 }}>
                    <Typography sx={{ fontSize: '0.74rem', color: '#666', mb: 1, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Qualifying Legs ({legs.length})
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                      {legs.map((leg: any, i: number) => (
                        <Box key={i} sx={{
                          px: 1.5, py: 1,
                          bgcolor: 'rgba(255,165,0,0.05)',
                          border: `1px solid ${leg.low_total && leg.is_road ? 'rgba(255,165,0,0.4)' : 'rgba(255,255,255,0.07)'}`,
                          borderRadius: 1.5,
                          minWidth: 200,
                          flex: '0 1 auto',
                        }}>
                          <Typography sx={{ fontSize: '0.78rem', color: '#ddd', fontWeight: 600, lineHeight: 1.3 }}>
                            {leg.bet}
                          </Typography>
                          <Typography sx={{ fontSize: '0.7rem', color: '#777', lineHeight: 1.3 }}>
                            {leg.matchup}
                          </Typography>
                          <Box sx={{ display: 'flex', gap: 0.75, mt: 0.5, flexWrap: 'wrap', alignItems: 'center' }}>
                            <Box sx={{ fontSize: '0.68rem', color: '#FFA500', fontFamily: 'monospace' }}>
                              → teased to {leg.teased_line > 0 ? '+' : ''}{leg.teased_line}
                            </Box>
                            {leg.pin_nvp && (
                              <Box sx={{ fontSize: '0.68rem', color: '#888', fontFamily: 'monospace' }}>NVP {leg.pin_nvp}</Box>
                            )}
                            {leg.projected_prob_pct != null && (
                              <Box sx={{ fontSize: '0.68rem', color: '#4CAF50', fontFamily: 'monospace', fontWeight: 600 }}>
                                proj {leg.projected_prob_pct}%
                              </Box>
                            )}
                          </Box>
                          <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5, flexWrap: 'wrap' }}>
                            {leg.is_road && <Box sx={{ fontSize: '0.65rem', color: '#64B5F6', px: 0.75, py: 0.25, bgcolor: 'rgba(100,181,246,0.1)', borderRadius: 0.75 }}>🏈 Road</Box>}
                            {leg.low_total && <Box sx={{ fontSize: '0.65rem', color: '#81C784', px: 0.75, py: 0.25, bgcolor: 'rgba(129,199,132,0.1)', borderRadius: 0.75 }}>↓ O/U {leg.game_total}</Box>}
                            {leg.pin_limit >= 5000 && <Box sx={{ fontSize: '0.65rem', color: '#CE93D8', px: 0.75, py: 0.25, bgcolor: 'rgba(206,147,216,0.08)', borderRadius: 0.75 }}>Lim {(leg.pin_limit/1000).toFixed(0)}k</Box>}
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

                const top8 = [...combos].sort((a, b) => (b.ev_blended_pct ?? b.ev_pct) - (a.ev_blended_pct ?? a.ev_pct)).slice(0, 8);

                const ComboCard = ({ combo, ci }: { combo: any; ci: number }) => (
                  <Box key={ci} sx={{
                    p: 1.5,
                    bgcolor: combo.flagged ? 'rgba(255,165,0,0.07)' : 'rgba(255,255,255,0.03)',
                    border: `1px solid ${combo.flagged ? 'rgba(255,165,0,0.35)' : 'rgba(255,255,255,0.07)'}`,
                    borderRadius: 1.5,
                    minWidth: 220,
                    flex: '0 1 auto',
                    position: 'relative',
                  }}>
                    {combo.flagged && (
                      <Box sx={{ position: 'absolute', top: 6, right: 8, fontSize: '0.62rem', color: '#FFA500', fontWeight: 700 }}>★ EDGE</Box>
                    )}
                    {combo.priority_score > 0 && (
                      <Box sx={{ position: 'absolute', top: combo.flagged ? 20 : 6, right: 8, fontSize: '0.62rem', color: '#64B5F6' }}>
                        {'⬆'.repeat(combo.priority_score)} priority
                      </Box>
                    )}
                    {combo.legs.map((leg: any, li: number) => (
                      <Box key={li} sx={{ mb: li < combo.legs.length - 1 ? 0.75 : 0 }}>
                        <Typography sx={{ fontSize: '0.76rem', color: '#ddd', fontWeight: 600, lineHeight: 1.2, pr: combo.flagged || combo.priority_score > 0 ? 4 : 0 }}>
                          {leg.bet}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 0.75, alignItems: 'center', flexWrap: 'wrap' }}>
                          <Typography sx={{ fontSize: '0.68rem', color: '#FFA500', fontFamily: 'monospace' }}>
                            → {leg.teased_line > 0 ? '+' : ''}{leg.teased_line}
                          </Typography>
                          {leg.is_road && <Box component="span" sx={{ fontSize: '0.62rem', color: '#64B5F6' }}>road</Box>}
                          {leg.low_total && <Box component="span" sx={{ fontSize: '0.62rem', color: '#81C784' }}>O/U {leg.game_total}</Box>}
                        </Box>
                      </Box>
                    ))}
                    <Box sx={{ mt: 1, pt: 0.75, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography sx={{ fontSize: '0.65rem', color: '#888', fontFamily: 'monospace' }}>
                          {combo.n_teams}T {combo.book_odds}
                        </Typography>
                        <Typography sx={{ fontSize: '0.7rem', color: '#4CAF50', fontWeight: 700 }}>
                          +{combo.ev_blended_pct ?? combo.ev_pct}% blended
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex' }}>
                        <Typography sx={{ fontSize: '0.62rem', color: '#666' }}>
                          Lim {(combo.min_pin_limit / 1000).toFixed(0)}k+
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
                        {(['top8', 'grouped'] as const).map(v => (
                          <Button key={v} size="small" onClick={() => setWongComboView(v)} sx={{
                            fontSize: '0.7rem', textTransform: 'none', borderRadius: 1.5, px: 1.5, py: 0.3,
                            color: wongComboView === v ? '#FFA500' : '#555',
                            border: `1px solid ${wongComboView === v ? 'rgba(255,165,0,0.4)' : 'rgba(255,255,255,0.07)'}`,
                            bgcolor: wongComboView === v ? 'rgba(255,165,0,0.07)' : 'transparent',
                            '&:hover': { borderColor: 'rgba(255,165,0,0.3)', color: '#FFA500' },
                          }}>
                            {v === 'top8' ? 'Top 8 Overall' : 'By Size'}
                          </Button>
                        ))}
                      </Box>
                    </Box>

                    {combosExpanded && wongComboView === 'top8' && (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                        {top8.map((combo, ci) => <ComboCard key={ci} combo={combo} ci={ci} />)}
                      </Box>
                    )}

                    {combosExpanded && wongComboView === 'grouped' && Object.entries(bySize).sort(([a], [b]) => Number(a) - Number(b)).map(([n, grpCombos]) => (
                      <Box key={n} sx={{ mb: 2 }}>
                        <Typography sx={{ fontSize: '0.76rem', color: '#888', fontWeight: 600, mb: 1 }}>
                          {n}-Team {wongTeaserType} &nbsp;
                          <span style={{ color: '#FFA500', fontFamily: 'monospace' }}>{grpCombos[0].book_odds}</span>
                          &nbsp;· Break-even <span style={{ color: '#999' }}>{grpCombos[0].break_even_pct}%/leg</span>
                        </Typography>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                          {grpCombos.slice(0, 6).map((combo: any, ci: number) => (
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
                <strong style={{ color: '#555' }}> Blended EV</strong> = per-combo: (hist + 0.01 if O/U ≤49) + (0.50 − NVP_implied) × 0.30, multiplied across legs.
                Hist EV = flat historical rate (reference). Pin limit ≥ 2,000. Road + O/U ≤49 prioritized. One line per game (main line only).
              </Typography>
            </Box>
          </Collapse>
        </Box>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          PARLAYS
      ══════════════════════════════════════════════════════════════════ */}
      {parlays && (
        <Box sx={{ mt: 1.5 }}>
          {/* Header row */}
          <Box
            onClick={() => setParlaysExpanded(v => !v)}
            sx={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              px: 2, py: 1.25,
              bgcolor: 'rgba(20,20,20,0.95)',
              border: '1px solid rgba(100,181,246,0.25)',
              borderRadius: parlaysExpanded ? '8px 8px 0 0' : '8px',
              cursor: 'pointer', userSelect: 'none',
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Typography sx={{ color: '#64B5F6', fontWeight: 600, fontSize: '0.9rem' }}>
                🎲 Parlays
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.75 }}>
                {([2, 3, 4] as const).map(n => {
                  const count = (parlays.parlays || []).filter((p: any) => p.n_legs === n).length;
                  return count > 0 ? (
                    <Box key={n} sx={{ px: 1, py: 0.25, bgcolor: 'rgba(100,181,246,0.12)', border: '1px solid rgba(100,181,246,0.25)', borderRadius: 1, fontSize: '0.72rem', color: '#64B5F6' }}>
                      {n}-leg ×{count}
                    </Box>
                  ) : null;
                })}
                {parlays.eligible_legs != null && (
                  <Box sx={{ px: 1, py: 0.25, fontSize: '0.72rem', color: '#555' }}>
                    {parlays.eligible_legs} eligible legs
                  </Box>
                )}
              </Box>
            </Box>
            {parlaysExpanded
              ? <ExpandLess sx={{ color: '#64B5F6', fontSize: '1.1rem' }} />
              : <ExpandMore sx={{ color: '#64B5F6', fontSize: '1.1rem' }} />}
          </Box>

          <Collapse in={parlaysExpanded}>
            <Box sx={{ border: '1px solid rgba(100,181,246,0.25)', borderTop: 'none', borderRadius: '0 0 8px 8px', bgcolor: 'rgba(20,20,20,0.95)', p: 2 }}>

              {(parlays.parlays || []).length === 0 ? (
                <Typography sx={{ color: '#555', fontSize: '0.82rem', fontStyle: 'italic' }}>
                  No qualifying parlays found (need pin_limit ≥ 1,000, leg EV ≥ −1%, odds ≤ +150).
                </Typography>
              ) : (
                <>
                  {/* Size filter tabs */}
                  <Box sx={{ display: 'flex', gap: 0.75, mb: 1.5, alignItems: 'center' }}>
                    {(['all', 2, 3, 4] as const).map(f => {
                      const label = f === 'all' ? 'All' : `${f}-leg`;
                      const count = f === 'all'
                        ? (parlays.parlays || []).length
                        : (parlays.parlays || []).filter((p: any) => p.n_legs === f).length;
                      const active = parlayLegFilter === f;
                      return count > 0 ? (
                        <Box
                          key={String(f)}
                          onClick={() => setParlayLegFilter(f)}
                          sx={{
                            px: 1.25, py: 0.3,
                            fontSize: '0.72rem', fontWeight: active ? 600 : 400,
                            color: active ? '#64B5F6' : '#666',
                            bgcolor: active ? 'rgba(100,181,246,0.12)' : 'transparent',
                            border: `1px solid ${active ? 'rgba(100,181,246,0.4)' : 'rgba(255,255,255,0.08)'}`,
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
                      {parlays.total_combos?.toLocaleString() ?? '?'} total combos · {parlays.eligible_legs} eligible legs
                    </Typography>
                  </Box>

                  {/* Parlay cards */}
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {(parlays.parlays || [])
                      .filter((p: any) => parlayLegFilter === 'all' || p.n_legs === parlayLegFilter)
                      .map((parlay: any, pi: number) => (
                      <Box key={pi} sx={{
                        p: 1.5,
                        bgcolor: parlay.ev_blended_pct >= 0 ? 'rgba(100,181,246,0.05)' : 'rgba(255,255,255,0.02)',
                        border: `1px solid ${parlay.same_sport ? 'rgba(100,181,246,0.3)' : 'rgba(255,255,255,0.07)'}`,
                        borderRadius: 1.5,
                        minWidth: 230,
                        maxWidth: 310,
                        flex: '0 1 auto',
                        position: 'relative',
                      }}>
                        {parlay.same_sport && (
                          <Box sx={{ position: 'absolute', top: 6, right: 8, fontSize: '0.6rem', color: '#64B5F6', fontWeight: 700, letterSpacing: '0.05em' }}>
                            ◆ SAME
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
                                <Box component="span" sx={{ fontSize: '0.6rem', color: '#64B5F6', px: 0.5, py: 0.1, bgcolor: 'rgba(100,181,246,0.08)', borderRadius: 0.5 }}>
                                  {leg.league}
                                </Box>
                              )}
                              <Box component="span" sx={{ fontSize: '0.62rem', color: leg.ev_pct >= 0 ? '#4CAF50' : '#aaa', fontFamily: 'monospace' }}>
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
                            <Typography sx={{ fontSize: '0.72rem', color: parlay.ev_blended_pct >= 0 ? '#4CAF50' : '#aaa', fontWeight: 700 }}>
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
                    Parlay EV = ∏(1 + leg_EV) − 1 · Parlay odds = product of BetBCK decimal odds · Top 5 per size shown.
                    Ranked highest EV to lowest · Pin limit ≥ 1,000 · Leg EV ≥ −1% · Odds ≤ +150 · Max 3 +money legs · One leg per game.
                  </Typography>
                </>
              )}
            </Box>
          </Collapse>
        </Box>
      )}
    </>
  );
};

export default BuckeyeScraper; 