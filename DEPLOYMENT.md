# Sonic AI Audio Analyzer - Deployment Guide

## 🚀 Quick Start (Local Development)

### 1. Activate Virtual Environment
```powershell
.\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```bash
pip install flask flask-sqlalchemy python-dotenv
```

### 3. Start the Web App
```bash
python sonic_app.py
```

Visit: **http://localhost:5000**

---

## 📋 System Architecture

```
User Browser (index.html)
    ↓
Flask Web Server (sonic_app.py)
    ├─ Authentication (Login/Register)
    ├─ Analysis API (/api/analyze)
    ├─ Product Recommendations (products.py)
    └─ Database (SQLite: user accounts, analysis history)
    ↓
Unified Analyzer (unified_analyzer.py)
    ├─ Spectral Analysis
    ├─ Key Detection
    ├─ BPM Detection
    ├─ Chord Recognition
    ├─ Mix Balance Analysis
    └─ 10 Metrics → JSON
    ↓
Shopify API (omega-house.net)
    └─ Product Catalog Integration
```

---

## 🛍️ Shopify Integration

### Step 1: Get OAuth Credentials
1. Go to: https://www.omega-house.net/admin/apps-and-sales-channels/development
2. Click "Create app"
3. Select "Custom app"
4. Under "Admin API scopes", select:
   - `read_products`
   - `write_products`
5. Copy credentials into `.env`:
   - `SHOPIFY_CLIENT_ID`
   - `SHOPIFY_CLIENT_SECRET`
   - `SHOPIFY_ACCESS_TOKEN`

### Step 2: Connect Your Products
Edit `products.py` to add your actual product catalog:

```python
PRODUCTS = {
    'drum_kits': [
        {
            'id': 1,
            'name': '808 Essentials Pack',
            'price': '$29.99',
            'bpm_range': [80, 120],
            'keys': ['all'],
            'genre': ['hiphop', 'trap'],
            'url': 'https://www.omega-house.net/products/808-essentials',
        },
        # Add more...
    ],
    'sample_packs': [
        # Add sample packs...
    ]
}
```

The analyzer automatically matches:
- **Detected Tempo** → Products in that BPM range
- **Musical Key** → Compatible keys
- **Genre/Mix Profile** → Relevant products

---

## 💾 Database Setup

SQLite database is created automatically at: `sonic_ai.db`

**Tables:**
- `user` - User accounts (username, email, password)
- `analysis` - Analysis history (file, results, timestamp)

To reset database:
```bash
rm sonic_ai.db
python sonic_app.py  # Creates fresh database
```

---

## 🔐 User Limits & Freemium Model

**Free Tier:**
- 2 analyses per day
- Tracked per user per UTC date

**Upgrade Model (Future):**
- Add `is_premium` column to User table
- Premium users get unlimited analyses
- Add Stripe integration for payments

**Current Limits in Code (`sonic_app.py`):**
```python
if analyses_today >= 2:  # Change this number
    return jsonify({'error': 'Daily limit reached'}), 429
```

---

## 🌐 Production Deployment

### Option 1: Heroku (Easiest)

1. **Install Heroku CLI**: https://devcenter.heroku.com/articles/heroku-cli

2. **Create Procfile**:
```
web: gunicorn sonic_app:app
```

3. **Install Production Server**:
```bash
pip install gunicorn
```

4. **Deploy**:
```bash
heroku login
heroku create your-app-name
git push heroku main
```

5. **Set Environment Variables**:
```bash
heroku config:set SHOPIFY_CLIENT_ID=your_id
heroku config:set SHOPIFY_CLIENT_SECRET=your_secret
heroku config:set SECRET_KEY=your_secret_key
```

### Option 2: AWS EC2 / DigitalOcean

1. **Install Nginx** as reverse proxy
2. **Run Flask with Gunicorn**:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 sonic_app:app
```

3. **Configure SSL** with Let's Encrypt:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

### Option 3: Docker (Recommended for Scaling)

Create `Dockerfile`:
```dockerfile
FROM python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "sonic_app:app"]
```

Build & run:
```bash
docker build -t sonic-ai .
docker run -p 5000:5000 sonic_ai
```

---

## 🔗 Embedding on Shopify

