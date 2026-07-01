from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
import os

# Initialize Flask App
app = Flask(__name__)

# Allow your Vercel frontend to access this API
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://school-board-frontend-snowy.vercel.app"
        ]
    }
})

# Supabase Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
print(f"DEBUG URL: {repr(SUPABASE_URL)}")
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
print(f"DEBUG KEY LEN: {len(SUPABASE_KEY) if SUPABASE_KEY else 0}")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_KEY in Render environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===== AUTHENTICATION ROUTE =====
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        key = data.get('key', '').strip()
        role = data.get('role', '').lower() # 'admin' or 'student'

        if not name or not key or not role:
            return jsonify({'message': 'Missing name, key, or role'}), 400

        if role == 'admin':
            # Check if Admin exists with this name AND key
            response = supabase.table('admins').select('*').eq('name', name).eq('key', key).execute()
            
            if not response.data:
                return jsonify({'message': 'Admin login failed. Name or Key is incorrect.'}), 401
            
            user = response.data[0]

        elif role == 'student':
            # 1. First, check if the Key provided belongs to ANY valid Admin
            admin_check = supabase.table('admins').select('name').eq('key', key).execute()
            
            if not admin_check.data:
                return jsonify({'message': 'Invalid Key. No Admin found with this code.'}), 401
            
            # 2. Key is valid. Now, check if student exists or create them (pairing)
            # Use upsert to prevent duplicate students for the same key
            student_response = supabase.table('students').upsert({
                'name': name,
                'key': key
            }, on_conflict='name,key').execute()
            
            user = student_response.data[0]

        else:
            return jsonify({'message': 'Invalid role specified'}), 400

        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': user['id'],
                'name': name,
                'key': key,
                'role': role
            }
        }), 200

    except Exception as e:
        print(f"Login Error: {str(e)}")
        return jsonify({'message': 'Internal Server Error'}), 500

# ===== CONTENT ROUTES (THE PAIRING LOGIC) =====

@app.route('/api/content', methods=['POST'])
def create_content():
    """Admin uploads a video and comment using their unique key"""
    try:
        data = request.get_json()
        
        # We use 'pair_key' to link the content to a specific Admin/Student group
        content_data = {
            'pair_key': data.get('key'),
            'admin_name': data.get('name'),
            'text_comment': data.get('text', ''),
            'youtube_url': data.get('youtube_url', '')
        }
        
        if not content_data['pair_key'] or not content_data['youtube_url']:
            return jsonify({'message': 'Key and YouTube URL are required'}), 400

        response = supabase.table('content').insert(content_data).execute()
        
        return jsonify({'message': 'Shared successfully', 'data': response.data[0]}), 201
    
    except Exception as e:
        return jsonify({'message': f'Upload error: {str(e)}'}), 500

@app.route('/api/content/<key>', methods=['GET'])
def get_content(key):
    """Students and Admins fetch only content matching their shared key"""
    try:
        response = supabase.table('content').select('*').eq('pair_key', key).order('created_at', desc=True).execute()
        
        return jsonify(response.data), 200
    
    except Exception as e:
        return jsonify({'message': f'Fetch error: {str(e)}'}), 500

# ===== HEALTH & ERROR HANDLING =====

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'online'}), 200

@app.errorhandler(404)
def not_found(e):
    return jsonify({'message': 'API route not found'}), 404

# ===== RUN SERVER =====

if __name__ == '__main__':
    # Render binds to the PORT environment variable
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
