import React, { useState, useEffect } from 'react';
import { FirebaseAuthService } from '../services/firebase/auth.service';
import { FirebaseException } from '../services/firebase/exception-handler';

export const ProfilePage: React.FC = () => {
  const [profile, setProfile] = useState({
    displayName: '',
    email: '',
    photoUrl: '',
    lastLogin: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);

  const authService = FirebaseAuthService.getInstance();

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = () => {
    try {
      const user = authService.currentUser;
      if (user) {
        setProfile({
          displayName: user.displayName || '',
          email: user.email || '',
          photoUrl: user.photoURL || '',
          lastLogin: user.metadata?.lastSignInTime?.toLocaleString() || 'Never',
        });
      }
    } catch (err) {
      setError('Failed to load profile');
    }
  };

  const handleSaveProfile = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      await authService.updateProfile({
        displayName: profile.displayName,
        photoUrl: profile.photoUrl,
      });
      setSuccess('Profile updated successfully!');
      setEditMode(false);
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      if (err instanceof FirebaseException) {
        setError(err.userMessage);
      } else if (err instanceof Error) {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md mx-auto bg-white rounded-lg shadow p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">My Profile</h1>

        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {success && (
          <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg">
            <p className="text-green-700">{success}</p>
          </div>
        )}

        <div className="space-y-4">
          {/* Display Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Display Name
            </label>
            <input
              type="text"
              value={profile.displayName}
              onChange={(e) =>
                setProfile({ ...profile, displayName: e.target.value })
              }
              disabled={!editMode || loading}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg disabled:bg-gray-100"
            />
          </div>

          {/* Email (Read-only) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email Address
            </label>
            <input
              type="email"
              value={profile.email}
              disabled
              className="w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-100"
            />
          </div>

          {/* Photo URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Photo URL
            </label>
            <input
              type="url"
              value={profile.photoUrl}
              onChange={(e) =>
                setProfile({ ...profile, photoUrl: e.target.value })
              }
              disabled={!editMode || loading}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg disabled:bg-gray-100"
            />
          </div>

          {/* Last Login */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Last Login
            </label>
            <p className="px-4 py-2 text-gray-600">{profile.lastLogin}</p>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 mt-6">
            {!editMode ? (
              <button
                onClick={() => setEditMode(true)}
                className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white py-2 rounded-lg"
              >
                Edit Profile
              </button>
            ) : (
              <>
                <button
                  onClick={handleSaveProfile}
                  disabled={loading}
                  className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white py-2 rounded-lg"
                >
                  {loading ? 'Saving...' : 'Save'}
                </button>
                <button
                  onClick={() => {
                    setEditMode(false);
                    loadProfile();
                  }}
                  className="flex-1 bg-gray-600 hover:bg-gray-700 text-white py-2 rounded-lg"
                >
                  Cancel
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