### Option 1: Embed as Sales Channel
1. Register Sonic AI as a custom sales channel
2. Add embedded iframe on your Shopify site:
```html
<iframe src="https://your-sonic-ai-domain.com" 
        width="100%" height="800px">
</iframe>
```

### Option 2: Redirect to Tool
1. Add button to your Shopify site:
```html
<a href="https://your-sonic-ai-domain.com" class="button">
  Free Audio Analysis Tool
</a>
```

### Option 3: Pop-up Modal
Embed script on Shopify:
```javascript
<script>
  document.getElementById('analyze-btn').addEventListener('click', () => {
    window.open('https://sonic-ai.com', 'analyzer', 'width=800,height=600');
  });
</script>
```

---

## 💰 Revenue Streams

### Stream 1: Freemium Model
- Free: 2 analyses/day
- Premium: Unlimited ($4.99/month or $39.99/year)

**Implementation:**
```python
@app.route('/api/upgrade', methods=['POST'])
def upgrade_user():
    user = User.query.get(session['user_id'])
    user.is_premium = True
    db.session.commit()
    return jsonify({'message': 'Upgraded!'})
```

### Stream 2: Recommended Products
- User detects key (e.g., "G Minor")
- System recommends drum kits that match
- Link to Shopify store → Commission on sales

### Stream 3: Premium Reports
- Free: JSON output
- Premium: PDF report with:
  - Mastering recommendations
  - Reference track analysis
  - Integration guide

---

## 📊 Analytics & Tracking

Add Google Analytics to `index.html`:
```html
<script async src="https://www.googletagmanager.com/gtag/js?id=GA_ID"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'GA_ID');
</script>
```

Track events:
- User registration
- Analysis completed
- Product click-through
- Upgrade success

---

## 🔧 API Endpoints Reference

```
POST /register
  Input: {username, email, password}
  Output: {message: "Registration successful!"}

POST /login
  Input: {username, password}
  Output: {message: "Login successful!"}

POST /logout
  Output: {message: "Logged out"}

GET /profile
  Output: {username, email, analyses_today, remaining_analyses, total_analyses}

POST /api/analyze
  Input: multipart/form-data (file)
  Output: {analysis: {...}, remaining_analyses: 2}

GET /api/history
  Output: [{id, filename, key, tempo, chord, lufs, created_at}]

GET /api/products
  Output: {drum_kits: [...], sample_packs: [...]}

POST /api/recommendations
  Input: {key, tempo, mix_profile}
  Output: {recommendations: [...]}

GET /health
  Output: {status: "healthy"}
```

---

## ⚠️ Security Checklist

- [ ] Change `SECRET_KEY` in `.env`
- [ ] **ROTATE Shopify credentials immediately** (they were exposed in chat)
- [ ] Set `FLASK_DEBUG=False` in production
- [ ] Use HTTPS only in production
- [ ] Add rate limiting:
```python
from flask_limiter import Limiter
limiter = Limiter(app, key_func=lambda: session.get('user_id'))

@app.route('/api/analyze', methods=['POST'])
@limiter.limit("10/hour")  # 10 analyses per hour per user
def analyze():
    ...
```

---

## 🎯 Next Steps

1. **Deploy to production** (Heroku/AWS/Docker)
2. **Connect to omega-house.net** (iframe or redirect)
3. **Set up Stripe** for premium subscriptions
4. **Add email confirmation** for signups
5. **Create landing page** explaining the tool
6. **Start collecting emails** for mailing list
7. **Track metrics** (user signups, analyses, conversions)

---

## 📞 Troubleshooting

**Port 5000 already in use:**
```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Mac/Linux
lsof -i :5000
kill -9 <PID>
```

**Database locked error:**
```bash
rm sonic_ai.db  # Start fresh
```

**Spotify API not working:**
- Verify credentials in `.env`
- Check Shopify app is installed on omega-house.net
- Restart Flask app after changing credentials

**CORS errors (if embedding):**
- Add to Flask app:
```python
from flask_cors import CORS
CORS(app)
```

---

## 📧 Support

For issues or questions:
1. Check the logs: `tail -f sonic_ai.log`
2. Verify `.env` file has all credentials
3. Test API endpoints with Postman
4. Check browser console for JavaScript errors

Good luck! 🚀
