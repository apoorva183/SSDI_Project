from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
from functools import wraps
import os
import json
from datetime import datetime

from src.core.config import Config
from src.core.models import AuthHelper
from src.utils.multi_agent_parse_llm import parse_resume_text_multiagent_deterministic
from src.utils.extract_text_from_pdf import extract_text_from_pdf

try:
    from src.resume_search.mongodb_search import search_profiles, index_profile, init_mongodb_search_db
    from src.resume_search.hybrid_search import hybrid_search, search_with_fallback, get_search_capabilities
    from src.resume_search.semantic_search import init_semantic_search, generate_profile_embedding
    RESUME_SEARCH_AVAILABLE = True
    print("MongoDB resume search available")
    print("Hybrid semantic search available")
except Exception as e:
    print(f"Resume search unavailable: {e}")
    RESUME_SEARCH_AVAILABLE = False

try:
    from src.core.database import db_manager
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

profiles_memory_store = []

# AUTO-INITIALIZE SEARCH DATABASES ON STARTUP
if RESUME_SEARCH_AVAILABLE:
    print("🔧 Auto-initializing search databases...")
    try:
        init_mongodb_search_db()
        print("✅ Keyword search database initialized")
    except Exception as e:
        print(f"⚠️  Keyword search initialization failed: {e}")
    
    try:
        init_semantic_search()
        print("✅ Semantic search database initialized")
    except Exception as e:
        print(f"⚠️  Semantic search initialization failed: {e}")
    
# AUTO-INITIALIZE SEARCH DATABASES ON STARTUP
if RESUME_SEARCH_AVAILABLE:
    print("🔧 Auto-initializing search databases...")
    try:
        init_mongodb_search_db()
        print("✅ Keyword search database initialized")
    except Exception as e:
        print(f"⚠️  Keyword search initialization failed: {e}")
    
    try:
        init_semantic_search()
        print("✅ Semantic search database initialized")
    except Exception as e:
        print(f"⚠️  Semantic search initialization failed: {e}")
    
    # AUTO-INDEX EXISTING PROFILES (KEYWORD ONLY - EMBEDDINGS IN BACKGROUND)
    if DATABASE_AVAILABLE and db_manager and db_manager.db is not None:
        try:
            print("🔄 Indexing existing profiles for keyword search...")
            profiles = list(db_manager.db.profiles.find({"status": "active"}))
            indexed_count = 0
            
            for profile in profiles:
                try:
                    profile_id = str(profile.get('_id'))
                    email = profile.get('personal_info', {}).get('email', '')
                    full_name = profile.get('personal_info', {}).get('full_name', '')
                    
                    # Build searchable content from profile
                    content_parts = []
                    
                    # Add personal info
                    if full_name:
                        content_parts.append(f"Name: {full_name}")
                    
                    personal_info = profile.get('personal_info', {})
                    if personal_info.get('major'):
                        content_parts.append(f"Major: {personal_info.get('major')}")
                    if personal_info.get('program'):
                        content_parts.append(f"Program: {personal_info.get('program')}")
                    
                    # Add academic info
                    academic = profile.get('academic', {})
                    courses = academic.get('courses', [])
                    if courses and isinstance(courses, list):
                        courses_str = ', '.join([str(c) for c in courses if isinstance(c, str)])
                        if courses_str:
                            content_parts.append(f"Courses: {courses_str}")
                    
                    certs = academic.get('certifications', [])
                    if certs and isinstance(certs, list):
                        certs_str = ', '.join([str(c) for c in certs if isinstance(c, str)])
                        if certs_str:
                            content_parts.append(f"Certifications: {certs_str}")
                    
                    if academic.get('past_academic_profile_text'):
                        content_parts.append(str(academic.get('past_academic_profile_text')))
                    
                    # Add skills
                    skills = profile.get('skills', {})
                    tech_skills = skills.get('technical', [])
                    if tech_skills and isinstance(tech_skills, list):
                        tech_str = ', '.join([str(s) for s in tech_skills if isinstance(s, str)])
                        if tech_str:
                            content_parts.append(f"Technical Skills: {tech_str}")
                    
                    soft_skills = skills.get('soft_skills', [])
                    if soft_skills and isinstance(soft_skills, list):
                        soft_str = ', '.join([str(s) for s in soft_skills if isinstance(s, str)])
                        if soft_str:
                            content_parts.append(f"Soft Skills: {soft_str}")
                    
                    # Add interests
                    interests = profile.get('interests', {})
                    academic_int = interests.get('academic', [])
                    if academic_int and isinstance(academic_int, list):
                        acad_str = ', '.join([str(i) for i in academic_int if isinstance(i, str)])
                        if acad_str:
                            content_parts.append(f"Academic Interests: {acad_str}")
                    
                    personal_int = interests.get('personal', [])
                    if personal_int and isinstance(personal_int, list):
                        pers_str = ', '.join([str(i) for i in personal_int if isinstance(i, str)])
                        if pers_str:
                            content_parts.append(f"Personal Interests: {pers_str}")
                    
                    # Add LLM parsed content if available
                    if profile.get('llm_parsed_backup'):
                        llm_data = profile.get('llm_parsed_backup', {})
                        if llm_data.get('past_academic_profile_text'):
                            content_parts.append(str(llm_data.get('past_academic_profile_text')))
                    
                    content = ' '.join(content_parts)
                    
                    if content.strip():
                        # Index for keyword search
                        index_profile(profile_id, email, full_name, content)
                        indexed_count += 1
                
                except Exception as e:
                    print(f"⚠️  Error indexing profile: {e}")
                    continue
            
            print(f"✅ Indexed {indexed_count} profiles for keyword search")
            print(f"ℹ️  Semantic embeddings will be generated in background...")
            
        except Exception as e:
            print(f"⚠️  Profile indexing failed: {e}")

