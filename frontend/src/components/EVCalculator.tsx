import React, { useState, useEffect } from "react";
import {
  Box,
  Paper,
  TextField,
  Typography,
  Grid,
  FormControl,
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

const inputSx = {
  "& .MuiInputBase-root": {
    backgroundColor: "#1A1A1A",
    borderRadius: 0,
    color: "#FFFFFF",
    fontSize: "0.875rem",
  },
  "& .MuiOutlinedInput-notchedOutline": { border: "none" },
  "& .MuiInputBase-root::before": {
    content: '""',
    display: "block",
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    height: "1px",
    backgroundColor: "#333333",
  },
  "& .MuiInputBase-root.Mui-focused::after": {
    content: '""',
    display: "block",
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    height: "1px",
    backgroundColor: "#9CA3AF",
  },
  "& .MuiInputLabel-root": { color: "#9CA3AF", fontSize: "0.75rem" },
  "& .MuiInputLabel-root.Mui-focused": { color: "#9CA3AF" },
  "& input[type=number]": { MozAppearance: "textfield" },
  "& input::-webkit-outer-spin-button, & input::-webkit-inner-spin-button": {
    WebkitAppearance: "none",
  },
};

const selectSx = {
  backgroundColor: "#1A1A1A",
  borderRadius: 0,
  color: "#FFFFFF",
  fontSize: "0.875rem",
  "& .MuiOutlinedInput-notchedOutline": { border: "none" },
  "&::before": {
    content: '""',
    display: "block",
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    height: "1px",
    backgroundColor: "#333333",
  },
  "&.Mui-focused::after": {
    content: '""',
    display: "block",
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    height: "1px",
    backgroundColor: "#9CA3AF",
  },
  "& .MuiSelect-icon": { color: "#9CA3AF" },
};

const EVCalculator: React.FC = () => {
  const [betAmount, setBetAmount] = useState<string>("");
  const [betOdds, setBetOdds] = useState<string>("");
  const [trueOdds, setTrueOdds] = useState<string>("");
  const [oddsFormat, setOddsFormat] = useState<string>("american");
  const [result, setResult] = useState<EVResult | null>(null);

  useEffect(() => {
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
    <Box sx={{ display: "flex", justifyContent: "center" }}>
      <Paper
        elevation={0}
        sx={{
          p: 3,
          minWidth: 360,
          maxWidth: 420,
          width: "100%",
          textAlign: "left",
          borderRadius: 0,
          background: "#111111",
          border: "1px solid #2A2A2A",
        }}
      >
        <Typography
          sx={{
            mb: 3,
            color: "#9CA3AF",
            fontWeight: 600,
            fontSize: "0.7rem",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
          }}
        >
          EV Calculator
        </Typography>

        <Grid container spacing={2}>
          <Grid item xs={12}>
            <Typography
              sx={{
                mb: 0.5,
                color: "#9CA3AF",
                fontSize: "0.7rem",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              Odds Format
            </Typography>
            <FormControl fullWidth>
              <Select
                value={oddsFormat}
                onChange={(e: SelectChangeEvent) => setOddsFormat(e.target.value)}
                sx={selectSx}
                MenuProps={{
                  PaperProps: {
                    sx: {
                      backgroundColor: "#1A1A1A",
                      border: "1px solid #2A2A2A",
                      borderRadius: 0,
                      "& .MuiMenuItem-root": {
                        color: "#E5E5E5",
                        fontSize: "0.875rem",
                        "&:hover": { backgroundColor: "#242424" },
                        "&.Mui-selected": {
                          backgroundColor: "#242424",
                          color: "#FFFFFF",
                        },
                      },
                    },
                  },
                }}
              >
                <MenuItem value="american">American</MenuItem>
                <MenuItem value="decimal">Decimal</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Bet Amount ($)"
              type="number"
              value={betAmount}
              onChange={(e) => setBetAmount(e.target.value)}
              sx={inputSx}
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Bet Odds"
              type="number"
              value={betOdds}
              onChange={(e) => setBetOdds(e.target.value)}
              sx={inputSx}
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="True Odds"
              type="number"
              value={trueOdds}
              onChange={(e) => setTrueOdds(e.target.value)}
              sx={inputSx}
            />
          </Grid>

          {result && (
            <Grid item xs={12}>
              <Box
                sx={{
                  mt: 2,
                  pt: 2,
                  borderTop: "1px solid #2A2A2A",
                }}
              >
                <Typography
                  sx={{
                    mb: 2,
                    color: "#9CA3AF",
                    fontSize: "0.7rem",
                    fontWeight: 600,
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                  }}
                >
                  Results
                </Typography>
                <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <Typography sx={{ color: "#9CA3AF", fontSize: "0.8rem" }}>
                      EV %
                    </Typography>
                    <Typography
                      sx={{
                        color: result.evPercent > 0 ? "#32D74B" : "#EF4444",
                        fontWeight: 600,
                        fontSize: "0.875rem",
                        fontFamily: "monospace",
                      }}
                    >
                      {result.evPercent > 0 ? "+" : ""}
                      {result.evPercent.toFixed(2)}%
                    </Typography>
                  </Box>

                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <Typography sx={{ color: "#9CA3AF", fontSize: "0.8rem" }}>
                      Expected Return
                    </Typography>
                    <Typography
                      sx={{
                        color: result.ev > 0 ? "#32D74B" : "#EF4444",
                        fontWeight: 600,
                        fontSize: "0.875rem",
                        fontFamily: "monospace",
                      }}
                    >
                      {result.ev > 0 ? "+$" : "-$"}
                      {Math.abs(result.ev).toFixed(2)}
                    </Typography>
                  </Box>

                  <Box
                    sx={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <Typography sx={{ color: "#9CA3AF", fontSize: "0.8rem" }}>
                      Implied Probability
                    </Typography>
                    <Typography
                      sx={{
                        color: "#E5E5E5",
                        fontWeight: 500,
                        fontSize: "0.875rem",
                        fontFamily: "monospace",
                      }}
                    >
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
