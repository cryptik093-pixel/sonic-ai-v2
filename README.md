# 🎵 Sonic AI - Audio Analysis Platform

Complete AI-powered music analysis system with Shopify integration, user authentication, and freemium model.

## Features

✅ **10-Stage Audio Analysis Pipeline**
- Musical key detection (Krumhansl-Schmuckler algorithm)
- Tempo/BPM detection (autocorrelation)
- Chord recognition (template matching)
- Spectral balance analysis (low/mid/high)
- LUFS loudness metering (ITU-R BS.1770-4)
- Harmonic complexity measurement
- Melodic contour detection
- Pitch distribution analysis
- Mix reference classification
- Spectral peak identification

✅ **User System**
- Registration & login
- Usage tracking (2 free analyses/day)
- Analysis history storage
- Premium upgrade path

✅ **Shopify Integration**
- Automatic product recommendations
- Tempo/Key matching
- Genre-aware suggestions
- Direct links to your store

✅ **Web Dashboard**
- Modern, responsive UI
- Real-time analysis results
- Beautiful data visualizations
- Product recommendations

---

## 🚀 Quick Start

### 1. Clone or Navigate to Project
```bash
cd mkdir_sonic_ai
```

### 2. Activate Virtual Environment
```powershell
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Shopify (Optional)
Edit `.env`:
```
SHOPIFY_CLIENT_ID=your_id
SHOPIFY_CLIENT_SECRET=your_secret
SHOPIFY_ACCESS_TOKEN=your_token
```

### 5. Run the Web App
```bash
python sonic_app.py
```

### 6. Open Browser
Visit: **http://localhost:5000**

### Separate Pyramid Ambient App
Run:
```bash
python pyramid_listening_app.py
```

Open: **http://localhost:5050**

This standalone app listens to environmental audio, accepts simple sensor values,
and generates a phrase plus melody blueprint shaped toward a King's Chamber-inspired
acoustic profile.

---

## 📁 Project Structure

```
mkdir_sonic_ai/
├── sonic_app.py              # Flask web app (main entry point)
├── unified_analyzer.py        # 10-stage audio analysis engine
├── products.py               # Shopify integration & recommendations
├── sonic_cli.py              # Command-line batch processor
├── sonic_api.py              # REST API (alternative to web app)
├── requirements.txt          # Python dependencies
├── .env                      # Configuration (credentials)
├── .env.example             # Configuration template
├── DEPLOYMENT.md            # Production deployment guide
├── templates/
│   └── index.html           # Web dashboard UI
├── sonic_ai.db              # SQLite database (auto-created)
└── venv/                    # Virtual environment
```

---

## 🔧 Core Components

### unified_analyzer.py
Main analysis engine processing audio through 10 stages:

```python
analyzer = SonicAnalyzer()
results = analyzer.analyze(record=False, filepath='beat.wav')
# Returns 10 metrics as JSON
```

**Output JSON:**
```json
{
  "key": "G Minor",
  "key_confidence": 0.87,
  "tempo": 120,
  "tempo_confidence": 0.88,
  "chord": "Gm7",
  "chord_confidence": 0.95,
  "mix_balance": {"low": 35, "mid": 45, "high": 20},
  "mix_reference": "hiphop",
  "lufs": -14.2,
  "loudness_category": "loud",
  "harmonic_complexity": 0.82,
  "melodic_contour": "stable",
  "pitch_distribution": [0.1, 0.2, 0.15, ...],
  "spectral_peaks": [98.5, 196.3, 294.2]
}
```

### sonic_app.py
Flask web server with authentication and analysis endpoint:

```python
# Routes:
GET  /                    # Web dashboard
POST /register           # Create account
POST /login              # Sign in
POST /logout             # Sign out
POST /api/analyze        # Upload and analyze
GET  /api/history        # Analysis history
GET  /api/products       # Shopify catalog
POST /api/recommendations # Get product recs
```

### products.py
Matches analyzed audio to your Shopify products:

```python
get_recommendations(key='G Minor', tempo=120, mix_profile='hiphop')
# Returns top 5 matching products with relevance scores
```

---

## 💰 Freemium Model

**Free Tier:**
- 2 analyses per day
- View results
- See product recommendations
- Access analysis history

**Premium Tier (Stripe):**
- Unlimited analyses
- Detailed insights
- Priority support
- API access

Implement with:
```python
# In sonic_app.py
@app.route('/api/upgrade')
def upgrade():
    # Stripe payment flow
    pass