# BACKGROUND EMBEDDING GENERATION FUNCTION
def generate_embeddings_background():
    """Generate embeddings in background after app starts"""
    import time
    time.sleep(5)  # Wait for Flask to fully start
    
    print("\n🔄 Background: Starting semantic embedding generation...")
    
    if not DATABASE_AVAILABLE or not db_manager or db_manager.db is None:
        return
    
    try:
        profiles = list(db_manager.db.profiles.find({"status": "active"}))
        semantic_count = 0
        
        for profile in profiles:
            try:
                profile_id = str(profile.get('_id'))
                email = profile.get('personal_info', {}).get('email', '')
                full_name = profile.get('personal_info', {}).get('full_name', '')
                
                # Build content
                content_parts = []
                if full_name:
                    content_parts.append(f"Name: {full_name}")
                
                personal_info = profile.get('personal_info', {})
                if personal_info.get('major'):
                    content_parts.append(f"Major: {personal_info.get('major')}")
                if personal_info.get('program'):
                    content_parts.append(f"Program: {personal_info.get('program')}")
                
                academic = profile.get('academic', {})
                courses = academic.get('courses', [])
                if courses and isinstance(courses, list):
                    courses_str = ', '.join([str(c) for c in courses if isinstance(c, str)])
                    if courses_str:
                        content_parts.append(f"Courses: {courses_str}")
                
                certs = academic.get('certifications', [])
                if certs and isinstance(certs, list):
                    certs_str = ', '.join([str(c) for c in certs if isinstance(c, str)])
                    if certs_str:
                        content_parts.append(f"Certifications: {certs_str}")
                
                if academic.get('past_academic_profile_text'):
                    content_parts.append(str(academic.get('past_academic_profile_text')))
                
                skills = profile.get('skills', {})
                tech_skills = skills.get('technical', [])
                if tech_skills and isinstance(tech_skills, list):
                    tech_str = ', '.join([str(s) for s in tech_skills if isinstance(s, str)])
                    if tech_str:
                        content_parts.append(f"Technical Skills: {tech_str}")
                
                soft_skills = skills.get('soft_skills', [])
                if soft_skills and isinstance(soft_skills, list):
                    soft_str = ', '.join([str(s) for s in soft_skills if isinstance(s, str)])
                    if soft_str:
                        content_parts.append(f"Soft Skills: {soft_str}")
                
                interests = profile.get('interests', {})
                academic_int = interests.get('academic', [])
                if academic_int and isinstance(academic_int, list):
                    acad_str = ', '.join([str(i) for i in academic_int if isinstance(i, str)])
                    if acad_str:
                        content_parts.append(f"Academic Interests: {acad_str}")
                
                personal_int = interests.get('personal', [])
                if personal_int and isinstance(personal_int, list):
                    pers_str = ', '.join([str(i) for i in personal_int if isinstance(i, str)])
                    if pers_str:
                        content_parts.append(f"Personal Interests: {pers_str}")
                
                if profile.get('llm_parsed_backup'):
                    llm_data = profile.get('llm_parsed_backup', {})
                    if llm_data.get('past_academic_profile_text'):
                        content_parts.append(str(llm_data.get('past_academic_profile_text')))
                
                content = ' '.join(content_parts)
                
                if content.strip():
                    # Generate embedding
                    time.sleep(0.5)  # Rate limiting
                    if generate_profile_embedding(profile_id, email, full_name, content):
                        semantic_count += 1
                        print(f"✅ Generated embedding {semantic_count} for {email}")
            
            except Exception as e:
                print(f"⚠️  Background embedding error for {profile_id}: {str(e)[:100]}")
                continue
        
        print(f"\n✅ Background: Generated {semantic_count} semantic embeddings")
        
    except Exception as e:
        print(f"⚠️  Background embedding generation failed: {e}")

# Start background embedding generation in a thread
import threading
if RESUME_SEARCH_AVAILABLE and DATABASE_AVAILABLE:
    bg_thread = threading.Thread(target=generate_embeddings_background, daemon=True)
    bg_thread.start()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def swipe_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login_page'))
        
        user_email = session.get('user_email')
        try:
            if DATABASE_AVAILABLE and db_manager and db_manager.db is not None:
                swipe_count = db_manager.db.swipe_feedback.count_documents({'user_email': user_email})
                if swipe_count == 0:
                    from flask import flash
                    return redirect(url_for('matches_page'))
        except Exception as e:
            print(f"Error checking swipe count: {e}")
        
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    is_logged_in = 'user_email' in session
    user_name = session.get('user_name', '')
    return render_template('index.html', is_logged_in=is_logged_in, user_name=user_name)

