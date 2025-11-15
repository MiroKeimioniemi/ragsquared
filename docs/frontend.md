# Frontend Development Guide

This document provides comprehensive guidance for building a beautiful, modern frontend for the AI Auditing System. It covers architecture decisions, design principles, implementation patterns, and best practices for creating an exceptional user experience.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture & Technology Stack](#architecture--technology-stack)
3. [Design System](#design-system)
4. [Component Architecture](#component-architecture)
5. [API Integration](#api-integration)
6. [User Experience Patterns](#user-experience-patterns)
7. [Performance Optimization](#performance-optimization)
8. [Accessibility](#accessibility)
9. [Testing Strategy](#testing-strategy)
10. [Deployment & Build](#deployment--build)

---

## Overview

### Goals

The frontend should provide:

- **Intuitive Navigation**: Easy access to audits, findings, and reports
- **Real-time Feedback**: Live updates on audit progress and status
- **Visual Clarity**: Clear presentation of compliance flags, scores, and recommendations
- **Responsive Design**: Seamless experience across desktop, tablet, and mobile devices
- **Accessibility**: WCAG 2.1 AA compliance for inclusive design
- **Performance**: Fast load times and smooth interactions

### Current State

The system currently includes:

- **Basic Review UI**: Flask-based Jinja templates at `/review/<audit-id>`
- **Static HTML Reports**: Pre-rendered reports in `data/reports/html/`
- **RESTful API**: Complete backend API for all audit operations
- **Developer CLI**: Command-line interface for power users

### Target Architecture

The recommended frontend architecture supports:

- **Progressive Enhancement**: Start with server-rendered templates, enhance with JavaScript
- **Component Reusability**: Shared components for flags, citations, and statistics
- **State Management**: Efficient handling of audit data and filters
- **Real-time Updates**: WebSocket or polling for live audit progress

---

## Architecture & Technology Stack

### Recommended Stack Options

#### Option 1: Modern React SPA (Recommended for Full-Featured UI)

**Stack:**
- **Framework**: React 18+ with TypeScript
- **Build Tool**: Vite or Next.js (for SSR/SSG)
- **State Management**: React Query (TanStack Query) for server state, Zustand for client state
- **Styling**: Tailwind CSS + Headless UI or shadcn/ui components
- **Routing**: React Router v6
- **Forms**: React Hook Form + Zod validation
- **Charts**: Recharts or Chart.js for compliance score visualizations

**Pros:**
- Rich interactivity and smooth user experience
- Excellent component ecosystem
- Strong TypeScript support
- Modern development tooling

**Cons:**
- Requires build step and deployment pipeline
- More complex initial setup

#### Option 2: Server-Side Rendered (SSR) with HTMX/Alpine.js

**Stack:**
- **Framework**: Flask + Jinja2 templates (existing)
- **Enhancement**: HTMX for dynamic updates, Alpine.js for interactivity
- **Styling**: Tailwind CSS (via CDN or build)
- **Charts**: Chart.js or lightweight SVG-based solutions

**Pros:**
- Minimal JavaScript, fast initial load
- Works with existing Flask backend
- Progressive enhancement approach
- Easy to maintain and deploy

**Cons:**
- Less interactive than SPA
- Limited offline capabilities

#### Option 3: Hybrid Approach (Recommended for MVP)

**Stack:**
- **Base**: Flask + Jinja2 templates (keep existing review UI)
- **Enhancement**: Alpine.js for interactivity, HTMX for dynamic updates
- **New Pages**: React components for complex views (audit dashboard, comparison tool)
- **Styling**: Tailwind CSS with custom design system

**Pros:**
- Leverages existing infrastructure
- Gradual migration path
- Best of both worlds

**Cons:**
- Requires managing two rendering approaches

### Recommendation

For a hackathon or MVP, start with **Option 2** (HTMX/Alpine.js) to quickly enhance the existing templates. For a production system, migrate to **Option 1** (React SPA) for maximum flexibility and user experience.

---

## Design System

### Color Palette

```css
/* Primary Colors */
--color-primary: #2c3e50;      /* Dark blue-gray for headers */
--color-primary-light: #3498db; /* Blue for actions */
--color-primary-dark: #1a252f;   /* Darker variant */

/* Severity Colors */
--color-red: #dc3545;           /* Critical issues */
--color-red-light: #fee;        /* Red background */
--color-red-border: #fcc;        /* Red border */

--color-yellow: #ffc107;        /* Warnings */
--color-yellow-light: #ffd;     /* Yellow background */
--color-yellow-border: #ffc;    /* Yellow border */

--color-green: #28a745;         /* Compliant */
--color-green-light: #efe;      /* Green background */
--color-green-border: #cfc;     /* Green border */

/* Neutral Colors */
--color-gray-50: #f8f9fa;
--color-gray-100: #e9ecef;
--color-gray-200: #dee2e6;
--color-gray-300: #ced4da;
--color-gray-600: #6c757d;
--color-gray-800: #343a40;
--color-gray-900: #212529;

/* Semantic Colors */
--color-success: #28a745;
--color-warning: #ffc107;
--color-danger: #dc3545;
--color-info: #17a2b8;
```

### Typography

```css
/* Font Stack */
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 
             'Helvetica Neue', Arial, sans-serif;

/* Scale */
--font-size-xs: 0.75rem;    /* 12px */
--font-size-sm: 0.875rem;    /* 14px */
--font-size-base: 1rem;      /* 16px */
--font-size-lg: 1.125rem;    /* 18px */
--font-size-xl: 1.25rem;     /* 20px */
--font-size-2xl: 1.5rem;     /* 24px */
--font-size-3xl: 1.875rem;   /* 30px */
--font-size-4xl: 2.25rem;    /* 36px */

/* Weights */
--font-weight-normal: 400;
--font-weight-medium: 500;
--font-weight-semibold: 600;
--font-weight-bold: 700;
```

### Spacing System

Use a consistent 4px base unit:

```css
--spacing-1: 0.25rem;  /* 4px */
--spacing-2: 0.5rem;   /* 8px */
--spacing-3: 0.75rem;  /* 12px */
--spacing-4: 1rem;     /* 16px */
--spacing-5: 1.25rem;  /* 20px */
--spacing-6: 1.5rem;   /* 24px */
--spacing-8: 2rem;     /* 32px */
--spacing-10: 2.5rem;  /* 40px */
--spacing-12: 3rem;    /* 48px */
```

### Component Styles

#### Cards

```css
.card {
  background: white;
  border-radius: 0.5rem;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  transition: box-shadow 0.2s ease;
}

.card:hover {
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}
```

#### Badges

```css
.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.75rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.badge-red {
  background-color: var(--color-red-light);
  color: var(--color-red);
  border: 1px solid var(--color-red-border);
}

.badge-yellow {
  background-color: var(--color-yellow-light);
  color: #856404;
  border: 1px solid var(--color-yellow-border);
}

.badge-green {
  background-color: var(--color-green-light);
  color: var(--color-green);
  border: 1px solid var(--color-green-border);
}
```

#### Buttons

```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  text-decoration: none;
}

.btn-primary {
  background-color: var(--color-primary-light);
  color: white;
}

.btn-primary:hover {
  background-color: #2980b9;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}
```

---

## Component Architecture

### Core Components

#### 1. Audit Dashboard

**Purpose**: Overview of all audits with status, scores, and quick actions.

**Features**:
- List of audits with filtering and sorting
- Status indicators (queued, running, completed, failed)
- Compliance score badges
- Quick actions (view, download report, compare)
- Real-time progress updates

**Example Structure**:
```html
<div class="audit-dashboard">
  <div class="dashboard-header">
    <h1>Audits</h1>
    <button class="btn btn-primary">New Audit</button>
  </div>
  
  <div class="filters">
    <!-- Filter controls -->
  </div>
  
  <div class="audit-list">
    <!-- Audit cards -->
  </div>
</div>
```

#### 2. Audit Detail View

**Purpose**: Comprehensive view of a single audit with all findings.

**Features**:
- Summary statistics (score, flag counts)
- Progress indicator
- Filterable flag table
- Detailed flag information with expand/collapse
- Citations and recommendations
- Auditor questions
- Export options (PDF, Markdown, JSON)

**Enhancement Ideas**:
- Side-by-side comparison with previous audit
- Timeline visualization of audit progress
- Interactive regulation reference links
- Highlighted text matching in chunk content

#### 3. Flag Component

**Purpose**: Display individual compliance flags with all details.

**Structure**:
```html
<div class="flag-card" data-severity="RED">
  <div class="flag-header">
    <span class="badge badge-red">RED</span>
    <span class="flag-score">85/100</span>
    <span class="flag-chunk-id">Chunk: doc_123_4_2</span>
  </div>
  
  <div class="flag-content">
    <h3>Findings</h3>
    <p>{{ findings }}</p>
    
    <div class="flag-gaps" v-if="gaps.length">
      <h4>Gaps Identified</h4>
      <ul>
        <li v-for="gap in gaps">{{ gap }}</li>
      </ul>
    </div>
    
    <div class="flag-recommendations" v-if="recommendations.length">
      <h4>Recommendations</h4>
      <ul>
        <li v-for="rec in recommendations">{{ rec }}</li>
      </ul>
    </div>
    
    <div class="flag-citations">
      <h4>Citations</h4>
      <div class="citations-list">
        <!-- Citation badges -->
      </div>
    </div>
  </div>
</div>
```

#### 4. Compliance Score Visualization

**Purpose**: Visual representation of compliance scores and trends.

**Options**:
- **Gauge Chart**: Circular gauge showing overall score
- **Bar Chart**: Breakdown by severity (RED/YELLOW/GREEN)
- **Line Chart**: Historical trend over multiple audits
- **Heatmap**: Compliance by regulation section

**Example with Recharts**:
```jsx
<ResponsiveContainer width="100%" height={300}>
  <PieChart>
    <Pie
      data={[
        { name: 'RED', value: redCount, fill: '#dc3545' },
        { name: 'YELLOW', value: yellowCount, fill: '#ffc107' },
        { name: 'GREEN', value: greenCount, fill: '#28a745' }
      ]}
      cx="50%"
      cy="50%"
      labelLine={false}
      label={renderCustomLabel}
      outerRadius={80}
      fill="#8884d8"
      dataKey="value"
    />
  </PieChart>
</ResponsiveContainer>
```

#### 5. Filter Panel

**Purpose**: Advanced filtering for flags and audits.

**Filters**:
- Severity (RED/YELLOW/GREEN)
- Regulation reference
- Date range
- Organization
- Draft vs. Full audits
- Score range

**Implementation**:
```html
<div class="filter-panel">
  <h3>Filters</h3>
  
  <div class="filter-group">
    <label>Severity</label>
    <select name="severity" hx-get="/api/flags" hx-target="#flags-list">
      <option value="">All</option>
      <option value="RED">RED</option>
      <option value="YELLOW">YELLOW</option>
      <option value="GREEN">GREEN</option>
    </select>
  </div>
  
  <!-- More filters -->
  
  <button class="btn btn-secondary" onclick="clearFilters()">
    Clear Filters
  </button>
</div>
```

#### 6. Progress Indicator

**Purpose**: Show audit processing progress.

**Features**:
- Progress bar with percentage
- Chunk count (processed/total)
- Estimated time remaining
- Status messages
- Cancel button (if supported)

**Example**:
```html
<div class="progress-card">
  <div class="progress-header">
    <h3>Processing Audit</h3>
    <span class="status-badge">Running</span>
  </div>
  
  <div class="progress-bar">
    <div class="progress-fill" style="width: 65%"></div>
  </div>
  
  <div class="progress-stats">
    <span>65 / 100 chunks processed</span>
    <span>~5 minutes remaining</span>
  </div>
</div>
```

---

## API Integration

### API Endpoints Reference

The backend provides the following RESTful endpoints:

#### Audits

```javascript
// List audits
GET /api/audits
Query params: ?status=completed&organization=ACME

// Get audit details
GET /api/audits/{audit_id}

// Create audit
POST /api/audits
Body: { document_id: "123", is_draft: false }

// Get audit status
GET /api/audits/{audit_id}/status
```

#### Flags

```javascript
// List flags for an audit
GET /api/audits/{audit_id}/flags
Query params: ?severity=RED&regulation=Part-145.A.30&page=1&page_size=20

// Get flag details
GET /api/flags/{flag_id}
```

#### Reports

```javascript
// Generate report
POST /api/audits/{audit_id}/reports
Body: { format: "pdf" }

// Download report
GET /api/reports/{report_id}/download
```

#### Scores

```javascript
// Get compliance scores
GET /api/scores
Query params: ?organization=ACME&limit=10

// Get score history
GET /api/organizations/{org_id}/scores
```

### API Client Implementation

#### Using Fetch API

```javascript
class AuditAPI {
  constructor(baseURL = '/api') {
    this.baseURL = baseURL;
  }

  async getAudits(filters = {}) {
    const params = new URLSearchParams(filters);
    const response = await fetch(`${this.baseURL}/audits?${params}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async getAudit(auditId) {
    const response = await fetch(`${this.baseURL}/audits/${auditId}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async getFlags(auditId, filters = {}) {
    const params = new URLSearchParams(filters);
    const response = await fetch(
      `${this.baseURL}/audits/${auditId}/flags?${params}`
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async createAudit(documentId, isDraft = false) {
    const response = await fetch(`${this.baseURL}/audits`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ document_id: documentId, is_draft: isDraft }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
}
```

#### Using React Query (TanStack Query)

```jsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

function useAudits(filters = {}) {
  return useQuery({
    queryKey: ['audits', filters],
    queryFn: async () => {
      const params = new URLSearchParams(filters);
      const res = await fetch(`/api/audits?${params}`);
      if (!res.ok) throw new Error('Failed to fetch audits');
      return res.json();
    },
  });
}

function useCreateAudit() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ documentId, isDraft }) => {
      const res = await fetch('/api/audits', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_id: documentId, is_draft: isDraft }),
      });
      if (!res.ok) throw new Error('Failed to create audit');
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['audits']);
    },
  });
}
```

### Error Handling

```javascript
async function handleAPIError(response) {
  if (!response.ok) {
    const error = await response.json().catch(() => ({
      message: `HTTP ${response.status}: ${response.statusText}`,
    }));
    throw new Error(error.message || 'An error occurred');
  }
  return response.json();
}

// Usage
try {
  const data = await fetch('/api/audits/123')
    .then(handleAPIError);
} catch (error) {
  showNotification(error.message, 'error');
}
```

---

## User Experience Patterns

### 1. Loading States

Always show loading indicators for async operations:

```html
<!-- Skeleton loader -->
<div class="skeleton-card">
  <div class="skeleton-line" style="width: 60%"></div>
  <div class="skeleton-line" style="width: 100%"></div>
  <div class="skeleton-line" style="width: 80%"></div>
</div>
```

```css
.skeleton-line {
  height: 1rem;
  background: linear-gradient(
    90deg,
    #f0f0f0 25%,
    #e0e0e0 50%,
    #f0f0f0 75%
  );
  background-size: 200% 100%;
  animation: loading 1.5s infinite;
  border-radius: 0.25rem;
  margin-bottom: 0.5rem;
}

@keyframes loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

### 2. Empty States

Provide helpful empty states when no data is available:

```html
<div class="empty-state">
  <svg class="empty-icon" width="64" height="64">
    <!-- Icon SVG -->
  </svg>
  <h3>No audits found</h3>
  <p>Get started by creating your first audit.</p>
  <button class="btn btn-primary">Create Audit</button>
</div>
```

### 3. Toast Notifications

Show success/error messages for user actions:

```javascript
function showNotification(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  
  setTimeout(() => toast.classList.add('show'), 100);
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}
```

### 4. Confirmation Dialogs

Use for destructive actions:

```html
<div class="modal" id="confirm-dialog">
  <div class="modal-content">
    <h3>Confirm Action</h3>
    <p>Are you sure you want to delete this audit?</p>
    <div class="modal-actions">
      <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn btn-danger" onclick="confirmDelete()">Delete</button>
    </div>
  </div>
</div>
```

### 5. Progressive Disclosure

Show summary first, details on demand:

```html
<div class="flag-summary" onclick="toggleDetails(this)">
  <div class="summary-header">
    <span class="badge badge-red">RED</span>
    <span class="flag-title">Missing Personnel Qualifications</span>
    <span class="expand-icon">▼</span>
  </div>
  <div class="flag-details" style="display: none;">
    <!-- Full details -->
  </div>
</div>
```

### 6. Keyboard Navigation

Support keyboard shortcuts:

```javascript
document.addEventListener('keydown', (e) => {
  // Cmd/Ctrl + K for search
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    openSearch();
  }
  
  // Escape to close modals
  if (e.key === 'Escape') {
    closeAllModals();
  }
});
```

---

## Performance Optimization

### 1. Code Splitting

Split JavaScript bundles by route:

```javascript
// React Router
const AuditDashboard = lazy(() => import('./pages/AuditDashboard'));
const AuditDetail = lazy(() => import('./pages/AuditDetail'));

// Usage
<Suspense fallback={<Loading />}>
  <Routes>
    <Route path="/" element={<AuditDashboard />} />
    <Route path="/audits/:id" element={<AuditDetail />} />
  </Routes>
</Suspense>
```

### 2. Image Optimization

- Use WebP format with fallbacks
- Implement lazy loading
- Provide responsive images

```html
<picture>
  <source srcset="image.webp" type="image/webp">
  <img src="image.jpg" alt="Description" loading="lazy">
</picture>
```

### 3. Caching Strategy

```javascript
// Service Worker for offline support
self.addEventListener('fetch', (event) => {
  if (event.request.url.includes('/api/audits')) {
    event.respondWith(
      caches.open('audits-v1').then((cache) => {
        return fetch(event.request).then((response) => {
          cache.put(event.request, response.clone());
          return response;
        });
      })
    );
  }
});
```

### 4. Virtual Scrolling

For long lists of flags:

```jsx
import { FixedSizeList } from 'react-window';

function FlagList({ flags }) {
  return (
    <FixedSizeList
      height={600}
      itemCount={flags.length}
      itemSize={100}
      width="100%"
    >
      {({ index, style }) => (
        <div style={style}>
          <FlagCard flag={flags[index]} />
        </div>
      )}
    </FixedSizeList>
  );
}
```

### 5. Debouncing Search

```javascript
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

const searchInput = document.getElementById('search');
searchInput.addEventListener('input', debounce(handleSearch, 300));
```

---

## Accessibility

### 1. Semantic HTML

```html
<main>
  <header>
    <h1>Audit Dashboard</h1>
    <nav aria-label="Main navigation">
      <!-- Navigation items -->
    </nav>
  </header>
  
  <section aria-labelledby="audits-heading">
    <h2 id="audits-heading">Recent Audits</h2>
    <!-- Audit list -->
  </section>
</main>
```

### 2. ARIA Labels

```html
<button
  aria-label="Delete audit"
  aria-describedby="delete-help"
  onclick="deleteAudit()"
>
  <span aria-hidden="true">🗑️</span>
</button>
<span id="delete-help" class="sr-only">
  Permanently delete this audit
</span>
```

### 3. Keyboard Navigation

Ensure all interactive elements are keyboard accessible:

```css
.focusable:focus {
  outline: 2px solid var(--color-primary-light);
  outline-offset: 2px;
}

/* Skip link for keyboard users */
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: var(--color-primary);
  color: white;
  padding: 8px;
  z-index: 100;
}

.skip-link:focus {
  top: 0;
}
```

### 4. Color Contrast

Ensure WCAG AA compliance (4.5:1 for normal text, 3:1 for large text):

```css
/* Good contrast */
.text-primary {
  color: #2c3e50; /* Contrast ratio: 12.6:1 on white */
}

/* Avoid low contrast */
.text-bad {
  color: #999; /* Contrast ratio: 2.8:1 - too low */
}
```

### 5. Screen Reader Support

```html
<div role="status" aria-live="polite" aria-atomic="true" class="sr-only">
  Audit processing complete. 100 chunks analyzed.
</div>
```

---

## Testing Strategy

### 1. Unit Tests

Test individual components:

```javascript
// Jest + React Testing Library
import { render, screen } from '@testing-library/react';
import FlagCard from './FlagCard';

test('renders flag with correct severity', () => {
  const flag = { flag_type: 'RED', findings: 'Test finding' };
  render(<FlagCard flag={flag} />);
  expect(screen.getByText('RED')).toBeInTheDocument();
});
```

### 2. Integration Tests

Test API integration:

```javascript
// Mock API responses
global.fetch = jest.fn(() =>
  Promise.resolve({
    json: () => Promise.resolve({ audits: [] }),
  })
);

test('loads audits on mount', async () => {
  render(<AuditDashboard />);
  await waitFor(() => {
    expect(fetch).toHaveBeenCalledWith('/api/audits');
  });
});
```

### 3. E2E Tests

Use Playwright or Cypress:

```javascript
// Playwright
test('create and view audit', async ({ page }) => {
  await page.goto('/');
  await page.click('text=New Audit');
  await page.fill('[name="document_id"]', '123');
  await page.click('button[type="submit"]');
  await expect(page.locator('.audit-card')).toBeVisible();
});
```

### 4. Visual Regression Tests

Use tools like Percy or Chromatic:

```javascript
// Storybook + Chromatic
export default {
  title: 'Components/FlagCard',
  component: FlagCard,
};

export const RedFlag = {
  args: {
    flag: { flag_type: 'RED', findings: 'Critical issue' },
  },
};
```

---

## Deployment & Build

### Development Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Build Configuration

#### Vite Example

```javascript
// vite.config.js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router'],
          charts: ['recharts'],
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
});
```

### Production Deployment

#### Option 1: Static Hosting (Vercel, Netlify)

```bash
# Build static files
npm run build

# Deploy to Vercel
vercel --prod

# Or Netlify
netlify deploy --prod --dir=dist
```

#### Option 2: Flask Integration

Serve built files from Flask:

```python
# backend/app/__init__.py
from flask import Flask, send_from_directory

app = Flask(__name__, static_folder='../frontend/dist', static_url_path='')

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)
```

### Environment Variables

```bash
# .env
VITE_API_BASE_URL=http://localhost:5000/api
VITE_WS_URL=ws://localhost:5000/ws
VITE_ENABLE_ANALYTICS=false
```

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1)

- [ ] Set up build tooling (Vite/Next.js)
- [ ] Implement design system (colors, typography, components)
- [ ] Create base layout and navigation
- [ ] Set up API client and error handling
- [ ] Implement authentication (if needed)

### Phase 2: Core Features (Week 2)

- [ ] Audit dashboard with list view
- [ ] Audit detail page with flag display
- [ ] Filtering and search functionality
- [ ] Compliance score visualizations
- [ ] Progress indicators for running audits

### Phase 3: Enhanced UX (Week 3)

- [ ] Real-time updates (WebSocket or polling)
- [ ] Advanced filtering and sorting
- [ ] Export functionality (PDF, JSON)
- [ ] Comparison view for multiple audits
- [ ] Responsive mobile design

### Phase 4: Polish (Week 4)

- [ ] Accessibility audit and fixes
- [ ] Performance optimization
- [ ] Error handling and edge cases
- [ ] User testing and feedback
- [ ] Documentation and deployment

---

## Best Practices Summary

1. **Start Simple**: Begin with server-rendered templates, enhance progressively
2. **Component Reusability**: Build small, focused components
3. **Performance First**: Optimize for fast initial load and smooth interactions
4. **Accessibility Always**: Build with accessibility in mind from the start
5. **Test Early**: Write tests alongside development
6. **User Feedback**: Show loading states, errors, and success messages
7. **Responsive Design**: Test on multiple devices and screen sizes
8. **Documentation**: Keep code and component documentation up to date

---

## Resources

### Design Inspiration

- [Tailwind UI Components](https://tailwindui.com/)
- [shadcn/ui](https://ui.shadcn.com/)
- [Headless UI](https://headlessui.com/)
- [Radix UI](https://www.radix-ui.com/)

### Learning Resources

- [React Documentation](https://react.dev/)
- [Web.dev Accessibility](https://web.dev/accessible/)
- [MDN Web Docs](https://developer.mozilla.org/)
- [A11y Project](https://www.a11yproject.com/)

### Tools

- [Figma](https://www.figma.com/) - Design and prototyping
- [Storybook](https://storybook.js.org/) - Component development
- [Lighthouse](https://developers.google.com/web/tools/lighthouse) - Performance auditing
- [WAVE](https://wave.webaim.org/) - Accessibility testing

---

*Document Version: 1.0*  
*Last Updated: 2025-11-15*

