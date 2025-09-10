import React, { useState, useEffect, useRef } from 'react';
import { Box, Button, Typography, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, CircularProgress, Alert } from '@mui/material';
import MatchingStats from './MatchingStats';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import { Analytics } from '@mui/icons-material';
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

const API_BASE = 'http://localhost:5001';

const BuckeyeScraper: React.FC = () => {
  const [events, setEvents] = useState<BuckeyeEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [topMarkets, setTopMarkets] = useState<any[]>([]);
  const [stats, setStats] = useState({ pinnacleEvents: 0, betbckMatches: 0, matchRate: 0 });
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'ev' | 'start_time' | 'pinnacle_limit'>('ev');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [pipelineRunning, setPipelineRunning] = useState(false);

  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const isPolling = useRef(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Connect WebSocket on component mount
  useEffect(() => {
    connectWebSocket();
    
    return () => {
      disconnectWebSocket();
      stopPolling();
    };
  }, []);

  const checkPipelineStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/pipeline-status`);
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
          fetchEvents(); // Fetch results when pipeline is done
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
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    
    const ws = new WebSocket('ws://localhost:5001/ws');
    wsRef.current = ws;
    
    ws.onopen = () => {
      console.log('[BuckeyeScraper] WebSocket connected');
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('[BuckeyeScraper] WebSocket message:', data);
        
        if (data.type === 'buckeye_update') {
          // Real-time update from streaming pipeline
          const { events, total_events, last_run, streaming, batch_completed, total_batches } = data.data;
          
          if (events && events.length > 0) {
            // Sort by EV (high to low) before setting
            const sortedEvents = [...events].sort((a: any, b: any) => {
              const evA = parseFloat(a.ev?.replace('%', '') || '0');
              const evB = parseFloat(b.ev?.replace('%', '') || '0');
              return evB - evA;
            });
            
            setTopMarkets(sortedEvents);
            setLastUpdate(last_run);
            setMessage(`Streaming: ${batch_completed}/${total_batches} batches completed (${total_events} events)`);
            console.log(`[BuckeyeScraper] Real-time update: ${events.length} events added to table (sorted by EV)`);
          }
        } else if (data.type === 'buckeye_complete') {
          // Pipeline completed
          const { events, total_events, last_run, total_processed, total_matched } = data.data;
          
          if (events && events.length > 0) {
            // Sort by EV (high to low) before setting
            const sortedEvents = [...events].sort((a: any, b: any) => {
              const evA = parseFloat(a.ev?.replace('%', '') || '0');
              const evB = parseFloat(b.ev?.replace('%', '') || '0');
              return evB - evA;
            });
            
            setTopMarkets(sortedEvents);
            setLastUpdate(last_run);
            setMessage(`Pipeline completed: ${total_matched} games matched, ${total_events} events found`);
            console.log(`[BuckeyeScraper] Pipeline completed: ${total_events} events total (sorted by EV)`);
          }
          
          setPipelineRunning(false);
          stopPolling();
        }
      } catch (err) {
        console.error('[BuckeyeScraper] Error parsing WebSocket message:', err);
      }
    };
    
    ws.onclose = () => {
      console.log('[BuckeyeScraper] WebSocket disconnected');
    };
    
    ws.onerror = (error) => {
      console.error('[BuckeyeScraper] WebSocket error:', error);
    };
  };

  const disconnectWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close();
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
        setLastUpdate(data.data.last_update || null);
        const allMarkets = data.data.markets || [];
        allMarkets.sort((a: any, b: any) => parseFloat(b.ev) - parseFloat(a.ev));
        // Show up to 150 markets (sorted by EV desc initially)
        const displayLimit = 150;
        setTopMarkets(allMarkets.length > 0 ? allMarkets.slice(0, displayLimit) : []);
      } else {
        setError(data.message || 'Failed to fetch results');
        setTopMarkets([]);
      }
    } catch (err) {
      console.error('[BuckeyeScraper] Error fetching results:', err);
      setError('Failed to fetch results');
      setTopMarkets([]);
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
    setLoading(true);
    setError(null);
    setMessage(null);
    setTopMarkets([]); // Clear any old data immediately
    setLastUpdate(null); // Clear last update timestamp
    try {
      console.log('[BuckeyeScraper] Starting streaming Buckeye pipeline...');
      const res = await fetch(`${API_BASE}/api/run-streaming-pipeline`, { method: 'POST' });
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
        setError(data.message || 'Failed to start streaming pipeline');
        setTopMarkets([]);
      }
    } catch (err) {
      console.error('[BuckeyeScraper] Error starting streaming pipeline:', err);
      setError('Failed to start streaming pipeline');
      setTopMarkets([]);
    } finally {
      setLoading(false);
    }
  };

  const handleRunAceCalculations = async () => {
    setLoading(true);
    setError(null);
    setMessage(null);
    setTopMarkets([]); // Clear any old data immediately
    setLastUpdate(null); // Clear last update timestamp
    // Don't start polling immediately - wait until calculations are actually running
    try {
      console.log('[BuckeyeScraper] Running Ace calculations...');
      const res = await fetch(`${API_BASE}/ace/run-calculations`, { method: 'POST' });
      const data = await res.json();
      console.log('[BuckeyeScraper] Ace calculations response:', data);
      
      // Handle the new response format with status field
      if (data.status === 'success') {
        setMessage(data.message || 'Ace calculations completed successfully');
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
        setTopMarkets([]);
        stopPolling(); // Stop polling on error
      } else {
        // Handle old format for backward compatibility
        if (data.message) {
          setMessage(data.message);
          // Don't fetch results immediately - let polling handle it
          // fetchAceEvents();
        } else {
          setError('Failed to run Ace calculations - unexpected response format');
          setTopMarkets([]);
          stopPolling();
        }
      }
    } catch (err) {
      console.error('[BuckeyeScraper] Error running Ace calculations:', err);
      setError('Failed to run Ace calculations - network error');
      setTopMarkets([]);
      stopPolling(); // Stop polling on error
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
      if (data.status === 'success') {
        setLastUpdate(data.last_update || null);
        const allMarkets = data.markets || [];
        allMarkets.sort((a: any, b: any) => parseFloat(b.ev) - parseFloat(a.ev));
        // Show up to 150 markets (sorted by EV desc initially)
        const displayLimit = 150;
        setTopMarkets(allMarkets.length > 0 ? allMarkets.slice(0, displayLimit) : []);
        stopPolling(); // Stop polling when results are loaded
      } else if (data.status === 'partial_success') {
        setLastUpdate(data.last_update || null);
        const allMarkets = data.markets || [];
        allMarkets.sort((a: any, b: any) => parseFloat(b.ev) - parseFloat(a.ev));
        // Show up to 150 markets
        const displayLimit = 150;
        setTopMarkets(allMarkets.length > 0 ? allMarkets.slice(0, displayLimit) : []);
        setMessage(data.message || 'Partial results loaded');
        stopPolling(); // Stop polling when results are loaded
      } else if (data.status === 'error') {
        setError(data.message || data.error || 'Failed to fetch Ace results');
        setTopMarkets([]);
        stopPolling(); // Stop polling on error
      } else {
        // Handle old format for backward compatibility
        if (data.data && data.data.markets) {
          setLastUpdate(data.data.last_update || null);
          const allMarkets = data.data.markets || [];
          allMarkets.sort((a: any, b: any) => parseFloat(b.ev) - parseFloat(a.ev));
          // Show up to 150 markets
          const displayLimit = 150;
          setTopMarkets(allMarkets.length > 0 ? allMarkets.slice(0, displayLimit) : []);
          stopPolling(); // Stop polling when results are loaded
        } else {
          setError('Failed to fetch Ace results - unexpected response format');
          setTopMarkets([]);
          stopPolling(); // Stop polling on error
        }
      }
    } catch (err) {
      console.error('[BuckeyeScraper] Error fetching Ace results:', err);
      setError('Failed to fetch Ace results - network error');
      setTopMarkets([]);
      stopPolling(); // Stop polling on error
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Box sx={{ display: 'flex', gap: 2, mb: 3, justifyContent: 'flex-start', flexWrap: 'wrap' }}>
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
        </Button>
        <Button
          variant="outlined"
          size="small"
          disabled={pipelineRunning}
          sx={{
            color: pipelineRunning ? '#2E7D32' : '#B0B0B0',
            borderColor: pipelineRunning ? '#2E7D32' : 'rgba(255, 255, 255, 0.2)',
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
              bgcolor: pipelineRunning ? 'rgba(46, 125, 50, 0.1)' : 'rgba(255, 255, 255, 0.05)',
              borderColor: pipelineRunning ? '#2E7D32' : 'rgba(255, 255, 255, 0.3)',
            },
          }}
          onClick={handleRunCalculations}
        >
          {pipelineRunning ? 'Running...' : 'Buckeye'}
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
      </Box>
      {lastUpdate && (
        <Typography variant="body2" sx={{ color: '#aaa', mb: 1, ml: 1 }}>
          Last Updated: {dayjs(lastUpdate).format('YYYY-MM-DD HH:mm:ss')} ({dayjs(lastUpdate).fromNow()})
        </Typography>
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
                  setTopMarkets(prev => {
                    const sorted = [...prev].sort((a: any, b: any) => (parseFloat(a.ev) - parseFloat(b.ev)) * (sortBy === 'ev' && sortDir === 'asc' ? 1 : -1));
                    return sorted;
                  });
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
                  setTopMarkets(prev => {
                    const sorted = [...prev].sort((a: any, b: any) => {
                      const da = parseStartTime(a.start_time);
                      const db = parseStartTime(b.start_time);
                      const va = da ? da.valueOf() : 0;
                      const vb = db ? db.valueOf() : 0;
                      return (va - vb) * (sortBy === 'start_time' && sortDir === 'asc' ? 1 : -1);
                    });
                    return sorted;
                  });
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
                  setTopMarkets(prev => {
                    const sorted = [...prev].sort((a: any, b: any) => {
                      const va = a.pinnacle_limit ?? -1;
                      const vb = b.pinnacle_limit ?? -1;
                      return (va - vb) * (sortBy === 'pinnacle_limit' && sortDir === 'asc' ? 1 : -1);
                    });
                    return sorted;
                  });
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
            {topMarkets.length === 0 && !loading && !error ? (
              <TableRow>
                <TableCell colSpan={8} align="center" sx={{ 
                  color: '#9E9E9E', 
                  fontStyle: 'italic',
                  py: 4,
                  fontSize: '0.875rem'
                }}>
                  No valid markets found. Click RUN CALCULATIONS to populate or check backend filters.
                </TableCell>
              </TableRow>
            ) : (
              topMarkets.map((row, idx) => (
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
    </>
  );
};

export default BuckeyeScraper; 