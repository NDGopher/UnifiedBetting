import React, { useEffect, useState, useCallback } from "react";
import {
  Box,
  Typography,
  Chip,
  Collapse,
  IconButton,
  Paper,
  Divider,
  Button,
  CircularProgress,
} from "@mui/material";
import {
  ExpandMore,
  ExpandLess,
  CheckCircleOutline,
  ErrorOutline,
  Search,
  NotInterested,
  HelpOutline,
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
  ev_found:                  { label: "EV Found",      color: "#32D74B", icon: <CheckCircleOutline sx={{ fontSize: 14 }} /> },
  found_no_ev:               { label: "No EV",         color: "#F4B740", icon: <Search sx={{ fontSize: 14 }} /> },
  not_found:                 { label: "Not Found",     color: "#EF4444", icon: <ErrorOutline sx={{ fontSize: 14 }} /> },
  error:                     { label: "Error",         color: "#EF4444", icon: <ErrorOutline sx={{ fontSize: 14 }} /> },
  skipped_prop:              { label: "Skipped",       color: "#6B7280", icon: <NotInterested sx={{ fontSize: 14 }} /> },
  dropped_suspect_event_id:  { label: "Wrong Fixture", color: "#EF4444", icon: <ErrorOutline sx={{ fontSize: 14 }} /> },
  completed:                 { label: "Completed",     color: "#32D74B", icon: <CheckCircleOutline sx={{ fontSize: 14 }} /> },
  pending:                   { label: "Pending",       color: "#6B7280", icon: <HelpOutline sx={{ fontSize: 14 }} /> },
};

