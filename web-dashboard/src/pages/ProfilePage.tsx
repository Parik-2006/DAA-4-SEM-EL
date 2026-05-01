import React, { useState, useEffect } from 'react';
import { Layout } from '../components';

export const ProfilePage: React.FC = () => {
  const [profile, setProfile] = useState({
    id: '',
    name: '',
    email: '',
    role: '',
    department: '',
    phoneNumber: '',
  });

  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    // Fetch user profile
    const fetchProfile = async () => {
      try {
        // Add API call here
        setProfile({
          id: 'FAC001',
          name: 'John Doe',
          email: 'john@example.com',
          role: 'Faculty',
          department: 'Computer Science',
          phoneNumber: '+91-9876543210',
        });
      } catch (error) {
        console.error('Error fetching profile:', error);
      }
    };

    fetchProfile();
  }, []);

  const handleUpdate = async () => {
    try {
      // Add API call here
      setIsEditing(false);
    } catch (error) {
      console.error('Error updating profile:', error);
    }
  };

  return (
    <Layout>
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-800 mb-6">Profile</h1>

        <div className="bg-white rounded-lg shadow-md p-6 space-y-4">
          <div>
            <label className="block text-gray-700 font-semibold mb-2">Name</label>
            <input
              type="text"
              value={profile.name}
              onChange={(e) => setProfile({ ...profile, name: e.target.value })}
              disabled={!isEditing}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg disabled:bg-gray-50"
            />
          </div>

          <div>
            <label className="block text-gray-700 font-semibold mb-2">Email</label>
            <input
              type="email"
              value={profile.email}
              disabled
              className="w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-50"
            />
          </div>

          <div>
            <label className="block text-gray-700 font-semibold mb-2">
              Department
            </label>
            <input
              type="text"
              value={profile.department}
              onChange={(e) => setProfile({ ...profile, department: e.target.value })}
              disabled={!isEditing}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg disabled:bg-gray-50"
            />
          </div>

          <div>
            <label className="block text-gray-700 font-semibold mb-2">
              Phone Number
            </label>
            <input
              type="tel"
              value={profile.phoneNumber}
              onChange={(e) => setProfile({ ...profile, phoneNumber: e.target.value })}
              disabled={!isEditing}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg disabled:bg-gray-50"
            />
          </div>

          <div className="flex gap-4 pt-4">
            {!isEditing ? (
              <button
                onClick={() => setIsEditing(true)}
                className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
              >
                Edit
              </button>
            ) : (
              <>
                <button
                  onClick={handleUpdate}
                  className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                >
                  Save
                </button>
                <button
                  onClick={() => setIsEditing(false)}
                  className="px-6 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
                >
                  Cancel
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
};
