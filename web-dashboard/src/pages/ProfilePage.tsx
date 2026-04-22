import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, Mail, Shield, Clock, Edit2, Save, X, Camera } from 'lucide-react';
import { FirebaseAuthService } from '../services/firebase/auth.service';
import { FirebaseException } from '../services/firebase/exception-handler';
import apiClient from '../services/api';

interface BackendProfile {
  user_id: string;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
}

export const ProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const authService = FirebaseAuthService.getInstance();

  const [backendProfile, setBackendProfile] = useState<BackendProfile | null>(null);
  const [profile, setProfile] = useState({
    displayName: '',
    email: '',
    photoUrl: '',
    lastLogin: '',
    emailVerified: false,
    createdAt: '',
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    setLoading(true);
    setError(null);
    try {
      const user = authService.currentUser;
      if (!user) {
        navigate('/login');
        return;
      }

      // Load Firebase user data
      setProfile({
        displayName: user.displayName || '',
        email: user.email || '',
        photoUrl: user.photoURL || '',
        lastLogin: user.metadata?.lastSignInTime
          ? new Date(user.metadata.lastSignInTime).toLocaleString()
          : 'N/A',
        emailVerified: user.emailVerified,
        createdAt: user.metadata?.creationTime
          ? new Date(user.metadata.creationTime).toLocaleString()
          : 'N/A',
      });

      // Try to load backend profile (role, etc.)
      // The backend stores user_id in localStorage after login
      const userId = localStorage.getItem('user_id');
      if (userId) {
        try {
          const response = await apiClient.get<BackendProfile>(`/api/v1/user/profile/${userId}`);
          setBackendProfile(response.data);
        } catch {
          // Backend profile optional – Firebase data is the fallback
        }
      } else {
        // Try fetching by email via admin endpoint
        try {
          const response = await apiClient.get('/api/v1/users/by-role/admin');
          const users: BackendProfile[] = response.data?.users || [];
          const match = users.find((u) => u.email === user.email);
          if (match) setBackendProfile(match);
          else {
            // try student role
            const sRes = await apiClient.get('/api/v1/users/by-role/student');
            const sUsers: BackendProfile[] = sRes.data?.users || [];
            const sMatch = sUsers.find((u) => u.email === user.email);
            if (sMatch) setBackendProfile(sMatch);
          }
        } catch {
          // Silently skip – role display is optional
        }
      }
    } catch (err) {
      setError('Failed to load profile information.');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await authService.updateProfile({
        displayName: profile.displayName,
        photoUrl: profile.photoUrl,
      });
      setSuccess('Profile updated successfully!');
      setEditMode(false);
      setTimeout(() => setSuccess(null), 4000);
    } catch (err) {
      if (err instanceof FirebaseException) {
        setError(err.userMessage);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to save profile. Please try again.');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setEditMode(false);
    loadProfile(); // Reset to saved values
  };

  const getRoleBadgeColor = (role?: string) => {
    if (!role) return 'bg-gray-100 text-gray-600';
    if (role === 'admin') return 'bg-purple-100 text-purple-700';
    return 'bg-blue-100 text-blue-700';
  };

  const getInitials = (name: string) => {
    if (!name) return '?';
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
          <p className="text-gray-600 font-medium">Loading profile...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-2xl mx-auto space-y-6">

        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">My Profile</h1>
          <p className="text-gray-500 mt-1">Manage your account information</p>
        </div>

        {/* Alerts */}
        {error && (
          <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-xl">
            <X size={18} className="text-red-500 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}
        {success && (
          <div className="flex items-start gap-3 p-4 bg-green-50 border border-green-200 rounded-xl">
            <Save size={18} className="text-green-500 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-green-700">{success}</p>
          </div>
        )}

        {/* Avatar + Name Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
          <div className="flex items-center gap-6">
            {/* Avatar */}
            <div className="relative">
              {profile.photoUrl ? (
                <img
                  src={profile.photoUrl}
                  alt={profile.displayName}
                  className="w-20 h-20 rounded-full object-cover border-4 border-indigo-100"
                />
              ) : (
                <div className="w-20 h-20 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-2xl font-bold border-4 border-indigo-100">
                  {getInitials(backendProfile?.name || profile.displayName)}
                </div>
              )}
              {editMode && (
                <div className="absolute -bottom-1 -right-1 w-7 h-7 bg-indigo-600 rounded-full flex items-center justify-center cursor-pointer hover:bg-indigo-700 transition-colors">
                  <Camera size={14} className="text-white" />
                </div>
              )}
            </div>

            {/* Name + Role */}
            <div className="flex-1">
              <h2 className="text-xl font-bold text-gray-900">
                {backendProfile?.name || profile.displayName || 'No name set'}
              </h2>
              <p className="text-gray-500 text-sm mt-0.5">{profile.email}</p>
              <div className="flex items-center gap-2 mt-2">
                {backendProfile?.role ? (
                  <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getRoleBadgeColor(backendProfile.role)}`}>
                    <Shield size={10} className="inline mr-1" />
                    {backendProfile.role.charAt(0).toUpperCase() + backendProfile.role.slice(1)}
                  </span>
                ) : (
                  <span className="px-3 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-600">
                    User
                  </span>
                )}
                {profile.emailVerified && (
                  <span className="px-3 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-700">
                    ✓ Verified
                  </span>
                )}
                {backendProfile?.is_active === false && (
                  <span className="px-3 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-700">
                    Inactive
                  </span>
                )}
              </div>
            </div>

            {/* Edit Toggle */}
            {!editMode ? (
              <button
                onClick={() => setEditMode(true)}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-50 text-indigo-600 rounded-lg hover:bg-indigo-100 transition-colors font-medium text-sm"
              >
                <Edit2 size={15} />
                Edit
              </button>
            ) : null}
          </div>
        </div>

        {/* Editable Fields */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-5">
          <h3 className="font-semibold text-gray-900 text-lg flex items-center gap-2">
            <User size={18} className="text-indigo-500" />
            Account Details
          </h3>

          {/* Display Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Display Name
            </label>
            {editMode ? (
              <input
                type="text"
                value={profile.displayName}
                onChange={(e) => setProfile({ ...profile, displayName: e.target.value })}
                placeholder="Enter your name"
                className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
              />
            ) : (
              <p className="px-4 py-2.5 bg-gray-50 rounded-lg text-gray-800 font-medium">
                {backendProfile?.name || profile.displayName || '—'}
              </p>
            )}
          </div>

          {/* Email (read-only) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Email Address
            </label>
            <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-50 rounded-lg">
              <Mail size={16} className="text-gray-400" />
              <p className="text-gray-800 font-medium">{profile.email}</p>
              <span className="ml-auto text-xs text-gray-400">(read-only)</span>
            </div>
          </div>

          {/* Photo URL */}
          {editMode && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Photo URL <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <input
                type="url"
                value={profile.photoUrl}
                onChange={(e) => setProfile({ ...profile, photoUrl: e.target.value })}
                placeholder="https://example.com/photo.jpg"
                className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
              />
            </div>
          )}

          {/* Role (read-only from backend) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Role
            </label>
            <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-50 rounded-lg">
              <Shield size={16} className="text-gray-400" />
              <p className="text-gray-800 font-medium capitalize">
                {backendProfile?.role || 'Not assigned'}
              </p>
            </div>
          </div>

          {/* Edit Buttons */}
          {editMode && (
            <div className="flex gap-3 pt-2">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white rounded-lg font-medium transition-colors"
              >
                {saving ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Save size={16} />
                )}
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
              <button
                onClick={handleCancel}
                disabled={saving}
                className="flex items-center gap-2 px-5 py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-medium transition-colors"
              >
                <X size={16} />
                Cancel
              </button>
            </div>
          )}
        </div>

        {/* Account Metadata */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
          <h3 className="font-semibold text-gray-900 text-lg flex items-center gap-2 mb-4">
            <Clock size={18} className="text-indigo-500" />
            Session Information
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center py-2 border-b border-gray-50">
              <span className="text-sm text-gray-500">Account Created</span>
              <span className="text-sm font-medium text-gray-800">{profile.createdAt}</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-50">
              <span className="text-sm text-gray-500">Last Sign In</span>
              <span className="text-sm font-medium text-gray-800">{profile.lastLogin}</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-50">
              <span className="text-sm text-gray-500">Email Verified</span>
              <span className={`text-sm font-semibold ${profile.emailVerified ? 'text-green-600' : 'text-red-500'}`}>
                {profile.emailVerified ? 'Yes' : 'No'}
              </span>
            </div>
            {backendProfile?.user_id && (
              <div className="flex justify-between items-center py-2">
                <span className="text-sm text-gray-500">User ID</span>
                <span className="text-xs font-mono text-gray-600 bg-gray-100 px-2 py-1 rounded">
                  {backendProfile.user_id}
                </span>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};
