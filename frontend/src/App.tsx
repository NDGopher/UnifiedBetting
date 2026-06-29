import React, { createContext, useRef, useState } from "react";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import Typography from "@mui/material/Typography";
import { AppBar, Toolbar, Slider, Switch, TextField, Divider, InputAdornment, Select, MenuItem, FormControl, InputLabel, Chip } from "@mui/material";
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
      default: "#0D0D0D",
      paper: "#151515",
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
          backgroundColor: "#151515",
          border: "1px solid rgba(255, 255, 255, 0.06)",
          borderRadius: "12px",
          boxShadow: "0 2px 16px rgba(0, 0, 0, 0.4)",
          backdropFilter: "blur(20px)",
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          background: "rgba(13, 13, 13, 0.95)",
          backdropFilter: "blur(20px)",
          borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
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
          transition: "all 150ms cubic-bezier(0.4, 0, 0.2, 1)",
          '&:hover': {
            transform: "translateY(-1px)",
            boxShadow: "0 4px 12px rgba(0,0,0,0.25)",
          },
          '&:active': {
            transform: "translateY(0px)",
          },
        },
        containedPrimary: {
          backgroundColor: "#2E7D32",
          color: "#FFFFFF",
          boxShadow: "0 2px 8px rgba(46, 125, 50, 0.2)",
          '&:hover': {
            backgroundColor: "#1B5E20",
            boxShadow: "0 6px 16px rgba(46, 125, 50, 0.3)",
          },
        },
        outlined: {
          borderColor: "rgba(255, 255, 255, 0.1)",
          color: "#9CA3AF",
          '&:hover': {
            borderColor: "rgba(255, 255, 255, 0.2)",
            backgroundColor: "rgba(255, 255, 255, 0.06)",
          },
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: 'rgba(255,255,255,0.03)',
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
    bgcolor: '#151515', border: '1px solid rgba(46,125,50,0.5)',
    fontSize: '0.75rem', color: '#2E7D32',
  },
};

