"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { api, type AuditWithDetails, type Flag, type AuditorQuestion, type FlagContext } from "@/lib/api";
import Link from "next/link";
import { ArrowLeft, RefreshCw, CheckCircle2, XCircle, Clock, FileText, AlertCircle, Play, FileDown, ChevronDown, ChevronUp } from "lucide-react";
import { format } from "date-fns";

export default function ReviewPage() {
  const params = useParams();
  const router = useRouter();
  const auditId = params.auditId as string;

  const [audit, setAudit] = useState<AuditWithDetails | null>(null);
  const [flags, setFlags] = useState<Flag[]>([]);
  const [questions, setQuestions] = useState<AuditorQuestion[]>([]);
  const [regulations, setRegulations] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState<string>("no-green"); // Hide green by default
  const [regulationFilter, setRegulationFilter] = useState<string>("all");
  const [resuming, setResuming] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [reportData, setReportData] = useState<any>(null);
  const [showReportModal, setShowReportModal] = useState(false);
  const [expandedFlags, setExpandedFlags] = useState<Set<string>>(new Set());
  const [expandedContexts, setExpandedContexts] = useState<Set<string>>(new Set());

  const loadAudit = async () => {
    try {
      const data = await api.audits.get(auditId);
      setAudit(data);
      return data;
    } catch (error) {
      console.error("Failed to load audit:", error);
      throw error;
    }
  };

  const loadFlags = async () => {
    try {
      // Handle "no-green" filter - exclude GREEN flags
      let severityParam: string | undefined = undefined;
      if (severityFilter === "no-green") {
        // We'll filter client-side to exclude GREEN
        severityParam = undefined; // Get all flags, filter client-side
      } else if (severityFilter && severityFilter !== "all") {
        severityParam = severityFilter;
      }
      
      const data = await api.flags.list(auditId, {
        severity: severityParam,
        regulation: regulationFilter && regulationFilter !== "all" ? regulationFilter : undefined,
      });
      
      // Filter out GREEN if "no-green" is selected
      const filteredData = severityFilter === "no-green" 
        ? data.filter(flag => flag.flag_type !== "GREEN")
        : data;
      
      setFlags(filteredData);
      return filteredData;
    } catch (error) {
      console.error("Failed to load flags:", error);
      return [];
    }
  };

  const loadQuestions = async () => {
    try {
      const data = await api.questions.list(auditId);
      setQuestions(data);
    } catch (error) {
      console.error("Failed to load questions:", error);
    }
  };

  const loadRegulations = async () => {
    try {
      const data = await api.regulations.list(auditId);
      setRegulations(data);
    } catch (error) {
      console.error("Failed to load regulations:", error);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        await Promise.all([loadAudit(), loadFlags(), loadQuestions(), loadRegulations()]);
      } catch (error) {
        console.error("Error loading data:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [auditId]);

  useEffect(() => {
    if (audit) {
      loadFlags();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [severityFilter, regulationFilter]);

  useEffect(() => {
    if (audit && (audit.status === "running" || audit.status === "queued")) {
      let prevChunkCompleted = audit.chunk_completed;
      const interval = setInterval(async () => {
        try {
          const status = await api.audits.getStatus(auditId) as {
            status: 'queued' | 'running' | 'completed' | 'failed';
            chunk_completed: number;
            chunk_total: number;
            progress_percent: number;
            current_activity?: string;
            completed_at?: string;
            failed_at?: string;
            failure_reason?: string;
            is_draft?: boolean;
          };
          setAudit((prev) => {
            if (!prev) return prev;
            // Reload flags if chunks have been processed (new flags may have been generated)
            if (status.chunk_completed > prevChunkCompleted) {
              prevChunkCompleted = status.chunk_completed;
              loadFlags();
            }
            if (status.status !== prev.status) {
              if (status.status === "completed" || status.status === "failed") {
                loadAudit();
                loadFlags();
                loadQuestions();
              }
              return { ...prev, ...status } as AuditWithDetails;
            }
            return { ...prev, chunk_completed: status.chunk_completed, chunk_total: status.chunk_total };
          });
        } catch (error) {
          console.error("Error polling status:", error);
        }
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [audit?.status, auditId]);

  const handleResumeAudit = async () => {
    setResuming(true);
    try {
      await api.audits.resume(auditId);
      setTimeout(() => {
        loadAudit();
        setResuming(false);
      }, 1500);
    } catch (error: any) {
      alert(`Failed to resume audit: ${error.message}`);
      setResuming(false);
    }
  };

  const handleGenerateReport = async () => {
    // Check if report is already saved
    const savedReport = localStorage.getItem(`report_${auditId}`);
    if (savedReport) {
      try {
        const report = JSON.parse(savedReport);
        setReportData(report);
        setShowReportModal(true);
        return;
      } catch (e) {
        // If parsing fails, regenerate
        localStorage.removeItem(`report_${auditId}`);
      }
    }

    setGeneratingReport(true);
    try {
      const report = await api.audits.generateFinalReport(auditId) as any;
      // Save report to localStorage with timestamp
      const reportWithTimestamp = {
        ...(report || {}),
        generated_at: new Date().toISOString(),
      };
      localStorage.setItem(`report_${auditId}`, JSON.stringify(reportWithTimestamp));
      setReportData(reportWithTimestamp);
      setShowReportModal(true);
    } catch (error: any) {
      alert(`Failed to generate report: ${error.message}`);
    } finally {
      setGeneratingReport(false);
    }
  };

  const downloadReport = (format: 'json' | 'pdf' | 'docx' = 'json') => {
    if (!reportData) return;
    
    const auditName = audit?.document?.original_filename?.replace(/\.[^/.]+$/, "") || `audit_${auditId}`;
    const dateStr = new Date().toISOString().split("T")[0];
    
    if (format === 'json') {
      const dataStr = JSON.stringify(reportData, null, 2);
      const dataBlob = new Blob([dataStr], { type: "application/json" });
      const url = URL.createObjectURL(dataBlob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `final_report_${auditName}_${dateStr}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } else if (format === 'pdf') {
      // Generate PDF using browser print functionality
      const printWindow = window.open('', '_blank');
      if (!printWindow) {
        alert('Please allow popups to download PDF');
        return;
      }
      
      const htmlContent = generateReportHTML();
      printWindow.document.write(htmlContent);
      printWindow.document.close();
      
      // Wait for content to load, then print
      setTimeout(() => {
        printWindow.print();
        // Optionally close after print dialog
        // printWindow.close();
      }, 250);
    } else if (format === 'docx') {
      // Generate Word document
      generateWordDocument(auditName, dateStr);
    }
  };

  const generateReportHTML = () => {
    if (!reportData) return '';
    
    return `
      <!DOCTYPE html>
      <html>
        <head>
          <title>Final Compliance Report</title>
          <style>
            body { font-family: Arial, sans-serif; padding: 40px; line-height: 1.6; }
            h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
            h2 { color: #34495e; margin-top: 30px; }
            h3 { color: #7f8c8d; margin-top: 20px; }
            .critical { background: #fee; border-left: 4px solid #dc3545; padding: 15px; margin: 15px 0; }
            .warning { background: #ffd; border-left: 4px solid #ffc107; padding: 15px; margin: 15px 0; }
            .summary { background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; }
            ul { margin-left: 20px; }
            @media print {
              body { padding: 20px; }
              .no-print { display: none; }
            }
          </style>
        </head>
        <body>
          <h1>Final Compliance Report</h1>
          <p><strong>Audit ID:</strong> ${auditId}</p>
          <p><strong>Date:</strong> ${new Date().toLocaleDateString()}</p>
          
          <div class="summary">
            <h2>Executive Summary</h2>
            <p>${reportData.executive_summary?.replace(/\n/g, '<br>') || 'N/A'}</p>
          </div>
          
          ${reportData.critical_issues && reportData.critical_issues.length > 0 ? `
            <h2>Critical Issues (${reportData.critical_issues.length})</h2>
            ${reportData.critical_issues.map((issue: any, idx: number) => `
              <div class="critical">
                <h3>${idx + 1}. ${escapeHtml(issue.title || 'Critical Issue')}</h3>
                <p>${escapeHtml(issue.description || '').replace(/\n/g, '<br>')}</p>
                ${issue.recommendations && issue.recommendations.length > 0 ? `
                  <p><strong>Recommendations:</strong></p>
                  <ul>
                    ${issue.recommendations.map((rec: string) => `<li>${escapeHtml(rec)}</li>`).join('')}
                  </ul>
                ` : ''}
              </div>
            `).join('')}
          ` : ''}
          
          ${reportData.warnings && reportData.warnings.length > 0 ? `
            <h2>Warnings (${reportData.warnings.length})</h2>
            ${reportData.warnings.map((warning: any, idx: number) => `
              <div class="warning">
                <h3>${idx + 1}. ${escapeHtml(warning.title || 'Warning')}</h3>
                <p>${escapeHtml(warning.description || '').replace(/\n/g, '<br>')}</p>
                ${warning.recommendations && warning.recommendations.length > 0 ? `
                  <p><strong>Recommendations:</strong></p>
                  <ul>
                    ${warning.recommendations.map((rec: string) => `<li>${escapeHtml(rec)}</li>`).join('')}
                  </ul>
                ` : ''}
              </div>
            `).join('')}
          ` : ''}
          
          ${reportData.recommendations && reportData.recommendations.length > 0 ? `
            <h2>Prioritized Recommendations</h2>
            <ol>
              ${reportData.recommendations.map((rec: string) => `<li>${escapeHtml(rec)}</li>`).join('')}
            </ol>
          ` : ''}
          
          <h2>Overall Assessment</h2>
          <div class="summary">
            <p>${reportData.overall_assessment?.replace(/\n/g, '<br>') || 'N/A'}</p>
          </div>
        </body>
      </html>
    `;
  };

  const generateWordDocument = (auditName: string, dateStr: string) => {
    if (!reportData) return;
    
    // Create a simple HTML document that Word can open
    const htmlContent = generateReportHTML();
    const blob = new Blob(['\ufeff', htmlContent], { type: 'application/msword' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `final_report_${auditName}_${dateStr}.doc`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const escapeHtml = (text: string) => {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  };

  const toggleFlagExpanded = (flagId: string) => {
    const newSet = new Set(expandedFlags);
    if (newSet.has(flagId)) {
      newSet.delete(flagId);
    } else {
      newSet.add(flagId);
    }
    setExpandedFlags(newSet);
  };

  const toggleContextExpanded = (flagId: string) => {
    const newSet = new Set(expandedContexts);
    if (newSet.has(flagId)) {
      newSet.delete(flagId);
    } else {
      newSet.add(flagId);
    }
    setExpandedContexts(newSet);
  };

  const getStatusBadge = (status: string | undefined) => {
    if (!status) return <Badge variant="warning">UNKNOWN</Badge>;
    switch (status) {
      case "completed":
        return <Badge className="bg-green-100 text-green-800 border-green-300">COMPLETED</Badge>;
      case "running":
        return <Badge className="bg-yellow-100 text-yellow-800 border-yellow-300">RUNNING</Badge>;
      case "failed":
        return <Badge className="bg-red-100 text-red-800 border-red-300">FAILED</Badge>;
      default:
        return <Badge className="bg-yellow-100 text-yellow-800 border-yellow-300">QUEUED</Badge>;
    }
  };

  const getFlagBadge = (flagType: string) => {
    switch (flagType) {
      case "RED":
        return <Badge className="bg-red-100 text-red-800 border-red-300">Critical</Badge>;
      case "YELLOW":
        return <Badge className="bg-yellow-100 text-yellow-800 border-yellow-300">Warning</Badge>;
      case "GREEN":
        return <Badge className="bg-green-100 text-green-800 border-green-300">Info</Badge>;
      default:
        return <Badge>{flagType}</Badge>;
    }
  };

  const getFlagTypeLabel = (flagType: string) => {
    switch (flagType) {
      case "RED":
        return "Critical";
      case "YELLOW":
        return "Warning";
      case "GREEN":
        return "Info";
      default:
        return flagType;
    }
  };

  if (loading || !audit) {
    return (
      <div className="container mx-auto py-8 px-4 max-w-7xl">
        <div className="text-center py-12">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">Loading audit...</p>
        </div>
      </div>
    );
  }

  const progressPercent = audit.chunk_total > 0 ? (audit.chunk_completed / audit.chunk_total) * 100 : 0;

  return (
    <div className="container mx-auto py-8 px-4 max-w-7xl">
      <Link href="/dashboard">
        <Button variant="ghost" className="mb-6">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Dashboard
        </Button>
      </Link>

      {/* Audit Info */}
      <Card className="mb-6">
        <CardHeader>
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div>
              <CardTitle className="text-2xl mb-2">
                {audit.document?.original_filename || `Audit: ${audit.external_id}`}
              </CardTitle>
              <CardDescription className="flex items-center gap-2 mt-2">
                <FileText className="h-4 w-4" />
                <span>ID: {audit.external_id}</span>
                {audit.document && (
                  <span className="text-muted-foreground">• {audit.document.original_filename}</span>
                )}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {getStatusBadge(audit.status)}
              {audit.is_draft && <Badge className="bg-yellow-100 text-yellow-800 border-yellow-300">DRAFT</Badge>}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <div>
              <p className="text-sm text-muted-foreground">Status</p>
              <p className="font-medium">{audit.status?.toUpperCase() || "UNKNOWN"}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Chunks Processed</p>
              <p className="font-medium">
                {audit.chunk_completed} / {audit.chunk_total}
              </p>
            </div>
            {audit.completed_at && (
              <div>
                <p className="text-sm text-muted-foreground">Completed</p>
                <p className="font-medium">{format(new Date(audit.completed_at), "PPpp")}</p>
              </div>
            )}
            {audit.created_at && (
              <div>
                <p className="text-sm text-muted-foreground">Created</p>
                <p className="font-medium">{format(new Date(audit.created_at), "PPpp")}</p>
              </div>
            )}
          </div>

          {(audit.status === "running" || audit.status === "queued") && (
            <div className="mt-4">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-muted-foreground">
                  Processing: {audit.chunk_completed} / {audit.chunk_total} chunks
                </span>
                {audit.chunk_total > 0 && (
                  <span className="text-muted-foreground">{Math.round(progressPercent)}%</span>
                )}
              </div>
              {audit.chunk_total > 0 && <Progress value={progressPercent} className="h-2" />}
            </div>
          )}

          {audit.failed_at && audit.failure_reason && (
            <div className="mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-md">
              <p className="text-sm font-semibold text-destructive mb-1">Failure Reason</p>
              <p className="text-sm text-destructive">{audit.failure_reason}</p>
            </div>
          )}

          <div className="flex gap-2 mt-4">
            {(audit.status === "failed" || (audit.status === "running" && audit.chunk_total > 0 && audit.chunk_completed < audit.chunk_total)) && (
              <Button onClick={handleResumeAudit} disabled={resuming}>
                <Play className="mr-2 h-4 w-4" />
                {resuming ? "Resuming..." : "Resume Audit"}
              </Button>
            )}
            {audit.status === "completed" && (
              <Button onClick={handleGenerateReport} disabled={generatingReport}>
                <FileDown className="mr-2 h-4 w-4" />
                {generatingReport ? "Generating..." : "Generate Final Report"}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Summary Statistics */}
      {audit.status === "completed" && audit.flag_summary && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Summary Statistics</CardTitle>
          </CardHeader>
          <CardContent>
            {/* Compliance Score Gauge */}
            <div className="flex justify-center mb-8">
              <div className="relative w-48 h-48">
                <svg className="transform -rotate-90 w-48 h-48">
                  <circle
                    cx="96"
                    cy="96"
                    r="80"
                    stroke="currentColor"
                    strokeWidth="20"
                    fill="none"
                    className="text-muted"
                  />
                  <circle
                    cx="96"
                    cy="96"
                    r="80"
                    stroke={
                      audit.flag_summary.compliance_score >= 80
                        ? "rgb(34, 197, 94)"
                        : audit.flag_summary.compliance_score >= 60
                        ? "rgb(234, 179, 8)"
                        : "rgb(239, 68, 68)"
                    }
                    strokeWidth="20"
                    fill="none"
                    strokeDasharray={`${2 * Math.PI * 80}`}
                    strokeDashoffset={`${2 * Math.PI * 80 * (1 - audit.flag_summary.compliance_score / 100)}`}
                    className="transition-all duration-500"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <div className="text-4xl font-bold text-primary">
                    {audit.flag_summary.compliance_score}
                  </div>
                  <div className="text-sm text-muted-foreground">Score</div>
                </div>
              </div>
            </div>

            {/* Flag Breakdown Bar Chart */}
            {audit.flag_summary.total_flags > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold mb-3 text-primary">Flag Breakdown</h3>
                <div className="flex h-10 rounded-md overflow-hidden mb-2">
                  {audit.flag_summary.red_count > 0 && (
                    <div
                      className="bg-red-500 flex items-center justify-center text-white font-semibold text-sm"
                      style={{
                        width: `${(audit.flag_summary.red_count / audit.flag_summary.total_flags) * 100}%`,
                      }}
                      title={`RED: ${audit.flag_summary.red_count}`}
                    >
                      {(audit.flag_summary.red_count / audit.flag_summary.total_flags) * 100 > 10 &&
                        audit.flag_summary.red_count}
                    </div>
                  )}
                  {audit.flag_summary.yellow_count > 0 && (
                    <div
                      className="bg-yellow-500 flex items-center justify-center text-yellow-900 font-semibold text-sm"
                      style={{
                        width: `${(audit.flag_summary.yellow_count / audit.flag_summary.total_flags) * 100}%`,
                      }}
                      title={`YELLOW: ${audit.flag_summary.yellow_count}`}
                    >
                      {(audit.flag_summary.yellow_count / audit.flag_summary.total_flags) * 100 > 10 &&
                        audit.flag_summary.yellow_count}
                    </div>
                  )}
                  {audit.flag_summary.green_count > 0 && (
                    <div
                      className="bg-green-500 flex items-center justify-center text-white font-semibold text-sm"
                      style={{
                        width: `${(audit.flag_summary.green_count / audit.flag_summary.total_flags) * 100}%`,
                      }}
                      title={`GREEN: ${audit.flag_summary.green_count}`}
                    >
                      {(audit.flag_summary.green_count / audit.flag_summary.total_flags) * 100 > 10 &&
                        audit.flag_summary.green_count}
                    </div>
                  )}
                </div>
                <div className="flex gap-4 justify-center text-sm text-muted-foreground">
                  <span>Critical: {audit.flag_summary.red_count}</span>
                  <span>Warning: {audit.flag_summary.yellow_count}</span>
                  <span>Info: {audit.flag_summary.green_count}</span>
                </div>
              </div>
            )}

            {/* Stats Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
              <div className="text-center">
                <div className="text-3xl font-bold text-primary">
                  {audit.flag_summary.compliance_score}
                </div>
                <div className="text-sm text-muted-foreground">Compliance Score</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold">{audit.flag_summary.total_flags}</div>
                <div className="text-sm text-muted-foreground">Total Flags</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-red-500">
                  {audit.flag_summary.red_count}
                </div>
                <div className="text-sm text-muted-foreground">Critical</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-yellow-500">
                  {audit.flag_summary.yellow_count}
                </div>
                <div className="text-sm text-muted-foreground">Warning</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-green-500">
                  {audit.flag_summary.green_count}
                </div>
                <div className="text-sm text-muted-foreground">Info</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <label className="text-sm font-medium mb-2 block">Severity</label>
              <Select value={severityFilter} onValueChange={setSeverityFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="All Severities" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Severities</SelectItem>
                  <SelectItem value="no-green">Hide Green (Critical & Warning Only)</SelectItem>
                  <SelectItem value="RED">Critical</SelectItem>
                  <SelectItem value="YELLOW">Warning</SelectItem>
                  <SelectItem value="GREEN">Info</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {regulations.length > 0 && (
              <div className="flex-1">
                <label className="text-sm font-medium mb-2 block">Regulation</label>
                <Select value={regulationFilter} onValueChange={setRegulationFilter}>
                  <SelectTrigger>
                    <SelectValue placeholder="All Regulations" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Regulations</SelectItem>
                    {regulations.map((reg) => (
                      <SelectItem key={reg} value={reg}>
                        {reg}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="flex items-end">
              <Button
                variant="outline"
                onClick={() => {
                  setSeverityFilter("all");
                  setRegulationFilter("all");
                }}
              >
                Clear Filters
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Flags List */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Compliance Flags ({flags.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {flags.length === 0 ? (
            <div className="text-center py-12">
              <AlertCircle className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-xl font-semibold mb-2">No flags found</h3>
              <p className="text-muted-foreground">
                {severityFilter !== "all" || regulationFilter !== "all"
                  ? "No flags match the selected filters."
                  : audit.status === "running" || audit.status === "queued"
                  ? "Flags will appear here as chunks are processed..."
                  : "This audit has no compliance flags."}
              </p>
            </div>
          ) : (
                <div className="space-y-4">
                  {flags.map((flag) => {
                    const isExpanded = expandedFlags.has(flag.id);
                    const isContextExpanded = expandedContexts.has(flag.id);
                    const borderColor =
                      flag.flag_type === "RED"
                        ? "border-red-500"
                        : flag.flag_type === "YELLOW"
                        ? "border-yellow-500"
                        : "border-green-500";

                    return (
                      <div
                        key={flag.id}
                        className={`border-l-4 ${borderColor} p-4 bg-muted/50 rounded-md`}
                      >
                        <div
                          className="flex justify-between items-start cursor-pointer"
                          onClick={() => toggleFlagExpanded(flag.id)}
                        >
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              {getFlagBadge(flag.flag_type)}
                              <span className="font-semibold">Score: {flag.severity_score}</span>
                              <span className="text-sm text-muted-foreground">
                                Chunk: <code>{flag.chunk_id}</code>
                              </span>
                            </div>
                            <p className="text-sm line-clamp-2">
                              {flag.findings.length > 200
                                ? `${flag.findings.substring(0, 200)}...`
                                : flag.findings}
                            </p>
                            {flag.citations && flag.citations.length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-2">
                                {flag.citations.map((citation, idx) => (
                                  <Badge key={idx} variant="outline" className="text-xs">
                                    {citation.reference}
                                  </Badge>
                                ))}
                              </div>
                            )}
                          </div>
                          <div className="ml-4">
                            {isExpanded ? (
                              <ChevronUp className="h-5 w-5 text-muted-foreground" />
                            ) : (
                              <ChevronDown className="h-5 w-5 text-muted-foreground" />
                            )}
                          </div>
                        </div>

                        {isExpanded && (
                          <div className="mt-4 pt-4 border-t space-y-4">
                            <div>
                              <h4 className="font-semibold mb-2">Findings</h4>
                              <p className="text-sm whitespace-pre-wrap">{flag.findings}</p>
                            </div>
                            {flag.gaps && flag.gaps.length > 0 && (
                              <div>
                                <h4 className="font-semibold mb-2">Gaps Identified</h4>
                                <ul className="list-disc list-inside space-y-1 text-sm">
                                  {flag.gaps.map((gap, i) => (
                                    <li key={i}>{gap}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {flag.recommendations && flag.recommendations.length > 0 && (
                              <div>
                                <h4 className="font-semibold mb-2">Recommendations</h4>
                                <ul className="list-disc list-inside space-y-1 text-sm">
                                  {flag.recommendations.map((rec, i) => (
                                    <li key={i}>{rec}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {flag.citations && flag.citations.length > 0 && (
                              <div>
                                <h4 className="font-semibold mb-2">Citations</h4>
                                <div className="flex flex-wrap gap-2">
                                  {flag.citations.map((citation, idx) => (
                                    <Badge key={idx} variant="outline" className="text-xs">
                                      <strong>{citation.type}:</strong> {citation.reference}
                                    </Badge>
                                  ))}
                                </div>
                              </div>
                            )}
                            {flag.context && (
                              <div className="pt-4 border-t">
                                <div
                                  className="flex justify-between items-center cursor-pointer mb-2"
                                  onClick={() => toggleContextExpanded(flag.id)}
                                >
                                  <h4 className="font-semibold">Context Used for Analysis</h4>
                                  {isContextExpanded ? (
                                    <ChevronUp className="h-5 w-5 text-muted-foreground" />
                                  ) : (
                                    <ChevronDown className="h-5 w-5 text-muted-foreground" />
                                  )}
                                </div>
                                {isContextExpanded && (
                                  <div className="mt-3 space-y-4 bg-muted/30 p-4 rounded-md">
                                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-sm">
                                      <div>
                                        <span className="text-muted-foreground">Total Tokens:</span>
                                        <strong className="ml-1">{flag.context.total_tokens}</strong>
                                      </div>
                                      <div>
                                        <span className="text-muted-foreground">Manual Chunks:</span>
                                        <strong className="ml-1">
                                          {flag.context.manual_neighbors_count}
                                        </strong>
                                      </div>
                                      <div>
                                        <span className="text-muted-foreground">Regulations:</span>
                                        <strong className="ml-1">
                                          {flag.context.regulation_slices_count}
                                        </strong>
                                      </div>
                                      <div>
                                        <span className="text-muted-foreground">Guidance:</span>
                                        <strong className="ml-1">
                                          {flag.context.guidance_slices_count}
                                        </strong>
                                      </div>
                                      <div>
                                        <span className="text-muted-foreground">Evidence:</span>
                                        <strong className="ml-1">
                                          {flag.context.evidence_slices_count}
                                        </strong>
                                      </div>
                                    </div>
                                    {flag.context.truncated && (
                                      <div className="text-yellow-600 font-semibold text-sm">
                                        ⚠️ Context Truncated
                                      </div>
                                    )}
                                    {/* Context details would go here - similar to Flask template */}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Auditor Questions */}
          {questions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Auditor Questions ({questions.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left p-2">Priority</th>
                        <th className="text-left p-2">Regulation</th>
                        <th className="text-left p-2">Question</th>
                        <th className="text-left p-2">Rationale</th>
                      </tr>
                    </thead>
                    <tbody>
                      {questions.map((question) => (
                        <tr key={question.question_id} className="border-b hover:bg-muted/50">
                          <td className="p-2">{question.priority}</td>
                          <td className="p-2">
                            <code className="text-xs">{question.regulation_reference}</code>
                          </td>
                          <td className="p-2">{question.question_text}</td>
                          <td className="p-2">{question.rationale || "N/A"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

      {/* Final Report Modal */}
      {showReportModal && reportData && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setShowReportModal(false)}
        >
          <div
            className="bg-background rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-bold">Final Compliance Report</h2>
                <Button variant="ghost" onClick={() => setShowReportModal(false)}>
                  ×
                </Button>
              </div>
              <div className="space-y-6">
                <div>
                  <h3 className="font-semibold mb-2">Executive Summary</h3>
                  <div className="bg-muted p-4 rounded-md whitespace-pre-wrap">
                    {reportData.executive_summary}
                  </div>
                </div>
                {reportData.critical_issues && reportData.critical_issues.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2 text-red-600">
                      Critical Issues ({reportData.critical_issues.length})
                    </h3>
                    {reportData.critical_issues.map((issue: any, idx: number) => (
                      <div key={idx} className="bg-red-50 border-l-4 border-red-500 p-4 rounded-md mb-3">
                        <h4 className="font-semibold mb-2">{idx + 1}. {issue.title}</h4>
                        <p className="mb-2">{issue.description}</p>
                        {issue.recommendations && issue.recommendations.length > 0 && (
                          <div>
                            <strong>Recommendations:</strong>
                            <ul className="list-disc list-inside mt-1">
                              {issue.recommendations.map((rec: string, i: number) => (
                                <li key={i}>{rec}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {reportData.warnings && reportData.warnings.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2 text-yellow-600">
                      Warnings ({reportData.warnings.length})
                    </h3>
                    {reportData.warnings.map((warning: any, idx: number) => (
                      <div
                        key={idx}
                        className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-md mb-3"
                      >
                        <h4 className="font-semibold mb-2">{idx + 1}. {warning.title}</h4>
                        <p className="mb-2">{warning.description}</p>
                        {warning.recommendations && warning.recommendations.length > 0 && (
                          <div>
                            <strong>Recommendations:</strong>
                            <ul className="list-disc list-inside mt-1">
                              {warning.recommendations.map((rec: string, i: number) => (
                                <li key={i}>{rec}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {reportData.recommendations && reportData.recommendations.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2">Prioritized Recommendations</h3>
                    <ol className="list-decimal list-inside space-y-2">
                      {reportData.recommendations.map((rec: string, i: number) => (
                        <li key={i}>{rec}</li>
                      ))}
                    </ol>
                  </div>
                )}
                <div>
                  <h3 className="font-semibold mb-2">Overall Assessment</h3>
                  <div className="bg-muted p-4 rounded-md whitespace-pre-wrap">
                    {reportData.overall_assessment}
                  </div>
                </div>
              </div>
              <div className="flex gap-2 justify-end mt-6 pt-4 border-t">
                <Button variant="outline" onClick={() => setShowReportModal(false)}>
                  Close
                </Button>
                <Button variant="outline" onClick={() => downloadReport('json')}>
                  <FileDown className="mr-2 h-4 w-4" />
                  JSON
                </Button>
                <Button variant="outline" onClick={() => downloadReport('pdf')}>
                  <FileDown className="mr-2 h-4 w-4" />
                  PDF
                </Button>
                <Button variant="outline" onClick={() => downloadReport('docx')}>
                  <FileDown className="mr-2 h-4 w-4" />
                  Word
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
