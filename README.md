# 🎥 Short-form Content Rewards Platform

A comprehensive content creator rewards platform that combines short-form video sharing with AI-powered analysis and blockchain-inspired revenue sharing. Creators earn points based on engagement metrics, content quality, and AI analysis, with monthly revenue distribution through a secure wallet system.

## 🌟 Features

### 📱 **ShortsHub - Video Platform**

- **Short-form Video Upload & Sharing** - Create and share engaging vertical videos
- **Interactive Engagement** - Like, comment, and view tracking with real-time analytics
- **User Profiles** - Personalized creator profiles with statistics and content galleries
- **Responsive Design** - Modern, mobile-first interface with smooth animations

### 🤖 **AI-Powered Analysis**

- **Video Quality Analysis** - Google Gemini AI evaluates content engagement, production quality, and audience appeal
- **Audio Quality Assessment** - Comprehensive audio analysis for speech clarity and overall quality
- **Comment Sentiment Analysis** - Real-time sentiment scoring using TextBlob for moderation and engagement insights
- **Automated Scoring** - Multi-dimensional scoring system (0-100) across various quality metrics

### 💰 **Rewards & Revenue System**

- **Point-Based Rewards** - Creators earn points from views (1pt), likes (5pts), comments (10pts), and watch percentage
- **AI Bonus System** - Up to 50% bonus based on video quality (30%), audio quality (15%), and comment sentiment (5%)
- **Monthly Revenue Sharing** - 50% of platform revenue distributed to creators based on average points per video
- **Blockchain-Inspired Security** - Secure transactions with cryptographic hashing and chain verification

### 🛡️ **Moderation & Quality Control**

- **Automated Flagging** - Content flagged for review when sentiment scores are outside -0.8 to 0.8 range
- **Admin Moderation Tools** - Manual adjustment capabilities with percentage-based reward modifications
- **Content Analytics** - Comprehensive reporting on content quality, engagement, and performance metrics

### 💳 **Wallet & Transactions**

- **Secure Digital Wallets** - User wallets with balance tracking and transaction history
- **Monthly Payouts** - Automated revenue distribution with detailed calculation breakdowns
- **Withdrawal System** - Full wallet withdrawal capabilities with audit trail
- **Transparent Reporting** - Complete transaction logs with cryptographic verification

## 🏗️ Architecture

### Backend (Django REST Framework)

```
backend/
├── api/                          # Main API application
│   ├── models.py                 # Database models (Short, User, Wallet, Transaction)
│   ├── views.py                  # API endpoints and business logic
│   ├── serializers.py            # Data serialization
│   ├── reward_service.py         # Revenue sharing and reward calculations
│   ├── comment_analysis_service.py # Sentiment analysis service
│   ├── gemini_video_service.py   # Google Gemini AI video analysis
│   └── management/commands/      # Django management commands
├── backend/                      # Django project settings
├── media/                        # Uploaded videos and audio files
└── requirements.txt              # Python dependencies
```

### Frontend (React + Vite)

```
frontend/
├── src/
│   ├── components/              # Reusable UI components
│   │   ├── VideoPlayer.jsx      # Video player with analytics overlay
│   │   ├── Navigation.jsx       # Main navigation component
│   │   └── VideoAnalytics.jsx   # Real-time analytics display
│   ├── pages/                   # Main application pages
│   │   ├── Home.jsx             # Dashboard and video feed
│   │   ├── Profile.jsx          # User profiles and content management
│   │   └── Login.jsx            # Authentication
│   ├── services/                # API service layer
│   ├── styles/                  # CSS styling and animations
│   └── contexts/                # React context providers
└── package.json                 # Node.js dependencies
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+**
- **Node.js 18+**
- **Django 4.2+**
- **Google Gemini API Key** (for AI analysis)

### Backend Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/henrychooi/live-streaming-rewards.git
   cd live-streaming-rewards/backend
   ```

2. **Create virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Environment configuration**

   ```bash
   cp .env.example .env
   # Edit .env with your configuration:
   # - GEMINI_API_KEY=your_google_gemini_api_key
   # - SECRET_KEY=your_django_secret_key
   # - DEBUG=True
   ```

5. **Database setup**

   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

6. **Run development server**
   ```bash
   python manage.py runserver
   ```

### Frontend Setup

1. **Navigate to frontend directory**

   ```bash
   cd ../frontend
   ```

2. **Install dependencies**

   ```bash
   npm install
   ```

3. **Start development server**

   ```bash
   npm run dev
   ```

4. **Access the application**
   - Frontend: `http://localhost:5173`
   - Backend API: `http://localhost:8000`
   - Admin Panel: `http://localhost:8000/admin`

## 📊 API Endpoints

### Authentication

- `POST /api/user/register/` - User registration
- `POST /api/token/` - JWT token authentication
- `POST /api/token/refresh/` - Token refresh

### Content Management

- `GET /api/shorts/` - List all shorts
- `POST /api/shorts/create/` - Upload new short video
- `GET /api/shorts/{id}/` - Get specific short details
- `POST /api/shorts/{id}/like/` - Like/unlike a short
- `POST /api/shorts/{id}/comment/` - Add comment

### Analytics & AI

- `POST /api/analyze-video/{short_id}/` - Trigger AI video analysis
- `GET /api/video-analysis/{short_id}/` - Get analysis results
- `POST /api/analyze-comments/{short_id}/` - Analyze comment sentiment