@app.route('/login')
def login_page():
    if 'user_email' in session:
        return redirect(url_for('matches_page'))
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        if DATABASE_AVAILABLE and db_manager and db_manager.db is not None:
            user = db_manager.db.profiles.find_one({'personal_info.email': email})
            
            if not user:
                return jsonify({'error': 'Invalid email or password'}), 401
            
            stored_password_hash = user.get('personal_info', {}).get('password_hash', '')
            if not stored_password_hash or not AuthHelper.check_password(stored_password_hash, password):
                return jsonify({'error': 'Invalid email or password'}), 401
            
            session['user_email'] = email
            session['user_name'] = user.get('personal_info', {}).get('full_name', '')
            session['user_id'] = str(user.get('_id', ''))
            
            return jsonify({
                'success': True,
                'message': 'Login successful!',
                'user': {
                    'email': email,
                    'name': session['user_name']
                }
            })
        else:
            return jsonify({'error': 'Database unavailable'}), 503
            
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'An error occurred during login'}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/logout')
def logout_page():
    session.clear()
    return redirect(url_for('index'))

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
        
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        if file_size == 0:
            return jsonify({'error': 'File is empty'}), 400
        
        if file_size > app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024):
            return jsonify({'error': 'File is too large'}), 400
        
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(filepath)
        print(f"File saved: {filepath}")
        
        print("Starting LLM resume parsing...")
        resume_text = extract_text_from_pdf(filepath)
        
        try:
            parsed_resume = parse_resume_text_multiagent_deterministic(resume_text)
            parsed_data = parsed_resume.model_dump()
            print("LLM resume parsing completed successfully")
        except Exception as e:
            print(f"LLM parsing failed: {e}")
            print("Using basic pattern-based parser as fallback...")
            
            # Import and use basic parser
            from src.utils.basic_resume_parser import parse_resume_basic
            parsed_data = parse_resume_basic(resume_text)
            parsed_data["parsing_method"] = "basic_fallback"
            print("Basic resume parsing completed")
        
        if not parsed_data:
            return jsonify({
                'error': 'Failed to extract meaningful data from resume'
            }), 400
        
        print("LLM resume parsing completed")
        
        session['parsed_data'] = parsed_data
        session['llm_parsed_backup'] = parsed_data.copy()
        
        return jsonify({
            'success': True,
            'data': parsed_data,
            'message': 'Resume parsed successfully!'
        })
        
    except Exception as e:
        print(f"Error processing resume: {e}")
        return jsonify({'error': f'Failed to process resume: {str(e)}'}), 500
    
    finally:
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
                print(f"Cleaned up temporary file: {filepath}")
            except Exception as cleanup_error:
                print(f"Warning: Could not delete temporary file: {cleanup_error}")

@app.route('/review')
def review_profile():
    parsed_data = session.get('parsed_data', {})
    is_logged_in = 'user_email' in session
    user_name = session.get('user_name', '')
    import time
    cache_buster = int(time.time())
    return render_template('review.html', parsed_data=parsed_data, cache_buster=cache_buster, 
                          is_logged_in=is_logged_in, user_name=user_name)

@app.route('/search')
def search_page():
    is_logged_in = 'user_email' in session
    user_name = session.get('user_name', '')
    user_email = session.get('user_email', '')
    return render_template('search.html', is_logged_in=is_logged_in, user_name=user_name, user_email=user_email)

