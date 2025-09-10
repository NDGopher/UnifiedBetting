import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Paper,
  Typography,
  Box,
  Grid,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Alert,
  CircularProgress,
  IconButton,
  Tooltip,
  Badge,
  TableContainer,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
} from "@mui/material";
import {
  PlayArrow,
  Stop,
  Refresh,
  FilterList,
  SportsBasketball,
  SportsSoccer,
  SportsFootball,
  SportsBaseball,
  SportsHockey,
  Casino,
  Delete,
  Cancel,
} from "@mui/icons-material";
import { useWebSocket } from '../hooks/useWebSocket';

interface PTOProp {
  prop: {
    sport: string;
    teams: string[];
    propDesc: string;
    betType: string;
    odds: string;
    width: string;
    gameTime: string;
    fairValue: string;
    ev: string;
    timestamp: string;
    books: string[];
  };
  created_at: string;
  updated_at: string;
}

interface PTOData {
  props: PTOProp[];
  total_count: number;
  last_update: string;
}

interface ScraperStatus {
  is_running: boolean;
  total_props: number;
  last_refresh: number;
  refresh_interval: number;
}

const PropBuilder: React.FC = () => {
  const [ptoData, setPtoData] = useState<PTOData | null>(null);
  const [scraperStatus, setScraperStatus] = useState<ScraperStatus | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [minEvFilter, setMinEvFilter] = useState<number>(3.0);
  const [sportFilter, setSportFilter] = useState<string>("all");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [showOnlyPositiveEv, setShowOnlyPositiveEv] = useState(true);
  const [initialLoad, setInitialLoad] = useState(true);
  const [manualRefresh, setManualRefresh] = useState(false);
  const prevPropsRef = useRef<any[]>([]);
  const { lastMessage, isConnected } = useWebSocket('ws://localhost:5001/ws');
  const [hiddenProps, setHiddenProps] = useState<Set<string>>(new Set());
  const [showHidden, setShowHidden] = useState(false);

  const API_BASE = "http://localhost:5001";

  const getSportIcon = (sport: string, size: number = 24): React.ReactElement => {
    const sportLower = sport.toLowerCase();
    const iconProps = { sx: { fontSize: size, color: '#2E7D32' } };
    if (sportLower.includes("nba") || sportLower.includes("wnba"))
      return <SportsBasketball {...iconProps} />;
    if (sportLower.includes("mlb")) return <SportsBaseball {...iconProps} />;
    if (sportLower.includes("nfl")) return <SportsFootball {...iconProps} />;
    if (sportLower.includes("nhl")) return <SportsHockey {...iconProps} />;
    if (
      sportLower.includes("soccer") ||
      sportLower.includes("futbol") ||
      sportLower.includes("football")
    )
      return <SportsSoccer {...iconProps} />;
    return <Casino {...iconProps} />;
  };

  const fetchPTOData = useCallback(async (isManual = false) => {
    if (initialLoad || isManual) setLoading(true);
    setError(null);
    try {
      const endpoint = showOnlyPositiveEv
        ? `/pto/props/ev/${minEvFilter}`
        : "/pto/props";
      const response = await fetch(`${API_BASE}${endpoint}`);
      if (!response.ok) throw new Error("Failed to fetch PTO data");
      const data = await response.json();
      const safeProps = (data.data.props || []).filter((p: any, i: number) => {
        const valid = p && typeof p === 'object' && p.prop && p.prop.sport;
        if (!valid) {
          console.warn(`[PropBuilder] Skipping malformed prop at index ${i}:`, p);
        }
        return valid;
      });
      setPtoData({ ...data.data, props: safeProps });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      if (initialLoad) setInitialLoad(false);
      setLoading(false);
      setManualRefresh(false);
    }
  }, [initialLoad, showOnlyPositiveEv, minEvFilter]);

  const fetchScraperStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/pto/scraper/status`);
      if (response.ok) {
        const data = await response.json();
        setScraperStatus(data.data);
      }
    } catch (err) {
      console.error("Failed to fetch scraper status:", err);
    }
  }, []);

  const toggleScraper = async (start: boolean) => {
    try {
      const endpoint = start ? "/pto/scraper/start" : "/pto/scraper/stop";
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
      });
      if (response.ok) {
        await fetchScraperStatus();
        if (start) await fetchPTOData();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to toggle scraper");
    }
  };

  useEffect(() => {
    fetchPTOData();
    fetchScraperStatus();
    // eslint-disable-next-line
  }, [fetchPTOData, fetchScraperStatus]);

  useEffect(() => {
    if (autoRefresh && !isConnected) {
      // Only poll if WebSocket is not connected
      const interval = setInterval(() => {
        fetchPTOData();
        fetchScraperStatus();
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, fetchPTOData, fetchScraperStatus, isConnected]);

  useEffect(() => {
    fetchPTOData();
  }, [minEvFilter, showOnlyPositiveEv, fetchPTOData]);

  useEffect(() => {
    if (ptoData && ptoData.props && ptoData.props.length > 0) {
      ptoData.props.forEach((p, idx) => {
        const prev = prevPropsRef.current[idx];
        if (prev && prev.prop) {
          if (
            p.prop.ev !== prev.prop.ev ||
            p.prop.width !== prev.prop.width
          ) {
            console.log(
              `[PropBuilder] EV/Width changed for ${p.prop.propDesc} (${p.prop.teams?.join(' vs ') || ''}):`,
              `EV: ${prev.prop.ev} → ${p.prop.ev}, Width: ${prev.prop.width} → ${p.prop.width}`
            );
          }
        }
      });
      prevPropsRef.current = ptoData.props;
    }
  }, [ptoData]);

  // WebSocket: update PTO data on new message
  useEffect(() => {
    if (lastMessage && lastMessage.data) {
      try {
        const data = JSON.parse(lastMessage.data);
        if (data.type === 'pto_prop_update' && data.props) {
          // Replace the entire PTO prop list with the latest from backend
          setPtoData({
            props: data.props,
            total_count: data.total_count || 0,
            last_update: data.last_update || new Date().toISOString()
          });
        }
      } catch (e) {
        console.error('[PropBuilder] WebSocket message parse error:', e);
      }
    }
  }, [lastMessage]);

  const handleHideProp = (propId: string) => {
    setHiddenProps(prev => new Set(prev).add(propId));
  };

  const filteredProps = (ptoData?.props ?? []).filter((prop) => {
    const propId = prop.prop && prop.prop.propDesc ? prop.prop.propDesc + (prop.prop.teams?.join('-') || '') : '';
    if (!showHidden && hiddenProps.has(propId)) return false;
    if (
      sportFilter !== "all" &&
      !prop.prop.sport.toLowerCase().includes(sportFilter.toLowerCase())
    ) {
      return false;
    }
    return true;
  });

  const sports = (ptoData?.props ?? []).reduce((acc: string[], p) => {
    if (!acc.includes(p.prop.sport)) {
      acc.push(p.prop.sport);
    }
    return acc;
  }, []);

  // Manual refresh handler
  const handleManualRefresh = () => {
    setManualRefresh(true);
    fetchPTOData(true);
  };

  // Robust mapping for book names to icon filenames
  const bookIconMap: Record<string, string> = {
    '365': 'bet365.png',
    'bet365': 'bet365.png',
    'MGM': 'mgm.png',
    'mgm': 'mgm.png',
    'BV': 'bovada.png',
    'bovada': 'bovada.png',
    'ESPN': 'espnbet.png',
    'espn': 'espnbet.png',
    'HR': 'hardrock.png',
    'PIN': 'pinnacle.png',
    'DK': 'draftkings.png',
    'CS': 'caesars.png',
    'hardrock': 'hardrock.png',
    'BetRivers': 'betrivers.png',
    'betrivers': 'betrivers.png',
    'Caesars': 'caesars.png',
    'caesars': 'caesars.png',
    'Circa': 'circa.png',
    'circa': 'circa.png',
    'CA': 'circa.png',
    'DraftKings': 'draftkings.png',
    'draftkings': 'draftkings.png',
    'FanDuel': 'fanduel.png',
    'fanduel': 'fanduel.png',
    'FD': 'fanduel.png',
    'BR': 'betrivers.png',
    'Pinnacle': 'pinnacle.png',
    'pinnacle': 'pinnacle.png',
    'F': 'fliff.png',
    'NV': 'novig.png',
    'PX': 'prophetx.png',
    'BM': 'bookmaker.png',
  };

  const normalizeBook = (book: string) => {
    if (!book) return '';
    // Lowercase, remove spaces, dashes, special chars
    let b = book.toLowerCase().replace(/[^a-z0-9]/g, '');
    // Handle common variants
    if (b.includes('pinnacle')) return 'pinnacle';
    if (b.includes('fanduel')) return 'fanduel';
    if (b.includes('draftkings') || b === 'dk') return 'draftkings';
    if (b.includes('betrivers')) return 'betrivers';
    if (b.includes('bovada')) return 'bovada';
    if (b.includes('caesars')) return 'caesars';
    if (b.includes('circa')) return 'circa';
    if (b.includes('hardrock')) return 'hardrock';
    if (b.includes('mgm')) return 'mgm';
    // Add more as needed
    return b;
  };

  // Sort filteredProps by EV% descending
  const sortedProps = [...filteredProps].sort((a, b) => {
    const evA = parseFloat(a.prop.ev.replace('%', ''));
    const evB = parseFloat(b.prop.ev.replace('%', ''));
    return evB - evA;
  });

  return (
    <Paper
      sx={{ p: 2, height: "100%", display: "flex", flexDirection: "column" }}
    >
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 1,
        }}
      >
        <Box
          sx={{ display: "flex", gap: 1, alignItems: "center" }}
        >
          <Tooltip title={scraperStatus?.is_running ? "Stop Scraper" : "Start Scraper"}>
            <IconButton
              onClick={() => toggleScraper(!scraperStatus?.is_running)}
              color={scraperStatus?.is_running ? "error" : "success"}
              size="small"
            >
              {scraperStatus?.is_running ? <Stop /> : <PlayArrow />}
            </IconButton>
          </Tooltip>
          <Tooltip title="Refresh Data">
            <IconButton
              onClick={handleManualRefresh}
              disabled={loading}
              size="small"
            >
              <Refresh />
            </IconButton>
          </Tooltip>
          <Badge
            badgeContent={ptoData?.total_count || 0}
            color="primary"
          >
            <FilterList />
          </Badge>
          <FormControlLabel
            control={<Switch checked={showHidden} onChange={e => setShowHidden(e.target.checked)} size="small" />}
            label="Show Hidden"
            sx={{ ml: 2 }}
          />
          {/* Status dot and info, compact */}
          <Box sx={{ display: 'flex', alignItems: 'center', ml: 2, gap: 1, bgcolor: 'transparent' }}>
            <span
              style={{
                display: 'inline-block',
                width: 12,
                height: 12,
                borderRadius: '50%',
                backgroundColor: scraperStatus?.is_running ? '#43a047' : '#e53935',
                marginRight: 6,
              }}
            />
            <Typography variant="body2" sx={{ color: scraperStatus?.is_running ? '#43a047' : '#e53935', fontWeight: 600 }}>
              {scraperStatus?.is_running ? 'Running' : 'Stopped'}
            </Typography>
          </Box>
        </Box>
      </Box>

      {/* Error Display */}
      {error && (
        <Alert
          severity="error"
          sx={{ mb: 1, py: 0.5 }}
          onClose={() => setError(null)}
        >
          {error}
        </Alert>
      )}

      {/* Loading State */}
      {loading && (initialLoad || manualRefresh) && (
        <Box
          sx={{ display: "flex", justifyContent: "center", p: 1 }}
        >
          <CircularProgress size={20} />
        </Box>
      )}

      {/* Props Display */}
      <Box
        sx={{
          flexGrow: 1,
          mt: 0,
          mb: 0,
          overflow: "hidden",
        }}
      >
        {filteredProps.length > 0 ? (
          <Grid container spacing={2}>
            {sortedProps.map((propObj, idx) => {
              const prop = propObj.prop;
              const propId = prop.propDesc + (prop.teams?.join('-') || '');
              // Debug: log the full prop object and books field
              console.log('Full prop object:', propObj);
              console.log('prop.books:', (prop as any).books);
              return (
                <Grid item xs={12} md={6} lg={4} key={propId}>
                  <Paper sx={{ 
                    p: 3, 
                    borderRadius: 2, 
                    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
                    mb: 2, 
                    background: 'rgba(26, 26, 26, 0.8)',
                    backdropFilter: 'blur(20px)',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    position: 'relative', 
                    minHeight: 240,
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    '&:hover': {
                      boxShadow: '0 8px 32px rgba(46, 125, 50, 0.15)',
                      transform: 'translateY(-2px)',
                    }
                  }}>
                    {/* Delete icon absolute top right */}
                    <IconButton 
                      size="small" 
                      sx={{ 
                        position: 'absolute', 
                        top: 12, 
                        right: 12, 
                        zIndex: 2,
                        color: '#9E9E9E',
                        '&:hover': {
                          color: '#F44336',
                          backgroundColor: 'rgba(244, 67, 54, 0.1)'
                        }
                      }} 
                      onClick={() => handleHideProp(propId)}
                    >
                      <Delete fontSize="small" />
                    </IconButton>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '100%' }}>
                      {/* Left: Main Info */}
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 600, fontSize: '1em', mb: 0.2, pr: 2, wordBreak: 'break-word' }}>{prop.teams?.join(' vs ')}</Typography>
                        <Typography variant="body2" sx={{ color: 'gray', mb: 0.5 }}>{prop.gameTime}</Typography>
                        <Box sx={{ mb: 1 }}>
                          <Typography variant="body2" sx={{ fontWeight: 500 }}>{prop.propDesc}</Typography>
                          {prop.betType && (
                            <Typography variant="body2" sx={{ color: 'gray', fontStyle: 'italic', fontWeight: 400, mb: 0.5 }}>{prop.betType}</Typography>
                          )}
                          <Typography variant="body2" sx={{ color: 'lightgreen', fontWeight: 700 }}>{prop.odds}</Typography>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            {prop.fairValue && (
                              <Typography variant="body2" sx={{ color: 'gray', fontSize: '0.9em' }}>({prop.fairValue})</Typography>
                            )}
                          </Box>
                        </Box>
                        <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography variant="body2" sx={{ mr: 0.5 }}>Width:</Typography>
                          <Typography variant="body2" sx={{ fontWeight: 700 }}>{prop.width}</Typography>
                          {/* Book icons */}
                          <Box sx={{ display: 'flex', alignItems: 'center', ml: 1 }}>
                            {prop.books && prop.books.length > 0 ? (
                              prop.books.map((book: string, idx: number) => {
                                const iconFile = bookIconMap[book] || bookIconMap[book.toLowerCase()];
                                if (!iconFile) {
                                  console.warn('Unknown book name:', book);
                                }
                                return iconFile ? (
                                  <img
                                    key={idx}
                                    src={`/book_icons/${iconFile}`}
                                    alt={book}
                                    style={{ width: 24, height: 24, marginRight: 4, verticalAlign: 'middle' }}
                                  />
                                ) : (
                                  <span key={idx} style={{ color: 'red', fontSize: 24, marginRight: 4 }}>✗</span>
                                );
                              })
                            ) : null}
                          </Box>
                        </Box>
                      </Box>
                      {/* Right: EV% */}
                      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 60, ml: 2, flexShrink: 0, justifyContent: 'center', height: '100%' }}>
                        <Typography variant="caption" sx={{ color: 'gray', mb: 0.2, fontWeight: 500, textAlign: 'center', width: '100%' }}>EV</Typography>
                        <Box sx={{
                          bgcolor: 'rgba(46, 125, 50, 0.1)',
                          border: '2px solid #2E7D32',
                          borderRadius: 1.5,
                          px: 2,
                          py: 0.5,
                          minWidth: 50,
                          display: 'flex',
                          justifyContent: 'center',
                          alignItems: 'center',
                          mb: 0.5,
                        }}>
                          <Typography variant="h6" sx={{ 
                            color: '#2E7D32', 
                            fontWeight: 700, 
                            fontSize: '1.1em', 
                            lineHeight: 1, 
                            textAlign: 'center', 
                            width: '100%' 
                          }}>
                            {prop.ev}
                          </Typography>
                        </Box>
                        {/* Room for future buttons */}
                      </Box>
                    </Box>
                    {/* Sport icon in bottom right corner */}
                    <Box sx={{ position: 'absolute', bottom: 10, right: 10, zIndex: 1 }}>
                      {getSportIcon(prop.sport, 22)}
                    </Box>
                  </Paper>
                </Grid>
              );
            })}
          </Grid>
        ) : (
          <Typography variant="body2" sx={{ color: 'gray', textAlign: 'center', mt: 2 }}>
            No props found.
          </Typography>
        )}
      </Box>
    </Paper>
  );
};

export default PropBuilder;