### Rewards & Payouts

- `POST /api/calculate-rewards/{short_id}/` - Calculate reward points
- `GET /api/monthly-creator-points/` - Get monthly point summary
- `POST /api/monthly-revenue-share/` - Calculate revenue distribution
- `POST /api/process-monthly-payouts/` - Process actual payouts

### Wallet Management

- `GET /api/wallet/` - Get wallet details
- `GET /api/wallet/transactions/` - Transaction history
- `POST /api/wallet/withdraw/` - Withdraw funds

## 🧪 Quick Demo: Monthly Payouts

You can demo creator payouts end-to-end without waiting a full month.

- Create recent test data (3 creators, multiple shorts each):
  - `python manage.py create_simple_test_data --recent`
- Dry run 5‑minute payout (average points per video, 50% creator pool):
  - `python manage.py test_5min_payout --revenue 5000`
- Real 5‑minute payout (credits wallets, creates transactions):
  - `python manage.py test_5min_payout --revenue 5000 --real`
- View balances and withdraw in the app:
  - Open the Wallet modal in the UI, or call `GET /api/wallet/` and `POST /api/wallet/withdraw/`

Admin API endpoints are also available for testing:

- `POST /api/admin/revenue-share/test-5min/` with body `{ "platform_revenue": 5000, "dry_run": true }`
- `POST /api/admin/revenue-share/test-3min/` with body `{ "platform_revenue": 5000, "dry_run": true }`
- `POST /api/admin/revenue-share/calculate/` and `/process-payouts/` for full monthly runs

## 🔧 Key Management Commands

### Revenue & Rewards

```bash
# Calculate points for uncalculated shorts
python manage.py calculate_points_for_shorts --year 2025 --month 8

# Process monthly payouts (dry run)
python manage.py process_monthly_payouts --year 2025 --month 8 --revenue 10000 --dry-run

# Process actual monthly payouts
python manage.py process_monthly_payouts --year 2025 --month 8 --revenue 10000
```

### Content Analysis

```bash
# Analyze video content with AI
python manage.py analyze_videos --limit 10

# Analyze comment sentiment
python manage.py analyze_comments --short-id 123

# Create test data
python manage.py create_simple_test_data
```

## 🎯 Reward Calculation Formula

### Base Points

```
Main Reward = (views × 1) + (likes × 5) + (comments × 10) + (avg_watch_percentage × 0.5)
```

### AI Bonus (0-50%)

```
Video Quality Bonus: 30% × (video_score/100)^1.5
Audio Quality Bonus: 15% × (audio_score/100)^1.2
Sentiment Bonus: 5% × normalized_sentiment_score
```

### Final Score

```
Final Reward = Main Reward + (Main Reward × AI Bonus %) + Moderation Adjustment
```

### Revenue Distribution

```
Creator Share = (Creator Average Points / Total Average Points) × 50% Platform Revenue
```

## 🛠️ Technology Stack

### Backend

- **Django 4.2** - Web framework
- **Django REST Framework** - API development
- **PostgreSQL/SQLite** - Database
- **Google Gemini AI** - Video analysis
- **TextBlob** - Sentiment analysis
- **JWT Authentication** - Secure authentication
- **Python-dotenv** - Environment management

### Frontend

- **React 19** - UI framework
- **Vite** - Build tool and development server
- **React Router** - Client-side routing
- **Axios** - HTTP client
- **Tailwind CSS** - Utility-first styling
- **Lucide React** - Icon library

### Analysis & AI

- **Google Generative AI** - Video content analysis
- **TextBlob** - Natural language processing
- **FFmpeg** - Video processing
- **MoviePy** - Video manipulation
- **Librosa** - Audio analysis

## 📈 Performance Features

### Optimization

- **Lazy Loading** - Progressive content loading
- **Image/Video Optimization** - Automatic compression and formatting
- **Caching** - Strategic API response caching
- **Database Indexing** - Optimized query performance

### Scalability

- **Batch Processing** - Efficient bulk operations
- **Background Tasks** - Asynchronous content analysis
- **CDN Ready** - Static file distribution support
- **API Rate Limiting** - Resource protection

## 🔒 Security

### Data Protection

- **JWT Authentication** - Secure token-based auth
- **CORS Configuration** - Cross-origin request management
- **Input Validation** - Comprehensive data sanitization
- **File Upload Security** - Safe file handling

### Blockchain-Inspired Features

- **Transaction Hashing** - Cryptographic transaction integrity
- **Chain Verification** - Sequential transaction validation
- **Digital Signatures** - Transaction authenticity
- **Audit Logs** - Immutable activity tracking

## 📋 Contributing

1. **Fork the repository**
2. **Create feature branch** (`git checkout -b feature/amazing-feature`)
3. **Commit changes** (`git commit -m 'Add amazing feature'`)
4. **Push to branch** (`git push origin feature/amazing-feature`)
5. **Open Pull Request**

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Support

For support, email support@shortshub.com or create an issue in the GitHub repository.

## 🙏 Acknowledgments

- **Google Gemini AI** - Advanced video analysis capabilities
- **Django Community** - Robust web framework
- **React Team** - Modern frontend development
- **Contributors** - All the amazing developers who contributed to this project

---

**Made with ❤️ by the ShortsHub Team**
