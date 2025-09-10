import React, { useEffect, useState, useCallback, useRef, useContext } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Typography,
  Box,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Alert,
  Grid,
} from "@mui/material";
import { 
  Refresh as RefreshIcon,
  Star as StarIcon,
  TrendingUp,
  Close,
  CheckCircle,
  Warning
} from "@mui/icons-material";
import { BetbckTabContext } from "../App";
import { useWebSocket } from '../hooks/useWebSocket';
import { showEnhancedNotification } from '../utils/notificationUtils';
import './PODAlerts.css';

interface Market {
  market: string;
  selection: string;
  line: string;
  pinnacle_nvp: string;
  betbck_odds: string;
  ev: string;
}

interface EventData {
  title: string;
  meta_info: string;
  last_update: number;
  alert_description: string;
  alert_meta: string;
  markets: Market[];
  alert_arrival_timestamp: number;
  start_time?: string;
  old_odds?: string;
  new_odds?: string;
  betbck_payload?: any;
}

const POLL_INTERVAL = 2000; // 2 seconds for fast POD alert updates
const NEGATIVE_EV_DISMISS_MS = 60 * 1000; // 1 minute for negative EV alerts
const POSITIVE_EV_DISMISS_MS = 3 * 60 * 1000; // 3 minutes for positive EV alerts
const MAX_RETRIES = 3; // Maximum number of retries before showing error

