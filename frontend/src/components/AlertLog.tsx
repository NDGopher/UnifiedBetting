import React, { useEffect, useState, useCallback } from "react";
import {
  Box,
  Typography,
  Chip,
  Collapse,
  IconButton,
  Paper,
  Badge,
  Divider,
} from "@mui/material";
import {
  ExpandMore,
  ExpandLess,
  CheckCircle,
  Error,
  Search,
  NotInterested,
  HelpOutline,
  Timeline,
} from "@mui/icons-material";
import { WS_BASE, API_BASE } from "../utils/apiConfig";

interface AlertStep {
  tag: string;
  message: string;
  detail: any;
}

interface EVEntry {
  market: string;
  selection: string;
  ev_pct: number;
}

interface AlertRecord {
  event_id: string;
  timestamp: string;
  teams: { home?: string; away?: string; league?: string };
  steps: AlertStep[];
  result: string;
  ev_summary: EVEntry[];
}

const RESULT_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  ev_found:      { label: "EV Found",    color: "#2E7D32", icon: <CheckCircle sx={{ fontSize: 14 }} /> },
  found_no_ev:   { label: "No EV",       color: "#FF9800", icon: <Search sx={{ fontSize: 14 }} /> },
  not_found:     { label: "Not Found",   color: "#F44336", icon: <Error sx={{ fontSize: 14 }} /> },
  error:         { label: "Error",       color: "#F44336", icon: <Error sx={{ fontSize: 14 }} /> },
  skipped_prop:  { label: "Skipped",     color: "#9E9E9E", icon: <NotInterested sx={{ fontSize: 14 }} /> },
  completed:     { label: "Completed",   color: "#2196F3", icon: <CheckCircle sx={{ fontSize: 14 }} /> },
  pending:       { label: "Pending",     color: "#9E9E9E", icon: <HelpOutline sx={{ fontSize: 14 }} /> },
};

const TAG_COLORS: Record<string, string> = {
  "ALERT IN":    "#2196F3",
  "SEARCH TERM": "#9E9E9E",
  "SEARCH":      "#9E9E9E",
  "MATCH":       "#FF9800",
  "FOUND":       "#2E7D32",
  "NOT FOUND":   "#F44336",
  "ODDS":        "#9E9E9E",
  "EV":          "#4CAF50",
  "ERROR":       "#F44336",
  "SKIP":        "#9E9E9E",
  "INFO":        "#9E9E9E",
};

