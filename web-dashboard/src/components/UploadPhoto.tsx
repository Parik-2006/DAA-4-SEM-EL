import React, { useState, useRef } from 'react';
import { Upload, Loader, X } from 'lucide-react';
import { attendanceAPI } from '@/services/api';
import { Card, Button } from '@/components';

interface UploadPhotoProps {
  onAttendanceMarked: (data: any) => void;
  onProcessing: (isProcessing: boolean) => void;
  isLoading: boolean;
}

export const UploadPhotoComponent: React.FC<UploadPhotoProps> = ({
  onAttendanceMarked,
  onProcessing,
  isLoading,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];

    if (!file) return;

    // Validate file type
    const validTypes = ['image/jpeg', 'image/jpg', 'image/png'];
    if (!validTypes.includes(file.type)) {
      setError('Please select a JPG or PNG image');
      return;
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      setError('File size must be less than 10MB');
      return;
    }

    setSelectedFile(file);
    setError(null);

    // Create preview
    const reader = new FileReader();
    reader.onload = (e) => {
      setPreview(e.target?.result as string);
    };
    reader.readAsDataURL(file);
  };

  const clearSelection = () => {
    setSelectedFile(null);
    setPreview(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleMarkAttendance = async () => {
    if (!selectedFile) {
      setError('Please select a photo first');
      return;
    }

    try {
      setError(null);
      onProcessing(true);

      const formData = new FormData();
      formData.append('file', selectedFile);

      const result = await attendanceAPI.detectAndMarkAttendance(formData);

      if (result.matched) {
        onAttendanceMarked({
          status: 'success',
          message: `Attendance marked for ${result.student_name}`,
          student_name: result.student_name,
          student_id: result.student_id,
          confidence: result.confidence,
        });

        // Clear selection after success
        setTimeout(() => {
          clearSelection();
        }, 2000);
      } else {
        onAttendanceMarked({
          status: 'error',
          message: result.message || 'No student matched. Please try another photo.',
        });
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to process image';
      setError(errorMsg);
      onAttendanceMarked({
        status: 'error',
        message: errorMsg,
      });
    } finally {
      onProcessing(false);
    }
  };

  return (
    <Card>
      <div className="space-y-4">
        {/* Upload Area */}
        <div
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-all"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/jpg,image/png"
            onChange={handleFileSelect}
            className="hidden"
          />

          {!preview ? (
            <div className="flex flex-col items-center gap-2">
              <Upload className="text-gray-400" size={48} />
              <div>
                <p className="text-gray-700 font-medium">Click to upload or drag and drop</p>
                <p className="text-gray-500 text-sm">JPG or PNG, max 10MB</p>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <img
                src={preview}
                alt="Preview"
                className="max-h-64 rounded-lg object-contain"
              />
              <p className="text-sm text-gray-600 font-medium">{selectedFile?.name}</p>
            </div>
          )}
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-800 text-sm flex items-start gap-2">
            <X size={16} className="flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          {selectedFile ? (
            <>
              <Button
                onClick={handleMarkAttendance}
                className="flex-1 bg-green-600 hover:bg-green-700"
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <Loader className="animate-spin mr-2" size={18} />
                    Processing...
                  </>
                ) : (
                  <>
                    <Upload size={18} className="mr-2" />
                    Mark Attendance
                  </>
                )}
              </Button>
              <Button
                onClick={clearSelection}
                className="flex-1 bg-gray-300 hover:bg-gray-400"
                disabled={isLoading}
              >
                Clear
              </Button>
            </>
          ) : (
            <Button
              onClick={() => fileInputRef.current?.click()}
              className="w-full bg-blue-600 hover:bg-blue-700"
              disabled={isLoading}
            >
              <Upload size={18} className="mr-2" />
              Select Photo
            </Button>
          )}
        </div>

        {/* Info */}
        <div className="bg-gray-50 rounded-lg p-3 text-sm text-gray-700">
          <p className="font-medium mb-1">How it works</p>
          <ul className="space-y-1 text-xs">
            <li>✓ Select a clear photo of your face</li>
            <li>✓ Ensure good lighting</li>
            <li>✓ Click "Mark Attendance" to process</li>
            <li>✓ System will match your face and mark attendance</li>
          </ul>
        </div>
      </div>
    </Card>
  );
};