const PODAlerts: React.FC = () => {
  const [events, setEvents] = useState<{ [eventId: string]: EventData }>({});
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [modalMarket, setModalMarket] = useState<null | { event: EventData; market: Market }>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [retryCount, setRetryCount] = useState(0);
  const [showOnlyEV, setShowOnlyEV] = useState(false);
  const prevMarketsRef = useRef<{ [eventId: string]: Market[] }>({});
  const notifiedEventsRef = useRef<Set<string>>(new Set());
  const { lastMessage, isConnected } = useWebSocket('ws://localhost:5001/ws');
  const [nvpFlash, setNvpFlash] = useState<{ [key: string]: boolean }>({});

  // Helper to safely convert any value to string
  const safeString = (val: any) => (val === null || val === undefined ? '' : String(val));

  // Helper to get markets from event
  const getMarkets = (event: any) => Array.isArray(event.markets) ? event.markets : [];

  // WebSocket real-time updates
  useEffect(() => {
    if (lastMessage && lastMessage.data) {
      try {
        const data = JSON.parse(lastMessage.data);
        console.log('[PODAlerts] WebSocket message received:', data.type, data);
        
        if (data.type === 'pod_alerts_full' && data.events) {
          // Replace the entire event list with the latest from backend
          console.log('[PODAlerts] Received pod_alerts_full with', Object.keys(data.events).length, 'events');
          setEvents(data.events);
          setLastUpdate(new Date());
        } else if (data.type === 'pod_alert' && (data.eventId || data.eventid) && data.event) {
          // Fallback: update the specific event
          const eventId = data.eventId || data.eventid;
          console.log('[PODAlerts] Received pod_alert update for eventId:', eventId);
          console.log('[PODAlerts] Event data:', data.event);
          console.log('[PODAlerts] Current markets in event:', data.event.markets);
          
          setEvents(prev => {
            const newEvents = { ...prev, [eventId]: data.event };
            console.log('[PODAlerts] Updated events state:', Object.keys(newEvents));
            return newEvents;
          });
          setLastUpdate(new Date());
          
          // NVP flash effect logic remains unchanged
          const event = data.event;
          if (event.markets && Array.isArray(event.markets)) {
            event.markets.forEach((market: Market, idx: number) => {
              const key = `${eventId}_${market.market}_${market.selection}_${market.line}`;
              const prevMarkets = prevMarketsRef.current[eventId] || [];
              const prev = prevMarkets[idx];
              if (prev && prev.pinnacle_nvp !== market.pinnacle_nvp) {
                console.log('[PODAlerts] NVP change detected:', prev.pinnacle_nvp, '->', market.pinnacle_nvp);
                setNvpFlash(flash => ({ ...flash, [key]: true }));
                setTimeout(() => setNvpFlash(flash => ({ ...flash, [key]: false })), 1500);
              }
            });
          }
        } else if (data.type === 'pod_alert_removed' && (data.eventId || data.eventid)) {
          // Remove the expired alert from the UI
          const eventId = data.eventId || data.eventid;
          console.log(`Removing expired alert: ${eventId}`);
          setEvents(prev => {
            const newEvents = { ...prev };
            delete newEvents[eventId];
            return newEvents;
          });
          setLastUpdate(new Date());
        }
      } catch (e) {
        console.error('Error parsing WebSocket message:', e);
      }
    }
  }, [lastMessage]);

  // Polling fallback: only poll if not connected to WebSocket
  const fetchEvents = useCallback(async () => {
    try {
      setError(null);
      const res = await fetch('http://localhost:5001/get_active_events_data');
      if (res.ok) {
        const data = await res.json() as { [eventId: string]: EventData };
        setEvents(data);
        setLastUpdate(new Date());
        setRetryCount(0);
        setLoading(false);
      } else {
        const errorText = await res.text();
        throw new Error(`Failed to fetch events data: ${errorText}`);
      }
    } catch (e) {
      const newRetryCount = retryCount + 1;
      setRetryCount(newRetryCount);
      if (newRetryCount >= MAX_RETRIES) {
        setError(`Error fetching events data: ${e instanceof Error ? e.message : 'Unknown error'}`);
        setLoading(false);
      }
    }
  }, [retryCount]);

  useEffect(() => {
    if (isConnected) return; // Don't poll if WebSocket is connected
    fetchEvents();
    const poller = setInterval(fetchEvents, POLL_INTERVAL);
    return () => clearInterval(poller);
  }, [fetchEvents, isConnected]);

  // NVP flash effect
  useEffect(() => {
    Object.entries(events).forEach(([eventId, event]) => {
      getMarkets(event).forEach((market: Market, idx: number) => {
        const key = `${eventId}_${market.market}_${market.selection}_${market.line}`;
        const prev = prevMarketsRef.current[eventId]?.[idx];
        if (prev && prev.pinnacle_nvp !== market.pinnacle_nvp) {
          setNvpFlash(flash => ({ ...flash, [key]: true }));
          setTimeout(() => setNvpFlash(flash => ({ ...flash, [key]: false })), 1500);
        }
      });
    });
    prevMarketsRef.current = Object.fromEntries(
      Object.entries(events).map(([eventId, event]) => [eventId, getMarkets(event)])
    );
  }, [events]);

  const handleManualRefresh = useCallback(() => {
    setRetryCount(0);
    setLoading(true);
    fetchEvents();
  }, [fetchEvents]);

  const testConnection = useCallback(async () => {
    try {
      const res = await fetch('http://localhost:5001/test');
      const data = await res.json();
      alert(`Backend connection test: ${data.message}`);
    } catch (e) {
      alert(`Backend connection failed: ${e instanceof Error ? e.message : 'Unknown error'}`);
    }
  }, []);

  // Auto-dismiss timer - runs every 30 seconds to check for expired alerts
  useEffect(() => {
    const checkExpiredAlerts = () => {
    const now = Date.now();
    Object.entries(events).forEach(([eventId, event]) => {
      if (dismissed.has(eventId)) return;
      const msSinceAlert = now - (event.alert_arrival_timestamp * 1000);
        const hasPositiveEV = getBestEV(event.markets) > 0;
        const dismissTime = hasPositiveEV ? POSITIVE_EV_DISMISS_MS : NEGATIVE_EV_DISMISS_MS;
        
        if (msSinceAlert > dismissTime) {
          console.log(`[PODAlerts] Auto-dismissing ${hasPositiveEV ? 'positive' : 'negative'} EV alert: ${eventId} (${msSinceAlert}ms old, limit: ${dismissTime}ms)`);
        setDismissed(prev => new Set(prev).add(eventId));
      }
    });
    };

    // Run immediately
    checkExpiredAlerts();
    
    // Then run every 30 seconds
    const interval = setInterval(checkExpiredAlerts, 30000);
    
    return () => clearInterval(interval);
  }, [events, dismissed]);

  const handleDismiss = useCallback((eventId: string) => {
    setDismissed(prev => new Set(prev).add(eventId));
  }, []);

  const handleEVClick = (event: EventData, market: Market) => {
    setModalMarket({ event, market });
  };
  const closeModal = () => setModalMarket(null);

  const sortMarkets = (markets: Market[]) => {
    return [...markets].sort((a, b) => {
      const evA = parseFloat(a.ev);
      const evB = parseFloat(b.ev);
      return evB - evA;
    });
  };

  const getBestEV = (markets: Market[]) => {
    if (!markets || markets.length === 0) return -Infinity;
    return Math.max(...markets.map(m => parseFloat(m.ev)));
  };

  const activeEvents = Object.entries(events)
    .filter(([eventId]) => !dismissed.has(eventId))
    .sort(([, a], [, b]) => getBestEV(b.markets) - getBestEV(a.markets));

  const formatStartTime = (isoString: string) => {
    if (!isoString) return '';
    // Always parse as UTC and convert to Central Time
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;
    // Format as M/D h:mm A Central Time
    return date.toLocaleString('en-US', {
      timeZone: 'America/Chicago',
      month: 'numeric',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  useEffect(() => {
    // Compare new markets to previous markets for NVP/EV changes
    Object.entries(events).forEach(([eventId, event]) => {
      const prevMarkets = prevMarketsRef.current[eventId] || [];
      
      // Check for new positive EV markets (first time seeing this event)
      if (prevMarkets.length === 0 && event.markets.length > 0) {
        const positiveEVMarkets = event.markets.filter(m => parseFloat(m.ev) > 0);
        if (positiveEVMarkets.length > 0) {
          console.log(
            `[PODAlerts] NEW POSITIVE EV MARKETS DISCOVERED for ${event.title}:`,
            `\n   Found ${positiveEVMarkets.length} positive EV markets:`,
            ...positiveEVMarkets.map(m => 
              `\n   - ${m.market} ${m.selection} ${m.line}: EV ${m.ev}%, NVP ${m.pinnacle_nvp}, BetBCK ${m.betbck_odds}`
            )
          );
        }
      }
      
      event.markets.forEach((market, idx) => {
        const prev = prevMarkets[idx];
        if (prev) {
          const currentEV = parseFloat(market.ev);
          const prevEV = parseFloat(prev.ev);
          
          // Only log changes for positive EV plays
          if (currentEV > 0 && (market.pinnacle_nvp !== prev.pinnacle_nvp || market.ev !== prev.ev)) {
            const evChange = currentEV - prevEV;
            const evChangeDirection = evChange > 0 ? '↗' : evChange < 0 ? '↘' : '→';
            
            console.log(
              `[PODAlerts] POSITIVE EV CHANGE for ${event.title}`,
              `\n   Market: ${market.market} ${market.selection} ${market.line}`,
              `\n   NVP: ${prev.pinnacle_nvp} → ${market.pinnacle_nvp}`,
              `\n   EV: ${prev.ev} → ${market.ev} ${evChangeDirection}`,
              `\n   EV Change: ${evChange > 0 ? '+' : ''}${evChange.toFixed(2)}%`,
              `\n   BetBCK Odds: ${market.betbck_odds}`
            );
            
            // Log significant EV improvements
            if (evChange > 1.0) {
              console.log(
                `[PODAlerts] SIGNIFICANT EV IMPROVEMENT! ${evChange.toFixed(2)}% increase for ${event.title} - ${market.market} ${market.selection}`
              );
            }
          }
        }
      });
      // --- Trigger enhanced notification if any market EV > 2.5% ---
      const hasHighEV = event.markets.some(m => parseFloat(m.ev) > 2.5);
      if (hasHighEV && !notifiedEventsRef.current.has(eventId)) {
        console.log(`[PODAlerts] HIGH EV ALERT! ${event.title} has a market with EV > 2.5%`);
        
        // Find the best market for notification
        const bestMarket = event.markets.reduce((best, current) => {
          const currentEV = parseFloat(current.ev);
          const bestEV = parseFloat(best.ev);
          return currentEV > bestEV ? current : best;
        });
        
        // Create enhanced notification data
        const notificationData = {
          sport: event.title.split(' - ')[0] || 'Unknown Sport',
          awayTeam: event.title.split(' - ')[1]?.split(' vs ')[0] || 'Unknown',
          homeTeam: event.title.split(' - ')[1]?.split(' vs ')[1] || 'Unknown',
          ev: parseFloat(bestMarket.ev),
          bet: bestMarket.selection,
          odds: bestMarket.betbck_odds,
          nvp: bestMarket.pinnacle_nvp,
          eventId: eventId
        };
        
        // Show enhanced notification
        showEnhancedNotification(notificationData);
        notifiedEventsRef.current.add(eventId);
      }
    });
    // Save current markets for next comparison
    prevMarketsRef.current = Object.fromEntries(
      Object.entries(events).map(([eventId, event]) => [eventId, event.markets])
    );
  }, [events]);

  const formatTotal = (line: string) => {
    if (typeof line === 'string' && line.endsWith('.0')) {
      return line.slice(0, -2);
    }
    return line;
  };

  // Debug: Log current events state
  useEffect(() => {
    console.log('[PODAlerts] Current events state:', Object.keys(events));
    Object.entries(events).forEach(([eventId, event]) => {
      console.log(`[PODAlerts] Event ${eventId}:`, {
        title: event.title,
        marketsCount: event.markets?.length || 0,
        lastUpdate: event.last_update,
        sampleMarket: event.markets?.[0]
      });
    });
  }, [events]);

  return (
    <Box>
      <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="body2" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CheckCircle sx={{ fontSize: 16 }} />
            Last update: {lastUpdate.toLocaleTimeString()}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
          <Button 
            startIcon={<RefreshIcon />} 
            onClick={handleManualRefresh} 
            disabled={loading} 
            variant="outlined" 
            size="small"
            sx={{ minWidth: 'auto' }}
          >
            Refresh
          </Button>
          <Button 
            onClick={testConnection} 
            variant="outlined" 
            size="small" 
            color="secondary"
            sx={{ minWidth: 'auto' }}
          >
            Test
          </Button>
          <Button 
            onClick={() => setShowOnlyEV(ev => !ev)} 
            variant={showOnlyEV ? "contained" : "outlined"} 
            size="small" 
            color="success"
            startIcon={<TrendingUp />}
            sx={{ minWidth: 'auto' }}
          >
            {showOnlyEV ? "All" : "+EV Only"}
          </Button>
        </Box>
      </Box>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {loading ? (
        <Box display="flex" justifyContent="center" alignItems="center" minHeight={200}>
          <CircularProgress />
        </Box>
      ) : Object.keys(events).length === 0 && !loading && !error && (
        <Typography variant="body2" sx={{ color: 'gray', textAlign: 'center', fontStyle: 'italic', mt: 2 }}>
          No active alerts at the moment
        </Typography>
      )}
      {activeEvents.length === 0 && Object.keys(events).length !== 0 ? null : (
        <Grid container spacing={2} wrap="wrap">
          {activeEvents
            .filter(([, event]) => !showOnlyEV || getBestEV(event.markets) > 0)
            .map(([eventId, event]) => {
              const bestEV = getBestEV(event.markets);
              return (
                <Grid item xs={12} sm={12} md={6} key={eventId} sx={{ maxWidth: 900, width: '100%' }}>
                  <Paper sx={{ 
                    p: 3, 
                    mb: 3, 
                    borderRadius: 2, 
                    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
                    border: '1px solid rgba(46, 125, 50, 0.2)',
                    background: 'rgba(26, 26, 26, 0.8)',
                    backdropFilter: 'blur(20px)',
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    '&:hover': {
                      boxShadow: '0 8px 32px rgba(46, 125, 50, 0.15)',
                      transform: 'translateY(-2px)',
                    }
                  }} className="event-container">
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={3}>
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography variant="subtitle1" sx={{ 
                          color: '#FFFFFF', 
                          fontWeight: 600, 
                          mb: 1,
                          lineHeight: 1.3
                        }}>
                          {event.title}
                        </Typography>
                        <Typography variant="body2" sx={{ 
                          color: '#B0B0B0', 
                          fontSize: '0.875rem',
                          mb: 1
                        }}>
                          {event.meta_info} {event.start_time && (<span> | {formatStartTime(event.start_time)}</span>)}
                        </Typography>
                        <Typography variant="caption" sx={{ 
                          color: '#9E9E9E',
                          fontSize: '0.75rem',
                          display: 'block'
                        }}>
                          Alert: {event.alert_description} {event.alert_meta}
                          {event.old_odds && event.new_odds && (() => {
                            const oldOdds = parseFloat(event.old_odds!);
                            const newOdds = parseFloat(event.new_odds!);
                            if (!isNaN(oldOdds) && !isNaN(newOdds)) {
                              const drop = oldOdds - newOdds;
                              const dropPct = (drop / Math.abs(oldOdds)) * 100;
                              return <span> | Drop: {drop > 0 ? '-' : ''}{Math.abs(drop).toFixed(2)} ({dropPct.toFixed(1)}%)</span>;
                            }
                            return null;
                          })()}
                        </Typography>
                      </Box>
                      <Button 
                        onClick={() => handleDismiss(eventId)} 
                        variant="outlined" 
                        color="secondary" 
                        size="small"
                        startIcon={<Close />}
                        sx={{ 
                          minWidth: 'auto',
                          px: 2,
                          py: 0.5
                        }}
                      >
                        Dismiss
                      </Button>
                    </Box>
                    <TableContainer sx={{ 
                      background: 'transparent', 
                      boxShadow: 'none', 
                      width: '100%', 
                      maxWidth: 900, 
                      overflowX: 'hidden',
                      borderRadius: 1
                    }}>
                      <Table size="small" aria-label="Odds Table" sx={{ width: '100%', tableLayout: 'auto' }}>
                        <TableHead>
                          <TableRow sx={{ 
                            '& .MuiTableCell-root': { 
                              borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                              py: 1.5
                            }
                          }}>
                            <TableCell sx={{ 
                              fontWeight: 600, 
                              textAlign: 'left', 
                              pl: 0, 
                              whiteSpace: 'normal',
                              color: '#B0B0B0',
                              fontSize: '0.875rem'
                            }}>
                              Selection
                            </TableCell>
                            <TableCell align="center" sx={{ 
                              fontWeight: 600,
                              color: '#B0B0B0',
                              fontSize: '0.875rem'
                            }}>
                              Line
                            </TableCell>
                            <TableCell align="center" sx={{ 
                              fontWeight: 600,
                              color: '#B0B0B0',
                              fontSize: '0.875rem'
                            }}>
                              Pinnacle NVP
                            </TableCell>
                            <TableCell align="center" sx={{ 
                              fontWeight: 600,
                              color: '#B0B0B0',
                              fontSize: '0.875rem'
                            }}>
                              BetBCK Odds
                            </TableCell>
                            <TableCell align="center" sx={{ 
                              fontWeight: 600,
                              color: '#B0B0B0',
                              fontSize: '0.875rem'
                            }}>
                              EV %
                            </TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {sortMarkets(event.markets).map((market, idx) => {
                            const ev = parseFloat(market.ev);
                            const isPositiveEV = ev > 0;
                            const isBestEV = ev === bestEV && isPositiveEV;
                            let homeTeam = '', awayTeam = '';
                            if (event.title && event.title.includes(' vs ')) {
                              [homeTeam, awayTeam] = event.title.split(' vs ');
                            }
                            let selectionDisplay = market.selection;
                            if (market.market.toLowerCase().includes('moneyline') || market.market.toLowerCase().includes('spread')) {
                              if (market.selection === 'Home') selectionDisplay = homeTeam;
                              else if (market.selection === 'Away') selectionDisplay = awayTeam;
                            }
                            let evDisplay = market.ev;
                            if (!evDisplay.startsWith('-') && !evDisplay.startsWith('0') && !evDisplay.startsWith('+')) {
                              evDisplay = '+' + evDisplay;
                            }
                            let lineDisplay = market.line;
                            if (lineDisplay === "0" || lineDisplay === "+0" || lineDisplay === "-0") {
                              lineDisplay = "PK";
                            } else if (market.market.toLowerCase() === 'moneyline' || market.market.toLowerCase().includes('moneyline')) {
                              lineDisplay = 'ML';
                            } else if (market.market.toLowerCase().includes('spread') && market.line && !market.line.startsWith('-') && !market.line.startsWith('+')) {
                              lineDisplay = `+${market.line}`;
                            }
                            return (
                              <TableRow
                                key={idx}
                                sx={{
                                  background: isBestEV ? 'rgba(46, 125, 50, 0.15)' : isPositiveEV ? 'rgba(46, 125, 50, 0.08)' : undefined,
                                  '&:hover': {
                                    background: isBestEV ? 'rgba(46, 125, 50, 0.2)' : isPositiveEV ? 'rgba(46, 125, 50, 0.12)' : 'rgba(255, 255, 255, 0.04)'
                                  },
                                  height: 36,
                                  '& .MuiTableCell-root': { 
                                    padding: '4px 12px', 
                                    fontSize: '0.875rem',
                                    borderBottom: '1px solid rgba(255, 255, 255, 0.06)'
                                  }
                                }}
                              >
                                <TableCell sx={{ textAlign: 'left', pl: 0, whiteSpace: 'normal' }}>{selectionDisplay}</TableCell>
                                <TableCell align="center">{market.market.toLowerCase() === 'total' ? formatTotal(lineDisplay) : lineDisplay}</TableCell>
                                <TableCell 
                                  align="center"
                                  className={nvpFlash[`${eventId}_${market.market}_${market.selection}_${market.line}`] ? 'nvp-flash' : ''}
                                >
                                  {market.pinnacle_nvp && !market.pinnacle_nvp.startsWith('-') && !market.pinnacle_nvp.startsWith('+') ? `+${market.pinnacle_nvp}` : market.pinnacle_nvp}
                                </TableCell>
                                <TableCell align="center">{market.betbck_odds}</TableCell>
                                <TableCell align="center">
                                  <Button
                                    variant="text"
                                    color={isPositiveEV ? 'success' : 'inherit'}
                                    onClick={() => handleEVClick(event, market)}
                                    sx={{
                                      fontWeight: isBestEV ? 700 : isPositiveEV ? 600 : 500,
                                      '&:hover': {
                                        background: isBestEV ? 'rgba(46, 125, 50, 0.15)' : isPositiveEV ? 'rgba(46, 125, 50, 0.08)' : 'rgba(255, 255, 255, 0.04)'
                                      },
                                      minWidth: 0,
                                      padding: '4px 8px',
                                      fontSize: '0.875rem',
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: 0.5,
                                      borderRadius: 1,
                                      color: isPositiveEV ? '#2E7D32' : '#B0B0B0',
                                      textTransform: 'none'
                                    }}
                                  >
                                    {isBestEV && <StarIcon fontSize="small" sx={{ color: '#FFD700', mr: 0.5 }} />}
                                    {evDisplay}
                                  </Button>
                                </TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  </Paper>
                </Grid>
              );
            })}
        </Grid>
      )}
      <Dialog open={!!modalMarket} onClose={closeModal} maxWidth="sm" fullWidth>
        <DialogTitle>Bet Details</DialogTitle>
        <DialogContent>
          {modalMarket && (
            <LiveEVModal event={modalMarket.event} market={modalMarket.market} />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeModal}>Close</Button>
          <Button
            variant="contained"
            color="success"
            onClick={async () => {
              console.log("🎯 PLACE BET button clicked!");
              console.log("Modal market data:", modalMarket);
              
              if (!modalMarket) {
                console.log("❌ No modal market data found");
                return;
              }
              
              const event = Object.values(events).find(e => e.title === modalMarket.event.title);
              console.log("Found event:", event);
              
              const payload = event?.betbck_payload;
              if (!payload) {
                console.log("❌ BetBCK payload not found for this event.");
                return;
              }
              
              console.log("✅ BetBCK payload found:", payload);
              
              // Gather bet info for extension
              const betInfo = {
                line: modalMarket.market.line,
                ev: modalMarket.market.ev,
                betbck_odds: modalMarket.market.betbck_odds,
                nvp: modalMarket.market.pinnacle_nvp,
                eventId: Object.keys(events).find(
                  k => events[k].title === modalMarket.event.title
                ),
                keyword_search: payload.keyword_search || ''
              };
              
              console.log("📤 Sending bet info to extension:", betInfo);
              
              // Send message to Chrome extension using window.postMessage (no extension ID needed)
              // The extension content script will listen for this message and relay it to the background script
              window.postMessage({
                type: 'FOCUS_BETBCK_TAB',
                keyword: betInfo.keyword_search,
                betInfo
              }, '*');
              
              console.log("✅ Message sent to extension via window.postMessage");
              console.log("🔍 Check the Chrome extension popup for bet details");
            }}
          >
            Place Bet
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

const LiveEVModal: React.FC<{ event: EventData; market: Market }> = ({ event, market }) => {
  const [liveMarket, setLiveMarket] = useState<Market>(market);
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch('http://localhost:5001/get_active_events_data');
        if (res.ok) {
          const data = await res.json();
          const updatedEvent = data[event.title];
          if (updatedEvent) {
            const updatedMarket = updatedEvent.markets.find((m: Market) => m.market === market.market && m.selection === market.selection && m.line === market.line);
            if (updatedMarket) setLiveMarket(updatedMarket);
          }
        }
      } catch {}
    }, 3000);
    return () => clearInterval(interval);
  }, [event, market]);

  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="subtitle1" gutterBottom>{event.title}</Typography>
      <Typography variant="body2" gutterBottom>Market: {liveMarket.market}</Typography>
      <Typography variant="body2" gutterBottom>Selection: {liveMarket.selection}</Typography>
      <Typography variant="body2" gutterBottom>Line: {liveMarket.line}</Typography>
      <Typography variant="body2" gutterBottom>Pinnacle NVP: {liveMarket.pinnacle_nvp}</Typography>
      <Typography variant="body2" gutterBottom>BetBCK Odds: {liveMarket.betbck_odds}</Typography>
      <Typography variant="body2" color={parseFloat(liveMarket.ev) > 0 ? 'success.main' : 'text.primary'} sx={{ fontWeight: 'bold' }}>
        EV: {liveMarket.ev}
      </Typography>
    </Box>
  );
};

export default PODAlerts;
