"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, type AuditWithDetails } from "@/lib/api";
import Link from "next/link";
import { FileText, Upload, RefreshCw, CheckCircle2, XCircle, Clock } from "lucide-react";
import { format } from "date-fns";

export default function DashboardPage() {
  const [audits, setAudits] = useState<AuditWithDetails[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [draftFilter, setDraftFilter] = useState<string>("all");

  const loadAudits = async () => {
    setLoading(true);
    try {
      const filters: any = {};
      if (statusFilter && statusFilter !== "all") filters.status = statusFilter;
      if (draftFilter && draftFilter !== "all") filters.is_draft = draftFilter;
      const data = await api.audits.list(filters);
      setAudits(data);
    } catch (error) {
      console.error("Failed to load audits:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAudits();
    const interval = setInterval(loadAudits, 5000);
    return () => clearInterval(interval);
  }, [statusFilter, draftFilter]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return <Badge variant="success">COMPLETED</Badge>;
      case "running":
        return <Badge variant="warning">RUNNING</Badge>;
      case "failed":
        return <Badge variant="danger">FAILED</Badge>;
      default:
        return <Badge variant="warning">QUEUED</Badge>;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="h-5 w-5 text-green-500" />;
      case "failed":
        return <XCircle className="h-5 w-5 text-red-500" />;
      case "running":
        return <RefreshCw className="h-5 w-5 text-yellow-500 animate-spin" />;
      default:
        return <Clock className="h-5 w-5 text-gray-500" />;
    }
  };

  return (
    <div className="container mx-auto py-8 px-4 max-w-7xl">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 gap-4">
        <div>
          <h1 className="text-4xl font-bold tracking-tight mb-2">Audit Dashboard</h1>
          <p className="text-muted-foreground">Manage and monitor your compliance audits</p>
        </div>
        <Link href="/upload">
          <Button>
            <Upload className="mr-2 h-4 w-4" />
            Upload Document
          </Button>
        </Link>
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Filters</CardTitle>
          <CardDescription>Filter audits by status and type</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <label className="text-sm font-medium mb-2 block">Status</label>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="All Statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="queued">Queued</SelectItem>
                  <SelectItem value="running">Running</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex-1">
              <label className="text-sm font-medium mb-2 block">Type</label>
              <Select value={draftFilter} onValueChange={setDraftFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="All Types" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="false">Full Audit</SelectItem>
                  <SelectItem value="true">Draft</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end">
              <Button
                variant="outline"
                onClick={() => {
                  setStatusFilter("all");
                  setDraftFilter("all");
                }}
              >
                Clear Filters
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Audit List */}
      {loading ? (
        <div className="text-center py-12">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">Loading audits...</p>
        </div>
      ) : audits.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FileText className="h-16 w-16 text-muted-foreground mb-4" />
            <h3 className="text-xl font-semibold mb-2">No audits found</h3>
            <p className="text-muted-foreground mb-6 text-center">
              Get started by uploading a document and creating your first audit.
            </p>
            <Link href="/upload">
              <Button>
                <Upload className="mr-2 h-4 w-4" />
                Upload Document
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6">
          {audits.map((audit) => (
            <Card
              key={audit.id}
              className="hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => (window.location.href = `/review/${audit.external_id}`)}
            >
              <CardHeader>
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      {getStatusIcon(audit.status)}
                      <CardTitle className="text-xl">
                        {audit.document?.original_filename || audit.external_id}
                      </CardTitle>
                      {audit.is_draft && <Badge variant="warning">DRAFT</Badge>}
                    </div>
                    <CardDescription className="text-sm">
                      <FileText className="inline h-4 w-4 mr-1" />
                      ID: {audit.external_id}
                      {audit.document && (
                        <span className="text-muted-foreground"> • {audit.document.original_filename}</span>
                      )}
                    </CardDescription>
                    <p className="text-sm text-muted-foreground mt-2">
                      Created: {format(new Date(audit.created_at), "PPpp")}
                    </p>
                  </div>
                  <div>{getStatusBadge(audit.status)}</div>
                </div>
              </CardHeader>
              <CardContent>
                {(audit.status === "running" || audit.status === "queued") && (
                  <div className="mb-4">
                    <div className="flex justify-between text-sm mb-2">
                      <span className="text-muted-foreground">
                        Processing: {audit.chunk_completed} / {audit.chunk_total} chunks
                      </span>
                      {audit.chunk_total > 0 && (
                        <span className="text-muted-foreground">
                          {Math.round((audit.chunk_completed / audit.chunk_total) * 100)}%
                        </span>
                      )}
                    </div>
                    {audit.chunk_total > 0 && (
                      <Progress
                        value={(audit.chunk_completed / audit.chunk_total) * 100}
                        className="h-2"
                      />
                    )}
                  </div>
                )}

                {audit.status === "completed" && audit.flag_summary && (
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 mb-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-primary">
                        {audit.flag_summary.compliance_score}
                      </div>
                      <div className="text-xs text-muted-foreground">Score</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold">{audit.flag_summary.total_flags}</div>
                      <div className="text-xs text-muted-foreground">Total Flags</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-red-500">
                        {audit.flag_summary.red_count}
                      </div>
                      <div className="text-xs text-muted-foreground">Critical</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-yellow-500">
                        {audit.flag_summary.yellow_count}
                      </div>
                      <div className="text-xs text-muted-foreground">Warning</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-500">
                        {audit.flag_summary.green_count}
                      </div>
                      <div className="text-xs text-muted-foreground">Info</div>
                    </div>
                  </div>
                )}

                <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                  <Link href={`/review/${audit.external_id}`} className="flex-1">
                    <Button className="w-full" variant="default">
                      View Details
                    </Button>
                  </Link>
                  {audit.status === "completed" && (
                    <a
                      href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'}/api/audits/${audit.external_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Button variant="outline">API JSON</Button>
                    </a>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

