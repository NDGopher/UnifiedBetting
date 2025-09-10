import React, { createContext, useRef, useContext } from "react";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { AppBar, Toolbar, IconButton } from "@mui/material";
import { 
  TrendingUp, 
  Analytics, 
  Calculate, 
  NotificationsActive,
  Build,
  SportsEsports,
  AutoMode
} from "@mui/icons-material";
import PODAlerts from "./components/PODAlerts";
import EVCalculator from "./components/EVCalculator";
import PropBuilder from "./components/PropBuilder";
import BuckeyeScraper from './components/BuckeyeScraper';
import BetBCKStatusPopup from './components/BetBCKStatusPopup';
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
              {/* PropBuilder Section */}
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
                    <Build sx={{ fontSize: 24, color: "#2E7D32" }} />
                    <Typography
                      component="h2"
                      variant="h6"
                      sx={{ 
                        color: '#FFFFFF', 
                        fontWeight: 500,
                        letterSpacing: "-0.01em"
                      }}
                    >
                      PropBuilder EV
                    </Typography>
                  </Box>
                  <PropBuilder />
                </Paper>
              </Grid>
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
                    <AutoMode sx={{ fontSize: 24, color: "#2E7D32" }} />
                    <Typography
                      component="h2"
                      variant="h6"
                      sx={{ 
                        color: '#FFFFFF', 
                        fontWeight: 500,
                        letterSpacing: "-0.01em"
                      }}
                    >
                      Auto Bet Placement
                    </Typography>
                    <Box sx={{ flexGrow: 1 }} />
                    <Box
                      sx={{
                        px: 2,
                        py: 0.5,
                        borderRadius: '8px',
                        background: 'rgba(255, 152, 0, 0.1)',
                        border: '1px solid rgba(255, 152, 0, 0.3)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.5,
                        fontSize: '0.75rem',
                        color: '#FF9800',
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
                          backgroundColor: '#FF9800',
                        }}
                      />
                      COMING SOON
                    </Box>
                  </Box>
                  
                  <Box sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    py: 6,
                    textAlign: 'center'
                  }}>
                    <AutoMode sx={{ 
                      fontSize: 64, 
                      color: 'rgba(46, 125, 50, 0.3)', 
                      mb: 3 
                    }} />
                    <Typography variant="h6" sx={{ 
                      color: '#B0B0B0', 
                      mb: 2,
                      fontWeight: 500
                    }}>
                      Automated Bet Placement
                    </Typography>
                    <Typography variant="body2" sx={{ 
                      color: '#9E9E9E',
                      maxWidth: 400,
                      lineHeight: 1.6
                    }}>
                      This feature will automatically place bets on high EV opportunities 
                      based on your configured parameters and risk management settings.
                    </Typography>
                  </Box>
                </Paper>
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