const inputSx = {
  '& .MuiOutlinedInput-root': {
    bgcolor: '#1A1A1A',
    borderRadius: '6px',
    '& fieldset': { border: 'none' },
    '&::after': {
      content: '""',
      position: 'absolute', bottom: 0, left: 0, right: 0, height: '1px',
      bgcolor: 'rgba(255,255,255,0.1)',
    },
    '&:hover::after': { bgcolor: 'rgba(255,255,255,0.2)' },
    '&.Mui-focused::after': { bgcolor: 'rgba(255,255,255,0.3)', height: '1px' },
  },
  '& .MuiInputLabel-root': { color: '#6B7280', fontSize: '0.75rem' },
  '& .MuiInputLabel-root.Mui-focused': { color: '#9CA3AF' },
  '& input': { color: '#F5F5F5', fontSize: '0.875rem', fontFamily: '"JetBrains Mono", "Fira Code", "Consolas", monospace', fontVariantNumeric: 'tabular-nums' },
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
    <Box sx={{ pt: 5, pb: 5, display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Box sx={{ px: 0.875, py: 0.375, border: '1px solid rgba(255,255,255,0.22)', borderRadius: '4px', fontSize: '0.6rem', fontWeight: 700, color: '#F5F5F5', letterSpacing: '0.06em', lineHeight: 1.6, userSelect: 'none' }}>AB</Box>
        <Typography component="h2" sx={{ fontSize: '0.6875rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#9CA3AF' }}>
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
                <InputLabel sx={{ color: '#6B7280', fontSize: '0.75rem', '&.Mui-focused': { color: '#9CA3AF' } }}>Sizing Method</InputLabel>
                <Select value={kelly} onChange={e => setKelly(e.target.value)} label="Sizing Method"
                  sx={{ bgcolor: '#1A1A1A', color: '#F5F5F5', fontSize: '0.875rem', borderRadius: '6px',
                    '& .MuiOutlinedInput-notchedOutline': { border: 'none' },
                    '&:hover .MuiOutlinedInput-notchedOutline': { border: 'none' },
                    '&.Mui-focused .MuiOutlinedInput-notchedOutline': { border: 'none' },
                    '& .MuiSvgIcon-root': { color: '#6B7280' } }}>
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
    </Box>
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
  const [now, setNow] = useState(new Date());

  React.useEffect(() => {
    openBetbckTabOnLoad(betbckTabRef);
  }, []);

  React.useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const cdtTime = now.toLocaleTimeString('en-US', {
    timeZone: 'America/Chicago',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  });

  return (
    <BetbckTabContext.Provider value={{ betbckTabRef }}>
      <ThemeProvider theme={modernTheme}>
        <CssBaseline />
        <Box
          sx={{
            minHeight: "100vh",
            background: "#0D0D0D",
          }}
        >
          {/* Navigation Bar */}
          <AppBar position="static" elevation={0}>
            <Toolbar sx={{ px: { xs: 2, sm: 4 }, minHeight: '48px !important', height: 48 }}>
              {/* Brand lockup */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Box sx={{
                  px: 0.875, py: 0.375,
                  border: '1px solid rgba(255,255,255,0.22)',
                  borderRadius: '4px',
                  fontSize: '0.6rem', fontWeight: 700, color: '#F5F5F5',
                  letterSpacing: '0.06em', lineHeight: 1.6,
                  userSelect: 'none',
                }}>
                  UB
                </Box>
                <Typography sx={{
                  fontSize: '0.75rem', fontWeight: 600, color: '#F5F5F5',
                  letterSpacing: '0.1em', textTransform: 'uppercase',
                }}>
                  Unified Betting
                </Typography>
              </Box>

              <Box sx={{ flexGrow: 1 }} />

              {/* System status cluster */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5 }}>
                <Typography sx={{
                  fontSize: '0.6875rem', color: '#4B5563',
                  fontFamily: '"JetBrains Mono", "Fira Code", "Consolas", monospace',
                  letterSpacing: '0.03em',
                }}>
                  {cdtTime} CDT
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                  <Box sx={{ width: 5, height: 5, borderRadius: '50%', bgcolor: '#32D74B', flexShrink: 0 }} />
                  <Typography sx={{ fontSize: '0.6875rem', color: '#4B5563', letterSpacing: '0.02em' }}>
                    System: Online
                  </Typography>
                </Box>
              </Box>
            </Toolbar>
          </AppBar>
          
          <Container maxWidth="xl" sx={{ px: { xs: 2, sm: 3 } }}>

            {/* Alert Log Section */}
            <Box sx={{ py: 5 }}>
              <AlertLog />
            </Box>

            {/* POD Alerts Section */}
            <Box sx={{ borderTop: '1px solid rgba(255,255,255,0.06)', pt: 5, pb: 5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 4 }}>
                <Box sx={{ px: 0.875, py: 0.375, border: '1px solid rgba(255,255,255,0.22)', borderRadius: '4px', fontSize: '0.6rem', fontWeight: 700, color: '#F5F5F5', letterSpacing: '0.06em', lineHeight: 1.6, userSelect: 'none' }}>PA</Box>
                <Typography component="h2" sx={{ fontSize: '0.6875rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#9CA3AF' }}>
                  POD Alerts
                </Typography>
                <Box sx={{ flexGrow: 1 }} />
                <Box sx={{
                  px: 2, py: 0.5, borderRadius: '8px',
                  background: 'rgba(46, 125, 50, 0.1)', border: '1px solid rgba(46, 125, 50, 0.3)',
                  display: 'flex', alignItems: 'center', gap: 0.75,
                  fontSize: '0.7rem', color: '#2E7D32', fontWeight: 600,
                  letterSpacing: '0.06em', textTransform: 'uppercase',
                }}>
                  <Box sx={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: '#2E7D32', animation: 'pulse 2s infinite' }} />
                  LIVE
                </Box>
              </Box>
              <PODAlerts />
            </Box>

            {/* EV Bets Section */}
            <Box sx={{ borderTop: '1px solid rgba(255,255,255,0.06)', pt: 5, pb: 5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 4 }}>
                <Box sx={{ px: 0.875, py: 0.375, border: '1px solid rgba(255,255,255,0.22)', borderRadius: '4px', fontSize: '0.6rem', fontWeight: 700, color: '#F5F5F5', letterSpacing: '0.06em', lineHeight: 1.6, userSelect: 'none' }}>EV</Box>
                <Typography component="h2" sx={{ fontSize: '0.6875rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#9CA3AF' }}>
                  EV Bets
                </Typography>
              </Box>
              <BuckeyeScraper />
            </Box>

            {/* Auto Bet Placement Section */}
            <Box sx={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
              <AutoBetPlacementPanel />
            </Box>

            {/* EV Calculator Section */}
            <Box sx={{ borderTop: '1px solid rgba(255,255,255,0.06)', pt: 5, pb: 8 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 4 }}>
                <Box sx={{ px: 0.875, py: 0.375, border: '1px solid rgba(255,255,255,0.22)', borderRadius: '4px', fontSize: '0.6rem', fontWeight: 700, color: '#F5F5F5', letterSpacing: '0.06em', lineHeight: 1.6, userSelect: 'none' }}>EVC</Box>
                <Typography component="h2" sx={{ fontSize: '0.6875rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#9CA3AF' }}>
                  EV Calculator
                </Typography>
              </Box>
              <EVCalculator />
            </Box>

          </Container>
        </Box>
        
        {/* BetBCK Status Popup - appears only when needed */}
        <BetBCKStatusPopup />
      </ThemeProvider>
    </BetbckTabContext.Provider>
  );
}

export default App;