@app.route('/api/search')
def api_search():
    """Search profiles using advanced hybrid search (keyword + semantic)"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            return jsonify({
                'success': True,
                'results': [],
                'message': 'Please enter a search query'
            })
        
        if not RESUME_SEARCH_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Resume search is not available. Please run sync_mongodb_search.py first.'
            }), 503
        
        # Get search parameters
        topk = int(request.args.get('topk', 10))
        use_semantic = request.args.get('semantic', 'true').lower() == 'true'
        
        # Perform hybrid search with fallback
        search_result = search_with_fallback(query, topk=topk)
        
        # Add profile links to results
        for result in search_result['results']:
            result['type'] = 'profile'
            result['profile_link'] = f"/profile/{result['profile_id']}"
        
        return jsonify({
            'success': True,
            'results': search_result['results'],
            'query': query,
            'count': len(search_result['results']),
            'total_found': search_result['total_found'],
            'methods_used': search_result['methods_used'],
            'semantic_available': search_result['semantic_available'],
            'search_type': 'hybrid' if len(search_result['methods_used']) > 1 else search_result['methods_used'][0] if search_result['methods_used'] else 'keyword'
        })
        
    except Exception as e:
        print(f"Resume search error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/search-capabilities')
def api_search_capabilities():
    """Get information about available search capabilities"""
    try:
        if RESUME_SEARCH_AVAILABLE:
            capabilities = get_search_capabilities()
            
            # Get additional statistics
            from src.resume_search.mongodb_search import get_index_stats
            from src.resume_search.semantic_search import get_stats as get_embedding_stats
            
            keyword_stats = get_index_stats()
            semantic_stats = get_embedding_stats()
            
            return jsonify({
                'success': True,
                'capabilities': capabilities,
                'statistics': {
                    'keyword_search': {
                        'indexed_profiles': keyword_stats.get('indexed_profiles', 0),
                        'database_path': keyword_stats.get('database_path', 'N/A')
                    },
                    'semantic_search': {
                        'total_embeddings': semantic_stats.get('total_embeddings', 0),
                        'available': semantic_stats.get('semantic_search_available', False),
                        'latest_update': semantic_stats.get('latest_update', 'Never')
                    }
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Search functionality not available'
            }), 503
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
        
        # Hash password before saving
        if 'personal_info' in profile_data and 'password' in profile_data['personal_info']:
            password = profile_data['personal_info'].pop('password')
            profile_data['personal_info']['password_hash'] = AuthHelper.hash_password(password)
        
        # Check if email already exists
        email = profile_data.get('personal_info', {}).get('email', '').strip().lower()
        if DATABASE_AVAILABLE and db_manager and db_manager.db is not None:
            existing_user = db_manager.db.profiles.find_one({'personal_info.email': email})
            if existing_user:
                return jsonify({'error': 'An account with this email already exists. Please login instead.'}), 409
        
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
                
                # Auto-login after successful registration
                session['user_email'] = email
                session['user_name'] = profile_data.get('personal_info', {}).get('full_name', '')
                session['user_id'] = profile_id
                
                # Index profile for search and generate embedding (if available)
                if RESUME_SEARCH_AVAILABLE:
                    try:
                        from src.utils.sync_mongodb_search import extract_resume_text
                        full_name = profile_data.get('personal_info', {}).get('full_name', '')
                        content = extract_resume_text(profile_data)
                        
                        if content and len(content) >= 50:
                            # Index for keyword search
                            keyword_success = index_profile(
                                profile_id=profile_id,
                                email=email,
                                full_name=full_name,
                                content=content,
                                upload_date=str(profile_data.get('created_at', '')),
                                updated_at=str(profile_data.get('updated_at', ''))
                            )
                            
                            # Generate semantic embedding
                            embedding_success = generate_profile_embedding(
                                profile_id=profile_id,
                                email=email,
                                full_name=full_name,
                                content=content
                            )
                            
                            if keyword_success and embedding_success:
                                print(f"✅ Profile indexed with semantic embedding: {email}")
                            elif keyword_success:
                                print(f"✅ Profile indexed (keyword only): {email}")
                            else:
                                print(f"⚠️ Failed to index profile: {email}")
                                
                    except Exception as index_error:
                        print(f"⚠️ Failed to index profile for search: {index_error}")
                
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

@app.route('/api/search-courses')
def search_courses_api():
    try:
        import csv
        from pathlib import Path
        
        query = request.args.get('q', '').strip()
        limit = min(int(request.args.get('limit', 20)), 50)  # Max 50 results
        
        if not query:
            return jsonify({'success': True, 'courses': []})
        
        # Load and search courses directly in this function
        csv_path = Path(__file__).parent / "data" / "courses.csv"
        courses = []
        matches = {}
        
        if csv_path.exists():
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row['Course'].strip() and row['Code'].strip() and row['Title'].strip():
                        course = {
                            'department': row['Course'].strip(),
                            'code': row['Code'].strip(), 
                            'title': row['Title'].strip(),
                            'full_code': f"{row['Course'].strip()} {row['Code'].strip()}"
                        }
                        courses.append(course)
        
        # Search logic
        query_upper = query.upper()
        for course in courses:
            course_id = f"{course['department']}_{course['code']}"
            score = 0
            
            # Exact full code match (highest score)
            if query_upper == course['full_code'].upper():
                score = 100
            # Partial matches
            elif query_upper in course['full_code'].upper():
                score = 80
            elif query_upper in course['title'].upper():
                score = 60
            elif any(word in course['title'].upper() for word in query_upper.split()):
                score = 40
            elif course['department'].upper().startswith(query_upper):
                score = 30
            
            if score > 0:
                matches[course_id] = (course, score)
        
        # Sort by score and format results
        sorted_matches = sorted(matches.values(), key=lambda x: x[1], reverse=True)
        results = []
        
        for course, score in sorted_matches[:limit]:
            results.append({
                'department': course['department'],
                'code': course['code'],
                'title': course['title'],
                'full_code': course['full_code'],
                'display_text': f"{course['full_code']}: {course['title']}",
                'score': score
            })
        
        return jsonify({
            'success': True,
            'courses': results,
            'query': query
        })
        
    except Exception as e:
        print(f"Course search error: {e}")
        return jsonify({'error': 'Failed to search courses'}), 500

@app.route('/matches')
@login_required
def matches_page():
    import time
    cache_buster = int(time.time())
    user_email = session.get('user_email', '')
    user_name = session.get('user_name', '')
    return render_template('matches.html', cache_buster=cache_buster, user_email=user_email, user_name=user_name)

def _extract_shared_items(commonalities, keyword):
    """Extract shared items from commonalities list based on keyword"""
    shared_items = []
    for commonality in commonalities:
        if keyword in commonality.lower():
            # Extract items after the colon
            if ':' in commonality:
                items_str = commonality.split(':', 1)[1].strip()
                items = [item.strip() for item in items_str.split(',')]
                shared_items.extend(items)
    return shared_items

@app.route('/api/start-fresh-session', methods=['POST'])
@login_required
def start_fresh_session():
    """Start a fresh swipe session (clear session tracking)"""
    try:
        # Clear the current session ID to start fresh
        if 'swipe_session_id' in session:
            del session['swipe_session_id']
        
        return jsonify({'success': True, 'message': 'Fresh session started'})
    except Exception as e:
        print(f"Error starting fresh session: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/find-matches')
@login_required
def find_matches():
    """Find potential matches for the current user"""
    try:
        from src.utils.similarity_matcher import student_matcher, set_matcher_db
        
        set_matcher_db(db_manager)
        
        # Get user email from session instead of request parameter
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({'error': 'User not logged in'}), 401
        
        # Get user profile from database
        user_profile = db_manager.get_profile_by_email(user_email)
        
        # If exact match not found, try finding by partial email match
        if not user_profile and '@' in user_email:
            email_base = user_email.split('@')[0]  # Get username part
            domain = user_email.split('@')[1]     # Get domain part
            
            # Search for emails that start with the base email
            search_pattern = f"{email_base}@{domain}"
            potential_profiles = list(db_manager.db.profiles.find({
                "personal_info.email": {"$regex": f"^{search_pattern.replace('.', '\\.')}"}, 
                "status": "active"
            }))
            
            if potential_profiles:
                user_profile = potential_profiles[0]  # Use first match
                print(f"✅ Found profile with similar email: {user_profile.get('personal_info', {}).get('email')}")
        
        if not user_profile:
            return jsonify({'error': 'User profile not found'}), 404
        
        # Debug: Print sample data to understand structure
        print(f"Debug - User profile keys: {list(user_profile.keys())}")
        if user_profile.get('skills'):
            print(f"Debug - Skills structure: {user_profile.get('skills')}")
        
        print("🔍 Starting ML-based similarity matching...")
        
        # Find matches - Lower threshold to ensure more matches for swiping
        raw_matches = student_matcher.find_matches_for_user(
            user_profile, 
            exclude_user_id=user_profile.get('profile_id'),
            limit=20,  # Get more matches for swiping
            min_similarity=0.01  # Very low threshold to include almost all potential matches
        )
        
        print(f"✅ ML similarity algorithm found {len(raw_matches)} matches")
        if raw_matches:
            for i, match in enumerate(raw_matches[:3]):  # Log first 3 matches
                print(f"Match {i+1}: {match.get('similarity_score', 0):.2f} similarity score")
        
        # Format matches for frontend
        formatted_matches = []
        for match in raw_matches:
            # DEBUG: Print the actual match structure
            print(f"🔍 DEBUG Match structure keys: {list(match.keys())}")
            print(f"🔍 DEBUG personal_info: {match.get('personal_info')}")
            print(f"🔍 DEBUG skills structure: {match.get('skills')}")
            print(f"🔍 DEBUG past_academic_profile_text: '{match.get('past_academic_profile_text', 'NOT_FOUND')}'")
            print(f"🔍 DEBUG academic section: {match.get('academic', {})}")
            
            # Extract skills properly - handle both string and dict formats
            skills_data = match.get('skills', {})
            technical_skills = skills_data.get('technical', []) if isinstance(skills_data, dict) else []
            
            # Convert skill objects to simple format
            formatted_skills = []
            for skill in technical_skills:
                if isinstance(skill, dict):
                    formatted_skills.append({
                        'skillName': skill.get('skillName', skill.get('name', 'Unknown')),
                        'skillProficiency': skill.get('skillProficiency', skill.get('proficiency', ''))
                    })
                else:
                    formatted_skills.append({'skillName': str(skill), 'skillProficiency': ''})
            
            # Extract languages properly
            languages = match.get('background', {}).get('languages', [])
            if not languages:
                languages = match.get('personal_info', {}).get('languages', [])
            
            # Extract courses properly
            academic_data = match.get('academic', {})
            courses = academic_data.get('courses', [])
            if not courses:
                courses = academic_data.get('courses_taken', [])
            
            formatted_match = {
                'profile': {
                    'profile_id': match.get('profile_id'),
                    'name': match.get('personal_info', {}).get('full_name', 'Student'),
                    'full_name': match.get('personal_info', {}).get('full_name', 'Student'),
                    'email': match.get('personal_info', {}).get('email', ''),
                    'major': match.get('personal_info', {}).get('major', 'Computer Science'),
                    'academic_level': match.get('personal_info', {}).get('year', 'Graduate'),
                    'skills': formatted_skills,
                    'courses_taken': courses,
                    'languages': languages,
                    'past_academic_background': match.get('past_academic_profile_text', '')
                },
                'similarity': {
                    'overall_score': match.get('similarity_score', 0),
                    'similarity_details': {
                        'shared_skills': _extract_shared_items(match.get('commonalities', []), 'skills'),
                        'shared_courses': _extract_shared_items(match.get('commonalities', []), 'taking'),
                        'shared_languages': _extract_shared_items(match.get('commonalities', []), 'speak'),
                        'academic_level_match': any('Both are' in c for c in match.get('commonalities', [])),
                        'commonalities': match.get('commonalities', [])
                    }
                }
            }
            
            # DEBUG: Print what we're sending to frontend
            print(f"🔍 FRONTEND DATA - past_academic_background: '{formatted_match['profile']['past_academic_background']}'")
            print(f"🔍 FRONTEND DATA - name: {formatted_match['profile']['full_name']}")
            
            formatted_matches.append(formatted_match)
        
        return jsonify({
            'success': True,
            'matches': formatted_matches,
            'count': len(formatted_matches)
        })
        
    except Exception as e:
        print(f"Error finding matches: {e}")
        return jsonify({'error': 'Failed to find matches'}), 500

@app.route('/api/swipe-feedback', methods=['POST'])
def swipe_feedback():
    """Record user swipe feedback to improve future recommendations"""
    try:
        from src.utils.similarity_matcher import student_matcher, set_matcher_db
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # DEBUG: Print what we received
        print(f"📥 Received swipe feedback:")
        print(f"   Data keys: {list(data.keys())}")
        print(f"   user_id: {data.get('user_id')}")
        print(f"   user_email: {data.get('user_email')}")
        print(f"   matched_user_id: {data.get('matched_user_id')}")
        print(f"   matched_user_email: {data.get('matched_user_email')}")
        print(f"   feedback: {data.get('feedback')}")
        
        user_id = data.get('user_id')
        matched_user_id = data.get('matched_user_id') 
        feedback = data.get('feedback')  # 'like' or 'dislike'
        similarity_features = data.get('similarity_features', {})
        
        if not all([user_id, matched_user_id, feedback]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Set up matcher
        set_matcher_db(db_manager)
        
        # Get or create session ID for tracking current swipe session
        session_id = session.get('swipe_session_id')
        if not session_id:
            session_id = f"session_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{user_id}"
            session['swipe_session_id'] = session_id
        
        # Store feedback in database
        feedback_doc = {
            'user_id': user_id,
            'user_email': session.get('user_email'),  # Get user email from session
            'matched_user_id': matched_user_id,
            'matched_user_email': data.get('matched_user_email'),  # Add this field
            'feedback': feedback,
            'similarity_features': similarity_features,
            'session_id': session_id,  # Track which session this swipe belongs to
            'timestamp': datetime.utcnow()
        }
        
        print(f"💾 Saving to database: {feedback_doc}")
        
        result = db_manager.db.swipe_feedback.insert_one(feedback_doc)
        
        print(f"✅ Saved with ID: {result.inserted_id}")
        
        # Update user preferences based on feedback
        # Convert feedback to numerical values and feature importance
        feedback_value = 1 if feedback == 'like' else -1
        
        # Create feedback data for preference learning
        feature_feedback = []
        for feature, score in similarity_features.items():
            # Weight the feedback by how much this feature contributed to the match
            weighted_feedback = feedback_value * score
            feature_feedback.append((feature, weighted_feedback))
        
        # Update user preferences
        updated_weights = student_matcher.update_user_preferences(user_id, feature_feedback)
        
        return jsonify({
            'success': True,
            'message': 'Feedback recorded',
            'updated_preferences': updated_weights
        })
        
    except Exception as e:
        print(f"Error recording swipe feedback: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to record feedback'}), 500

@app.route('/api/get-connections')
@login_required
def get_connections():
    """Get all connections/matches for a user"""
    try:
        # Get user email from session instead of request parameter
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({'error': 'User not logged in'}), 401
        
        if not DATABASE_AVAILABLE or not db_manager:
            return jsonify({'error': 'Database not available'}), 500
        
        # Get user profile
        user_profile = db_manager.get_profile_by_email(user_email)
        if not user_profile:
            return jsonify({'error': 'User profile not found'}), 404
        
        # Check if user wants fresh session results only
        fresh_only = request.args.get('fresh_only', 'false').lower() == 'true'
        session_id = session.get('swipe_session_id')
        
        print(f"🔍 Getting connections for {user_email} (fresh_only: {fresh_only}, session: {session_id})")
        
        # Build query based on fresh_only flag
        query = {'user_email': user_email}
        if fresh_only and session_id:
            query['session_id'] = session_id
        
        # Get swipe feedback using email (since profile_id isn't consistently available)
        swipe_feedback = list(db_manager.db.swipe_feedback.find(query))
        
        print(f"📊 Found {len(swipe_feedback)} swipe records for this user")
        
        # Get emails of profiles that user liked
        liked_emails = [
            feedback['matched_user_email'] 
            for feedback in swipe_feedback 
            if feedback.get('feedback') == 'like' and feedback.get('matched_user_email')
        ]
        
        # Get profiles that liked this user (swipes where matched_user_email is this user)
        liked_by_feedback = list(db_manager.db.swipe_feedback.find({
            'matched_user_email': user_email,
            'feedback': 'like'
        }))
        
        liked_by_emails = [
            feedback['user_email']
            for feedback in liked_by_feedback
            if feedback.get('user_email')
        ]
        
        print(f"👍 User liked: {len(liked_emails)} profiles")
        print(f"❤️ Liked by: {len(liked_by_emails)} profiles")
        
        # For fresh session, only show users liked in this session
        if fresh_only:
            connection_emails = liked_emails
            print(f"🔗 Fresh session connections: {len(connection_emails)}")
        else:
            connection_emails = list(set(liked_emails + liked_by_emails))
            print(f"🔗 Total unique connections: {len(connection_emails)}")

        # Get full profiles for all connections
        connections = []
        for email in connection_emails:
            profile = db_manager.get_profile_by_email(email)
            
            if profile:
                # Remove ObjectId for JSON serialization
                if '_id' in profile:
                    profile['_id'] = str(profile['_id'])
                
                # Add match metadata
                profile['likedByMe'] = email in liked_emails
                profile['likedMe'] = email in liked_by_emails
                profile['mutualMatch'] = profile['likedByMe'] and profile['likedMe']
                
                from src.utils.similarity_matcher import student_matcher, set_matcher_db
                set_matcher_db(db_manager)
                
                try:
                    similarity_score, breakdown = student_matcher.calculate_similarity(user_profile, profile)
                    profile['similarity_score'] = similarity_score
                    
                    # Add detailed similarity breakdown
                    profile['similarity_details'] = {
                        'shared_skills': _extract_shared_items(breakdown.get('commonalities', []), 'skills'),
                        'shared_courses': _extract_shared_items(breakdown.get('commonalities', []), 'taking'),
                        'shared_languages': _extract_shared_items(breakdown.get('commonalities', []), 'speak'),
                        'academic_level_match': any('Both are' in c for c in breakdown.get('commonalities', [])),
                        'commonalities': breakdown.get('commonalities', [])
                    }
                except Exception as sim_error:
                    print(f"Error calculating similarity: {sim_error}")
                    profile['similarity_score'] = 0
                    profile['similarity_details'] = {
                        'shared_skills': [],
                        'shared_courses': [],
                        'shared_languages': [],
                        'academic_level_match': False,
                        'commonalities': []
                    }
                
                connections.append(profile)
        
        # Sort by mutual matches first, then by similarity score
        connections.sort(key=lambda x: (x.get('mutualMatch', False), x.get('similarity_score', 0)), reverse=True)
        
        print(f"✅ Returning {len(connections)} connections")
        
        return jsonify({
            'success': True,
            'connections': connections,
            'count': len(connections),
            'stats': {
                'liked_by_me': len(liked_emails),
                'liked_me': len(liked_by_emails),
                'mutual_matches': sum(1 for c in connections if c.get('mutualMatch'))
            }
        })
        
    except Exception as e:
        print(f"Error getting connections: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to get connections: {str(e)}'}), 500

@app.route('/results')
@login_required
def results_page():
    """Results/Connections page - requires login"""
    user_email = session.get('user_email', '')
    user_name = session.get('user_name', '')
    return render_template('results.html', user_email=user_email, user_name=user_name)

@app.route('/edit-profile')
@login_required
def edit_profile_page():
    """Edit profile page"""
    import time
    cache_buster = int(time.time())
    user_email = session.get('user_email', '')
    user_name = session.get('user_name', '')
    return render_template('edit_profile.html', cache_buster=cache_buster, user_email=user_email, user_name=user_name)

@app.route('/api/get-my-profile')
@login_required
def get_my_profile():
    """Get current user's profile"""
    try:
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({'error': 'Not logged in'}), 401
        
        if DATABASE_AVAILABLE and db_manager and db_manager.db is not None:
            profile = db_manager.get_profile_by_email(user_email)
            if profile:
                # Convert ObjectId to string for JSON serialization
                profile['_id'] = str(profile['_id'])
                return jsonify({'success': True, 'profile': profile})
            else:
                return jsonify({'error': 'Profile not found'}), 404
        else:
            return jsonify({'error': 'Database unavailable'}), 503
    except Exception as e:
        print(f"Error getting profile: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/update-profile', methods=['PUT'])
@login_required
def update_profile():
    """Update user's profile"""
    try:
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({'error': 'Not logged in'}), 401
        
        profile_data = request.get_json()
        if not profile_data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Don't allow email changes
        if 'personal_info' in profile_data and 'email' in profile_data['personal_info']:
            del profile_data['personal_info']['email']
        
        # Don't allow password changes through this endpoint
        if 'personal_info' in profile_data and 'password' in profile_data['personal_info']:
            del profile_data['personal_info']['password']
        if 'personal_info' in profile_data and 'password_hash' in profile_data['personal_info']:
            del profile_data['personal_info']['password_hash']
        
        if DATABASE_AVAILABLE and db_manager and db_manager.db is not None:
            # Get current profile
            current_profile = db_manager.get_profile_by_email(user_email)
            if not current_profile:
                return jsonify({'error': 'Profile not found'}), 404
            
            # Update profile fields
            update_data = {}
            
            # Update personal info (except email and password)
            if 'personal_info' in profile_data:
                for key, value in profile_data['personal_info'].items():
                    if key not in ['email', 'password', 'password_hash', 'email_hash']:
                        update_data[f'personal_info.{key}'] = value
            
            # Update other sections
            for section in ['background', 'academic', 'skills', 'interests']:
                if section in profile_data:
                    for key, value in profile_data[section].items():
                        update_data[f'{section}.{key}'] = value
            
            # Update professional experience
            if 'professional_experience' in profile_data:
                update_data['professional_experience'] = profile_data['professional_experience']
            
            # Update past_academic_profile_text at root level
            if 'past_academic_profile_text' in profile_data:
                update_data['academic.past_academic_profile_text'] = profile_data['past_academic_profile_text']
            
            # Perform update
            result = db_manager.db.profiles.update_one(
                {'personal_info.email': user_email},
                {'$set': update_data}
            )
            
            if result.modified_count > 0 or result.matched_count > 0:
                # Update session if name changed
                if 'personal_info.full_name' in update_data:
                    session['user_name'] = update_data['personal_info.full_name']
                
                return jsonify({'success': True, 'message': 'Profile updated successfully'})
            else:
                return jsonify({'error': 'No changes made'}), 400
        else:
            return jsonify({'error': 'Database unavailable'}), 503
            
    except Exception as e:
        print(f"Error updating profile: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/list-profiles')
def list_profiles():
    """Debug endpoint to list all profile emails"""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        profiles = list(db_manager.db.profiles.find(
            {"status": "active"}, 
            {"personal_info.email": 1, "personal_info.full_name": 1, "_id": 0}
        ).limit(10))
        
        return jsonify({
            'success': True,
            'count': len(profiles),
            'profiles': profiles
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug-profile/<email>')
def debug_profile(email):
    """Debug endpoint to check profile structure"""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    profile = db_manager.get_profile_by_email(email)
    if not profile:
        return jsonify({'error': 'Profile not found'}), 404
    
    # Remove ObjectId for JSON serialization
    if '_id' in profile:
        profile['_id'] = str(profile['_id'])
    
    return jsonify(profile)

@app.route('/api/debug-swipes/<email>')
def debug_swipes(email):
    """Debug endpoint to check swipe feedback"""
    if not DATABASE_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        # Get user profile to find profile_id
        profile = db_manager.get_profile_by_email(email)
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404
        
        user_id = profile.get('profile_id')
        
        # Get all swipe feedback for this user
        swipes_by_user = list(db_manager.db.swipe_feedback.find({'user_id': user_id}))
        swipes_for_user = list(db_manager.db.swipe_feedback.find({'matched_user_id': user_id}))
        
        # Convert ObjectId to string
        for swipe in swipes_by_user + swipes_for_user:
            if '_id' in swipe:
                swipe['_id'] = str(swipe['_id'])
            if 'timestamp' in swipe:
                swipe['timestamp'] = str(swipe['timestamp'])
        
        return jsonify({
            'success': True,
            'email': email,
            'profile_id': user_id,
            'swipes_by_user': swipes_by_user,
            'swipes_for_user': swipes_for_user,
            'total_swipes': len(swipes_by_user),
            'total_received': len(swipes_for_user)
        })
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/test-ml-algorithm')
def test_ml_algorithm():
    """Test endpoint to verify ML similarity algorithm is working"""
    try:
        from src.utils.similarity_matcher import student_matcher, set_matcher_db
        
        set_matcher_db(db_manager)
        
        # Get sample profiles for testing
        all_profiles = list(db_manager.db.profiles.find({"status": "active"}).limit(2))
        
        if len(all_profiles) < 2:
            return jsonify({
                'error': 'Need at least 2 profiles to test similarity',
                'profile_count': len(all_profiles)
            })
        
        # Test similarity calculation
        profile1 = all_profiles[0] 
        profile2 = all_profiles[1]
        
        print(f"🧪 Testing ML algorithm with profiles: {profile1.get('personal_info', {}).get('full_name')} vs {profile2.get('personal_info', {}).get('full_name')}")
        
        similarity_score, breakdown = student_matcher.calculate_similarity(profile1, profile2)
        
        return jsonify({
            'success': True,
            'ml_algorithm_working': True,
            'test_results': {
                'profile1_name': profile1.get('personal_info', {}).get('full_name', 'Unknown'),
                'profile2_name': profile2.get('personal_info', {}).get('full_name', 'Unknown'),
                'similarity_score': similarity_score,
                'breakdown': breakdown,
                'algorithm_weights': student_matcher.default_weights
            }
        })
        
    except Exception as e:
        print(f"❌ ML Algorithm Test Failed: {e}")
        return jsonify({
            'success': False,
            'ml_algorithm_working': False,
            'error': str(e)
        }), 500

@app.route('/api/manual-test-matching/<email>')
def manual_test_matching(email):
    """Manual test of the entire matching pipeline"""
    try:
        print(f"🔬 MANUAL TEST: Starting complete matching test for {email}")
        
        from src.utils.similarity_matcher import student_matcher, set_matcher_db
        
        set_matcher_db(db_manager)
        
        # Get user profile
        user_profile = db_manager.get_profile_by_email(email)
        if not user_profile:
            return jsonify({'error': 'User profile not found', 'email': email}), 404
            
        print(f"✅ Found user profile: {user_profile.get('personal_info', {}).get('full_name', 'Unknown')}")
        
        # Get all other profiles for comparison
        all_profiles = list(db_manager.db.profiles.find({
            "status": "active", 
            "personal_info.email": {"$ne": email}
        }))
        
        print(f"📊 Found {len(all_profiles)} other profiles to compare against")
        
        if len(all_profiles) == 0:
            return jsonify({
                'error': 'No other profiles found for matching',
                'user_profile_exists': True,
                'other_profiles_count': 0
            })
        
        # Test ML algorithm on first profile
        test_profile = all_profiles[0]
        similarity_score, breakdown = student_matcher.calculate_similarity(user_profile, test_profile)
        
        print(f"🎯 ML Algorithm calculated similarity: {similarity_score:.3f}")
        
        # Get actual matches using the full pipeline
        matches = student_matcher.find_matches_for_user(
            user_profile,
            exclude_user_id=user_profile.get('profile_id'),
            limit=5,
            min_similarity=0.1  # Lower threshold for testing
        )
        
        return jsonify({
            'success': True,
            'user_email': email,
            'user_name': user_profile.get('personal_info', {}).get('full_name', 'Unknown'),
            'total_profiles_available': len(all_profiles),
            'ml_algorithm_working': True,
            'sample_similarity_score': similarity_score,
            'sample_breakdown': breakdown,
            'matches_found': len(matches),
            'matches': matches[:2] if matches else [],  # Return first 2 matches
            'algorithm_weights': student_matcher.default_weights
        })
        
    except Exception as e:
        print(f"❌ Manual test failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

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