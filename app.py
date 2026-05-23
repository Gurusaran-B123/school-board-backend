from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from datetime import datetime
import os
from functools import wraps

# Initialize Flask App
app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://school-board-frontend-snowy.vercel.app"
        ]
    }
}, supports_credentials=True)

# Supabase Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_KEY in environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# ===== HELPER FUNCTIONS =====

def validate_youtube_url(url):
    """Validate if URL is a valid YouTube URL"""
    if not url:
        return True
    return 'youtube.com' in url or 'youtu.be' in url

# ===== AUTHENTICATION ROUTES =====

@app.route('/api/login', methods=['POST'])
def login():
    """Login endpoint for students and parents
    
    CHANGED: Now uses Name + Key instead of Name + DOB
    
    Expected JSON body:
    {
        "name": "John",
        "key": "123",
        "role": "student" or "parent"
    }
    """
    try:
        data = request.get_json()
        
        # Validate input
        if not data.get('name') or not data.get('key') or not data.get('role'):
            return jsonify({'message': 'Missing required fields'}), 400
        
        name = data['name'].strip()
        key = data['key'].strip()
        role = data['role']
        
        if role not in ['student', 'parent']:
            return jsonify({'message': 'Invalid role'}), 400
        
        # Determine table based on role
        table = 'students' if role == 'student' else 'parents'
        
        # Query database - Check name AND key
        response = supabase.table(table).select('*').eq('key', key).execute()
        
        if not response.data:
            return jsonify({'message': 'Invalid name or key'}), 401
        
        user = response.data[0]
        
        # Return user info
        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': user['id'],
                'name': user['name'],
                'key': user['key'],
                'role': role
            }
        }), 200
    
    except Exception as e:
        return jsonify({'message': f'Server error: {str(e)}'}), 500


@app.route('/api/admin/create', methods=['POST'])
def create_admin():
    try:
        data = request.get_json()

        name = data.get('name')
        key = data.get('key')

        if not name or not key:
            return jsonify({'message': 'Missing fields'}), 400

        response = supabase.table('parents').insert({
            'name': name,
            'key': key
        }).execute()

        return jsonify({
            'message': 'Admin created successfully',
            'admin': response.data[0]
        }), 201

    except Exception as e:
        return jsonify({'message': str(e)}), 500

# ===== CONTENT ROUTES =====

@app.route('/api/content', methods=['POST'])
def create_content():
    """Create new content (parents only)
    
    Expected JSON body:
    {
        "parent_id": 1,
        "text": "Message text",
        "youtube_link": "https://www.youtube.com/watch?v=..."
    }
    """
    try:
        data = request.get_json()
        
        # Validate input
        if not data.get('parent_id'):
            return jsonify({'message': 'Parent ID required'}), 400
        
        text = data.get('text', '').strip()
        youtube_link = data.get('youtube_link', '').strip()
        
        if not text and not youtube_link:
            return jsonify({'message': 'Please provide text or YouTube link'}), 400
        
        if youtube_link and not validate_youtube_url(youtube_link):
            return jsonify({'message': 'Invalid YouTube URL'}), 400
        
        # Get parent name and key
        parent_response = supabase.table('parents').select('name, key').eq('id', data['parent_id']).execute()
        
        if not parent_response.data:
            return jsonify({'message': 'Parent not found'}), 404
        
        parent_name = parent_response.data[0]['name']
        parent_key = parent_response.data[0]['key']
        
        # Insert content with parent's key
        content_data = {
            'parent_id': data['parent_id'],
            'parent_name': parent_name,
            'key': parent_key,
            'text': text,
            'youtube_link': youtube_link,
            'created_at': datetime.utcnow().isoformat()
        }
        
        response = supabase.table('content').insert(content_data).execute()
        
        return jsonify({
            'message': 'Content created successfully',
            'content': response.data[0]
        }), 201
    
    except Exception as e:
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/content', methods=['GET'])
def get_content():
    """Get all content
    
    Returns all content in reverse chronological order
    """
    try:
        response = supabase.table('content').select('*').order('created_at', desc=True).execute()
        
        return jsonify({
            'message': 'Content retrieved successfully',
            'content': response.data
        }), 200
    
    except Exception as e:
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/content/<int:content_id>', methods=['DELETE'])
def delete_content(content_id):
    """Delete content (parents only)
    """
    try:
        # Delete content
        response = supabase.table('content').delete().eq('id', content_id).execute()
        
        return jsonify({
            'message': 'Content deleted successfully'
        }), 200
    
    except Exception as e:
        return jsonify({'message': f'Server error: {str(e)}'}), 500

# ===== UTILITY ROUTES =====

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint
    """
    return jsonify({'status': 'ok', 'message': 'Server is running'}), 200

# ===== ERROR HANDLERS =====

@app.errorhandler(404)
def not_found(error):
    return jsonify({'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'message': 'Internal server error'}), 500

# ===== RUN SERVER =====

if __name__ == '__main__':
    # For development
    app.run(debug=True, host='0.0.0.0', port=5000)
    
    # For production, use:
    # gunicorn app:app --bind 0.0.0.0:5000
