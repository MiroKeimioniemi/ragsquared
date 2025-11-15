"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText, Shield, Zap, TrendingUp, CheckCircle2, AlertTriangle, Info, Layers, Brain, Target } from "lucide-react";
import Link from "next/link";

export default function HomePage() {
  return (
    <div className="flex flex-col">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-primary/10 via-background to-primary/5 py-20 px-4">
        <div className="container mx-auto max-w-6xl">
          <div className="flex flex-col items-center text-center space-y-8">
            <div className="space-y-4">
              <div className="inline-flex items-center justify-center px-4 py-2 rounded-full bg-primary/10 text-primary text-sm font-semibold mb-4">
                Proprietary Recursive RAG Technology
              </div>
              <h1 className="text-5xl font-bold tracking-tight sm:text-6xl md:text-7xl">
                rag<span className="text-primary">²</span>
              </h1>
              <p className="mx-auto max-w-2xl text-2xl font-semibold text-foreground">
                Enterprise Compliance Auditing
                <span className="block text-xl font-normal text-muted-foreground mt-2">
                  Powered by recursive RAG where RAG meets RAG, and your agent gets more RAG
                </span>
              </p>
              <p className="mx-auto max-w-3xl text-lg text-muted-foreground mt-4">
                Transform your compliance operations with our proprietary recursive retrieval architecture. 
                Unlike traditional RAG systems, rag² performs RAG on RAG, recursively expanding context 
                through reference chains, litigation analysis, and multi-level document traversal. 
                Your AI agent doesn't just retrieve information. It builds comprehensive understanding.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-4">
              <Link href="/upload">
                <Button size="lg" className="text-lg px-8 py-6">
                  <FileText className="mr-2 h-5 w-5" />
                  Start Your First Audit
                </Button>
              </Link>
              <Link href="/dashboard">
                <Button size="lg" variant="outline" className="text-lg px-8 py-6">
                  View Dashboard
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* What Makes Us Special Section */}
      <section className="py-20 px-4 bg-background">
        <div className="container mx-auto max-w-6xl">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold tracking-tight mb-4">What Makes rag² Different</h2>
            <p className="text-muted-foreground text-xl max-w-3xl mx-auto">
              Our proprietary recursive RAG architecture delivers enterprise-grade compliance intelligence
            </p>
          </div>
          <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3 mb-12">
            <Card className="border-2">
              <CardHeader>
                <Layers className="h-12 w-12 text-primary mb-4" />
                <CardTitle className="text-2xl">RAG on RAG</CardTitle>
                <CardDescription className="text-base">
                  Our system doesn't stop at initial retrieval. When your documents reference other sections, 
                  regulations, or guidance materials, we perform RAG again on those references, and recursively 
                  on their references. This creates a comprehensive knowledge graph that traditional RAG systems miss.
                </CardDescription>
              </CardHeader>
            </Card>
            <Card className="border-2">
              <CardHeader>
                <Brain className="h-12 w-12 text-primary mb-4" />
                <CardTitle className="text-2xl">Enhanced Agent RAG</CardTitle>
                <CardDescription className="text-base">
                  Your AI agent doesn't just receive static context. It has access to expanded RAG capabilities 
                  that dynamically retrieve related litigation, cross-reference regulations, and traverse document 
                  hierarchies. The agent sees the full picture, not just isolated chunks.
                </CardDescription>
              </CardHeader>
            </Card>
            <Card className="border-2">
              <CardHeader>
                <Target className="h-12 w-12 text-primary mb-4" />
                <CardTitle className="text-2xl">Multi-Level Context</CardTitle>
                <CardDescription className="text-base">
                  While competitors analyze documents in isolation, rag² builds context across multiple levels: 
                  base regulations, referenced sections, related litigation, and cross-document relationships. 
                  This depth of understanding catches compliance issues that surface only when documents are 
                  analyzed together.
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
          <div className="bg-muted/50 rounded-lg p-8 border-2 border-primary/20">
            <h3 className="text-2xl font-bold mb-4 text-center">The rag² Advantage</h3>
            <div className="grid md:grid-cols-2 gap-6 text-left">
              <div>
                <h4 className="font-semibold text-lg mb-2">Traditional RAG</h4>
                <ul className="space-y-2 text-muted-foreground">
                  <li className="flex items-start">
                    <span className="text-destructive mr-2">×</span>
                    <span>Single-pass retrieval</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-destructive mr-2">×</span>
                    <span>Isolated document analysis</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-destructive mr-2">×</span>
                    <span>Misses cross-references</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-destructive mr-2">×</span>
                    <span>Limited context depth</span>
                  </li>
                </ul>
              </div>
              <div>
                <h4 className="font-semibold text-lg mb-2">rag² Recursive RAG</h4>
                <ul className="space-y-2 text-muted-foreground">
                  <li className="flex items-start">
                    <span className="text-primary mr-2">✓</span>
                    <span>Multi-level recursive retrieval</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-primary mr-2">✓</span>
                    <span>Comprehensive document relationships</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-primary mr-2">✓</span>
                    <span>Automatic reference traversal</span>
                  </li>
                  <li className="flex items-start">
                    <span className="text-primary mr-2">✓</span>
                    <span>Deep context with litigation insights</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-4 bg-muted/30">
        <div className="container mx-auto max-w-6xl">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold tracking-tight mb-4">Enterprise-Grade Features</h2>
            <p className="text-muted-foreground text-lg">
              Built for compliance teams who need accuracy, depth, and actionable insights
            </p>
          </div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <Shield className="h-10 w-10 text-primary mb-4" />
                <CardTitle>Automated Compliance Checks</CardTitle>
                <CardDescription>
                  AI analyzes your documents against regulatory requirements automatically
                </CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <Zap className="h-10 w-10 text-primary mb-4" />
                <CardTitle>Real-Time Processing</CardTitle>
                <CardDescription>
                  Get instant feedback as your documents are processed and analyzed
                </CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <TrendingUp className="h-10 w-10 text-primary mb-4" />
                <CardTitle>Compliance Scoring</CardTitle>
                <CardDescription>
                  Track your compliance score and identify areas for improvement
                </CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <FileText className="h-10 w-10 text-primary mb-4" />
                <CardTitle>Detailed Reports</CardTitle>
                <CardDescription>
                  Generate comprehensive audit reports with findings and recommendations
                </CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <AlertTriangle className="h-10 w-10 text-primary mb-4" />
                <CardTitle>Flag Management</CardTitle>
                <CardDescription>
                  Categorize and prioritize compliance flags by severity (Critical, Warning, Info)
                </CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <Info className="h-10 w-10 text-primary mb-4" />
                <CardTitle>Regulatory Context</CardTitle>
                <CardDescription>
                  Understand the regulatory basis for each finding with citations
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-20 px-4 bg-muted/50">
        <div className="container mx-auto max-w-6xl">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold tracking-tight mb-4">How It Works</h2>
            <p className="text-muted-foreground text-lg">
              Simple steps to get started with AI-powered auditing
            </p>
          </div>
          <div className="grid gap-8 md:grid-cols-3">
            <div className="flex flex-col items-center text-center space-y-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary text-primary-foreground text-2xl font-bold">
                1
              </div>
              <h3 className="text-xl font-semibold">Upload Document</h3>
              <p className="text-muted-foreground">
                Upload your compliance documents in PDF, DOCX, or other supported formats
              </p>
            </div>
            <div className="flex flex-col items-center text-center space-y-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary text-primary-foreground text-2xl font-bold">
                2
              </div>
              <h3 className="text-xl font-semibold">AI Analysis</h3>
              <p className="text-muted-foreground">
                Our AI system processes and analyzes your document against regulatory requirements
              </p>
            </div>
            <div className="flex flex-col items-center text-center space-y-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary text-primary-foreground text-2xl font-bold">
                3
              </div>
              <h3 className="text-xl font-semibold">Review Results</h3>
              <p className="text-muted-foreground">
                Review detailed findings, compliance scores, and actionable recommendations
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4 bg-primary text-primary-foreground">
        <div className="container mx-auto max-w-4xl text-center space-y-8">
          <h2 className="text-4xl font-bold">Experience the rag² Difference</h2>
          <p className="text-xl opacity-90">
            See how recursive RAG technology delivers deeper insights and more accurate compliance analysis
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/upload">
              <Button size="lg" variant="secondary" className="text-lg px-8 py-6">
                <FileText className="mr-2 h-5 w-5" />
                Start Free Trial
              </Button>
            </Link>
            <Link href="/dashboard">
              <Button size="lg" variant="outline" className="text-lg px-8 py-6 border-primary-foreground/20 text-primary-foreground hover:bg-primary-foreground/10">
                Schedule Demo
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

