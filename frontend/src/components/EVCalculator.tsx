import React, { useState, useEffect } from "react";
import {
  Box,
  Paper,
  TextField,
  Typography,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  SelectChangeEvent,
} from "@mui/material";
import { americanToDecimal, calculateEV } from "../utils/oddsUtils";

interface EVResult {
  ev: number;
  decimalOdds: number;
  impliedProbability: number;
  evPercent: number;
}

const EVCalculator: React.FC = () => {
  const [betAmount, setBetAmount] = useState<string>("");
  const [betOdds, setBetOdds] = useState<string>("");
  const [trueOdds, setTrueOdds] = useState<string>("");
  const [oddsFormat, setOddsFormat] = useState<string>("american");
  const [result, setResult] = useState<EVResult | null>(null);

  useEffect(() => {
    // Auto-calculate EV as inputs change
    try {
      const betAmountNum = parseFloat(betAmount);
      const betOddsNum = parseFloat(betOdds);
      const trueOddsNum = parseFloat(trueOdds);
      if (
        isNaN(betAmountNum) ||
        isNaN(betOddsNum) ||
        isNaN(trueOddsNum) ||
        betAmount === "" ||
        betOdds === "" ||
        trueOdds === ""
      ) {
        setResult(null);
        return;
      }
      let betDecimalOdds: number;
      let trueDecimalOdds: number;
      if (oddsFormat === "american") {
        betDecimalOdds = americanToDecimal(betOddsNum);
        trueDecimalOdds = americanToDecimal(trueOddsNum);
      } else {
        betDecimalOdds = betOddsNum;
        trueDecimalOdds = trueOddsNum;
      }
      const ev = calculateEV(betAmountNum, betDecimalOdds, trueDecimalOdds);
      const impliedProbability = (1 / trueDecimalOdds) * 100;
      const evPercent = ((betDecimalOdds / trueDecimalOdds) - 1) * 100;
      setResult({
        ev,
        decimalOdds: trueDecimalOdds,
        impliedProbability,
        evPercent,
      });
    } catch (error) {
      setResult(null);
    }
  }, [betAmount, betOdds, trueOdds, oddsFormat]);

  return (
    <Box sx={{ display: 'flex', justifyContent: 'center' }}>
      <Paper sx={{ 
        p: 4, 
        minWidth: 360, 
        maxWidth: 420, 
        width: '100%', 
        textAlign: 'center', 
        borderRadius: 2, 
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
        background: 'rgba(26, 26, 26, 0.8)',
        backdropFilter: 'blur(20px)',
        border: '1px solid rgba(255, 255, 255, 0.08)'
      }}>
        <Typography variant="h6" sx={{ 
          mb: 3, 
          color: '#FFFFFF', 
          fontWeight: 500,
          letterSpacing: '-0.01em'
        }}>
          EV Calculator
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>Odds Format</InputLabel>
              <Select
                value={oddsFormat}
                label="Odds Format"
                onChange={(e: SelectChangeEvent) => setOddsFormat(e.target.value)}
              >
                <MenuItem value="american">American</MenuItem>
                <MenuItem value="decimal">Decimal</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Bet Amount"
              type="number"
              value={betAmount}
              onChange={(e) => setBetAmount(e.target.value)}
              InputProps={{
                startAdornment: <Typography>$</Typography>,
              }}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Bet Odds"
              type="number"
              value={betOdds}
              onChange={(e) => setBetOdds(e.target.value)}
              InputProps={{
                startAdornment: oddsFormat === "american" && (
                  <Typography>{parseFloat(betOdds) > 0 ? "+" : ""}</Typography>
                ),
              }}
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="True Odds"
              type="number"
              value={trueOdds}
              onChange={(e) => setTrueOdds(e.target.value)}
              InputProps={{
                startAdornment: oddsFormat === "american" && (
                  <Typography>{parseFloat(trueOdds) > 0 ? "+" : ""}</Typography>
                ),
              }}
            />
          </Grid>
          {result && (
            <Grid item xs={12}>
              <Box sx={{ 
                mt: 3, 
                p: 3, 
                bgcolor: 'rgba(46, 125, 50, 0.1)', 
                borderRadius: 2,
                border: '1px solid rgba(46, 125, 50, 0.2)'
              }}>
                <Typography variant="subtitle1" sx={{ 
                  mb: 2, 
                  color: '#FFFFFF', 
                  fontWeight: 600 
                }}>
                  Results
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography sx={{ color: '#B0B0B0', fontSize: '0.875rem' }}>
                      EV %:
                    </Typography>
                    <Typography sx={{ 
                      color: result.evPercent > 0 ? '#2E7D32' : '#F44336', 
                      fontWeight: 700,
                      fontSize: '1rem'
                    }}>
                      {result.evPercent > 0 ? '+' : ''}{result.evPercent.toFixed(2)}%
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography sx={{ color: '#B0B0B0', fontSize: '0.875rem' }}>
                      Expected Return:
                    </Typography>
                    <Typography sx={{ 
                      color: result.ev > 0 ? '#2E7D32' : '#F44336', 
                      fontWeight: 700,
                      fontSize: '1rem'
                    }}>
                      ${result.ev > 0 ? '+' : ''}{result.ev.toFixed(2)}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography sx={{ color: '#B0B0B0', fontSize: '0.875rem' }}>
                      Implied Probability:
                    </Typography>
                    <Typography sx={{ color: '#FFFFFF', fontWeight: 500, fontSize: '0.875rem' }}>
                      {result.impliedProbability.toFixed(2)}%
                    </Typography>
                  </Box>
                </Box>
              </Box>
            </Grid>
          )}
        </Grid>
      </Paper>
    </Box>
  );
};

export default EVCalculator;
