from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime

from config import Config
from multi_agent_parse_llm import parse_resume_text_multiagent_deterministic
from extract_text_from_pdf import extract_text_from_pdf

# Database connection
try:
    from database import db_manager
    DATABASE_AVAILABLE = True
    print("Database connection available")
except Exception as e:
    print(f"Database unavailable: {e}")
    DATABASE_AVAILABLE = False
    db_manager = None

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = app.config.get('SECRET_KEY', 'ninermatch-dev-key-2025')
CORS(app)

# Backup storage when database is offline
profiles_memory_store = []

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_resume():
    filepath = None
    try:
        if 'resume' not in request.files:
            return jsonify({'error': 'No resume file provided'}), 400
        
        file = request.files['resume']
        if file.filename == '' or file.filename is None:
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Only PDF files are allowed'}), 400
        
        # Check file size
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        if file_size == 0:
            return jsonify({'error': 'File is empty'}), 400
        
        if file_size > app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024):
            return jsonify({'error': 'File is too large'}), 400
        
        # Save file with timestamp
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(filepath)
        print(f"File saved: {filepath}")
        
        # Parse resume using LLM
        print("Starting LLM resume parsing...")
        resume_text = extract_text_from_pdf(filepath)
        parsed_resume = parse_resume_text_multiagent_deterministic(resume_text)
        
        # Convert to dict for JSON serialization
        parsed_data = parsed_resume.model_dump()
        
        if not parsed_data:
            return jsonify({
                'error': 'Failed to extract meaningful data from resume'
            }), 400
        
        print("LLM resume parsing completed")
        
        # Store both processed data and original parsed backup for the review form
        session['parsed_data'] = parsed_data
        session['llm_parsed_backup'] = parsed_data.copy()  # Store original LLM output as backup
        
        return jsonify({
            'success': True,
            'data': parsed_data,
            'message': 'Resume parsed successfully!'
        })
        
    except Exception as e:
        print(f"Error processing resume: {e}")
        return jsonify({'error': f'Failed to process resume: {str(e)}'}), 500
    
    finally:
        # Clean up uploaded file
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
                print(f"Cleaned up temporary file: {filepath}")
            except Exception as cleanup_error:
                print(f"Warning: Could not delete temporary file: {cleanup_error}")

@app.route('/review')
def review_profile():
    # Get parsed data from session
    parsed_data = session.get('parsed_data', {})
    return render_template('review.html', parsed_data=parsed_data)

@app.route('/submit_profile', methods=['POST'])
def submit_profile():
    try:
        # Handle both JSON and form data
        if request.is_json:
            profile_data = request.get_json()
            pdf_file = None
        else:
            # Get form data
            profile_data = {}
            for key, value in request.form.items():
                if key != 'resume_file':
                    # Handle nested data structure
                    if '.' in key:
                        keys = key.split('.')
                        current = profile_data
                        for k in keys[:-1]:
                            if k not in current:
                                current[k] = {}
                            current = current[k]
                        current[keys[-1]] = value
                    else:
                        profile_data[key] = value
            
            # Get PDF file if uploaded
            pdf_file = request.files.get('resume_file')
        
        if not profile_data:
            return jsonify({'error': 'No profile data provided'}), 400
        
        # Add LLM parsed backup data from session if available
        llm_backup = session.get('llm_parsed_backup', None)
        if llm_backup:
            profile_data['llm_parsed_backup'] = llm_backup
        
        # Save profile - try database first, fallback to memory
        if DATABASE_AVAILABLE and db_manager and db_manager.db is not None:
            # Save to MongoDB with force_new_id=True to always create new profiles
            try:
                profile_id = db_manager.save_profile(profile_data, force_new_id=True)
                
                # If there's a PDF file, store it with the profile ID
                pdf_file_id = None
                if pdf_file and pdf_file.filename:
                    pdf_content = pdf_file.read()
                    pdf_file_id = db_manager.store_pdf(
                        pdf_content, 
                        pdf_file.filename, 
                        profile_id,
                        metadata={'original_name': pdf_file.filename}
                    )
                    
                    # Update profile with PDF file reference
                    if pdf_file_id:
                        db_manager.update_profile(profile_id, {'resume_file_id': pdf_file_id})
                
                # Clear session data after successful save
                session.pop('parsed_data', None)
                session.pop('llm_parsed_backup', None)
                
                return jsonify({
                    'success': True,
                    'profile_id': profile_id,
                    'pdf_file_id': str(pdf_file_id) if pdf_file_id else None,
                    'message': 'Profile saved to database successfully!'
                })
            except Exception as db_error:
                print(f"Database save failed: {db_error}")
                # Fall through to memory storage
        
        # Fallback to in-memory storage
        profile_data['created_at'] = datetime.utcnow().isoformat()
        profile_data['profile_id'] = f"mem_{len(profiles_memory_store) + 1}"
        profiles_memory_store.append(profile_data)
        
        # Clear session data after successful save
        session.pop('parsed_data', None)
        session.pop('llm_parsed_backup', None)
        
        storage_type = "database" if DATABASE_AVAILABLE else "local memory"
        return jsonify({
            'success': True,
            'profile_id': profile_data['profile_id'],
            'message': f'Profile saved to {storage_type} successfully!'
        })
            
    except Exception as e:
        print(f"Error saving profile: {e}")
        return jsonify({'error': f'Failed to save profile: {str(e)}'}), 500