```

---

## 🛍️ Shopify Setup

1. **Get OAuth Credentials:**
   - https://www.omega-house.net/admin/apps-and-sales-channels/development
   - Create custom app with `read_products` scope

2. **Add Products to System:**
   - Edit `products.py` `PRODUCTS` dictionary
   - Include: name, price, BPM range, keys, genres, URL

3. **Recommendations Automatically Trigger:**
   - User uploads beat
   - AI analyzes (detects Key: G Minor, Tempo: 120 BPM)
   - System recommends matching products
   - User clicks → buys from your store

---

## 🌐 Deployment Options

### Local Development
```bash
python sonic_app.py
```
Runs on http://localhost:5000

### Production (Heroku)
```bash
heroku create your-app
git push heroku main
heroku config:set SHOPIFY_CLIENT_ID=xxx
```

### Production (Docker)
```bash
docker build -t sonic-ai .
docker run -p 5000:5000 sonic_ai
```

See **DEPLOYMENT.md** for full production setup.

---

## 📊 Analytics & Metrics

Track:
- User registrations
- Analyses completed
- Product click-throughs
- Conversion rate (analysis → purchase)

Add Google Analytics to `index.html` for full tracking.

---

## 🔐 Security

**Important:**
- Change `SECRET_KEY` in `.env`
- Rotate Shopify credentials regularly
- Use HTTPS in production
- Never commit `.env` to Git

**Add rate limiting:**
```python
from flask_limiter import Limiter
limiter = Limiter(app, key_func=lambda: session.get('user_id'))

@app.route('/api/analyze')
@limiter.limit("10/hour")
def analyze():
    pass
```

---

## 🧪 Testing

### Test Analyzer Locally
```bash
python test_unified_analyzer.py
```

### Test API
```bash
python sonic_api.py
# In another terminal:
curl -X POST -F "file=@test.wav" http://localhost:5000/analyze
```

### Test CLI Tool
```bash
python sonic_cli.py test_audio.wav --output-dir results/
```

---

## 🎯 Roadmap

**Phase 1 (Done):**
- ✅ Audio analysis engine (10 metrics)
- ✅ Web dashboard
- ✅ User authentication
- ✅ Shopify integration

**Phase 2 (Next):**
- 🔄 Stripe payment integration
- 🔄 Email confirmation
- 🔄 Advanced analytics dashboard
- 🔄 Mix comparison feature

**Phase 3 (Future):**
- DAW plugin wrapper
- Mobile app
- API for third-party developers
- Automated mastering recommendations

---

## 🐛 Troubleshooting

**Port 5000 in use?**
```powershell
netstat -ano | findstr :5000
taskkill /PID <PID> /F
```

**Database error?**
```bash
rm sonic_ai.db
python sonic_app.py
```

**Shopify API not working?**
- Verify `.env` has correct credentials
- Check app is installed on omega-house.net
- Restart Flask app

**Audio file not analyzing?**
- Ensure file is WAV or MP3
- Check file is not corrupted
- Try test file: `test_unified_analyzer.py`

---

## 📚 API Reference

### Upload & Analyze
```bash
curl -X POST \
  -F "file=@beat.wav" \
  -H "Cookie: session=..." \
  http://localhost:5000/api/analyze
```

**Response:**
```json
{
  "analysis": {...},
  "remaining_analyses": 1
}
```

### Get Recommendations
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"key":"G Minor","tempo":120,"mix_profile":"hiphop"}' \
  http://localhost:5000/api/recommendations
```

**Response:**
```json
{
  "recommendations": [
    {
      "name": "808 Essentials",
      "price": "$29.99",
      "reason": "Perfect for 120 BPM • Great for hiphop",
      "url": "..."
    }
  ]
}
```

---

## 📞 Support

Issues? Check:
1. `.env` file has all required variables
2. Dependencies installed: `pip install -r requirements.txt`
3. Virtual environment activated
4. Port 5000 not in use
5. Database not corrupted

---

## 📄 License

This project was created for **Omega House** (www.omega-house.net).

---

## 🎉 You're Ready!

1. Start the app: `python sonic_app.py`
2. Visit: http://localhost:5000
3. Sign up, upload audio, get recommendations
4. Deploy to production when ready
5. Watch the sales come in from your products! 🚀

Questions? Check `DEPLOYMENT.md` for advanced setup.
