import React, { createContext, useRef, useState } from "react";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { AppBar, Toolbar, Slider, Switch, TextField, Divider, InputAdornment, Select, MenuItem, FormControl, InputLabel, Chip } from "@mui/material";
import { 
  Analytics, 
  Calculate, 
  NotificationsActive,
  // Build,  // PropBuilder icon — disabled for now
  SportsEsports,
  AutoMode
} from "@mui/icons-material";
import PODAlerts from "./components/PODAlerts";
import EVCalculator from "./components/EVCalculator";
// import PropBuilder from "./components/PropBuilder"; // Props disabled for now
import BuckeyeScraper from './components/BuckeyeScraper';
import BetBCKStatusPopup from './components/BetBCKStatusPopup';
import AlertLog from './components/AlertLog';
// import HighEVHistory from './components/HighEVHistory'; // Removed - replaced with Auto Bet Placement

// Premium minimalist theme inspired by Swiss design principles
const modernTheme = createTheme({
  palette: {
    mode: "dark",
    primary: {
      main: "#2E7D32", // Refined forest green
      light: "#4CAF50",
      dark: "#1B5E20",
    },
    secondary: {
      main: "#9E9E9E", // Sophisticated gray
      light: "#BDBDBD",
      dark: "#616161",
    },
    background: {
      default: "#0A0A0A", // Deep charcoal
      paper: "#1A1A1A", // Refined dark gray
    },
    text: {
      primary: "#FFFFFF",
      secondary: "#B0B0B0",
    },
    error: {
      main: "#F44336",
    },
    success: {
      main: "#2E7D32",
    },
    warning: {
      main: "#FF9800",
    },
    info: {
      main: "#2196F3",
    },
  },
  typography: {
    fontFamily: '"SF Pro Display", "Inter", "Helvetica Neue", "Arial", sans-serif',
    h4: {
      fontWeight: 600,
      letterSpacing: "-0.025em",
      fontSize: "1.75rem",
    },
    h6: {
      fontWeight: 500,
      letterSpacing: "-0.015em",
      fontSize: "1.125rem",
    },
    subtitle1: {
      fontWeight: 500,
      fontSize: "1rem",
      letterSpacing: "0.01em",
    },
    body1: {
      fontSize: "0.875rem",
      lineHeight: 1.5,
    },
    body2: {
      fontSize: "0.8125rem",
      lineHeight: 1.4,
    },
  },
  spacing: 8,
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: "#1A1A1A",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          borderRadius: "12px",
          boxShadow: "0 2px 16px rgba(0, 0, 0, 0.4)",
          backdropFilter: "blur(20px)",
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          background: "rgba(10, 10, 10, 0.95)",
          backdropFilter: "blur(20px)",
          borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
          boxShadow: "0 1px 8px rgba(0, 0, 0, 0.3)",
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          fontWeight: 500,
          borderRadius: 8,
          textTransform: "none",
          letterSpacing: "0.02em",
          padding: "8px 16px",
        },
        containedPrimary: {
          backgroundColor: "#2E7D32",
          color: "#FFFFFF",
          boxShadow: "0 2px 8px rgba(46, 125, 50, 0.3)",
          '&:hover': {
            backgroundColor: "#1B5E20",
            boxShadow: "0 4px 12px rgba(46, 125, 50, 0.4)",
          },
        },
        outlined: {
          borderColor: "rgba(255, 255, 255, 0.2)",
          color: "#B0B0B0",
          '&:hover': {
            borderColor: "rgba(255, 255, 255, 0.3)",
            backgroundColor: "rgba(255, 255, 255, 0.05)",
          },
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: 'rgba(46, 125, 50, 0.06)',
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          padding: "12px 16px",
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          background: 'rgba(255, 255, 255, 0.08)',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          fontWeight: 500,
        },
      },
    },
  },
});

// ─── Auto Bet Placement Panel ────────────────────────────────────────────────
const sliderSx = {
  color: '#2E7D32',
  '& .MuiSlider-thumb': { width: 14, height: 14, bgcolor: '#2E7D32' },
  '& .MuiSlider-rail': { bgcolor: 'rgba(255,255,255,0.15)' },
  '& .MuiSlider-track': { bgcolor: '#2E7D32', border: 'none' },
  '& .MuiSlider-valueLabel': {
    bgcolor: '#1a1a1a', border: '1px solid rgba(46,125,50,0.5)',
    fontSize: '0.75rem', color: '#2E7D32',
  },
};