const MONO = '"JetBrains Mono", "Fira Code", "Consolas", monospace';
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
        pl: 0,
        mb: 0.5,
        cursor: "pointer",
        opacity: historical ? 0.65 : 1,
        borderRadius: '4px',
        '&:hover': { bgcolor: 'rgba(255,255,255,0.02)' },
      }}
      onClick={() => setExpanded(v => !v)}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, py: 0.5, px: 0.5 }}>
        {/* Status dot — pure CSS, no SVG */}
        <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: cfg.color, flexShrink: 0 }} />

        <Typography sx={{ color: "#D1D5DB", fontWeight: 600, flexGrow: 1, fontSize: "0.8rem", lineHeight: 1.3 }}>
          {matchup}
        </Typography>

        {/* EV badges — flat bg, green text only */}
        {positiveEvs.length > 0 && (
          <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap" }}>
            {positiveEvs.map((e, i) => (
              <Chip
                key={i}
                label={`+${e.ev_pct.toFixed(1)}% ${e.market}`}
                size="small"
                sx={{
                  fontSize: "0.65rem", height: 18,
                  backgroundColor: "rgba(255,255,255,0.05)",
                  color: "#32D74B",
                  border: "none",
                  fontFamily: MONO,
                }}
              />
            ))}
          </Box>
        )}

        {/* Status badge — flat bg, colored text only, no border */}
        <Chip
          label={cfg.label}
          size="small"
          sx={{
            fontSize: "0.65rem",
            height: 18,
            backgroundColor: "rgba(255,255,255,0.05)",
            color: cfg.color,
            border: "none",
          }}
        />

        <Typography sx={{ color: "#6B7280", fontSize: "0.68rem", whiteSpace: "nowrap" }}>
          {ts}
        </Typography>
        <IconButton size="small" sx={{ p: 0, color: "#4B5563" }}>
          {expanded ? <ExpandLess sx={{ fontSize: 14 }} /> : <ExpandMore sx={{ fontSize: 14 }} />}
        </IconButton>
      </Box>

      {/* ── Expanded console ─────────────────────────────────────────── */}
      <Collapse in={expanded}>
        <Box sx={{
          mx: 0.5, mb: 0.75,
          bgcolor: '#0A0A0A',
          borderRadius: '6px',
          p: 1.25,
          boxShadow: 'inset 0 1px 8px rgba(0,0,0,0.6)',
        }}>
          {record.steps.map((step, i) => {
            const isEV = step.tag === "EV" && /=>\s*\+/.test(step.message);
            return (
            <Box key={i} sx={{
              display: "flex", gap: 0.75, mb: 0.125,
              ...(isEV && {
                bgcolor: 'rgba(50,215,75,0.06)',
                borderRadius: '3px',
                px: 0.5,
                mx: -0.5,
              }),
            }}>
              {/* [TAG] with dim brackets and light keyword */}
              <Typography sx={{
                fontSize: "0.75rem",
                lineHeight: 1.5,
                whiteSpace: "nowrap",
                minWidth: 80,
                fontFamily: MONO,
                flexShrink: 0,
              }}>
                <Box component="span" sx={{ color: isEV ? 'rgba(50,215,75,0.5)' : '#6B7280' }}>[</Box>
                <Box component="span" sx={{ color: isEV ? '#32D74B' : '#D1D5DB', fontWeight: 600 }}>{step.tag}</Box>
                <Box component="span" sx={{ color: isEV ? 'rgba(50,215,75,0.5)' : '#6B7280' }}>]</Box>
              </Typography>
              <Typography sx={{
                color: isEV ? 'rgba(50,215,75,0.85)' : "#9CA3AF",
                fontSize: "0.75rem",
                lineHeight: 1.5,
                wordBreak: "break-word",
                fontFamily: MONO,
                fontWeight: isEV ? 500 : 400,
              }}>
                {step.message}
              </Typography>
            </Box>
            );
          })}
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
      es.onerror = () => {};
    }

    connect();
    return () => { es?.close(); };
  }, [addRecord]);

  const visibleRecords = allRecords.slice(0, visibleCount);
  const hasMore = visibleCount < allRecords.length;
  const positiveCount = allRecords.filter(r => r.result === "ev_found").length;

  const handleLoadMore = () => setVisibleCount(prev => prev + PAGE_SIZE);

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
        mb: 1,
        px: 2, pt: 1.25, pb: 1.25,
        backgroundColor: "#111",
        border: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      {/* ── Header ────────────────────────────────────────────────────── */}
      <Box
        sx={{ display: "flex", alignItems: "center", gap: 1, cursor: "pointer", mb: panelOpen ? 1 : 0 }}
        onClick={() => setPanelOpen(v => !v)}
      >
        <Box sx={{ px: 0.875, py: 0.375, border: '1px solid rgba(255,255,255,0.22)', borderRadius: '4px', fontSize: '0.6rem', fontWeight: 700, color: '#F5F5F5', letterSpacing: '0.08em', lineHeight: 1.6, userSelect: 'none', flexShrink: 0 }}>ALERT LOG</Box>
        <Box sx={{ flexGrow: 1 }} />

        {/* Total count badge — neutral */}
        {allRecords.length > 0 && (
          <Box sx={{
            px: 0.875, py: 0.1,
            bgcolor: 'rgba(255,255,255,0.05)',
            borderRadius: '4px',
            fontSize: '0.65rem', color: '#6B7280',
            lineHeight: 1.6,
          }}>
            {allRecords.length}
          </Box>
        )}

        {/* EV hit count badge — neutral bg, green text */}
        {positiveCount > 0 && (
          <Chip
            label={`${positiveCount} EV`}
            size="small"
            sx={{
              fontSize: "0.65rem",
              height: 18,
              backgroundColor: "rgba(255,255,255,0.05)",
              color: "#32D74B",
              border: "none",
            }}
          />
        )}

        <Typography sx={{ color: "#4B5563", fontSize: "0.68rem", mr: 0.5 }}>
          {allRecords.length === 0 ? "waiting for alerts..." : `${allRecords.length} alerts`}
        </Typography>

        {allRecords.length > 0 && (
          <Button
            size="small"
            startIcon={clearing ? <CircularProgress size={10} sx={{ color: "#EF4444" }} /> : <DeleteSweep sx={{ fontSize: 13 }} />}
            onClick={handleClearLog}
            disabled={clearing}
            sx={{
              fontSize: "0.65rem",
              color: "#4B5563",
              textTransform: "none",
              minWidth: "auto",
              px: 0.75,
              py: 0.25,
              mr: 0.5,
              border: "1px solid rgba(255,255,255,0.07)",
              borderRadius: 1,
              "&:hover": { color: "#EF4444", borderColor: "rgba(239,68,68,0.35)", bgcolor: "rgba(239,68,68,0.05)" },
            }}
          >
            Clear
          </Button>
        )}
        <IconButton size="small" sx={{ p: 0, color: "#4B5563" }}>
          {panelOpen ? <ExpandLess sx={{ fontSize: 16 }} /> : <ExpandMore sx={{ fontSize: 16 }} />}
        </IconButton>
      </Box>

      <Collapse in={panelOpen}>
        <Divider sx={{ mb: 1.5, borderColor: "rgba(255,255,255,0.06)" }} />
        {loadingHistory && allRecords.length === 0 ? (
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <CircularProgress size={12} sx={{ color: "#555" }} />
            <Typography sx={{ color: "#555", fontSize: "0.75rem" }}>
              Loading alert history...
            </Typography>
          </Box>
        ) : allRecords.length === 0 ? (
          <Typography sx={{ color: "#4B5563", fontSize: "0.75rem" }}>
            No alerts processed yet. Load the POD Chrome Extension and open pinnacleoddsdropper.com to start.
          </Typography>
        ) : (
          <Box sx={{
            maxHeight: 180,
            overflowY: "auto",
            '&::-webkit-scrollbar': { width: 4 },
            '&::-webkit-scrollbar-track': { bgcolor: '#151515' },
            '&::-webkit-scrollbar-thumb': { bgcolor: '#333333', borderRadius: '2px' },
          }}>
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
                  startIcon={<History sx={{ fontSize: 13 }} />}
                  onClick={e => { e.stopPropagation(); handleLoadMore(); }}
                  sx={{
                    fontSize: "0.68rem",
                    color: "#4B5563",
                    textTransform: "none",
                    "&:hover": { color: "#9CA3AF" },
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
