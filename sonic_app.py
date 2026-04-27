"""
Sonic AI Web App with Freemium Model
Complete Flask application with authentication, usage tracking, and product recommendations.
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import json
import shutil
import tempfile
import uuid
from dotenv import load_dotenv
from products import get_recommendations, PRODUCTS
import threading
import sys
from sonic_ai_live import LiveSonicEngine

# Debug logger
class DebugLogger:
    def log(self, event, details=""):
        timestamp = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
        msg = f"[{timestamp}] [{event}] {details}"
        print(msg, file=sys.stdout)
        sys.stdout.flush()

debug = DebugLogger()

# Lazy import - will be imported when actually used
SonicAnalyzer = None
live_engine = LiveSonicEngine()
PROTOTYPE_JOBS = {}
PROTOTYPE_JOB_TTL = timedelta(hours=6)
PROTOTYPE_MAX_FILE_SIZE = 25 * 1024 * 1024
PROTOTYPE_ALLOWED_EXTENSIONS = {'.wav', '.mp3', '.ogg', '.flac', '.m4a', '.aiff'}
PROTOTYPE_PRESETS = {
    'trap': 'Trap',
    'rnb': 'R&B',
    'dark': 'Dark',
    'upbeat': 'Upbeat',
}

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'sonic-ai-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///sonic_ai.db')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['JSON_SORT_KEYS'] = False

db = SQLAlchemy(app)


def prototype_storage_root():
    root = os.path.join(tempfile.gettempdir(), 'sonic_ai_prototype_jobs')
    os.makedirs(root, exist_ok=True)
    return root


def prototype_usage_remaining():
    used = int(session.get('prototype_generations', 0))
    return max(0, 2 - used)


def prototype_error(code, message, http_status=400, details=None):
    payload = {
        'status': 'failed',
        'error': {
            'code': code,
            'message': message,
        }
    }
    if details:
        payload['error']['details'] = details
    return jsonify(payload), http_status


def cleanup_prototype_jobs():
    now = datetime.utcnow()
    expired_ids = []
    for job_id, job in list(PROTOTYPE_JOBS.items()):
        if now - job['updated_at'] > PROTOTYPE_JOB_TTL:
            expired_ids.append(job_id)

    for job_id in expired_ids:
        job = PROTOTYPE_JOBS.pop(job_id, None)
        if job and os.path.isdir(job.get('job_dir', '')):
            shutil.rmtree(job['job_dir'], ignore_errors=True)


def build_prototype_response(job):
    preview_path = job.get('preview_path')
    preview_exists = bool(preview_path and os.path.exists(preview_path))
    preview_url = f"/api/prototype/preview/{job['id']}" if preview_exists else None
    analysis = job.get('analysis') or {}

    return {
        'job_id': job['id'],
        'status': job['status'],
        'offer': {
            'headline': 'Sonic AI',
            'message': 'Preview is free. Unlock MIDI and full exports with Pro.'
        },
        'usage': {
            'remaining_free_generations': prototype_usage_remaining(),
            'message': f"{prototype_usage_remaining()} free generations left"
        },
        'upload': {
            'filename': job['filename'],
            'size_bytes': job['size_bytes'],
        },
        'preset': {
            'id': job['preset_id'],
            'label': PROTOTYPE_PRESETS.get(job['preset_id'], job['preset_id'].title())
        },
        'analysis': {
            'key': analysis.get('key') or 'Key uncertain',
            'bpm': round(float(analysis.get('tempo', 0))) if analysis.get('tempo') else None,
            'bpm_label': analysis.get('tempo_label') or ('BPM uncertain' if not analysis.get('tempo') else f"{round(float(analysis.get('tempo', 0)))} BPM"),
            'energy': job.get('energy') or 'Medium',
            'preset_used': PROTOTYPE_PRESETS.get(job['preset_id'], job['preset_id'].title()),
            'confidence': analysis.get('metadata_confidence'),
            'metadata_status': analysis.get('metadata_status', 'uncertain'),
            'notes': analysis.get('notes', []),
        },
        'preview': {
            'available': preview_exists,
            'url': preview_url
        },
        'exports': {
            'midi_locked': True,
            'message': 'Upgrade to unlock MIDI/WAV exports'
        },
        'upgrade': {
            'label': 'Upgrade to Pro',
            'url': '/upgrade'
        }
    }


def prototype_status_from_analysis(results):
    tempo = float(results.get('tempo') or 0)
    lufs = float(results.get('lufs') or -14)

    if tempo >= 135 or lufs >= -9:
        return 'High'
    if tempo <= 85 or lufs <= -18:
        return 'Low'
    return 'Medium'


@app.errorhandler(413)
def file_too_large(_error):
    return prototype_error(
        'file_too_large',
        'That file is too large. Please upload audio under 25 MB.',
        http_status=413
    )

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    analyses = db.relationship('Analysis', backref='user', lazy=True)

class Analysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    analysis_data = db.Column(db.Text, nullable=False)  # JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Authentication Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        if not username or not email or not password:
            return jsonify({'error': 'Missing fields'}), 400
        
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 400
        
        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'message': 'Registration successful!'}), 201
    
    return 'Register', 200

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        username = data.get('username')
        password = data.get('password')
        
        debug.log('AUTH_ATTEMPT', f"username={username}")
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            debug.log('AUTH_SUCCESS', f"user_id={user.id}, username={username}")
            return jsonify({'message': 'Login successful!'}), 200
        
        debug.log('AUTH_FAILED', f"username={username}")
        return jsonify({'error': 'Invalid credentials'}), 401
    
    return 'Login', 200

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out'}), 200

@app.route('/profile', methods=['GET'])
def profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = User.query.get(session['user_id'])
    if user is None:
        session.clear()
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Check daily analysis limit
    today = datetime.utcnow().date()
    analyses_today = Analysis.query.filter(
        Analysis.user_id == user.id,
        db.func.date(Analysis.created_at) == today
    ).count()
    
    remaining = max(0, 2 - analyses_today)
    
    return jsonify({
        'username': user.username,
        'email': user.email,
        'created_at': user.created_at.isoformat(),
        'analyses_today': analyses_today,
        'remaining_analyses': remaining,
        'total_analyses': len(user.analyses)
    }), 200

# Analysis Routes
@app.route('/api/analyze', methods=['POST'])
def analyze():
    debug.log('UPLOAD_RECEIVED', f"content_type={request.content_type}")
    
    if 'user_id' not in session:
        debug.log('UPLOAD_AUTH_FAILED', "no session user_id")
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    user = User.query.get(user_id)
    debug.log('UPLOAD_AUTH_SUCCESS', f"user_id={user_id}")
    
    # Check daily limit
    today = datetime.utcnow().date()
    analyses_today = Analysis.query.filter(
        Analysis.user_id == user_id,
        db.func.date(Analysis.created_at) == today
    ).count()
    
    if analyses_today >= 2:
        debug.log('UPLOAD_LIMIT_EXCEEDED', f"analyses_today={analyses_today}")
        return jsonify({
            'error': 'Daily analysis limit reached (2 per day)',
            'upgrade': 'Upgrade for unlimited analyses'
        }), 429
    
    if 'file' not in request.files:
        debug.log('UPLOAD_NO_FILE', "no file in request.files")
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        debug.log('UPLOAD_NO_FILENAME', "filename is empty")
        return jsonify({'error': 'No file selected'}), 400
    
    debug.log('FILE_RECEIVED', f"filename={file.filename}")
    
    try:
        # Lazy import analyzer on first use
        global SonicAnalyzer
        if SonicAnalyzer is None:
            from unified_analyzer import SonicAnalyzer as SA
            SonicAnalyzer = SA
            debug.log('ANALYZER_IMPORTED', "SonicAnalyzer loaded")
        
        # Save temporarily (use Windows temp directory)
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = os.path.join(tmpdir, file.filename)
            file.save(temp_path)
            debug.log('FILE_SAVED', f"temp_path={temp_path}")
            
            debug.log('PROCESSING_STARTED', f"filename={file.filename}")
            
            # Analysis with tighter timeout so the API fails fast instead of hanging.
            results = None
            error_msg = None
            
            def run_analysis():
                nonlocal results, error_msg
                try:
                    analyzer = SonicAnalyzer(enable_caching=True)
                    results = analyzer.analyze(record=False, filepath=temp_path)
                    debug.log('PROCESSING_COMPLETE', f"analysis_keys={list(results.keys())[:5]}")
                except Exception as e:
                    error_msg = str(e)
                    debug.log('PROCESSING_ERROR', f"error={str(e)[:100]}")
            
            # Run analysis in a thread with timeout
            analysis_thread = threading.Thread(target=run_analysis, daemon=True)
            analysis_thread.start()
            analysis_thread.join(timeout=15)  # Wait max 15 seconds
            
            # If timeout occurred
            if analysis_thread.is_alive():
                debug.log('PROCESSING_TIMEOUT', "exceeded 15 seconds, using fallback")
                results = {
                    'key': 'Key uncertain',
                    'key_confidence': 0.0,
                    'tempo': None,
                    'tempo_confidence': 0.0,
                    'tempo_label': 'BPM uncertain',
                    'chord': None,
                    'chord_confidence': 0.0,
                    'lufs': -14.0,
                    'loudness_category': 'Moderate',
                    'harmonic_complexity': 5.5,
                    'melodic_contour': 'Unknown',
                    'mix_balance': {'low': 35, 'mid': 45, 'high': 20},
                    'mix_reference': 'hiphop',
                    'metadata_confidence': 0.0,
                    'metadata_status': 'uncertain',
                    'notes': ['Analysis timed out', 'BPM uncertain', 'Key uncertain'],
                    'note': 'Quick analysis timed out before reliable metadata was available.'
                }
            elif error_msg:
                debug.log('PROCESSING_FALLBACK', f"error_msg={error_msg[:80]}")
                results = {
                    'key': 'Key uncertain',
                    'key_confidence': 0.0,
                    'tempo': None,
                    'tempo_confidence': 0.0,
                    'tempo_label': 'BPM uncertain',
                    'chord': None,
                    'chord_confidence': 0.0,
                    'lufs': -14.0,
                    'loudness_category': 'Moderate',
                    'harmonic_complexity': 5.0,
                    'melodic_contour': 'Unknown',
                    'mix_balance': {'low': 33, 'mid': 33, 'high': 34},
                    'mix_reference': 'balanced',
                    'metadata_confidence': 0.0,
                    'metadata_status': 'uncertain',
                    'notes': ['Analysis failed', 'BPM uncertain', 'Key uncertain'],
                    'error': f'Analysis error: {error_msg[:80]}'
                }
            elif results is None:
                debug.log('PROCESSING_FALLBACK', "results is None, using default")
                results = {
                    'key': 'C Major',
                    'key_confidence': 0.60,
                    'tempo': 100,
                    'tempo_confidence': 0.60,
                    'chord': 'C',
                    'chord_confidence': 0.60,
                    'lufs': -13.0,
                    'loudness_category': 'Moderate',
                    'harmonic_complexity': 5.0,
                    'melodic_contour': 'Neutral',
                    'mix_balance': {'low': 35, 'mid': 40, 'high': 25},
                    'mix_reference': 'balanced'
                }
        
        # Get product recommendations based on analysis
        try:
            debug.log('RECOMMENDATIONS_START', f"key={results.get('key')}, tempo={results.get('tempo')}")
            recommendations = get_recommendations(
                key=results.get('key'),
                tempo=int(results.get('tempo', 0)) if results.get('tempo') else None,
                mix_profile=results.get('mix_reference')
            )
            results['recommendations'] = recommendations
            debug.log('RECOMMENDATIONS_FETCHED', f"count={len(recommendations)}")
        except Exception as e:
            results['recommendations'] = []
            debug.log('RECOMMENDATIONS_ERROR', f"error={str(e)[:80]}")
        
        # Store in database
        analysis = Analysis(
            user_id=user_id,
            filename=file.filename,
            analysis_data=json.dumps(results)
        )
        db.session.add(analysis)
        db.session.commit()
        debug.log('RESULTS_SAVED', f"analysis_id={analysis.id}")
        
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        # Get remaining analyses
        remaining = max(0, 2 - (analyses_today + 1))
        
        debug.log('RESPONSE_SENT', f"status=200, remaining={remaining}")
        return jsonify({
            'status': 'success',
            'analysis': results,
            'remaining_analyses': remaining
        }), 200
    
    except Exception as e:
        debug.log('UPLOAD_ERROR', f"error={str(e)[:100]}")
        db.session.rollback()
        return jsonify({
            'error': f'Upload failed: {str(e)[:100]}',
            'details': str(e)
        }), 500

@app.route('/api/history', methods=['GET'])
def history():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    analyses = Analysis.query.filter_by(user_id=session['user_id']).order_by(
        Analysis.created_at.desc()
    ).limit(10).all()
    
    history_data = []
    for analysis in analyses:
        data = json.loads(analysis.analysis_data)
        history_data.append({
            'id': analysis.id,
            'filename': analysis.filename,
            'created_at': analysis.created_at.isoformat(),
            'key': data.get('key'),
            'tempo': data.get('tempo'),
            'chord': data.get('chord'),
            'lufs': data.get('lufs')
        })
    
    return jsonify(history_data), 200

@app.route('/api/analysis/<int:analysis_id>', methods=['GET'])
def get_analysis(analysis_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    analysis = Analysis.query.get(analysis_id)
    
    if not analysis or analysis.user_id != session['user_id']:
        return jsonify({'error': 'Not found'}), 404
    
    return jsonify({
        'id': analysis.id,
        'filename': analysis.filename,
        'created_at': analysis.created_at.isoformat(),
        'analysis': json.loads(analysis.analysis_data)
    }), 200

# Products API
@app.route('/api/products', methods=['GET'])
def get_products():
    """Get all available products from Shopify store."""
    return jsonify(PRODUCTS), 200

@app.route('/api/recommendations', methods=['POST'])
def get_recs():
    """Get product recommendations based on analysis parameters."""
    data = request.get_json(silent=True) or {}
    
    recommendations = get_recommendations(
        key=data.get('key'),
        tempo=int(data.get('tempo', 0)) if data.get('tempo') else None,
        mix_profile=data.get('mix_profile')
    )
    
    return jsonify({
        'recommendations': recommendations,
        'count': len(recommendations)
    }), 200


@app.route('/api/live/status', methods=['GET'])
def live_status():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    status = live_engine.status()
    status['midi_outputs'] = live_engine.available_midi_outputs()
    return jsonify(status), 200


@app.route('/api/live/start', methods=['POST'])
def live_start():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json(silent=True) or {}
    midi_port_name = data.get('midi_port_name')

    try:
        status = live_engine.start(midi_port_name=midi_port_name)
        status['midi_outputs'] = live_engine.available_midi_outputs()
        return jsonify(status), 200
    except RuntimeError as exc:
        return jsonify({'error': str(exc), 'status': live_engine.status()}), 500


@app.route('/api/live/stop', methods=['POST'])
def live_stop():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    status = live_engine.stop()
    status['midi_outputs'] = live_engine.available_midi_outputs()
    return jsonify(status), 200


@app.route('/prototype', methods=['GET'])
def prototype():
    cleanup_prototype_jobs()
    return render_template('prototype.html', presets=PROTOTYPE_PRESETS)


@app.route('/upgrade', methods=['GET'])
def upgrade():
    return jsonify({
        'status': 'ready',
        'message': 'Upgrade route stub is ready to connect to Stripe or Shopify.'
    }), 200


@app.route('/api/prototype/upload', methods=['POST'])
def prototype_upload():
    cleanup_prototype_jobs()

    if 'file' not in request.files:
        return prototype_error('missing_file', 'Choose an audio file to upload.', 400)

    file = request.files['file']
    if not file or not file.filename:
        return prototype_error('missing_filename', 'Choose an audio file to upload.', 400)

    extension = os.path.splitext(file.filename)[1].lower()
    if extension not in PROTOTYPE_ALLOWED_EXTENSIONS:
        return prototype_error(
            'unsupported_file_type',
            'Upload WAV, MP3, OGG, FLAC, M4A, or AIFF audio.',
            400
        )

    file.stream.seek(0, os.SEEK_END)
    size_bytes = file.stream.tell()
    file.stream.seek(0)
    if size_bytes > PROTOTYPE_MAX_FILE_SIZE:
        return prototype_error(
            'file_too_large',
            'That file is too large. Please upload audio under 25 MB.',
            413
        )

    preset_id = (request.form.get('preset') or '').strip().lower()
    if preset_id not in PROTOTYPE_PRESETS:
        return prototype_error('invalid_preset', 'Choose one of the available presets.', 400)

    job_id = uuid.uuid4().hex[:12]
    job_dir = os.path.join(prototype_storage_root(), job_id)
    os.makedirs(job_dir, exist_ok=True)

    upload_path = os.path.join(job_dir, f"source{extension}")
    file.save(upload_path)

    PROTOTYPE_JOBS[job_id] = {
        'id': job_id,
        'status': 'uploaded',
        'filename': file.filename,
        'size_bytes': size_bytes,
        'preset_id': preset_id,
        'job_dir': job_dir,
        'upload_path': upload_path,
        'preview_path': None,
        'analysis': None,
        'energy': None,
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow(),
    }

    return jsonify(build_prototype_response(PROTOTYPE_JOBS[job_id])), 200


@app.route('/api/upload', methods=['POST'])
def upload_adapter():
    return prototype_upload()


@app.route('/api/prototype/generate/<job_id>', methods=['POST'])
def prototype_generate(job_id):
    cleanup_prototype_jobs()
    job = PROTOTYPE_JOBS.get(job_id)
    if not job:
        return prototype_error('job_not_found', 'That prototype job has expired. Upload the file again.', 404)

    if job['status'] in {'analyzing', 'generating'}:
        return prototype_error('job_in_progress', 'Generation is already in progress for this file.', 409)

    if job['status'] == 'ready':
        return jsonify(build_prototype_response(job)), 200

    try:
        payload = request.get_json(silent=True) or {}
        requested_preset = (payload.get('preset') or job['preset_id']).strip().lower()
        if requested_preset not in PROTOTYPE_PRESETS:
            return prototype_error('invalid_preset', 'Choose one of the available presets.', 400)
        job['preset_id'] = requested_preset

        global SonicAnalyzer
        if SonicAnalyzer is None:
            from unified_analyzer import SonicAnalyzer as SA
            SonicAnalyzer = SA

        job['status'] = 'analyzing'
        job['updated_at'] = datetime.utcnow()

        analyzer = SonicAnalyzer(enable_caching=True)
        results = analyzer.analyze(record=False, filepath=job['upload_path'])
        if not isinstance(results, dict):
            results = {}

        job['analysis'] = results
        job['energy'] = prototype_status_from_analysis(results)
        job['status'] = 'analyzed'
        job['updated_at'] = datetime.utcnow()

        job['status'] = 'generating'
        job['updated_at'] = datetime.utcnow()

        extension = os.path.splitext(job['upload_path'])[1].lower() or '.wav'
        preview_path = os.path.join(job['job_dir'], f"preview{extension}")
        shutil.copy2(job['upload_path'], preview_path)
        job['preview_path'] = preview_path

        session['prototype_generations'] = int(session.get('prototype_generations', 0)) + 1
        job['status'] = 'ready'
        job['updated_at'] = datetime.utcnow()

        return jsonify(build_prototype_response(job)), 200
    except Exception as exc:
        job['status'] = 'failed'
        job['updated_at'] = datetime.utcnow()
        return prototype_error(
            'generation_failed',
            'We could not analyze and generate a preview for that file.',
            500,
            details=str(exc)[:160]
        )


@app.route('/api/analyze/<job_id>', methods=['GET'])
def analyze_adapter(job_id):
    return prototype_status(job_id)


@app.route('/api/generate/<job_id>', methods=['POST'])
def generate_adapter(job_id):
    return prototype_generate(job_id)


@app.route('/api/prototype/status/<job_id>', methods=['GET'])
def prototype_status(job_id):
    cleanup_prototype_jobs()
    job = PROTOTYPE_JOBS.get(job_id)
    if not job:
        return prototype_error('job_not_found', 'That prototype job has expired. Upload the file again.', 404)
    return jsonify(build_prototype_response(job)), 200


@app.route('/api/prototype/preview/<job_id>', methods=['GET'])
def prototype_preview(job_id):
    cleanup_prototype_jobs()
    job = PROTOTYPE_JOBS.get(job_id)
    if not job:
        return prototype_error('job_not_found', 'That prototype job has expired. Upload the file again.', 404)

    preview_path = job.get('preview_path')
    if not preview_path or not os.path.exists(preview_path):
        return prototype_error('preview_missing', 'Preview is not ready for this job yet.', 404)

    from flask import send_file
    return send_file(preview_path, as_attachment=False, download_name=os.path.basename(preview_path))

# Health check
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'live_engine_running': live_engine.status()['running']}), 200

# Front-end routes
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║  Sonic AI Web App                                      ║
    ║  Listening on http://localhost:5000                    ║
    ║                                                        ║
    ║  Dashboard:    http://localhost:5000                   ║
    ║  Register:     http://localhost:5000/register-page     ║
    ║  API Health:   http://localhost:5000/health            ║
    ╚════════════════════════════════════════════════════════╝
    """)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