const inputSx = {
  '& .MuiOutlinedInput-root': {
    bgcolor: 'rgba(255,255,255,0.04)',
    '& fieldset': { borderColor: 'rgba(255,255,255,0.15)' },
    '&:hover fieldset': { borderColor: 'rgba(46,125,50,0.5)' },
    '&.Mui-focused fieldset': { borderColor: '#2E7D32' },
  },
  '& .MuiInputLabel-root': { color: '#777', fontSize: '0.8rem' },
  '& .MuiInputLabel-root.Mui-focused': { color: '#2E7D32' },
  '& input': { color: '#fff', fontSize: '0.85rem' },
};

function AutoBetPlacementPanel() {
  const [minEv, setMinEv] = useState(4);
  const [maxEv, setMaxEv] = useState(20);
  const [enabled, setEnabled] = useState(false);
  const [unitSize, setUnitSize] = useState('50');
  const [maxPerEvent, setMaxPerEvent] = useState('200');
  const [kelly, setKelly] = useState('fixed');
  const [kellyCap, setKellyCap] = useState('150');
  const [minOdds, setMinOdds] = useState('-300');
  const [maxOdds, setMaxOdds] = useState('+400');

  const kellyDesc: Record<string, string> = {
    fixed: `Flat $${unitSize} per qualifying bet.`,
    quarter_kelly: 'Quarter Kelly — conservative, recommended for live use.',
    half_kelly: 'Half Kelly — moderate risk.',
    full_kelly: 'Full Kelly — aggressive, higher variance.',
  };

  return (
    <Paper
      sx={{
        p: 4,
        display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'hidden',
        border: enabled ? '1px solid rgba(76,175,80,0.25)' : '1px solid rgba(255,255,255,0.08)',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        '&:hover': { boxShadow: '0 8px 32px rgba(46, 125, 50, 0.15)', transform: 'translateY(-2px)' },
      }}
    >
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <AutoMode sx={{ fontSize: 24, color: enabled ? '#4CAF50' : '#2E7D32' }} />
        <Typography component="h2" variant="h6" sx={{ color: '#FFFFFF', fontWeight: 500, letterSpacing: '-0.01em' }}>
          Auto Bet Placement
        </Typography>
        {enabled && (
          <Chip label="ACTIVE" size="small" sx={{ bgcolor: 'rgba(76,175,80,0.15)', color: '#4CAF50', border: '1px solid rgba(76,175,80,0.35)', fontSize: '0.65rem', height: 20, fontWeight: 700, letterSpacing: '0.05em',
            '& .MuiChip-label': { px: 1 } }} />
        )}
        <Box sx={{ flexGrow: 1 }} />
        <Typography sx={{ fontSize: '0.8rem', color: enabled ? '#4CAF50' : '#777' }}>
          {enabled ? 'Enabled' : 'Disabled'}
        </Typography>
        <Switch
          checked={enabled}
          onChange={e => setEnabled(e.target.checked)}
          sx={{
            '& .MuiSwitch-switchBase.Mui-checked': { color: '#4CAF50' },
            '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { bgcolor: '#4CAF50' },
            '& .MuiSwitch-track': { bgcolor: 'rgba(255,255,255,0.15)' },
          }}
        />
      </Box>

      <Divider sx={{ mb: 3 }} />

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 4 }}>
        {/* Left: EV Range */}
        <Box>
          <Typography sx={{ color: '#B0B0B0', fontSize: '0.75rem', fontWeight: 600, mb: 2, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            EV Range to Bet
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
            <Typography sx={{ fontSize: '0.75rem', color: '#777', width: 30, flexShrink: 0 }}>Min</Typography>
            <Slider value={minEv} onChange={(_, v) => setMinEv(v as number)}
              min={0} max={20} step={0.5} valueLabelDisplay="auto" valueLabelFormat={v => `${v}%`} sx={sliderSx} />
            <Typography sx={{ fontSize: '0.8rem', color: '#2E7D32', width: 36, textAlign: 'right', flexShrink: 0, fontWeight: 600 }}>
              {minEv}%
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Typography sx={{ fontSize: '0.75rem', color: '#777', width: 30, flexShrink: 0 }}>Max</Typography>
            <Slider value={maxEv} onChange={(_, v) => setMaxEv(v as number)}
              min={0} max={20} step={0.5} valueLabelDisplay="auto" valueLabelFormat={v => v >= 20 ? '∞' : `${v}%`} sx={sliderSx} />
            <Typography sx={{ fontSize: '0.8rem', color: maxEv >= 20 ? '#555' : '#2E7D32', width: 36, textAlign: 'right', flexShrink: 0, fontWeight: 600 }}>
              {maxEv >= 20 ? '∞' : `${maxEv}%`}
            </Typography>
          </Box>
          <Typography sx={{ fontSize: '0.7rem', color: '#555', mt: 1.5, lineHeight: 1.5 }}>
            Only bets with EV between {minEv}% and {maxEv >= 20 ? '∞' : `${maxEv}%`} will be placed automatically when a POD alert fires.
          </Typography>
        </Box>

        {/* Right: Stake + Odds Settings */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>

          {/* Stake Settings */}
          <Box>
            <Typography sx={{ color: '#B0B0B0', fontSize: '0.75rem', fontWeight: 600, mb: 1.5, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Stake Settings
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
              <TextField
                label="Unit Size" value={unitSize} onChange={e => setUnitSize(e.target.value)} size="small"
                InputProps={{ startAdornment: <InputAdornment position="start"><Typography sx={{ color: '#777', fontSize: '0.8rem' }}>$</Typography></InputAdornment> }}
                sx={inputSx}
              />
              <TextField
                label="Max / Event" value={maxPerEvent} onChange={e => setMaxPerEvent(e.target.value)} size="small"
                InputProps={{ startAdornment: <InputAdornment position="start"><Typography sx={{ color: '#777', fontSize: '0.8rem' }}>$</Typography></InputAdornment> }}
                sx={inputSx}
              />
            </Box>
            <Box sx={{ display: 'grid', gridTemplateColumns: kelly === 'fixed' ? '1fr' : '1fr 1fr', gap: 2 }}>
              <FormControl size="small" fullWidth>
                <InputLabel sx={{ color: '#777', fontSize: '0.8rem', '&.Mui-focused': { color: '#2E7D32' } }}>Sizing Method</InputLabel>
                <Select value={kelly} onChange={e => setKelly(e.target.value)} label="Sizing Method"
                  sx={{ bgcolor: 'rgba(255,255,255,0.04)', color: '#fff', fontSize: '0.85rem',
                    '& .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(255,255,255,0.15)' },
                    '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(46,125,50,0.5)' },
                    '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: '#2E7D32' },
                    '& .MuiSvgIcon-root': { color: '#777' } }}>
                  <MenuItem value="fixed">Fixed Unit Size</MenuItem>
                  <MenuItem value="quarter_kelly">Quarter Kelly</MenuItem>
                  <MenuItem value="half_kelly">Half Kelly</MenuItem>
                  <MenuItem value="full_kelly">Full Kelly</MenuItem>
                </Select>
              </FormControl>
              {kelly !== 'fixed' && (
                <TextField
                  label="Kelly Cap" value={kellyCap} onChange={e => setKellyCap(e.target.value)} size="small"
                  InputProps={{ startAdornment: <InputAdornment position="start"><Typography sx={{ color: '#777', fontSize: '0.8rem' }}>$</Typography></InputAdornment> }}
                  sx={inputSx}
                  helperText="Max bet regardless of Kelly size"
                  FormHelperTextProps={{ sx: { color: '#555', fontSize: '0.65rem' } }}
                />
              )}
            </Box>
            <Typography sx={{ fontSize: '0.7rem', color: '#555', mt: 1, lineHeight: 1.5 }}>
              {kellyDesc[kelly]}
            </Typography>
          </Box>

          {/* Odds Range */}
          <Box>
            <Typography sx={{ color: '#B0B0B0', fontSize: '0.75rem', fontWeight: 600, mb: 1.5, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Odds Range
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
              <TextField
                label="Min Odds" value={minOdds} onChange={e => setMinOdds(e.target.value)} size="small"
                placeholder="-300"
                sx={inputSx}
                helperText="Shortest (e.g. -300)"
                FormHelperTextProps={{ sx: { color: '#555', fontSize: '0.65rem' } }}
              />
              <TextField
                label="Max Odds" value={maxOdds} onChange={e => setMaxOdds(e.target.value)} size="small"
                placeholder="+400"
                sx={inputSx}
                helperText="Longest (e.g. +400)"
                FormHelperTextProps={{ sx: { color: '#555', fontSize: '0.65rem' } }}
              />
            </Box>
            <Typography sx={{ fontSize: '0.7rem', color: '#555', mt: 0.5, lineHeight: 1.5 }}>
              Skip bets with BetBCK odds outside this range. Avoids very short favourites and long shots.
            </Typography>
          </Box>

        </Box>
      </Box>

      <Divider sx={{ mt: 3, mb: 2 }} />

      {/* Status footer */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
        <Typography sx={{ fontSize: '0.72rem', color: '#555' }}>
          ⚑ Duplicate protection is always on — each game/market combination is only bet once per session.
        </Typography>
        <Typography sx={{ fontSize: '0.72rem', color: '#444', fontStyle: 'italic' }}>
          Wager POST endpoint pending — configure once BetBCK form selectors are confirmed.
        </Typography>
      </Box>
    </Paper>
  );
}

// Context for BetBCK tab reference
export const BetbckTabContext = createContext<{ betbckTabRef: React.MutableRefObject<Window | null> }>({ betbckTabRef: { current: null } });

function openBetbckTabOnLoad(betbckTabRef: React.MutableRefObject<Window | null>) {
  if (!betbckTabRef.current || betbckTabRef.current.closed) {
    betbckTabRef.current = window.open('https://betbck.com', 'betbck_tab');
  }
}

function App() {
  const betbckTabRef = useRef<Window | null>(null);

  React.useEffect(() => {
    openBetbckTabOnLoad(betbckTabRef);
  }, []);

  return (
    <BetbckTabContext.Provider value={{ betbckTabRef }}>
      <ThemeProvider theme={modernTheme}>
        <CssBaseline />
        <Box
          sx={{
            minHeight: "100vh",
            background: "linear-gradient(135deg, #0A0A0A 0%, #1A1A1A 100%)",
          }}
        >
          {/* Premium Header */}
          <AppBar position="static" elevation={0}>
            <Toolbar sx={{ py: 3, justifyContent: 'center', minHeight: 80 }}>
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 2,
                  px: 4,
                  py: 2,
                  borderRadius: "20px",
                  background: "rgba(26, 26, 26, 0.8)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  backdropFilter: "blur(20px)",
                  maxWidth: 500,
                  mx: 'auto',
                  boxShadow: "0 8px 32px rgba(0, 0, 0, 0.3)",
                }}
              >
                <Box
                  sx={{
                    width: 40,
                    height: 40,
                    borderRadius: "12px",
                    background: "linear-gradient(135deg, #2E7D32 0%, #4CAF50 100%)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    boxShadow: "0 4px 16px rgba(46, 125, 50, 0.3)",
                  }}
                >
                  <Analytics sx={{ fontSize: 24, color: "#FFFFFF" }} />
                </Box>
                <Typography
                  variant="h4"
                  component="div"
                  sx={{
                    fontWeight: 700,
                    color: "#FFFFFF",
                    letterSpacing: "-0.03em",
                    fontSize: "1.75rem",
                    background: "linear-gradient(135deg, #FFFFFF 0%, #B0B0B0 100%)",
                    backgroundClip: "text",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                  }}
                >
                  Unified Betting
                </Typography>
              </Box>
            </Toolbar>
          </AppBar>
          
          <Container maxWidth="xl" sx={{ py: 6, px: { xs: 2, sm: 3 } }}>
            <Grid container spacing={4}>
              {/* Alert Log Section */}
              <Grid item xs={12}>
                <AlertLog />
              </Grid>

              {/* POD Alerts Section */}
              <Grid item xs={12}>
                <Paper
                  sx={{
                    p: 4,
                    display: "flex",
                    flexDirection: "column",
                    position: "relative",
                    overflow: "hidden",
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    '&:hover': {
                      boxShadow: '0 8px 32px rgba(46, 125, 50, 0.15)',
                      transform: 'translateY(-2px)',
                    },
                  }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 2,
                      mb: 3,
                    }}
                  >
                    <NotificationsActive sx={{ fontSize: 24, color: "#2E7D32" }} />
                    <Typography
                      component="h2"
                      variant="h6"
                      sx={{ 
                        color: '#FFFFFF', 
                        fontWeight: 500,
                        letterSpacing: "-0.01em"
                      }}
                    >
                      POD Alerts
                    </Typography>
                    <Box sx={{ flexGrow: 1 }} />
                    <Box
                      sx={{
                        px: 2,
                        py: 0.5,
                        borderRadius: '8px',
                        background: 'rgba(46, 125, 50, 0.1)',
                        border: '1px solid rgba(46, 125, 50, 0.3)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.5,
                        fontSize: '0.75rem',
                        color: '#2E7D32',
                        fontWeight: 500,
                        letterSpacing: "0.05em",
                        textTransform: "uppercase",
                      }}
                    >
                      <Box
                        sx={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          backgroundColor: '#2E7D32',
                          animation: 'pulse 2s infinite',
                        }}
                      />
                      LIVE
                    </Box>
                  </Box>
                  <PODAlerts />
                </Paper>
              </Grid>
              {/* PropBuilder Section — disabled until prop support is re-enabled
              <Grid item xs={12}>
                <Paper sx={{ p: 4, display: "flex", flexDirection: "column", position: "relative", overflow: "hidden" }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
                    <Build sx={{ fontSize: 24, color: "#2E7D32" }} />
                    <Typography component="h2" variant="h6" sx={{ color: '#FFFFFF', fontWeight: 500 }}>
                      PropBuilder EV
                    </Typography>
                  </Box>
                  <PropBuilder />
                </Paper>
              </Grid>
              */}
              {/* BuckeyeScraper Section */}
              <Grid item xs={12}>
                <Paper
                  sx={{
                    p: 4,
                    display: "flex",
                    flexDirection: "column",
                    position: "relative",
                    overflow: "hidden",
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    '&:hover': {
                      boxShadow: '0 8px 32px rgba(46, 125, 50, 0.15)',
                      transform: 'translateY(-2px)',
                    },
                  }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 2,
                      mb: 3,
                    }}
                  >
                    <SportsEsports sx={{ fontSize: 24, color: "#2E7D32" }} />
                    <Typography
                      component="h2"
                      variant="h6"
                      sx={{ 
                        color: '#FFFFFF', 
                        fontWeight: 500,
                        letterSpacing: "-0.01em"
                      }}
                    >
                      EV Bets
                    </Typography>
                  </Box>
                  <BuckeyeScraper />
                </Paper>
              </Grid>
              {/* Auto Bet Placement Section */}
              <Grid item xs={12}>
                <AutoBetPlacementPanel />
              </Grid>
              
              {/* EV Calculator at the bottom, centered */}
              <Grid item xs={12}>
                <Paper
                  sx={{
                    p: 4,
                    display: "flex",
                    flexDirection: "column",
                    position: "relative",
                    overflow: "hidden",
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    '&:hover': {
                      boxShadow: '0 8px 32px rgba(46, 125, 50, 0.15)',
                      transform: 'translateY(-2px)',
                    },
                  }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 2,
                      mb: 3,
                    }}
                  >
                    <Calculate sx={{ fontSize: 24, color: "#2E7D32" }} />
                    <Typography
                      component="h2"
                      variant="h6"
                      sx={{ 
                        color: '#FFFFFF', 
                        fontWeight: 500,
                        letterSpacing: "-0.01em"
                      }}
                    >
                      EV Calculator
                    </Typography>
                  </Box>
                  <EVCalculator />
                </Paper>
              </Grid>
            </Grid>
          </Container>
        </Box>
        
        {/* BetBCK Status Popup - appears only when needed */}
        <BetBCKStatusPopup />
      </ThemeProvider>
    </BetbckTabContext.Provider>
  );
}

export default App;