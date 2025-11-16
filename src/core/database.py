from pymongo import MongoClient, ASCENDING
import gridfs
from datetime import datetime
import os
from .config import Config
from bson import ObjectId

class DatabaseManager:
    def __init__(self):
        self.client = None
        self.db = None
        self.fs = None  # GridFS for file storage
        self.connect()
    
    def connect(self):
        try:
            self.client = MongoClient(
                Config.MONGODB_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000
            )
            self.db = self.client[Config.DATABASE_NAME]
            self.fs = gridfs.GridFS(self.db)
            
            self.client.admin.command('ismaster')
            print("Connected to MongoDB Atlas")
            self.setup_collections()
            
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            self.client = None
            self.db = None
            self.fs = None
    
    def setup_collections(self):
        """Setup database collections and indexes"""
        if self.db is None:
            return
        
        # Profiles collection
        profiles = self.db.profiles
        
        # Create indexes for better performance
        profiles.create_index([("personal_info.email", ASCENDING)], unique=True)
        profiles.create_index([("created_at", ASCENDING)])
        profiles.create_index([("status", ASCENDING)])
        profiles.create_index([("skills.technical", ASCENDING)])
        profiles.create_index([("preferences.study_subjects", ASCENDING)])
        
        print("Database collections and indexes setup complete!")
    
    def save_profile(self, profile_data, force_new_id=False):
        """Save user profile to database
        
        Args:
            profile_data (dict): Profile data to save
            force_new_id (bool): If True, always create new profile even if email exists
        """
        if self.db is None:
            raise Exception("Database not connected")
        
        # Add metadata
        profile_data['created_at'] = datetime.utcnow()
        profile_data['updated_at'] = datetime.utcnow()
        profile_data['status'] = 'active'
        profile_data['version'] = '1.0'
        
        # Validate required fields
        if not profile_data.get('personal_info', {}).get('email'):
            raise Exception("Email is required")
        
        try:
            result = self.db.profiles.insert_one(profile_data)
            return str(result.inserted_id)
        except Exception as e:
            if 'duplicate key' in str(e).lower() and not force_new_id:
                # Update existing profile only if force_new_id is False
                email = profile_data['personal_info']['email']
                profile_data['updated_at'] = datetime.utcnow()
                profile_data.pop('created_at', None)  # Don't update created_at
                
                result = self.db.profiles.update_one(
                    {"personal_info.email": email},
                    {"$set": profile_data}
                )
                
                if result.matched_count > 0:
                    # Get the profile ID
                    existing_profile = self.db.profiles.find_one({"personal_info.email": email})
                    return str(existing_profile['_id'])
                else:
                    raise Exception("Failed to update existing profile")
            elif 'duplicate key' in str(e).lower() and force_new_id:
                # Generate new unique email or ID to force creation of new profile
                import time
                original_email = profile_data['personal_info']['email']
                timestamp = int(time.time() * 1000)  # milliseconds since epoch
                
                # Modify email to make it unique while preserving original in backup
                profile_data['personal_info']['email'] = f"{original_email}.{timestamp}"
                profile_data['original_email'] = original_email
                
                # Try again with modified email
                result = self.db.profiles.insert_one(profile_data)
                return str(result.inserted_id)
            else:
                raise e
    
    def get_profile_by_email(self, email):
        """Get profile by email"""
        if self.db is None:
            return None
        
        return self.db.profiles.find_one({"personal_info.email": email})
    
    def get_all_profiles(self, limit=100):
        """Get all profiles (for matching purposes)"""
        if self.db is None:
            return []
        
        return list(self.db.profiles.find({"status": "active"}).limit(limit))
    
    def update_profile(self, profile_id, updates):
        """Update existing profile"""
        if self.db is None:
            raise Exception("Database not connected")
        
        from bson import ObjectId
        
        updates['updated_at'] = datetime.utcnow()
        
        result = self.db.profiles.update_one(
            {"_id": ObjectId(profile_id)},
            {"$set": updates}
        )
        
        return result.modified_count > 0
    
    def delete_profile(self, profile_id):
        """Soft delete profile (mark as inactive)"""
        if self.db is None:
            raise Exception("Database not connected")
        
        from bson import ObjectId
        
        result = self.db.profiles.update_one(
            {"_id": ObjectId(profile_id)},
            {"$set": {"status": "deleted", "updated_at": datetime.utcnow()}}
        )
        
        return result.modified_count > 0
    
    def get_database_stats(self):
        """Get database statistics"""
        if self.db is None:
            return {"error": "Database not connected"}
        
        try:
            profiles_count = self.db.profiles.count_documents({"status": "active"})
            total_profiles = self.db.profiles.count_documents({})
            
            # Get some sample skills for statistics
            pipeline = [
                {"$match": {"status": "active"}},
                {"$unwind": "$skills.technical"},
                {"$group": {"_id": "$skills.technical", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10}
            ]
            
            top_skills = list(self.db.profiles.aggregate(pipeline))
            
            return {
                "active_profiles": profiles_count,
                "total_profiles": total_profiles,
                "top_technical_skills": top_skills,
                "database_name": Config.DATABASE_NAME,
                "collections": self.db.list_collection_names()
            }
        except Exception as e:
            return {"error": str(e)}
    
    def store_pdf(self, file_data, filename, profile_id, metadata=None):
        """Store PDF file in MongoDB using GridFS"""
        try:
            if self.fs is None:
                print("GridFS not initialized")
                return None
            
            # Prepare metadata for GridFS
            file_metadata = {
                'profile_id': profile_id,
                'original_filename': filename,
                'content_type': 'application/pdf',
                'upload_date': datetime.utcnow(),
                **(metadata or {})
            }
            
            # Store file using GridFS
            file_id = self.fs.put(
                file_data,
                filename=filename,
                metadata=file_metadata
            )
            
            print(f"✅ PDF stored successfully with ID: {file_id}")
            return file_id
            
        except Exception as e:
            print(f"❌ Error storing PDF: {e}")
            return None
    
    def get_pdf(self, file_id):
        """Retrieve PDF file from GridFS"""
        try:
            if self.fs is None:
                return None
            
            from bson import ObjectId
            file_doc = self.fs.get(ObjectId(file_id))
            
            return {
                'data': file_doc.read(),
                'filename': file_doc.filename,
                'metadata': file_doc.metadata
            }
            
        except Exception as e:
            print(f"Error retrieving PDF: {e}")
            return None
    


# Global database manager instance
db_manager = DatabaseManager()