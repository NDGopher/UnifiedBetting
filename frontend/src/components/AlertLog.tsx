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
  Button,
  CircularProgress,
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
  History,
  DeleteSweep,
} from "@mui/icons-material";
import { API_BASE } from "../utils/apiConfig";

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
  ev_found:                  { label: "EV Found",       color: "#2E7D32", icon: <CheckCircle sx={{ fontSize: 14 }} /> },
  found_no_ev:               { label: "No EV",          color: "#FF9800", icon: <Search sx={{ fontSize: 14 }} /> },
  not_found:                 { label: "Not Found",      color: "#F44336", icon: <Error sx={{ fontSize: 14 }} /> },
  error:                     { label: "Error",          color: "#F44336", icon: <Error sx={{ fontSize: 14 }} /> },
  skipped_prop:              { label: "Skipped",        color: "#9E9E9E", icon: <NotInterested sx={{ fontSize: 14 }} /> },
  dropped_suspect_event_id:  { label: "Wrong Fixture",  color: "#FF5722", icon: <Error sx={{ fontSize: 14 }} /> },
  completed:                 { label: "Completed",      color: "#2196F3", icon: <CheckCircle sx={{ fontSize: 14 }} /> },
  pending:                   { label: "Pending",        color: "#9E9E9E", icon: <HelpOutline sx={{ fontSize: 14 }} /> },
};

const TAG_COLORS: Record<string, string> = {
  "ALERT IN":    "#2196F3",
  "SWORDFISH":   "#00BCD4",
  "SEARCH TERM": "#9E9E9E",
  "SEARCH":      "#9E9E9E",
  "MATCH":       "#FF9800",
  "FOUND":       "#2E7D32",
  "ORIENT":      "#FFB300",
  "BCK DATE":    "#78909C",
  "NOT FOUND":   "#F44336",
  "CLOSEST":     "#FF6F00",
  "ODDS":        "#9E9E9E",
  "EV":          "#4CAF50",
  "ERROR":       "#F44336",
  "WARNING":     "#FF5722",
  "SKIP":        "#9E9E9E",
  "INFO":        "#9E9E9E",
};

const PAGE_SIZE = 20;

function AlertEntry({ record, historical }: { record: AlertRecord; historical?: boolean }) {
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
        opacity: historical ? 0.75 : 1,
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
  const [allRecords, setAllRecords] = useState<AlertRecord[]>([]);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [panelOpen, setPanelOpen] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [totalFetched, setTotalFetched] = useState(0); // eslint-disable-line @typescript-eslint/no-unused-vars

  const addRecord = useCallback((rec: AlertRecord) => {
    setAllRecords(prev => {
      const deduped = prev.filter(r => !(r.event_id === rec.event_id && r.timestamp === rec.timestamp));
      return [rec, ...deduped];
    });
  }, []);

  useEffect(() => {
    setLoadingHistory(true);
    fetch(`${API_BASE}/api/alert-log`)
      .then(r => r.json())
      .then((data: AlertRecord[]) => {
        if (Array.isArray(data)) {
          setAllRecords(data);
          setTotalFetched(data.length);
        }
      })
      .catch(() => {})
      .finally(() => setLoadingHistory(false));
  }, []);

  useEffect(() => {
    let es: EventSource | null = null;

    function connect() {
      es = new EventSource('/api/events/stream');
      es.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "alert_log" && msg.data) {
            addRecord(msg.data);
          }
        } catch {}
      };
      es.onerror = () => {
        // EventSource auto-reconnects
      };
    }

    connect();
    return () => {
      es?.close();
    };
  }, [addRecord]);

  const visibleRecords = allRecords.slice(0, visibleCount);
  const hasMore = visibleCount < allRecords.length;
  const positiveCount = allRecords.filter(r => r.result === "ev_found").length;

  const handleLoadMore = () => {
    setVisibleCount(prev => prev + PAGE_SIZE);
  };

  const handleClearLog = useCallback(async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('Clear the entire alert log? This cannot be undone.')) return;
    setClearing(true);
    try {
      await fetch(`${API_BASE}/api/alert-log`, { method: 'DELETE' });
      setAllRecords([]);
      setVisibleCount(PAGE_SIZE);
    } catch {}
    finally { setClearing(false); }
  }, []);

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
        <Timeline sx={{ fontSize: 14, color: "#9CA3AF" }} />
        <Typography sx={{ color: "#9CA3AF", fontWeight: 600, flexGrow: 1, fontSize: "0.6875rem", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          Alert Log
        </Typography>
        {allRecords.length > 0 && (
          <Badge badgeContent={allRecords.length} color="primary" sx={{ mr: 1 }}>
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
          {allRecords.length === 0 ? "waiting for alerts..." : `${allRecords.length} alerts`}
        </Typography>
        {allRecords.length > 0 && (
          <Button
            size="small"
            startIcon={clearing ? <CircularProgress size={10} sx={{ color: "#F44336" }} /> : <DeleteSweep sx={{ fontSize: 14 }} />}
            onClick={handleClearLog}
            disabled={clearing}
            sx={{
              fontSize: "0.65rem",
              color: "#555",
              textTransform: "none",
              minWidth: "auto",
              px: 0.75,
              py: 0.25,
              mr: 0.5,
              border: "1px solid rgba(244,67,54,0.2)",
              borderRadius: 1,
              "&:hover": { color: "#F44336", borderColor: "rgba(244,67,54,0.5)", bgcolor: "rgba(244,67,54,0.06)" },
            }}
          >
            Clear
          </Button>
        )}
        <IconButton size="small" sx={{ p: 0, color: "#555" }}>
          {panelOpen ? <ExpandLess sx={{ fontSize: 16 }} /> : <ExpandMore sx={{ fontSize: 16 }} />}
        </IconButton>
      </Box>

      <Collapse in={panelOpen}>
        <Divider sx={{ mb: 1.5, borderColor: "rgba(255,255,255,0.06)" }} />
        {loadingHistory && allRecords.length === 0 ? (
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <CircularProgress size={12} sx={{ color: "#555" }} />
            <Typography variant="caption" sx={{ color: "#555", fontSize: "0.75rem" }}>
              Loading alert history...
            </Typography>
          </Box>
        ) : allRecords.length === 0 ? (
          <Typography variant="caption" sx={{ color: "#555", fontSize: "0.75rem" }}>
            No alerts processed yet. Load the POD Chrome Extension and open pinnacleoddsdropper.com to start.
          </Typography>
        ) : (
          <Box sx={{ maxHeight: 320, overflowY: "auto" }}>
            {visibleRecords.map((rec, i) => (
              <AlertEntry
                key={`${rec.event_id}-${rec.timestamp}-${i}`}
                record={rec}
                historical={i >= PAGE_SIZE}
              />
            ))}
            {hasMore && (
              <Box sx={{ textAlign: "center", pt: 1 }}>
                <Button
                  size="small"
                  startIcon={<History sx={{ fontSize: 14 }} />}
                  onClick={e => { e.stopPropagation(); handleLoadMore(); }}
                  sx={{
                    fontSize: "0.7rem",
                    color: "#666",
                    textTransform: "none",
                    "&:hover": { color: "#999" },
                  }}
                >
                  Load more ({allRecords.length - visibleCount} remaining)
                </Button>
              </Box>
            )}
          </Box>
        )}
      </Collapse>
    </Paper>
  );
}