@app.route('/api/profiles', methods=['GET'])
def get_profiles():
    try:
        safe_profiles = []
        
        # Try database first
        if DATABASE_AVAILABLE and db_manager and db_manager.db is not None:
            try:
                profiles = db_manager.get_all_profiles()
                for profile in profiles:
                    safe_profile = {
                        'id': str(profile.get('_id', profile.get('profile_id', 'unknown'))),
                        'name': profile.get('personal_info', {}).get('full_name', 'Anonymous'),
                        'email': profile.get('personal_info', {}).get('email', ''),
                        'major': profile.get('personal_info', {}).get('major', ''),
                        'created_at': profile.get('created_at')
                    }
                    safe_profiles.append(safe_profile)
            except Exception as db_error:
                print(f"Database read failed: {db_error}")
                # Fall through to memory storage
        
        # Fallback to memory storage or if database failed
        if not safe_profiles:
            for profile in profiles_memory_store:
                safe_profile = {
                    'id': profile.get('profile_id', 'unknown'),
                    'name': profile.get('personal_info', {}).get('full_name', 'Anonymous'),
                    'email': profile.get('personal_info', {}).get('email', ''),
                    'major': profile.get('personal_info', {}).get('major', ''),
                    'created_at': profile.get('created_at')
                }
                safe_profiles.append(safe_profile)
        
        storage_type = "database" if DATABASE_AVAILABLE and len(safe_profiles) > len(profiles_memory_store) else "memory"
        return jsonify({
            'success': True,
            'profiles': safe_profiles,
            'count': len(safe_profiles),
            'storage': storage_type
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/profile/<email>', methods=['GET'])
def get_profile_by_email(email):
    try:
        profile = db_manager.get_profile_by_email(email)
        
        if profile:
            profile['_id'] = str(profile['_id'])
            return jsonify({
                'success': True,
                'profile': profile
            })
        else:
            return jsonify({'error': 'Profile not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/resume/<file_id>')
def get_resume(file_id):
    try:
        pdf_data = db_manager.get_pdf(file_id)
        
        if not pdf_data:
            return jsonify({'error': 'Resume not found'}), 404
        
        from flask import send_file
        import io
        
        return send_file(
            io.BytesIO(pdf_data['data']),
            download_name=pdf_data['filename'],
            as_attachment=True,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Error retrieving resume: {e}")
        return jsonify({'error': 'Failed to retrieve resume'}), 500

@app.route('/health')
def health_check():
    try:
        if DATABASE_AVAILABLE and db_manager and db_manager.db is not None:
            db_stats = db_manager.get_database_stats()
            storage_info = {
                'type': 'mongodb',
                'status': 'connected',
                'stats': db_stats
            }
        else:
            storage_info = {
                'type': 'memory',
                'status': 'active',
                'profiles_count': len(profiles_memory_store)
            }
        
        return jsonify({
            'status': 'healthy',
            'storage': storage_info,
            'features': {
                'resume_parsing': True,
                'profile_creation': True,
                'database_storage': DATABASE_AVAILABLE and db_manager and db_manager.db is not None,
                'memory_storage': True
            },
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'healthy',
            'storage': {'type': 'memory', 'status': 'active'},
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })

if __name__ == '__main__':
    print("Starting NinerMatch...")
    print(f"Storage: {'Database' if DATABASE_AVAILABLE else 'Memory'}")
    print("Running on http://localhost:5000")
    
    try:
        app.run(debug=False, host='127.0.0.1', port=5000, threaded=True)
    except Exception as e:
        print(f"Server error: {e}")
        print("Try running on a different port or check if port 5000 is in use")