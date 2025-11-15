# Frontend Setup Guide

## Quick Start

1. **Install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Start the development server:**
   ```bash
   npm run dev
   ```

3. **Open your browser:**
   Navigate to [http://localhost:3000](http://localhost:3000)

## Prerequisites

- Node.js 18+ installed
- Flask backend running on `http://localhost:5000`

## Project Structure

```
frontend/
├── app/                    # Next.js app directory
│   ├── page.tsx           # Landing page
│   ├── dashboard/         # Dashboard page
│   ├── upload/            # Upload page
│   └── review/[auditId]/  # Review page
├── components/
│   ├── ui/               # shadcn/ui components
│   └── navigation.tsx    # Navigation component
├── lib/
│   ├── api.ts            # API client
│   └── utils.ts          # Utility functions
└── package.json
```

## Features

### Landing Page (`/`)
- Beautiful hero section
- Feature highlights
- How it works section
- Call-to-action buttons

### Dashboard (`/dashboard`)
- List all audits
- Filter by status and type
- Real-time progress updates
- Compliance score summaries

### Upload Page (`/upload`)
- Drag-and-drop file upload
- Document metadata input
- Progress tracking
- Success/error handling

### Review Page (`/review/[auditId]`)
- Detailed audit information
- Compliance score visualization
- Flag filtering and display
- Expandable flag details

## API Integration

The frontend connects to the Flask backend via API proxy configured in `next.config.js`. All API calls go through `/api/*` which is proxied to `http://localhost:5000/api/*`.

## Building for Production

```bash
npm run build
npm start
```

## Environment Variables

Create a `.env.local` file if you need to customize the API URL:

```
NEXT_PUBLIC_API_URL=http://localhost:5000
```

