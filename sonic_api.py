"""
Sonic AI REST API
Backend service for audio analysis via HTTP.

Usage:
    python sonic_api.py

Then POST to: http://localhost:5000/analyze with audio file
"""

from flask import Flask, request, jsonify
import os
import tempfile
from unified_analyzer import SonicAnalyzer

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB max


def save_uploaded_file(uploaded_file):
    """Persist an uploaded file to a temporary path and return that path."""
    suffix = os.path.splitext(uploaded_file.filename or "")[1]
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.close()
    uploaded_file.save(temp_file.name)
    return temp_file.name

# API Routes

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'Sonic AI Analyzer',
        'version': '1.0.0'
    })

@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Analyze audio file.
    
    Request:
        POST /analyze
        Content-Type: multipart/form-data
        file: <audio file>
    
    Response:
        {
            "key": "G Minor",
            "key_confidence": 0.87,
            "tempo": 120,
            "chord": "C Major",
            ...
        }
    """
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save uploaded file temporarily
        temp_path = save_uploaded_file(file)
        
        # Analyze
        analyzer = SonicAnalyzer(enable_caching=True)
        results = analyzer.analyze(record=False, filepath=temp_path)
        
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return jsonify(results), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analyze-url', methods=['POST'])
def analyze_url():
    """
    Analyze audio from a URL.
    
    Request:
        POST /analyze-url
        Content-Type: application/json
        {
            "url": "https://example.com/audio.wav"
        }
    """
    try:
        data = request.get_json(silent=True) or {}
        
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL provided'}), 400
        
        url = data['url']
        
        # Download audio from URL
        import urllib.request
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_file.close()
        temp_path = temp_file.name
        urllib.request.urlretrieve(url, temp_path)
        
        # Analyze
        analyzer = SonicAnalyzer(enable_caching=True)
        results = analyzer.analyze(record=False, filepath=temp_path)
        
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return jsonify(results), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/reference-profiles', methods=['GET'])
def reference_profiles():
    """Get available reference mix profiles."""
    analyzer = SonicAnalyzer()
    return jsonify({
        'reference_profiles': analyzer.reference_profiles
    })

@app.route('/compare', methods=['POST'])
def compare_mixes():
    """
    Compare two audio files.
    
    Request:
        POST /compare
        Content-Type: multipart/form-data
        file1: <audio file 1>
        file2: <audio file 2>
    """
    try:
        if 'file1' not in request.files or 'file2' not in request.files:
            return jsonify({'error': 'Two files required'}), 400
        
        file1 = request.files['file1']
        file2 = request.files['file2']
        
        temp_path1 = save_uploaded_file(file1)
        temp_path2 = save_uploaded_file(file2)
        
        # Analyze both
        analyzer1 = SonicAnalyzer(enable_caching=True)
        results1 = analyzer1.analyze(record=False, filepath=temp_path1)
        
        analyzer2 = SonicAnalyzer(enable_caching=True)
        results2 = analyzer2.analyze(record=False, filepath=temp_path2)
        
        # Compare
        comparison = {
            'file1': {
                'filename': file1.filename,
                'analysis': results1
            },
            'file2': {
                'filename': file2.filename,
                'analysis': results2
            },
            'differences': {
                'key_match': results1['key'] == results2['key'],
                'tempo_diff': abs(results1.get('tempo', 0) - results2.get('tempo', 0)),
                'lufs_diff': abs(results1.get('lufs', 0) - results2.get('lufs', 0)),
                'mix_balance_diff': {
                    'low': abs(results1['mix_balance']['low'] - results2['mix_balance']['low']),
                    'mid': abs(results1['mix_balance']['mid'] - results2['mix_balance']['mid']),
                    'high': abs(results1['mix_balance']['high'] - results2['mix_balance']['high']),
                },
                'complexity_diff': abs(results1.get('harmonic_complexity', 0) - results2.get('harmonic_complexity', 0))
            }
        }
        
        # Cleanup
        if os.path.exists(temp_path1):
            os.remove(temp_path1)
        if os.path.exists(temp_path2):
            os.remove(temp_path2)
        
        return jsonify(comparison), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/batch', methods=['POST'])
def batch_analyze():
    """
    Analyze multiple audio files.
    
    Request:
        POST /batch
        Content-Type: multipart/form-data
        files: [<file1>, <file2>, ...]
    """
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        
        results = {}
        
        for file in files:
            if file.filename:
                temp_path = save_uploaded_file(file)
                
                try:
                    analyzer = SonicAnalyzer(enable_caching=True)
                    analysis = analyzer.analyze(record=False, filepath=temp_path)
                    results[file.filename] = {
                        'status': 'success',
                        'analysis': analysis
                    }
                except Exception as e:
                    results[file.filename] = {
                        'status': 'error',
                        'error': str(e)
                    }
                
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        
        return jsonify(results), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/info', methods=['GET'])
def info():
    """Get API information and capabilities."""
    return jsonify({
        'service': 'Sonic AI Audio Analyzer',
        'version': '1.0.0',
        'endpoints': {
            'POST /analyze': 'Analyze single audio file',
            'POST /analyze-url': 'Analyze audio from URL',
            'POST /batch': 'Analyze multiple files',
            'POST /compare': 'Compare two audio files',
            'GET /reference-profiles': 'Get mix reference profiles',
            'GET /health': 'Health check',
        },
        'analysis_metrics': [
            'key', 'key_confidence',
            'tempo', 'tempo_confidence',
            'chord', 'chord_confidence',
            'mix_balance', 'mix_reference',
            'lufs', 'loudness_category',
            'harmonic_complexity', 'melodic_contour',
            'pitch_distribution', 'spectral_peaks'
        ]
    })

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found. Use GET /info for API documentation'}), 404

if __name__ == '__main__':
    print("""
    ╔════════════════════════════════════════╗
    ║  Sonic AI REST API Server              ║
    ║  Listening on http://localhost:5000    ║
    ║                                        ║
    ║  API Documentation:                    ║
    ║  GET  http://localhost:5000/info       ║
    ║  GET  http://localhost:5000/health     ║
    ╚════════════════════════════════════════╝
    """)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