function AlertEntry({ record }: { record: AlertRecord }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = RESULT_CONFIG[record.result] || RESULT_CONFIG["pending"];
  const ts = new Date(record.timestamp).toLocaleTimeString();
  const matchup = record.teams.away && record.teams.home
    ? `${record.teams.away} @ ${record.teams.home}`
    : record.event_id;
  const positiveEvs = record.ev_summary.filter(e => e.ev_pct > 0);

  return (
    <Box
      sx={{
        borderLeft: `3px solid ${cfg.color}`,
        pl: 1.5,
        mb: 1,
        cursor: "pointer",
      }}
      onClick={() => setExpanded(v => !v)}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, py: 0.5 }}>
        <Box sx={{ color: cfg.color, display: "flex", alignItems: "center" }}>
          {cfg.icon}
        </Box>
        <Typography variant="body2" sx={{ color: "#E0E0E0", fontWeight: 500, flexGrow: 1, fontSize: "0.8rem" }}>
          {matchup}
        </Typography>
        {positiveEvs.length > 0 && (
          <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap" }}>
            {positiveEvs.map((e, i) => (
              <Chip
                key={i}
                label={`+${e.ev_pct.toFixed(1)}% ${e.market}`}
                size="small"
                sx={{ fontSize: "0.65rem", height: 18, backgroundColor: "rgba(46,125,50,0.2)", color: "#4CAF50" }}
              />
            ))}
          </Box>
        )}
        <Chip
          label={cfg.label}
          size="small"
          sx={{
            fontSize: "0.65rem",
            height: 18,
            backgroundColor: `${cfg.color}22`,
            color: cfg.color,
            border: `1px solid ${cfg.color}44`,
          }}
        />
        <Typography variant="caption" sx={{ color: "#666", fontSize: "0.7rem", whiteSpace: "nowrap" }}>
          {ts}
        </Typography>
        <IconButton size="small" sx={{ p: 0, color: "#666" }}>
          {expanded ? <ExpandLess sx={{ fontSize: 16 }} /> : <ExpandMore sx={{ fontSize: 16 }} />}
        </IconButton>
      </Box>

      <Collapse in={expanded}>
        <Box sx={{ mt: 0.5, mb: 1, pl: 0.5 }}>
          {record.steps.map((step, i) => (
            <Box key={i} sx={{ display: "flex", gap: 1, mb: 0.25 }}>
              <Typography
                variant="caption"
                sx={{
                  color: TAG_COLORS[step.tag] || "#9E9E9E",
                  fontWeight: 600,
                  fontSize: "0.68rem",
                  minWidth: 72,
                  whiteSpace: "nowrap",
                  fontFamily: "monospace",
                }}
              >
                [{step.tag}]
              </Typography>
              <Typography
                variant="caption"
                sx={{ color: "#B0B0B0", fontSize: "0.68rem", lineHeight: 1.4, wordBreak: "break-word" }}
              >
                {step.message}
              </Typography>
            </Box>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}

interface AlertLogProps {
  wsRef?: React.MutableRefObject<WebSocket | null>;
}

export default function AlertLog({ wsRef }: AlertLogProps) {
  const [records, setRecords] = useState<AlertRecord[]>([]);
  const [panelOpen, setPanelOpen] = useState(true);

  const addRecord = useCallback((rec: AlertRecord) => {
    setRecords(prev => [rec, ...prev].slice(0, 20));
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/api/alert-log`)
      .then(r => r.json())
      .then((data: AlertRecord[]) => {
        if (Array.isArray(data)) setRecords(data.slice(0, 20));
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      try {
        ws = new WebSocket(`${WS_BASE}/ws`);
        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === "alert_log" && msg.data) {
              addRecord(msg.data);
            }
          } catch {}
        };
        ws.onclose = () => {
          reconnectTimer = setTimeout(connect, 3000);
        };
        ws.onerror = () => {
          ws?.close();
        };
      } catch {}
    }

    connect();
    return () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [addRecord]);

  const positiveCount = records.filter(r => r.result === "ev_found").length;

  return (
    <Paper
      sx={{
        mb: 2,
        p: 2,
        backgroundColor: "#111",
        border: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <Box
        sx={{ display: "flex", alignItems: "center", gap: 1, cursor: "pointer", mb: panelOpen ? 1.5 : 0 }}
        onClick={() => setPanelOpen(v => !v)}
      >
        <Timeline sx={{ fontSize: 18, color: "#2E7D32" }} />
        <Typography variant="body2" sx={{ color: "#E0E0E0", fontWeight: 600, flexGrow: 1, fontSize: "0.85rem" }}>
          Alert Log
        </Typography>
        {records.length > 0 && (
          <Badge badgeContent={records.length} color="primary" sx={{ mr: 1 }}>
            <Box />
          </Badge>
        )}
        {positiveCount > 0 && (
          <Chip
            label={`${positiveCount} EV`}
            size="small"
            sx={{
              fontSize: "0.65rem",
              height: 18,
              backgroundColor: "rgba(46,125,50,0.2)",
              color: "#4CAF50",
              border: "1px solid rgba(46,125,50,0.4)",
              mr: 0.5,
            }}
          />
        )}
        <Typography variant="caption" sx={{ color: "#555", fontSize: "0.7rem", mr: 0.5 }}>
          {records.length === 0 ? "waiting for alerts..." : `${records.length} alerts`}
        </Typography>
        <IconButton size="small" sx={{ p: 0, color: "#555" }}>
          {panelOpen ? <ExpandLess sx={{ fontSize: 16 }} /> : <ExpandMore sx={{ fontSize: 16 }} />}
        </IconButton>
      </Box>

      <Collapse in={panelOpen}>
        <Divider sx={{ mb: 1.5, borderColor: "rgba(255,255,255,0.06)" }} />
        {records.length === 0 ? (
          <Typography variant="caption" sx={{ color: "#555", fontSize: "0.75rem" }}>
            No alerts processed yet. Load the POD Chrome Extension and open pinnacleoddsdropper.com to start.
          </Typography>
        ) : (
          <Box sx={{ maxHeight: 320, overflowY: "auto" }}>
            {records.map((rec, i) => (
              <AlertEntry key={`${rec.event_id}-${rec.timestamp}-${i}`} record={rec} />
            ))}
          </Box>
        )}
      </Collapse>
    </Paper>
  );
}
